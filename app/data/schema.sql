CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT,
  spouse_name TEXT,
  spouse_birthday TEXT,
  risk_level TEXT,
  role TEXT DEFAULT 'user',
  email TEXT,
  password_hash TEXT,
  status TEXT DEFAULT 'active',
  created_at TEXT,
  updated_at TEXT,
  last_login TEXT
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
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  annual_rate REAL NOT NULL,
  risk_level TEXT NOT NULL,
  min_amount REAL NOT NULL,
  term_days INTEGER NOT NULL,
  description TEXT
);
CREATE TABLE IF NOT EXISTS investments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  product_code TEXT NOT NULL,
  product_name TEXT NOT NULL,
  amount REAL NOT NULL,
  annual_rate REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'holding',
  purchased_at TEXT NOT NULL,
  redeemed_at TEXT
);
CREATE TABLE IF NOT EXISTS scheduled_transfers(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  payee_name TEXT NOT NULL,
  payee_account TEXT,
  amount REAL NOT NULL,
  execute_at TEXT NOT NULL,
  cycle TEXT NOT NULL DEFAULT 'once',
  status TEXT NOT NULL DEFAULT 'scheduled',
  memo TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aa_collections(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  total REAL NOT NULL,
  people INTEGER NOT NULL,
  per_person REAL NOT NULL,
  code TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'collecting',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  card_no TEXT NOT NULL UNIQUE,
  card_type TEXT NOT NULL DEFAULT 'debit',
  card_brand TEXT NOT NULL DEFAULT 'UnionPay',
  status TEXT NOT NULL DEFAULT 'inactive',
  daily_limit REAL NOT NULL DEFAULT 5000,
  monthly_limit REAL NOT NULL DEFAULT 50000,
  frozen INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- Performance indexes for common queries
CREATE INDEX IF NOT EXISTS idx_transactions_user_ts ON transactions(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_trace ON audit_logs(user_id, trace_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_status_execute ON scheduled_transfers(status, execute_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status ON subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_pending_user_status ON pending_actions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_investments_user_status ON investments(user_id, status);
CREATE INDEX IF NOT EXISTS idx_contacts_user_phone ON contacts(user_id, phone);
CREATE INDEX IF NOT EXISTS idx_contacts_user_name ON contacts(user_id, name);
CREATE INDEX IF NOT EXISTS idx_contacts_user_relation ON contacts(user_id, relation);
CREATE INDEX IF NOT EXISTS idx_products_risk ON products(risk_level);
CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status);
