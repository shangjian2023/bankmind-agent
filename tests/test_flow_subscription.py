from tests.conftest import chat


def _confirm(client, res):
    return client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()


def test_subscription_list(client):
    res = chat(client, "查我的订阅")
    assert res["status"] == "need_confirm"
    out = _confirm(client, res)
    assert out["status"] == "ok"
    assert "腾讯视频VIP" in out["reply"] and "超级健身房" in out["reply"]
    assert "月度合计" in out["reply"]


def test_subscription_cancel(client):
    res = chat(client, "取消健身房的订阅")
    assert res["status"] == "need_confirm"
    out = _confirm(client, res)
    assert out["status"] == "ok"
    assert "超级健身房" in out["reply"] and "299.00" in out["reply"]
    after = _confirm(client, chat(client, "查我的订阅"))
    assert "超级健身房" not in after["reply"]


def test_subscription_cancel_not_found(client):
    res = chat(client, "取消不存在的服务的订阅")
    out = _confirm(client, res)
    assert out["status"] == "rejected"
