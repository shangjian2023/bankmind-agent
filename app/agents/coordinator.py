"""多智能体协调器：编排 IntentAgent、PlannerAgent、ExecutorAgent、ReviewerAgent 的协作流程。"""

import json
import uuid
from typing import Any

from app import config
from app.agents.intent_agent import intent_agent
from app.agents.planner_agent import planner_agent
from app.agents.executor_agent import executor_agent
from app.agents.reviewer_agent import reviewer_agent
from app.data import repositories as repo
from app.models import ChatOut
from app.security import audit, circuit, mfa, permissions
from app.tools.registry import REGISTRY, ToolError

# 会话状态存储（多轮对话）
SESSIONS = {}

HELP_TEXT = (
    "我是 BankMind 银行智能助手（模拟环境），可以：\n"
    "1. 查询余额、账单分析（含异常交易识别）\n"
    "2. 智能转账：如「给李娜转500元 备注买菜」，小额需确认，大额需短信验证码\n"
    "3. 订阅/代扣管理：如「查订阅」「取消健身房的订阅」\n"
    "4. 卡片挂失（需强验证）\n"
    "5. 生日关怀规划：如「我爱人生日快到了，帮我安排鲜花蛋糕，预算500元」"
)

ASK = {
    "amount": "请问要转多少金额？例如「500元」。",
    "budget": "请问预算是多少？例如「预算500元」。",
    "merchant": "要取消哪个订阅？例如「取消健身房的订阅」。",
    "product": "请问是哪款产品？例如「稳健90天」。可发送「推荐理财」查看列表。",
    "risk_answer": "请选择您的风险偏好：保守 / 稳健 / 进取。",
    "people": "一共几个人分摊？例如「4个人」。",
    "schedule": "什么时候执行？例如「明天上午9点」「每周五」。",
}


def _out(status, reply, trace_id=None, action_id=None, data=None, mfa_hint=None):
    return ChatOut(
        status=status,
        reply=reply,
        trace_id=trace_id,
        action_id=action_id,
        data=data or {},
        mfa_hint=mfa_hint,
    )


def _describe(intent, slots):
    """生成操作描述。"""
    if intent == "transfer":
        payee = slots.get("payee_raw") or slots.get("phone") or "（待解析联系人）"
        return (
            f"向 {payee} 转出 {slots.get('amount', 0):.2f} 元"
            + (f"，备注「{slots['memo']}」" if slots.get("memo") else "")
        )
    if intent == "subscription_cancel":
        return f"取消订阅「{slots.get('merchant', '')}」"
    if intent == "birthday_plan":
        return f"生日关怀方案，预算 {slots.get('budget') or slots.get('amount', 0):.2f} 元"
    if intent == "investment_purchase":
        return f"申购「{slots.get('product', '')}」{slots.get('amount', 0):.2f} 元"
    if intent == "investment_redeem":
        return f"赎回「{slots.get('product', '')}」持仓"
    if intent == "scheduled_transfer":
        s = slots.get("schedule") or {}
        payee = slots.get("payee_raw") or slots.get("phone") or "（待解析联系人）"
        return f"创建定时转账：向 {payee} 每次 {slots.get('amount', 0):.2f} 元，{s.get('desc', '指定时间')} 执行"
    if intent == "aa_split":
        return f"创建 AA 收款：总额 {slots.get('amount', 0):.2f} 元 ÷ {slots.get('people', '?')} 人"
    return json.dumps(slots, ensure_ascii=False)


