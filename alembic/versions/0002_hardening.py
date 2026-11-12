"""Evidence quarantine state and session creation timestamps."""
from alembic import op
revision = '0002'
down_revision = '0001'

def upgrade():
    op.execute("""
    ALTER TABLE topups ADD COLUMN evidence_state text NOT NULL DEFAULT 'pending_scan' CHECK(evidence_state IN ('pending_scan','clean','rejected'));
    ALTER TABLE sessions ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
    -- Session listing/revocation requires visibility of all own sessions,
    -- not just the current-hash row. WITH CHECK unchanged: writes still
    -- require user_id = app.user_id.
    DROP POLICY session_scope ON sessions;
    CREATE POLICY session_scope ON sessions TO voicegen_api USING (id=current_setting('app.session_hash',true) OR user_id=nullif(current_setting('app.user_id',true),'')::uuid) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),'')::uuid);
    """)

def downgrade():
    op.execute("""
    DROP POLICY session_scope ON sessions;
    CREATE POLICY session_scope ON sessions TO voicegen_api USING (id=current_setting('app.session_hash',true)) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),'')::uuid);
    ALTER TABLE topups DROP COLUMN evidence_state;
    ALTER TABLE sessions DROP COLUMN created_at;
    """)
