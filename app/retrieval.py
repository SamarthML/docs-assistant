from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import embed_query
from app.models import Chunk


def search(db: Session, question: str, top_k: int) -> list[tuple[Chunk, float]]:
    """Return the top_k closest chunks with their cosine similarity."""
    query_vector = embed_query(question)
    distance = Chunk.embedding.cosine_distance(query_vector)

    rows = db.execute(select(Chunk, distance).order_by(distance).limit(top_k)).all()
    return [(chunk, 1 - dist) for chunk, dist in rows]
