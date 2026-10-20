"""Send a signed ticket webhook to the API.

Uses only the standard library, so it runs without installing anything:

    python scripts/send_webhook.py --event-id evt_1 --ticket-id T-100 --title "Printer broken" --priority high
"""

import argparse
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def read_env_value(key: str) -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip().strip("\"'")
    raise SystemExit(f"{key} not found in {ENV_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a signed ticket webhook.")
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--ticket-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--priority", required=True, choices=["low", "medium", "high", "urgent"])
    parser.add_argument("--type", default="ticket.created")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/tickets")
    parser.add_argument("--bad-signature", action="store_true", help="send a wrong signature on purpose")
    args = parser.parse_args()

    payload = {
        "event_id": args.event_id,
        "type": args.type,
        "data": {"ticket_id": args.ticket_id, "title": args.title, "priority": args.priority},
    }
    body = json.dumps(payload).encode()

    secret = "wrong-secret" if args.bad_signature else read_env_value("WEBHOOK_SECRET")
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    request = urllib.request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json", "X-Signature": f"sha256={signature}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode())


if __name__ == "__main__":
    main()
