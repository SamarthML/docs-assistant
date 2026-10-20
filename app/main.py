import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import models  # noqa: F401  (registers the tables on Base)
from app.db import Base, enable_pgvector, engine
from app.routers import ask, documents, tickets, webhooks

logging.basicConfig(level=logging.INFO)

INDEX_HTML = Path(__file__).parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    enable_pgvector()
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="AI Docs Assistant",
    description="Answers questions from uploaded documents with citations, and manages support tickets.",
    lifespan=lifespan,
)
app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(webhooks.router)
app.include_router(tickets.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(INDEX_HTML)
