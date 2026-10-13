"""Translation helper.

Two dictionaries live next to this file: ``en.json`` and ``bn.json``.
A test in ``test_i18n.py`` fails if the two files diverge in keys.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import get_settings

_SUPPORTED = ("en", "bn")

_translations: dict[str, dict[str, str]] = {}
_loaded = False


def _load() -> None:
    global _loaded
    if _loaded:
        return
    base = Path(__file__).parent / "i18n"
    for lang in _SUPPORTED:
        with (base / f"{lang}.json").open(encoding="utf-8") as fh:
            _translations[lang] = json.load(fh)
    _loaded = True


def supported_languages() -> tuple[str, ...]:
    return _SUPPORTED


def reload_translations() -> None:
    """Force a reload (used in tests after editing the JSON files)."""
    global _loaded
    _loaded = False
    _translations.clear()
    _load()


def t(key: str, lang: str | None = None, **params: Any) -> str:
    """Return the translation for ``key`` in the given language.

    Falls back to English for missing keys.  Supports ``{name}``-style
    formatting via ``**params``.
    """
    _load()
    if lang is None:
        lang = get_settings().default_language
    if lang not in _SUPPORTED:
        lang = "en"
    template = _translations.get(lang, {}).get(key) or _translations["en"].get(key) or key
    if params:
        try:
            return template.format(**params)
        except (KeyError, IndexError):
            return template
    return template


__all__ = ["reload_translations", "supported_languages", "t"]
