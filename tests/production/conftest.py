import os
import uuid
import pytest
from sqlalchemy import create_engine,text
from production.db import Database

OWNER=os.getenv('TEST_DATABASE_URL','postgresql+psycopg://voicegen_test:voicegen_test@127.0.0.1:55432/voicegen_test')
RUNTIME=OWNER.replace('voicegen_test:voicegen_test@','voicegen_runtime:voicegen_runtime@')
WORKER=OWNER.replace('voicegen_test:voicegen_test@','voicegen_jobs:voicegen_jobs@')

@pytest.fixture(scope='session',autouse=True)
def provision():
    engine=create_engine(OWNER)
    with engine.begin() as tx:
        tx.execute(text("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='voicegen_runtime') THEN CREATE ROLE voicegen_runtime LOGIN PASSWORD 'voicegen_runtime' NOINHERIT NOBYPASSRLS; END IF; IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='voicegen_jobs') THEN CREATE ROLE voicegen_jobs LOGIN PASSWORD 'voicegen_jobs' NOINHERIT NOBYPASSRLS; END IF; END $$"))
        tx.execute(text('GRANT voicegen_api TO voicegen_runtime'))
        tx.execute(text('GRANT voicegen_worker TO voicegen_jobs'))
    yield
    engine.dispose()

@pytest.fixture
def owner():
    engine=create_engine(OWNER)
    yield engine
    engine.dispose()

@pytest.fixture
def database():
    db=Database(RUNTIME)
    yield db
    db.engine.dispose()

@pytest.fixture
def worker_db():
    db=Database(WORKER,'voicegen_worker')
    yield db
    db.engine.dispose()

@pytest.fixture
def user(owner):
    ident=uuid.uuid4()
    with owner.begin() as tx:
        tx.execute(text('INSERT INTO users(id,email) VALUES(:id,:e)'),{'id':ident,'e':str(ident)+'@example.test'})
        tx.execute(text('INSERT INTO wallets(user_id,available) VALUES(:id,10000)'),{'id':ident})
    return ident
