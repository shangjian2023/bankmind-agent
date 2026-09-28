"""后台管理模块"""

from app.admin.auth import router as auth_router
from app.admin.users import router as users_router
from app.admin.api_keys import router as api_keys_router
from app.admin.announcements import router as announcements_router
from app.admin.config import router as config_router
from app.admin.logs import router as logs_router

__all__ = [
    "auth_router",
    "users_router",
    "api_keys_router",
    "announcements_router",
    "config_router",
    "logs_router",
]
