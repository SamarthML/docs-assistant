from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}

# Preferred places to end a chunk, best first.
BREAK_POINTS = ["\n\n", ". ", "! ", "? ", "\n", " "]


def extract_pages(file_name: str, data: bytes) -> list[tuple[int, str]]:
    """Return (page_number, text) pairs. Page numbers start at 1."""
    extension = Path(file_name).suffix.lower()

    if extension == ".pdf":
        try:
            reader = PdfReader(BytesIO(data))
            return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except Exception as e:
            raise ValueError(f"Could not read PDF: {e}") from e

    if extension in (".txt", ".md"):
        try:
            return [(1, data.decode("utf-8-sig"))]
        except UnicodeDecodeError as e:
            raise ValueError("File is not valid UTF-8 text") from e

    raise ValueError(f"Unsupported file type: {extension}")


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            end = find_break(text, start, end)

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break
        start = next_start(text, end, overlap)

    return chunks


def find_break(text: str, start: int, end: int) -> int:
    # Only look in the second half of the window so chunks don't get too small.
    search_from = start + (end - start) // 2
    for separator in BREAK_POINTS:
        position = text.rfind(separator, search_from, end)
        if position != -1:
            return position + len(separator)
    return end


def next_start(text: str, end: int, overlap: int) -> int:
    start = end - overlap
    # Move forward to the next word so the overlap doesn't start mid-word.
    space = text.find(" ", start, end)
    if space != -1:
        start = space + 1
    return start
