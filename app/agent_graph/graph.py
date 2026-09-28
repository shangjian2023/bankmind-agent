"""LangGraph 编排图：guard→intent→planner→slots→preflight→permission→HITL→executor→reviewer。

与 legacy 实现的对照：
- app/agent/orchestrator.py：自研单 Agent 状态机（初版基线）
- app/agents/coordinator.py：手写多 Agent 协调器（复制改造，保留作对照）
- 本模块：图结构、中断恢复、状态持久化交给 LangGraph；业务组件原样复用
  （guard / intent / planner / slots / permissions / audit / circuit / mfa / reviewer / tools）。

人工确认（黄）与 MFA（红）通过 interrupt() 暂停图，由 runner 以 Command(resume=...) 恢复；
thread_id = trace_id；pending 行照旧写数据库（审计、防重复确认、abort 联动、管理端可见）。
"""

import uuid

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app import config
from app.agent import intent as intent_mod
from app.agent import planner
from app.agent import replies
from app.agent import slots as slots_mod
from app.agent.guard import check_injection
from app.agent.reviewer import reviewer
from app.agent_graph.state import SESSIONS, BankState
from app.data import database
from app.data import repositories as repo
from app.security import audit, circuit, mfa, permissions
from app.tools.registry import REGISTRY, ToolError


def _chat(status, reply, trace_id=None, action_id=None, data=None, mfa_hint=None):
    """构造 chat_out 状态字段（与 app.models.ChatOut 同构）。"""
    return {
        "status": status,
        "reply": reply,
        "trace_id": trace_id,
        "action_id": action_id,
        "data": data or {},
        "mfa_hint": mfa_hint,
    }


# ---------------------------------------------------------------- 节点


def guard_node(state: BankState) -> dict:
    """入口闸门：熔断锁定检查 + Prompt 注入防御。"""
    user_id, text, trace_id = state["user_id"], state["text"], state["trace_id"]
    audit.log(trace_id, user_id, "receive", detail={"message": text[:300]})

    if circuit.is_locked(user_id):
        remain = circuit.lock_remaining(user_id)
        audit.log(trace_id, user_id, "circuit_block")
        return {"stop": True, "chat_out": _chat("locked", f"账户已触发安全锁定，请 {remain // 60 + 1} 分钟后再试。", trace_id)}

    ok, reason = check_injection(text)
    if not ok:
        audit.log(trace_id, user_id, "guard", detail={"verdict": "rejected", "reason": reason})
        locked = circuit.record_suspicious(user_id)
        extra = " 连续可疑输入已触发安全锁定。" if locked else ""
        return {
            "stop": True,
            "chat_out": _chat("rejected", f"检测到疑似 Prompt 注入（{reason}），请求已拒绝并记录审计。{extra}", trace_id),
        }
    return {}


def intent_node(state: BankState) -> dict:
    """意图识别 + 槽位提取 + 多轮会话恢复合并。"""
    user_id, text, trace_id = state["user_id"], state["text"], state["trace_id"]

    it, conf = intent_mod.classify(text)
    sess = SESSIONS.get(user_id)
    if it is None and sess:
        # 本轮没识别出意图但会话中有未完成意图：恢复意图，从本轮输入重提槽位
        it = sess["intent"]
        slots = slots_mod.extract(text)
        conf = 0.5
    elif it is not None:
        slots = slots_mod.extract(text)
    else:
        slots = {}
    if it is None:
        audit.log(trace_id, user_id, "intent", detail={"intent": None})
        SESSIONS.pop(user_id, None)
        return {"stop": True, "chat_out": _chat("ok", "抱歉，我没理解您的意图。" + replies.HELP_TEXT, trace_id)}
    audit.log(trace_id, user_id, "intent", intent=it, detail={"confidence": conf, "source": "langgraph"})

    merged = dict(sess["slots"]) if sess and sess.get("intent") == it else {}
    merged.update({k: v for k, v in slots.items() if v})
    if it == "bill_yearly":
        merged.setdefault("period", "year")
    audit.log(trace_id, user_id, "slots", intent=it, detail=merged)
    return {"intent": it, "confidence": conf, "slots": merged}


def planner_node(state: BankState) -> dict:
    """DAG 规划 + 特殊意图（帮助/中止/转人工）短路。"""
    user_id, trace_id, it = state["user_id"], state["trace_id"], state["intent"]

    template = planner.build(it)
    if template is None:
        return {"stop": True, "chat_out": _chat("rejected", f"意图 {it} 暂不支持", trace_id)}

    if it == "help":
        SESSIONS.pop(user_id, None)
        return {"stop": True, "chat_out": _chat("ok", replies.HELP_TEXT, trace_id)}

    if it == "abort":
        SESSIONS.pop(user_id, None)
        pending = repo.latest_pending(user_id)
        extra = ""
        if pending:
            repo.set_pending_status(pending["id"], "declined")
            extra = f"，待确认的「{pending['intent']}」操作已一并取消"
        audit.log(trace_id, user_id, "abort", detail={"cancelled_pending": pending["id"] if pending else None})
        return {"stop": True, "chat_out": _chat("ok", "好的，已中止当前操作" + extra + "。", trace_id)}

    if it == "human_takeover":
        SESSIONS.pop(user_id, None)
        audit.log(trace_id, user_id, "human_takeover")
        return {
            "stop": True,
            "chat_out": _chat(
                "ok",
                "已为您转接人工坐席（模拟）。智能助手已停止自动执行，会话与审计记录将完整移交给坐席；"
                "如需继续使用智能服务，请直接发送新的指令。",
                trace_id,
            ),
        }

    return {"required_slots": template["required_slots"]}


