import io
import json
import logging
import struct
import uuid
import zlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from production.app import create_app
from production.ratelimit import SlidingWindowLimiter
from test_core import FakeStorage, VALID_PNG, login, auth

ENV={'APP_ORIGIN':'https://app.example.test','DATABASE_URL':'unused','SUPPLIER_ENABLED':'true','CREDIT_PER_CHARACTER':'2','SUPABASE_URL':'https://auth.example.test','SUPABASE_ANON_KEY':'public-anon-fixture'}

def make_client(database,auth,env_overrides=None,limiter=None):
    storage=FakeStorage()
    env={**ENV,**(env_overrides or {})}
    app=create_app(env,auth=auth[0],storage=storage,database=database,limiter=limiter or SlidingWindowLimiter(env))
    client=TestClient(app,base_url='https://app.example.test',headers={'origin':'https://app.example.test'})
    client.storage=storage
    return client

def png_with(extra=b''):
    return VALID_PNG+extra

def pdf_with(objects=b''):
    return b'%PDF-1.4\n'+objects+b'\n%%EOF'

def test_session_rate_limit_per_ip(database,auth,user):
    client=make_client(database,auth,{'RATE_LIMIT_SESSION_PER_MINUTE':'3'})
    for _ in range(3):
        assert client.post('/api/session',json={'access_token':auth[1](user)}).status_code==200
    blocked=client.post('/api/session',json={'access_token':auth[1](user)})
    assert blocked.status_code==429
    assert 'retry-after' in {k.lower():v for k,v in blocked.headers.items()}
    assert int(blocked.headers['Retry-After'])>=1

def test_topup_rate_limit_isolated_per_user(database,auth,user):
    client=make_client(database,auth,{'RATE_LIMIT_TOPUP_PER_MINUTE':'2'})
    login(client,auth,user)
    data={'request_id':'topup_rl','amount':100,'reference':'bank-rl'}
    assert client.post('/api/topups',json=data).status_code==200
    assert client.post('/api/topups',json={**data,'request_id':'topup_rl2'}).status_code==200
    assert client.post('/api/topups',json={**data,'request_id':'topup_rl3'}).status_code==429
    # A different user has an independent allowance.
    other=uuid.uuid4(); login(client,auth,other)
    assert client.post('/api/topups',json={'request_id':'other_rl','amount':100,'reference':'bank-other'}).status_code==200

def test_polyglot_png_rejected_valid_accepted(database,auth,user):
    client=make_client(database,auth)
    login(client,auth,user)
    ident=client.post('/api/topups',json={'request_id':'evidence_ok','amount':100,'reference':'bank-ev'}).json()['topup']['id']
    assert client.put(f'/api/topups/{ident}/evidence',content=VALID_PNG,headers={'content-type':'image/png'}).status_code==200
    # Polyglot: valid PNG + appended script payload.
    second=client.post('/api/topups',json={'request_id':'evidence_poly','amount':100,'reference':'bank-ev2'}).json()['topup']['id']
    payload=png_with(b'<script>alert(1)</script>')
    result=client.put(f'/api/topups/{second}/evidence',content=payload,headers={'content-type':'image/png'})
    assert result.status_code==415
    with database.transaction(user) as tx:
        state=tx.execute(text('SELECT evidence_state FROM topups WHERE id=:i'),{'i':second}).scalar()
    assert state=='rejected'

def test_pdf_javascript_rejected(database,auth,user):
    client=make_client(database,auth)
    login(client,auth,user)
    ident=client.post('/api/topups',json={'request_id':'evidence_js','amount':100,'reference':'bank-js'}).json()['topup']['id']
    bad=pdf_with(b'1 0 obj << /S /JavaScript /JS (app.alert) >> endobj')
    assert client.put(f'/api/topups/{ident}/evidence',content=bad,headers={'content-type':'application/pdf'}).status_code==415
    clean=client.post('/api/topups',json={'request_id':'evidence_pdf','amount':100,'reference':'bank-pdf'}).json()['topup']['id']
    good=pdf_with(b'1 0 obj << /Pages 2 0 R >> endobj')
    assert client.put(f'/api/topups/{clean}/evidence',content=good,headers={'content-type':'application/pdf'}).status_code==200

def test_session_list_and_revoke(database,auth,user):
    client=make_client(database,auth)
    login(client,auth,user)
    first=client.get('/api/sessions')
    assert first.status_code==200
    assert len(first.json()['items'])==1 and first.json()['items'][0]['current'] is True
    # Second login creates another session for the same user.
    client.post('/api/session',json={'access_token':auth[1](user)})
    items=client.get('/api/sessions').json()['items']
    assert len(items)==2
    assert sum(1 for i in items if i['current'])==1
    # Revoke the non-current session.
    victim=[i for i in items if not i['current']][0]
    assert client.delete(f"/api/sessions/{victim['id']}").status_code==200
    remaining=client.get('/api/sessions').json()['items']
    assert len(remaining)==1 and remaining[0]['current'] is True
    # Revoking an unknown session 404s.
    assert client.delete('/api/sessions/not-a-real-hash').status_code==404

def test_revoke_all_other_sessions(database,auth,user):
    client=make_client(database,auth)
    login(client,auth,user)
    # Two more sessions; the cookie jar tracks the most recent login.
    client.post('/api/session',json={'access_token':auth[1](user)})
    client.post('/api/session',json={'access_token':auth[1](user)})
    items=client.get('/api/sessions').json()['items']
    assert len(items)==3
    current=[i for i in items if i['current']][0]
    result=client.delete('/api/sessions')
    assert result.status_code==200 and result.json()['revoked']==2
    items=client.get('/api/sessions').json()['items']
    assert len(items)==1 and items[0]['id']==current['id'] and items[0]['current'] is True
    # Current session still works.
    assert client.get('/api/me').status_code==200

def test_request_id_header_and_log_record(database,auth,user):
    client=make_client(database,auth)
    login(client,auth,user)
    response=client.get('/api/me')
    assert response.status_code==200
    rid=response.headers.get('X-Request-Id')
    assert rid and len(rid)>=16
    # A second request gets a different id.
    assert client.get('/api/me').headers['X-Request-Id']!=rid

def test_log_scrubs_secrets(database,auth,user,caplog):
    client=make_client(database,auth)
    token=auth[1](user)
    with caplog.at_level(logging.INFO):
        response=client.post('/api/session',json={'access_token':token})
    assert response.status_code==200
    rendered=[r.getMessage() for r in caplog.records]
    assert any('request' in m for m in rendered)
    # Neither the token nor the session cookie value appears in any log record.
    cookie=client.cookies.get('__Host-voicegen_session')
    for record in caplog.records:
        formatted=record.getMessage()+json.dumps({k:getattr(record,k) for k in ('request_id','user_id','path','method','status_code') if hasattr(record,k)},default=str)
        assert token not in formatted
        if cookie: assert cookie not in formatted
    assert any(getattr(r,'request_id',None) for r in caplog.records)
