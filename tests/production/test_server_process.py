import json
import os
import socket
import subprocess
import sys
import time
import httpx
from conftest import RUNTIME

def test_uvicorn_entrypoint_health_cookie_boundary():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    env={**os.environ,'DATABASE_URL':RUNTIME,'APP_ORIGIN':'https://app.example.test','SUPABASE_ISSUER':'https://fixture.supabase.test/auth/v1','SUPABASE_JWKS_URL':'https://fixture.supabase.test/auth/v1/.well-known/jwks.json','SUPABASE_URL':'https://fixture.supabase.test','SUPABASE_ANON_KEY':'public-fixture-anon'}
    process=subprocess.Popen([sys.executable,'-m','uvicorn','production.app:create_app','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=2) as client:
            for _ in range(100):
                try: response=client.get('/api/health'); break
                except httpx.ConnectError: time.sleep(0.05)
            else: raise AssertionError('server did not start')
            assert response.status_code==200
            health=response.json()
            assert health['mode']=='production' and health['auth']['anonKey']=='public-fixture-anon'
            assert not health['capabilities']['generation']
            assert client.get('/api/me').status_code==401
            assert client.post('/api/session',json={'access_token':'x'*30}).status_code==403
            assert client.post('/api/session',json={'token':'owner-bypass'},headers={'origin':'https://app.example.test'}).status_code==422
            assert client.post('/api/session',content=b'x'*70000,headers={'origin':'https://app.example.test'}).status_code==413
    finally:
        process.terminate()
        try: process.communicate(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.communicate()
