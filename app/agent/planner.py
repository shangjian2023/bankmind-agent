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
        "required_slots": ["budget"],
        "optional_slots": [],
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
