from fastapi import APIRouter, HTTPException

from app import config
from app.agent import orchestrator
from app.data import repositories as repo
from app.data import database
from app.models import ChatIn, ChatOut, ConfirmIn, MFAIn
from app.security import audit

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok", "app": config.APP_NAME, "llm_mode": config.LLM_MODE, "db": config.DB_PATH}


@router.get("/users")
def users():
    return {"users": repo.list_users()}


@router.post("/chat", response_model=ChatOut)
def chat(inp: ChatIn):
    if not repo.get_user(inp.user_id):
        raise HTTPException(404, f"用户 {inp.user_id} 不存在")
    return orchestrator.handle_message(inp.user_id, inp.message)


@router.post("/confirm", response_model=ChatOut)
def confirm(inp: ConfirmIn):
    return orchestrator.confirm_action(inp.action_id, inp.approve)


@router.post("/mfa/verify", response_model=ChatOut)
def verify(inp: MFAIn):
    return orchestrator.verify_mfa(inp.action_id, inp.code)


@router.get("/audit")
def audit_logs(user_id: str, limit: int = 50, trace_id: str | None = None):
    return {"logs": audit.for_user(user_id, limit, trace_id)}


@router.post("/admin/reseed")
def reseed():
    database.reset_and_seed()
    return {"status": "reseeded"}
