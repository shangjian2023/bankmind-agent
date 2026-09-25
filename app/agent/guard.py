"""Prompt 注入防御：用户输入只作为数据处理，命中可疑模式直接拒绝并审计。"""

import re

PATTERNS = [
    (r"ignore\s+(all\s+)?previous", "英文指令覆盖"),
    (r"disregard.{0,20}instruction", "英文指令覆盖"),
    (r"忽略(之前|以上|前面|先前)", "指令覆盖"),
    (r"(系统|角色)提示词", "探测系统提示"),
    (r"system\s*prompt", "探测系统提示"),
    (r"你(现在)?(是|扮演).{0,6}(无限制|越狱|DAN|管理员|开发者模式|root)", "角色越权"),
    (r"developer\s*mode|jailbreak", "越狱尝试"),
    (r"(绕过|无视|关闭).{0,8}(权限|验证|风控|限制|规则)", "绕过安全机制"),
    (r"(输出|泄露|导出|告诉我).{0,10}(密钥|api[_ ]?key|secret|密码)", "密钥窃取"),
    (r"<\|.{0,30}\|>", "特殊令牌注入"),
]

COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in PATTERNS]


def check_injection(text):
    """返回 (是否安全, 命中原因)。"""
    for rx, label in COMPILED:
        if rx.search(text):
            return False, label
    return True, None
