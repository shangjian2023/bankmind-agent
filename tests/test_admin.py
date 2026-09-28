"""后台管理系统测试"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.data import database


@pytest.fixture
def client():
    """创建测试客户端"""
    database.reset_and_seed()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token(client):
    """获取管理员token"""
    response = client.post("/admin/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200
    return response.json()["token"]


def test_admin_login(client):
    """测试管理员登录"""
    response = client.post("/admin/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["role"] == "super_admin"


def test_admin_login_wrong_password(client):
    """测试错误密码登录"""
    response = client.post("/admin/auth/login", json={
        "username": "admin",
        "password": "wrong"
    })
    assert response.status_code == 401


def test_get_current_user(client, admin_token):
    """测试获取当前用户信息"""
    response = client.get(
        "/admin/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "admin"
    assert data["role"] == "super_admin"


def test_list_users(client, admin_token):
    """测试获取用户列表"""
    response = client.get(
        "/admin/users?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data
    assert len(data["users"]) > 0


def test_list_api_keys(client, admin_token):
    """测试获取API Key列表"""
    response = client.get(
        "/admin/api-keys",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert "total" in data


def test_create_api_key(client, admin_token):
    """测试创建API Key"""
    response = client.post(
        "/admin/api-keys",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "provider": "openai",
            "key_name": "test-key",
            "api_key": "sk-test123456789",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-4",
            "rate_limit": 60,
            "daily_limit": 1000
        }
    )
    if response.status_code != 201:
        print(f"Error: {response.json()}")
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "openai"
    assert data["key_name"] == "test-key"
    assert "api_key_masked" in data


def test_list_announcements(client, admin_token):
    """测试获取公告列表"""
    response = client.get(
        "/admin/announcements",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "announcements" in data
    assert "total" in data


def test_create_announcement(client, admin_token):
    """测试创建公告"""
    response = client.post(
        "/admin/announcements",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "测试公告",
            "content": "这是一条测试公告",
            "type": "info",
            "priority": 0
        }
    )
    if response.status_code != 201:
        print(f"Error response: {response.json()}")
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "测试公告"
    assert data["status"] == "draft"


def test_list_configs(client, admin_token):
    """测试获取系统配置"""
    response = client.get(
        "/admin/config",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "configs" in data
    assert "total" in data


def test_update_config(client, admin_token):
    """测试更新系统配置"""
    # 先获取配置
    response = client.get(
        "/admin/config",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    configs = response.json()["configs"]

    if len(configs) > 0:
        config_key = configs[0]["config_key"]
        new_value = "test_value"

        response = client.put(
            f"/admin/config/{config_key}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"config_value": new_value}
        )
        assert response.status_code == 200


def test_list_intents(client, admin_token):
    """测试获取意图列表"""
    response = client.get(
        "/admin/intents",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "intents" in data
    assert "total" in data


def test_list_logs(client, admin_token):
    """测试获取操作日志"""
    response = client.get(
        "/admin/logs?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert "total" in data


def test_unauthorized_access(client):
    """测试未授权访问"""
    response = client.get("/admin/users")
    assert response.status_code == 401


def test_logout(client, admin_token):
    """测试退出登录"""
    response = client.post(
        "/admin/auth/logout",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # 验证token失效
    response = client.get(
        "/admin/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 401
