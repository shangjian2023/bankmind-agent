from datetime import datetime, timedelta

from app.data import repositories as repo
from tests.conftest import chat


def _confirm(client, res):
    return client.post("/api/confirm", json={"action_id": res["action_id"], "approve": True}).json()


def test_create_and_query_scheduled(client):
    res = chat(client, "明天上午9点给李娜转200元")
    assert res["status"] == "need_confirm"
    out = _confirm(client, res)
    assert out["status"] == "ok" and "定时转账已创建" in out["reply"] and "李娜" in out["reply"]
    q = chat(client, "查我的定时转账")
    assert q["status"] == "ok" and "待执行" in q["reply"] and "200.00" in q["reply"]


def test_scheduler_executes_due(client):
    payee = repo.find_contacts_by_name("u001", "李娜")[0]
    past = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    repo.insert_scheduled("u001", payee["name"], payee["account_no"], 200.0, past, "once")
    r = client.post("/api/admin/scheduler/tick").json()
    assert r["executed"]
    assert chat(client, "查一下我的余额")["reply"].count("15600.50") == 1
    assert any(t["status"] == "executed" for t in repo.list_scheduled("u001"))


def test_scheduler_blocks_over_limit(client):
    payee = repo.find_contacts_by_name("u001", "王强")[0]
    past = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    repo.insert_scheduled("u001", payee["name"], payee["account_no"], 1200.0, past, "once")
    r = client.post("/api/admin/scheduler/tick").json()
    assert not r["executed"]
    assert any(t["status"] == "blocked" for t in repo.list_scheduled("u001"))
    assert chat(client, "查一下我的余额")["reply"].count("15800.50") == 1


def test_scheduler_recurring_reschedules(client):
    payee = repo.find_contacts_by_name("u001", "李娜")[0]
    past = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
    repo.insert_scheduled("u001", payee["name"], payee["account_no"], 100.0, past, "weekly")
    client.post("/api/admin/scheduler/tick")
    tasks = repo.list_scheduled("u001")
    t = next(x for x in tasks if x["cycle"] == "weekly")
    assert t["status"] == "scheduled", "循环任务执行后应重新排期"
    assert t["execute_at"] > past
    assert chat(client, "查一下我的余额")["reply"].count("15700.50") == 1
