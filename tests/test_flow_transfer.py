from tests.conftest import chat, mfa_code_of


def test_balance_green(client):
    res = chat(client, "查一下我的余额")
    assert res["status"] == "ok"
    assert "15800.50" in res["reply"]


def test_transfer_yellow_confirm_and_execute(client):
    res = chat(client, "给李娜转500元 备注买菜")
    assert res["status"] == "need_confirm"
    assert res["data"]["slots"]["amount"] == 500
    out = client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()
    assert out["status"] == "ok"
    assert "李娜" in out["reply"] and "500.00" in out["reply"]
    assert chat(client, "查一下我的余额")["reply"].count("15300.50") == 1


def test_transfer_declined_keeps_balance(client):
    res = chat(client, "给李娜转100元")
    out = client.post("/api/confirm", json={"action_id": res["action_id"], "approve": False}).json()
    assert out["status"] == "ok"
    assert chat(client, "查一下我的余额")["reply"].count("15800.50") == 1


def test_transfer_red_mfa(client):
    res = chat(client, "给王强转3000元")
    assert res["status"] == "need_mfa"
    wrong = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": "000000"}).json()
    assert wrong["status"] == "need_mfa" and "剩余 2 次" in wrong["reply"]
    out = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": mfa_code_of(res)}).json()
    assert out["status"] == "ok"
    assert "3000.00" in out["reply"]
    assert chat(client, "查一下我的余额")["reply"].count("12800.50") == 1


def test_transfer_daily_cumulative_escalates_to_red(client):
    r1 = chat(client, "给陈晨转600元")
    assert r1["status"] == "need_confirm"
    assert client.post("/api/confirm", json={"action_id": r1["action_id"], "approve": True}).json()["status"] == "ok"
    r2 = chat(client, "给陈晨转600元")
    assert r2["status"] == "need_mfa", "日累计 1200 应升级为红色"


def test_transfer_insufficient_balance(client):
    res = chat(client, "给李娜转99999元")
    assert res["status"] == "rejected"
    assert "余额不足" in res["reply"]


def test_transfer_missing_amount_multiturn(client):
    r1 = chat(client, "给李娜转一笔钱")
    assert r1["status"] == "need_slots"
    r2 = chat(client, "500元")
    assert r2["status"] == "need_confirm"
    out = client.post("/api/confirm", json={"action_id": r2["action_id"], "approve": True}).json()
    assert out["status"] == "ok"


def test_transfer_unknown_payee(client):
    res = chat(client, "给陌生人转100元")
    assert res["status"] == "need_confirm"
    out = client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()
    assert out["status"] == "rejected"
    assert "联系人" in out["reply"]


def test_transfer_by_phone(client):
    res = chat(client, "给13900002222转200元")
    assert res["status"] == "need_confirm"
    out = client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()
    assert out["status"] == "ok" and "李娜" in out["reply"]
