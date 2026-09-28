from datetime import date, timedelta

from app import config
from app.data import repositories as repo
from app.tools.registry import tool, ToolError


@tool("list_subscriptions")
def list_subscriptions(ctx):
    rows = repo.active_subscriptions(ctx["user_id"])
    today = date.today()
    soon = today + timedelta(days=config.BILL_SUBSCRIPTION_SOON_DAYS)
    out = []
    for r in rows:
        nc = date.fromisoformat(r["next_charge"])
        out.append(
            {
                **r,
                "days_until_charge": (nc - today).days,
                "renewing_soon": nc <= soon,
            }
        )
    monthly = sum(x["amount"] for x in out if x["cycle"] == "monthly")
    return {"subscriptions": out, "monthly_total": round(monthly, 2)}


@tool("find_subscription")
def find_subscription(ctx):
    merchant = ctx["slots"].get("merchant", "")
    rows = repo.find_active_subscriptions_by_merchant(ctx["user_id"], merchant)
    if not rows:
        raise ToolError(f"未找到包含「{merchant}」的生效订阅，可先发送「查订阅」查看列表")
    if len(rows) > 1:
        names = "、".join(r["merchant"] for r in rows)
        raise ToolError(f"匹配到多个订阅（{names}），请提供更精确的名称")
    return rows[0]


@tool("cancel_subscription")
def cancel_subscription(ctx):
    sub = ctx["results"].get("find_subscription")
    if not sub:
        raise ToolError("未定位到要取消的订阅")
    repo.cancel_subscription(sub["id"])
    return {
        "cancelled": sub["merchant"],
        "monthly_saved": sub["amount"] if sub["cycle"] == "monthly" else 0,
    }
