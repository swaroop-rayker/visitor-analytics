"""Add tracking reliability and visitor classification fields.

Revision ID: 0003_reliability_and_classification
Revises: 0002_location_intelligence
Create Date: 2026-06-12 18:25:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_reliability_and_classification"
down_revision = "0002_location_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add columns to visitors table
    op.add_column("visitors", sa.Column("is_crawler", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("visitors", sa.Column("classification", sa.String(length=50), nullable=False, server_default="Unknown"))
    op.add_column("visitors", sa.Column("classification_confidence", sa.Float(), nullable=False, server_default="0.0"))
    op.add_column("visitors", sa.Column("classification_reason", sa.String(length=255), nullable=True))
    op.add_column("visitors", sa.Column("current_country_confidence", sa.String(length=20), nullable=False, server_default="Low"))
    op.add_column("visitors", sa.Column("current_state_confidence", sa.String(length=20), nullable=False, server_default="Low"))
    op.add_column("visitors", sa.Column("current_city_confidence", sa.String(length=20), nullable=False, server_default="Low"))
    op.add_column("visitors", sa.Column("current_location_confidence", sa.String(length=20), nullable=False, server_default="Low"))

    # 2. Add columns to visit_logs table
    op.add_column("visit_logs", sa.Column("tracking_status", sa.String(length=30), nullable=False, server_default="received"))
    op.add_column("visit_logs", sa.Column("tracking_failure_reason", sa.String(length=255), nullable=True))
    op.add_column("visit_logs", sa.Column("classification", sa.String(length=50), nullable=False, server_default="Unknown"))
    op.add_column("visit_logs", sa.Column("classification_confidence", sa.Float(), nullable=False, server_default="0.0"))
    op.add_column("visit_logs", sa.Column("classification_reason", sa.String(length=255), nullable=True))
    op.add_column("visit_logs", sa.Column("country_confidence", sa.String(length=20), nullable=False, server_default="Low"))
    op.add_column("visit_logs", sa.Column("state_confidence", sa.String(length=20), nullable=False, server_default="Low"))
    op.add_column("visit_logs", sa.Column("city_confidence", sa.String(length=20), nullable=False, server_default="Low"))
    op.add_column("visit_logs", sa.Column("location_confidence", sa.String(length=20), nullable=False, server_default="Low"))


def downgrade() -> None:
    # Downgrade visit_logs columns
    op.drop_column("visit_logs", "location_confidence")
    op.drop_column("visit_logs", "city_confidence")
    op.drop_column("visit_logs", "state_confidence")
    op.drop_column("visit_logs", "country_confidence")
    op.drop_column("visit_logs", "classification_reason")
    op.drop_column("visit_logs", "classification_confidence")
    op.drop_column("visit_logs", "classification")
    op.drop_column("visit_logs", "tracking_failure_reason")
    op.drop_column("visit_logs", "tracking_status")

    # Downgrade visitors columns
    op.drop_column("visitors", "current_location_confidence")
    op.drop_column("visitors", "current_city_confidence")
    op.drop_column("visitors", "current_state_confidence")
    op.drop_column("visitors", "current_country_confidence")
    op.drop_column("visitors", "classification_reason")
    op.drop_column("visitors", "classification_confidence")
    op.drop_column("visitors", "classification")
    op.drop_column("visitors", "is_crawler")
