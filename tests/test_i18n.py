"""i18n helper contract: every key in en.json exists in bn.json."""

from __future__ import annotations

import json
from pathlib import Path

from splitmate.i18n import reload_translations, supported_languages, t


def _load(name: str) -> dict[str, str]:
    return json.loads((Path(__file__).resolve().parent.parent / "splitmate" / "i18n" / name).read_text(encoding="utf-8"))


def test_en_and_bn_have_same_keys() -> None:
    en = _load("en.json")
    bn = _load("bn.json")
    assert set(en.keys()) == set(bn.keys()), (
        "en and bn dictionaries must have identical keys",
        set(en.keys()) ^ set(bn.keys()),
    )


def test_supported_languages() -> None:
    assert supported_languages() == ("en", "bn")


def test_t_returns_translation() -> None:
    assert t("app.title", lang="en") == "SplitMate"
    assert t("app.title", lang="bn") == "স্প্লিটমেট"


def test_t_falls_back_to_english() -> None:
    # Unknown language falls back to English.
    assert t("app.title", lang="xx") == "SplitMate"


def test_t_formats_params() -> None:
    out = t("balance.owes", lang="en", name="Asha", amount="৳10.00")
    assert "Asha" in out and "10.00" in out


def test_t_returns_key_when_missing() -> None:
    assert t("definitely.not.a key") == "definitely.not.a key"


def test_reload_translations() -> None:
    reload_translations()
    assert t("app.title", lang="en") == "SplitMate"
