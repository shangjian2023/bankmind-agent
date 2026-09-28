"""回复生成与操作描述：仅由工具返回值插值，杜绝编造数字（幻觉防护）。

供 LangGraph 引擎（app/agent_graph）使用；legacy orchestrator/coordinator 各自持有旧副本作对照。
"""

import json

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


def describe(intent, slots):
    """生成待确认操作的摘要描述（黄/红确认卡片用）。"""
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
    if intent == "card_query":
        return "查询名下卡片"
    if intent == "card_apply":
        return f"申请新卡（类型：{slots.get('card_type', 'debit')}）"
    if intent == "card_activate":
        return f"激活卡片（ID：{slots.get('card_id', '?')}）"
    if intent == "card_freeze":
        return f"冻结卡片（ID：{slots.get('card_id', '?')}）"
    if intent == "card_unfreeze":
        return f"解冻卡片（ID：{slots.get('card_id', '?')}）"
    if intent == "card_limit":
        return f"修改卡片限额（ID：{slots.get('card_id', '?')}）"
    if intent == "card_deactivate":
        return f"注销卡片（ID：{slots.get('card_id', '?')}）"
    return json.dumps(slots, ensure_ascii=False)


def build_reply(intent, r):
    """回复仅由工具返回值插值生成，杜绝编造数字（幻觉防护）。"""
    if intent == "transfer":
        t = r["execute_transfer"]
        return (
            f"转账成功：已向 {t['payee']}（{t['account_no']}）转出 {t['amount']:.2f} 元，"
            f"流水号 {t['txn_id']}，余额 {t['balance_after']:.2f} 元。"
        )
    if intent == "balance_query":
        return "\n".join(
            f"账户 {a['account_no']}（{a['type']}）余额 {a['balance']:.2f} 元。"
            for a in r["get_balance"]["accounts"]
        )
    if intent in ("bill_analysis", "bill_yearly"):
        return r["analyze_bills"]["report_text"]
    if intent == "subscription_query":
        s = r["list_subscriptions"]
        lines = [f"生效订阅 {len(s['subscriptions'])} 项，月度合计 {s['monthly_total']:.2f} 元："]
        for x in s["subscriptions"]:
            flag = "（7 天内将续费）" if x["renewing_soon"] else ""
            lines.append(f"- {x['merchant']}：{x['amount']:.2f} 元/{x['cycle']}，下次扣费 {x['next_charge']}{flag}")
        return "\n".join(lines)
    if intent == "subscription_cancel":
        c = r["cancel_subscription"]
        saved = f"，每月可省 {c['monthly_saved']:.2f} 元" if c["monthly_saved"] else ""
        return f"已取消订阅「{c['cancelled']}」{saved}。"
    if intent == "report_loss":
        d = r["do_report_loss"]
        return f"挂失成功，工单号 {d['ticket']}，卡片状态：{d['card_status']}。"
    if intent == "birthday_plan":
        return r["plan_birthday"]["plan_text"]
    if intent == "investment_query":
        return r["recommend_products"]["text"]
    if intent == "my_investments":
        return r["my_investments"]["text"]
    if intent == "risk_assessment":
        return r["save_risk"]["text"]
    if intent == "investment_purchase":
        p = r["execute_purchase"]
        return (
            f"申购成功：「{p['product']}」{p['amount']:.2f} 元，参考年化 {p['annual_rate']:.2f}%，"
            f"持仓编号 #{p['inv_id']}，余额 {p['balance_after']:.2f} 元。"
        )
    if intent == "investment_redeem":
        p = r["execute_redeem"]
        return f"赎回成功：「{p['product']}」本金 {p['amount']:.2f} 元已回款到活期，余额 {p['balance_after']:.2f} 元。"
    if intent == "scheduled_transfer":
        return r["create_scheduled"]["text"]
    if intent == "scheduled_query":
        return r["list_scheduled"]["text"]
    if intent == "aa_split":
        return r["split_aa"]["text"]
    # 卡片管理
    if intent == "card_query":
        return r["list_cards"]["text"]
    if intent == "card_apply":
        return r["apply_card"]["text"]
    if intent == "card_activate":
        return r["activate_card"]["text"]
    if intent == "card_freeze":
        return r["freeze_card"]["text"]
    if intent == "card_unfreeze":
        return r["unfreeze_card"]["text"]
    if intent == "card_limit":
        return r["update_card_limit"]["text"]
    if intent == "card_deactivate":
        return r["deactivate_card"]["text"]
    return "操作完成。"


def compact(results):
    """压缩执行结果，只保留前端展示需要的字段。"""
    keep_keys = {"accounts", "subscriptions", "anomalies_big", "anomalies_duplicate", "monthly_series", "category_totals"}
    out = {}
    for k, v in results.items():
        if isinstance(v, dict):
            out[k] = {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict)) or kk in keep_keys}
    return out
