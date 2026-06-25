# pysqlite3 shim: chromadb needs a newer sqlite3 than some systems ship.
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import re
import sqlite3
import sys
import time
from html import escape
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
    "mobiles": ["Samsung 5G phones under ₹20,000", "Snapdragon phones with 8 GB RAM",
                "Best rated phones with 128 GB storage"],
    "laptops": ["Intel i5 laptops under ₹60,000", "Laptops with 16 GB RAM",
                "Top rated laptops"],
    "headphones": ["boAt headphones under ₹2,000", "Best rated wireless headphones",
                   "Headphones with the biggest discount"],
    "smartwatches": ["Smartwatches under ₹2,000", "Best rated smartwatches",
                     "Smartwatches with a big display"],
    "televisions": ["43 inch 4K TVs", "Full HD TVs under ₹30,000",
                    "Top rated smart TVs"],
    "tablets": ["Tablets with 128 GB storage", "Top rated tablets under ₹20,000",
                "Tablets with 4G"],
    "earbuds": ["Earbuds with 40+ hours battery", "Best rated true wireless earbuds",
                "boAt earbuds under ₹1,500"],
    BROWSE_ALL: ["Intel i5 laptops under ₹60,000", "Best rated 5G phones",
                 "What is your return policy?"],
}

CLARIFY = (
    "I'm not sure what you mean. Are you asking about a product, a store "
    "policy (returns, delivery, payments), or just saying hi?"
)

BASE_CSS = """
<style>
.stApp {
    color: var(--text);
    background-color: var(--bg);
    background-image:
        linear-gradient(var(--grid) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid) 1px, transparent 1px),
        radial-gradient(circle at 16% 10%, var(--wash-a), transparent 32%),
        radial-gradient(circle at 86% 4%, var(--wash-b), transparent 28%);
    background-size: 34px 34px, 34px 34px, auto, auto;
}
.block-container { max-width: 1080px; padding-top: 1.6rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] {
    background: var(--sidebar);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] * { color: var(--text); }
.hero {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 1.15rem 1.25rem;
    color: var(--text);
    background:
        linear-gradient(135deg, var(--panel), var(--panel-strong)),
        linear-gradient(90deg, var(--accent), var(--accent-2));
    box-shadow: 0 18px 45px var(--shadow);
    margin-bottom: 1rem;
    animation: fade 0.35s ease;
}
.hero h1 {
    margin: 0;
    font-size: clamp(2.1rem, 7vw, 4.9rem);
    line-height: 0.92;
    letter-spacing: 0;
    font-weight: 900;
}
.hero .sub {
    display: inline-flex;
    gap: 0.45rem;
    align-items: center;
    color: var(--muted);
    font-size: 0.8rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-top: 0.55rem;
}
.hero p {
    margin: 0.75rem 0 0;
    color: var(--muted);
    max-width: 780px;
    font-size: 0.98rem;
}
.stat-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.65rem;
    margin: 0.9rem 0 1rem;
}
.stat {
    min-height: 86px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    padding: 0.8rem 0.9rem;
    box-shadow: 0 12px 32px var(--shadow);
}
.stat b { display:block; font-size:1.3rem; color:var(--text); }
.stat span { display:block; margin-top:0.25rem; color:var(--muted); font-size:0.84rem; }
.rail-head {
    display:flex;
    align-items:flex-end;
    justify-content:space-between;
    gap:1rem;
    margin: 1.1rem 0 0.45rem;
}
.rail-head h3 { margin:0; font-size:1rem; letter-spacing:0; }
.rail-head span { color:var(--muted); font-size:0.82rem; }
.product-rail {
    display:flex;
    gap:0.8rem;
    overflow-x:auto;
    padding:0.1rem 0 0.75rem;
    scroll-snap-type:x mandatory;
}
.product-card {
    flex: 0 0 245px;
    min-height: 214px;
    scroll-snap-align:start;
    display:flex;
    flex-direction:column;
    justify-content:space-between;
    border:1px solid var(--line);
    border-radius:8px;
    background: var(--panel);
    padding:0.9rem;
    box-shadow: 0 12px 32px var(--shadow);
}
.product-card .tag {
    width:max-content;
    max-width:100%;
    border:1px solid var(--line);
    border-radius:999px;
    padding:0.18rem 0.52rem;
    color:var(--muted);
    font-size:0.72rem;
    text-transform:uppercase;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}
.product-card h4 {
    margin:0.65rem 0 0.45rem;
    color:var(--text);
    font-size:0.94rem;
    line-height:1.25;
    letter-spacing:0;
    display:-webkit-box;
    -webkit-line-clamp:3;
    -webkit-box-orient:vertical;
    overflow:hidden;
}
.product-card .meta {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:0.6rem;
    color:var(--muted);
    font-size:0.78rem;
}
.product-card .price {
    display:block;
    color:var(--accent);
    font-weight:800;
    font-size:1.05rem;
    margin-top:0.35rem;
}
.product-card a {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    height:34px;
    border-radius:6px;
    background:var(--button);
    color:var(--button-text) !important;
    text-decoration:none;
    font-weight:700;
    margin-top:0.75rem;
}
.category-note {
    color: var(--muted);
    margin-top: -0.15rem;
    margin-bottom: 0.85rem;
}
.stChatMessage {
    border:1px solid var(--line);
    border-radius:8px;
    background: var(--chat);
    animation: fade 0.25s ease;
}
.stButton button {
    border-radius: 6px;
    border-color: var(--line);
    background: var(--panel);
    color: var(--text);
    transition: all 0.15s ease;
}
.stButton button:hover {
    border-color: var(--accent);
    color: var(--accent);
    transform: translateY(-1px);
}
div[data-testid="stChatInput"] { border-color: var(--line); }
@media (max-width: 760px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .stat-grid { grid-template-columns: 1fr; }
    .product-card { flex-basis: 82vw; }
    .hero { padding: 1rem; }
}
@keyframes fade { from {opacity:0; transform: translateY(5px);} to {opacity:1; transform:none;} }
</style>
"""


