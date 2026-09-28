"""公告管理模块"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.data import database
from app.admin.auth import get_current_admin

router = APIRouter(prefix="/admin/announcements", tags=["admin-announcements"])


class AnnouncementCreate(BaseModel):
    title: str
    content: str
    type: str = "info"  # info, warning, critical
    priority: int = 0
    target_users: Optional[List[str]] = None  # None 表示所有用户
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class AnnouncementUpdate(BaseModel):
    title: Optional[str]
    content: Optional[str]
    type: Optional[str]
    priority: Optional[int]
    status: Optional[str]
    target_users: Optional[List[str]]
    start_time: Optional[str]
    end_time: Optional[str]


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    content: str
    type: str
    priority: int
    status: str
    target_users: Optional[List[str]]
    start_time: Optional[str]
    end_time: Optional[str]
    created_by: str
    created_at: str
    updated_at: str


class AnnouncementListResponse(BaseModel):
    announcements: List[AnnouncementResponse]
    total: int


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """获取公告列表"""
    query = "SELECT * FROM announcements WHERE 1=1"
    params = []

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    if type_filter:
        query += " AND type = ?"
        params.append(type_filter)

    query += " ORDER BY priority DESC, created_at DESC"

    with database.connect() as conn:
        announcements = [dict(row) for row in conn.execute(query, params).fetchall()]

    # 解析 target_users JSON
    import json
    for ann in announcements:
        if ann["target_users"]:
            try:
                ann["target_users"] = json.loads(ann["target_users"])
            except:
                ann["target_users"] = None

    return AnnouncementListResponse(
        announcements=[AnnouncementResponse(**ann) for ann in announcements],
        total=len(announcements)
    )


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    ann_data: AnnouncementCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """创建公告"""
    import json
    now = datetime.now().isoformat()
    target_users_json = json.dumps(ann_data.target_users) if ann_data.target_users else None

    with database.connect() as conn:
        cursor = conn.execute(
            """INSERT INTO announcements
               (title, content, type, priority, status, target_users, start_time, end_time,
                created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)""",
            (ann_data.title, ann_data.content, ann_data.type, ann_data.priority,
             target_users_json, ann_data.start_time, ann_data.end_time,
             current_admin["user_id"], now, now)
        )

        ann_id = cursor.lastrowid

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'create_announcement', 'announcement', ?, ?, ?)""",
            (current_admin["user_id"], str(ann_id),
             f'{{"title": "{ann_data.title}", "type": "{ann_data.type}"}}', now)
        )

        ann = conn.execute(
            "SELECT * FROM announcements WHERE id = ?",
            (ann_id,)
        ).fetchone()

    ann_dict = dict(ann)
    if ann_dict["target_users"]:
        try:
            ann_dict["target_users"] = json.loads(ann_dict["target_users"])
        except:
            ann_dict["target_users"] = None

    return AnnouncementResponse(**ann_dict)


@router.get("/{ann_id}", response_model=AnnouncementResponse)
async def get_announcement(
    ann_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """获取公告详情"""
    import json

    with database.connect() as conn:
        ann = conn.execute(
            "SELECT * FROM announcements WHERE id = ?",
            (ann_id,)
        ).fetchone()

        if not ann:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )

    ann_dict = dict(ann)
    if ann_dict["target_users"]:
        try:
            ann_dict["target_users"] = json.loads(ann_dict["target_users"])
        except:
            ann_dict["target_users"] = None

    return AnnouncementResponse(**ann_dict)


@router.put("/{ann_id}", response_model=AnnouncementResponse)
async def update_announcement(
    ann_id: int,
    ann_data: AnnouncementUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """更新公告"""
    import json

    with database.connect() as conn:
        ann = conn.execute(
            "SELECT * FROM announcements WHERE id = ?",
            (ann_id,)
        ).fetchone()

        if not ann:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )

        updates = []
        params = []

        if ann_data.title is not None:
            updates.append("title = ?")
            params.append(ann_data.title)
        if ann_data.content is not None:
            updates.append("content = ?")
            params.append(ann_data.content)
        if ann_data.type is not None:
            updates.append("type = ?")
            params.append(ann_data.type)
        if ann_data.priority is not None:
            updates.append("priority = ?")
            params.append(ann_data.priority)
        if ann_data.status is not None:
            updates.append("status = ?")
            params.append(ann_data.status)
        if ann_data.target_users is not None:
            updates.append("target_users = ?")
            params.append(json.dumps(ann_data.target_users))
        if ann_data.start_time is not None:
            updates.append("start_time = ?")
            params.append(ann_data.start_time)
        if ann_data.end_time is not None:
            updates.append("end_time = ?")
            params.append(ann_data.end_time)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(ann_id)

            conn.execute(
                f"UPDATE announcements SET {', '.join(updates)} WHERE id = ?",
                params
            )

            # 记录操作日志
            conn.execute(
                """INSERT INTO admin_logs
                   (admin_id, action, target_type, target_id, details, created_at)
                   VALUES (?, 'update_announcement', 'announcement', ?, ?, ?)""",
                (current_admin["user_id"], str(ann_id),
                 str({k: v for k, v in ann_data.dict().items() if v is not None}),
                 datetime.now().isoformat())
            )

        updated_ann = conn.execute(
            "SELECT * FROM announcements WHERE id = ?",
            (ann_id,)
        ).fetchone()

    ann_dict = dict(updated_ann)
    if ann_dict["target_users"]:
        try:
            ann_dict["target_users"] = json.loads(ann_dict["target_users"])
        except:
            ann_dict["target_users"] = None

    return AnnouncementResponse(**ann_dict)


@router.delete("/{ann_id}")
async def delete_announcement(
    ann_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """删除公告"""
    with database.connect() as conn:
        ann = conn.execute(
            "SELECT * FROM announcements WHERE id = ?",
            (ann_id,)
        ).fetchone()

        if not ann:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )

        conn.execute(
            "DELETE FROM announcements WHERE id = ?",
            (ann_id,)
        )

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'delete_announcement', 'announcement', ?, ?, ?)""",
            (current_admin["user_id"], str(ann_id),
             f'{{"title": "{ann["title"]}"}}', datetime.now().isoformat())
        )

    return {"message": "Announcement deleted successfully"}


@router.post("/{ann_id}/publish")
async def publish_announcement(
    ann_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """发布公告"""
    with database.connect() as conn:
        ann = conn.execute(
            "SELECT * FROM announcements WHERE id = ?",
            (ann_id,)
        ).fetchone()

        if not ann:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Announcement not found"
            )

        conn.execute(
            "UPDATE announcements SET status = 'published', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), ann_id)
        )

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'publish_announcement', 'announcement', ?, ?, ?)""",
            (current_admin["user_id"], str(ann_id),
             f'{{"title": "{ann["title"]}"}}', datetime.now().isoformat())
        )

    return {"message": "Announcement published successfully"}
