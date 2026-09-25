import re

# 顺序敏感：cancel 在 query 前，transfer 在 balance 前
RULES = [
    ("subscription_cancel", r"(取消|退订|关闭|停用).{0,8}(订阅|会员|代扣|自动续费)|取消健身房", 0.9),
    ("transfer", r"(转账|转给|转一笔|汇款|付给|转过去|转.{0,6}元)", 0.9),
    ("subscription_query", r"(订阅|代扣|自动扣费|续费|会员费)", 0.85),
    ("bill_analysis", r"(账单|消费分析|消费报告|月度报告|异常交易|花了多少钱|支出|省钱)", 0.85),
    ("balance_query", r"(余额|还有多少[钱块]|存款|账户.{0,4}(多少钱|余额)|活期)", 0.9),
    ("report_loss", r"(挂失|补卡|卡丢|银行卡丢)", 0.95),
    ("birthday_plan", r"(生日|纪念日).{0,20}(鲜花|蛋糕|安排|规划|准备)|(鲜花|蛋糕).{0,10}(订|买)", 0.85),
    ("help", r"(帮助|你能做什么|怎么用|你好|hello|hi)", 0.6),
]

COMPILED = [(name, re.compile(pat, re.IGNORECASE), conf) for name, pat, conf in RULES]


def classify(text):
    for name, rx, conf in COMPILED:
        if rx.search(text):
            return name, conf
    return None, 0.0
