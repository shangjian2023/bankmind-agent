import re
from typing import Optional
from app.agent.llm import get_llm

# 顺序敏感：abort/takeover 最先；赎回/申购在理财查询前；定时在普通转账前；挂失在卡片查询前
RULES = [
    ("abort", r"(算了|不要了|先不转了|重新来|取消刚才|取消待办)", 0.9),
    ("human_takeover", r"(转人工|人工接管|人工客服|我要投诉)", 0.95),
    ("report_loss", r"(挂失|补卡|卡丢|银行卡丢|卡不见了|找不到卡|卡片丢失|卡被吞)", 0.95),
    ("card_deactivate", r"(注销|销户)[^，。]{0,6}(卡|银行卡)", 0.95),
    ("card_freeze", r"(冻结|锁卡)[^，。]{0,6}(卡|银行卡)", 0.95),
    ("card_unfreeze", r"(解冻|解锁)[^，。]{0,6}(卡|银行卡)", 0.95),
    ("card_limit", r"(限额|额度|日限|月限)", 0.9),
    ("card_activate", r"(激活|启用)[^，。]{0,6}(卡|银行卡)", 0.9),
    ("card_apply", r"(申请|办|开)[^，。]{0,6}(卡|银行卡|新卡)", 0.9),
    ("card_query", r"(我的卡|卡片|银行卡|查卡|有哪些卡)", 0.85),
    ("investment_redeem", r"赎回", 0.9),
    ("investment_purchase", r"(申购|买入|购买)|买[一-龥A-Za-z0-9]{0,10}(理财|产品|基金|存款)", 0.9),
    ("scheduled_query", r"查.{0,6}(定时|预约)|定时转账.{0,4}(记录|列表|有哪些|查)", 0.9),
    ("scheduled_transfer", r"(定时|预约|明天|后天|下周|每周|每天)[^，。]{0,15}(转|汇|付)", 0.9),
    ("aa_split", r"(AA|aa|均摊|平摊|拆分收款)", 0.9),
    ("risk_assessment", r"(风险测评|风险评估|测一?下?风险|风险承受)", 0.9),
    ("my_investments", r"(持仓|我的投资|我买[的了]|查看投资|投资记录|持有产品)", 0.9),
    ("investment_query", r"(理财|收益|有什么产品|产品推荐|推荐[一-龥]{0,4}(理财|产品|基金))", 0.85),
    ("bill_yearly", r"(年度|全年|今年)[^，。]{0,10}(账单|报告|消费|支出)", 0.9),
    ("subscription_cancel", r"(取消|退订|关闭|停用)[^，。]{0,8}(订阅|会员|代扣|自动续费)|取消健身房", 0.9),
    ("transfer", r"(转账|转给|转一笔|汇款|付给|转过去|转[^，。]{0,6}元)", 0.9),
    ("subscription_query", r"(订阅|代扣|自动扣费|续费|会员费)", 0.85),
    ("bill_analysis", r"(账单|消费分析|消费报告|月度报告|异常交易|花了多少钱|支出|省钱)", 0.85),
    ("balance_query", r"(余额|还有多少[钱块]|存款|账户[^，。]{0,4}(多少钱|余额)|活期)", 0.9),
    ("birthday_plan", r"(生日|纪念日).{0,20}(鲜花|蛋糕|安排|规划|准备)|(鲜花|蛋糕).{0,10}(订|买)", 0.85),
    ("help", r"(帮助|你能做什么|怎么用|你好|hello|hi)", 0.6),
]

COMPILED = [(name, re.compile(pat, re.IGNORECASE), conf) for name, pat, conf in RULES]

# 意图分类提示词
INTENT_CLASSIFICATION_PROMPT = """你是一个银行智能助手的意图分类器。根据用户输入，判断用户的意图属于以下哪个类别：

可用意图：
- transfer: 转账、汇款给某人
- balance_query: 查询账户余额
- bill_analysis: 分析账单、消费统计
- subscription_query: 查询订阅服务
- subscription_cancel: 取消订阅
- report_loss: 挂失银行卡
- card_query: 查询卡片信息
- card_apply: 申请新卡
- card_activate: 激活卡片
- card_freeze: 冻结卡片
- card_unfreeze: 解冻卡片
- card_limit: 修改卡片限额
- card_deactivate: 注销卡片
- investment_query: 查询理财产品
- investment_purchase: 购买理财产品
- investment_redeem: 赎回理财
- my_investments: 查看我的投资持仓
- risk_assessment: 风险测评
- scheduled_transfer: 设置定时转账
- scheduled_query: 查询定时转账
- aa_split: AA制收款
- birthday_plan: 生日关怀规划
- abort: 取消当前操作
- human_takeover: 转人工客服
- help: 询问帮助

请只返回意图名称（如 "transfer"），不要返回其他内容。如果无法识别，返回 "unknown"。"""


def classify(text: str) -> tuple[Optional[str], float]:
    """
    对用户输入进行意图分类。

    策略：
    1. 先用正则快速匹配（低延迟）
    2. 正则失败时，如果配置了 LLM，调用 LLM 进行语义理解

    Args:
        text: 用户输入的文本

    Returns:
        (intent_name, confidence): 意图名称和置信度，未匹配时返回 (None, 0.0)
    """
    # 第一步：正则匹配
    for name, rx, conf in COMPILED:
        if rx.search(text):
            return name, conf

    # 第二步：LLM fallback（如果配置了 LLM）
    try:
        llm = get_llm()
        if llm.name != "mock":  # 只有配置了真实 LLM 才使用
            messages = [
                {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
                {"role": "user", "content": text}
            ]
            response = llm.chat(messages)
            intent = response.get("content", "").strip().lower()

            # 验证返回的意图是否有效
            valid_intents = {name for name, _, _ in RULES}
            if intent in valid_intents:
                return intent, 0.85  # LLM 识别的置信度
    except Exception as e:
        # LLM 调用失败时静默处理，返回 None
        print(f"LLM intent classification failed: {e}")

    return None, 0.0
