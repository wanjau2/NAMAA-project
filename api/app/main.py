from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.db import init_db
from app.errors import AppError, app_error_handler
from app.routers import analytics, cases, demo, extractions, health, meta, ops, patients
from app.workers import runtime


def create_app(*, start_workers: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        init_db()
        if start_workers:
            await runtime.start()
        try:
            yield
        finally:
            if start_workers:
                await runtime.stop()

    app = FastAPI(
        title="Namaa Demo API",
        description=(
            "Synthetic precision-prevention workflow API. "
            "NOT FOR CLINICAL USE. No real patient data. "
            "Extraction progress via SSE; FHIR dual-store via transactional outbox (D004)."
        ),
        version=__version__,
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)

    app.include_router(health.router)
    app.include_router(demo.router)
    app.include_router(cases.router)
    app.include_router(patients.router)
    app.include_router(analytics.router)
    app.include_router(meta.router)
    app.include_router(extractions.router)
    app.include_router(ops.router)
    return app


app = create_app()