THEME_CSS = {
    "Light": """
    <style>
    :root {
        --bg:#f7f5ef; --panel:#fffdf8; --panel-strong:#f3efe5; --sidebar:#ebe7dc;
        --text:#1e2329; --muted:#626970; --line:rgba(30,35,41,0.14);
        --grid:rgba(30,35,41,0.07); --accent:#0f7c80; --accent-2:#b24c35;
        --button:#1e2329; --button-text:#fffdf8; --chat:rgba(255,253,248,0.84);
        --shadow:rgba(35,42,50,0.08); --wash-a:rgba(15,124,128,0.14);
        --wash-b:rgba(178,76,53,0.12);
    }
    </style>
    """,
    "Dark": """
    <style>
    :root {
        --bg:#101214; --panel:#171b1f; --panel-strong:#20262a; --sidebar:#15181b;
        --text:#f2efe8; --muted:#a8b0b7; --line:rgba(242,239,232,0.14);
        --grid:rgba(242,239,232,0.065); --accent:#49c2bd; --accent-2:#f08c5d;
        --button:#f2efe8; --button-text:#101214; --chat:rgba(23,27,31,0.84);
        --shadow:rgba(0,0,0,0.32); --wash-a:rgba(73,194,189,0.13);
        --wash-b:rgba(240,140,93,0.12);
    }
    </style>
    """,
}


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
        # Query the category's view (clean columns) when a real category is chosen.
        sql_category = category if category in CATEGORIES else None
        return sql_chain(query, history, category=sql_category)
    if routed.name == "small-talk":
        return small_talk_chain(query, history)
    return CLARIFY


