"""FAQ intent: retrieve -> cross-encoder rerank -> CRAG-lite grade -> answer.

Pipeline:
  1. ChromaDB pulls FAQ_RETRIEVE_K candidate Q/A pairs (bi-encoder recall).
  2. A cross-encoder reranks them for precision.
  3. CRAG-lite: if the best candidate scores below a relevance threshold we
     refuse to answer instead of hallucinating from an irrelevant FAQ.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import chromadb
import pandas as pd
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from config import (
    CHROMA_PATH,
    EMBEDDING_MODEL,
    FAQ_DATA_PATH,
    FAQ_RERANK_K,
    FAQ_RETRIEVE_K,
    RERANK_MODEL,
    RERANK_RELEVANCE_THRESHOLD,
)
from llm import chat
from sentence_transformers import CrossEncoder

# ChromaDB's telemetry is a noisy no-op here (a posthog version mismatch logs a
# harmless "capture() takes 1 positional..." on every event) — silence it.
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
chromadb.api.client.SharedSystemClient.clear_system_cache()

_chroma = chromadb.PersistentClient(
    path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False)
)
_collection_name = "faq"
_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

_reranker: Optional[CrossEncoder] = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker


def ingest_faq_data(path=FAQ_DATA_PATH) -> None:
    existing = [c for c in _chroma.list_collections()]
    if _collection_name in existing:
        return
    collection = _chroma.get_or_create_collection(name=_collection_name, embedding_function=_ef)
    df = pd.read_csv(path)
    collection.add(
        documents=df["question"].to_list(),
        metadatas=[{"answer": a} for a in df["answer"].to_list()],
        ids=[f"id_{i}" for i in range(len(df))],
    )


def _retrieve(query: str, k: int) -> List[Tuple[str, str]]:
    """Return [(question, answer)] candidates from the vector store."""
    collection = _chroma.get_collection(name=_collection_name, embedding_function=_ef)
    res = collection.query(query_texts=[query], n_results=k)
    questions = res["documents"][0]
    answers = [m["answer"] for m in res["metadatas"][0]]
    return list(zip(questions, answers))


def _rerank(query: str, candidates: List[Tuple[str, str]]) -> List[Tuple[float, str, str]]:
    """Score (question) against query with the cross-encoder, best first."""
    pairs = [(query, q) for q, _ in candidates]
    scores = _get_reranker().predict(pairs)
    ranked = [(float(s), q, a) for s, (q, a) in zip(scores, candidates)]
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked


def _generate_answer(query: str, context: str, history: Optional[str] = None) -> str:
    history_block = f"Conversation so far:\n{history}\n\n" if history else ""
    prompt = (
        "Answer the question using ONLY the context below. "
        'If the context does not contain the answer, say "I don\'t know". '
        "Do not make anything up.\n\n"
        f"{history_block}QUESTION: {query}\n\nCONTEXT: {context}"
    )
    return chat(messages=[{"role": "user", "content": prompt}], max_tokens=512)


def faq_chain(query: str, history: Optional[str] = None) -> str:
    candidates = _retrieve(query, FAQ_RETRIEVE_K)
    if not candidates:
        return "I don't have information about that yet."

    ranked = _rerank(query, candidates)

    # CRAG-lite relevance gate: refuse rather than hallucinate.
    if ranked[0][0] < RERANK_RELEVANCE_THRESHOLD:
        return (
            "I'm not sure about that one. I can help with orders, returns, "
            "payments, delivery, or finding products. Could you rephrase?"
        )

    context = "\n".join(a for _, _, a in ranked[:FAQ_RERANK_K])
    return _generate_answer(query, context, history)


if __name__ == "__main__":
    ingest_faq_data()
    print(faq_chain("Do you take cash as payment option?"))
    print(faq_chain("What is the capital of France?"))  # should refuse
