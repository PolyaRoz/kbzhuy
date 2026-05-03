"""plan recipe requests queue

Allows users to queue recipe posts from the Tray feed into their next
generated meal plan.

Revision ID: 0005_plan_recipe_requests
Revises: 0004_tray_posts
Create Date: 2026-05-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_plan_recipe_requests"
down_revision = "0004_tray_posts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tray_plan_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("tray_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Filled with the plan id once the request is consumed at plan generation time.
        # NULL means "still pending".
        sa.Column("used_in_plan_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "post_id", name="uq_plan_recipe_request"),
    )
    op.create_index("ix_tray_plan_requests_user_id", "tray_plan_requests", ["user_id"])
    op.create_index("ix_tray_plan_requests_post_id", "tray_plan_requests", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_tray_plan_requests_post_id", table_name="tray_plan_requests")
    op.drop_index("ix_tray_plan_requests_user_id", table_name="tray_plan_requests")
    op.drop_table("tray_plan_requests")
