"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=True),
        sa.Column("phone", sa.String(20), unique=True, index=True, nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("auth_provider", sa.String(50), nullable=False, server_default="local"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # profiles
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True),
        sa.Column("sex", sa.String(10), nullable=True, server_default="male"),
        sa.Column("age", sa.Integer(), nullable=True, server_default="30"),
        sa.Column("height_cm", sa.Float(), nullable=True, server_default="175.0"),
        sa.Column("weight_kg", sa.Float(), nullable=True, server_default="80.0"),
        sa.Column("activity_level", sa.String(20), nullable=True, server_default="moderate"),
        sa.Column("goal", sa.String(30), nullable=True, server_default="maintain"),
        sa.Column("target_kcal", sa.Integer(), nullable=True),
        sa.Column("target_protein_g", sa.Integer(), nullable=True),
        sa.Column("target_fat_g", sa.Integer(), nullable=True),
        sa.Column("target_carbs_g", sa.Integer(), nullable=True),
        sa.Column("allergies", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("disliked_foods", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("diet_type", sa.String(30), nullable=True),
        sa.Column("budget_rub_week", sa.Integer(), nullable=True),
        sa.Column("cooking_frequency", sa.String(20), nullable=True, server_default="twice_a_week"),
        sa.Column("family_size", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("kitchen_equipment", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("eating_schedule", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("flexibility_pct", sa.Integer(), nullable=True, server_default="10"),
        sa.Column("planned_deviations", sa.JSON(), nullable=True, server_default="[]"),
    )

    # storage_locations
    op.create_table(
        "storage_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("type", sa.String(20), nullable=False),   # fridge | freezer | pantry
        sa.Column("name", sa.String(100), nullable=False),
    )
    op.create_index("ix_storage_locations_user_id", "storage_locations", ["user_id"])

    # recipes
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("ingredients", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("steps", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("kbzhu_per_serving", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("time_min", sa.Integer(), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(300), nullable=True),
        sa.Column("storage_instructions", sa.String(500), nullable=True),
        sa.Column("heating_instructions", sa.String(500), nullable=True),
    )

    # ingredients (standalone lookup table, NOT tied to a specific recipe)
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False, server_default="g"),
        sa.Column("kbzhu_per_100g", sa.JSON(), nullable=False),
        sa.Column("avg_price_rub", sa.Float(), nullable=True),
    )

    # meal_plans
    op.create_table(
        "meal_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("daily_targets", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # day_plans
    op.create_table(
        "day_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("meal_plans.id", ondelete="CASCADE"), index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
    )

    # containers (before meals — meals FK to containers)
    op.create_table(
        "containers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("label", sa.String(10), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("meal_plans.id"), index=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("storage_locations.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="empty"),
        sa.Column("contents_description", sa.String(300), nullable=True),
        sa.Column("heating_instructions", sa.String(500), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("kbzhu", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # meals
    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day_id", sa.Integer(), sa.ForeignKey("day_plans.id", ondelete="CASCADE"), index=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id"), nullable=True),
        sa.Column("container_id", sa.Integer(), sa.ForeignKey("containers.id"), nullable=True),
        sa.Column("meal_type", sa.String(20), nullable=False),
        sa.Column("portions", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("kbzhu_actual", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
    )

    # cooking_plans
    op.create_table(
        "cooking_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("meal_plans.id"), unique=True),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("estimated_time_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_time_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parallel_groups", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("container_distribution", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # cooking_steps
    op.create_table(
        "cooking_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cooking_plan_id", sa.Integer(), sa.ForeignKey("cooking_plans.id", ondelete="CASCADE"), index=True),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_parallel", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("parallel_group", sa.Integer(), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False, server_default="false"),
    )

    # prep_tasks
    op.create_table(
        "prep_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("container_id", sa.Integer(), sa.ForeignKey("containers.id"), nullable=True),
        sa.Column("type", sa.String(30), nullable=False),        # defrost | move | check_expiry
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # pending | done | skipped
    )

    # deviations
    op.create_table(
        "deviations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("meal_plans.id"), nullable=True, index=True),
        sa.Column("deviation_type", sa.String(20), nullable=False),  # planned | spontaneous
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("kbzhu_impact", sa.JSON(), nullable=True),
        sa.Column("recurrence", sa.String(50), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # shopping_lists
    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("meal_plans.id"), unique=True),
        sa.Column("week_start", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # shopping_items
    op.create_table(
        "shopping_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shopping_list_id", sa.Integer(), sa.ForeignKey("shopping_lists.id", ondelete="CASCADE"), index=True),
        sa.Column("ingredient_id", sa.Integer(), sa.ForeignKey("ingredients.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("quantity", sa.String(50), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("at_home", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
    )

    # progress_logs
    op.create_table(
        "progress_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("meals_followed", sa.Integer(), nullable=True),
        sa.Column("meals_total", sa.Integer(), nullable=True),
        sa.Column("kbzhu_actual", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("progress_logs")
    op.drop_table("shopping_items")
    op.drop_table("shopping_lists")
    op.drop_table("deviations")
    op.drop_table("prep_tasks")
    op.drop_table("cooking_steps")
    op.drop_table("cooking_plans")
    op.drop_table("meals")
    op.drop_table("containers")
    op.drop_table("day_plans")
    op.drop_table("meal_plans")
    op.drop_table("ingredients")
    op.drop_table("recipes")
    op.drop_table("storage_locations")
    op.drop_table("profiles")
    op.drop_table("users")
