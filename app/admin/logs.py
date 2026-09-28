"""操作日志管理模块"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.data import database
from app.admin.auth import get_current_admin

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])


class LogResponse(BaseModel):
    id: int
    admin_id: str
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str


class LogListResponse(BaseModel):
    logs: List[LogResponse]
    total: int


@router.get("", response_model=LogListResponse)
async def list_logs(
    page: int = 1,
    page_size: int = 50,
    action: Optional[str] = None,
    admin_id: Optional[str] = None,
    target_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """获取操作日志列表"""
    offset = (page - 1) * page_size

    query = "SELECT * FROM admin_logs WHERE 1=1"
    params = []

    if action:
        query += " AND action = ?"
        params.append(action)

    if admin_id:
        query += " AND admin_id = ?"
        params.append(admin_id)

    if target_type:
        query += " AND target_type = ?"
        params.append(target_type)

    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date)

    if end_date:
        query += " AND created_at <= ?"
        params.append(end_date)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, offset])

    with database.connect() as conn:
        logs = [dict(row) for row in conn.execute(query, params).fetchall()]

        # 获取总数
        count_query = "SELECT COUNT(*) FROM admin_logs WHERE 1=1"
        count_params = []
        if action:
            count_query += " AND action = ?"
            count_params.append(action)
        if admin_id:
            count_query += " AND admin_id = ?"
            count_params.append(admin_id)
        if target_type:
            count_query += " AND target_type = ?"
            count_params.append(target_type)
        if start_date:
            count_query += " AND created_at >= ?"
            count_params.append(start_date)
        if end_date:
            count_query += " AND created_at <= ?"
            count_params.append(end_date)

        total = conn.execute(count_query, count_params).fetchone()[0]

    return LogListResponse(
        logs=[LogResponse(**log) for log in logs],
        total=total
    )


@router.get("/actions")
async def list_actions(
    current_admin: dict = Depends(get_current_admin)
):
    """获取所有操作类型"""
    with database.connect() as conn:
        actions = [row[0] for row in conn.execute(
            "SELECT DISTINCT action FROM admin_logs ORDER BY action"
        ).fetchall()]

    return {"actions": actions}


@router.get("/stats")
async def get_log_stats(
    current_admin: dict = Depends(get_current_admin)
):
    """获取日志统计"""
    with database.connect() as conn:
        # 按操作类型统计
        action_stats = [dict(row) for row in conn.execute(
            """SELECT action, COUNT(*) as count
               FROM admin_logs
               GROUP BY action
               ORDER BY count DESC"""
        ).fetchall()]

        # 按管理员统计
        admin_stats = [dict(row) for row in conn.execute(
            """SELECT al.admin_id, u.name, COUNT(*) as count
               FROM admin_logs al
               LEFT JOIN users u ON al.admin_id = u.id
               GROUP BY al.admin_id
               ORDER BY count DESC"""
        ).fetchall()]

        # 今日操作数
        today = datetime.now().date().isoformat()
        today_count = conn.execute(
            "SELECT COUNT(*) FROM admin_logs WHERE created_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]

        # 最近 7 天趋势
        daily_stats = [dict(row) for row in conn.execute(
            """SELECT DATE(created_at) as date, COUNT(*) as count
               FROM admin_logs
               WHERE created_at >= DATE('now', '-7 days')
               GROUP BY DATE(created_at)
               ORDER BY date"""
        ).fetchall()]

    return {
        "action_stats": action_stats,
        "admin_stats": admin_stats,
        "today_count": today_count,
        "daily_trend": daily_stats
    }


@router.get("/{log_id}")
async def get_log_detail(
    log_id: int,
    current_admin: dict = Depends(get_current_admin)
):
    """获取日志详情"""
    with database.connect() as conn:
        log = conn.execute(
            "SELECT * FROM admin_logs WHERE id = ?",
            (log_id,)
        ).fetchone()

        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Log not found"
            )

    return LogResponse(**dict(log))
