"""结构化日志配置：统一格式、级别、输出。"""

import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON 格式日志，便于日志收集和分析。"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        # 拼接为单行 JSON
        import json
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level=logging.INFO):
    """初始化日志系统。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # 降低第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


def get_logger(name):
    """获取命名 logger。"""
    return logging.getLogger(name)
