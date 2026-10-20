from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers the tables on Base)
from app.db import Base, enable_pgvector, engine
from app.routers import documents


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    enable_pgvector()
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="docs-assistant", lifespan=lifespan)
app.include_router(documents.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
