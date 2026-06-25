"""Small-talk intent: short, friendly, on-brand replies."""
from __future__ import annotations

from typing import Optional

from llm import chat

SYSTEM = (
    "You are a friendly assistant for an e-commerce shoe store. "
    "Keep small-talk replies to one or two short sentences, then gently steer "
    "the user toward products or FAQs you can help with."
)


def small_talk_chain(query: str, history: Optional[str] = None) -> str:
    user = query if not history else f"Conversation so far:\n{history}\n\nUser: {query}"
    return chat(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.5,
        max_tokens=256,
    )
