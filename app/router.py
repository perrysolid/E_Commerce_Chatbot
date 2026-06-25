"""Lightweight intent router.

Instead of a heavy routing library we embed a few example utterances per
intent and match queries by cosine similarity. The best similarity doubles
as a confidence score, which the app uses to ask a clarifying question when
no intent is a clear winner.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional

import numpy as np
from config import EMBEDDING_MODEL
from sentence_transformers import SentenceTransformer

ROUTES: Dict[str, List[str]] = {
    "faq": [
        "What is the return policy of the products?",
        "Do I get discount with the HDFC credit card?",
        "How can I track my order?",
        "How long does it take to process a refund?",
        "Are there any ongoing sales or promotions?",
        "Can I cancel or modify my order after placing it?",
        "Do you offer international shipping?",
        "What are the modes of refund available after cancellation?",
        "Can I reschedule the pickup date?",
        "How quickly can I get my order delivered?",
    ],
    "sql": [
        "I want to buy nike shoes that have 50% discount.",
        "Are there any shoes under Rs. 3000?",
        "Do you have formal shoes in size 9?",
        "Are there any Puma shoes on sale?",
        "What is the price of puma running shoes?",
        "Show me the top rated adidas shoes",
    ],
    "small-talk": [
        "Hi",
        "How are you?",
        "What is your name?",
        "Are you a robot?",
        "What do you do?",
        "How can you help me?",
    ],
}


class Routed(NamedTuple):
    name: Optional[str]
    confidence: float


_model: Optional[SentenceTransformer] = None
_route_names: List[str] = []
_route_embeddings: Optional[np.ndarray] = None


def _ensure_loaded() -> None:
    global _model, _route_names, _route_embeddings
    if _model is not None:
        return
    _model = SentenceTransformer(EMBEDDING_MODEL)
    names, utterances = [], []
    for name, examples in ROUTES.items():
        names.extend([name] * len(examples))
        utterances.extend(examples)
    _route_names = names
    _route_embeddings = _model.encode(utterances, normalize_embeddings=True)


def route(query: str) -> Routed:
    """Return the best-matching intent and its cosine-similarity confidence."""
    _ensure_loaded()
    q = _model.encode([query], normalize_embeddings=True)[0]
    sims = _route_embeddings @ q  # cosine sim (vectors are normalized)
    best = int(np.argmax(sims))
    return Routed(name=_route_names[best], confidence=float(sims[best]))


if __name__ == "__main__":
    for q in ["What is your policy on defective product?",
              "Pink Puma shoes in price range 1000 to 5000",
              "hello there",
              "asdfghjkl"]:
        print(f"{q!r} -> {route(q)}")
