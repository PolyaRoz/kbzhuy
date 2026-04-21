"""profile onboarding fields

Revision ID: 0002_profile_onboarding_fields
Revises: 0001_initial
Create Date: 2026-04-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_profile_onboarding_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("name", sa.String(100), nullable=True))
    op.add_column("profiles", sa.Column("measurements", sa.JSON(), nullable=True, server_default="{}"))
    op.add_column("profiles", sa.Column("training_days", sa.JSON(), nullable=True, server_default="[]"))
    op.add_column("profiles", sa.Column("sport_types", sa.JSON(), nullable=True, server_default="[]"))
    op.add_column("profiles", sa.Column("cooking_time_budget", sa.JSON(), nullable=True, server_default="{}"))


def downgrade() -> None:
    op.drop_column("profiles", "cooking_time_budget")
    op.drop_column("profiles", "sport_types")
    op.drop_column("profiles", "training_days")
    op.drop_column("profiles", "measurements")
    op.drop_column("profiles", "name")
