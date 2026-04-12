"""Tests for main.py: FastAPI clinic chatbot with LangChain memory."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic tests without calling OpenAI."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import main as main_module

    main_module._chain_with_history = None


def test_get_home_returns_html(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"].lower()
    html_body = resp.text
    assert html_body.strip()
    assert "clínica" in html_body.lower() or "esterilización" in html_body.lower()


def test_post_ask_bot_urlencoded_ok(client: TestClient) -> None:
    resp = client.post(
        "/ask_bot",
        content=b"msg=hello&session_id=s1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "s1"
    assert "msg" in data
    assert "OPENAI_API_KEY" in data["msg"]


def test_post_ask_bot_missing_msg(client: TestClient) -> None:
    resp = client.post(
        "/ask_bot",
        content=b"session_id=s1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 422


def test_post_ask_bot_missing_session_id(client: TestClient) -> None:
    resp = client.post(
        "/ask_bot",
        content=b"msg=hello",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 422


def test_post_ask_bot_whitespace_msg(client: TestClient) -> None:
    resp = client.post(
        "/ask_bot",
        content=b"msg=+++&session_id=s1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 422


def test_post_ask_bot_empty_body(client: TestClient) -> None:
    resp = client.post(
        "/ask_bot",
        content=b"",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 422


def test_post_ask_bot_json_unsupported(client: TestClient) -> None:
    resp = client.post(
        "/ask_bot",
        json={"msg": "hello", "session_id": "s1"},
    )
    assert resp.status_code == 415


def test_openapi_json_contains_paths(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    openapi = resp.json()
    paths = openapi.get("paths", {})
    assert "/" in paths
    assert "/ask_bot" in paths
    get_home = paths["/"].get("get", {})
    assert get_home.get("summary") == "Home"
    post_ask = paths["/ask_bot"].get("post", {})
    assert post_ask.get("summary") == "Ask Bot"
