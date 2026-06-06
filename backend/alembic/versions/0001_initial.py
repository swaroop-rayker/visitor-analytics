"""Initial analytics schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visitors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visitor_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("total_visits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_city", sa.String(120)),
        sa.Column("current_state", sa.String(120)),
        sa.Column("current_country", sa.String(120)),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_visitors_last_seen", "visitors", ["last_seen"])
    op.create_table(
        "visit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("visitor_id", sa.Integer(), sa.ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("city", sa.String(120)),
        sa.Column("state", sa.String(120)),
        sa.Column("country", sa.String(120)),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("browser", sa.String(80)),
        sa.Column("os", sa.String(80)),
        sa.Column("device_type", sa.String(40)),
        sa.Column("network_type", sa.String(40), nullable=False, server_default="Unknown"),
        sa.Column("asn", sa.Integer()),
        sa.Column("network_organization", sa.String(200)),
        sa.Column("timezone", sa.String(80)),
        sa.Column("language", sa.String(32)),
        sa.Column("screen_resolution", sa.String(32)),
        sa.Column("is_anomalous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("anomaly_reasons", sa.JSON()),
    )
    op.create_index("ix_visit_logs_timestamp", "visit_logs", ["timestamp"])
    op.create_index("ix_visit_logs_visitor_timestamp", "visit_logs", ["visitor_id", "timestamp"])
    op.create_table(
        "aggregated_daily_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("city", sa.String(120), nullable=False, server_default="Unknown"),
        sa.Column("state", sa.String(120), nullable=False, server_default="Unknown"),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_visitors", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("date", "city", "state", name="uq_daily_location"),
    )
    op.create_index("ix_daily_stats_date", "aggregated_daily_stats", ["date"])
    op.create_table(
        "daily_stat_visitors",
        sa.Column("daily_stat_id", sa.Integer(), sa.ForeignKey("aggregated_daily_stats.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("visitor_id", sa.Integer(), sa.ForeignKey("visitors.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON()),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("daily_stat_visitors")
    op.drop_table("aggregated_daily_stats")
    op.drop_table("visit_logs")
    op.drop_table("visitors")

