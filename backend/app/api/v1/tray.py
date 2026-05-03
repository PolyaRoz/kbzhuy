from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User
from app.models.plan import MealPlan, DayPlan, Meal
from app.models.post import Post, PostComment, PostLike, PlanRecipeRequest

router = APIRouter()


VALID_CATEGORIES = {"recipe", "lifehack", "progress", "idea", "discussion"}


# ----- Schemas -----


class PostCreate(BaseModel):
    category: str = Field(..., description="recipe | lifehack | progress | idea | discussion")
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(default="", max_length=5000)
    image_url: Optional[str] = Field(default=None, description="http(s) URL or data:image/...;base64,...")


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


# ----- Helpers -----


def _user_label(user: User | None) -> dict:
    if user is None:
        return {"id": 0, "name": "Аноним"}
    name = (user.email or "").split("@")[0] or f"user{user.id}"
    return {"id": user.id, "name": name}


def _serialize_post(
    post: Post,
    like_count: int,
    comment_count: int,
    liked_by_me: bool,
    queued_for_plan: bool = False,
) -> dict:
    return {
        "id": post.id,
        "category": post.category,
        "title": post.title,
        "text": post.text,
        "image_url": post.image_url,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "author": _user_label(post.user),
        "like_count": like_count,
        "comment_count": comment_count,
        "liked_by_me": liked_by_me,
        "queued_for_plan": queued_for_plan,
    }


# ----- Posts -----


