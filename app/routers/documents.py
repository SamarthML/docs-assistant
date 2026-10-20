from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.embeddings import embed_documents
from app.ingestion import ALLOWED_EXTENSIONS, chunk_text, extract_pages
from app.models import Chunk, Document

MAX_FILE_SIZE = 10 * 1024 * 1024

router = APIRouter()


@router.post("/documents")
def upload_document(file: UploadFile, db: Session = Depends(get_db)) -> dict[str, Any]:
    file_name = file.filename or ""
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only .pdf, .txt and .md files are allowed")

    # Read one byte past the limit so we can tell if the file is too big.
    data = file.file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File is larger than 10 MB")
    if not data:
        raise HTTPException(400, "File is empty")

    try:
        pages = extract_pages(file_name, data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if not any(text.strip() for _, text in pages):
        raise HTTPException(400, "No text could be extracted. Scanned PDFs are not supported.")

    page_chunks = []
    for page_number, text in pages:
        for chunk in chunk_text(text, settings.chunk_size, settings.chunk_overlap):
            page_chunks.append((page_number, chunk))

    embeddings = embed_documents([chunk for _, chunk in page_chunks])

    document = Document(file_name=file_name)
    for index, ((page_number, content), embedding) in enumerate(zip(page_chunks, embeddings)):
        document.chunks.append(
            Chunk(
                file_name=file_name,
                page_number=page_number,
                chunk_index=index,
                content=content,
                embedding=embedding,
            )
        )

    db.add(document)
    db.commit()

    return {
        "document_id": document.id,
        "file_name": file_name,
        "pages": len(pages),
        "chunks": len(page_chunks),
    }
