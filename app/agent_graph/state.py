"""LangGraph 图状态定义。"""

from typing import TypedDict


class BankState(TypedDict, total=False):
    user_id: str
    text: str
    trace_id: str
    # 任意节点置 stop=True 并填 chat_out 即短路到 END
    stop: bool
    chat_out: dict
    # 意图与槽位
    intent: str
    confidence: float
    slots: dict
    required_slots: list
    # 规划
    dag: list
    # 权限与 HITL
    level: str
    why: str
    action_id: str
    hitl_payload: dict
    approved: bool
    # 执行
    results: dict


# 多轮槽位补全会话（user_id -> {"intent", "slots"}），与 legacy 引擎同语义
SESSIONS: dict[str, dict] = {}
