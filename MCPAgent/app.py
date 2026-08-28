import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from chat_service import answer_question
from mcp_client import MicrosoftLearnMCP

load_dotenv()

st.set_page_config(
    page_title="Microsoft Learn Chat",
    page_icon=":material/menu_book:",
    layout="centered",
)

st.title("Microsoft Learn chat")
st.caption("Answers grounded in official Microsoft documentation")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Conversation")
    if st.button("Start new chat", icon=":material/add:", width="stretch"):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.caption("The assistant searches Microsoft Learn before answering technical questions.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about Azure, .NET, PowerShell, or Microsoft technologies"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            api_key = os.getenv("MODEL_API_KEY")
            if not api_key:
                raise RuntimeError("Set MODEL_API_KEY in your environment or .env file.")
            with st.spinner("Searching Microsoft Learn..."):
                model_client = OpenAI(
                    api_key=api_key,
                    base_url=os.getenv("MODEL_BASE_URL", "https://api.openai.com/v1"),
                )
                with MicrosoftLearnMCP(
                    os.getenv("MICROSOFT_LEARN_MCP_URL", "https://learn.microsoft.com/api/mcp"),
                    timeout=float(os.getenv("MCP_TIMEOUT_SECONDS", "45")),
                ) as mcp_client:
                    answer = answer_question(
                        model_client,
                        mcp_client,
                        st.session_state.messages,
                        os.getenv("MODEL_NAME", "gpt-4o-mini"),
                    )
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as error:
            st.error(f"Unable to answer from Microsoft Learn: {error}")
