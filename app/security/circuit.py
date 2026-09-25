"""异常熔断：连续失败 / 可疑行为达到阈值后临时锁定。内存实现，重启清零（见 SECURITY.md 已知限制）。"""

import time

from app import config

_state = {}  # user_id -> {"fails": int, "susp": int, "locked_until": float}


def _rec(user_id):
    return _state.setdefault(user_id, {"fails": 0, "susp": 0, "locked_until": 0})


def record_failure(user_id):
    rec = _rec(user_id)
    rec["fails"] += 1
    if rec["fails"] >= config.CIRCUIT_FAIL_LIMIT:
        _lock(rec)
        return True
    return False


def record_suspicious(user_id):
    rec = _rec(user_id)
    rec["susp"] += 1
    if rec["susp"] >= config.CIRCUIT_FAIL_LIMIT:
        _lock(rec)
        return True
    return False


def record_success(user_id):
    _state[user_id] = {"fails": 0, "susp": 0, "locked_until": 0}


def _lock(rec):
    rec["locked_until"] = time.time() + config.CIRCUIT_LOCK_SECONDS


def is_locked(user_id):
    return _rec(user_id)["locked_until"] > time.time()


def lock_remaining(user_id):
    return max(0, int(_rec(user_id)["locked_until"] - time.time()))
