"""配置管理 - 从数据库读取配置"""

import os
from app.data import database


def get_config(key: str, default=None):
    """从数据库读取配置"""
    try:
        with database.connect() as conn:
            row = conn.execute(
                "SELECT config_value FROM system_config WHERE config_key = ?",
                (key,)
            ).fetchone()

            if row:
                return row["config_value"]
    except Exception:
        pass

    return default


def get_config_typed(key: str, default=None):
    """从数据库读取配置并转换类型"""
    try:
        with database.connect() as conn:
            row = conn.execute(
                "SELECT config_value, config_type FROM system_config WHERE config_key = ?",
                (key,)
            ).fetchone()

            if row:
                value = row["config_value"]
                config_type = row["config_type"]

                if config_type == "number":
                    return float(value)
                elif config_type == "boolean":
                    return value.lower() in ("true", "1", "yes")
                elif config_type == "json":
                    import json
                    return json.loads(value)
                else:
                    return value
    except Exception:
        pass

    return default


# 系统配置（从环境变量或数据库读取）
APP_NAME = os.environ.get("APP_NAME", "BankMind 银行智能助手")
DB_PATH = os.environ.get("BANK_DB", "bank.db")

# LLM 配置
LLM_MODE = get_config("llm_provider", os.environ.get("LLM_MODE", "mock"))
OPENAI_BASE_URL = get_config("llm_base_url", os.environ.get("OPENAI_BASE_URL", ""))
OPENAI_API_KEY = get_config("llm_api_key", os.environ.get("OPENAI_API_KEY", ""))
OPENAI_MODEL = get_config("llm_model", os.environ.get("OPENAI_MODEL", "gpt-4"))

# 权限与风控
YELLOW_DAILY_TRANSFER_LIMIT = float(get_config("transfer_daily_limit", "1000"))
CIRCUIT_FAIL_LIMIT = int(get_config("circuit_fail_limit", "3"))
CIRCUIT_LOCK_SECONDS = int(get_config("circuit_lock_seconds", "900"))
MFA_MAX_ATTEMPTS = int(get_config("mfa_max_attempts", "3"))
ANOMALY_AMOUNT_SIGMA = float(get_config("anomaly_amount_sigma", "3.0"))
ANOMALY_DUPLICATE_MIN = int(get_config("anomaly_duplicate_min", "3"))

# 槽位提取限制
MAX_TRANSFER_AMOUNT = float(get_config("max_transfer_amount", "10000000"))
MAX_MEMO_LENGTH = int(get_config("max_memo_length", "30"))
MAX_PAYEE_LENGTH = int(get_config("max_payee_length", "8"))
MAX_MERCHANT_LENGTH = int(get_config("max_merchant_length", "12"))
MAX_PRODUCT_LENGTH = int(get_config("max_product_length", "15"))

# 账单分析窗口
BILL_ANALYSIS_WINDOW_DAYS = int(get_config("bill_analysis_window_days", "90"))
BILL_YEARLY_WINDOW_DAYS = int(get_config("bill_yearly_window_days", "365"))
BILL_SUBSCRIPTION_SOON_DAYS = int(get_config("bill_subscription_soon_days", "7"))

# 生日关怀
BIRTHDAY_ORDER_ADVANCE_DAYS = int(get_config("birthday_order_advance_days", "2"))

# 配偶关键词
SPOUSE_KEYWORDS = {"爱人", "老婆", "媳妇", "太太", "老公", "丈夫", "配偶"}

# 限流
RATE_LIMIT_WINDOW_SECONDS = int(get_config("rate_limit_window_seconds", "60"))
RATE_LIMIT_MAX_REQUESTS = int(get_config("rate_limit_per_minute", "30"))
RATE_LIMIT_MFA_MAX = int(get_config("rate_limit_mfa_max", "10"))

# 意图识别
INTENT_FALLBACK_ENABLED = get_config_typed("intent_fallback_enabled", True)
INTENT_CONFIDENCE_THRESHOLD = float(get_config("intent_confidence_threshold", "0.7"))

# 开发/调试
DEV_SHOW_MFA_CODE = os.environ.get("DEV_SHOW_MFA_CODE", "1") == "1"

# 加密密钥（用于 API Key 加密）
SECRET_KEY = os.environ.get("SECRET_KEY", "bankmind-secret-key-change-in-production")
