from typing import Optional
from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    user_id: str
    message: str = Field(max_length=2000)


class ChatOut(BaseModel):
    status: str
    reply: str
    trace_id: Optional[str] = None
    action_id: Optional[str] = None
    data: dict = {}
    mfa_hint: Optional[str] = None


class ConfirmIn(BaseModel):
    action_id: str
    approve: bool


class MFAIn(BaseModel):
    action_id: str
    code: str
