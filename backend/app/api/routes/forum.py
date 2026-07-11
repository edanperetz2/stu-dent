import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models.forum_comment import ForumComment
from app.models.forum_comment_vote import ForumCommentVote
from app.models.forum_post import ForumPost
from app.models.forum_post_vote import ForumPostVote
from app.models.user import RoleEnum, User
from app.schemas.forum import (
    ForumCommentCreate,
    ForumCommentOut,
    ForumPostCreate,
    ForumPostOut,
    ForumPostUpdate,
    VoteIn,
)
from app.services.audit import record_audit_log

router = APIRouter(tags=["forum"])


def _post_score_subquery():
    return (
        select(func.coalesce(func.sum(ForumPostVote.value), 0))
        .where(ForumPostVote.post_id == ForumPost.id)
        .scalar_subquery()
    )


def _comment_score_subquery():
    return (
        select(func.coalesce(func.sum(ForumCommentVote.value), 0))
        .where(ForumCommentVote.comment_id == ForumComment.id)
        .scalar_subquery()
    )


def _post_score(db: Session, post_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(ForumPostVote.value), 0)).where(
            ForumPostVote.post_id == post_id
        )
    )


def _comment_score(db: Session, comment_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(ForumCommentVote.value), 0)).where(
            ForumCommentVote.comment_id == comment_id
        )
    )


