"""canvas fingerprinting
Revision ID: 0006
Revises: 0005
Create Date: 2026-06-14 18:20:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('visit_logs', sa.Column('canvas_hash', sa.String(length=64), nullable=True))
    op.add_column('visit_logs', sa.Column('webgl_hash', sa.String(length=64), nullable=True))

def downgrade():
    op.drop_column('visit_logs', 'canvas_hash')
    op.drop_column('visit_logs', 'webgl_hash')
