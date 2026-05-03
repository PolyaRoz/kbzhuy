from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User
from app.models.post import Post, PostComment, PostLike

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


def _serialize_post(post: Post, like_count: int, comment_count: int, liked_by_me: bool) -> dict:
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

    return {
        "items": [
            _serialize_post(
                p,
                like_count=like_counts.get(p.id, 0),
                comment_count=comment_counts.get(p.id, 0),
                liked_by_me=p.id in my_likes,
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

    return _serialize_post(post, like_count=like_count, comment_count=comment_count, liked_by_me=liked_by_me)


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