def _build_reply(intent, results):
    """根据执行结果生成回复文本。"""
    if intent == "transfer":
        t = results.get("execute_transfer", {})
        return (
            f"转账成功：已向 {t.get('payee', '')}（{t.get('account_no', '')}）转出 {t.get('amount', 0):.2f} 元，"
            f"流水号 {t.get('txn_id', '')}，余额 {t.get('balance_after', 0):.2f} 元。"
        )
    if intent == "balance_query":
        accounts = results.get("get_balance", {}).get("accounts", [])
        return "\n".join(
            f"账户 {a['account_no']}（{a['type']}）余额 {a['balance']:.2f} 元。"
            for a in accounts
        )
    if intent in ("bill_analysis", "bill_yearly"):
        return results.get("analyze_bills", {}).get("report_text", "")
    if intent == "subscription_query":
        s = results.get("list_subscriptions", {})
        subs = s.get("subscriptions", [])
        lines = [f"生效订阅 {len(subs)} 项，月度合计 {s.get('monthly_total', 0):.2f} 元："]
        for x in subs:
            flag = "（7 天内将续费）" if x.get("renewing_soon") else ""
            lines.append(f"- {x['merchant']}：{x['amount']:.2f} 元/{x['cycle']}，下次扣费 {x['next_charge']}{flag}")
        return "\n".join(lines)
    if intent == "subscription_cancel":
        c = results.get("cancel_subscription", {})
        saved = f"，每月可省 {c.get('monthly_saved', 0):.2f} 元" if c.get("monthly_saved") else ""
        return f"已取消订阅「{c.get('cancelled', '')}」{saved}。"
    if intent == "report_loss":
        d = results.get("do_report_loss", {})
        return f"挂失成功，工单号 {d.get('ticket', '')}，卡片状态：{d.get('card_status', '')}。"
    if intent == "birthday_plan":
        return results.get("plan_birthday", {}).get("plan_text", "")
    if intent == "investment_query":
        return results.get("recommend_products", {}).get("text", "")
    if intent == "my_investments":
        return results.get("my_investments", {}).get("text", "")
    if intent == "risk_assessment":
        return results.get("save_risk", {}).get("text", "")
    if intent == "investment_purchase":
        p = results.get("execute_purchase", {})
        return (
            f"申购成功：「{p.get('product', '')}」{p.get('amount', 0):.2f} 元，参考年化 {p.get('annual_rate', 0):.2f}%，"
            f"持仓编号 #{p.get('inv_id', '')}，余额 {p.get('balance_after', 0):.2f} 元。"
        )
    if intent == "investment_redeem":
        p = results.get("execute_redeem", {})
        return f"赎回成功：「{p.get('product', '')}」本金 {p.get('amount', 0):.2f} 元已回款到活期，余额 {p.get('balance_after', 0):.2f} 元。"
    if intent == "scheduled_transfer":
        return results.get("create_scheduled", {}).get("text", "")
    if intent == "scheduled_query":
        return results.get("list_scheduled", {}).get("text", "")
    if intent == "aa_split":
        return results.get("split_aa", {}).get("text", "")
    return "操作完成。"


