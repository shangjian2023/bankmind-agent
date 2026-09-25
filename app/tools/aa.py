import uuid

from app.data import repositories as repo
from app.tools.registry import tool, ToolError


@tool("split_aa")
def split_aa(ctx):
    total = ctx["slots"]["amount"]
    people = ctx["slots"]["people"]
    if people < 2:
        raise ToolError("AA 至少需要 2 人")
    per = round(total / people, 2)
    code = "AA" + uuid.uuid4().hex[:6].upper()
    repo.insert_aa(ctx["user_id"], total, people, per, code)
    return {
        "code": code,
        "total": total,
        "people": people,
        "per_person": per,
        "text": f"AA 收款已创建：总额 {total:.2f} 元 ÷ {people} 人，每人应付 {per:.2f} 元。"
        f"收款口令 {code}（模拟），已向参与人发送收款通知（模拟）。",
    }
