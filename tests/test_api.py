"""Iris AI Gateway - API 集成测试"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """创建测试客户端（带认证头）"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers():
    """认证头"""
    return {"Authorization": "Bearer iris-test-key"}


class TestHealthEndpoints:
    """测试健康检查端点"""

    def test_root(self, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Iris AI Gateway"

    def test_health(self, client):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


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
