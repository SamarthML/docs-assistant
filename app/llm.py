import re
from dataclasses import dataclass
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

TICKET_SYSTEM_PROMPT = f"""{SYSTEM_PROMPT}
- You have a create_ticket tool. Call it ONLY if the user is asking you to raise, create or open a ticket.
- If the user is asking a question about tickets, do not call the tool. Answer from the context as usual."""

CREATE_TICKET_TOOL = {
    "type": "function",
    "function": {
        "name": "create_ticket",
        "description": "Create a support ticket for the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short summary of the problem."},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "default": "medium",
                },
                "description": {"type": "string", "description": "More detail about the problem."},
            },
            "required": ["title"],
        },
    },
}


@dataclass
class ToolCall:
    name: str
    arguments: str


@lru_cache
def get_client() -> Groq:
    return Groq(api_key=settings.groq_api_key, timeout=30)


def build_context(chunks: list[Chunk]) -> str:
    parts = []
    for number, chunk in enumerate(chunks, start=1):
        parts.append(f"[{number}] (file: {chunk.file_name}, page {chunk.page_number})\n{chunk.content}")
    return "\n\n".join(parts)


def build_messages(system_prompt: str, question: str, chunks: list[Chunk]) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{build_context(chunks)}\n\nQuestion: {question}"},
    ]


def clean_answer(content: str | None) -> str:
    answer = (content or "").strip()
    # Some models (e.g. gpt-oss) cite with full-width brackets like 【1】.
    return re.sub(r"【(\d+)】", r"[\1]", answer)


def generate_answer(question: str, chunks: list[Chunk]) -> str:
    response = get_client().chat.completions.create(
        model=settings.groq_model,
        temperature=0,
        messages=build_messages(SYSTEM_PROMPT, question, chunks),
    )
    return clean_answer(response.choices[0].message.content)


def generate_answer_with_tools(question: str, chunks: list[Chunk]) -> str | ToolCall:
    """Return the answer text, or the tool call if the model chose to create a ticket."""
    response = get_client().chat.completions.create(
        model=settings.groq_model,
        temperature=0,
        messages=build_messages(TICKET_SYSTEM_PROMPT, question, chunks),
        tools=[CREATE_TICKET_TOOL],
        tool_choice="auto",
    )
    message = response.choices[0].message
    if message.tool_calls:
        call = message.tool_calls[0]
        return ToolCall(name=call.function.name, arguments=call.function.arguments)
    return clean_answer(message.content)


def extract_citations(answer: str, chunk_count: int) -> list[int]:
    """Return the cited chunk numbers in order, ignoring repeats and numbers out of range."""
    cited = []
    for match in re.findall(r"\[(\d+)\]", answer):
        number = int(match)
        if 1 <= number <= chunk_count and number not in cited:
            cited.append(number)
    return cited
