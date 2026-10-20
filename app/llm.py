import re
from functools import lru_cache

from groq import Groq

from app.config import settings
from app.models import Chunk

NOT_FOUND = "NOT_FOUND"

SYSTEM_PROMPT = f"""You answer questions about company documents.
Rules:
- Answer ONLY using the provided context. Do not use outside knowledge.
- Cite the context chunks you used by their number, like [1] or [2][3].
- Write plain text only. No markdown: no bold, italics, headings, bullet lists or tables.
- If the context does not contain the answer, reply with exactly: {NOT_FOUND}"""


@lru_cache
def get_client() -> Groq:
    return Groq(api_key=settings.groq_api_key, timeout=30)


def build_context(chunks: list[Chunk]) -> str:
    parts = []
    for number, chunk in enumerate(chunks, start=1):
        parts.append(f"[{number}] (file: {chunk.file_name}, page {chunk.page_number})\n{chunk.content}")
    return "\n\n".join(parts)


def generate_answer(question: str, chunks: list[Chunk]) -> str:
    response = get_client().chat.completions.create(
        model=settings.groq_model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{build_context(chunks)}\n\nQuestion: {question}"},
        ],
    )
    answer = (response.choices[0].message.content or "").strip()
    # Some models (e.g. gpt-oss) cite with full-width brackets like 【1】.
    return re.sub(r"【(\d+)】", r"[\1]", answer)


def extract_citations(answer: str, chunk_count: int) -> list[int]:
    """Return the cited chunk numbers in order, ignoring repeats and numbers out of range."""
    cited = []
    for match in re.findall(r"\[(\d+)\]", answer):
        number = int(match)
        if 1 <= number <= chunk_count and number not in cited:
            cited.append(number)
    return cited
