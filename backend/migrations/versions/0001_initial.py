"""Initial campaign and offer tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("keitaro_id", sa.Integer(), nullable=True),
        sa.Column("keitaro_alias", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaigns_name", "campaigns", ["name"])
    op.create_table("campaign_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keitaro_offer_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="100"),
    )
    op.create_index("ix_campaign_offers_campaign_id", "campaign_offers", ["campaign_id"])

def downgrade():
    op.drop_index("ix_campaign_offers_campaign_id", table_name="campaign_offers")
    op.drop_table("campaign_offers")
    op.drop_index("ix_campaigns_name", table_name="campaigns")
    op.drop_table("campaigns")
