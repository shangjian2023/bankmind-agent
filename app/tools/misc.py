import uuid
from datetime import date

from app.data import repositories as repo
from app.tools.registry import tool, ToolError


@tool("do_report_loss")
def do_report_loss(ctx):
    ticket = "LS" + uuid.uuid4().hex[:8].upper()
    return {"ticket": ticket, "card_status": "已挂失（模拟）", "note": "模拟环境：不涉及真实卡片"}


@tool("plan_birthday")
def plan_birthday(ctx):
    budget = ctx["slots"].get("budget") or ctx["slots"].get("amount")
    if not budget:
        raise ToolError("请告诉我预算金额，例如「预算500元」")
    bal = ctx["results"].get("get_balance")
    if not bal or not bal.get("accounts"):
        raise ToolError("未找到您的账户")
    balance = bal["accounts"][0]["balance"]
    if balance < budget:
        raise ToolError(f"活期余额 {balance:.2f} 元不足以锁定 {budget:.2f} 元预算")
    u = repo.get_user(ctx["user_id"]) or {}
    spouse = u.get("spouse_name") or "家人"
    bday = u.get("spouse_birthday")
    days_left = (date.fromisoformat(bday) - date.today()).days if bday else None
    order_id = "BD" + uuid.uuid4().hex[:8].upper()
    flowers = round(budget * 0.6, 2)
    cake = round(budget * 0.4, 2)
    text = (
        f"已为{spouse}的生日（{bday}，还有 {days_left} 天）制定方案："
        f"鲜花预算 {flowers:.2f} 元 + 蛋糕预算 {cake:.2f} 元，合计 {budget:.2f} 元，"
        f"已从活期锁定该预算（模拟），预订单号 {order_id}，生日前 1 天自动确认配送（模拟）。"
    )
    return {
        "order_id": order_id,
        "spouse": spouse,
        "birthday": bday,
        "days_left": days_left,
        "budget": budget,
        "flowers": flowers,
        "cake": cake,
        "balance": balance,
        "plan_text": text,
    }