def handle_message(user_id: str, text: str) -> ChatOut:
    """
    处理用户消息，协调多个 Agent 完成任务。

    流程：
    1. IntentAgent: 意图识别 + 槽位填充
    2. PlannerAgent: DAG 规划
    3. 权限判定 + 确认/MFA
    4. ExecutorAgent: 工具执行
    5. ReviewerAgent: 输出审核
    """
    trace_id = uuid.uuid4().hex[:12]
    audit.log(trace_id, user_id, "receive", detail={"message": text[:300]})

    # 检查熔断
    if circuit.is_locked(user_id):
        remain = circuit.lock_remaining(user_id)
        audit.log(trace_id, user_id, "circuit_block")
        return _out("locked", f"账户已触发安全锁定，请 {remain // 60 + 1} 分钟后再试。", trace_id)

    # Phase 1: IntentAgent 意图识别
    intent_result = intent_agent.process(text)
    if not intent_result["safe"]:
        audit.log(trace_id, user_id, "guard", detail={"verdict": "rejected", "reason": intent_result["injection_reason"]})
        locked = circuit.record_suspicious(user_id)
        extra = " 连续可疑输入已触发安全锁定。" if locked else ""
        return _out("rejected", f"检测到疑似 Prompt 注入（{intent_result['injection_reason']}），请求已拒绝并记录审计。{extra}", trace_id)

    intent = intent_result["intent"]
    confidence = intent_result["confidence"]
    slots = intent_result["slots"]

    # 处理会话状态（多轮对话）
    sess = SESSIONS.get(user_id)
    if intent is None and sess:
        # 恢复之前的意图
        intent = sess["intent"]
        # 重新尝试从当前输入中提取槽位
        from app.agent import slots as slots_mod
        slots = slots_mod.extract(text)
        confidence = 0.5  # 降低置信度，表示这是上下文恢复
    if intent is None:
        audit.log(trace_id, user_id, "intent", detail={"intent": None})
        SESSIONS.pop(user_id, None)
        return _out("ok", "抱歉，我没理解您的意图。" + HELP_TEXT, trace_id)

    audit.log(trace_id, user_id, "intent", intent=intent, detail={"confidence": confidence, "source": "intent_agent"})

    # 合并会话槽位
    merged = dict(sess["slots"]) if sess and sess.get("intent") == intent else {}
    merged.update({k: v for k, v in slots.items() if v})
    if intent == "bill_yearly":
        merged.setdefault("period", "year")
    audit.log(trace_id, user_id, "slots", intent=intent, detail=merged)

    # Phase 2: PlannerAgent 任务规划
    dag_template = planner_agent.plan(intent)
    if dag_template is None:
        return _out("rejected", f"意图 {intent} 暂不支持", trace_id)

    # 处理特殊意图
    if intent == "help":
        SESSIONS.pop(user_id, None)
        return _out("ok", HELP_TEXT, trace_id)

    if intent == "abort":
        SESSIONS.pop(user_id, None)
        pending = repo.latest_pending(user_id)
        extra = ""
        if pending:
            repo.set_pending_status(pending["id"], "declined")
            extra = f"，待确认的「{pending['intent']}」操作已一并取消"
        audit.log(trace_id, user_id, "abort", detail={"cancelled_pending": pending["id"] if pending else None})
        return _out("ok", "好的，已中止当前操作" + extra + "。", trace_id)

    if intent == "human_takeover":
        SESSIONS.pop(user_id, None)
        audit.log(trace_id, user_id, "human_takeover")
        return _out(
            "ok",
            "已为您转接人工坐席（模拟）。智能助手已停止自动执行，会话与审计记录将完整移交给坐席；"
            "如需继续使用智能服务，请直接发送新的指令。",
            trace_id,
        )

    # 检查必需槽位
    required_slots = dag_template.get("required_slots", [])
    missing = [s for s in required_slots if not merged.get(s)]
    if missing:
        SESSIONS[user_id] = {"intent": intent, "slots": merged}
        audit.log(trace_id, user_id, "need_slots", intent=intent, detail={"missing": missing})
        return _out("need_slots", " ".join(ASK.get(s, f"请补充{s}") for s in missing), trace_id)

    SESSIONS.pop(user_id, None)

    # 构建 DAG
    dag = dag_template["nodes"]
    edges = [{"from": d, "to": n["id"]} for n in dag for d in n["deps"]]
    audit.log(trace_id, user_id, "plan", intent=intent, detail={"nodes": [n["id"] for n in dag], "edges": edges})

    # 转账前检查余额
    if intent == "transfer":
        acct = repo.get_primary_account(user_id)
        if not acct or acct["balance"] < merged["amount"]:
            bal = acct["balance"] if acct else 0
            audit.log(trace_id, user_id, "preflight_reject", intent=intent, detail={"reason": "余额不足", "balance": bal})
            return _out("rejected", f"余额不足：当前 {bal:.2f} 元，无法转出 {merged['amount']:.2f} 元。", trace_id)

    # 权限判定
    level, why = permissions.classify(intent, merged, user_id)
    audit.log(trace_id, user_id, "permission", intent=intent, level=level, detail={"reason": why})

    # 绿色：直接执行
    if level == permissions.GREEN:
        return _run(trace_id, user_id, intent, merged, dag, level)

    # 黄色/红色：需要确认或 MFA
    action_id = uuid.uuid4().hex[:10]
    repo.insert_pending(
        action_id,
        trace_id,
        user_id,
        intent,
        merged,
        dag,
        level,
        mfa_code=mfa.issue() if level == permissions.RED else None,
    )

    if level == permissions.YELLOW:
        audit.log(trace_id, user_id, "confirm_request", intent=intent, level=level, detail=merged)
        return _out(
            "need_confirm",
            f"【{permissions.LEVEL_DESC[level]}】{why}\n{_describe(intent, merged)}\n请确认是否执行。",
            trace_id,
            action_id,
            {"slots": merged, "level": level},
        )

    # 红色：MFA
    audit.log(trace_id, user_id, "mfa_issue", intent=intent, level=level)
    hint = None
    if config.DEV_SHOW_MFA_CODE:
        hint = f"（演示环境模拟短信验证码：{repo.get_pending(action_id)['mfa_code']}）"
    return _out(
        "need_mfa",
        f"【{permissions.LEVEL_DESC[level]}】{why}\n{_describe(intent, merged)}\n已发送短信验证码（模拟），请输入 6 位验证码。{hint or ''}",
        trace_id,
        action_id,
        {"slots": merged, "level": level},
        mfa_hint=hint,
    )


