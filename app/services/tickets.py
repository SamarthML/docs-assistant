import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Ticket, WebhookEvent

logger = logging.getLogger(__name__)


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
