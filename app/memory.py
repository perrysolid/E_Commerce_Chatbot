"""Lightweight conversation memory: sliding window + running summary.

Keeps the last ``window`` turns verbatim and compresses anything older into a
one-paragraph summary. This is enough to resolve follow-ups like
"show me cheaper ones" without the cost of a full long-term memory store.
"""
from __future__ import annotations

from typing import List, Tuple

from llm import chat


class ConversationMemory:
    def __init__(self, window: int = 4):
        self.window = window
        self.turns: List[Tuple[str, str]] = []  # (role, content)
        self.summary: str = ""

    def add(self, role: str, content: str) -> None:
        self.turns.append((role, content))
        # Once we exceed the window, fold the oldest turn into the summary.
        while len(self.turns) > self.window:
            old_role, old_content = self.turns.pop(0)
            self._fold(old_role, old_content)

    def _fold(self, role: str, content: str) -> None:
        prompt = (
            "Update the running summary of this shopping conversation in 2-3 "
            "sentences. Keep product preferences, budgets and constraints.\n\n"
            f"Current summary: {self.summary or '(none)'}\n"
            f"New message ({role}): {content}"
        )
        try:
            self.summary = chat(messages=[{"role": "user", "content": prompt}], max_tokens=200)
        except Exception:  # summary is best-effort; never break the chat over it
            pass

    def context(self) -> str:
        """Render memory as a compact string to prepend to a chain prompt."""
        parts = []
        if self.summary:
            parts.append(f"Summary of earlier conversation: {self.summary}")
        for role, content in self.turns:
            parts.append(f"{role}: {content}")
        return "\n".join(parts)
