"""Track offers removed from Keitaro in the Adrobot archive."""
from alembic import op
import sqlalchemy as sa

revision = "0003_archive_campaign_offers"
down_revision = "0002_offer_weight_precision"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("campaign_offers", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("campaign_offers", "archived")
