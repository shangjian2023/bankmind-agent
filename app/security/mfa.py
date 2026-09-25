"""模拟 MFA：生成 6 位验证码，绑定 pending_action，限次校验。演示用，不发真实短信。"""

import random

from app import config


def issue():
    return f"{random.randrange(0, 1000000):06d}"


def failed(action_id):
    from app.data import repositories as repo

    repo.mfa_attempt_failed(action_id)


def attempts_exhausted(pending_row):
    return pending_row["mfa_attempts"] >= config.MFA_MAX_ATTEMPTS
