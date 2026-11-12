from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import subprocess
import sys
import threading
import uuid
import httpx
import pytest
from sqlalchemy import text
from botocore.stub import Stubber
from botocore.response import StreamingBody
import io
from production.worker import Worker,DefinitePreacceptFailure
from production.storage import PrivateStorage
from production.service import reserve
from production.db import one
from test_core import PAYLOAD,FakeStorage

@pytest.fixture
def worker_isolation(owner):
    # Tests share one disposable DB; retire unrelated queued fixture jobs first.
    with owner.begin() as tx:
        tx.execute(text("UPDATE outbox SET state='done'"))
        tx.execute(text("UPDATE generations SET state='failed' WHERE state IN ('queued','pending','uncertain')"))

@pytest.fixture
def supplier_http():
    class Handler(BaseHTTPRequestHandler):
        calls=0; mode='ok'; lock=threading.Lock(); claimed=False
        def log_message(self,*args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('content-length','0')))
            with self.lock: type(self).calls+=1
            if self.mode=='drop': self.connection.shutdown(2); self.connection.close(); return
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"task_id":"mock-local-task"}')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    yield f'http://127.0.0.1:{server.server_port}',Handler
    server.shutdown(); thread.join(); server.server_close()

class FixtureHttpSupplier:
    """Local mock protocol only; deliberately unrelated to GenMax claims."""
    def __init__(self,url): self.url=url
    def submit(self,payload):
        response=httpx.post(self.url,json=payload,timeout=2); response.raise_for_status()
        return response.json()['task_id']
    def poll(self,task_id): return {'state':'completed','audio':b'mock-audio-bytes'}

def test_multiworker_committed_claim(worker_isolation,database,worker_db,user,supplier_http):
    url,handler=supplier_http
    with database.transaction(user) as tx: ident=reserve(tx,user,PAYLOAD,2)['id']
    class CheckedSupplier(FixtureHttpSupplier):
        def submit(self,payload):
            # Separate connection sees committed claim before remote dispatch.
            with worker_db.transaction() as tx:
                assert one(tx,'SELECT state FROM generations WHERE id=:id',id=ident)['state']=='uncertain'
                assert one(tx,'SELECT state FROM outbox WHERE generation_id=:id',id=ident)['state']=='claimed'
            return super().submit(payload)
    workers=[Worker(worker_db,CheckedSupplier(url)) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as executor: results=list(executor.map(lambda w:w.dispatch_one(),workers))
    assert sum(results)==1 and handler.calls==1
    storage=FakeStorage(); worker=Worker(worker_db,FixtureHttpSupplier(url),storage)
    assert worker.poll_one()
    assert not worker.poll_one()
    with database.transaction(user) as tx:
        assert one(tx,'SELECT state FROM generations WHERE id=:id',id=ident)['state']=='completed'
        assert one(tx,'SELECT available,reserved FROM wallets WHERE user_id=:u',u=user)=={'available':9990,'reserved':0}

def test_unknown_post_no_retry_after_process_restart(worker_isolation,database,worker_db,user,supplier_http):
    url,handler=supplier_http; handler.mode='drop'
    with database.transaction(user) as tx: ident=reserve(tx,user,PAYLOAD,2)['id']
    assert Worker(worker_db,FixtureHttpSupplier(url)).dispatch_one()
    assert handler.calls==1
    # Fresh interpreter and fresh connections must not replay the unknown POST.
    command="from production.db import Database; from production.worker import Worker; import sys; assert Worker(Database(sys.argv[1],'voicegen_worker')).dispatch_one() is False"
    result=subprocess.run([sys.executable,'-c',command,worker_db.engine.url.render_as_string(hide_password=False)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert handler.calls==1
    with database.transaction(user) as tx:
        assert one(tx,'SELECT state FROM generations WHERE id=:id',id=ident)['state']=='uncertain'
        assert one(tx,'SELECT available,reserved FROM wallets WHERE user_id=:u',u=user)=={'available':9990,'reserved':10}

def test_definite_failure_refunds_and_safe_fallback(worker_isolation,database,worker_db,user):
    with database.transaction(user) as tx: ident=reserve(tx,user,PAYLOAD,2)['id']
    class Reject:
        def submit(self,payload): raise DefinitePreacceptFailure('No bytes sent')
    worker=Worker(worker_db,Reject())
    assert worker.dispatch_one(); assert not worker.dispatch_one()
    with database.transaction(user) as tx:
        assert one(tx,'SELECT state FROM generations WHERE id=:id',id=ident)['state']=='failed'
        assert one(tx,'SELECT available,reserved FROM wallets WHERE user_id=:u',u=user)=={'available':10000,'reserved':0}
    with database.transaction(user) as tx: second=reserve(tx,user,{**PAYLOAD,'request_id':'fallback_request'},2)['id']
    class Accept:
        calls=0
        def submit(self,payload): self.calls+=1; return 'accepted-fallback'
        def poll(self,task_id):
            assert task_id=='accepted-fallback'
            return {'state':'failed'}
    fallback=Accept(); assert Worker(worker_db,Reject(),fallback=fallback).dispatch_one()
    assert fallback.calls==1
    assert Worker(worker_db,Reject(),fallback=fallback).poll_one()
    with database.transaction(user) as tx: assert one(tx,'SELECT task_id FROM generations WHERE id=:id',id=second)['task_id']=='accepted-fallback'

def test_unknown_never_uses_fallback(worker_isolation,database,worker_db,user):
    with database.transaction(user) as tx: reserve(tx,user,PAYLOAD,2)
    class Unknown:
        def submit(self,payload): raise TimeoutError('unknown remote acceptance')
    class Forbidden:
        def submit(self,payload): pytest.fail('fallback must not be used')
    assert Worker(worker_db,Unknown(),fallback=Forbidden()).dispatch_one()

def test_private_s3_request_and_ranges():
    storage=PrivateStorage({'S3_BUCKET':'fixture-private','S3_ENDPOINT_URL':'https://fixture.r2.cloudflarestorage.com','S3_ACCESS_KEY_ID':'fixture','S3_SECRET_ACCESS_KEY':'fixture'})
    user=uuid.uuid4(); ident=uuid.uuid4(); key=storage.key(user,ident,'audio')
    assert key.startswith(f'audio/{user}/{ident}/') and '..' not in key
    with pytest.raises(ValueError): storage.key('../escape',ident,'audio')
    with Stubber(storage.client) as stub:
        stub.add_response('put_object',{}, {'Bucket':'fixture-private','Key':key,'Body':b'01234','ContentType':'audio/mpeg','Metadata':{'private':'true'}})
        storage.put(key,b'01234','audio/mpeg')
        stub.add_response('get_object',{'Body':StreamingBody(io.BytesIO(b'12'),2),'ContentLength':2,'ContentRange':'bytes 1-2/5','ContentType':'audio/mpeg'}, {'Bucket':'fixture-private','Key':key,'Range':'bytes=1-2'})
        obj=storage.get(key,'bytes=1-2'); assert obj['Body'].read()==b'12'
        stub.assert_no_pending_responses()
    with pytest.raises(Exception) as error: storage.get(key,'bytes=0-1,3-4')
    assert error.value.status_code==416
