import re

from fastapi import APIRouter, Depends, HTTPException
from groq import APIError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.llm import NOT_FOUND, ToolCall, extract_citations, generate_answer, generate_answer_with_tools
from app.models import Chunk
from app.retrieval import search
from app.routers.tickets import TicketOut
from app.services.tickets import create_agent_ticket

NOT_FOUND_ANSWER = "I couldn't find the answer in the uploaded documents."

router = APIRouter(tags=["ask"])


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
    ticket: TicketOut | None = None


@router.post("/ask")
def ask(request: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    results = search(db, request.question, settings.top_k)
    relevant = [(chunk, score) for chunk, score in results if score >= settings.min_similarity]

    if is_ticket_request(request.question):
        return ask_with_ticket_tool(db, request.question, relevant)

    if not relevant:
        return not_found()

    chunks = [chunk for chunk, _ in relevant]
    try:
        answer = generate_answer(request.question, chunks)
    except APIError as e:
        raise groq_failed(e) from e

    return answer_response(answer, relevant)


def is_ticket_request(question: str) -> bool:
    return re.search(r"\bticket", question, re.IGNORECASE) is not None


def ask_with_ticket_tool(db: Session, question: str, relevant: list[tuple[Chunk, float]]) -> AskResponse:
    # The LLM is called even without relevant chunks, because creating a ticket needs no context.
    chunks = [chunk for chunk, _ in relevant]
    try:
        result = generate_answer_with_tools(question, chunks)
    except APIError as e:
        raise groq_failed(e) from e

    if not isinstance(result, ToolCall):
        return answer_response(result, relevant)

    if result.name != "create_ticket":
        return AskResponse(answer=f"I couldn't create the ticket: unknown tool {result.name}", found=False, sources=[])

    try:
        ticket = create_agent_ticket(db, result.arguments)
    except ValueError as e:
        return AskResponse(answer=f"I couldn't create the ticket: {e}", found=False, sources=[])

    return AskResponse(
        answer=f"Created ticket {ticket.ticket_id}: {ticket.title} (priority {ticket.priority}).",
        found=True,
        sources=[],
        ticket=TicketOut.model_validate(ticket),
    )


def answer_response(answer: str, relevant: list[tuple[Chunk, float]]) -> AskResponse:
    if NOT_FOUND in answer or not relevant:
        return not_found()

    cited = extract_citations(answer, len(relevant))
    # If the model cited nothing, fall back to every chunk it was given.
    if not cited:
        cited = list(range(1, len(relevant) + 1))

    sources = []
    seen = set()
    for number in cited:
        chunk, score = relevant[number - 1]
        key = (chunk.file_name, chunk.page_number)
        if key in seen:
            continue
        seen.add(key)
        sources.append(Source(file_name=chunk.file_name, page=chunk.page_number, similarity=round(score, 3)))

    return AskResponse(answer=answer, found=True, sources=sources)


def not_found() -> AskResponse:
    return AskResponse(answer=NOT_FOUND_ANSWER, found=False, sources=[])


def groq_failed(error: APIError) -> HTTPException:
    return HTTPException(502, f"The answer service (Groq) failed: {error}")
