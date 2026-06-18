"""Iris AI Gateway - API 集成测试"""

import pytest
from fastapi.testclient import TestClient
from main import app


class FakeReadyDispatcher:
    """避免 /ready 测试触发真实上游网络探测。"""

    async def health_check(self):
        return {"openai": True}

    async def close(self):
        return None


@pytest.fixture
def client():
    """创建测试客户端（带认证头）"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """认证头"""
    return {"Authorization": "Bearer iris-key-1"}


class TestHealthEndpoints:
    """测试健康检查端点"""

    def test_root(self, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Iris AI Gateway"

    def test_health(self, client):
        """测试轻量健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert data["providers"] == {}

    def test_ready(self, client):
        """测试就绪检查"""
        client.app.state.dispatcher = FakeReadyDispatcher()

        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["providers"] == {"openai": True}


class TestOpenAIEndpoints:
    """测试 OpenAI 兼容端点"""

    def test_list_models(self, client, auth_headers):
        """测试模型列表"""
        response = client.get("/v1/models", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0


class TestAnthropicEndpoints:
    """测试 Anthropic 兼容端点"""

    def test_list_models(self, client, auth_headers):
        """测试模型列表"""
        response = client.get("/v1/models", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