@router.get("/posts")
async def list_posts(
    category: Optional[str] = Query(default=None),
    my: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")

    stmt = select(Post).options(selectinload(Post.user)).order_by(Post.created_at.desc()).offset(offset).limit(limit)
    if my:
        stmt = stmt.where(Post.user_id == user_id)
    if category:
        stmt = stmt.where(Post.category == category)
    posts = (await db.execute(stmt)).scalars().all()

    if not posts:
        return {"items": []}

    post_ids = [p.id for p in posts]

    # Aggregate counts
    like_counts_rows = (
        await db.execute(
            select(PostLike.post_id, func.count(PostLike.id))
            .where(PostLike.post_id.in_(post_ids))
            .group_by(PostLike.post_id)
        )
    ).all()
    like_counts = {pid: cnt for pid, cnt in like_counts_rows}

    comment_counts_rows = (
        await db.execute(
            select(PostComment.post_id, func.count(PostComment.id))
            .where(PostComment.post_id.in_(post_ids))
            .group_by(PostComment.post_id)
        )
    ).all()
    comment_counts = {pid: cnt for pid, cnt in comment_counts_rows}

    my_likes_rows = (
        await db.execute(
            select(PostLike.post_id)
            .where(PostLike.post_id.in_(post_ids))
            .where(PostLike.user_id == user_id)
        )
    ).all()
    my_likes = {row[0] for row in my_likes_rows}

    # Plan-queue status: button stays "В плане" while either
    #   (a) request is still pending (NULL used_in_plan_id), or
    #   (b) request was eagerly inserted into a still-active future plan.
    today = date.today()
    my_queued_rows = (
        await db.execute(
            select(PlanRecipeRequest.post_id)
            .outerjoin(MealPlan, MealPlan.id == PlanRecipeRequest.used_in_plan_id)
            .where(PlanRecipeRequest.post_id.in_(post_ids))
            .where(PlanRecipeRequest.user_id == user_id)
            .where(
                or_(
                    PlanRecipeRequest.used_in_plan_id.is_(None),
                    and_(MealPlan.status == "active", MealPlan.period_end >= today),
                )
            )
        )
    ).all()
    my_queued = {row[0] for row in my_queued_rows}

    return {
        "items": [
            _serialize_post(
                p,
                like_count=like_counts.get(p.id, 0),
                comment_count=comment_counts.get(p.id, 0),
                liked_by_me=p.id in my_likes,
                queued_for_plan=p.id in my_queued,
            )
            for p in posts
        ]
    }


@router.post("/posts")
async def create_post(
    body: PostCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")

    post = Post(
        user_id=user_id,
        category=body.category,
        title=body.title.strip(),
        text=body.text.strip(),
        image_url=(body.image_url or None),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post, ["user"])
    return _serialize_post(post, like_count=0, comment_count=0, liked_by_me=False)


@router.get("/posts/{post_id}")
async def get_post(
    post_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    post = (
        await db.execute(
            select(Post).options(selectinload(Post.user)).where(Post.id == post_id)
        )
    ).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    like_count = (await db.execute(select(func.count(PostLike.id)).where(PostLike.post_id == post_id))).scalar() or 0
    comment_count = (await db.execute(select(func.count(PostComment.id)).where(PostComment.post_id == post_id))).scalar() or 0
    liked_by_me = (
        await db.execute(
            select(PostLike.id).where(PostLike.post_id == post_id).where(PostLike.user_id == user_id)
        )
    ).first() is not None
    queued_for_plan = (
        await db.execute(
            select(PlanRecipeRequest.id)
            .outerjoin(MealPlan, MealPlan.id == PlanRecipeRequest.used_in_plan_id)
            .where(PlanRecipeRequest.post_id == post_id)
            .where(PlanRecipeRequest.user_id == user_id)
            .where(
                or_(
                    PlanRecipeRequest.used_in_plan_id.is_(None),
                    and_(MealPlan.status == "active", MealPlan.period_end >= date.today()),
                )
            )
        )
    ).first() is not None

    return _serialize_post(
        post,
        like_count=like_count,
        comment_count=comment_count,
        liked_by_me=liked_by_me,
        queued_for_plan=queued_for_plan,
    )


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your post")
    await db.delete(post)
    await db.commit()
    return {"status": "deleted"}


# ----- Likes -----


@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    post_exists = (await db.execute(select(Post.id).where(Post.id == post_id))).first()
    if post_exists is None:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = (
        await db.execute(
            select(PostLike).where(PostLike.post_id == post_id).where(PostLike.user_id == user_id)
        )
    ).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        liked = False
    else:
        db.add(PostLike(post_id=post_id, user_id=user_id))
        liked = True

    await db.commit()
    like_count = (await db.execute(select(func.count(PostLike.id)).where(PostLike.post_id == post_id))).scalar() or 0
    return {"liked": liked, "like_count": like_count}


# ----- Plan-queue -----


async def _insert_into_existing_future_plan(
    db: AsyncSession, user_id: int, title: str
) -> int | None:
    """If the user already has a generated plan for a future period, replace
    one of its meal slots with this recipe immediately. Returns plan_id if
    inserted, None otherwise.
    """
    today = date.today()
    result = await db.execute(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .where(MealPlan.status == "active")
        .where(MealPlan.period_start > today)
        .order_by(MealPlan.period_start.asc())
        .options(
            selectinload(MealPlan.days)
            .selectinload(DayPlan.meals)
            .selectinload(Meal.container)
        )
    )
    future_plan = result.scalars().first()
    if not future_plan or not future_plan.days:
        return None

    title_lower = title.casefold()

    # Skip if already in plan (idempotent)
    for day in future_plan.days:
        for meal in day.meals:
            desc = (meal.container.contents_description or "").casefold() if meal.container else ""
            if desc and (title_lower in desc or desc in title_lower):
                return future_plan.id  # already there, treat as success

    # Pick a slot, prioritizing lunch / main meals
    days_sorted = sorted(future_plan.days, key=lambda d: d.date)
    type_priority = (
        "lunch", "meal_2", "dinner", "meal_4",
        "breakfast", "meal_1", "snack", "meal_3",
    )
    target: Meal | None = None
    for meal_type in type_priority:
        for day in days_sorted:
            for meal in day.meals:
                if meal.meal_type == meal_type and meal.container is not None:
                    target = meal
                    break
            if target:
                break
        if target:
            break
    if target is None:
        # Fallback to any meal with a container
        for day in days_sorted:
            for meal in day.meals:
                if meal.container is not None:
                    target = meal
                    break
            if target:
                break

    if target is None or target.container is None:
        return None

    target.container.contents_description = title
    target.container.heating_instructions = (
        "Твой рецепт из ленты «Поднос» — приготовь по своему усмотрению"
    )
    return future_plan.id


@router.post("/posts/{post_id}/plan-request")
async def toggle_plan_request(
    post_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Toggle whether a recipe post is queued for the next generated meal plan.

    Behaviour:
    - Always toggles the queue entry (PlanRecipeRequest row).
    - If the user already has a generated plan for a future period, inserts
      the recipe into it immediately (so it shows up without a regeneration).
    - Otherwise the recipe stays queued and is applied during the next
      `POST /plan/generate` for a future week.

    Only posts with category='recipe' can be queued.
    Returns {"queued": bool, "title": str, "applied_to_plan_id": int | None}.
    """
    post = (
        await db.execute(
            select(Post).where(Post.id == post_id)
        )
    ).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.category != "recipe":
        raise HTTPException(status_code=400, detail="Only recipe posts can be added to a plan")

    today = date.today()
    existing = (
        await db.execute(
            select(PlanRecipeRequest)
            .outerjoin(MealPlan, MealPlan.id == PlanRecipeRequest.used_in_plan_id)
            .where(PlanRecipeRequest.post_id == post_id)
            .where(PlanRecipeRequest.user_id == user_id)
            .where(
                or_(
                    PlanRecipeRequest.used_in_plan_id.is_(None),
                    and_(MealPlan.status == "active", MealPlan.period_end >= today),
                )
            )
        )
    ).scalar_one_or_none()

    applied_plan_id: int | None = None

    if existing:
        # UNTOGGLE — drop the queue entry. If the recipe was already injected
        # into a future plan, we leave the meal slot alone (user can replace
        # it via the plan UI).
        await db.delete(existing)
        queued = False
        await db.commit()
    else:
        # TOGGLE ON. Clear stale historical entries first to avoid the
        # (user_id, post_id) unique-constraint clash for re-queueing later.
        await db.execute(
            delete(PlanRecipeRequest)
            .where(PlanRecipeRequest.user_id == user_id)
            .where(PlanRecipeRequest.post_id == post_id)
        )
        title = post.title.strip()
        # Try to inject into an already-generated future plan first
        applied_plan_id = await _insert_into_existing_future_plan(db, user_id, title)

        request = PlanRecipeRequest(
            user_id=user_id,
            post_id=post_id,
            title=title,
            used_in_plan_id=applied_plan_id,  # set when eagerly inserted
        )
        db.add(request)
        queued = True
        await db.commit()

    return {"queued": queued, "title": post.title, "applied_to_plan_id": applied_plan_id}


# ----- Comments -----


@router.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(PostComment)
            .options(selectinload(PostComment.user))
            .where(PostComment.post_id == post_id)
            .order_by(PostComment.created_at.asc())
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": c.id,
                "text": c.text,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "author": _user_label(c.user),
                "is_mine": c.user_id == user_id,
            }
            for c in rows
        ]
    }


@router.post("/posts/{post_id}/comments")
async def add_comment(
    post_id: int,
    body: CommentCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    post_exists = (await db.execute(select(Post.id).where(Post.id == post_id))).first()
    if post_exists is None:
        raise HTTPException(status_code=404, detail="Post not found")
    comment = PostComment(post_id=post_id, user_id=user_id, text=body.text.strip())
    db.add(comment)
    await db.commit()
    await db.refresh(comment, ["user"])
    return {
        "id": comment.id,
        "text": comment.text,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "author": _user_label(comment.user),
        "is_mine": True,
    }


@router.delete("/posts/{post_id}/comments/{comment_id}")
async def delete_comment(
    post_id: int,
    comment_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    comment = (
        await db.execute(
            select(PostComment).where(PostComment.id == comment_id).where(PostComment.post_id == post_id)
        )
    ).scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your comment")
    await db.delete(comment)
    await db.commit()
    return {"status": "deleted"}
