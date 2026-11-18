from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.db import init_db
from app.errors import AppError, app_error_handler
from app.routers import analytics, cases, demo, health, meta, patients


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Namaa Demo API",
        description=(
            "Synthetic precision-prevention workflow API. "
            "NOT FOR CLINICAL USE. No real patient data."
        ),
        version=__version__,
        lifespan=lifespan,
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
    return app


app = create_app()