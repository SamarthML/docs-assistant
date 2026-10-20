"""Measure how well search() finds the right page for a set of known questions.

Run inside the api container:

    docker compose exec api python -m scripts.evaluate
"""

import json
from pathlib import Path

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Document
from app.retrieval import search

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = ROOT / "eval" / "questions.json"
SAMPLE_DOCS = ROOT / "sample_docs"
API_URL = "http://localhost:8000"


def upload_missing_documents() -> None:
    with SessionLocal() as db:
        existing = set(db.scalars(select(Document.file_name)))

    for path in sorted(SAMPLE_DOCS.iterdir()):
        if path.name in existing:
            continue
        with path.open("rb") as f:
            response = httpx.post(f"{API_URL}/documents", files={"file": (path.name, f)}, timeout=60)
        response.raise_for_status()
        print(f"Uploaded {path.name}: {response.json()['chunks']} chunks")


def find_rank(results: list, file_name: str, page: int) -> int | None:
    """Return the 1-based rank of the expected file and page, or None if missing."""
    for rank, (chunk, _) in enumerate(results, start=1):
        if chunk.file_name == file_name and chunk.page_number == page:
            return rank
    return None


def shorten(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 3] + "..."


def main() -> None:
    upload_missing_documents()
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    top_k = settings.top_k

    print(f"\n{'Question':<50} {'Expected':<26} {'Top result':<26} {'Rank':>4} {'Sim':>6}")
    print("-" * 116)

    ranks = []
    misses = []
    with SessionLocal() as db:
        for item in questions:
            results = search(db, item["question"], top_k)
            rank = find_rank(results, item["file_name"], item["page"])
            ranks.append(rank)

            expected = f"{item['file_name']} p{item['page']}"
            top_chunk, _ = results[0]
            top_result = f"{top_chunk.file_name} p{top_chunk.page_number}"
            # Similarity of the expected page, or of the top result on a miss.
            similarity = results[rank - 1][1] if rank else results[0][1]
            rank_text = str(rank) if rank else "-"
            print(f"{shorten(item['question'], 50):<50} {expected:<26} {top_result:<26} {rank_text:>4} {similarity:>6.3f}")

            if rank is None:
                misses.append(item)

    total = len(questions)
    hit_at_1 = sum(1 for rank in ranks if rank == 1) / total
    hit_at_k = sum(1 for rank in ranks if rank is not None) / total
    mrr = sum(1 / rank for rank in ranks if rank is not None) / total

    print(f"\nQuestions: {total}")
    print(f"Hit@1:     {hit_at_1:.2f}")
    print(f"Hit@{top_k}:     {hit_at_k:.2f}")
    print(f"MRR:       {mrr:.3f}")

    if misses:
        print("\nMisses:")
        for item in misses:
            print(f"  - {item['question']} (expected {item['file_name']} p{item['page']})")
    else:
        print("\nMisses: none")


if __name__ == "__main__":
    main()
