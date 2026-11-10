from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Comment, User
from ..schemas import CommentIn, CommentOut

router = APIRouter(prefix="/api/comments", tags=["comments"])

ALLOWED_TARGETS = {"media", "album"}


def _out(comment: Comment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        target_type=comment.target_type,
        target_id=comment.target_id,
        author_id=comment.author_id,
        author_name=comment.author.username if comment.author else None,
        body=comment.body,
        created_at=comment.created_at,
    )


@router.post("", response_model=CommentOut)
def create_comment(data: CommentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.target_type not in ALLOWED_TARGETS:
        raise HTTPException(400, "target_type 必须是 media 或 album")
    if not data.body.strip():
        raise HTTPException(400, "评论内容不能为空")
    comment = Comment(
        target_type=data.target_type,
        target_id=data.target_id,
        author_id=user.id,
        body=data.body.strip(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _out(comment)


@router.get("", response_model=list[CommentOut])
def list_comments(
    target_type: str,
    target_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if target_type not in ALLOWED_TARGETS:
        raise HTTPException(400, "target_type 必须是 media 或 album")
    items = db.scalars(
        select(Comment)
        .where(Comment.target_type == target_type, Comment.target_id == target_id)
        .order_by(Comment.created_at.asc())
    ).all()
    return [_out(c) for c in items]


@router.delete("/{comment_id}")
def delete_comment(comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(404, "评论不存在")
    # 家庭内用户等权，均可删除
    db.delete(comment)
    db.commit()
    return {"ok": True}
