"""编排器：意图→槽位→DAG→权限→确认/MFA→执行→审计，trace_id 贯穿全链路。"""

import json
import uuid

from app import config
from app.agent import intent as intent_mod
from app.agent import planner
from app.agent import slots as slots_mod
from app.agent.guard import check_injection
from app.data import repositories as repo
from app.models import ChatOut
from app.security import audit, circuit, mfa, permissions
from app.tools.registry import REGISTRY, ToolError

SESSIONS = {}  # user_id -> {"intent": str, "slots": dict}，多轮槽位补全用

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


def handle_message(user_id, text):
    trace_id = uuid.uuid4().hex[:12]
    audit.log(trace_id, user_id, "receive", detail={"message": text[:300]})

    if circuit.is_locked(user_id):
        remain = circuit.lock_remaining(user_id)
        audit.log(trace_id, user_id, "circuit_block")
        return _out("locked", f"账户已触发安全锁定，请 {remain // 60 + 1} 分钟后再试。", trace_id)

    ok, reason = check_injection(text)
    if not ok:
        audit.log(trace_id, user_id, "guard", detail={"verdict": "rejected", "reason": reason})
        locked = circuit.record_suspicious(user_id)
        extra = " 连续可疑输入已触发安全锁定。" if locked else ""
        return _out("rejected", f"检测到疑似 Prompt 注入（{reason}），请求已拒绝并记录审计。{extra}", trace_id)

    it, conf = intent_mod.classify(text)
    sess = SESSIONS.get(user_id)
    if it is None and sess:
        it = sess["intent"]
    if it is None:
        audit.log(trace_id, user_id, "intent", detail={"intent": None})
        SESSIONS.pop(user_id, None)
        return _out("ok", "抱歉，我没理解您的意图。" + HELP_TEXT, trace_id)
    audit.log(trace_id, user_id, "intent", intent=it, detail={"confidence": conf, "source": "rule+session"})

    merged = dict(sess["slots"]) if sess and sess.get("intent") == it else {}
    merged.update({k: v for k, v in slots_mod.extract(text).items() if v})
    if it == "bill_yearly":
        merged.setdefault("period", "year")
    audit.log(trace_id, user_id, "slots", intent=it, detail=merged)

    template = planner.build(it)
    if template is None:
        return _out("rejected", f"意图 {it} 暂不支持", trace_id)

    if it == "help":
        SESSIONS.pop(user_id, None)
        return _out("ok", HELP_TEXT, trace_id)

    if it == "abort":
        SESSIONS.pop(user_id, None)
        pending = repo.latest_pending(user_id)
        extra = ""
        if pending:
            repo.set_pending_status(pending["id"], "declined")
            extra = f"，待确认的「{pending['intent']}」操作已一并取消"
        audit.log(
            trace_id, user_id, "abort", detail={"cancelled_pending": pending["id"] if pending else None}
        )
        return _out("ok", "好的，已中止当前操作" + extra + "。", trace_id)

    if it == "human_takeover":
        SESSIONS.pop(user_id, None)
        audit.log(trace_id, user_id, "human_takeover")
        return _out(
            "ok",
            "已为您转接人工坐席（模拟）。智能助手已停止自动执行，会话与审计记录将完整移交给坐席；"
            "如需继续使用智能服务，请直接发送新的指令。",
            trace_id,
        )

    missing = [s for s in template["required_slots"] if not merged.get(s)]
    if missing:
        SESSIONS[user_id] = {"intent": it, "slots": merged}
        audit.log(trace_id, user_id, "need_slots", intent=it, detail={"missing": missing})
        return _out("need_slots", " ".join(ASK.get(s, f"请补充{s}") for s in missing), trace_id)
    SESSIONS.pop(user_id, None)

    dag = template["nodes"]
    edges = [{"from": d, "to": n["id"]} for n in dag for d in n["deps"]]
    audit.log(trace_id, user_id, "plan", intent=it, detail={"nodes": [n["id"] for n in dag], "edges": edges})

    if it == "transfer":
        acct = repo.get_primary_account(user_id)
        if not acct or acct["balance"] < merged["amount"]:
            bal = acct["balance"] if acct else 0
            audit.log(trace_id, user_id, "preflight_reject", intent=it, detail={"reason": "余额不足", "balance": bal})
            return _out("rejected", f"余额不足：当前 {bal:.2f} 元，无法转出 {merged['amount']:.2f} 元。", trace_id)

    level, why = permissions.classify(it, merged, user_id)
    audit.log(trace_id, user_id, "permission", intent=it, level=level, detail={"reason": why})

    if level == permissions.GREEN:
        return _run(trace_id, user_id, it, merged, dag, level)

    action_id = uuid.uuid4().hex[:10]
    repo.insert_pending(
        action_id,
        trace_id,
        user_id,
        it,
        merged,
        dag,
        level,
        mfa_code=mfa.issue() if level == permissions.RED else None,
    )

    if level == permissions.YELLOW:
        audit.log(trace_id, user_id, "confirm_request", intent=it, level=level, detail=merged)
        return _out(
            "need_confirm",
            f"【{permissions.LEVEL_DESC[level]}】{why}\n{_describe(it, merged)}\n请确认是否执行。",
            trace_id,
            action_id,
            {"slots": merged, "level": level},
        )

    audit.log(trace_id, user_id, "mfa_issue", intent=it, level=level)
    hint = None
    if config.DEV_SHOW_MFA_CODE:
        hint = f"（演示环境模拟短信验证码：{repo.get_pending(action_id)['mfa_code']}）"
    return _out(
        "need_mfa",
        f"【{permissions.LEVEL_DESC[level]}】{why}\n{_describe(it, merged)}\n已发送短信验证码（模拟），请输入 6 位验证码。{hint or ''}",
        trace_id,
        action_id,
        {"slots": merged, "level": level},
        mfa_hint=hint,
    )


