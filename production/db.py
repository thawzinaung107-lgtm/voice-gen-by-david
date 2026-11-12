from contextlib import contextmanager
from sqlalchemy import create_engine, text

class Database:
    def __init__(self, url, role="voicegen_api"):
        if role not in {"voicegen_api", "voicegen_worker"}: raise ValueError("invalid role")
        self.engine = create_engine(url, pool_pre_ping=True)
        self.role = role

    @contextmanager
    def transaction(self, user=None, session_hash=""):
        with self.engine.begin() as db:
            # Do not silently accept credentials that bypass the runtime boundary.
            role = db.execute(text("SELECT rolsuper,rolbypassrls,rolinherit, EXISTS(SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='users' AND c.relowner=pg_roles.oid) AS owns_data FROM pg_roles WHERE rolname=current_user")).one()
            if role.rolsuper or role.rolbypassrls or role.rolinherit or role.owns_data: raise RuntimeError("runtime login must not bypass RLS or own data; NOINHERIT required")
            db.execute(text(f"SET LOCAL ROLE {self.role}"))
            effective = db.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
            if effective.rolsuper or effective.rolbypassrls: raise RuntimeError("effective runtime role must not bypass RLS")
            db.execute(text("SELECT set_config('app.user_id',:u,true),set_config('app.session_hash',:s,true)"), {"u":str(user) if user else "", "s":session_hash})
            yield db

def one(db, sql, **params):
    return db.execute(text(sql),params).mappings().first()
