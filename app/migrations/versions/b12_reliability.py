"""Order idempotency and database invariants."""
from alembic import op
import sqlalchemy as sa
revision = 'b12_reliability'
down_revision = '0a7f32b01830'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('idempotency_key', sa.String(128), nullable=True))
    op.create_unique_constraint('uq_orders_user_key', 'orders', ['user_id', 'idempotency_key'])
    for table, name, condition in [
        ('products', 'ck_products_stock', 'stock >= 0'),
        ('products', 'ck_products_price', 'price > 0'),
        ('cart_items', 'ck_cart_quantity', 'quantity > 0'),
        ('order_items', 'ck_order_quantity', 'quantity > 0'),
        ('reviews', 'ck_review_grade', 'grade BETWEEN 1 AND 5'),
    ]:
        op.create_check_constraint(name, table, condition)


def downgrade():
    for table, name in [('products','ck_products_stock'), ('products','ck_products_price'),
                        ('cart_items','ck_cart_quantity'), ('order_items','ck_order_quantity'),
                        ('reviews','ck_review_grade')]:
        op.drop_constraint(name, table, type_='check')
    op.drop_constraint('uq_orders_user_key', 'orders', type_='unique')
    op.drop_column('orders', 'idempotency_key')
