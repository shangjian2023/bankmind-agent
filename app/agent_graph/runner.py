"""LangGraph 引擎对外入口：与 legacy orchestrator/coordinator 同签名，routes 与测试零改动切换。

handle_message / confirm_action / verify_mfa 的行为契约与 app/agent/orchestrator.py 保持一致。
"""

import uuid

from langgraph.types import Command

from app import config  # noqa: F401  （保持与其他引擎一致的导入面）
from app.agent_graph import graph as graph_mod
from app.agent_graph.state import SESSIONS
from app.data import repositories as repo
from app.models import ChatOut
from app.security import permissions


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _extract(result, thread_id: str) -> tuple[ChatOut, bool]:
    """从 invoke 结果取 ChatOut；返回 (chat_out, 是否因中断暂停)。"""
    interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
    if interrupts:
        val = interrupts[0].value
        if isinstance(val, dict):
            return ChatOut(**val), True
        return ChatOut(status="need_confirm", reply=str(val)), True
    if isinstance(result, dict) and result.get("chat_out"):
        return ChatOut(**result["chat_out"]), False
    snap = graph_mod.graph.get_state(_cfg(thread_id))
    if snap.values.get("chat_out"):
        return ChatOut(**snap.values["chat_out"]), False
    return ChatOut(status="ok", reply="操作完成。"), False


def handle_message(user_id: str, text: str) -> ChatOut:
    trace_id = uuid.uuid4().hex[:12]
    result = graph_mod.graph.invoke(
        {"user_id": user_id, "text": text, "trace_id": trace_id},
        config=_cfg(trace_id),
    )
    out, _ = _extract(result, trace_id)
    return out


def _load_pending(action_id: str):
    row = repo.get_pending(action_id)
    if not row:
        return None, ChatOut(status="rejected", reply="操作不存在或已过期。")
    return row, None


def _resume(row, payload: dict) -> ChatOut:
    thread_id = row["trace_id"]
    action_id = row["id"]
    try:
        result = graph_mod.graph.invoke(Command(resume=payload), config=_cfg(thread_id))
    except Exception:
        # 检查点在内存中，服务重启后线程丢失：pending 行仍在，但图无法恢复
        return ChatOut(
            status="rejected",
            reply="操作会话已失效（服务重启），请重新发起操作。",
            trace_id=thread_id,
            action_id=action_id,
        )
    out, interrupted = _extract(result, thread_id)
    out.action_id = out.action_id or action_id
    # 仅当图跑完（非重试中断）才落终态；declined/cancelled 已在图内落库，不覆盖
    if not interrupted:
        fresh = repo.get_pending(action_id)
        if fresh and fresh["status"] == "pending":
            repo.set_pending_status(action_id, "executed" if out.status == "ok" else "failed")
    return out


def confirm_action(action_id: str, approve: bool) -> ChatOut:
    row, err = _load_pending(action_id)
    if err:
        return err
    if row["status"] != "pending":
        return ChatOut(
            status="rejected",
            reply=f"该操作已处理（当前状态 {row['status']}），不能重复确认。",
            trace_id=row["trace_id"],
            action_id=action_id,
        )
    if row["level"] != permissions.YELLOW:
        return ChatOut(
            status="rejected",
            reply="红色操作需先通过 MFA 验证，不能直接确认。",
            trace_id=row["trace_id"],
            action_id=action_id,
        )
    return _resume(row, {"approve": approve})


def verify_mfa(action_id: str, code: str) -> ChatOut:
    row, err = _load_pending(action_id)
    if err:
        return err
    if row["status"] != "pending":
        return ChatOut(
            status="rejected",
            reply=f"该操作已处理（当前状态 {row['status']}）。",
            trace_id=row["trace_id"],
            action_id=action_id,
        )
    if row["level"] != permissions.RED:
        return ChatOut(
            status="rejected",
            reply="该操作不需要 MFA。",
            trace_id=row["trace_id"],
            action_id=action_id,
        )
    return _resume(row, {"code": code})


def reset_runtime():
    """测试/重置用：清空多轮会话与图检查点（InMemorySaver 中的暂停线程一并丢弃）。"""
    SESSIONS.clear()
    graph_mod.graph = graph_mod.build_graph()
