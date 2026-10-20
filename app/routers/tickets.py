from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Ticket

router = APIRouter(tags=["tickets"])


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: str
    title: str
    description: str | None
    priority: str
    status: str
    source: str
    created_at: datetime


@router.get("/tickets")
def list_tickets(
    status: str | None = None,
    priority: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    query = select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
    if status:
        query = query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)

    tickets = db.scalars(query.limit(limit).offset(offset)).all()
    return [TicketOut.model_validate(ticket) for ticket in tickets]