def _run(trace_id, user_id, intent, slots, dag, level):
    """执行 DAG 并审核结果。"""
    ctx = {"user_id": user_id, "slots": slots, "results": {}}
    order = planner_agent.get_execution_order(dag)
    nodes = {n["id"]: n for n in dag}

    try:
        # ExecutorAgent 执行
        execution_result = executor_agent.execute_dag(dag, order, ctx)
        for nid, res in execution_result.items():
            audit.log(trace_id, user_id, f"tool:{nid}", intent=intent, level=level, detail={"output": res})

        # ReviewerAgent 审核
        review_result = reviewer_agent.review_output(intent, execution_result, slots)
        if not review_result["approved"]:
            audit.log(trace_id, user_id, "review_rejected", intent=intent, detail={"reason": review_result["reason"]})
            return _out("rejected", f"操作被拒绝：{review_result['reason']}", trace_id)

        circuit.record_success(user_id)
        audit.log(trace_id, user_id, "done", intent=intent, level=level)
        return _out("ok", _build_reply(intent, execution_result), trace_id, data=_compact(execution_result))

    except ToolError as e:
        circuit.record_failure(user_id)
        audit.log(trace_id, user_id, "tool_error", intent=intent, level=level, detail={"error": str(e)})
        return _out("rejected", f"操作未完成：{e}", trace_id)


def _compact(results):
    """压缩结果数据。"""
    keep_keys = {"accounts", "subscriptions", "anomalies_big", "anomalies_duplicate", "monthly_series", "category_totals"}
    out = {}
    for k, v in results.items():
        if isinstance(v, dict):
            out[k] = {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict)) or kk in keep_keys}
    return out


def confirm_action(action_id, approve):
    """确认操作。"""
    row, err = _load_pending(action_id)
    if err:
        return err
    if row["status"] != "pending":
        return _out("rejected", f"该操作已处理（当前状态 {row['status']}），不能重复确认。")
    if row["level"] != permissions.YELLOW:
        return _out("rejected", "红色操作需先通过 MFA 验证，不能直接确认。")
    if not approve:
        repo.set_pending_status(action_id, "declined")
        audit.log(row["trace_id"], row["user_id"], "confirm_declined", intent=row["intent"], level=row["level"])
        return _out("ok", "已按您的指示取消该操作。", row["trace_id"], action_id)
    audit.log(row["trace_id"], row["user_id"], "confirm_approved", intent=row["intent"], level=row["level"])
    out = _run(row["trace_id"], row["user_id"], row["intent"], json.loads(row["slots"]), json.loads(row["dag"]), row["level"])
    repo.set_pending_status(action_id, "executed" if out.status == "ok" else "failed")
    out.action_id = action_id
    return out


def verify_mfa(action_id, code):
    """验证 MFA。"""
    row, err = _load_pending(action_id)
    if err:
        return err
    if row["status"] != "pending":
        return _out("rejected", f"该操作已处理（当前状态 {row['status']}）。")
    if row["level"] != permissions.RED:
        return _out("rejected", "该操作不需要 MFA。")
    if code == row["mfa_code"]:
        audit.log(row["trace_id"], row["user_id"], "mfa_verify", intent=row["intent"], level="red", detail={"result": "pass"})
        out = _run(row["trace_id"], row["user_id"], row["intent"], json.loads(row["slots"]), json.loads(row["dag"]), row["level"])
        repo.set_pending_status(action_id, "executed" if out.status == "ok" else "failed")
        out.action_id = action_id
        return out
    mfa.failed(action_id)
    audit.log(row["trace_id"], row["user_id"], "mfa_verify", intent=row["intent"], level="red", detail={"result": "fail"})
    fresh = repo.get_pending(action_id)
    if mfa.attempts_exhausted(fresh):
        repo.set_pending_status(action_id, "cancelled")
        circuit.record_failure(row["user_id"])
        audit.log(row["trace_id"], row["user_id"], "mfa_exhausted", intent=row["intent"], level="red")
        return _out("rejected", "验证码错误次数已达上限，操作已取消并记录风控事件。", row["trace_id"], action_id)
    left = config.MFA_MAX_ATTEMPTS - fresh["mfa_attempts"]
    return _out("need_mfa", f"验证码错误，剩余 {left} 次机会。", row["trace_id"], action_id)


def _load_pending(action_id):
    """加载待处理操作。"""
    row = repo.get_pending(action_id)
    if not row:
        return None, _out("rejected", "操作不存在或已过期。")
    return row, None
