"""Production identities, wallet, durable jobs and RLS."""
from alembic import op
revision = '0001'
down_revision = None

def upgrade():
    op.execute("""
    DO $$ BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='voicegen_api') THEN CREATE ROLE voicegen_api NOLOGIN NOBYPASSRLS; END IF;
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='voicegen_worker') THEN CREATE ROLE voicegen_worker NOLOGIN NOBYPASSRLS; END IF;
    END $$;
    CREATE TABLE users (id uuid PRIMARY KEY, email text, is_admin boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE wallets (user_id uuid PRIMARY KEY REFERENCES users, available bigint NOT NULL DEFAULT 0 CHECK(available>=0), reserved bigint NOT NULL DEFAULT 0 CHECK(reserved>=0));
    CREATE TABLE sessions (id text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users, expires_at timestamptz NOT NULL);
    CREATE TABLE generations (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users, request_id text NOT NULL, payload_hash text NOT NULL, payload jsonb NOT NULL, cost bigint NOT NULL CHECK(cost>0), state text NOT NULL CHECK(state IN ('queued','uncertain','pending','completed','failed')), task_id text, dispatch_provider text NOT NULL DEFAULT 'primary' CHECK(dispatch_provider IN ('primary','fallback')), object_key text, created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL, UNIQUE(user_id,request_id));
    CREATE TABLE outbox (generation_id uuid PRIMARY KEY REFERENCES generations, user_id uuid NOT NULL REFERENCES users, state text NOT NULL DEFAULT 'ready' CHECK(state IN ('ready','claimed','done')), claimed_at timestamptz);
    CREATE TABLE topups (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users, request_id text NOT NULL, amount bigint NOT NULL CHECK(amount>0), reference text NOT NULL, evidence_key text, state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','approved')), verification_reference text UNIQUE, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,request_id));
    CREATE TABLE ledger (id bigserial PRIMARY KEY, user_id uuid NOT NULL REFERENCES users, event_key text NOT NULL UNIQUE, available_delta bigint NOT NULL, reserved_delta bigint NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE admin_audit (id bigserial PRIMARY KEY, actor_id uuid NOT NULL REFERENCES users, action text NOT NULL, target_id uuid NOT NULL, details jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
    CREATE FUNCTION immutable_record() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable record'; END $$;
    CREATE TRIGGER immutable_ledger BEFORE UPDATE OR DELETE OR TRUNCATE ON ledger FOR EACH STATEMENT EXECUTE FUNCTION immutable_record();
    CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON admin_audit FOR EACH STATEMENT EXECUTE FUNCTION immutable_record();
    CREATE FUNCTION app_admin() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$ SELECT coalesce((SELECT is_admin FROM public.users WHERE id=nullif(current_setting('app.user_id',true),'')::uuid),false) $$;
    REVOKE ALL ON FUNCTION app_admin() FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app_admin() TO voicegen_api,voicegen_worker;
    GRANT USAGE ON SCHEMA public TO voicegen_api,voicegen_worker;
    GRANT SELECT,INSERT ON users TO voicegen_api;
    GRANT SELECT,INSERT,UPDATE,DELETE ON sessions TO voicegen_api;
    GRANT SELECT,INSERT,UPDATE ON wallets,generations,outbox,topups TO voicegen_api,voicegen_worker;
    GRANT SELECT ON users TO voicegen_worker;
    GRANT SELECT,INSERT ON ledger,admin_audit TO voicegen_api,voicegen_worker;
    GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO voicegen_api,voicegen_worker;
    REVOKE ALL ON users,wallets,sessions,generations,outbox,topups,ledger,admin_audit FROM PUBLIC;
    DO $$ DECLARE role_name text; BEGIN
      FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS(SELECT FROM pg_roles WHERE rolname=role_name) THEN
          EXECUTE format('REVOKE ALL ON users,wallets,sessions,generations,outbox,topups,ledger,admin_audit FROM %I',role_name);
          EXECUTE format('REVOKE ALL ON FUNCTION app_admin() FROM %I',role_name);
        END IF;
      END LOOP;
    END $$;
    REVOKE INSERT ON users FROM voicegen_api;
    GRANT INSERT(id,email) ON users TO voicegen_api;
    """)
    for table, column in [('users','id'),('wallets','user_id'),('generations','user_id'),('outbox','user_id'),('topups','user_id'),('ledger','user_id')]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # Owner bypass is intentionally required only by SECURITY DEFINER role lookup.
        if table != 'users': op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY owner_scope ON {table} TO voicegen_api USING ({column}=nullif(current_setting('app.user_id',true),'')::uuid OR app_admin()) WITH CHECK ({column}=nullif(current_setting('app.user_id',true),'')::uuid OR app_admin())")
        op.execute(f"CREATE POLICY worker_scope ON {table} TO voicegen_worker USING (true) WITH CHECK (true)")
    op.execute("""
    ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
    CREATE POLICY session_scope ON sessions TO voicegen_api USING (id=current_setting('app.session_hash',true)) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),'')::uuid);
    ALTER TABLE admin_audit ENABLE ROW LEVEL SECURITY;
    ALTER TABLE admin_audit FORCE ROW LEVEL SECURITY;
    CREATE POLICY audit_admin ON admin_audit TO voicegen_api USING(app_admin()) WITH CHECK(app_admin() AND actor_id=nullif(current_setting('app.user_id',true),'')::uuid);
    CREATE POLICY audit_worker ON admin_audit TO voicegen_worker USING(true) WITH CHECK(true);
    """)

def downgrade():
    op.execute("DROP TABLE admin_audit,ledger,topups,outbox,generations,sessions,wallets CASCADE")
    op.execute("DROP POLICY owner_scope ON users")
    op.execute("DROP FUNCTION app_admin()")
    op.execute("DROP TABLE users")
    op.execute("DROP FUNCTION immutable_record()")
