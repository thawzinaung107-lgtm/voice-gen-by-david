import json
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa,ec
from production.auth import Authenticator
from production.import_sqlite import dry_run

def test_real_local_jwks_fetch_rotation_and_es256():
    rs=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    es=ec.generate_private_key(ec.SECP256R1())
    keys=[]
    for key,kid,alg in [(rs,'rsa','RS256'),(es,'ec','ES256')]:
        jwk=json.loads(jwt.algorithms.get_default_algorithms()[alg].to_jwk(key.public_key()))
        keys.append({**jwk,'kid':kid,'alg':alg,'use':'sig'})
    class Handler(BaseHTTPRequestHandler):
        count=0
        def log_message(self,*args): pass
        def do_GET(self):
            type(self).count+=1
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({'keys':keys}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        auth=Authenticator('https://fixture.supabase.test/auth/v1','authenticated','https://fixture.supabase.test/jwks')
        # Only test wiring is local HTTP; production constructor requires HTTPS.
        auth.jwks.uri=f'http://127.0.0.1:{server.server_port}/jwks'
        user=str(uuid.uuid4())
        for key,kid,alg in [(rs,'rsa','RS256'),(es,'ec','ES256')]:
            token=jwt.encode({'sub':user,'iss':auth.issuer,'aud':'authenticated','iat':int(time.time()),'exp':int(time.time())+60},key,algorithm=alg,headers={'kid':kid})
            assert auth.verify(token)['sub']==user
        assert Handler.count>=1
    finally: server.shutdown(); thread.join(); server.server_close()

def test_sqlite_inventory_is_read_only_and_never_credits_supplier(tmp_path):
    path=tmp_path/'fixture.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE generations(id TEXT,credits REAL)')
        db.execute('INSERT INTO generations VALUES(?,?)',('staging-id',123.5))
    before=path.read_bytes()
    result=dry_run(path)
    assert result['customer_credits_to_import']==0
    assert result['tables']['generations']['rows']==1
    assert result['supplier_financial_audit'][0]['raw']['credits']==123.5
    assert result['supplier_financial_audit'][0]['customer_credit_delta']==0
    assert path.read_bytes()==before
