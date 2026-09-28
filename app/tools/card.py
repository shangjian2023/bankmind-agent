"""卡片管理工具：查询、激活、冻结、限额、注销"""

from datetime import date, timedelta
from typing import Any

from app.data import repositories as repo
from app.security import audit
from app.tools.registry import tool


def _mask_card(card_no: str) -> str:
    """卡号脱敏：显示前4后4"""
    if len(card_no) <= 8:
        return card_no
    return f"{card_no[:4]} **** **** {card_no[-4:]}"


@tool("list_cards")
def list_cards(ctx):
    """查询用户名下所有卡片"""
    user_id = ctx["user_id"]
    cards = repo.list_cards(user_id)
    if not cards:
        return {"cards": [], "text": "您名下暂无卡片"}

    result = []
    for c in cards:
        status_cn = {
            "inactive": "未激活",
            "active": "正常",
            "frozen": "已冻结",
            "deactivated": "已注销",
        }.get(c["status"], c["status"])

        result.append({
            "card_id": c["id"],
            "card_no": _mask_card(c["card_no"]),
            "card_type": "借记卡" if c["card_type"] == "debit" else "信用卡",
            "card_brand": c["card_brand"],
            "status": status_cn,
            "daily_limit": c["daily_limit"],
            "monthly_limit": c["monthly_limit"],
            "expires_at": c["expires_at"],
        })

    lines = [f"您名下共有 {len(result)} 张卡片："]
    for r in result:
        lines.append(f"- {r['card_no']}（{r['card_type']}）状态：{r['status']}，日限额 {r['daily_limit']} 元")

    return {"cards": result, "text": "\n".join(lines)}


@tool("apply_card")
def apply_card(ctx):
    """申请新卡"""
    user_id = ctx["user_id"]
    card_type = ctx["slots"].get("card_type", "debit")

    # 生成卡号（19位）
    import random
    prefix = "6222" if card_type == "debit" else "6228"
    card_no = prefix + "".join([str(random.randint(0, 9)) for _ in range(15)])

    # 有效期 5 年
    expires = (date.today() + timedelta(days=5*365)).isoformat()

    card_id = repo.insert_card(
        user_id=user_id,
        card_no=card_no,
        card_type=card_type,
        card_brand="UnionPay",
        expires_at=expires,
    )

    type_cn = "借记卡" if card_type == "debit" else "信用卡"
    return {
        "card_id": card_id,
        "card_no": _mask_card(card_no),
        "card_type": type_cn,
        "status": "未激活",
        "text": f"{type_cn}申请成功，卡号 {_mask_card(card_no)}，请激活后使用",
    }


@tool("activate_card")
def activate_card(ctx):
    """激活卡片（黄色确认）"""
    user_id = ctx["user_id"]
    card_id = ctx["slots"].get("card_id")

    card = repo.get_card_by_id(card_id)
    if not card or card["user_id"] != user_id:
        raise Exception("卡片不存在")

    if card["status"] == "active":
        return {"text": "卡片已处于激活状态"}

    if card["status"] != "inactive":
        raise Exception(f"卡片状态为{card['status']}，无法激活")

    repo.activate_card(card_id)
    return {"text": f"卡片 {_mask_card(card['card_no'])} 已激活，可正常使用"}


@tool("freeze_card")
def freeze_card(ctx):
    """冻结卡片（红色MFA）"""
    user_id = ctx["user_id"]
    card_id = ctx["slots"].get("card_id")

    card = repo.get_card_by_id(card_id)
    if not card or card["user_id"] != user_id:
        raise Exception("卡片不存在")

    if card["status"] != "active":
        raise Exception("只能冻结状态为'正常'的卡片")

    repo.freeze_card(card_id)
    return {"text": f"卡片 {_mask_card(card['card_no'])} 已冻结，暂停所有交易"}


@tool("unfreeze_card")
def unfreeze_card(ctx):
    """解冻卡片（黄色确认）"""
    user_id = ctx["user_id"]
    card_id = ctx["slots"].get("card_id")

    card = repo.get_card_by_id(card_id)
    if not card or card["user_id"] != user_id:
        raise Exception("卡片不存在")

    if card["frozen"] == 0:
        return {"text": "卡片未处于冻结状态"}

    repo.unfreeze_card(card_id)
    return {"text": f"卡片 {_mask_card(card['card_no'])} 已解冻，恢复正常使用"}


@tool("update_card_limit")
def update_limit(ctx):
    """修改卡片限额（黄色确认）"""
    user_id = ctx["user_id"]
    card_id = ctx["slots"].get("card_id")
    daily_limit = ctx["slots"].get("daily_limit")
    monthly_limit = ctx["slots"].get("monthly_limit")

    card = repo.get_card_by_id(card_id)
    if not card or card["user_id"] != user_id:
        raise Exception("卡片不存在")

    if card["status"] != "active":
        raise Exception("只能修改激活状态卡片的限额")

    repo.update_card_limits(card_id, daily_limit, monthly_limit)

    msg_parts = []
    if daily_limit is not None:
        msg_parts.append(f"日限额调整为 {daily_limit} 元")
    if monthly_limit is not None:
        msg_parts.append(f"月限额调整为 {monthly_limit} 元")

    return {"text": f"卡片 {_mask_card(card['card_no'])} " + "，".join(msg_parts)}


@tool("deactivate_card")
def deactivate_card(ctx):
    """注销卡片（红色MFA）"""
    user_id = ctx["user_id"]
    card_id = ctx["slots"].get("card_id")

    card = repo.get_card_by_id(card_id)
    if not card or card["user_id"] != user_id:
        raise Exception("卡片不存在")

    if card["status"] == "deactivated":
        raise Exception("卡片已注销")

    repo.deactivate_card(card_id)
    return {"text": f"卡片 {_mask_card(card['card_no'])} 已注销，无法恢复"}
