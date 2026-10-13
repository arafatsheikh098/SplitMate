"""Health endpoint smoke test."""

from __future__ import annotations


def test_health_returns_ok(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_home_renders(client) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "SplitMate" in r.text


def test_lang_toggle(client) -> None:
    r = client.post("/lang/bn", follow_redirects=True)
    assert r.status_code == 200
    assert client.cookies.get("lang") == "bn"
    assert "স্প্লিটমেট" in r.text
