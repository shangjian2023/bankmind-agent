import os

APP_NAME = "BankMind 银行AI智能体"
DB_PATH = os.environ.get("BANK_DB", "bank.db")

YELLOW_DAILY_TRANSFER_LIMIT = 1000.0
CIRCUIT_FAIL_LIMIT = 3
CIRCUIT_LOCK_SECONDS = 15 * 60
MFA_MAX_ATTEMPTS = 3
ANOMALY_AMOUNT_SIGMA = 3.0
ANOMALY_DUPLICATE_MIN = 3

LLM_MODE = os.environ.get("LLM_MODE", "mock")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "")

DEV_SHOW_MFA_CODE = os.environ.get("DEV_SHOW_MFA_CODE", "1") == "1"
