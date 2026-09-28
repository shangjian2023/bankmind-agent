import re
from datetime import datetime, timedelta
from typing import Optional

from app import config

AMOUNT_RX = re.compile(r"(\d+(?:\.\d{1,2})?)\s*(元|块钱|块|人民币|¥)", re.IGNORECASE)
BARE_NUM_RX = re.compile(r"(?:转|付|汇)\s*(\d+(?:\.\d{1,2})?)")
PHONE_RX = re.compile(r"1[3-9]\d{9}")
MEMO_RX = re.compile(rf"备注[:：]?\s*([^\s，。,]{{1,{config.MAX_MEMO_LENGTH}}})")
PAYEE_RX = re.compile(rf"(?:转给|付给|汇给|给)\s*([^\s，。,转账付汇块钱元]{{1,{config.MAX_PAYEE_LENGTH}}}?)(?=\s|\d|，|,|。|$|转|付|汇)")
PRODUCT_RX = re.compile(rf"(?:申购|购买|买入|赎回)\s*([一-龥A-Za-z0-9]{{2,{config.MAX_PRODUCT_LENGTH}}})")
RISK_RX = re.compile(r"(保守|稳健|进取)")
PEOPLE_RX = re.compile(r"(\d+)\s*(?:个)?人")
SCHED_RX = re.compile(r"(今天|明天|后天|每天|每周[一二三四五六日天]?|\d{1,2}月\d{1,2}日?)")
HOUR_RX = re.compile(r"(上午|下午|晚上)?\s*(\d{1,2})[点时:：]")
CARD_ID_RX = re.compile(r"(?:卡片|卡)\s*(\d+)")
DAILY_LIMIT_RX = re.compile(r"日限额\s*(?:为|到|至)?\s*(\d+(?:\.\d{1,2})?)")
MONTHLY_LIMIT_RX = re.compile(r"月限额\s*(?:为|到|至)?\s*(\d+(?:\.\d{1,2})?)")

WEEK = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def _schedule(text: str) -> Optional[dict]:
    """
    解析时间表达式，提取调度信息。

    Args:
        text: 用户输入文本

    Returns:
        包含 execute_at、cycle、desc 的字典，或 None
    """
    m = SCHED_RX.search(text)
    if not m:
        return None
    hour = 9
    hm = HOUR_RX.search(text)
    if hm:
        h = int(hm.group(2))
        if hm.group(1) == "下午" and h < 12:
            h += 12
        if hm.group(1) == "晚上" and h < 12:
            h += 12
        hour = max(0, min(h, 23))
    now = datetime.now()
    tok = m.group(0)
    cycle = "once"
    if tok == "今天":
        dt = now
    elif tok == "明天":
        dt = now + timedelta(days=1)
    elif tok == "后天":
        dt = now + timedelta(days=2)
    elif tok == "每天":
        dt, cycle = now, "daily"
    elif tok.startswith("每周"):
        wd = WEEK.get(m.group(1)[-1])
        if wd is None:
            dt, cycle = now, "weekly"
        else:
            delta = (wd - now.weekday()) % 7 or 7
            dt, cycle = now + timedelta(days=delta), "weekly"
    else:
        mm, dd = re.findall(r"\d+", tok)
        try:
            dt = now.replace(month=int(mm), day=int(dd))
        except ValueError:
            return None
    dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    if dt <= now and cycle == "once":
        dt += timedelta(days=1)
    return {"execute_at": dt.isoformat(timespec="seconds"), "cycle": cycle, "desc": f"{tok} {hour:02d}:00"}


def extract(text: str) -> dict:
    """
    从用户输入中提取槽位信息。

    Args:
        text: 用户输入文本

    Returns:
        包含提取到的槽位的字典，如 amount、phone、payee_raw 等
    """
    slots = {}
    m = AMOUNT_RX.search(text) or BARE_NUM_RX.search(text)
    if m:
        val = float(m.group(1))
        if val < config.MAX_TRANSFER_AMOUNT:
            slots["amount"] = val
    m = PHONE_RX.search(text)
    if m:
        slots["phone"] = m.group(0)
    m = PAYEE_RX.search(text)
    if m:
        slots["payee_raw"] = m.group(1)
    m = MEMO_RX.search(text)
    if m:
        slots["memo"] = m.group(1)
    m = re.search(r"预算\s*(\d+(?:\.\d{1,2})?)", text)
    if m:
        slots["budget"] = float(m.group(1))
        slots.setdefault("amount", slots["budget"])
    m = re.search(rf"(?:取消|退订|关闭)\s*([一-龥A-Za-z0-9]{{2,{config.MAX_MERCHANT_LENGTH}}}?)的?(?:订阅|会员|代扣|自动续费)", text)
    if m:
        slots["merchant"] = m.group(1)
    if not m:
        m = re.search(rf"(?:取消|退订|关闭)([一-龥A-Za-z0-9]{{2,{config.MAX_MERCHANT_LENGTH}}}?)", text)
        if m:
            slots["merchant"] = m.group(1)
    m = PRODUCT_RX.search(text)
    if m:
        name = re.sub(r"(理财|产品|基金|存款|一份|一份儿)$", "", m.group(1)) or m.group(1)
        slots["product"] = name
    m = RISK_RX.search(text)
    if m:
        slots["risk_answer"] = m.group(1)
    m = PEOPLE_RX.search(text)
    if m:
        slots["people"] = int(m.group(1))
    sched = _schedule(text)
    if sched:
        slots["schedule"] = sched
    # 卡片相关槽位
    m = CARD_ID_RX.search(text)
    if m:
        slots["card_id"] = int(m.group(1))
    m = DAILY_LIMIT_RX.search(text)
    if m:
        slots["daily_limit"] = float(m.group(1))
    m = MONTHLY_LIMIT_RX.search(text)
    if m:
        slots["monthly_limit"] = float(m.group(1))
    return slots
