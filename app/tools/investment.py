from app.data import repositories as repo
from app.tools.registry import tool, ToolError

RISK_MAP = {"保守": "R1", "稳健": "R2", "进取": "R3"}
RANK = {"R1": 1, "R2": 2, "R3": 3}


@tool("recommend_products")
def recommend_products(ctx):
    user = repo.get_user(ctx["user_id"]) or {}
    user_risk = user.get("risk_level")
    products = repo.list_products()
    lines = []
    if user_risk:
        fit = [p for p in products if RANK[p["risk_level"]] <= RANK[user_risk]]
        lines.append(f"根据您的风险测评（{user_risk}），为您推荐以下 {len(fit)} 款产品：")
    else:
        fit = [p for p in products if p["risk_level"] == "R1"]
        lines.append("您还未做风险测评，先展示低风险（R1）产品；发送「风险测评」可解锁更多产品。")
    for p in fit:
        lines.append(
            f"- {p['name']}（{p['type']}）：参考年化 {p['annual_rate']:.2f}%，风险 {p['risk_level']}，"
            f"{p['min_amount']:.0f} 元起购，期限 {p['term_days']} 天。{p['description']}"
        )
    return {"user_risk": user_risk, "products": fit, "text": "\n".join(lines)}


@tool("my_investments")
def my_investments(ctx):
    rows = repo.list_investments(ctx["user_id"])
    if not rows:
        return {"holdings": [], "text": "您当前没有持仓。发送「推荐理财」看看适合您的产品。"}
    total = sum(r["amount"] for r in rows)
    lines = [f"当前持仓 {len(rows)} 笔，本金合计 {total:.2f} 元："]
    for r in rows:
        lines.append(f"- {r['product_name']}：本金 {r['amount']:.2f} 元，参考年化 {r['annual_rate']:.2f}%（{r['purchased_at'][:10]} 买入）")
    return {"holdings": rows, "total": round(total, 2), "text": "\n".join(lines)}


@tool("save_risk")
def save_risk(ctx):
    answer = ctx["slots"]["risk_answer"]
    level = RISK_MAP[answer]
    repo.set_user_risk(ctx["user_id"], level)
    return {
        "risk_level": level,
        "text": f"风险测评完成：您当前的风险偏好为「{answer}」（{level}），将只为您推荐不高于该等级的产品。",
    }


@tool("find_product")
def find_product(ctx):
    keyword = ctx["slots"].get("product", "")
    rows = repo.find_products_by_name(keyword)
    if not rows:
        raise ToolError(f"未找到匹配「{keyword}」的产品，可发送「推荐理财」查看产品列表")
    if len(rows) > 1:
        names = "、".join(r["name"] for r in rows)
        raise ToolError(f"匹配到多款产品（{names}），请提供更精确的名称")
    return rows[0]


@tool("execute_purchase")
def execute_purchase(ctx):
    product = ctx["results"]["find_product"]
    chk = ctx["results"]["check_balance"]
    amount = ctx["slots"]["amount"]
    user = repo.get_user(ctx["user_id"]) or {}
    user_risk = user.get("risk_level")
    if not user_risk:
        raise ToolError("购买理财产品前需完成风险测评，请发送「风险测评」")
    if RANK[product["risk_level"]] > RANK[user_risk]:
        raise ToolError(f"产品风险等级 {product['risk_level']} 超出您的风险承受等级 {user_risk}，无法购买")
    if amount < product["min_amount"]:
        raise ToolError(f"起购金额 {product['min_amount']:.0f} 元，本次 {amount:.2f} 元不足")
    if not chk["sufficient"]:
        raise ToolError(f"余额不足：当前 {chk['balance']:.2f} 元，本次需 {amount:.2f} 元")
    inv_id = repo.insert_investment(ctx["user_id"], product["code"], product["name"], amount, product["annual_rate"])
    acct = repo.get_primary_account(ctx["user_id"])
    repo.debit_account(acct["id"], amount)
    return {
        "inv_id": inv_id,
        "product": product["name"],
        "amount": amount,
        "annual_rate": product["annual_rate"],
        "balance_after": round(acct["balance"] - amount, 2),
    }


@tool("find_holding")
def find_holding(ctx):
    keyword = ctx["slots"].get("product", "")
    rows = repo.find_holdings_by_name(ctx["user_id"], keyword)
    if not rows:
        raise ToolError(f"未找到「{keyword}」的持仓，可发送「查我的持仓」查看")
    if len(rows) > 1:
        names = "、".join(f"{r['product_name']}(#{r['id']})" for r in rows)
        raise ToolError(f"匹配到多笔持仓（{names}），请提供更精确的名称或份额")
    return rows[0]


@tool("execute_redeem")
def execute_redeem(ctx):
    holding = ctx["results"]["find_holding"]
    repo.redeem_investment(holding["id"])
    acct = repo.get_primary_account(ctx["user_id"])
    repo.debit_account(acct["id"], -holding["amount"])
    return {
        "inv_id": holding["id"],
        "product": holding["product_name"],
        "amount": holding["amount"],
        "balance_after": round(acct["balance"] + holding["amount"], 2),
    }
