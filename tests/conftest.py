import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_DATABASE = "docs_assistant_test"


def create_test_database() -> str:
    """Create the test database next to the one in DATABASE_URL and return its URL."""
    main_url = make_url(os.environ["DATABASE_URL"])
    admin_engine = create_engine(main_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DATABASE}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    admin_engine.dispose()
    return main_url.set(database=TEST_DATABASE).render_as_string(hide_password=False)


# These must be set before the app is imported, because settings are read at import time.
os.environ["DATABASE_URL"] = create_test_database()
os.environ["WEBHOOK_SECRET"] = "test-secret"
os.environ["GROQ_API_KEY"] = "dummy"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, enable_pgvector, engine  # noqa: E402
from app.llm import ToolCall  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> None:
    enable_pgvector()
    Base.metadata.create_all(engine)


@pytest.fixture(autouse=True)
def clean_tables() -> None:
    table_names = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


class FakeLLM:
    def __init__(self) -> None:
        self.answer = "NOT_FOUND"
        self.tool_call: ToolCall | None = None
        self.calls = 0

    def generate_answer(self, question: str, chunks: list) -> str:
        self.calls += 1
        return self.answer

    def generate_answer_with_tools(self, question: str, chunks: list) -> str | ToolCall:
        self.calls += 1
        return self.tool_call or self.answer


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """Replace the Groq calls in every test so tests never hit the real API."""
    fake = FakeLLM()
    # Patched where they are used, because ask.py imports the functions directly.
    monkeypatch.setattr("app.routers.ask.generate_answer", fake.generate_answer)
    monkeypatch.setattr("app.routers.ask.generate_answer_with_tools", fake.generate_answer_with_tools)
    return fake


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
