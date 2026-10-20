from fastapi import APIRouter, Depends, HTTPException
from groq import APIError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.llm import NOT_FOUND, extract_citations, generate_answer
from app.retrieval import search

NOT_FOUND_ANSWER = "I couldn't find the answer in the uploaded documents."

router = APIRouter()


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=3, max_length=500)


class Source(BaseModel):
    file_name: str
    page: int
    similarity: float


class AskResponse(BaseModel):
    answer: str
    found: bool
    sources: list[Source]


@router.post("/ask")
def ask(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    results = search(db, request.question, settings.top_k)
    relevant = [(chunk, score) for chunk, score in results if score >= settings.min_similarity]
    if not relevant:
        return AskResponse(answer=NOT_FOUND_ANSWER, found=False, sources=[])

    chunks = [chunk for chunk, _ in relevant]
    try:
        answer = generate_answer(request.question, chunks)
    except APIError as e:
        raise HTTPException(502, f"The answer service (Groq) failed: {e}") from e

    if NOT_FOUND in answer:
        return AskResponse(answer=NOT_FOUND_ANSWER, found=False, sources=[])

    sources = []
    seen = set()
    for number in extract_citations(answer, len(chunks)):
        chunk, score = relevant[number - 1]
        key = (chunk.file_name, chunk.page_number)
        if key in seen:
            continue
        seen.add(key)
        sources.append(Source(file_name=chunk.file_name, page=chunk.page_number, similarity=round(score, 3)))

    return AskResponse(answer=answer, found=True, sources=sources)
