"""数据库管理模块 - 包含后台管理系统初始化"""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from app import config

BASE = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(BASE, "schema.sql")
ADMIN_SCHEMA_PATH = os.path.join(BASE, "admin_schema.sql")
SEED_DIR = os.path.join(BASE, "seed")

_local = threading.local()


@contextmanager
def connect():
    """获取数据库连接"""
    existing = getattr(_local, "conn", None)
    if existing is not None:
        yield existing
        return
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


@contextmanager
def transaction():
    """事务管理"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    old = getattr(_local, "conn", None)
    _local.conn = conn
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        _local.conn = old


def now_iso():
    """获取当前时间的 ISO 格式"""
    return datetime.now().isoformat(timespec="seconds")


def init_db():
    """初始化业务数据库"""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        with connect() as conn:
            conn.executescript(f.read())


def init_admin_db():
    """初始化管理后台数据库"""
    if not os.path.exists(ADMIN_SCHEMA_PATH):
        return

    with open(ADMIN_SCHEMA_PATH, encoding="utf-8") as f:
        with connect() as conn:
            conn.executescript(f.read())

    # 创建默认管理员账户（如果不存在）
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE name = 'admin'"
        ).fetchone()

        if not existing:
            now = now_iso()
            # 默认密码: admin123 (实际生产环境应该强制修改)
            from app.admin.auth import hash_password
            admin_id = "admin"
            password_hash = hash_password("admin123", admin_id)

            conn.execute(
                """INSERT INTO users
                   (id, name, phone, email, password_hash, role, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (admin_id, "admin", "13800000000", "admin@bankmind.local",
                 password_hash, "super_admin", "active", now, now)
            )

            # 记录初始化日志
            conn.execute(
                """INSERT INTO admin_logs
                   (admin_id, action, target_type, target_id, details, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("admin", "system_init", "system", "admin_user",
                 json.dumps({"message": "系统初始化，创建默认管理员账户"}), now)
            )


def is_seeded():
    """检查数据库是否已播种"""
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def _load(name):
    """加载种子数据"""
    with open(os.path.join(SEED_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def seed():
    """播种数据库"""
    with connect() as conn:
        for u in _load("users"):
            conn.execute(
                "INSERT INTO users(id,name,phone,spouse_name,spouse_birthday,created_at) VALUES(?,?,?,?,?,?)",
                (u["id"], u["name"], u["phone"], u.get("spouse_name"), u.get("spouse_birthday"), now_iso()),
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
            from datetime import date, timedelta
            ts_date = date.today() - timedelta(days=t["days_ago"])
            ts = f"{ts_date.isoformat()}T{t.get('hour', 10):02d}:00:00"
            conn.execute(
                "INSERT INTO transactions(account_id,user_id,counterparty,amount,category,status,memo,ts)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (acct_id, "u001", t["counterparty"], t["amount"], t["category"], "success", t.get("memo"), ts),
            )
        for s in _load("subscriptions"):
            from datetime import date, timedelta
            next_charge = (date.today() + timedelta(days=s["next_charge_days_ahead"])).isoformat()
            conn.execute(
                "INSERT INTO subscriptions(user_id,merchant,amount,cycle,next_charge) VALUES(?,?,?,?,?)",
                (s["user_id"], s["merchant"], s["amount"], s["cycle"], next_charge),
            )
        for p in _load("products"):
            conn.execute(
                "INSERT INTO products(code,name,type,annual_rate,risk_level,min_amount,term_days,description)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (p["code"], p["name"], p["type"], p["annual_rate"], p["risk_level"], p["min_amount"], p["term_days"], p["description"]),
            )


def reset_and_seed():
    """重置并播种数据库"""
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    init_db()
    init_admin_db()
    seed()
