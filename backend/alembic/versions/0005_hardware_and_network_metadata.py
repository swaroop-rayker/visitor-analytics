"""hardware and network metadata

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-13 23:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004_backfill_classifications'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('visit_logs', sa.Column('cores', sa.Integer(), nullable=True))
    op.add_column('visit_logs', sa.Column('memory', sa.Float(), nullable=True))
    op.add_column('visit_logs', sa.Column('gpu', sa.String(length=256), nullable=True))
    op.add_column('visit_logs', sa.Column('rtt', sa.Integer(), nullable=True))
    op.add_column('visit_logs', sa.Column('downlink', sa.Float(), nullable=True))
    op.add_column('visit_logs', sa.Column('save_data', sa.Boolean(), nullable=True))
    op.add_column('visit_logs', sa.Column('has_private_ip', sa.Boolean(), nullable=True))
    op.add_column('visit_logs', sa.Column('ping_jitter', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('visit_logs', 'cores')
    op.drop_column('visit_logs', 'memory')
    op.drop_column('visit_logs', 'gpu')
    op.drop_column('visit_logs', 'rtt')
    op.drop_column('visit_logs', 'downlink')
    op.drop_column('visit_logs', 'save_data')
    op.drop_column('visit_logs', 'has_private_ip')
    op.drop_column('visit_logs', 'ping_jitter')
