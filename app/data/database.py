"""数据层：连接管理 + schema 初始化 + JSON 种子播种。业务代码禁止绕过 repositories 直接写 SQL。"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from app import config

BASE = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(BASE, "schema.sql")
SEED_DIR = os.path.join(BASE, "seed")


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def init_db():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        with connect() as conn:
            conn.executescript(f.read())


def is_seeded():
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def _load(name):
    with open(os.path.join(SEED_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def seed():
    with connect() as conn:
        for u in _load("users"):
            bday = (
                date.today() + timedelta(days=u["spouse_birthday_days_ahead"])
                if u.get("spouse_birthday_days_ahead") is not None
                else None
            )
            conn.execute(
                "INSERT INTO users(id,name,phone,spouse_name,spouse_birthday) VALUES(?,?,?,?,?)",
                (u["id"], u["name"], u["phone"], u.get("spouse_name"), bday.isoformat() if bday else None),
            )
        for a in _load("accounts"):
            conn.execute(
                "INSERT INTO accounts(user_id,account_no,balance,type,currency) VALUES(?,?,?,?,?)",
                (a["user_id"], a["account_no"], a["balance"], a["type"], a.get("currency", "CNY")),
            )
        for c in _load("contacts"):
            conn.execute(
                "INSERT INTO contacts(user_id,name,phone,account_no,relation) VALUES(?,?,?,?,?)",
                (c["user_id"], c["name"], c["phone"], c["account_no"], c["relation"]),
            )
        acct_id = conn.execute("SELECT id FROM accounts WHERE user_id='u001'").fetchone()["id"]
        for t in _load("transactions"):
            ts_date = date.today() - timedelta(days=t["days_ago"])
            ts = f"{ts_date.isoformat()}T{t.get('hour', 10):02d}:00:00"
            conn.execute(
                "INSERT INTO transactions(account_id,user_id,counterparty,amount,category,status,memo,ts)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (acct_id, "u001", t["counterparty"], t["amount"], t["category"], "success", t.get("memo"), ts),
            )
        for s in _load("subscriptions"):
            nc = date.today() + timedelta(days=s["next_charge_days_ahead"])
            conn.execute(
                "INSERT INTO subscriptions(user_id,merchant,amount,cycle,next_charge) VALUES(?,?,?,?,?)",
                (s["user_id"], s["merchant"], s["amount"], s["cycle"], nc.isoformat()),
            )
        for p in _load("products"):
            conn.execute(
                "INSERT INTO products(code,name,type,annual_rate,risk_level,min_amount,term_days,description)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (p["code"], p["name"], p["type"], p["annual_rate"], p["risk_level"], p["min_amount"], p["term_days"], p["description"]),
            )


def reset_and_seed():
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    init_db()
    seed()
