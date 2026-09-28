"""管理员认证模块"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.data import database

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
security = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: str
    role: str
    expires_at: str


class UserInfo(BaseModel):
    id: str
    name: str
    role: str
    email: Optional[str]


def hash_password(password: str, salt: str) -> str:
    """密码哈希"""
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()


def generate_token() -> str:
    """生成会话 token"""
    return secrets.token_urlsafe(32)


def create_session(user_id: str, ip_address: str = "", user_agent: str = "") -> dict:
    """创建用户会话"""
    session_id = generate_token()
    token_hash = hash_password(session_id, user_id)
    expires_at = datetime.now() + timedelta(hours=24)

    with database.connect() as conn:
        conn.execute(
            """INSERT INTO user_sessions
               (id, user_id, token_hash, expires_at, created_at, last_activity, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, token_hash, expires_at.isoformat(),
             datetime.now().isoformat(), datetime.now().isoformat(), ip_address, user_agent)
        )

    return {
        "session_id": session_id,
        "expires_at": expires_at.isoformat()
    }


def validate_session(token: str) -> Optional[dict]:
    """验证会话 token"""
    with database.connect() as conn:
        row = conn.execute(
            """SELECT us.*, u.name, u.role
               FROM user_sessions us
               JOIN users u ON us.user_id = u.id
               WHERE us.id = ? AND us.expires_at > ?""",
            (token, datetime.now().isoformat())
        ).fetchone()

        if row:
            # 更新最后活动时间
            conn.execute(
                "UPDATE user_sessions SET last_activity = ? WHERE id = ?",
                (datetime.now().isoformat(), token)
            )
            return dict(row)
    return None


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前管理员用户"""
    session = validate_session(credentials.credentials)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    if session["role"] not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    return session


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """管理员登录"""
    with database.connect() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE name = ? AND status = 'active'",
            (request.username,)
        ).fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        user = dict(user)

        # 验证密码
        password_hash = hash_password(request.password, user["id"])
        if user.get("password_hash") != password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if user.get("role") not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not an administrator"
            )

        # 创建会话
        session = create_session(user["id"])

        # 更新最后登录时间
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(), user["id"])
        )

        return LoginResponse(
            token=session["session_id"],
            user_id=user["id"],
            role=user["role"],
            expires_at=session["expires_at"]
        )


@router.post("/logout")
async def logout(current_admin: dict = Depends(get_current_admin)):
    """管理员登出"""
    with database.connect() as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE user_id = ?",
            (current_admin["user_id"],)
        )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_admin: dict = Depends(get_current_admin)):
    """获取当前用户信息"""
    return UserInfo(
        id=current_admin["user_id"],
        name=current_admin["name"],
        role=current_admin["role"],
        email=current_admin.get("email")
    )
