"""定时转账调度器：APScheduler 驱动；到期执行、余额不足失败、超日累计安全拦截（blocked，需手动 MFA 转账）。

tick() 保持纯函数（手动触发端点 /api/admin/scheduler/tick 与测试直接调用）；
start()/stop() 由 main.lifespan 调用，AsyncIOScheduler 每 30 秒执行一次 tick。
"""

import logging
import uuid
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import config
from app.data import database
from app.data import repositories as repo
from app.data.database import now_iso
from app.security import audit

logger = logging.getLogger("app.scheduler")


def tick():
    executed = []
    for t in repo.due_scheduled(now_iso()):
        trace_id = "sch" + uuid.uuid4().hex[:10]
        audit.log(trace_id, t["user_id"], "scheduled_due", intent="scheduled_transfer", detail=dict(t))
        acct = repo.get_primary_account(t["user_id"])
        if not acct or acct["balance"] < t["amount"]:
            repo.update_scheduled(t["id"], status="failed_insufficient")
            audit.log(trace_id, t["user_id"], "scheduled_failed", intent="scheduled_transfer",
                      detail={"reason": "余额不足"})
            continue
        if repo.sum_transferred_today(t["user_id"]) + t["amount"] > config.YELLOW_DAILY_TRANSFER_LIMIT:
            repo.update_scheduled(t["id"], status="blocked")
            audit.log(trace_id, t["user_id"], "scheduled_blocked", intent="scheduled_transfer",
                      detail={"reason": "超日累计限额，需手动发起并完成 MFA"})
            continue
        try:
            with database.transaction():
                repo.insert_transaction(
                    acct["id"], t["user_id"], f"定时转账-{t['payee_name']}", -t["amount"],
                    "transfer_out", t.get("memo") or "定时转账",
                )
                repo.debit_account(acct["id"], t["amount"])
                if t["cycle"] != "once":
                    nxt = datetime.fromisoformat(t["execute_at"]) + timedelta(days=1 if t["cycle"] == "daily" else 7)
                    repo.update_scheduled(t["id"], status="scheduled", execute_at=nxt.isoformat(timespec="seconds"))
                else:
                    repo.update_scheduled(t["id"], status="executed")
        except Exception as e:
            repo.update_scheduled(t["id"], status="failed")
            audit.log(trace_id, t["user_id"], "scheduled_failed", intent="scheduled_transfer",
                      detail={"reason": str(e)})
            logger.error(f"定时转账执行失败: {e}", extra={"task_id": t["id"], "user_id": t["user_id"]})
            continue
        audit.log(trace_id, t["user_id"], "scheduled_executed", intent="scheduled_transfer",
                  detail={"payee": t["payee_name"], "amount": t["amount"]})
        executed.append(t["id"])
    return executed


_scheduler: AsyncIOScheduler | None = None


def create_scheduler() -> AsyncIOScheduler:
    """构建调度器：30s 间隔执行 tick；单实例防堆积，错过的触发合并为一次。"""
    sch = AsyncIOScheduler(timezone="Asia/Shanghai")
    sch.add_job(
        tick,
        "interval",
        seconds=30,
        id="scheduled_transfer_tick",
        max_instances=1,
        coalesce=True,
    )
    return sch


def start():
    """启动调度器（需在运行中的事件循环内调用，如 FastAPI lifespan）。"""
    global _scheduler
    _scheduler = create_scheduler()
    _scheduler.start()
    logger.info("调度器启动（APScheduler，每 30 秒）")


def stop():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("调度器停止")


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running
