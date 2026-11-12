from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import io
import json
import time
import uuid
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from production.auth import Authenticator
from production.app import create_app
from production.db import one,Database
from production.service import reserve,settle,now
from production.worker import Worker,DefinitePreacceptFailure

PAYLOAD={'request_id':'test_request_1','kind':'tts','text':'hello','voice_id':'voice','provider':'test','model_id':'model','language_code':'en','voice_settings':{}}
# Minimal valid 1x1 PNG (IHDR+IDAT+IEND).
VALID_PNG=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82'

def test_rls_and_no_owner_bypass(database,owner,user):
    stranger=uuid.uuid4()
    with database.transaction(stranger) as tx:
        assert one(tx,'SELECT * FROM wallets WHERE user_id=:u',u=user) is None
        assert tx.execute(text('SELECT current_user')).scalar()=='voicegen_api'
        assert not tx.execute(text('SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user')).scalar()
    with pytest.raises(RuntimeError,match='bypass RLS'):
        with Database(owner.url).transaction(): pass
    with database.transaction(user) as tx:
        with pytest.raises(DBAPIError): tx.execute(text('UPDATE users SET is_admin=true WHERE id=:u'),{'u':user})

def test_concurrent_idempotency_and_wallet(database,user):
    def submit(_):
        with database.transaction(user) as tx: return str(reserve(tx,user,PAYLOAD,2)['id'])
    with ThreadPoolExecutor(max_workers=8) as executor: ids=list(executor.map(submit,range(16)))
    assert len(set(ids))==1
    with database.transaction(user) as tx:
        w=one(tx,'SELECT * FROM wallets WHERE user_id=:u',u=user)
        assert (w['available'],w['reserved'])==(9990,10)
        assert one(tx,'SELECT expires_at-created_at AS ttl FROM generations WHERE user_id=:u',u=user)['ttl']==timedelta(hours=24)
        assert one(tx,'SELECT count(*) AS n FROM outbox WHERE user_id=:u',u=user)['n']==1
    with pytest.raises(HTTPException) as error:
        with database.transaction(user) as tx: reserve(tx,user,{**PAYLOAD,'text':'different'},2)
    assert error.value.status_code==409

def test_overdraft_parallel(database,user):
    def submit(i):
        try:
            with database.transaction(user) as tx: reserve(tx,user,{**PAYLOAD,'request_id':f'request_{i}'},1000)
            return True
        except HTTPException as e: assert e.status_code==402; return False
    with ThreadPoolExecutor(max_workers=8) as executor: results=list(executor.map(submit,range(8)))
    assert sum(results)==2
    with database.transaction(user) as tx:
        assert one(tx,'SELECT available,reserved FROM wallets WHERE user_id=:u',u=user)=={'available':0,'reserved':10000}

def test_refund_once_and_immutable(database,user):
    with database.transaction(user) as tx: ident=reserve(tx,user,PAYLOAD,2)['id']
    for _ in range(3):
        with database.transaction(user) as tx: settle(tx,ident,False)
    with database.transaction(user) as tx:
        assert one(tx,'SELECT available,reserved FROM wallets WHERE user_id=:u',u=user)=={'available':10000,'reserved':0}
    for sql in ['UPDATE ledger SET available_delta=0','DELETE FROM ledger','TRUNCATE ledger']:
        with pytest.raises(DBAPIError):
            with database.transaction(user) as tx: tx.execute(text(sql))

class FakeStorage:
    from production.storage import PrivateStorage
    key=staticmethod(PrivateStorage.key)
    def __init__(self): self.objects={}; self.calls=[]
    def put(self,key,data,content_type): self.objects[key]=(data,content_type)
    def get(self,key,byte_range=None):
        self.calls.append((key,byte_range)); data,kind=self.objects[key]; total=len(data); result={}
        if byte_range:
            import re
            from fastapi import HTTPException
            if not re.fullmatch(r'bytes=\d+-\d*',byte_range): raise HTTPException(416,'range')
            start,end=byte_range[6:].split('-'); start=int(start); end=int(end) if end else total-1
            data=data[start:end+1]; result['ContentRange']=f'bytes {start}-{end}/{total}'
        return {**result,'Body':io.BytesIO(data),'ContentLength':len(data),'ContentType':kind}

@pytest.fixture
def auth():
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    authenticator=Authenticator('https://auth.example.test','authenticated','https://auth.example.test/jwks')
    class Key: key=private.public_key()
    authenticator.jwks.get_signing_key_from_jwt=lambda token: Key()
    def token(user,**kw):
        claims={'sub':str(user),'iat':int(time.time()),'exp':int(time.time())+300,'iss':'https://auth.example.test','aud':'authenticated','email':'test@example.test','user_metadata':{'is_admin':True},**kw}
        return jwt.encode(claims,private,algorithm='RS256',headers={'kid':'fixture'})
    return authenticator,token

