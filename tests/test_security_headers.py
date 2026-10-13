"""Security headers tests (M7 A3)."""

from __future__ import annotations

import re


def test_security_headers_present_on_404(client) -> None:
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert "content-security-policy" in resp.headers


def test_security_headers_present_on_dashboard(client) -> None:
    r = client.post(
        "/groups/new",
        data={"name": "Trip", "currency_symbol": "৳", "admin_name": "Asha"},
    )
    g_id = int(re.search(r"/groups/(\d+)", r.text).group(1))
    resp = client.get(f"/groups/{g_id}", follow_redirects=False)
    assert resp.status_code == 200, resp.text
    csp = resp.headers.get("content-security-policy")
    assert csp is not None and "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    # script-src is locked to 'self'; styles may use 'unsafe-inline' for HTMX.
    assert "script-src 'self'" in csp
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "no-referrer"


def test_csp_blocks_inline_scripts(client) -> None:
    """The CSP must not allow inline scripts (no 'unsafe-inline' for scripts)."""
    resp = client.get("/")
    csp = resp.headers.get("content-security-policy", "")
    # The script-src directive must not include 'unsafe-inline'.
    script_src = ""
    for part in csp.split(";"):
        if part.strip().startswith("script-src"):
            script_src = part
            break
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in script_src
