from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..auth import hash_password, verify_password, create_access_token, get_current_user
from ..config import INVITE_CODE
from ..database import get_db
from ..models import LoginLog, Media, User
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _log_login(db: Session, username: str, ip: str | None, ok: bool, user_id: int | None = None):
    db.add(LoginLog(user_id=user_id, username=username[:64], ip=(ip or "")[:64], ok=ok))


@router.post("/register", response_model=TokenOut)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if data.invite_code != INVITE_CODE:
        raise HTTPException(403, "邀请码错误")
    username = data.username.strip()
    if not username or len(data.password) < 6:
        raise HTTPException(400, "用户名不能为空，密码至少 6 位")
    exists = db.scalar(select(User).where(User.username == username))
    if exists:
        raise HTTPException(409, "用户名已存在")
    user = User(username=username, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    _log_login(db, username, request.client.host if request.client else None, True, user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username.strip()))
    ip = request.client.host if request.client else None
    if not user or not verify_password(data.password, user.password_hash):
        _log_login(db, data.username.strip(), ip, False)
        db.commit()
        raise HTTPException(401, "用户名或密码错误")
    _log_login(db, user.username, ip, True, user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.post("/refresh", response_model=TokenOut)
def refresh(user: User = Depends(get_current_user)):
    """静默续期：客户端每次打开应用时调用，换取 30 天新 token。"""
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


# ---- 账号管理（家庭平权模型：所有登录用户可查看）----

@router.get("/users")
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(User.id, User.username, User.created_at, func.count(Media.id))
        .outerjoin(Media, Media.uploader_id == User.id)
        .group_by(User.id)
        .order_by(User.id)
    ).all()
    return [
        {"id": r[0], "username": r[1], "created_at": r[2], "media_count": r[3]}
        for r in rows
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除账号。家庭信任模型：任何人可删，但不能删自己、不能删有作品的账号。"""
    if user_id == user.id:
        raise HTTPException(400, "不能删除当前登录的账号")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "账号不存在")
    n_media = db.scalar(select(func.count()).select_from(select(Media).where(Media.uploader_id == user_id).subquery()))
    if (n_media or 0) > 0:
        raise HTTPException(400, f"该账号名下还有 {n_media} 个照片/视频，请先在相册中处理后再删除")
    db.delete(target)
    db.commit()
    return {"ok": True}


@router.get("/logs")
def login_logs(limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """最近登录记录（成功+失败）。"""
    rows = db.execute(
        select(LoginLog)
        .order_by(LoginLog.created_at.desc(), LoginLog.id.desc())
        .limit(min(limit, 200))
    ).scalars().all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "ip": r.ip,
            "ok": r.ok,
            "created_at": r.created_at,
        }
        for r in rows
    ]
