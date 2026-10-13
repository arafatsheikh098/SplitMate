"""Static-asset size guard: split_form.js must be tiny and total page
JavaScript (excluding vendored HTMX) must stay well under 100 KB.
"""

from __future__ import annotations

import pathlib

JS_DIR = pathlib.Path(__file__).resolve().parents[1] / "splitmate" / "static" / "js"
VENDOR_DIR = pathlib.Path(__file__).resolve().parents[1] / "splitmate" / "static" / "vendor"
MAX_OWN_JS_BYTES = 100 * 1024  # 100 KB


def test_split_form_js_exists_and_is_small() -> None:
    p = JS_DIR / "split_form.js"
    assert p.exists(), f"{p} missing"
    assert p.stat().st_size < 10_000, (
        f"split_form.js is {p.stat().st_size} bytes — should be < 10 KB"
    )


def test_total_own_js_under_100_kb() -> None:
    total = 0
    for p in JS_DIR.glob("*.js"):
        total += p.stat().st_size
    assert total < MAX_OWN_JS_BYTES, (
        f"Total non-vendor JS is {total} bytes, limit {MAX_OWN_JS_BYTES}"
    )


def test_no_inline_javascript_in_templates() -> None:
    """CSP says no inline scripts.  Templates must not contain ``<script>``
    blocks that aren't ``src`` references.
    """
    template_dir = pathlib.Path(__file__).resolve().parents[1] / "splitmate" / "templates"
    for tpl in template_dir.rglob("*.j2"):
        text = tpl.read_text(encoding="utf-8")
        # Allow ``<script type="module" src="..."></script>`` only.
        import re

        for m in re.finditer(r"<script[^>]*>", text):
            tag = m.group(0)
            if "src=" not in tag:
                raise AssertionError(
                    f"{tpl.relative_to(template_dir.parent)} has inline <script>: {tag}"
                )
