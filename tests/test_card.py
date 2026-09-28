"""卡片管理功能测试"""
import pytest
from app.data import database, repositories as repo
from app.agent_graph.runner import handle_message, confirm_action, verify_mfa
from app.security import permissions


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前重置数据库"""
    database.reset_and_seed()
    yield


def test_card_query_green():
    """测试卡片查询（绿色权限）"""
    # 先申请一张卡
    result = handle_message("u001", "申请一张新卡")
    assert result.status == "need_confirm"
    action_id = result.action_id
    confirm_action(action_id, approve=True)

    # 查询卡片
    result = handle_message("u001", "查看我的卡片")
    assert result.status == "ok"
    assert "卡片" in result.reply
    assert "6222" in result.reply or "6228" in result.reply


def test_card_apply_yellow():
    """测试卡片申请（黄色权限）"""
    result = handle_message("u001", "申请一张借记卡")
    assert result.status == "need_confirm"
    assert result.data["level"] == permissions.YELLOW

    # 确认申请
    action_id = result.action_id
    result = confirm_action(action_id, approve=True)
    assert result.status == "ok"
    assert "申请成功" in result.reply
    assert "卡号" in result.reply


def test_card_activate_yellow():
    """测试卡片激活（黄色权限）"""
    # 先申请一张卡
    result = handle_message("u001", "申请新卡")
    action_id = result.action_id
    confirm_action(action_id, approve=True)

    # 获取卡片ID
    cards = repo.list_cards("u001")
    card_id = cards[0]["id"]

    # 激活卡片
    result = handle_message("u001", f"激活卡片{card_id}")
    assert result.status == "need_confirm"
    assert result.data["level"] == permissions.YELLOW

    # 确认激活
    action_id = result.action_id
    result = confirm_action(action_id, approve=True)
    assert result.status == "ok"
    assert "已激活" in result.reply


def test_card_freeze_red():
    """测试卡片冻结（红色权限，需要MFA）"""
    # 申请并激活一张卡
    result = handle_message("u001", "申请新卡")
    confirm_action(result.action_id, approve=True)

    cards = repo.list_cards("u001")
    card_id = cards[0]["id"]

    result = handle_message("u001", f"激活卡片{card_id}")
    confirm_action(result.action_id, approve=True)

    # 冻结卡片
    result = handle_message("u001", f"冻结卡片{card_id}")
    assert result.status == "need_mfa"
    assert result.data["level"] == permissions.RED

    # 验证MFA
    action_id = result.action_id
    mfa_code = repo.get_pending(action_id)["mfa_code"]
    result = verify_mfa(action_id, mfa_code)
    assert result.status == "ok"
    assert "已冻结" in result.reply


def test_card_unfreeze_yellow():
    """测试卡片解冻（黄色权限）"""
    # 申请、激活、冻结一张卡
    result = handle_message("u001", "申请新卡")
    confirm_action(result.action_id, approve=True)

    cards = repo.list_cards("u001")
    card_id = cards[0]["id"]

    result = handle_message("u001", f"激活卡片{card_id}")
    confirm_action(result.action_id, approve=True)

    result = handle_message("u001", f"冻结卡片{card_id}")
    mfa_code = repo.get_pending(result.action_id)["mfa_code"]
    verify_mfa(result.action_id, mfa_code)

    # 解冻卡片
    result = handle_message("u001", f"解冻卡片{card_id}")
    assert result.status == "need_confirm"
    assert result.data["level"] == permissions.YELLOW

    action_id = result.action_id
    result = confirm_action(action_id, approve=True)
    assert result.status == "ok"
    assert "已解冻" in result.reply


def test_card_limit_yellow():
    """测试修改卡片限额（黄色权限）"""
    # 申请并激活一张卡
    result = handle_message("u001", "申请新卡")
    confirm_action(result.action_id, approve=True)

    cards = repo.list_cards("u001")
    card_id = cards[0]["id"]

    result = handle_message("u001", f"激活卡片{card_id}")
    confirm_action(result.action_id, approve=True)

    # 修改限额
    result = handle_message("u001", f"修改卡片{card_id}日限额为10000")
    assert result.status == "need_confirm"
    assert result.data["level"] == permissions.YELLOW

    action_id = result.action_id
    result = confirm_action(action_id, approve=True)
    assert result.status == "ok"
    assert "限额" in result.reply


def test_card_deactivate_red():
    """测试卡片注销（红色权限，需要MFA）"""
    # 申请并激活一张卡
    result = handle_message("u001", "申请新卡")
    confirm_action(result.action_id, approve=True)

    cards = repo.list_cards("u001")
    card_id = cards[0]["id"]

    result = handle_message("u001", f"激活卡片{card_id}")
    confirm_action(result.action_id, approve=True)

    # 注销卡片
    result = handle_message("u001", f"注销卡片{card_id}")
    assert result.status == "need_mfa"
    assert result.data["level"] == permissions.RED

    # 验证MFA
    action_id = result.action_id
    mfa_code = repo.get_pending(action_id)["mfa_code"]
    result = verify_mfa(action_id, mfa_code)
    assert result.status == "ok"
    assert "已注销" in result.reply


def test_card_permission_levels():
    """验证卡片操作的权限级别"""
    # 查询 - 绿色
    level, _ = permissions.classify("card_query", {}, "u001")
    assert level == permissions.GREEN

    # 申请 - 黄色
    level, _ = permissions.classify("card_apply", {}, "u001")
    assert level == permissions.YELLOW

    # 激活 - 黄色
    level, _ = permissions.classify("card_activate", {"card_id": 1}, "u001")
    assert level == permissions.YELLOW

    # 冻结 - 红色
    level, _ = permissions.classify("card_freeze", {"card_id": 1}, "u001")
    assert level == permissions.RED

    # 解冻 - 黄色
    level, _ = permissions.classify("card_unfreeze", {"card_id": 1}, "u001")
    assert level == permissions.YELLOW

    # 限额 - 黄色
    level, _ = permissions.classify("card_limit", {"card_id": 1}, "u001")
    assert level == permissions.YELLOW

    # 注销 - 红色
    level, _ = permissions.classify("card_deactivate", {"card_id": 1}, "u001")
    assert level == permissions.RED
