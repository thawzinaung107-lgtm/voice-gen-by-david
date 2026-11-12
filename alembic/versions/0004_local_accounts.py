"""Local password accounts. Supabase UUID users stay passwordless."""
from alembic import op
revision = '0004'
down_revision = '0003'

def upgrade():
    op.execute("""
    ALTER TABLE users ADD COLUMN password_hash text;
    CREATE UNIQUE INDEX users_email_local ON users (lower(email)) WHERE password_hash IS NOT NULL;
    GRANT INSERT(password_hash) ON users TO voicegen_api;
    CREATE FUNCTION lookup_local_account(account_email text) RETURNS TABLE(id uuid, password_hash text)
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
        SELECT id, password_hash FROM users WHERE lower(email)=lower(account_email) AND password_hash IS NOT NULL
      $$;
    REVOKE ALL ON FUNCTION lookup_local_account(text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION lookup_local_account(text) TO voicegen_api;
    """)

def downgrade():
    op.execute("""
    DROP INDEX users_email_local;
    ALTER TABLE users DROP COLUMN password_hash;
    """)
