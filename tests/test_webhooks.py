import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Ticket, WebhookEvent


def make_event(event_id: str = "evt_1") -> bytes:
    event = {
        "event_id": event_id,
        "type": "ticket.created",
        "data": {"ticket_id": "T-1", "title": "VPN not connecting", "priority": "high"},
    }
    return json.dumps(event).encode()


def sign(body: bytes, secret: str = "test-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post_event(client: TestClient, body: bytes, signature: str | None):
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Signature"] = signature
    return client.post("/webhooks/tickets", content=body, headers=headers)


def count_rows(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_webhook_rejects_invalid_signature(client: TestClient) -> None:
    body = make_event()

    response = post_event(client, body, sign(body, secret="wrong-secret"))

    assert response.status_code == 401
    assert count_rows(WebhookEvent) == 0


def test_webhook_rejects_missing_signature(client: TestClient) -> None:
    response = post_event(client, make_event(), signature=None)

    assert response.status_code == 401


def test_valid_webhook_creates_ticket(client: TestClient) -> None:
    body = make_event()

    response = post_event(client, body, sign(body))

    assert response.status_code == 202
    tickets = client.get("/tickets").json()
    assert len(tickets) == 1
    assert tickets[0]["ticket_id"] == "T-1"
    assert tickets[0]["source"] == "webhook"


def test_duplicate_event_is_processed_once(client: TestClient) -> None:
    body = make_event()

    post_event(client, body, sign(body))
    second = post_event(client, body, sign(body))

    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert count_rows(Ticket) == 1
    assert count_rows(WebhookEvent) == 1
