"""
Shared pytest fixtures for email_outreach tests.

Builds a standalone FastAPI app carrying only email_outreach's router
(not the full app.main - importing that pulls in every other module,
including voice_interview, which requires local model files this repo
doesn't ship). Uses an in-memory SQLite database instead of Postgres so
these tests run anywhere, no external services required - the module's
models use only portable column types (String/Text/Boolean/DateTime/
Numeric/Integer), so this is a safe substitution for the real backend.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.deps import get_db
from app.modules.email_outreach.api import router as email_outreach_router
from app.modules.email_outreach import models  # noqa: F401 - registers tables on Base


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignores FK constraints by default - turn them on so
    # cascade/ordering bugs surface in tests the same way they would
    # against Postgres.
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app(db_session):
    test_app = FastAPI()
    test_app.include_router(email_outreach_router, prefix="/email")

    def _get_test_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_test_db
    return test_app


@pytest.fixture()
def client(app):
    return TestClient(app)
