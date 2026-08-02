import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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


def _post_likes_subquery():
    return (
        select(func.count(ForumPostVote.id))
        .where(ForumPostVote.post_id == ForumPost.id, ForumPostVote.value == 1)
        .scalar_subquery()
    )


def _post_dislikes_subquery():
    return (
        select(func.count(ForumPostVote.id))
        .where(ForumPostVote.post_id == ForumPost.id, ForumPostVote.value == -1)
        .scalar_subquery()
    )


def _comment_likes_subquery():
    return (
        select(func.count(ForumCommentVote.id))
        .where(ForumCommentVote.comment_id == ForumComment.id, ForumCommentVote.value == 1)
        .scalar_subquery()
    )


def _comment_dislikes_subquery():
    return (
        select(func.count(ForumCommentVote.id))
        .where(ForumCommentVote.comment_id == ForumComment.id, ForumCommentVote.value == -1)
        .scalar_subquery()
    )


def _post_comment_count_subquery():
    return (
        select(func.count(ForumComment.id))
        .where(ForumComment.post_id == ForumPost.id, ForumComment.deleted_at.is_(None))
        .scalar_subquery()
    )


def _post_my_vote_subquery(user_id: uuid.UUID):
    return (
        select(ForumPostVote.value)
        .where(ForumPostVote.post_id == ForumPost.id, ForumPostVote.student_id == user_id)
        .scalar_subquery()
    )


def _comment_my_vote_subquery(user_id: uuid.UUID):
    return (
        select(ForumCommentVote.value)
        .where(
            ForumCommentVote.comment_id == ForumComment.id, ForumCommentVote.student_id == user_id
        )
        .scalar_subquery()
    )


def _post_comment_count(db: Session, post_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count(ForumComment.id)).where(
                ForumComment.post_id == post_id, ForumComment.deleted_at.is_(None)
            )
        )
        or 0
    )


def _post_my_vote(db: Session, post_id: uuid.UUID, user_id: uuid.UUID) -> int | None:
    return db.scalar(
        select(ForumPostVote.value).where(
            ForumPostVote.post_id == post_id, ForumPostVote.student_id == user_id
        )
    )


def _comment_my_vote(db: Session, comment_id: uuid.UUID, user_id: uuid.UUID) -> int | None:
    return db.scalar(
        select(ForumCommentVote.value).where(
            ForumCommentVote.comment_id == comment_id, ForumCommentVote.student_id == user_id
        )
    )


def _post_vote_counts(db: Session, post_id: uuid.UUID) -> tuple[int, int]:
    likes = db.scalar(
        select(func.count(ForumPostVote.id)).where(
            ForumPostVote.post_id == post_id, ForumPostVote.value == 1
        )
    )
    dislikes = db.scalar(
        select(func.count(ForumPostVote.id)).where(
            ForumPostVote.post_id == post_id, ForumPostVote.value == -1
        )
    )
    return likes, dislikes


def _comment_vote_counts(db: Session, comment_id: uuid.UUID) -> tuple[int, int]:
    likes = db.scalar(
        select(func.count(ForumCommentVote.id)).where(
            ForumCommentVote.comment_id == comment_id, ForumCommentVote.value == 1
        )
    )
    dislikes = db.scalar(
        select(func.count(ForumCommentVote.id)).where(
            ForumCommentVote.comment_id == comment_id, ForumCommentVote.value == -1
        )
    )
    return likes, dislikes


