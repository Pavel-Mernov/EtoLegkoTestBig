"""Keep Keitaro offer shares to hundredth-percent precision."""
from alembic import op
import sqlalchemy as sa

revision = "0002_offer_weight_precision"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("campaign_offers") as batch_op:
        batch_op.alter_column(
            "weight",
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=False,
        )

def downgrade():
    with op.batch_alter_table("campaign_offers") as batch_op:
        batch_op.alter_column(
            "weight",
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
