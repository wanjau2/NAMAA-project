"""Real API fixtures; no LocalSyntheticPolicy and no mock HTTP responses."""
import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from namaa_ai.backend import BackendApiClient


@pytest.fixture
def api_stack(request):
    if request.config.getoption("--require-backend"):
        missing = [name for name in ("fastapi", "sqlalchemy", "pydantic_settings")
                   if importlib.util.find_spec(name) is None]
        if missing:
            pytest.fail("Install ai/requirements-integration.txt; missing " + ", ".join(missing), pytrace=False)
    pytest.importorskip("fastapi", reason="install requirements-integration.txt")
    pytest.importorskip("sqlalchemy", reason="install requirements-integration.txt")
    pytest.importorskip("pydantic_settings", reason="install requirements-integration.txt")
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db import Base, get_db
    from app.main import create_app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)

    def database():
        with session_factory() as db:
            yield db

    app = create_app(start_workers=False)
    app.dependency_overrides[get_db] = database
    transport = httpx.ASGITransport(app=app)
    headers = {"X-Namaa-Session": f"guest-ai-test-{uuid4().hex[:12]}",
               "X-Namaa-Role": "clinical_reviewer"}
    backend = BackendApiClient("http://testserver", headers, transport=transport)
    yield SimpleNamespace(backend=backend, transport=transport, headers=headers, db=session_factory)
    app.dependency_overrides.clear()
    engine.dispose()
