"""Reject screenshot-only approval and unreconciled completed audio."""
from alembic import op
revision = '0003'
down_revision = '0002'

def upgrade():
    op.execute("""
    ALTER TABLE topups ADD CONSTRAINT evidence_clean_before_approval
      CHECK (state <> 'approved' OR evidence_state = 'clean');
    ALTER TABLE generations ADD CONSTRAINT completed_requires_object
      CHECK (state <> 'completed' OR object_key IS NOT NULL);
    """)

def downgrade():
    op.execute("""
    ALTER TABLE topups DROP CONSTRAINT evidence_clean_before_approval;
    ALTER TABLE generations DROP CONSTRAINT completed_requires_object;
    """)
