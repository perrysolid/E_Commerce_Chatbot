"""Single shared Groq client + a thin chat helper.

Replaces the three hardcoded clients that previously leaked the API key.
"""
from __future__ import annotations

from typing import List, Optional

from config import GROQ_API_KEY, GROQ_MODEL
from groq import Groq

_client: Optional[Groq] = None


def get_client() -> Groq:
    """Lazy singleton so importing this module never crashes without a key."""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to app/.env and add your key."
            )
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def chat(
    messages: List[dict],
    temperature: float = 0.2,
    max_tokens: int = 1024,
    reasoning_effort: str = "low",
) -> str:
    """Call the chat model and return the text content.

    ``reasoning_effort`` keeps gpt-oss models from spending the whole token
    budget on hidden reasoning, which would otherwise return empty content.
    """
    completion = get_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
    return (completion.choices[0].message.content or "").strip()