def _post_out(
    post: ForumPost, likes: int, dislikes: int, comment_count: int, my_vote: int | None
) -> ForumPostOut:
    return ForumPostOut(
        id=post.id,
        author_student_id=post.author_student_id,
        title=post.title,
        body=post.body,
        likes=likes,
        dislikes=dislikes,
        comment_count=comment_count,
        my_vote=my_vote,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _comment_out(
    comment: ForumComment, likes: int, dislikes: int, my_vote: int | None
) -> ForumCommentOut:
    return ForumCommentOut(
        id=comment.id,
        post_id=comment.post_id,
        author_student_id=comment.author_student_id,
        body=comment.body,
        likes=likes,
        dislikes=dislikes,
        my_vote=my_vote,
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
    return _post_out(post, 0, 0, 0, None)


@router.get("/forum/posts", response_model=list[ForumPostOut])
def list_posts(
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[ForumPostOut]:
    stmt = (
        select(
            ForumPost,
            _post_likes_subquery().label("likes"),
            _post_dislikes_subquery().label("dislikes"),
            _post_comment_count_subquery().label("comment_count"),
            _post_my_vote_subquery(current_user.id).label("my_vote"),
        )
        .where(ForumPost.deleted_at.is_(None))
        .order_by(ForumPost.created_at.desc())
        # Defensive cap, not full pagination (out of scope for this fix) --
        # posts are never hard-deleted, so this list grows monotonically.
        .limit(500)
    )
    return [
        _post_out(post, likes, dislikes, comment_count, my_vote)
        for post, likes, dislikes, comment_count, my_vote in db.execute(stmt).all()
    ]


@router.get("/forum/posts/{post_id}", response_model=ForumPostOut)
def get_post(
    post_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> ForumPostOut:
    post = _get_active_post(db, post_id)
    likes, dislikes = _post_vote_counts(db, post.id)
    comment_count = _post_comment_count(db, post.id)
    my_vote = _post_my_vote(db, post.id, current_user.id)
    return _post_out(post, likes, dislikes, comment_count, my_vote)


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
    likes, dislikes = _post_vote_counts(db, post.id)
    comment_count = _post_comment_count(db, post.id)
    my_vote = _post_my_vote(db, post.id, current_user.id)
    return _post_out(post, likes, dislikes, comment_count, my_vote)


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
    return _comment_out(comment, 0, 0, None)


@router.get("/forum/posts/{post_id}/comments", response_model=list[ForumCommentOut])
def list_comments(
    post_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.student, RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> list[ForumCommentOut]:
    _get_active_post(db, post_id)

    stmt = (
        select(
            ForumComment,
            _comment_likes_subquery().label("likes"),
            _comment_dislikes_subquery().label("dislikes"),
            _comment_my_vote_subquery(current_user.id).label("my_vote"),
        )
        .where(ForumComment.post_id == post_id, ForumComment.deleted_at.is_(None))
        .order_by(ForumComment.created_at.asc())
    )
    return [
        _comment_out(comment, likes, dislikes, my_vote)
        for comment, likes, dislikes, my_vote in db.execute(stmt).all()
    ]


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
        # A SAVEPOINT, not a bare insert: two concurrent requests from the
        # same student (a real double-click, or two open tabs) can both
        # reach here having seen no existing row -- the UniqueConstraint on
        # (post_id, student_id) would otherwise surface as a bare 500
        # instead of the second request just updating the winner's row,
        # same shape as services/messaging.py::get_or_create_conversation.
        try:
            with db.begin_nested():
                vote = ForumPostVote(
                    post_id=post_id, student_id=current_user.id, value=payload.value
                )
                db.add(vote)
                db.flush()
        except IntegrityError:
            vote = db.scalar(
                select(ForumPostVote).where(
                    ForumPostVote.post_id == post_id, ForumPostVote.student_id == current_user.id
                )
            )
            if vote is None:
                raise
            vote.value = payload.value
    else:
        vote.value = payload.value

    record_audit_log(
        db,
        action="forum_post_vote",
        actor_id=current_user.id,
        target_type="forum_post",
        target_id=post.id,
        extra_data={"value": payload.value},
    )
    db.commit()

    likes, dislikes = _post_vote_counts(db, post_id)
    comment_count = _post_comment_count(db, post_id)
    return _post_out(post, likes, dislikes, comment_count, payload.value)


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
        record_audit_log(
            db,
            action="forum_post_unvote",
            actor_id=current_user.id,
            target_type="forum_post",
            target_id=post.id,
        )
        db.commit()

    likes, dislikes = _post_vote_counts(db, post_id)
    comment_count = _post_comment_count(db, post_id)
    return _post_out(post, likes, dislikes, comment_count, None)


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
        # Same concurrent-duplicate-insert race as vote_on_post above.
        try:
            with db.begin_nested():
                vote = ForumCommentVote(
                    comment_id=comment_id, student_id=current_user.id, value=payload.value
                )
                db.add(vote)
                db.flush()
        except IntegrityError:
            vote = db.scalar(
                select(ForumCommentVote).where(
                    ForumCommentVote.comment_id == comment_id,
                    ForumCommentVote.student_id == current_user.id,
                )
            )
            if vote is None:
                raise
            vote.value = payload.value
    else:
        vote.value = payload.value

    record_audit_log(
        db,
        action="forum_comment_vote",
        actor_id=current_user.id,
        target_type="forum_comment",
        target_id=comment.id,
        extra_data={"value": payload.value},
    )
    db.commit()

    likes, dislikes = _comment_vote_counts(db, comment_id)
    return _comment_out(comment, likes, dislikes, payload.value)


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
        record_audit_log(
            db,
            action="forum_comment_unvote",
            actor_id=current_user.id,
            target_type="forum_comment",
            target_id=comment.id,
        )
        db.commit()

    likes, dislikes = _comment_vote_counts(db, comment_id)
    return _comment_out(comment, likes, dislikes, None)
