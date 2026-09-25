from app.data import repositories as repo
from app.tools.registry import tool


@tool("create_scheduled")
def create_scheduled(ctx):
    payee = ctx["results"]["resolve_payee"]
    s = ctx["slots"]["schedule"]
    amount = ctx["slots"]["amount"]
    task_id = repo.insert_scheduled(
        ctx["user_id"],
        payee["name"],
        payee["account_no"],
        amount,
        s["execute_at"],
        s["cycle"],
        ctx["slots"].get("memo"),
    )
    cycle_desc = {"once": "单次", "daily": "每日循环", "weekly": "每周循环"}[s["cycle"]]
    return {
        "task_id": task_id,
        "payee": payee["name"],
        "amount": amount,
        "execute_at": s["execute_at"],
        "cycle": s["cycle"],
        "text": f"定时转账已创建（任务 #{task_id}，{cycle_desc}）：向 {payee['name']} 转出 {amount:.2f} 元，"
        f"将于 {s['desc']} 首次执行。到期自动扣款；若届时日累计超过限额，任务会被安全拦截并提示手动处理。",
    }


@tool("list_scheduled")
def list_scheduled(ctx):
    rows = repo.list_scheduled(ctx["user_id"])
    if not rows:
        return {"tasks": [], "text": "当前没有定时转账任务。可以说「明天上午9点给李娜转200元」创建。"}
    status_desc = {
        "scheduled": "待执行",
        "executed": "已执行",
        "cancelled": "已取消",
        "blocked": "已拦截（超日限额）",
        "failed_insufficient": "失败（余额不足）",
    }
    lines = [f"共 {len(rows)} 条定时转账任务："]
    for t in rows:
        lines.append(
            f"- #{t['id']} 向 {t['payee_name']} 转 {t['amount']:.2f} 元，{t['execute_at']} 执行，"
            f"状态：{status_desc.get(t['status'], t['status'])}"
        )
    return {"tasks": rows, "text": "\n".join(lines)}
