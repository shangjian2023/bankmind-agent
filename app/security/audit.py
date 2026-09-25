"""操作审计：trace_id 贯穿全链路，每个阶段落库（写入经 repository 层）。"""

from app.data import repositories as repo


def log(trace_id, user_id, stage, intent=None, level=None, detail=None):
    repo.insert_audit(trace_id, user_id, stage, intent, level, detail)


def for_user(user_id, limit=100, trace_id=None):
    return repo.query_audit(user_id, limit, trace_id)
