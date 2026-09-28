"""安全响应头中间件：OWASP 推荐的安全头。"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"
        # 防止点击劫持
        response.headers["X-Frame-Options"] = "DENY"
        # 启用浏览器 XSS 过滤
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # 禁止 Referer 泄露敏感路径
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # 限制浏览器功能
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # 内容安全策略（允许内联脚本和样式，因为前端用了 Vite 构建）
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )

        return response
