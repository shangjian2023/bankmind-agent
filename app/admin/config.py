"""系统配置管理模块"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.data import database
from app.admin.auth import get_current_admin

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


class ConfigItem(BaseModel):
    config_key: str
    config_value: str
    config_type: str = "string"  # string, number, boolean, json
    description: Optional[str]


class ConfigUpdate(BaseModel):
    config_value: str
    description: Optional[str]


class ConfigResponse(BaseModel):
    id: int
    config_key: str
    config_value: str
    config_type: str
    description: Optional[str]
    updated_by: Optional[str]
    updated_at: str


class ConfigListResponse(BaseModel):
    configs: List[ConfigResponse]
    total: int


# 默认配置项
DEFAULT_CONFIGS = [
    # LLM 配置
    ("llm_provider", "openai", "string", "LLM 提供商 (openai, azure, aliyun, etc.)"),
    ("llm_base_url", "https://api.openai.com/v1", "string", "LLM API 基础 URL"),
    ("llm_model", "gpt-4", "string", "默认使用的模型"),
    ("llm_temperature", "0.7", "number", "生成温度"),
    ("llm_max_tokens", "2000", "number", "最大 token 数"),

    # 意图识别配置
    ("intent_fallback_enabled", "true", "boolean", "是否启用 LLM 意图识别 fallback"),
    ("intent_confidence_threshold", "0.7", "number", "意图识别置信度阈值"),
    ("intent_max_retries", "3", "number", "意图识别失败最大重试次数"),

    # 安全配置
    ("rate_limit_per_minute", "60", "number", "每分钟请求限制"),
    ("rate_limit_per_day", "1000", "number", "每日请求限制"),
    ("session_timeout_hours", "24", "number", "会话超时时间（小时）"),
    ("mfa_required", "false", "boolean", "是否强制启用 MFA"),

    # 业务配置
    ("transfer_daily_limit", "1000", "number", "每日转账限额"),
    ("anomaly_amount_sigma", "3.0", "number", "异常金额检测标准差"),
    ("bill_analysis_window_days", "90", "number", "账单分析窗口天数"),

    # 系统配置
    ("maintenance_mode", "false", "boolean", "维护模式"),
    ("debug_mode", "false", "boolean", "调试模式"),
]


@router.get("", response_model=ConfigListResponse)
async def list_configs(
    current_admin: dict = Depends(get_current_admin)
):
    """获取所有配置"""
    with database.connect() as conn:
        configs = [dict(row) for row in conn.execute(
            "SELECT * FROM system_config ORDER BY config_key"
        ).fetchall()]

    return ConfigListResponse(
        configs=[ConfigResponse(**config) for config in configs],
        total=len(configs)
    )


@router.get("/{config_key}", response_model=ConfigResponse)
async def get_config(
    config_key: str,
    current_admin: dict = Depends(get_current_admin)
):
    """获取指定配置"""
    with database.connect() as conn:
        config = conn.execute(
            "SELECT * FROM system_config WHERE config_key = ?",
            (config_key,)
        ).fetchone()

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Config not found"
            )

    return ConfigResponse(**dict(config))


@router.put("/{config_key}", response_model=ConfigResponse)
async def update_config(
    config_key: str,
    config_data: ConfigUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """更新配置"""
    with database.connect() as conn:
        config = conn.execute(
            "SELECT * FROM system_config WHERE config_key = ?",
            (config_key,)
        ).fetchone()

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Config not found"
            )

        now = datetime.now().isoformat()
        updates = ["config_value = ?", "updated_at = ?", "updated_by = ?"]
        params = [config_data.config_value, now, current_admin["user_id"]]

        if config_data.description is not None:
            updates.append("description = ?")
            params.append(config_data.description)

        params.append(config_key)

        conn.execute(
            f"UPDATE system_config SET {', '.join(updates)} WHERE config_key = ?",
            params
        )

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'update_config', 'config', ?, ?, ?)""",
            (current_admin["user_id"], config_key,
             f'{{"config_key": "{config_key}", "old_value": "{config["config_value"]}", "new_value": "{config_data.config_value}"}}',
             now)
        )

        updated_config = conn.execute(
            "SELECT * FROM system_config WHERE config_key = ?",
            (config_key,)
        ).fetchone()

    return ConfigResponse(**dict(updated_config))


@router.post("/init-defaults")
async def init_default_configs(
    current_admin: dict = Depends(get_current_admin)
):
    """初始化默认配置"""
    now = datetime.now().isoformat()
    created_count = 0

    with database.connect() as conn:
        for key, value, config_type, description in DEFAULT_CONFIGS:
            existing = conn.execute(
                "SELECT config_key FROM system_config WHERE config_key = ?",
                (key,)
            ).fetchone()

            if not existing:
                conn.execute(
                    """INSERT INTO system_config
                       (config_key, config_value, config_type, description, updated_by, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (key, value, config_type, description, current_admin["user_id"], now)
                )
                created_count += 1

    return {
        "message": f"Initialized {created_count} default configurations",
        "created_count": created_count
    }


@router.get("/value/{config_key}")
async def get_config_value(
    config_key: str
):
    """获取配置值（无需认证，用于系统内部调用）"""
    with database.connect() as conn:
        config = conn.execute(
            "SELECT config_value, config_type FROM system_config WHERE config_key = ?",
            (config_key,)
        ).fetchone()

        if not config:
            # 返回默认值
            for key, value, config_type, _ in DEFAULT_CONFIGS:
                if key == config_key:
                    return {"config_key": config_key, "config_value": value, "config_type": config_type}

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Config not found"
            )

    return {
        "config_key": config_key,
        "config_value": config["config_value"],
        "config_type": config["config_type"]
    }
