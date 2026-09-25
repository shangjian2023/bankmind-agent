from app.agent.intent import classify


def test_basic_intents():
    cases = {
        "给李娜转500元": "transfer",
        "查一下我的余额": "balance_query",
        "分析一下我最近的账单": "bill_analysis",
        "查我的订阅": "subscription_query",
        "取消健身房的订阅": "subscription_cancel",
        "我的卡丢了，帮我挂失": "report_loss",
        "我爱人生日快到了，帮我安排鲜花蛋糕，预算500元": "birthday_plan",
        "你能做什么": "help",
    }
    for text, expect in cases.items():
        got, _ = classify(text)
        assert got == expect, f"{text} → {got}，期望 {expect}"


def test_unknown():
    assert classify("今天天气怎么样")[0] is None
