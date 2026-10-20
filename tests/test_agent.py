import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.llm import ToolCall
from app.models import Ticket


def ticket_call(**arguments) -> ToolCall:
    return ToolCall(name="create_ticket", arguments=json.dumps(arguments))


def test_agent_creates_ticket(client: TestClient, fake_llm) -> None:
    fake_llm.tool_call = ticket_call(title="VPN keeps disconnecting", priority="urgent")

    response = client.post("/ask", json={"question": "Please raise a ticket: VPN keeps disconnecting"})

    body = response.json()
    assert body["found"] is True
    assert body["ticket"]["title"] == "VPN keeps disconnecting"
    assert body["ticket"]["priority"] == "urgent"
    assert body["ticket"]["source"] == "agent"
    assert body["ticket"]["ticket_id"].startswith("T-")

    tickets = client.get("/tickets").json()
    assert [ticket["ticket_id"] for ticket in tickets] == [body["ticket"]["ticket_id"]]


def test_agent_rejects_invalid_tool_input(client: TestClient, fake_llm) -> None:
    fake_llm.tool_call = ticket_call(title="VPN keeps disconnecting", priority="super-high")

    response = client.post("/ask", json={"question": "Please raise a ticket: VPN keeps disconnecting"})

    body = response.json()
    assert body["found"] is False
    assert body["ticket"] is None
    assert body["answer"].startswith("I couldn't create the ticket:")
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Ticket)) == 0
