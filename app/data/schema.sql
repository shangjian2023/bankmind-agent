CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT,
  spouse_name TEXT,
  spouse_birthday TEXT
);
CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  account_no TEXT NOT NULL,
  balance REAL NOT NULL DEFAULT 0,
  type TEXT NOT NULL DEFAULT 'checking',
  currency TEXT NOT NULL DEFAULT 'CNY'
);
CREATE TABLE IF NOT EXISTS contacts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  phone TEXT,
  account_no TEXT,
  relation TEXT
);
CREATE TABLE IF NOT EXISTS transactions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL,
  user_id TEXT NOT NULL,
  counterparty TEXT NOT NULL,
  amount REAL NOT NULL,
  category TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'success',
  memo TEXT,
  ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscriptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  merchant TEXT NOT NULL,
  amount REAL NOT NULL,
  cycle TEXT NOT NULL DEFAULT 'monthly',
  next_charge TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS audit_logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trace_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  intent TEXT,
  level TEXT,
  detail TEXT,
  ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_actions(
  id TEXT PRIMARY KEY,
  trace_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  intent TEXT NOT NULL,
  slots TEXT NOT NULL,
  dag TEXT NOT NULL,
  level TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  mfa_code TEXT,
  mfa_attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
