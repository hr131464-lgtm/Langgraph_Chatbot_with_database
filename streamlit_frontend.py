import streamlit as st
from langgraph_backend import chatbot, retrieve_all_threads
from langchain_core.messages import HumanMessage, AIMessage
import uuid

# Helper Functions


def generate_thread_id():
    return uuid.uuid4()


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def reset_chat():
    thread_id = generate_thread_id()

    st.session_state["thread_id"] = thread_id
    st.session_state["message_history"] = []

    add_thread(thread_id)


def load_conversation(thread_id):
    state = chatbot.get_state(
        config={"configurable": {"thread_id": thread_id}}
    )

    return state.values.get("messages", [])

# Session State


if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrieve_all_threads()


add_thread(st.session_state["thread_id"])


# Sidebar

st.sidebar.title("🤖 LangGraph Chatbot")

if st.sidebar.button("➕ New Chat", use_container_width=True):
    reset_chat()

st.sidebar.markdown("---")
st.sidebar.subheader("Recent Chats")

for thread_id in st.session_state["chat_threads"][::-1]:

    messages = load_conversation(thread_id)

    title = "New Chat"

    # Use first user message as title
    for msg in messages:
        if isinstance(msg, HumanMessage):
            title = msg.content.strip()

            if len(title) > 35:
                title = title[:35] + "..."

            break

    current = thread_id == st.session_state["thread_id"]

    icon = "🟢" if current else "💬"

    if st.sidebar.button(
        f"{icon} {title}",
        key=str(thread_id),
        use_container_width=True
    ):

        st.session_state["thread_id"] = thread_id

        temp_messages = []

        for msg in messages:

            role = "user" if isinstance(msg, HumanMessage) else "assistant"

            temp_messages.append(
                {
                    "role": role,
                    "content": msg.content,
                }
            )

        st.session_state["message_history"] = temp_messages

        st.rerun()



# Chat History


for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Chat Input


user_input = st.chat_input("Type here")

if user_input:

    # Add user message

    st.session_state["message_history"].append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    # -------- Save Chat Title --------

    thread_key = str(st.session_state["thread_id"])

    if thread_key not in st.session_state["chat_titles"]:

        title = user_input.strip()

        if len(title) > 35:
            title = title[:35] + "..."

        st.session_state["chat_titles"][thread_key] = title

    with st.chat_message("user"):
        st.markdown(user_input)

    CONFIG = {
        "configurable": {
            "thread_id": st.session_state["thread_id"]
        },
        "metadata": {
            "thread_id": st.session_state["thread_id"]
        },
        "run_name": "chat_turn",
    }

    with st.chat_message("assistant"):

        def ai_only_stream():

            for message_chunk, metadata in chatbot.stream(
                {
                    "messages": [
                        HumanMessage(content=user_input)
                    ]
                },
                config=CONFIG,
                stream_mode="messages",
            ):

                if isinstance(message_chunk, AIMessage):
                    yield message_chunk.content

        ai_message = st.write_stream(ai_only_stream())

    st.session_state["message_history"].append(
        {
            "role": "assistant",
            "content": ai_message,
        }
    )