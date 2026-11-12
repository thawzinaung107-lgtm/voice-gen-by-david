import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import text
from .db import one

def now(): return datetime.now(timezone.utc)
def serialize(row):
    return {"id":str(row["id"]), "taskId":row["task_id"] or "", "requestId":row["request_id"],"kind":row["payload"].get("kind","tts"),"state":row["state"] if row['expires_at']>now() else 'expired',"voiceIds":[row["payload"]["voice_id"]],"createdAt":int(row["created_at"].timestamp()*1000),"expiresAt":int(row["expires_at"].timestamp()*1000),"credits":row["cost"],"audioUrl":f"/api/audio/{row['id']}" if row['object_key'] and row['expires_at']>now() else None}

def reserve(db,user,payload,rate):
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    hashed=hashlib.sha256(canonical.encode()).hexdigest()
    # Serialize reservations and duplicate checks against the same wallet row.
    wallet=one(db,"SELECT * FROM wallets WHERE user_id=:u FOR UPDATE",u=user)
    existing=one(db,"SELECT * FROM generations WHERE user_id=:u AND request_id=:r",u=user,r=payload['request_id'])
    if existing:
        if existing['payload_hash']!=hashed: raise HTTPException(409,"request_id payload conflict")
        return existing
    cost=len(payload['text'])*rate
    if not wallet or wallet['available']<cost: raise HTTPException(402,"Insufficient application credits")
    ident=uuid.uuid4()
    row=one(db,"INSERT INTO generations(id,user_id,request_id,payload_hash,payload,cost,state,expires_at) VALUES(:id,:u,:r,:h,CAST(:p AS jsonb),:c,'queued',now()+interval '24 hours') RETURNING *",id=ident,u=user,r=payload['request_id'],h=hashed,p=canonical,c=cost)
    db.execute(text("UPDATE wallets SET available=available-:c,reserved=reserved+:c WHERE user_id=:u"),{'u':user,'c':cost})
    db.execute(text("INSERT INTO ledger(user_id,event_key,available_delta,reserved_delta) VALUES(:u,:k,:a,:r)"),{'u':user,'k':f'reserve:{ident}','a':-cost,'r':cost})
    db.execute(text("INSERT INTO outbox(generation_id,user_id) VALUES(:id,:u)"),{'id':ident,'u':user})
    return row

def settle(db,ident,success):
    job=one(db,"SELECT * FROM generations WHERE id=:id FOR UPDATE",id=ident)
    if not job: raise HTTPException(404,"Generation not found")
    if job['state'] in {'failed','completed'}: return job
    # Wallet lock and ledger key make refund/capture atomic and exactly once locally.
    one(db,"SELECT * FROM wallets WHERE user_id=:u FOR UPDATE",u=job['user_id'])
    db.execute(text("UPDATE wallets SET reserved=reserved-:c,available=available+:a WHERE user_id=:u"),{'u':job['user_id'],'c':job['cost'],'a':0 if success else job['cost']})
    db.execute(text("INSERT INTO ledger(user_id,event_key,available_delta,reserved_delta) VALUES(:u,:k,:a,:r)"),{'u':job['user_id'],'k':f'settle:{ident}','a':0 if success else job['cost'],'r':-job['cost']})
    return one(db,"UPDATE generations SET state=:s WHERE id=:id RETURNING *",id=ident,s='completed' if success else 'failed')

def approve(db,actor,ident,reference):
    row=one(db,"SELECT * FROM topups WHERE id=:id FOR UPDATE",id=ident)
    if not row: raise HTTPException(404,"Topup not found")
    if str(row['user_id'])==str(actor): raise HTTPException(403,"Independent approver required")
    if row['state']=='approved':
        if row['verification_reference']!=reference: raise HTTPException(409,"Approval reference conflict")
        return row
    if not row['evidence_key'] or row['evidence_state']!='clean': raise HTTPException(409,'Independently scanned evidence required')
    if one(db,"SELECT id FROM topups WHERE verification_reference=:r",r=reference): raise HTTPException(409,"Verification reference already used")
    one(db,"SELECT * FROM wallets WHERE user_id=:u FOR UPDATE",u=row['user_id'])
    db.execute(text("UPDATE wallets SET available=available+:a WHERE user_id=:u"),{'u':row['user_id'],'a':row['amount']})
    db.execute(text("INSERT INTO ledger(user_id,event_key,available_delta,reserved_delta) VALUES(:u,:k,:a,0)"),{'u':row['user_id'],'k':f'topup:{ident}','a':row['amount']})
    db.execute(text("INSERT INTO admin_audit(actor_id,action,target_id,details) VALUES(:a,'topup_approve',:id,CAST(:d AS jsonb))"),{'a':actor,'id':ident,'d':json.dumps({'verification_reference':reference})})
    return one(db,"UPDATE topups SET state='approved',verification_reference=:r WHERE id=:id RETURNING *",id=ident,r=reference)
