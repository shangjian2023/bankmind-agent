from tests.conftest import chat


def _confirm(client, res):
    return client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()


def test_aa_split(client):
    res = chat(client, "我们4个人AA了240元")
    assert res["status"] == "need_confirm"
    out = _confirm(client, res)
    assert out["status"] == "ok" and "60.00" in out["reply"] and "4 人" in out["reply"]


def test_abort_cancels_pending(client):
    res = chat(client, "给李娜转500元")
    assert res["status"] == "need_confirm"
    out = chat(client, "算了")
    assert out["status"] == "ok" and "已中止" in out["reply"] and "取消" in out["reply"]
    stale = client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()
    assert stale["status"] == "rejected", "被中止的操作不能再确认"


def test_human_takeover(client):
    res = chat(client, "转人工")
    assert res["status"] == "ok" and "人工坐席" in res["reply"]
    logs = client.get("/api/audit", params={"user_id": "u001", "limit": 5, "trace_id": res["trace_id"]}).json()["logs"]
    assert "human_takeover" in [l["stage"] for l in logs]


def test_yearly_report(client):
    res = chat(client, "看看我今年的年度账单")
    assert res["status"] == "ok"
    assert "逐月支出" in res["reply"] and "最大单笔支出" in res["reply"]


def test_birthday_default_locks_1000(client):
    res = chat(client, "我爱人生日快到了，帮我安排鲜花蛋糕")
    assert res["status"] == "need_confirm"
    out = _confirm(client, res)
    assert out["status"] == "ok"
    assert "锁定 1000.00 元" in out["reply"] and "前 2 天" in out["reply"]
    assert "600.00" in out["reply"] and "400.00" in out["reply"]
