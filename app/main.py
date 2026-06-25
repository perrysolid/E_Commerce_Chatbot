# pysqlite3 shim: chromadb needs a newer sqlite3 than some systems ship.
try:
    __import__("pysqlite3")
    import sys
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import streamlit as st
from config import ROUTER_CONFIDENCE_THRESHOLD
from faq import faq_chain, ingest_faq_data
from memory import ConversationMemory
from router import route
from smalltalk import small_talk_chain
from sql import sql_chain

CLARIFY = (
    "I'm not sure what you mean. Are you asking about a product, a store "
    "policy (returns, delivery, payments), or just saying hi?"
)


@st.cache_resource
def _bootstrap():
    """Ingest FAQ data once per server process."""
    ingest_faq_data()
    return True


def ask(query: str, memory: ConversationMemory) -> str:
    routed = route(query)
    history = memory.context()

    if routed.name is None or routed.confidence < ROUTER_CONFIDENCE_THRESHOLD:
        return CLARIFY
    if routed.name == "faq":
        return faq_chain(query, history)
    if routed.name == "sql":
        return sql_chain(query, history)
    if routed.name == "small-talk":
        return small_talk_chain(query, history)
    return CLARIFY


_bootstrap()
st.title("🛍️ E-Commerce Chatbot")

if "memory" not in st.session_state:
    st.session_state.memory = ConversationMemory()
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

query = st.chat_input("Ask about products, returns, delivery...")
if query:
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.messages.append({"role": "user", "content": query})

    response = ask(query, st.session_state.memory)
    st.session_state.memory.add("user", query)
    st.session_state.memory.add("assistant", response)

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
