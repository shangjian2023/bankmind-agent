"""定时转账调度器：到期执行、余额不足失败、超日累计安全拦截（blocked，需手动 MFA 转账）。"""

import asyncio
import uuid
from datetime import datetime, timedelta

from app import config
from app.data import repositories as repo
from app.data.database import now_iso
from app.security import audit


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
        audit.log(trace_id, t["user_id"], "scheduled_executed", intent="scheduled_transfer",
                  detail={"payee": t["payee_name"], "amount": t["amount"]})
        executed.append(t["id"])
    return executed


async def loop():
    while True:
        await asyncio.sleep(30)
        try:
            tick()
        except Exception as e:  # 后台任务不允许中断
            print(f"[scheduler] tick error: {e}")
