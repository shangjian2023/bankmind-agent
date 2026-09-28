"""PII 脱敏工具：审计日志中敏感信息的脱敏处理。"""

import re


def mask_phone(phone: str) -> str:
    """手机号脱敏：保留前3后4，中间用****替换。"""
    if not phone or len(phone) != 11:
        return phone
    return f"{phone[:3]}****{phone[7:]}"


def mask_account(account_no: str) -> str:
    """账号脱敏：保留前4后4，中间用****替换。"""
    if not account_no or len(account_no) <= 8:
        return account_no
    return f"{account_no[:4]}****{account_no[-4:]}"


def mask_id_card(id_card: str) -> str:
    """身份证号脱敏：保留前6后4，中间用****替换。"""
    if not id_card or len(id_card) != 18:
        return id_card
    return f"{id_card[:6]}********{id_card[-4:]}"


def mask_detail(detail: dict | None) -> dict | None:
    """递归脱敏 detail 字典中的敏感字段。"""
    if not detail:
        return detail

    masked = {}
    for key, value in detail.items():
        if isinstance(value, dict):
            masked[key] = mask_detail(value)
        elif isinstance(value, str):
            # 手机号
            if re.match(r'^1[3-9]\d{9}$', value):
                masked[key] = mask_phone(value)
            # 身份证号
            elif re.match(r'^\d{17}[\dXx]$', value):
                masked[key] = mask_id_card(value)
            # 银行卡号（16-19位数字）
            elif re.match(r'^\d{16,19}$', value):
                masked[key] = mask_account(value)
            else:
                masked[key] = value
        else:
            masked[key] = value

    return masked