def slots_node(state: BankState) -> dict:
    """必需槽位检查：缺槽进入多轮补全，齐了落定 DAG 并记审计。"""
    user_id, trace_id, it = state["user_id"], state["trace_id"], state["intent"]
    merged = state["slots"]

    missing = [s for s in state["required_slots"] if not merged.get(s)]
    if missing:
        SESSIONS[user_id] = {"intent": it, "slots": merged}
        audit.log(trace_id, user_id, "need_slots", intent=it, detail={"missing": missing})
        return {
            "stop": True,
            "chat_out": _chat("need_slots", " ".join(replies.ASK.get(s, f"请补充{s}") for s in missing), trace_id),
        }
    SESSIONS.pop(user_id, None)

    dag = planner.build(it)["nodes"]
    edges = [{"from": d, "to": n["id"]} for n in dag for d in n["deps"]]
    audit.log(trace_id, user_id, "plan", intent=it, detail={"nodes": [n["id"] for n in dag], "edges": edges})
    return {"dag": dag}


def preflight_node(state: BankState) -> dict:
    """执行前校验：转账余额预检。"""
    user_id, trace_id, it = state["user_id"], state["trace_id"], state["intent"]
    if it == "transfer":
        merged = state["slots"]
        acct = repo.get_primary_account(user_id)
        if not acct or acct["balance"] < merged["amount"]:
            bal = acct["balance"] if acct else 0
            audit.log(trace_id, user_id, "preflight_reject", intent=it, detail={"reason": "余额不足", "balance": bal})
            return {
                "stop": True,
                "chat_out": _chat("rejected", f"余额不足：当前 {bal:.2f} 元，无法转出 {merged['amount']:.2f} 元。", trace_id),
            }
    return {}


def permission_node(state: BankState) -> dict:
    """权限分级判定；黄/红登记 pending 行等待人工介入。"""
    user_id, trace_id, it = state["user_id"], state["trace_id"], state["intent"]
    level, why = permissions.classify(it, state["slots"], user_id)
    audit.log(trace_id, user_id, "permission", intent=it, level=level, detail={"reason": why})
    updates = {"level": level, "why": why}
    if level == permissions.GREEN:
        return updates

    action_id = uuid.uuid4().hex[:10]
    repo.insert_pending(
        action_id,
        trace_id,
        user_id,
        it,
        state["slots"],
        state["dag"],
        level,
        mfa_code=mfa.issue() if level == permissions.RED else None,
    )
    updates["action_id"] = action_id
    return updates


def hitl_request_node(state: BankState) -> dict:
    """发起人工介入请求（只执行一次：审计 + 首个中断 payload 落入 state）。"""
    user_id, trace_id, it = state["user_id"], state["trace_id"], state["intent"]
    level, action_id, slots = state["level"], state["action_id"], state["slots"]

    if level == permissions.YELLOW:
        audit.log(trace_id, user_id, "confirm_request", intent=it, level=level, detail=slots)
        msg = f"【{permissions.LEVEL_DESC[level]}】{state['why']}\n{replies.describe(it, slots)}\n请确认是否执行。"
        return {"hitl_payload": _chat("need_confirm", msg, trace_id, action_id, {"slots": slots, "level": level})}

    audit.log(trace_id, user_id, "mfa_issue", intent=it, level=level)
    hint = None
    if config.DEV_SHOW_MFA_CODE:
        hint = f"（演示环境模拟短信验证码：{repo.get_pending(action_id)['mfa_code']}）"
    msg = (
        f"【{permissions.LEVEL_DESC[level]}】{state['why']}\n{replies.describe(it, slots)}\n"
        f"已发送短信验证码（模拟），请输入 6 位验证码。{hint or ''}"
    )
    return {"hitl_payload": _chat("need_mfa", msg, trace_id, action_id, {"slots": slots, "level": level}, mfa_hint=hint)}


