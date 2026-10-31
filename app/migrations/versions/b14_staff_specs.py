"""Store staff and glasses specifications."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = 'b14_staff_specs'
down_revision = 'b13_audit'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('specifications', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    # Old self-registered sellers must be approved by an administrator.
    op.execute("UPDATE users SET role='buyer' WHERE role='seller'")
    op.create_check_constraint('ck_users_role', 'users', "role IN ('buyer','staff','admin')")


def downgrade():
    op.drop_constraint('ck_users_role', 'users', type_='check')
    op.execute("UPDATE users SET role='seller' WHERE role='staff'")
    op.drop_column('products', 'specifications')
