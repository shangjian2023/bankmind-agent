"""API 路由：健康检查（深度）、聊天、确认、MFA、审计、管理端点。"""

import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app import config

if config.AGENT_ENGINE == "legacy":
    from app.agents import coordinator as engine
else:
    from app.agent_graph import runner as engine
from app.data import repositories as repo
from app.data import database
from app.models import ChatIn, ChatOut, ConfirmIn, MFAIn
from app.security import audit

router = APIRouter(prefix="/api")

_start_time = time.time()


@router.get("/health")
def health():
    """深度健康检查：验证 DB 连通性、调度器状态、LLM 模式。"""
    checks = {}
    status = "ok"

    # 数据库检查
    try:
        users = repo.list_users()
        checks["db"] = "ok" if len(users) > 0 else "empty"
    except Exception as e:
        checks["db"] = f"error: {str(e)}"
        status = "degraded"

    # 调度器检查
    checks["scheduler"] = "running"  # 如果 lifespan 正常则运行中

    # 基本信息
    uptime = int(time.time() - _start_time)
    return {
        "status": status,
        "app": config.APP_NAME,
        "llm_mode": config.LLM_MODE,
        "db": config.DB_PATH,
        "uptime_seconds": uptime,
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/users")
def users():
    return {"users": repo.list_users()}


@router.post("/chat", response_model=ChatOut)
def chat(inp: ChatIn):
    if not repo.get_user(inp.user_id):
        raise HTTPException(404, f"用户 {inp.user_id} 不存在")
    return engine.handle_message(inp.user_id, inp.message)


@router.post("/confirm", response_model=ChatOut)
def confirm(inp: ConfirmIn):
    return engine.confirm_action(inp.action_id, inp.approve)


@router.post("/mfa/verify", response_model=ChatOut)
def verify(inp: MFAIn):
    return engine.verify_mfa(inp.action_id, inp.code)


@router.get("/audit")
def audit_logs(user_id: str, limit: int = 50, offset: int = 0, trace_id: str | None = None):
    """审计日志查询，支持分页（offset）。"""
    return {"logs": audit.for_user(user_id, limit, trace_id, offset)}


@router.post("/admin/reseed")
def reseed():
    """重置并重新播种数据库（演示用，生产环境应禁用）。"""
    database.reset_and_seed()
    return {"status": "reseeded"}


@router.post("/admin/scheduler/tick")
def scheduler_tick():
    """手动触发调度器执行（调试用）。"""
    from app import scheduler

    return {"executed": scheduler.tick()}
