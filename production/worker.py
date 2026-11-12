"""Durable worker. A claim is committed before the only remote POST.

An uncertain claim is never reclaimed or submitted by another worker. This trades
availability for safety: a crash before POST also requires manual reconciliation.
"""
import argparse
import json
import os
import time
import uuid
from sqlalchemy import text
from .db import Database, one
from .service import settle, now

class DefinitePreacceptFailure(Exception): pass
class UnknownSubmission(Exception): pass

class DisabledSupplier:
    def submit(self,payload):
        raise DefinitePreacceptFailure('Supplier contract not verified; no request sent')
    def poll(self,task_id): raise RuntimeError('Supplier disabled')

class GenMaxSupplier:
    """Deliberately disconnected until documented upstream schemas are verified."""
    def __init__(self,*args,**kwargs):
        raise RuntimeError('GenMax adapter unverified and disabled')

class Worker:
    def __init__(self,database,supplier=None,storage=None,fallback=None):
        self.db=database; self.supplier=supplier or DisabledSupplier(); self.storage=storage; self.fallback=fallback
    def dispatch_one(self):
        with self.db.transaction() as tx:
            job=one(tx,"SELECT o.generation_id FROM outbox o JOIN generations g ON g.id=o.generation_id WHERE o.state='ready' AND g.state='queued' ORDER BY g.created_at FOR UPDATE OF o SKIP LOCKED LIMIT 1")
            if not job: return False
            ident=job['generation_id']
            row=one(tx,"UPDATE generations SET state='uncertain' WHERE id=:id RETURNING *",id=ident)
            tx.execute(text("UPDATE outbox SET state='claimed',claimed_at=now() WHERE generation_id=:id"),{'id':ident})
            if row['expires_at']<=now():
                settle(tx,ident,False)
                tx.execute(text("UPDATE outbox SET state='done' WHERE generation_id=:id"),{'id':ident})
                return True
        # Transaction is committed; after this point any unknown result stays uncertain.
        provider='primary'
        try:
            try: task_id=self.supplier.submit(row['payload'])
            except DefinitePreacceptFailure:
                if not self.fallback: raise
                provider='fallback'
                task_id=self.fallback.submit(row['payload'])
            if not isinstance(task_id,str) or not task_id or len(task_id)>256: raise UnknownSubmission('Malformed acceptance')
        except DefinitePreacceptFailure:
            with self.db.transaction() as tx:
                settle(tx,ident,False)
                tx.execute(text("UPDATE outbox SET state='done' WHERE generation_id=:id"),{'id':ident})
            return True
        except Exception:
            # Timeout, 5xx, invalid JSON or process crash: no automatic retry/refund.
            return True
        with self.db.transaction() as tx:
            tx.execute(text("UPDATE generations SET state='pending',task_id=:t,dispatch_provider=:p WHERE id=:id AND state='uncertain'"),{'id':ident,'t':task_id,'p':provider})
            tx.execute(text("UPDATE outbox SET state='done' WHERE generation_id=:id"),{'id':ident})
        return True
    def poll_one(self):
        # Polls are safe reads; a transaction lock prevents concurrent completion.
        with self.db.transaction() as tx:
            row=one(tx,"SELECT * FROM generations WHERE state='pending' AND expires_at>now() ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1")
            if not row: return False
            try:
                supplier=self.fallback if row['dispatch_provider']=='fallback' else self.supplier
                if supplier is None: return False
                result=supplier.poll(row['task_id'])
            except Exception: return False
            if result.get('state')=='failed': settle(tx,row['id'],False); return True
            if result.get('state')!='completed': return False
            audio=result.get('audio')
            if self.storage is None or not isinstance(audio,bytes) or not audio or len(audio)>50*1024*1024: return False
            key=self.storage.key(row['user_id'],row['id'],'audio')
            self.storage.put(key,audio,'audio/mpeg')
            tx.execute(text('UPDATE generations SET object_key=:k WHERE id=:id'),{'id':row['id'],'k':key})
            settle(tx,row['id'],True)
            return True

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--once',action='store_true'); args=parser.parse_args()
    worker=Worker(Database(os.environ['WORKER_DATABASE_URL'],'voicegen_worker'))
    while True:
        worked=worker.dispatch_one()
        worked=worker.poll_one() or worked
        if args.once: return
        if not worked: time.sleep(1)
if __name__=='__main__': main()
