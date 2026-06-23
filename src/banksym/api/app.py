"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from banksym import __version__
from banksym.api.architecture import get_architecture
from banksym.api.container import get_container
from banksym.api.routers import auth, banking, banks, oauth, settlement, simulation
from banksym.core.kernel.errors import (
    AccountNotFoundError,
    BankSymError,
    CustomerNotFoundError,
)

_UI_DIR = Path(__file__).resolve().parents[3] / "ui"

_NOT_FOUND_ERRORS = (AccountNotFoundError, CustomerNotFoundError)

_DESCRIPTION = """\
**BankSym** is a configurable, multi-tenant **test bank framework**. Each *bank* is an isolated
tenant with its own branding, customers, accounts, transaction history and pluggable capabilities
(transaction generators, settlement engines, localization, authentication and Open Banking
protocols).

### How the API is organised

* **banks** — create, inspect and delete bank tenants, and discover the capabilities available
  when building one.
* **banking** — operate a running tenant: manage customers and accounts, read transactions and
  generate realistic history.
* **auth** — register PSU online-banking credentials and manage login sessions.
* **oauth (redirect SCA)** — the bank-hosted OAuth2 redirect flow a TPP uses to obtain an access
  token without ever seeing the PSU's credentials.
* **xs2a (Berlin Group)** — the standardised Open Banking (PSD2/XS2A) surface: consents,
  authorisation (SCA), account information (AIS) and payment initiation (PIS).
* **settlement** — trigger a tenant's deferred settlement cycle.
* **meta** — service health and a machine-readable description of the wired architecture.

Most endpoints are scoped to a single tenant via the `bank_id` path parameter.
"""

_OPENAPI_TAGS = [
    {
        "name": "banks",
        "description": "Instantiate, inspect and delete bank tenants.",
    },
    {
        "name": "capabilities",
        "description": "Discover the pluggable capability implementations a bank can be built "
        "from.",
    },
    {
        "name": "banking",
        "description": "Core banking operations for a tenant: customers, accounts, transactions "
        "and history generation.",
    },
    {
        "name": "auth",
        "description": "PSU online-banking credentials and login sessions.",
    },
    {
        "name": "oauth (redirect SCA)",
        "description": "Bank-hosted OAuth2 redirect authorisation. The TPP redirects the PSU to "
        "the bank, which returns a one-time code that is exchanged for an access token.",
    },
    {
        "name": "xs2a (Berlin Group)",
        "description": "Berlin Group XS2A (PSD2) Open Banking surface: consents, SCA, account "
        "information (AIS) and payment initiation (PIS).",
    },
    {
        "name": "settlement",
        "description": "Run a tenant's deferred settlement cycle.",
    },
    {
        "name": "simulation",
        "description": "Control the server-side live transaction simulator and poll its feed.",
    },
    {
        "name": "meta",
        "description": "Service health and architecture introspection.",
    },
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="BankSym",
        version=__version__,
        summary="A configurable, multi-tenant test bank framework.",
        description=_DESCRIPTION,
        openapi_tags=_OPENAPI_TAGS,
        docs_url="/swagger",
    )
    app.include_router(banks.router)
    app.include_router(banking.router)
    app.include_router(auth.router)
    app.include_router(oauth.router)
    app.include_router(settlement.router)
    app.include_router(simulation.router)

    # Mount every registered protocol adapter (e.g. Berlin Group XS2A).
    container = get_container()
    for adapter in container.protocol_adapters():
        app.include_router(adapter.build_router())

    @app.on_event("shutdown")
    async def _stop_simulation() -> None:
        await get_container().simulation.stop()

    @app.exception_handler(BankSymError)
    async def _domain_error_handler(_: Request, exc: BankSymError) -> JSONResponse:
        status = 404 if isinstance(exc, _NOT_FOUND_ERRORS) else 400
        return JSONResponse(
            status_code=status, content={"code": exc.code, "message": str(exc)}
        )

    @app.get("/health", tags=["meta"], summary="Service health check")
    def health() -> dict[str, str]:
        """Return a simple liveness payload with the running BankSym version."""
        return {"status": "ok", "version": __version__}

    @app.get("/architecture", tags=["meta"], summary="Describe the wired architecture")
    def architecture() -> dict:
        """Return a machine-readable description of the capabilities and adapters wired in."""
        return get_architecture()

    @app.get("/", include_in_schema=False)
    def ui_root() -> FileResponse:
        return FileResponse(_UI_DIR / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon_svg() -> FileResponse:
        return FileResponse(_UI_DIR / "favicon.svg", media_type="image/svg+xml")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon_ico() -> FileResponse:
        # Browsers that request /favicon.ico by default get the SVG mark.
        return FileResponse(_UI_DIR / "favicon.svg", media_type="image/svg+xml")

    @app.get("/builder", include_in_schema=False)
    def ui_builder() -> FileResponse:
        return FileResponse(_UI_DIR / "builder.html")

    @app.get("/console", include_in_schema=False)
    def ui_console() -> FileResponse:
        return FileResponse(_UI_DIR / "console.html")

    @app.get("/psd2", include_in_schema=False)
    def ui_psd2() -> FileResponse:
        return FileResponse(_UI_DIR / "psd2.html")

    @app.get("/live", include_in_schema=False)
    def ui_live() -> FileResponse:
        return FileResponse(_UI_DIR / "live.html")

    @app.get("/psd2-callback", include_in_schema=False)
    def ui_psd2_callback() -> FileResponse:
        return FileResponse(_UI_DIR / "psd2-callback.html")

    @app.get("/docs", include_in_schema=False)
    def ui_docs() -> FileResponse:
        # A branded web view that embeds the interactive Swagger UI (served at /swagger).
        return FileResponse(_UI_DIR / "docs.html")

    @app.get("/banks/{bank_id}/oauth/authorize", include_in_schema=False)
    def ui_bank_login(bank_id: str) -> FileResponse:
        # The bank-hosted login page reads its parameters from the URL on the client side.
        return FileResponse(_UI_DIR / "bank-login.html")

    return app


app = create_app()
