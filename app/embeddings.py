from functools import lru_cache

from fastembed import TextEmbedding

from app.config import settings


@lru_cache
def get_model() -> TextEmbedding:
    return TextEmbedding(model_name=settings.embedding_model)


def embed_documents(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in get_model().embed(texts)]


def embed_query(text: str) -> list[float]:
    # query_embed adds the query prefix that bge models expect.
    return next(iter(get_model().query_embed(text))).tolist()
