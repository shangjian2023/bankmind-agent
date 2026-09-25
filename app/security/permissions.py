"""权限分级引擎：绿=自动执行，黄=用户确认，红=MFA 强验证。金额阈值见 config。"""

from app import config
from app.data import repositories as repo

GREEN, YELLOW, RED = "green", "yellow", "red"

LEVEL_DESC = {
    GREEN: "绿色（自动执行）",
    YELLOW: "黄色（需用户确认）",
    RED: "红色（需多因子强验证）",
}

STATIC_LEVELS = {
    "balance_query": GREEN,
    "bill_analysis": GREEN,
    "help": GREEN,
    "subscription_query": YELLOW,
    "subscription_cancel": YELLOW,
    "report_loss": RED,
    "birthday_plan": YELLOW,
}


def classify(intent, slots, user_id):
    """返回 (级别, 判定说明)。转账按日累计金额动态分档。"""
    if intent == "transfer":
        amount = slots.get("amount", 0)
        used = repo.sum_transferred_today(user_id)
        if used + amount > config.YELLOW_DAILY_TRANSFER_LIMIT:
            return RED, f"日累计转出 {used:.2f} + 本笔 {amount:.2f} 超过 {config.YELLOW_DAILY_TRANSFER_LIMIT:.0f} 元限额"
        return YELLOW, f"日累计转出 {used:.2f} + 本笔 {amount:.2f} ≤ {config.YELLOW_DAILY_TRANSFER_LIMIT:.0f} 元"
    level = STATIC_LEVELS.get(intent, YELLOW)
    return level, "固定映射"
