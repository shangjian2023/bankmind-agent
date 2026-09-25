from app.data import repositories as repo
from app.tools.registry import tool, ToolError


@tool("execute_transfer")
def execute_transfer(ctx):
    slots = ctx["slots"]
    payee = ctx["results"].get("resolve_payee")
    chk = ctx["results"].get("check_balance")
    if not payee or not chk:
        raise ToolError("转账前置校验未完成")
    if not chk["sufficient"]:
        raise ToolError(f"余额不足：当前 {chk['balance']:.2f} 元，本次需 {chk['amount']:.2f} 元")
    amount = slots["amount"]
    memo = slots.get("memo") or f"转账给{payee['name']}"
    acct = repo.get_primary_account(ctx["user_id"])
    txn_id = repo.insert_transaction(
        account_id=acct["id"],
        user_id=ctx["user_id"],
        counterparty=f"转账-{payee['name']}",
        amount=-amount,
        category="transfer_out",
        memo=memo,
    )
    repo.debit_account(acct["id"], amount)
    return {
        "txn_id": txn_id,
        "payee": payee["name"],
        "account_no": payee["account_no"],
        "amount": amount,
        "memo": memo,
        "balance_after": round(acct["balance"] - amount, 2),
    }
