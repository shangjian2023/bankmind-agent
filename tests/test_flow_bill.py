from tests.conftest import chat


def test_bill_analysis_green(client):
    res = chat(client, "分析一下我最近的账单")
    assert res["status"] == "ok"
    assert "境外数码商城" in res["reply"], "应识别出 5800 元异常大额"
    assert "星辰科技会员" in res["reply"], "应识别出重复扣费"
    assert "餐饮" in res["reply"]
    assert "本月支出" in res["reply"]


def test_bill_data_provenance(client):
    res = chat(client, "分析一下我最近的账单")
    data = res["data"]["analyze_bills"]
    assert data["total_out"] > 0
    assert any(a["counterparty"] == "境外数码商城" for a in data["anomalies_big"])
    assert any(d["counterparty"] == "星辰科技会员" and d["count"] == 4 for d in data["anomalies_duplicate"])
