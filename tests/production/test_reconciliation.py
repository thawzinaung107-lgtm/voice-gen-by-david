import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from test_core import PAYLOAD,login,client,auth
from production.db import one
from production.service import reserve,approve

@pytest.mark.parametrize('state',['uncertain','expired_pending'])
def test_manual_reconcile_idempotent_audited(client,auth,user,owner,database,state):
    login(client,auth,user)
    ident=client.post('/api/generate',json=PAYLOAD).json()['generation']['id']
    with database.transaction(user) as tx:
        if state=='uncertain': tx.execute(text("UPDATE generations SET state='uncertain' WHERE id=:i"),{'i':ident})
        else: tx.execute(text("UPDATE generations SET state='pending',expires_at=now() WHERE id=:i"),{'i':ident})
    admin=uuid.uuid4(); login(client,auth,admin)
    with owner.begin() as tx: tx.execute(text('UPDATE users SET is_admin=true WHERE id=:u'),{'u':admin})
    for _ in range(2):
        response=client.post(f'/api/admin/generations/{ident}/reconcile',json={'outcome':'failed','verification_reference':'supplier-case-confirmed-no-job'})
        assert response.status_code==200,response.text
    assert client.post(f'/api/admin/generations/{ident}/reconcile',json={'outcome':'completed','verification_reference':'conflict-reference'}).status_code==409
    login(client,auth,user)
    assert client.get('/api/me').json()['wallet']['balance']==10000
    with owner.begin() as tx:
        assert tx.execute(text("SELECT count(*) FROM admin_audit WHERE target_id=:i AND action='reconcile'"),{'i':ident}).scalar()==1

def test_concurrent_topup_approval(database,user,owner):
    admin=uuid.uuid4(); ident=uuid.uuid4(); reference='verified-'+str(ident)
    with owner.begin() as tx:
        tx.execute(text('INSERT INTO users(id,is_admin) VALUES(:id,true)'),{'id':admin})
        tx.execute(text("INSERT INTO topups(id,user_id,request_id,amount,reference,evidence_key,evidence_state) VALUES(:id,:u,'request_concurrent',500,'bank','evidence/key','clean')"),{'id':ident,'u':user})
    def approval(_):
        with database.transaction(admin) as tx: return approve(tx,admin,ident,reference)['state']
    with ThreadPoolExecutor(max_workers=8) as executor: assert set(executor.map(approval,range(12)))=={'approved'}
    with database.transaction(user) as tx:
        assert one(tx,'SELECT available FROM wallets WHERE user_id=:u',u=user)['available']==10500
        assert one(tx,"SELECT count(*) AS n FROM ledger WHERE event_key=:k",k='topup:'+str(ident))['n']==1
