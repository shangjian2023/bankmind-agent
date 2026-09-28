"""API Key 管理模块"""

import base64
import hashlib
from datetime import datetime
from typing import Optional, List
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.data import database
from app.admin.auth import get_current_admin
from app import config

router = APIRouter(prefix="/admin/api-keys", tags=["admin-api-keys"])

# 加密密钥（从环境变量或配置获取）
ENCRYPTION_KEY = config.SECRET_KEY.encode() if hasattr(config, 'SECRET_KEY') else b'default-key-change-in-production'
cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(ENCRYPTION_KEY).digest()))


def encrypt_api_key(api_key: str) -> str:
    """加密 API Key"""
    return cipher.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """解密 API Key"""
    return cipher.decrypt(encrypted_key.encode()).decode()


class APIKeyCreate(BaseModel):
    provider: str
    key_name: str
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    rate_limit: int = 60
    daily_limit: int = 1000
    expires_at: Optional[str] = None


class APIKeyUpdate(BaseModel):
    api_key: Optional[str]
    base_url: Optional[str]
    model_name: Optional[str]
    status: Optional[str]
    rate_limit: Optional[int]
    daily_limit: Optional[int]
    expires_at: Optional[str]


class APIKeyResponse(BaseModel):
    id: int
    user_id: str
    provider: str
    key_name: str
    base_url: Optional[str]
    model_name: Optional[str]
    status: str
    rate_limit: int
    daily_limit: int
    created_at: str
    expires_at: Optional[str]
    # 不返回实际 API Key
    api_key_masked: str


class APIKeyListResponse(BaseModel):
    keys: List[APIKeyResponse]
    total: int


def mask_api_key(api_key: str) -> str:
    """掩码 API Key，只显示前4位和后4位"""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    provider: Optional[str] = None,
    status: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """获取 API Key 列表"""
    query = "SELECT * FROM api_keys WHERE 1=1"
    params = []

    if provider:
        query += " AND provider = ?"
        params.append(provider)

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"

    with database.connect() as conn:
        keys = [dict(row) for row in conn.execute(query, params).fetchall()]

    # 解密并掩码 API Key
    for key in keys:
        try:
            decrypted = decrypt_api_key(key["api_key_encrypted"])
            key["api_key_masked"] = mask_api_key(decrypted)
        except:
            key["api_key_masked"] = "****"
        del key["api_key_encrypted"]

    return APIKeyListResponse(
        keys=[APIKeyResponse(**key) for key in keys],
        total=len(keys)
    )


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """创建 API Key"""
    encrypted_key = encrypt_api_key(key_data.api_key)
    now = datetime.now().isoformat()

    with database.connect() as conn:
        cursor = conn.execute(
            """INSERT INTO api_keys
               (user_id, provider, key_name, api_key_encrypted, base_url, model_name,
                status, rate_limit, daily_limit, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
            (current_admin["user_id"], key_data.provider, key_data.key_name,
             encrypted_key, key_data.base_url, key_data.model_name,
             key_data.rate_limit, key_data.daily_limit, now, key_data.expires_at)
        )

        key_id = cursor.lastrowid

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'create_api_key', 'api_key', ?, ?, ?)""",
            (current_admin["user_id"], str(key_id),
             f'{{"provider": "{key_data.provider}", "key_name": "{key_data.key_name}"}}',
             now)
        )

        key = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?",
            (key_id,)
        ).fetchone()

    key_dict = dict(key)
    key_dict["api_key_masked"] = mask_api_key(key_data.api_key)
    del key_dict["api_key_encrypted"]

    return APIKeyResponse(**key_dict)


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """获取 API Key 详情"""
    with database.connect() as conn:
        key = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?",
            (key_id,)
        ).fetchone()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found"
            )

    key_dict = dict(key)
    try:
        decrypted = decrypt_api_key(key_dict["api_key_encrypted"])
        key_dict["api_key_masked"] = mask_api_key(decrypted)
    except:
        key_dict["api_key_masked"] = "****"
    del key_dict["api_key_encrypted"]

    return APIKeyResponse(**key_dict)


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    key_data: APIKeyUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """更新 API Key"""
    with database.connect() as conn:
        key = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?",
            (key_id,)
        ).fetchone()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found"
            )

        updates = []
        params = []

        if key_data.api_key is not None:
            updates.append("api_key_encrypted = ?")
            params.append(encrypt_api_key(key_data.api_key))
        if key_data.base_url is not None:
            updates.append("base_url = ?")
            params.append(key_data.base_url)
        if key_data.model_name is not None:
            updates.append("model_name = ?")
            params.append(key_data.model_name)
        if key_data.status is not None:
            updates.append("status = ?")
            params.append(key_data.status)
        if key_data.rate_limit is not None:
            updates.append("rate_limit = ?")
            params.append(key_data.rate_limit)
        if key_data.daily_limit is not None:
            updates.append("daily_limit = ?")
            params.append(key_data.daily_limit)
        if key_data.expires_at is not None:
            updates.append("expires_at = ?")
            params.append(key_data.expires_at)

        if updates:
            params.append(key_id)
            conn.execute(
                f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?",
                params
            )

            # 记录操作日志
            conn.execute(
                """INSERT INTO admin_logs
                   (admin_id, action, target_type, target_id, details, created_at)
                   VALUES (?, 'update_api_key', 'api_key', ?, ?, ?)""",
                (current_admin["user_id"], str(key_id),
                 str({k: v for k, v in key_data.dict().items() if v is not None}),
                 datetime.now().isoformat())
            )

        updated_key = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?",
            (key_id,)
        ).fetchone()

    key_dict = dict(updated_key)
    try:
        decrypted = decrypt_api_key(key_dict["api_key_encrypted"])
        key_dict["api_key_masked"] = mask_api_key(decrypted)
    except:
        key_dict["api_key_masked"] = "****"
    del key_dict["api_key_encrypted"]

    return APIKeyResponse(**key_dict)


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """删除 API Key"""
    with database.connect() as conn:
        key = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?",
            (key_id,)
        ).fetchone()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found"
            )

        conn.execute(
            "DELETE FROM api_keys WHERE id = ?",
            (key_id,)
        )

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'delete_api_key', 'api_key', ?, ?, ?)""",
            (current_admin["user_id"], str(key_id),
             f'{{"provider": "{key["provider"]}", "key_name": "{key["key_name"]}"}}',
             datetime.now().isoformat())
        )

    return {"message": "API Key deleted successfully"}


@router.post("/{key_id}/test")
async def test_api_key(
    key_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """测试 API Key 是否可用"""
    with database.connect() as conn:
        key = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?",
            (key_id,)
        ).fetchone()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found"
            )

    try:
        decrypted_key = decrypt_api_key(key["api_key_encrypted"])

        # 根据 provider 测试 API Key
        if key["provider"] == "openai":
            import httpx
            response = httpx.post(
                f"{key['base_url']}/models",
                headers={"Authorization": f"Bearer {decrypted_key}"},
                timeout=10
            )
            if response.status_code == 200:
                return {"status": "success", "message": "API Key is valid"}
            else:
                return {"status": "error", "message": f"API Key invalid: {response.text}"}
        else:
            return {"status": "warning", "message": f"Testing for {key['provider']} not implemented"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
