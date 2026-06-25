# pysqlite3 shim: chromadb needs a newer sqlite3 than some systems ship.
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import sys
import time
from pathlib import Path

# Make the etl package importable so the app can build its own DB on first run
# (the SQLite file is a build artifact and is not committed).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from config import DB_PATH, ROUTER_CONFIDENCE_THRESHOLD
from faq import faq_chain, ingest_faq_data
from memory import ConversationMemory
from router import route
from smalltalk import small_talk_chain
from sql import sql_chain

# --- Catalog metadata ---------------------------------------------------------
CATEGORIES = {
    "mobiles": "📱", "laptops": "💻", "headphones": "🎧", "smartwatches": "⌚",
    "televisions": "📺", "tablets": "📲", "earbuds": "🎵",
}
BROWSE_ALL = "Just browsing"

FAQ_SAMPLES = ["What is your return policy?", "How do I track my order?"]
SAMPLE_QUESTIONS = {
    "mobiles": ["Show Samsung phones under ₹20,000", "Best rated 5G phones",
                "Cheapest phones with good ratings"],
    "laptops": ["Laptops under ₹50,000", "Top rated laptops",
                "Laptops with the biggest discount"],
    "headphones": ["boAt headphones under ₹2,000", "Best rated wireless headphones",
                   "Headphones with the biggest discount"],
    "smartwatches": ["Smartwatches under ₹2,000", "Fire-Boltt smartwatches",
                     "Cheapest smartwatches"],
    "televisions": ["43 inch TVs under ₹30,000", "Top rated smart TVs",
                    "Televisions with the biggest discount"],
    "tablets": ["Tablets under ₹15,000", "Top rated tablets", "Samsung tablets"],
    "earbuds": ["Earbuds under ₹1,000", "Best rated true wireless earbuds",
                "boAt earbuds on sale"],
    BROWSE_ALL: ["Show me laptops under ₹50,000", "Best rated headphones",
                 "What is your return policy?"],
}

CLARIFY = (
    "I'm not sure what you mean. Are you asking about a product, a store "
    "policy (returns, delivery, payments), or just saying hi?"
)

CSS = """
<style>
.block-container { max-width: 820px; }
.hero {
    background: linear-gradient(120deg, #4C7BF3 0%, #7C3AED 100%);
    padding: 1.6rem 1.8rem; border-radius: 18px; color: #fff; margin-bottom: 1rem;
    animation: fade 0.6s ease;
}
.hero h1 { margin: 0; font-size: 1.9rem; letter-spacing: 0.5px; }
.hero .sub { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 2px;
    opacity: 0.85; margin-top: 0.15rem; }
.hero p { margin: 0.6rem 0 0; opacity: 0.92; font-size: 0.96rem; }
.cap { display:flex; gap:0.6rem; margin:0.9rem 0 0.3rem; flex-wrap:wrap; }
.cap div {
    flex:1; min-width:170px; background:rgba(124,58,237,0.07);
    border:1px solid rgba(124,58,237,0.15);
    border-radius:12px; padding:0.7rem 0.9rem; font-size:0.88rem; animation: fade 0.7s ease;
}
.stChatMessage { animation: fade 0.4s ease; }
.stButton button { border-radius: 999px; transition: all 0.15s ease; }
.stButton button:hover { border-color:#7C3AED; color:#7C3AED; transform: translateY(-1px); }
@keyframes fade { from {opacity:0; transform: translateY(6px);} to {opacity:1; transform:none;} }
</style>
"""


# --- Backend ------------------------------------------------------------------
@st.cache_resource
def _bootstrap():
    """Build the catalog from the committed snapshot (if needed) and ingest FAQs.

    Runs once per server process, so a fresh deploy (e.g. Streamlit Cloud) works
    with no manual setup.
    """
    if not DB_PATH.exists():
        from etl.pipeline import run_etl
        run_etl()
    ingest_faq_data()
    return True


def ask(query: str, memory: ConversationMemory, category: str) -> str:
    routed = route(query)
    history = memory.context()
    if category and category != BROWSE_ALL:
        history = f"{history}\nThe user is shopping in the '{category}' category.".strip()

    if routed.name is None or routed.confidence < ROUTER_CONFIDENCE_THRESHOLD:
        return CLARIFY
    if routed.name == "faq":
        return faq_chain(query, history)
    if routed.name == "sql":
        return sql_chain(query, history)
    if routed.name == "small-talk":
        return small_talk_chain(query, history)
    return CLARIFY


def _stream(text: str):
    """Word-by-word typing animation for the assistant reply."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


# --- UI -----------------------------------------------------------------------
st.set_page_config(page_title="Saarthi — Flipkart Electronics Chatbot",
                   page_icon="🛒", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)
_bootstrap()

if "category" not in st.session_state:
    st.session_state.category = None
if "memory" not in st.session_state:
    st.session_state.memory = ConversationMemory()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None

st.markdown(
    """
    <div class="hero">
      <h1>🛒 Saarthi</h1>
      <div class="sub">Flipkart Electronics Chatbot</div>
      <p>Your guide to Flipkart electronics — search products by price, brand &amp;
      rating, and ask store questions like returns, delivery and payments.
      All answers come from real Flipkart data, refreshed daily.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Step 1: pick a category.
if st.session_state.category is None:
    st.markdown(
        """
        <div class="cap">
          <div>🔎 <b>Find products</b><br/>"Show Samsung phones under ₹20,000"</div>
          <div>⭐ <b>Compare</b><br/>"Top rated laptops with discounts"</div>
          <div>📦 <b>Store help</b><br/>"What is your return policy?"</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("First, what are you shopping for?")
    items = list(CATEGORIES.items()) + [(BROWSE_ALL, "🛍️")]
    cols = st.columns(4)
    for i, (name, icon) in enumerate(items):
        if cols[i % 4].button(f"{icon}\n\n{name.title()}", key=f"cat_{name}",
                              use_container_width=True):
            st.session_state.category = name
            st.rerun()
    st.stop()

# Step 2: chat about the chosen category.
cat = st.session_state.category
icon = CATEGORIES.get(cat, "🛍️")
top = st.columns([4, 1])
top[0].markdown(f"#### {icon} Shopping: **{cat.title()}**")
if top[1].button("↺ Change", use_container_width=True):
    st.session_state.category = None
    st.rerun()

if not st.session_state.messages:
    st.caption("Try one of these to get started:")
    samples = SAMPLE_QUESTIONS.get(cat, []) + (FAQ_SAMPLES if cat != BROWSE_ALL else [])
    cols = st.columns(2)
    for i, q in enumerate(samples):
        if cols[i % 2].button(q, key=f"s_{i}", use_container_width=True):
            st.session_state.pending = q
            st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

typed = st.chat_input(f"Ask about {cat} or store policies…")
query = st.session_state.pending or typed
st.session_state.pending = None

if query:
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("assistant"):
        with st.spinner("Looking through the catalog…"):
            response = ask(query, st.session_state.memory, cat)
        st.write_stream(_stream(response))

    st.session_state.memory.add("user", query)
    st.session_state.memory.add("assistant", response)
    st.session_state.messages.append({"role": "assistant", "content": response})