@pytest.fixture
def client(database,auth):
    storage=FakeStorage()
    app=create_app({'APP_ORIGIN':'https://app.example.test','DATABASE_URL':'unused','SUPPLIER_ENABLED':'true','CREDIT_PER_CHARACTER':'2','SUPABASE_URL':'https://auth.example.test','SUPABASE_ANON_KEY':'public-anon-fixture'},auth=auth[0],storage=storage,database=database)
    with TestClient(app,base_url='https://app.example.test',headers={'origin':'https://app.example.test'}) as client:
        client.storage=storage
        yield client

def login(client,auth,user):
    response=client.post('/api/session',json={'access_token':auth[1](user)})
    assert response.status_code==200,response.text
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']

def test_jwt_boundaries(client,auth,user):
    assert client.get('/api/me').status_code==401
    for claims in [{'exp':int(time.time())-1},{'iss':'https://evil.test'},{'aud':'wrong'},{'sub':'not-a-uuid'}]:
        assert client.post('/api/session',json={'access_token':auth[1](user,**claims)}).status_code==401
    forged=jwt.encode({'sub':str(user),'exp':int(time.time())+300},'a-secure-length-fixture-hmac-key-12345',algorithm='HS256')
    assert client.post('/api/session',json={'access_token':forged}).status_code==401
    assert client.post('/api/session',json={'token':'owner-staging'}).status_code==422
    login(client,auth,user)
    assert client.get('/api/me').json()['user']['isAdmin'] is False
    assert client.get('/api/admin/topups').status_code==403
    assert client.post('/api/topups',headers={'origin':'https://evil.test'},json={}).status_code==403
    assert client.delete('/api/session').status_code==200
    assert client.get('/api/me').status_code==401

def test_new_user_zero_balance(client,auth):
    user=uuid.uuid4(); login(client,auth,user)
    assert client.get('/api/me').json()['wallet']['available']==0
    assert client.post('/api/generate',json=PAYLOAD).status_code==402

def test_user_history_isolation(client,auth,user):
    login(client,auth,user)
    response=client.post('/api/generate',json=PAYLOAD)
    assert response.status_code==200,response.text
    ident=response.json()['generation']['id']
    assert len(client.get('/api/history').json()['items'])==1
    login(client,auth,uuid.uuid4())
    assert client.get('/api/history').json()['items']==[]
    assert client.get('/api/history/'+ident).status_code==404
    assert client.get('/api/audio/'+ident).status_code==404

def test_manual_topup_independent_approval(client,auth,user,owner):
    login(client,auth,user)
    data={'request_id':'topup_request_1','amount':500,'reference':'bank-transfer-1'}
    response=client.post('/api/topups',json=data); assert response.status_code==200,response.text
    ident=response.json()['topup']['id']
    assert client.post('/api/topups',json=data).json()['topup']['id']==ident
    assert client.post('/api/topups',json={**data,'amount':501}).status_code==409
    assert client.put(f'/api/topups/{ident}/evidence',content=VALID_PNG,headers={'content-type':'image/png'}).status_code==200
    assert client.get('/api/me').json()['wallet']['balance']==10000
    admin=uuid.uuid4(); login(client,auth,admin)
    with owner.begin() as tx: tx.execute(text('UPDATE users SET is_admin=true WHERE id=:u'),{'u':admin})
    assert client.get('/api/admin/topups').status_code==200
    for _ in range(2):
        result=client.post(f'/api/admin/topups/{ident}/approve',json={'verification_reference':f'bank-verified-{ident}'})
        assert result.status_code==200,result.text
    login(client,auth,user)
    assert client.get('/api/me').json()['wallet']['balance']==10500
    with owner.begin() as tx:
        assert tx.execute(text('SELECT count(*) FROM admin_audit WHERE target_id=:i'),{'i':ident}).scalar()==1
        tx.execute(text('UPDATE users SET is_admin=true WHERE id=:u'),{'u':user})
    own=client.post('/api/topups',json={**data,'request_id':'topup_request_self'}).json()['topup']['id']
    assert client.post(f'/api/admin/topups/{own}/approve',json={'verification_reference':'bank-self-reference'}).status_code==403
    with pytest.raises(DBAPIError):
        with owner.begin() as tx: tx.execute(text('DELETE FROM admin_audit'))

def test_audio_ranges_expiry(client,auth,user,database):
    login(client,auth,user)
    ident=client.post('/api/generate',json=PAYLOAD).json()['generation']['id']
    key=client.storage.key(user,ident,'audio'); client.storage.put(key,b'0123456789','audio/mpeg')
    with database.transaction(user) as tx:
        tx.execute(text("UPDATE generations SET state='completed',object_key=:k WHERE id=:id"),{'k':key,'id':ident})
    r=client.get('/api/audio/'+ident,headers={'range':'bytes=2-5'})
    assert r.status_code==206 and r.content==b'2345'
    assert r.headers['content-range']=='bytes 2-5/10'
    assert client.head('/api/audio/'+ident).content==b''
    with database.transaction(user) as tx: tx.execute(text("UPDATE generations SET expires_at=now() WHERE id=:id"),{'id':ident})
    calls=len(client.storage.calls)
    assert client.get('/api/audio/'+ident,headers={'range':'bytes=0-1'}).status_code==410
    assert len(client.storage.calls)==calls