def _describe(intent, slots):
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


def _run(trace_id, user_id, it, slots, dag, level):
    ctx = {"user_id": user_id, "slots": slots, "results": {}}
    order = planner.topo_sort(dag)
    nodes = {n["id"]: n for n in dag}
    try:
        for nid in order:
            res = REGISTRY[nodes[nid]["tool"]](ctx)
            ctx["results"][nid] = res
            audit.log(trace_id, user_id, f"tool:{nid}", intent=it, level=level, detail={"output": res})
    except ToolError as e:
        circuit.record_failure(user_id)
        audit.log(trace_id, user_id, "tool_error", intent=it, level=level, detail={"error": str(e)})
        return _out("rejected", f"操作未完成：{e}", trace_id)
    circuit.record_success(user_id)
    audit.log(trace_id, user_id, "done", intent=it, level=level)
    return _out("ok", _build_reply(it, ctx["results"]), trace_id, data=_compact(ctx["results"]))


def _compact(results):
    keep_keys = {"accounts", "subscriptions", "anomalies_big", "anomalies_duplicate", "monthly_series", "category_totals"}
    out = {}
    for k, v in results.items():
        if isinstance(v, dict):
            out[k] = {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict)) or kk in keep_keys}
    return out


def _build_reply(it, r):
    """回复仅由工具返回值插值生成，杜绝编造数字（幻觉防护）。"""
    if it == "transfer":
        t = r["execute_transfer"]
        return (
            f"转账成功：已向 {t['payee']}（{t['account_no']}）转出 {t['amount']:.2f} 元，"
            f"流水号 {t['txn_id']}，余额 {t['balance_after']:.2f} 元。"
        )
    if it == "balance_query":
        return "\n".join(
            f"账户 {a['account_no']}（{a['type']}）余额 {a['balance']:.2f} 元。"
            for a in r["get_balance"]["accounts"]
        )
    if it in ("bill_analysis", "bill_yearly"):
        return r["analyze_bills"]["report_text"]
    if it == "subscription_query":
        s = r["list_subscriptions"]
        lines = [f"生效订阅 {len(s['subscriptions'])} 项，月度合计 {s['monthly_total']:.2f} 元："]
        for x in s["subscriptions"]:
            flag = "（7 天内将续费）" if x["renewing_soon"] else ""
            lines.append(f"- {x['merchant']}：{x['amount']:.2f} 元/{x['cycle']}，下次扣费 {x['next_charge']}{flag}")
        return "\n".join(lines)
    if it == "subscription_cancel":
        c = r["cancel_subscription"]
        saved = f"，每月可省 {c['monthly_saved']:.2f} 元" if c["monthly_saved"] else ""
        return f"已取消订阅「{c['cancelled']}」{saved}。"
    if it == "report_loss":
        d = r["do_report_loss"]
        return f"挂失成功，工单号 {d['ticket']}，卡片状态：{d['card_status']}。"
    if it == "birthday_plan":
        return r["plan_birthday"]["plan_text"]
    if it == "investment_query":
        return r["recommend_products"]["text"]
    if it == "my_investments":
        return r["my_investments"]["text"]
    if it == "risk_assessment":
        return r["save_risk"]["text"]
    if it == "investment_purchase":
        p = r["execute_purchase"]
        return (
            f"申购成功：「{p['product']}」{p['amount']:.2f} 元，参考年化 {p['annual_rate']:.2f}%，"
            f"持仓编号 #{p['inv_id']}，余额 {p['balance_after']:.2f} 元。"
        )
    if it == "investment_redeem":
        p = r["execute_redeem"]
        return f"赎回成功：「{p['product']}」本金 {p['amount']:.2f} 元已回款到活期，余额 {p['balance_after']:.2f} 元。"
    if it == "scheduled_transfer":
        return r["create_scheduled"]["text"]
    if it == "scheduled_query":
        return r["list_scheduled"]["text"]
    if it == "aa_split":
        return r["split_aa"]["text"]
    return "操作完成。"


def _load_pending(action_id):
    row = repo.get_pending(action_id)
    if not row:
        return None, _out("rejected", "操作不存在或已过期。")
    return row, None


def confirm_action(action_id, approve):
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
