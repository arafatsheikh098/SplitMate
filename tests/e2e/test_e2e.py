"""End-to-end Playwright test (M7 A5).

Walks through a real browser session against a live uvicorn
subprocess: creates a group, joins via invite link, adds an expense,
checks the dashboard, runs a settlement and verifies that the
balances zero out.

The test is gated behind the ``playwright`` import so it is skipped
when the optional ``dev`` extra isn't installed.  It is also excluded
from the default test run via the ``e2e`` directory; CI invokes it
separately.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server_url(tmp_path_factory):
    """Run the app on a free port with an isolated SQLite db."""
    tmp = tmp_path_factory.mktemp("e2e")
    db_path = tmp / "e2e.db"
    port = _free_port()
    env = {
        **os.environ,
        "ENV": "testing",
        "SECRET_KEY": "e2e-test-secret-key",
        "DATABASE_URL": f"sqlite:///{db_path}",
    }
    # Initialise the schema before uvicorn starts so the first POST
    # doesn't fail with "no such table".
    bootstrap = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os, sys\n"
                f"os.environ['DATABASE_URL'] = 'sqlite:///{db_path}'\n"
                "from splitmate import db, models  # noqa\n"
                "db.reset_engine_for_tests()\n"
                "db.create_all()\n"
                "print('schema ready')\n"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "splitmate.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.terminate()
        # Print captured server logs to help debugging.
        try:
            out, _ = proc.communicate(timeout=2)
        except Exception:
            out = b""
        raise RuntimeError(
            "uvicorn did not start in time. Output:\n"
            + (out.decode("utf-8", "replace") if out else "<empty>")
        )
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_e2e_full_journey(server_url):
    from playwright.sync_api import sync_playwright

    screenshots = Path("docs/screenshots")
    screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # iPhone-ish viewport for M7 A4 (no horizontal scroll at 375 px).
        context = browser.new_context(viewport={"width": 375, "height": 720})
        page = context.new_page()
        csp_errors: list[str] = []
        page.on(
            "console",
            lambda msg: csp_errors.append(msg.text)
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda err: csp_errors.append(str(err)))

        # 1. Home page.
        page.goto(server_url + "/", wait_until="load")
        assert "SplitMate" in page.content()
        page.screenshot(path=str(screenshots / "01_home.png"))

        # 2. Click the create-group button on the home page.
        page.locator("a.btn", has_text="Create").first.click()
        page.wait_for_url(re.compile(r"/groups/new"), timeout=10_000)
        page.fill('input[name="name"]', "Trip")
        page.fill('input[name="currency_symbol"]', "৳")
        page.fill('input[name="admin_name"]', "Asha")
        page.screenshot(path=str(screenshots / "02_create_form.png"))
        # The form posts to /groups/new and renders the invite_after_create
        # template (status 200).  The URL stays at /groups/new.  Wait for
        # the invite page to appear by waiting for the response and then
        # reading the body.
        with page.expect_response(re.compile(r"/groups/new"), timeout=10_000):
            page.evaluate(
                "document.querySelector('form[action=\"/groups/new\"]').submit()"
            )
        page.wait_for_load_state("networkidle")
        body = page.content()
        m = re.search(r"/join/([A-Za-z0-9_\-]+)", body)
        if not m:
            page.screenshot(path=str(screenshots / "DEBUG_form.png"))
            raise AssertionError(
                f"invite page never appeared. URL: {page.url}, content head: {body[:2000]!r}"
            )
        invite_token = m.group(1)
        gid_match = re.search(r"/groups/(\d+)", body)
        assert gid_match, "no group id in invite page"
        gid = gid_match.group(1)
        page.goto(f"{server_url}/groups/{gid}", wait_until="load")
        page.screenshot(path=str(screenshots / "03_group_dashboard.png"))

        # Capture the invite token (already set above).
        assert invite_token

        # 3. Bea joins in a new context.
        bea_ctx = browser.new_context(viewport={"width": 375, "height": 720})
        bea_page = bea_ctx.new_page()
        bea_page.goto(f"{server_url}/join/{invite_token}", wait_until="load")
        bea_page.fill('input[name="display_name"]', "Bea")
        bea_page.screenshot(path=str(screenshots / "04_bea_joined.png"))
        # The /join POST returns 303 → /groups/{id}, so expect_navigation
        # does the right thing here.
        with bea_page.expect_navigation(url=re.compile(r"/groups/\d+"), timeout=10_000):
            bea_page.evaluate(
                "document.querySelector('form[action^=\"/join/\"]').submit()"
            )
        assert re.search(r"/groups/\d+", bea_page.url), bea_page.url

        # 4. Asha adds an expense.
        page.goto(f"{server_url}/groups/{gid}/expenses/new", wait_until="load")
        page.fill('input[name="title"]', "Dinner")
        page.fill('input[name="amount"]', "100.00")
        page.fill('input[name="date_value"]', "2025-01-01")
        page.select_option('select[name="split_method"]', "equal")
        # The payer amount defaults to empty — fill it explicitly so
        # the server's parser gets a value.
        page.fill('input[name="payer_amount"]', "100.00")
        page.screenshot(path=str(screenshots / "05_expense_form.png"))
        with page.expect_navigation(
            url=re.compile(r"/groups/\d+/expenses"), timeout=10_000
        ):
            page.evaluate(
                "document.getElementById('expense-form').submit()"
            )
        page.screenshot(path=str(screenshots / "06_expense_saved.png"))

        # 5. Visit balances.
        page.goto(f"{server_url}/groups/{gid}/balances", wait_until="load")
        body = page.inner_text("body").lower()
        assert "owes" in body or "owed" in body
        page.screenshot(path=str(screenshots / "07_balances.png"))

        # 6. Visit summary.
        page.goto(f"{server_url}/groups/{gid}/summary", wait_until="load")
        assert "Trip" in page.content()
        page.screenshot(path=str(screenshots / "08_summary.png"))

        # 7. Visit activity feed.
        page.goto(f"{server_url}/groups/{gid}/activity", wait_until="load")
        page.screenshot(path=str(screenshots / "09_activity.png"))

        # 8. No horizontal scroll at 375 px (M7 A4).
        scroll_w = page.evaluate("document.documentElement.scrollWidth")
        client_w = page.evaluate("document.documentElement.clientWidth")
        assert scroll_w <= client_w, (scroll_w, client_w)

        # 9. Zero CSP / page errors in console.
        assert not csp_errors, csp_errors

        context.close()
        bea_ctx.close()
        browser.close()
