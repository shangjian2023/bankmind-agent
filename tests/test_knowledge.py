"""知识图谱（NetworkX 版）测试：构建、查询、异常检测、推荐、导出。"""

from app.knowledge import FinancialKnowledgeGraph


def test_build_from_database_and_profile():
    kg = FinancialKnowledgeGraph()
    kg.build_from_database()
    profile = kg.get_user_profile("u001")
    assert profile["account_count"] >= 1
    assert profile["transaction_count"] > 0
    assert profile["top_merchants"], "种子数据应包含消费记录"
    merchants = kg.get_user_merchants("u001")
    assert merchants and all(isinstance(m, str) for m in merchants)


def test_detect_anomalies_first_time_and_spike():
    kg = FinancialKnowledgeGraph()
    kg.add_user("u1", {"name": "测试用户"})

    # 首次与陌生商户交易 → medium
    r = kg.detect_anomalies("u1", "新商户", 100)
    assert r["is_anomaly"] and r["risk_level"] == "medium" and "首次" in r["reason"]

    # 历史均值 100 元，超过 3 倍 → high；3 倍以内 → 正常
    for i in range(3):
        kg.add_transaction(f"t{i}", {"amount": 100, "merchant": "老商户"}, "u1", "老商户")
    spike = kg.detect_anomalies("u1", "老商户", 400)
    assert spike["is_anomaly"] and spike["risk_level"] == "high"
    normal = kg.detect_anomalies("u1", "老商户", 200)
    assert not normal["is_anomaly"]


def test_recommend_products_excludes_held_and_sorts():
    kg = FinancialKnowledgeGraph()
    kg.add_user("u1", {})
    kg.add_product("P1", {"code": "P1", "name": "稳健低", "risk_level": "稳健", "annual_rate": 2.0})
    kg.add_product("P2", {"code": "P2", "name": "稳健高", "risk_level": "稳健", "annual_rate": 4.0})
    kg.add_product("P3", {"code": "P3", "name": "已持有", "risk_level": "稳健", "annual_rate": 5.0})
    kg.add_product("P4", {"code": "P4", "name": "其他等级", "risk_level": "进取", "annual_rate": 6.0})
    kg.add_investment("u1", "P3")

    recs = kg.recommend_products("u1", "稳健")
    assert [r["code"] for r in recs] == ["P2", "P1"], "按年化降序且排除已持有"


def test_merchant_users_and_export():
    kg = FinancialKnowledgeGraph()
    kg.add_user("u1", {})
    kg.add_user("u2", {})
    kg.add_transaction("t1", {"amount": 10, "merchant": "美团"}, "u1", "美团")
    kg.add_transaction("t2", {"amount": 20, "merchant": "美团"}, "u2", "美团")
    kg.add_investment("u1", "P1")

    assert kg.get_merchant_users("美团") == {"u1", "u2"}
    exported = kg.to_dict()
    assert any(n["id"] == "merchant:美团" for n in exported["nodes"])
    assert any(e["rel"] == "transacts_with" and e["target"] == "merchant:美团" for e in exported["edges"])
    assert any(e["rel"] == "holds" for e in exported["edges"])
