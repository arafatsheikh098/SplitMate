"""Share / summary tests (M7 A1)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient


def _create_and_login(client: TestClient) -> tuple[int, str]:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    token = re.search(r"/join/([A-Za-z0-9_\-]+)", r.text).group(1)
    client.post(f"/join/{token}", data={"display_name": "Bea"})
    return g_id, token


def test_summary_page_renders(client: TestClient) -> None:
    g_id, _ = _create_and_login(client)
    r = client.get(f"/groups/{g_id}/summary")
    assert r.status_code == 200
    assert "Trip" in r.text


def test_summary_text_endpoint(client: TestClient) -> None:
    g_id, _ = _create_and_login(client)
    r = client.get(f"/groups/{g_id}/summary.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert "Trip" in body
    assert "Asha" in body
    assert "Bea" in body


def test_summary_in_bangla(client: TestClient) -> None:
    g_id, _ = _create_and_login(client)
    client.cookies.set("lang", "bn")
    r = client.get(f"/groups/{g_id}/summary")
    assert r.status_code == 200
    # Bangla header keyword from translations.
    assert "হিসাব" in r.text or "কার্যকলাপ" in r.text or "খরচসমূহ" in r.text


def test_summary_golden_en(client: TestClient) -> None:
    """The English summary text must match the golden file (M7 A1)."""
    from pathlib import Path

    g_id, _ = _create_and_login(client)
    # Switch back to English in case a previous test changed the cookie.
    client.cookies.set("lang", "en")
    r = client.get(f"/groups/{g_id}/summary.txt")
    body = r.text
    golden = Path(__file__).parent / "golden" / "summary_en.txt"
    assert golden.exists(), f"missing golden file: {golden}"
    assert body.strip() == golden.read_text(encoding="utf-8").strip()


def test_summary_golden_bn(client: TestClient) -> None:
    """The Bangla summary text must match the golden file (M7 A1)."""
    from pathlib import Path

    g_id, _ = _create_and_login(client)
    client.cookies.set("lang", "bn")
    r = client.get(f"/groups/{g_id}/summary.txt")
    body = r.text
    golden = Path(__file__).parent / "golden" / "summary_bn.txt"
    assert golden.exists(), f"missing golden file: {golden}"
    assert body.strip() == golden.read_text(encoding="utf-8").strip()
