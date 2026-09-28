"""用户管理模块"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.data import database
from app.admin.auth import get_current_admin

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


class UserCreate(BaseModel):
    name: str
    phone: Optional[str]
    email: Optional[EmailStr]
    role: str = "customer"


class UserUpdate(BaseModel):
    name: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    role: Optional[str]
    status: Optional[str]


class UserResponse(BaseModel):
    id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    role: str
    status: str
    created_at: str
    last_login: Optional[str]


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    role: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """获取用户列表"""
    offset = (page - 1) * page_size

    query = "SELECT * FROM users WHERE 1=1"
    params = []

    if role:
        query += " AND role = ?"
        params.append(role)

    if status:
        query += " AND status = ?"
        params.append(status)

    if keyword:
        query += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)"
        keyword_param = f"%{keyword}%"
        params.extend([keyword_param, keyword_param, keyword_param])

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, offset])

    with database.connect() as conn:
        users = [dict(row) for row in conn.execute(query, params).fetchall()]

        # 获取总数
        count_query = "SELECT COUNT(*) FROM users WHERE 1=1"
        count_params = []
        if role:
            count_query += " AND role = ?"
            count_params.append(role)
        if status:
            count_query += " AND status = ?"
            count_params.append(status)
        if keyword:
            count_query += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)"
            count_params.extend([keyword_param, keyword_param, keyword_param])

        total = conn.execute(count_query, count_params).fetchone()[0]

    return UserListResponse(
        users=[UserResponse(**user) for user in users],
        total=total
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """创建用户"""
    user_id = f"u{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(2)}"
    now = datetime.now().isoformat()

    with database.connect() as conn:
        # 检查用户名是否已存在
        existing = conn.execute(
            "SELECT id FROM users WHERE name = ?",
            (user_data.name,)
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )

        conn.execute(
            """INSERT INTO users
               (id, name, phone, email, role, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?)""",
            (user_id, user_data.name, user_data.phone, user_data.email,
             user_data.role, now, now)
        )

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'create_user', 'user', ?, ?, ?)""",
            (current_admin["user_id"], user_id,
             f'{{"name": "{user_data.name}", "role": "{user_data.role}"}}', now)
        )

        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

    return UserResponse(**dict(user))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """获取用户详情"""
    with database.connect() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

    return UserResponse(**dict(user))


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """更新用户信息"""
    with database.connect() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        updates = []
        params = []

        if user_data.name is not None:
            updates.append("name = ?")
            params.append(user_data.name)
        if user_data.phone is not None:
            updates.append("phone = ?")
            params.append(user_data.phone)
        if user_data.email is not None:
            updates.append("email = ?")
            params.append(user_data.email)
        if user_data.role is not None:
            updates.append("role = ?")
            params.append(user_data.role)
        if user_data.status is not None:
            updates.append("status = ?")
            params.append(user_data.status)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(user_id)

            conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                params
            )

            # 记录操作日志
            conn.execute(
                """INSERT INTO admin_logs
                   (admin_id, action, target_type, target_id, details, created_at)
                   VALUES (?, 'update_user', 'user', ?, ?, ?)""",
                (current_admin["user_id"], user_id,
                 str({k: v for k, v in user_data.dict().items() if v is not None}),
                 datetime.now().isoformat())
            )

        updated_user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

    return UserResponse(**dict(updated_user))


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """删除用户（软删除）"""
    with database.connect() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # 软删除
        conn.execute(
            "UPDATE users SET status = 'deleted', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id)
        )

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'delete_user', 'user', ?, ?, ?)""",
            (current_admin["user_id"], user_id,
             f'{{"name": "{user["name"]}"}}', datetime.now().isoformat())
        )

    return {"message": "User deleted successfully"}


import secrets
