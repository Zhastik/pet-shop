"""Durable audit events."""
from alembic import op
import sqlalchemy as sa
revision = 'b13_audit'
down_revision = 'b12_reliability'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('audit_events', sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('actor_id', sa.Integer(), nullable=False), sa.Column('action', sa.String(64), nullable=False),
        sa.Column('target_id', sa.Integer()), sa.Column('created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False))
    op.create_index('ix_audit_created', 'audit_events', ['created_at'])


def downgrade():
    op.drop_table('audit_events')
