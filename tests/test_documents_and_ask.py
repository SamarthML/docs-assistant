from pathlib import Path

from fastapi.testclient import TestClient

SAMPLE_DOCS = Path(__file__).resolve().parent.parent / "sample_docs"


def upload(client: TestClient, file_name: str) -> None:
    path = SAMPLE_DOCS / file_name
    with path.open("rb") as f:
        response = client.post("/documents", files={"file": (file_name, f)})
    assert response.status_code == 200


def test_ask_with_no_matching_content(client: TestClient, fake_llm) -> None:
    upload(client, "faq.txt")

    response = client.post("/ask", json={"question": "Who won the cricket world cup in 2011?"})

    body = response.json()
    assert body["found"] is False
    assert body["sources"] == []
    assert fake_llm.calls == 0


def test_ask_returns_answer_with_sources(client: TestClient, fake_llm) -> None:
    upload(client, "northwind_handbook.pdf")
    fake_llm.answer = "24 days [1]"

    response = client.post("/ask", json={"question": "How many days of annual leave do employees get?"})

    body = response.json()
    assert body["found"] is True
    assert body["answer"] == "24 days [1]"
    assert any(
        source["file_name"] == "northwind_handbook.pdf" and source["page"] == 1
        for source in body["sources"]
    )


def test_list_documents_shows_chunk_count(client: TestClient) -> None:
    upload(client, "northwind_handbook.pdf")

    documents = client.get("/documents").json()

    assert len(documents) == 1
    assert documents[0]["file_name"] == "northwind_handbook.pdf"
    assert documents[0]["chunks"] == 4


def test_index_serves_html(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI Docs Assistant" in response.text


def test_upload_rejects_unsupported_file_type(client: TestClient) -> None:
    response = client.post("/documents", files={"file": ("data.csv", b"a,b\n1,2\n")})

    assert response.status_code == 400
