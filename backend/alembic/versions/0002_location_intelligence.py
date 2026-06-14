"""Add location intelligence and crawler analytics fields."""
from alembic import op
import sqlalchemy as sa

revision = "0002_location_intelligence"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("visitors", sa.Column("country_confidence_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("visitors", sa.Column("state_confidence_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("visitors", sa.Column("city_confidence_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("visitors", sa.Column("current_asn", sa.Integer()))
    op.add_column("visitors", sa.Column("current_isp", sa.String(200)))
    op.add_column("visitors", sa.Column("current_network_type", sa.String(40), nullable=False, server_default="Unknown"))
    op.add_column(
        "visitors",
        sa.Column("current_location_source", sa.String(80), nullable=False, server_default="IP/ASN Inference"),
    )

    op.add_column("visit_logs", sa.Column("city_raw", sa.String(120)))
    op.add_column("visit_logs", sa.Column("state_raw", sa.String(120)))
    op.add_column("visit_logs", sa.Column("country_raw", sa.String(120)))
    op.add_column("visit_logs", sa.Column("city_normalized", sa.String(120)))
    op.add_column("visit_logs", sa.Column("state_normalized", sa.String(120)))
    op.add_column("visit_logs", sa.Column("country_normalized", sa.String(120)))
    op.add_column("visit_logs", sa.Column("country_confidence_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("visit_logs", sa.Column("state_confidence_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("visit_logs", sa.Column("city_confidence_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "visit_logs",
        sa.Column("location_source", sa.String(80), nullable=False, server_default="IP/ASN Inference"),
    )
    op.add_column("visit_logs", sa.Column("location_source_detail", sa.String(240)))
    op.add_column("visit_logs", sa.Column("isp", sa.String(200)))
    op.add_column("visit_logs", sa.Column("accept_language", sa.String(256)))
    op.add_column("visit_logs", sa.Column("geolocation_accuracy_meters", sa.Integer()))
    op.add_column("visit_logs", sa.Column("is_crawler", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("visit_logs", sa.Column("crawler_type", sa.String(80)))
    op.create_index("ix_visit_logs_location_source", "visit_logs", ["location_source"])
    op.create_index("ix_visit_logs_network_type", "visit_logs", ["network_type"])
    op.create_index("ix_visit_logs_asn", "visit_logs", ["asn"])

    op.add_column("aggregated_daily_stats", sa.Column("country", sa.String(120), nullable=False, server_default="Unknown"))

    op.create_table(
        "crawler_visit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("crawler_type", sa.String(80), nullable=False, server_default="Unknown crawler"),
        sa.Column("user_agent_family", sa.String(120)),
        sa.Column("city", sa.String(120)),
        sa.Column("state", sa.String(120)),
        sa.Column("country", sa.String(120)),
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("asn", sa.Integer()),
        sa.Column("isp", sa.String(200)),
        sa.Column("network_type", sa.String(40), nullable=False, server_default="Unknown"),
        sa.Column("location_source", sa.String(80), nullable=False, server_default="IP/ASN Inference"),
    )
    op.create_index("ix_crawler_visit_logs_timestamp", "crawler_visit_logs", ["timestamp"])
    op.create_index("ix_crawler_visit_logs_crawler_type", "crawler_visit_logs", ["crawler_type"])


def downgrade() -> None:
    op.drop_index("ix_crawler_visit_logs_crawler_type", table_name="crawler_visit_logs")
    op.drop_index("ix_crawler_visit_logs_timestamp", table_name="crawler_visit_logs")
    op.drop_table("crawler_visit_logs")

    op.drop_column("aggregated_daily_stats", "country")

    op.drop_index("ix_visit_logs_asn", table_name="visit_logs")
    op.drop_index("ix_visit_logs_network_type", table_name="visit_logs")
    op.drop_index("ix_visit_logs_location_source", table_name="visit_logs")
    op.drop_column("visit_logs", "crawler_type")
    op.drop_column("visit_logs", "is_crawler")
    op.drop_column("visit_logs", "geolocation_accuracy_meters")
    op.drop_column("visit_logs", "accept_language")
    op.drop_column("visit_logs", "isp")
    op.drop_column("visit_logs", "location_source_detail")
    op.drop_column("visit_logs", "location_source")
    op.drop_column("visit_logs", "city_confidence_score")
    op.drop_column("visit_logs", "state_confidence_score")
    op.drop_column("visit_logs", "country_confidence_score")
    op.drop_column("visit_logs", "country_normalized")
    op.drop_column("visit_logs", "state_normalized")
    op.drop_column("visit_logs", "city_normalized")
    op.drop_column("visit_logs", "country_raw")
    op.drop_column("visit_logs", "state_raw")
    op.drop_column("visit_logs", "city_raw")

    op.drop_column("visitors", "current_location_source")
    op.drop_column("visitors", "current_network_type")
    op.drop_column("visitors", "current_isp")
    op.drop_column("visitors", "current_asn")
    op.drop_column("visitors", "city_confidence_score")
    op.drop_column("visitors", "state_confidence_score")
    op.drop_column("visitors", "country_confidence_score")
