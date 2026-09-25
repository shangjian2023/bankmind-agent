from tests.conftest import chat, mfa_code_of


def test_report_loss_red_mfa(client):
    res = chat(client, "我的卡丢了，帮我挂失")
    assert res["status"] == "need_mfa"
    out = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": mfa_code_of(res)}).json()
    assert out["status"] == "ok"
    assert "挂失成功" in out["reply"] and "LS" in out["reply"]


def test_birthday_plan_cross_scene(client):
    res = chat(client, "我爱人生日快到了，帮我安排鲜花蛋糕，预算500元")
    assert res["status"] == "need_confirm"
    out = client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()
    assert out["status"] == "ok"
    assert "李娜" in out["reply"] and "300.00" in out["reply"] and "200.00" in out["reply"]
    assert "BD" in out["reply"]


def test_mfa_exhausted(client):
    res = chat(client, "给王强转5000元")
    assert res["status"] == "need_mfa"
    last = None
    for _ in range(3):
        last = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": "000000"}).json()
    assert last["status"] == "rejected" and "上限" in last["reply"]
    again = client.post("/api/mfa/verify", json={"action_id": res["action_id"], "code": mfa_code_of(res)}).json()
    assert again["status"] == "rejected", "已取消的操作不能再用正确验证码执行"


def test_confirm_rejected_for_red(client):
    res = chat(client, "给王强转5000元")
    out = client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()
    assert out["status"] == "rejected" and "MFA" in out["reply"]
