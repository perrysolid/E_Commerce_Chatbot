"""Central configuration. All tunables live here so the rest of the code stays clean."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).parent
RESOURCES_DIR = APP_DIR / "resources"

# Load app/.env (never committed). See .env.example for the template.
load_dotenv(APP_DIR / ".env")

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# --- Paths ---
DB_PATH = APP_DIR / "db.sqlite"
FAQ_DATA_PATH = RESOURCES_DIR / "faq_data.csv"
CHROMA_PATH = str(APP_DIR / "chroma")

# --- Embeddings / retrieval ---
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
FAQ_RETRIEVE_K = 5      # candidates pulled from the vector store
FAQ_RERANK_K = 2        # passed to the LLM after cross-encoder rerank

# --- Guardrail thresholds (tuned via the eval harness) ---
ROUTER_CONFIDENCE_THRESHOLD = 0.35   # cosine sim below this -> ask a clarifying question
RERANK_RELEVANCE_THRESHOLD = 0.0     # CRAG-lite: below this -> "I don't know"
SQL_MAX_RETRIES = 1                  # self-correction attempts on a bad query
