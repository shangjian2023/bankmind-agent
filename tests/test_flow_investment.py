from tests.conftest import chat, mfa_code_of


def test_risk_assessment_multiturn(client):
    r1 = chat(client, "帮我做个风险测评")
    assert r1["status"] == "need_slots" and "风险偏好" in r1["reply"]
    r2 = chat(client, "稳健")
    assert r2["status"] == "ok" and "R2" in r2["reply"]


def test_recommend_before_assessment_only_r1(client):
    res = chat(client, "推荐一些理财产品")
    assert res["status"] == "ok"
    assert "天天盈货币" in res["reply"] and "淘金混合" not in res["reply"]


def test_recommend_filtered_by_risk(client):
    chat(client, "帮我做个风险测评")
    chat(client, "稳健")
    res = chat(client, "推荐一些理财产品")
    assert res["status"] == "ok"
    assert "稳健90天" in res["reply"]
    assert "淘金混合" not in res["reply"], "R2 用户不应看到 R3 产品"


def test_purchase_red_mfa_and_holding(client):
    chat(client, "帮我做个风险测评")
    chat(client, "进取")
    res = chat(client, "申购稳健90天理财 2000元")
    assert res["status"] == "need_mfa"
    out = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": mfa_code_of(res)}).json()
    assert out["status"] == "ok" and "稳健90天" in out["reply"] and "13800.50" in out["reply"]
    hold = chat(client, "查我的持仓")
    assert "稳健90天" in hold["reply"]


def test_purchase_min_amount(client):
    chat(client, "帮我做个风险测评")
    chat(client, "进取")
    res = chat(client, "申购稳健90天理财 500元")
    out = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": mfa_code_of(res)}).json()
    assert out["status"] == "rejected" and "起购" in out["reply"]


def test_purchase_risk_exceeded(client):
    chat(client, "帮我做个风险测评")
    chat(client, "保守")
    res = chat(client, "申购淘金混合 1000元")
    out = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": mfa_code_of(res)}).json()
    assert out["status"] == "rejected" and "风险" in out["reply"]
    assert chat(client, "查一下我的余额")["reply"].count("15800.50") == 1


def test_redeem_red_mfa(client):
    chat(client, "帮我做个风险测评")
    chat(client, "稳健")
    buy = chat(client, "申购稳健90天理财 2000元")
    client.post("/api/mfa/verify", json={"action_id": buy["action_id"], "code": mfa_code_of(buy)})
    res = chat(client, "赎回稳健90天")
    assert res["status"] == "need_mfa"
    out = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": mfa_code_of(res)}).json()
    assert out["status"] == "ok" and "15800.50" in out["reply"]
    assert chat(client, "查我的持仓")["reply"].count("没有持仓") == 1
