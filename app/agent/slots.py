import re

AMOUNT_RX = re.compile(r"(\d+(?:\.\d{1,2})?)\s*(元|块钱|块|人民币|¥)", re.IGNORECASE)
BARE_NUM_RX = re.compile(r"(?:转|付|汇)\s*(\d+(?:\.\d{1,2})?)")
PHONE_RX = re.compile(r"1[3-9]\d{9}")
MEMO_RX = re.compile(r"备注[:：]?\s*([^\s，。,]{1,30})")
PAYEE_RX = re.compile(r"(?:转给|付给|汇给|给)\s*([^\s，。,转账付汇块钱元]{1,8}?)(?=\s|\d|，|,|。|$|转|付|汇)")


def extract(text):
    slots = {}
    m = AMOUNT_RX.search(text) or BARE_NUM_RX.search(text)
    if m:
        val = float(m.group(1))
        if val < 10_000_000:
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
    m = re.search(r"(?:取消|退订|关闭)\s*([一-龥A-Za-z0-9]{2,12}?)的?(?:订阅|会员|代扣|自动续费)", text)
    if m:
        slots["merchant"] = m.group(1)
    if not m:
        m = re.search(r"(?:取消|退订|关闭)([一-龥A-Za-z0-9]{2,12})", text)
        if m:
            slots["merchant"] = m.group(1)
    return slots