def hitl_wait_node(state: BankState) -> dict:
    """单次中断等待用户裁决：黄色确认 / 红色 MFA。

    每次执行只调用一次 interrupt()：红验码错误时不在这里循环，
    而是更新 hitl_payload 后经自环边回到本节点再次中断（规范的 HITL 模式，
    避免同一次任务执行内多次 interrupt 的索引对位问题）。
    """
    user_id, trace_id, it = state["user_id"], state["trace_id"], state["intent"]
    level, action_id = state["level"], state["action_id"]
    ans = interrupt(state["hitl_payload"])

    if level == permissions.YELLOW:
        if ans.get("approve"):
            audit.log(trace_id, user_id, "confirm_approved", intent=it, level=level)
            return {"approved": True}
        repo.set_pending_status(action_id, "declined")
        audit.log(trace_id, user_id, "confirm_declined", intent=it, level=level)
        return {"stop": True, "chat_out": _chat("ok", "已按您的指示取消该操作。", trace_id, action_id)}

    code = ans.get("code", "")
    if code == repo.get_pending(action_id)["mfa_code"]:
        audit.log(trace_id, user_id, "mfa_verify", intent=it, level="red", detail={"result": "pass"})
        return {"approved": True}
    mfa.failed(action_id)
    audit.log(trace_id, user_id, "mfa_verify", intent=it, level="red", detail={"result": "fail"})
    fresh = repo.get_pending(action_id)
    if mfa.attempts_exhausted(fresh):
        repo.set_pending_status(action_id, "cancelled")
        circuit.record_failure(user_id)
        audit.log(trace_id, user_id, "mfa_exhausted", intent=it, level="red")
        return {
            "stop": True,
            "chat_out": _chat("rejected", "验证码错误次数已达上限，操作已取消并记录风控事件。", trace_id, action_id),
        }
    left = config.MFA_MAX_ATTEMPTS - fresh["mfa_attempts"]
    return {"hitl_payload": _chat("need_mfa", f"验证码错误，剩余 {left} 次机会。", trace_id, action_id)}


def executor_node(state: BankState) -> dict:
    """按拓扑序执行工具 DAG，事务包裹，逐节点审计。"""
    user_id, trace_id, it, level = state["user_id"], state["trace_id"], state["intent"], state["level"]
    ctx = {"user_id": user_id, "slots": state["slots"], "results": {}}
    order = planner.topo_sort(state["dag"])
    nodes = {n["id"]: n for n in state["dag"]}
    try:
        with database.transaction():
            for nid in order:
                res = REGISTRY[nodes[nid]["tool"]](ctx)
                ctx["results"][nid] = res
                audit.log(trace_id, user_id, f"tool:{nid}", intent=it, level=level, detail={"output": res})
    except ToolError as e:
        circuit.record_failure(user_id)
        audit.log(trace_id, user_id, "tool_error", intent=it, level=level, detail={"error": str(e)})
        return {"stop": True, "chat_out": _chat("rejected", f"操作未完成：{e}", trace_id)}
    return {"results": ctx["results"]}


def reviewer_node(state: BankState) -> dict:
    """输出审核：幻觉/异常/敏感信息检测，通过后生成回复。"""
    user_id, trace_id, it, level = state["user_id"], state["trace_id"], state["intent"], state["level"]
    results = state["results"]

    review = reviewer.review_output(it, results, state["slots"])
    if not review["approved"]:
        audit.log(trace_id, user_id, "review_rejected", intent=it, detail={"reason": review["reason"]})
        return {"stop": True, "chat_out": _chat("rejected", f"操作被拒绝：{review['reason']}", trace_id)}

    circuit.record_success(user_id)
    audit.log(trace_id, user_id, "done", intent=it, level=level)
    return {
        "stop": True,
        "chat_out": _chat("ok", replies.build_reply(it, results), trace_id, data=replies.compact(results)),
    }


# ---------------------------------------------------------------- 装配


def _next(name):
    """通用路由：节点已置 stop 则直接结束，否则走下一节点。"""

    def router(state: BankState) -> str:
        return END if state.get("stop") else name

    return router


def _after_permission(state: BankState) -> str:
    if state.get("stop"):
        return END
    return "executor" if state.get("level") == permissions.GREEN else "hitl_request"


def _after_hitl(state: BankState) -> str:
    if state.get("approved"):
        return "executor"
    if state.get("stop"):
        return END
    return "hitl_wait"  # 红验码错误：携重试 payload 自环，再次中断等待


def build_graph():
    g = StateGraph(BankState)
    g.add_node("guard", guard_node)
    g.add_node("intent", intent_node)
    g.add_node("planner", planner_node)
    g.add_node("slots", slots_node)
    g.add_node("preflight", preflight_node)
    g.add_node("permission", permission_node)
    g.add_node("hitl_request", hitl_request_node)
    g.add_node("hitl_wait", hitl_wait_node)
    g.add_node("executor", executor_node)
    g.add_node("reviewer", reviewer_node)

    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", _next("intent"))
    g.add_conditional_edges("intent", _next("planner"))
    g.add_conditional_edges("planner", _next("slots"))
    g.add_conditional_edges("slots", _next("preflight"))
    g.add_conditional_edges("preflight", _next("permission"))
    g.add_conditional_edges("permission", _after_permission)
    g.add_edge("hitl_request", "hitl_wait")
    g.add_conditional_edges("hitl_wait", _after_hitl)
    g.add_conditional_edges("executor", _next("reviewer"))
    g.add_edge("reviewer", END)
    return g.compile(checkpointer=InMemorySaver())


graph = build_graph()
