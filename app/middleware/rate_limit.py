"""简单限流中间件：基于内存的用户级请求限流。"""

import time
from collections import defaultdict
from typing import Dict, List

from app import config


class RateLimiter:
    """滑动窗口限流器。"""

    def __init__(self, window_seconds: int = config.RATE_LIMIT_WINDOW_SECONDS,
                 max_requests: int = config.RATE_LIMIT_MAX_REQUESTS):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        """检查用户是否允许请求。"""
        now = time.time()
        cutoff = now - self.window_seconds

        # 清理过期记录
        self.requests[user_id] = [t for t in self.requests[user_id] if t > cutoff]

        # 检查是否超限
        if len(self.requests[user_id]) >= self.max_requests:
            return False

        # 记录本次请求
        self.requests[user_id].append(now)
        return True

    def get_remaining(self, user_id: str) -> int:
        """获取用户剩余可用请求数。"""
        now = time.time()
        cutoff = now - self.window_seconds
        active = [t for t in self.requests[user_id] if t > cutoff]
        return max(0, self.max_requests - len(active))


# 全局限流器实例
limiter = RateLimiter()
