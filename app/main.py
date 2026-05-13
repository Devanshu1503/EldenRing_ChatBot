"""
Streamlit chat UI.
Run locally: streamlit run app/main.py
"""

import os
import sys
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# make sure app/ can import chat.py
sys.path.insert(0, str(Path(__file__).parent))
from chat import ask

st.set_page_config(
    page_title="Convergence Mod Guide",
    page_icon="⚔️",
    layout="centered",
)

st.title("⚔️ Convergence Mod Guide")
st.caption("Ask anything about Elden Ring with the Convergence overhaul mod.")

if "history" not in st.session_state:
    st.session_state.history = []

# render chat history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# input
if prompt := st.chat_input("Ask a question..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching game knowledge ..."):
            reply = ask(prompt, st.session_state.history[:-1])
        st.markdown(reply)

    st.session_state.history.append({"role": "assistant", "content": reply})
