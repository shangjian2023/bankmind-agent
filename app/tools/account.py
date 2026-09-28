from app import config
from app.data import repositories as repo
from app.tools.registry import tool, ToolError


@tool("resolve_payee")
def resolve_payee(ctx):
    slots = ctx["slots"]
    if slots.get("phone"):
        c = repo.find_contact_by_phone(ctx["user_id"], slots["phone"])
        if c:
            return {"name": c["name"], "account_no": c["account_no"], "matched_by": "手机号"}
    raw = slots.get("payee_raw") or ""
    if raw in config.SPOUSE_KEYWORDS:
        c = repo.find_spouse(ctx["user_id"])
        if c:
            return {"name": c["name"], "account_no": c["account_no"], "matched_by": "亲人称呼"}
    if raw:
        rows = repo.find_contacts_by_name(ctx["user_id"], raw)
        if len(rows) == 1:
            return {"name": rows[0]["name"], "account_no": rows[0]["account_no"], "matched_by": "联系人"}
        if len(rows) > 1:
            names = "、".join(r["name"] for r in rows)
            raise ToolError(f"找到多位匹配联系人（{names}），请使用完整姓名或手机号")
    raise ToolError("收款人不在常用联系人中，请提供完整姓名或手机号（仅支持模拟联系人）")


@tool("get_balance")
def get_balance(ctx):
    return {"accounts": repo.list_accounts(ctx["user_id"])}


@tool("check_balance")
def check_balance(ctx):
    amount = ctx["slots"].get("amount", 0)
    acct = repo.get_primary_account(ctx["user_id"])
    if not acct:
        raise ToolError("未找到您的账户")
    return {"balance": acct["balance"], "sufficient": acct["balance"] >= amount, "amount": amount}
