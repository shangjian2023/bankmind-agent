"""DAG 任务规划：每个意图对应一张工具节点依赖图。"""

DAG_TEMPLATES = {
    "transfer": {
        "required_slots": ["amount"],
        "optional_slots": ["payee_raw", "phone", "memo"],
        "nodes": [
            {"id": "resolve_payee", "tool": "resolve_payee", "deps": []},
            {"id": "check_balance", "tool": "check_balance", "deps": ["resolve_payee"]},
            {"id": "execute_transfer", "tool": "execute_transfer", "deps": ["resolve_payee", "check_balance"]},
        ],
    },
    "balance_query": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "get_balance", "tool": "get_balance", "deps": []}],
    },
    "bill_analysis": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "analyze_bills", "tool": "analyze_bills", "deps": []}],
    },
    "subscription_query": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "list_subscriptions", "tool": "list_subscriptions", "deps": []}],
    },
    "subscription_cancel": {
        "required_slots": ["merchant"],
        "optional_slots": [],
        "nodes": [
            {"id": "find_subscription", "tool": "find_subscription", "deps": []},
            {"id": "cancel_subscription", "tool": "cancel_subscription", "deps": ["find_subscription"]},
        ],
    },
    "report_loss": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "do_report_loss", "tool": "do_report_loss", "deps": []}],
    },
    "birthday_plan": {
        "required_slots": [],
        "optional_slots": ["budget"],
        "nodes": [
            {"id": "get_balance", "tool": "get_balance", "deps": []},
            {"id": "plan_birthday", "tool": "plan_birthday", "deps": ["get_balance"]},
        ],
    },
    "help": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [],
    },
    "investment_query": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "recommend_products", "tool": "recommend_products", "deps": []}],
    },
    "my_investments": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "my_investments", "tool": "my_investments", "deps": []}],
    },
    "risk_assessment": {
        "required_slots": ["risk_answer"],
        "optional_slots": [],
        "nodes": [{"id": "save_risk", "tool": "save_risk", "deps": []}],
    },
    "investment_purchase": {
        "required_slots": ["product", "amount"],
        "optional_slots": [],
        "nodes": [
            {"id": "find_product", "tool": "find_product", "deps": []},
            {"id": "check_balance", "tool": "check_balance", "deps": ["find_product"]},
            {"id": "execute_purchase", "tool": "execute_purchase", "deps": ["find_product", "check_balance"]},
        ],
    },
    "investment_redeem": {
        "required_slots": ["product"],
        "optional_slots": [],
        "nodes": [
            {"id": "find_holding", "tool": "find_holding", "deps": []},
            {"id": "execute_redeem", "tool": "execute_redeem", "deps": ["find_holding"]},
        ],
    },
    "scheduled_transfer": {
        "required_slots": ["amount", "schedule"],
        "optional_slots": ["payee_raw", "phone", "memo"],
        "nodes": [
            {"id": "resolve_payee", "tool": "resolve_payee", "deps": []},
            {"id": "create_scheduled", "tool": "create_scheduled", "deps": ["resolve_payee"]},
        ],
    },
    "scheduled_query": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "list_scheduled", "tool": "list_scheduled", "deps": []}],
    },
    "aa_split": {
        "required_slots": ["amount", "people"],
        "optional_slots": [],
        "nodes": [{"id": "split_aa", "tool": "split_aa", "deps": []}],
    },
    "bill_yearly": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "analyze_bills", "tool": "analyze_bills", "deps": []}],
    },
    "abort": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [],
    },
    "human_takeover": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [],
    },
    # 卡片管理
    "card_query": {
        "required_slots": [],
        "optional_slots": [],
        "nodes": [{"id": "list_cards", "tool": "list_cards", "deps": []}],
    },
    "card_apply": {
        "required_slots": [],
        "optional_slots": ["card_type"],
        "nodes": [{"id": "apply_card", "tool": "apply_card", "deps": []}],
    },
    "card_activate": {
        "required_slots": ["card_id"],
        "optional_slots": [],
        "nodes": [{"id": "activate_card", "tool": "activate_card", "deps": []}],
    },
    "card_freeze": {
        "required_slots": ["card_id"],
        "optional_slots": [],
        "nodes": [{"id": "freeze_card", "tool": "freeze_card", "deps": []}],
    },
    "card_unfreeze": {
        "required_slots": ["card_id"],
        "optional_slots": [],
        "nodes": [{"id": "unfreeze_card", "tool": "unfreeze_card", "deps": []}],
    },
    "card_limit": {
        "required_slots": ["card_id"],
        "optional_slots": ["daily_limit", "monthly_limit"],
        "nodes": [{"id": "update_card_limit", "tool": "update_card_limit", "deps": []}],
    },
    "card_deactivate": {
        "required_slots": ["card_id"],
        "optional_slots": [],
        "nodes": [{"id": "deactivate_card", "tool": "deactivate_card", "deps": []}],
    },
}


def build(intent):
    return DAG_TEMPLATES.get(intent)


def topo_sort(nodes):
    """Kahn 拓扑排序，返回执行顺序；检测到环抛异常。"""
    by_id = {n["id"]: n for n in nodes}
    indeg = {n["id"]: 0 for n in nodes}
    for n in nodes:
        for d in n["deps"]:
            if d not in by_id:
                raise ValueError(f"DAG 引用了不存在的节点: {d}")
            indeg[n["id"]] += 1
    queue = sorted([i for i, d in indeg.items() if d == 0])
    order = []
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for n in nodes:
            if nid in n["deps"]:
                indeg[n["id"]] -= 1
                if indeg[n["id"]] == 0:
                    queue.append(n["id"])
        queue.sort()
    if len(order) != len(nodes):
        raise ValueError("DAG 存在环，规划失败")
    return order
