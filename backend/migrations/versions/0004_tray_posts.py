"""tray posts (social feed)

Revision ID: 0004_tray_posts
Revises: 0003_inventory_items
Create Date: 2026-05-02 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_tray_posts"
down_revision = "0003_inventory_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tray_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tray_posts_user_id", "tray_posts", ["user_id"])
    op.create_index("ix_tray_posts_category", "tray_posts", ["category"])
    op.create_index("ix_tray_posts_created_at", "tray_posts", ["created_at"])

    op.create_table(
        "tray_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("tray_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tray_comments_post_id", "tray_comments", ["post_id"])
    op.create_index("ix_tray_comments_user_id", "tray_comments", ["user_id"])

    op.create_table(
        "tray_likes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("tray_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("post_id", "user_id", name="uq_tray_like"),
    )
    op.create_index("ix_tray_likes_post_id", "tray_likes", ["post_id"])
    op.create_index("ix_tray_likes_user_id", "tray_likes", ["user_id"])


def downgrade() -> None:
    op.drop_table("tray_likes")
    op.drop_table("tray_comments")
    op.drop_table("tray_posts")
