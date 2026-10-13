"""FastAPI application factory and core routes.

The factory is small on purpose: a single ``/health`` endpoint, a language
toggle, the base Jinja template, and static file mounting.  Per-milestone
routes are registered as their own routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeSerializer
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .db import get_engine
from .i18n import supported_languages, t
from .templates import render

_BASE_DIR = Path(__file__).parent
_STATIC_DIR = _BASE_DIR / "static"


def _lang_serializer(secret: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret, salt="lang")


def _read_lang(request: Request) -> str:
    cookie = request.cookies.get("lang")
    if cookie in supported_languages():
        return cookie
    return get_settings().default_language


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Ensure metadata is bound.  Migrations are run via alembic; this
    # only initialises the engine.
    get_engine()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=_lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=settings.session_cookie_secure,
    )

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": t("health.ok")}

    @app.get("/", include_in_schema=False)
    async def home(request: Request) -> HTMLResponse:
        return HTMLResponse(
            render(
                "base.html.j2",
                {
                    "lang": _read_lang(request),
                    "request": request,
                },
                block_title=t("app.title"),
                content=(
                    f"<section class='card'>"
                    f"<h1>{t('app.title')}</h1>"
                    f"<p>{t('app.tagline')}</p>"
                    f"<p><a class='btn' href='/groups/new'>{t('nav.create_group')}</a></p>"
                    f"</section>"
                ),
            )
        )

    @app.post("/lang/{lang}")
    async def set_lang(lang: str) -> RedirectResponse:
        if lang not in supported_languages():
            lang = get_settings().default_language
        response = RedirectResponse("/", status_code=303)
        response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
        return response

    @app.exception_handler(404)
    async def _not_found(request: Request, _exc) -> HTMLResponse:
        return HTMLResponse(
            render(
                "base.html.j2",
                {"lang": _read_lang(request), "request": request},
                block_title=t("error.404.title"),
                content=(
                    f"<section class='card'>"
                    f"<h1>{t('error.404.title')}</h1>"
                    f"<p><a href='/'>{t('error.back_home')}</a></p>"
                    f"</section>"
                ),
            ),
            status_code=404,
        )

    @app.exception_handler(500)
    async def _server_error(request: Request, _exc) -> HTMLResponse:
        return HTMLResponse(
            render(
                "base.html.j2",
                {"lang": _read_lang(request), "request": request},
                block_title=t("error.500.title"),
                content=(
                    f"<section class='card'>"
                    f"<h1>{t('error.500.title')}</h1>"
                    f"<p><a href='/'>{t('error.back_home')}</a></p>"
                    f"</section>"
                ),
            ),
            status_code=500,
        )

    # Register per-milestone routers.  Imports are deferred to keep the M1
    # surface tiny; later milestones add their own ``app.include_router`` calls.
    _register_milestone_routers(app)

    return app


def _register_milestone_routers(app: FastAPI) -> None:
    """Wire up routers added in later milestones.

    Each is imported lazily so an M1 build still starts cleanly.  We use a
    try/except so missing modules (because a milestone hasn't landed yet)
    don't crash the app — the milestone's commit will add the import.

    Real routers are registered **after** the stub routers so that
    when a milestone lands the real route wins; the stub's identical
    path is shadowed.
    """
    try:
        from .web import groups as _groups

        app.include_router(_groups.router)
    except Exception:  # pragma: no cover - milestone boundary
        pass
    try:
        from .web import _stubs as _stubs

        # Note: the expenses / balances / settlements stubs are
        # intentionally NOT registered because their real routers
        # exist.  Mounting both would let the stub's identical path
        # win.
        app.include_router(_stubs.activity_router)
        app.include_router(_stubs.share_router)
    except Exception:  # pragma: no cover
        pass
    try:
        from .web import expenses as _expenses

        # Replace stub with real router when milestone lands.
        app.include_router(_expenses.router)
    except Exception:  # pragma: no cover
        pass
    try:
        from .web import balances as _balances

        app.include_router(_balances.router)
    except Exception:  # pragma: no cover
        pass
    try:
        from .web import settlements as _settlements

        app.include_router(_settlements.router)
    except Exception:  # pragma: no cover
        pass
    try:
        from .web import activity as _activity

        app.include_router(_activity.router)
    except Exception:  # pragma: no cover
        pass
    try:
        from .web import share as _share

        app.include_router(_share.router)
    except Exception:  # pragma: no cover
        pass


# For ``uvicorn splitmate.main:app`` we expose ``app`` as a callable that
# defers to ``create_app()``.  This lets the process import this module
# without instantiating the engine, so tests can swap ``DATABASE_URL``
# before any database connection is made.
app = create_app


def main() -> None:  # pragma: no cover
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "splitmate.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
