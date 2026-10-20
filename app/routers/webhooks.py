import hashlib
import hmac
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import WebhookEvent
from app.services.tickets import process_event

router = APIRouter()


class TicketData(BaseModel):
    ticket_id: str
    title: str
    priority: Literal["low", "medium", "high", "urgent"]


class TicketEvent(BaseModel):
    event_id: str
    type: str
    data: TicketData


def is_valid_signature(body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    signature = signature.removeprefix("sha256=")
    expected = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/tickets", status_code=202)
async def receive_ticket_webhook(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    # The signature covers the exact bytes, so read them before any JSON parsing.
    body = await request.body()
    if not is_valid_signature(body, request.headers.get("X-Signature")):
        raise HTTPException(401, "Missing or invalid signature")

    try:
        event = TicketEvent.model_validate_json(body)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from e

    # The event_id primary key makes this a no-op for duplicates. Only a failed
    # event is reset to "received" so it can be processed again.
    statement = insert(WebhookEvent).values(
        event_id=event.event_id, type=event.type, payload=event.model_dump()
    )
    statement = statement.on_conflict_do_update(
        index_elements=["event_id"],
        set_={"status": "received", "payload": statement.excluded.payload},
        where=WebhookEvent.status == "failed",
    ).returning(WebhookEvent.event_id)
    inserted = db.execute(statement).scalar_one_or_none()
    db.commit()

    if inserted is None:
        response.status_code = 200
        return {"status": "duplicate", "event_id": event.event_id}

    background_tasks.add_task(process_event, event.event_id)
    return {"status": "accepted", "event_id": event.event_id}
