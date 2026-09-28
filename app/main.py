"""应用入口：FastAPI 生命周期、中间件注册、静态文件挂载。"""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app import config, scheduler
from app.api import routes
from app.admin import auth, users, api_keys, announcements, config as admin_config, logs, intents
from app.data import database
from app.logging_config import setup_logging
from app.middleware.rate_limit import limiter
from app.middleware.security_headers import SecurityHeadersMiddleware

DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
STATIC_DIR = DIST_DIR if os.path.isdir(DIST_DIR) else "static"

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app):
    setup_logging()
    logger.info("应用启动", extra={"llm_mode": config.LLM_MODE, "db": config.DB_PATH})
    database.init_db()
    database.init_admin_db()
    if not database.is_seeded():
        database.seed()
        logger.info("数据库播种完成")
    scheduler.start()
    yield
    scheduler.stop()
    logger.info("应用关闭")


app = FastAPI(title=config.APP_NAME, lifespan=lifespan)

# 中间件注册（注意：后注册的先执行）
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def logging_and_rate_limit_middleware(request: Request, call_next):
    """请求日志 + 限流中间件。"""
    start = time.time()

    # 限流检查（仅对写操作和敏感端点）
    user_id = None
    if request.url.path in ("/api/chat", "/api/confirm", "/api/mfa/verify"):
        try:
            body = await request.json()
            user_id = body.get("user_id")
        except Exception:
            pass
        if user_id and not limiter.is_allowed(user_id):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
            )

    response = await call_next(request)
    elapsed = time.time() - start

    logger.info(
        f"{request.method} {request.url.path} {response.status_code} {elapsed:.3f}s",
        extra={"method": request.method, "path": request.url.path, "status": response.status_code, "elapsed": elapsed},
    )
    return response


# 业务路由
app.include_router(routes.router)

# 管理后台路由（注意：各模块 router 已自带 prefix，这里不要再加）
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(api_keys.router)
app.include_router(announcements.router)
app.include_router(admin_config.router)
app.include_router(logs.router)
app.include_router(intents.router)

# 静态文件（必须最后挂载）
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

