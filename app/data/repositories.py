"""Repository 层：全部 SQL 集中在此。业务模块（tools/security/agent）只允许调用这里的函数。
更换数据库（SQLite → Postgres）或接入真实数据源时，仅需实现同签名函数。"""

import json
from datetime import date

from app.data.database import connect, now_iso


# ---------- users ----------

def get_user(user_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT id, name FROM users").fetchall()]


# ---------- accounts ----------

def list_accounts(user_id):
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,)).fetchall()]


def get_primary_account(user_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE user_id=? ORDER BY id LIMIT 1", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def debit_account(account_id, amount):
    with connect() as conn:
        conn.execute("UPDATE accounts SET balance=balance-? WHERE id=?", (amount, account_id))


# ---------- contacts ----------

def find_contact_by_phone(user_id, phone):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM contacts WHERE user_id=? AND phone=?", (user_id, phone)
        ).fetchone()
    return dict(row) if row else None


def find_contacts_by_name(user_id, name_like):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM contacts WHERE user_id=? AND name LIKE ?", (user_id, f"%{name_like}%")
            ).fetchall()
        ]


def find_spouse(user_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM contacts WHERE user_id=? AND relation='配偶'", (user_id,)
        ).fetchone()
    return dict(row) if row else None


# ---------- transactions ----------

def insert_transaction(account_id, user_id, counterparty, amount, category, memo=None, status="success"):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO transactions(account_id,user_id,counterparty,amount,category,status,memo,ts)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (account_id, user_id, counterparty, amount, category, status, memo, now_iso()),
        )
        return cur.lastrowid


def sum_transferred_today(user_id):
    today = date.today().isoformat()
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS s FROM transactions"
            " WHERE user_id=? AND category='transfer_out' AND status='success' AND ts LIKE ?",
            (user_id, f"{today}%"),
        ).fetchone()
    return abs(row["s"])


def transactions_since(user_id, since_iso):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT counterparty, amount, category, ts FROM transactions"
                " WHERE user_id=? AND ts>=? ORDER BY ts DESC",
                (user_id, since_iso),
            ).fetchall()
        ]


# ---------- subscriptions ----------

def active_subscriptions(user_id):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM subscriptions WHERE user_id=? AND status='active' ORDER BY next_charge",
                (user_id,),
            ).fetchall()
        ]


def find_active_subscriptions_by_merchant(user_id, merchant_like):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM subscriptions WHERE user_id=? AND status='active' AND merchant LIKE ?",
                (user_id, f"%{merchant_like}%"),
            ).fetchall()
        ]


def cancel_subscription(sub_id):
    with connect() as conn:
        conn.execute("UPDATE subscriptions SET status='cancelled' WHERE id=?", (sub_id,))


# ---------- pending actions ----------

def insert_pending(action_id, trace_id, user_id, intent, slots, dag, level, mfa_code=None):
    with connect() as conn:
        conn.execute(
            "INSERT INTO pending_actions(id,trace_id,user_id,intent,slots,dag,level,status,mfa_code,created_at)"
            " VALUES(?,?,?,?,?,?,?,'pending',?,?)",
            (
                action_id,
                trace_id,
                user_id,
                intent,
                json.dumps(slots, ensure_ascii=False),
                json.dumps(dag),
                level,
                mfa_code,
                now_iso(),
            ),
        )


def get_pending(action_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM pending_actions WHERE id=?", (action_id,)).fetchone()
    return dict(row) if row else None


def set_pending_status(action_id, status):
    with connect() as conn:
        conn.execute("UPDATE pending_actions SET status=? WHERE id=?", (status, action_id))


def mfa_attempt_failed(action_id):
    with connect() as conn:
        conn.execute("UPDATE pending_actions SET mfa_attempts=mfa_attempts+1 WHERE id=?", (action_id,))


# ---------- audit ----------

def insert_audit(trace_id, user_id, stage, intent=None, level=None, detail=None):
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit_logs(trace_id,user_id,stage,intent,level,detail,ts) VALUES(?,?,?,?,?,?,?)",
            (
                trace_id,
                user_id,
                stage,
                intent,
                level,
                json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
                now_iso(),
            ),
        )


def query_audit(user_id, limit=100, trace_id=None):
    q = "SELECT * FROM audit_logs WHERE user_id=?"
    params = [user_id]
    if trace_id:
        q += " AND trace_id=?"
        params.append(trace_id)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]
