import logging
import secrets
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Ticket, WebhookEvent

logger = logging.getLogger(__name__)


class TicketArguments(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=5, max_length=120)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    description: str | None = Field(default=None, max_length=1000)


def create_agent_ticket(db: Session, raw_arguments: str) -> Ticket:
    """Validate the LLM's tool arguments and save the ticket. Raises ValueError if invalid."""
    try:
        arguments = TicketArguments.model_validate_json(raw_arguments)
    except ValidationError as e:
        raise ValueError(short_reason(e)) from e

    ticket = Ticket(
        ticket_id="T-" + secrets.token_hex(3).upper(),
        title=arguments.title,
        description=arguments.description,
        priority=arguments.priority,
        status="open",
        source="agent",
    )
    db.add(ticket)
    db.commit()
    return ticket


def short_reason(error: ValidationError) -> str:
    first = error.errors()[0]
    if first["type"] == "json_invalid":
        return "the tool arguments were not valid JSON"
    field = ".".join(str(part) for part in first["loc"])
    return f"{field}: {first['msg']}"


def process_event(event_id: str) -> None:
    # Runs after the response is sent, so it needs its own session.
    with SessionLocal() as db:
        event = db.get(WebhookEvent, event_id)
        if event is None:
            logger.error("Webhook event %s not found", event_id)
            return

        try:
            handle_event(db, event)
            event.status = "processed"
            event.processed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            logger.exception("Failed to process webhook event %s", event_id)
            db.rollback()
            event.status = "failed"
            db.commit()


def handle_event(db: Session, event: WebhookEvent) -> None:
    data = event.payload["data"]

    if event.type == "ticket.created":
        create_or_update_ticket(db, data)
    elif event.type == "ticket.updated":
        ticket = find_ticket(db, data["ticket_id"])
        if ticket is None:
            logger.info("Ticket %s not found for event %s", data["ticket_id"], event.event_id)
        else:
            ticket.title = data["title"]
            ticket.priority = data["priority"]
    else:
        logger.info("Ignored webhook event %s with unknown type %s", event.event_id, event.type)


def create_or_update_ticket(db: Session, data: dict) -> None:
    ticket = find_ticket(db, data["ticket_id"])
    if ticket is None:
        db.add(
            Ticket(
                ticket_id=data["ticket_id"],
                title=data["title"],
                priority=data["priority"],
                source="webhook",
            )
        )
    else:
        ticket.title = data["title"]
        ticket.priority = data["priority"]


def find_ticket(db: Session, ticket_id: str) -> Ticket | None:
    return db.scalars(select(Ticket).where(Ticket.ticket_id == ticket_id)).first()