def _post_out(post: ForumPost, score: int) -> ForumPostOut:
    return ForumPostOut(
        id=post.id,
        author_student_id=post.author_student_id,
        title=post.title,
        body=post.body,
        score=score,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _comment_out(comment: ForumComment, score: int) -> ForumCommentOut:
    return ForumCommentOut(
        id=comment.id,
        post_id=comment.post_id,
        author_student_id=comment.author_student_id,
        body=comment.body,
        score=score,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def _get_active_post(db: Session, post_id: uuid.UUID) -> ForumPost:
    post = db.scalar(
        select(ForumPost).where(ForumPost.id == post_id, ForumPost.deleted_at.is_(None))
    )
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def _get_active_comment(db: Session, comment_id: uuid.UUID) -> ForumComment:
    comment = db.scalar(
        select(ForumComment).where(ForumComment.id == comment_id, ForumComment.deleted_at.is_(None))
    )
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


@router.post("/forum/posts", response_model=ForumPostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: ForumPostCreate,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> ForumPostOut:
    post = ForumPost(author_student_id=current_user.id, title=payload.title, body=payload.body)
    db.add(post)
    db.flush()

    record_audit_log(
        db,
        action="forum_post_create",
        actor_id=current_user.id,
        target_type="forum_post",
        target_id=post.id,
    )
    db.commit()
    db.refresh(post)
    return _post_out(post, 0)


@router.get("/forum/posts", response_model=list[ForumPostOut])
def list_posts(
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[ForumPostOut]:
    stmt = (
        select(ForumPost, _post_score_subquery().label("score"))
        .where(ForumPost.deleted_at.is_(None))
        .order_by(ForumPost.created_at.desc())
    )
    return [_post_out(post, score) for post, score in db.execute(stmt).all()]


@router.get("/forum/posts/{post_id}", response_model=ForumPostOut)
def get_post(
    post_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> ForumPostOut:
    post = _get_active_post(db, post_id)
    return _post_out(post, _post_score(db, post.id))


@router.patch("/forum/posts/{post_id}", response_model=ForumPostOut)
def update_post(
    post_id: uuid.UUID,
    payload: ForumPostUpdate,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> ForumPostOut:
    post = _get_active_post(db, post_id)
    if post.author_student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the post author")

    if payload.title is not None:
        post.title = payload.title
    if payload.body is not None:
        post.body = payload.body

    record_audit_log(
        db,
        action="forum_post_update",
        actor_id=current_user.id,
        target_type="forum_post",
        target_id=post.id,
    )
    db.commit()
    db.refresh(post)
    return _post_out(post, _post_score(db, post.id))


@router.delete("/forum/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> None:
    post = _get_active_post(db, post_id)
    is_author = post.author_student_id == current_user.id
    is_admin = current_user.role == RoleEnum.admin
    if not (is_author or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this post"
        )

    post.deleted_at = datetime.now(UTC)

    record_audit_log(
        db,
        action="forum_post_delete",
        actor_id=current_user.id,
        target_type="forum_post",
        target_id=post.id,
        extra_data={"moderation": is_admin and not is_author},
    )
    db.commit()


@router.post(
    "/forum/posts/{post_id}/comments",
    response_model=ForumCommentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: uuid.UUID,
    payload: ForumCommentCreate,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> ForumCommentOut:
    _get_active_post(db, post_id)

    comment = ForumComment(post_id=post_id, author_student_id=current_user.id, body=payload.body)
    db.add(comment)
    db.flush()

    record_audit_log(
        db,
        action="forum_comment_create",
        actor_id=current_user.id,
        target_type="forum_comment",
        target_id=comment.id,
    )
    db.commit()
    db.refresh(comment)
    return _comment_out(comment, 0)


@router.get("/forum/posts/{post_id}/comments", response_model=list[ForumCommentOut])
def list_comments(
    post_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[ForumCommentOut]:
    _get_active_post(db, post_id)

    stmt = (
        select(ForumComment, _comment_score_subquery().label("score"))
        .where(ForumComment.post_id == post_id, ForumComment.deleted_at.is_(None))
        .order_by(ForumComment.created_at.asc())
    )
    return [_comment_out(comment, score) for comment, score in db.execute(stmt).all()]


@router.delete("/forum/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> None:
    comment = _get_active_comment(db, comment_id)
    is_author = comment.author_student_id == current_user.id
    is_admin = current_user.role == RoleEnum.admin
    if not (is_author or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this comment"
        )

    comment.deleted_at = datetime.now(UTC)

    record_audit_log(
        db,
        action="forum_comment_delete",
        actor_id=current_user.id,
        target_type="forum_comment",
        target_id=comment.id,
        extra_data={"moderation": is_admin and not is_author},
    )
    db.commit()


@router.put("/forum/posts/{post_id}/vote", response_model=ForumPostOut)
def vote_on_post(
    post_id: uuid.UUID,
    payload: VoteIn,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> ForumPostOut:
    post = _get_active_post(db, post_id)

    vote = db.scalar(
        select(ForumPostVote).where(
            ForumPostVote.post_id == post_id, ForumPostVote.student_id == current_user.id
        )
    )
    if vote is None:
        db.add(ForumPostVote(post_id=post_id, student_id=current_user.id, value=payload.value))
    else:
        vote.value = payload.value
    db.commit()

    return _post_out(post, _post_score(db, post_id))


@router.delete("/forum/posts/{post_id}/vote", response_model=ForumPostOut)
def remove_post_vote(
    post_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> ForumPostOut:
    post = _get_active_post(db, post_id)

    vote = db.scalar(
        select(ForumPostVote).where(
            ForumPostVote.post_id == post_id, ForumPostVote.student_id == current_user.id
        )
    )
    if vote is not None:
        db.delete(vote)
        db.commit()

    return _post_out(post, _post_score(db, post_id))


@router.put("/forum/comments/{comment_id}/vote", response_model=ForumCommentOut)
def vote_on_comment(
    comment_id: uuid.UUID,
    payload: VoteIn,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> ForumCommentOut:
    comment = _get_active_comment(db, comment_id)

    vote = db.scalar(
        select(ForumCommentVote).where(
            ForumCommentVote.comment_id == comment_id,
            ForumCommentVote.student_id == current_user.id,
        )
    )
    if vote is None:
        db.add(
            ForumCommentVote(comment_id=comment_id, student_id=current_user.id, value=payload.value)
        )
    else:
        vote.value = payload.value
    db.commit()

    return _comment_out(comment, _comment_score(db, comment_id))


@router.delete("/forum/comments/{comment_id}/vote", response_model=ForumCommentOut)
def remove_comment_vote(
    comment_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student)),
    db: Session = Depends(get_db),
) -> ForumCommentOut:
    comment = _get_active_comment(db, comment_id)

    vote = db.scalar(
        select(ForumCommentVote).where(
            ForumCommentVote.comment_id == comment_id,
            ForumCommentVote.student_id == current_user.id,
        )
    )
    if vote is not None:
        db.delete(vote)
        db.commit()

    return _comment_out(comment, _comment_score(db, comment_id))
