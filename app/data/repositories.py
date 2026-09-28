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


def query_audit(user_id, limit=100, trace_id=None, offset=0):
    q = "SELECT * FROM audit_logs WHERE user_id=?"
    params = [user_id]
    if trace_id:
        q += " AND trace_id=?"
        params.append(trace_id)
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


# ---------- products / investments ----------

def list_products():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY risk_level, annual_rate DESC").fetchall()]


def find_products_by_name(keyword):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute("SELECT * FROM products WHERE name LIKE ?", (f"%{keyword}%",)).fetchall()
        ]


def insert_investment(user_id, product_code, product_name, amount, annual_rate):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO investments(user_id,product_code,product_name,amount,annual_rate,status,purchased_at)"
            " VALUES(?,?,?,?,?,'holding',?)",
            (user_id, product_code, product_name, amount, annual_rate, now_iso()),
        )
        return cur.lastrowid


def list_investments(user_id):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM investments WHERE user_id=? AND status='holding'", (user_id,)
            ).fetchall()
        ]


def find_holdings_by_name(user_id, keyword):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM investments WHERE user_id=? AND status='holding' AND product_name LIKE ?",
                (user_id, f"%{keyword}%"),
            ).fetchall()
        ]


def redeem_investment(inv_id):
    with connect() as conn:
        conn.execute(
            "UPDATE investments SET status='redeemed', redeemed_at=? WHERE id=?", (now_iso(), inv_id)
        )


def set_user_risk(user_id, level):
    with connect() as conn:
        conn.execute("UPDATE users SET risk_level=? WHERE id=?", (level, user_id))


# ---------- scheduled transfers ----------

def insert_scheduled(user_id, payee_name, payee_account, amount, execute_at, cycle, memo=None):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO scheduled_transfers(user_id,payee_name,payee_account,amount,execute_at,cycle,status,memo,created_at)"
            " VALUES(?,?,?,?,?,?, 'scheduled', ?, ?)",
            (user_id, payee_name, payee_account, amount, execute_at, cycle, memo, now_iso()),
        )
        return cur.lastrowid


def list_scheduled(user_id):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM scheduled_transfers WHERE user_id=? ORDER BY execute_at", (user_id,)
            ).fetchall()
        ]


def due_scheduled(now_iso):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM scheduled_transfers WHERE status='scheduled' AND execute_at<=?", (now_iso,)
            ).fetchall()
        ]


def update_scheduled(task_id, status=None, execute_at=None):
    sets, params = [], []
    if status is not None:
        sets.append("status=?")
        params.append(status)
    if execute_at is not None:
        sets.append("execute_at=?")
        params.append(execute_at)
    params.append(task_id)
    with connect() as conn:
        conn.execute(f"UPDATE scheduled_transfers SET {', '.join(sets)} WHERE id=?", params)


# ---------- aa collections ----------

def insert_aa(user_id, total, people, per_person, code):
    with connect() as conn:
        conn.execute(
            "INSERT INTO aa_collections(user_id,total,people,per_person,code,status,created_at)"
            " VALUES(?,?,?,?,?,'collecting',?)",
            (user_id, total, people, per_person, code, now_iso()),
        )


# ---------- pending actions（补充） ----------

def latest_pending(user_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM pending_actions WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


# ---------- cards ----------

def list_cards(user_id):
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM cards WHERE user_id=? ORDER BY id", (user_id,)
            ).fetchall()
        ]


def get_card_by_no(user_id, card_no):
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM cards WHERE user_id=? AND card_no=?", (user_id, card_no)
        ).fetchone()
    return dict(row) if row else None


def get_card_by_id(card_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    return dict(row) if row else None


def insert_card(user_id, card_no, card_type, card_brand, expires_at, daily_limit=5000, monthly_limit=50000):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO cards(user_id,card_no,card_type,card_brand,status,daily_limit,monthly_limit,frozen,expires_at,created_at)"
            " VALUES(?,?,?,'UnionPay','inactive',?,?,0,?,?)",
            (user_id, card_no, card_type, daily_limit, monthly_limit, expires_at, now_iso()),
        )
        return cur.lastrowid


def activate_card(card_id):
    with connect() as conn:
        conn.execute("UPDATE cards SET status='active' WHERE id=?", (card_id,))


def freeze_card(card_id):
    with connect() as conn:
        conn.execute("UPDATE cards SET frozen=1 WHERE id=?", (card_id,))


def unfreeze_card(card_id):
    with connect() as conn:
        conn.execute("UPDATE cards SET frozen=0 WHERE id=?", (card_id,))


def update_card_limits(card_id, daily_limit=None, monthly_limit=None):
    sets, params = [], []
    if daily_limit is not None:
        sets.append("daily_limit=?")
        params.append(daily_limit)
    if monthly_limit is not None:
        sets.append("monthly_limit=?")
        params.append(monthly_limit)
    if not sets:
        return
    params.append(card_id)
    with connect() as conn:
        conn.execute(f"UPDATE cards SET {', '.join(sets)} WHERE id=?", params)


def deactivate_card(card_id):
    with connect() as conn:
        conn.execute("UPDATE cards SET status='deactivated' WHERE id=?", (card_id,))

