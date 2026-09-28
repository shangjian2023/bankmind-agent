"""操作审计：trace_id 贯穿全链路，每个阶段落库（写入经 repository 层）。"""

from app.data import repositories as repo
from app.security.pii_mask import mask_detail


def log(trace_id, user_id, stage, intent=None, level=None, detail=None):
    # 自动脱敏敏感信息
    masked_detail = mask_detail(detail)
    repo.insert_audit(trace_id, user_id, stage, intent, level, masked_detail)


def for_user(user_id, limit=100, trace_id=None, offset=0):
    return repo.query_audit(user_id, limit, trace_id, offset)