def _stream(text: str):
    """Word-by-word typing animation for the assistant reply."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.012)


def _extract_product_links(text: str) -> list[str]:
    links = re.findall(r"https://www\.flipkart\.com/[^\s)]+", text)
    deduped = []
    for link in links:
        clean = link.rstrip(".,")
        if clean not in deduped:
            deduped.append(clean)
    return deduped


@st.cache_data(ttl=60)
def _catalog_counts() -> tuple[int, int]:
    with sqlite3.connect(DB_PATH) as conn:
        products = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]
        links = conn.execute("SELECT COUNT(DISTINCT product_link) FROM product").fetchone()[0]
    return products, links


@st.cache_data(ttl=60)
def _lookup_products(links: tuple[str, ...]) -> list[dict]:
    if not links:
        return []
    placeholders = ",".join("?" for _ in links)
    query = (
        "SELECT product_link, title, brand, category, price, discount, avg_rating, total_ratings "
        f"FROM product WHERE product_link IN ({placeholders})"
    )
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, links).fetchall()
    by_link = {row["product_link"]: dict(row) for row in rows}
    return [by_link[link] for link in links if link in by_link]


def _remember_products(response: str) -> None:
    products = _lookup_products(tuple(_extract_product_links(response)))
    if not products:
        return
    by_link = {p["product_link"]: p for p in products}
    for product in st.session_state.product_cards:
        by_link.setdefault(product["product_link"], product)
    st.session_state.product_cards = list(by_link.values())[:18]


def _render_product_rail(products: list[dict], title: str, note: str) -> None:
    if not products:
        return
    cards = []
    for product in products:
        title_text = escape(str(product["title"]))
        category = escape(str(product.get("category") or "catalog"))
        brand = escape(str(product.get("brand") or "Brand"))
        price = f"₹{int(product['price']):,}"
        rating = (
            f"{float(product['avg_rating']):.1f}★"
            if float(product.get("avg_rating") or 0)
            else "New"
        )
        discount = int(round(float(product.get("discount") or 0) * 100))
        deal = f"{discount}% off" if discount else "Live price"
        link = escape(str(product["product_link"]), quote=True)
        ratings = f"{int(product['total_ratings']):,} ratings"
        # Keep the HTML on one line with no leading whitespace — indented HTML in
        # st.markdown gets parsed as a code block and shown as raw text.
        cards.append(
            '<article class="product-card"><div>'
            f'<div class="tag">{category}</div>'
            f'<h4>{title_text}</h4>'
            f'<div class="meta"><span>{brand}</span><span>{rating}</span></div>'
            f'<span class="price">{price}</span>'
            f'<div class="meta"><span>{deal}</span><span>{ratings}</span></div>'
            '</div>'
            f'<a href="{link}" target="_blank" rel="noopener">Open product</a>'
            '</article>'
        )
    html = (
        f'<div class="rail-head"><h3>{escape(title)}</h3>'
        f'<span>{escape(note)}</span></div>'
        f'<div class="product-rail">{"".join(cards)}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# --- UI -----------------------------------------------------------------------
st.set_page_config(page_title="Saarthi — Flipkart Electronics Chatbot",
                   page_icon="🛒", layout="centered")
_bootstrap()

if "category" not in st.session_state:
    st.session_state.category = None
if "memory" not in st.session_state:
    st.session_state.memory = ConversationMemory()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "product_cards" not in st.session_state:
    st.session_state.product_cards = []
if "theme" not in st.session_state:
    st.session_state.theme = "Dark"

with st.sidebar:
    st.session_state.theme = "Light" if st.toggle(
        "Light mode", value=st.session_state.theme == "Light"
    ) else "Dark"
    product_count, link_count = _catalog_counts()
    st.metric("Catalog rows", f"{product_count:,}")
    st.metric("Saved product links", f"{link_count:,}")
    if st.button("Clear product rail", use_container_width=True):
        st.session_state.product_cards = []

st.markdown(THEME_CSS[st.session_state.theme], unsafe_allow_html=True)
st.markdown(BASE_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero">
      <h1>Saarthi</h1>
      <div class="sub">Flipkart electronics desk</div>
      <p>Search the catalog by price, brand, rating, and discount. Product answers stay tied to
      the scraped CSV snapshot, with links kept as first-class catalog records.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

product_count, link_count = _catalog_counts()
st.markdown(
    f"""
    <div class="stat-grid">
      <div class="stat"><b>{product_count:,}</b><span>catalog products</span></div>
      <div class="stat"><b>{link_count:,}</b><span>saved product links</span></div>
      <div class="stat"><b>7</b><span>shopping categories</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Step 1: pick a category.
if st.session_state.category is None:
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
            _remember_products(response)
        st.write_stream(_stream(response))

    st.session_state.memory.add("user", query)
    st.session_state.memory.add("assistant", response)
    st.session_state.messages.append({"role": "assistant", "content": response})

_render_product_rail(
    st.session_state.product_cards,
    "Recently opened from chat",
    "Cards are built from product links in answers",
)
