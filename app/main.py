from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import enable_pgvector


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    enable_pgvector()
    yield


app = FastAPI(title="docs-assistant", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
