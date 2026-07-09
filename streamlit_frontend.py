import streamlit as st
from langgraph_backend import chatbot, retrieve_all_threads
from langchain_core.messages import HumanMessage, AIMessage
import uuid

# -----------------------------
# Helper Functions
# -----------------------------

def generate_thread_id():
    return str(uuid.uuid4())


def add_thread(thread_id):
    if thread_id not in st.session_state.chat_threads:
        st.session_state.chat_threads.append(thread_id)


def reset_chat():
    new_thread = generate_thread_id()

    st.session_state.thread_id = new_thread
    st.session_state.message_history = []

    add_thread(new_thread)


def load_conversation(thread_id):
    state = chatbot.get_state(
        config={
            "configurable": {
                "thread_id": thread_id
            }
        }
    )

    return state.values.get("messages", [])


# -----------------------------
# Session State
# -----------------------------

if "message_history" not in st.session_state:
    st.session_state.message_history = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state.chat_threads = retrieve_all_threads()

add_thread(st.session_state.thread_id)


# -----------------------------
# Sidebar
# -----------------------------

st.sidebar.title("🤖 LangGraph Chatbot")

if st.sidebar.button("➕ New Chat", use_container_width=True):
    reset_chat()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Recent Chats")


for thread_id in reversed(st.session_state.chat_threads):

    messages = load_conversation(thread_id)

    title = "New Chat"

    for msg in messages:

        if isinstance(msg, HumanMessage):

            title = msg.content.strip()

            if len(title) > 35:
                title = title[:35] + "..."

            break

    current_chat = thread_id == st.session_state.thread_id

    icon = "🟢" if current_chat else "💬"

    if st.sidebar.button(
        f"{icon} {title}",
        key=f"chat_{thread_id}",
        use_container_width=True
    ):

        st.session_state.thread_id = thread_id

        history = []

        for msg in messages:

            history.append(
                {
                    "role": "user"
                    if isinstance(msg, HumanMessage)
                    else "assistant",

                    "content": msg.content
                }
            )

        st.session_state.message_history = history

        st.rerun()


# -----------------------------
# Display Chat History
# -----------------------------

for message in st.session_state.message_history:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# -----------------------------
# User Input
# -----------------------------

user_input = st.chat_input("Type your message...")

if user_input:

    st.session_state.message_history.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    CONFIG = {
        "configurable": {
            "thread_id": st.session_state.thread_id
        },
        "metadata": {
            "thread_id": st.session_state.thread_id
        },
        "run_name": "chat_turn"
    }

    with st.chat_message("assistant"):

        def ai_stream():

            for chunk, metadata in chatbot.stream(
                {
                    "messages": [
                        HumanMessage(content=user_input)
                    ]
                },
                config=CONFIG,
                stream_mode="messages",
            ):

                if isinstance(chunk, AIMessage):
                    yield chunk.content

        ai_response = st.write_stream(ai_stream())

    st.session_state.message_history.append(
        {
            "role": "assistant",
            "content": ai_response
        }
    )