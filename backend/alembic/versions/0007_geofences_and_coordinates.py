"""geofences and coordinates

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-16 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add coordinates columns to visit_logs
    op.add_column('visit_logs', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('visit_logs', sa.Column('longitude', sa.Float(), nullable=True))

    # 2. Create geofences table
    op.create_table(
        'geofences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('center_latitude', sa.Float(), nullable=True),
        sa.Column('center_longitude', sa.Float(), nullable=True),
        sa.Column('radius_meters', sa.Float(), nullable=True),
        sa.Column('coordinates', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # 1. Drop geofences table
    op.drop_table('geofences')

    # 2. Drop coordinates columns from visit_logs
    op.drop_column('visit_logs', 'longitude')
    op.drop_column('visit_logs', 'latitude')
