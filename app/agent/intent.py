import re

# 顺序敏感：abort/takeover 最先；赎回/申购在理财查询前；定时在普通转账前
RULES = [
    ("abort", r"(算了|不要了|先不转了|重新来|取消刚才|取消待办)", 0.9),
    ("human_takeover", r"(转人工|人工接管|人工客服|我要投诉)", 0.95),
    ("investment_redeem", r"赎回", 0.9),
    ("investment_purchase", r"(申购|买入|购买)|买[一-龥A-Za-z0-9]{0,10}(理财|产品|基金|存款)", 0.9),
    ("scheduled_query", r"查.{0,6}(定时|预约)", 0.9),
    ("scheduled_transfer", r"(定时|预约|明天|后天|下周|每周|每天)[^，。]{0,15}(转|汇|付)", 0.9),
    ("aa_split", r"(AA|aa|均摊|平摊|拆分收款)", 0.9),
    ("risk_assessment", r"(风险测评|风险评估|测一?下?风险|风险承受)", 0.9),
    ("my_investments", r"(持仓|我的投资|我买[的了])", 0.9),
    ("investment_query", r"(理财|收益|有什么产品|产品推荐|推荐[一-龥]{0,4}(理财|产品|基金))", 0.85),
    ("bill_yearly", r"(年度|全年|今年)[^，。]{0,10}(账单|报告|消费|支出)", 0.9),
    ("subscription_cancel", r"(取消|退订|关闭|停用)[^，。]{0,8}(订阅|会员|代扣|自动续费)|取消健身房", 0.9),
    ("transfer", r"(转账|转给|转一笔|汇款|付给|转过去|转[^，。]{0,6}元)", 0.9),
    ("subscription_query", r"(订阅|代扣|自动扣费|续费|会员费)", 0.85),
    ("bill_analysis", r"(账单|消费分析|消费报告|月度报告|异常交易|花了多少钱|支出|省钱)", 0.85),
    ("balance_query", r"(余额|还有多少[钱块]|存款|账户[^，。]{0,4}(多少钱|余额)|活期)", 0.9),
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
