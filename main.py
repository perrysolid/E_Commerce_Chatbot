__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
from faq import faq_chain, ingest_faq_data
from sql import sql_chain
from smalltalk import small_talk_chain
from router import router
from pathlib import Path

faqs_path = Path(__file__).parent / "resources/faq_data.csv"
ingest_faq_data(faqs_path)

def ask(query):
    route = router(query).name
    if route == 'faq':
        return faq_chain(query)
    elif route == 'sql':
        return sql_chain(query)
    elif route == 'small-talk':
        return small_talk_chain(query)
    else:
        return f"I don't have knowledge of your question. Please ask relevant questions that I can help with(like Flipkart products)"

st.title("E-Commerce chatbot")


query = st.chat_input("Write your query")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for message in st.session_state.messages:
    with st.chat_message(message['role']):
        st.markdown(message['content'])

if query:
    with st.chat_message("user"):
        st.markdown(query)

    st.session_state.messages.append({"role": "user", "content": query})

    response = ask(query)
    with st.chat_message("Assistant"):
        st.markdown(response)

    st.session_state.messages.append({"role": "Assistant", "content": response})
