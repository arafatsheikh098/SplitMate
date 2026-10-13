"""Tiny wrapper around Jinja's ``Environment`` for our templates.

A single global environment is created on first use.  Templates live in
``splitmate/templates`` and use the ``.html.j2`` suffix.
"""

from __future__ import annotations

import contextvars as _cv
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_BASE = Path(__file__).parent / "templates"

_env: Environment | None = None

# Stack-based current language set by the render() caller.
_current_lang: _cv.ContextVar[str] = _cv.ContextVar("current_lang", default="en")


def get_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(_BASE)),
            autoescape=select_autoescape(["html", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env


def render(template: str, context: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Render ``template`` (filename relative to ``templates/``).

    Top-level ``context`` keys plus keyword arguments are merged.  All
    templates get a ``t`` function and a ``lang`` key in the context
    unless the caller already provided them.
    """
    ctx: dict[str, Any] = {"t": _t_helper, **(context or {})}
    ctx.update(kwargs)
    lang = ctx.get("lang", "en")
    token = _current_lang.set(lang)
    try:
        return get_env().get_template(template).render(**ctx)
    finally:
        _current_lang.reset(token)


def _t_helper(key: str, **params: Any) -> str:
    from .i18n import t

    lang = _current_lang.get()
    return t(key, lang=lang, **params)


def reset_for_tests() -> None:
    global _env
    _env = None
