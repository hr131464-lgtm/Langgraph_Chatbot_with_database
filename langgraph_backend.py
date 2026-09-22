from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from datetime import datetime
import sqlite3

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0
)


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    action_status: str
    action_result: str
    action_error: str
    retry_count: int


checkpoint_conn = sqlite3.connect(
    database="chatbot.db",
    check_same_thread=False,
    timeout=30
)

task_conn = sqlite3.connect(
    database="chatbot.db",
    check_same_thread=False,
    timeout=30
)


cursor = task_conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT,
    title TEXT NOT NULL,
    due_date TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

task_conn.commit()


def validate_task(title, due_date):
    if not title or not title.strip():
        return False, "Task title is required."

    if len(title) > 200:
        return False, "Task title is too long."

    try:
        datetime.strptime(due_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return False, "Due date must be in YYYY-MM-DD format."

    return True, ""


@tool
def create_task(title: str, due_date: str, thread_id: str):
    """
    Create a task and store it in SQLite.
    """

    valid, error = validate_task(title, due_date)

    if not valid:
        return {
            "status": "error",
            "message": error
        }

    cursor = task_conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO tasks(thread_id, title, due_date)
            VALUES (?, ?, ?)
            """,
            (thread_id, title, due_date)
        )

        task_conn.commit()

        task_id = cursor.lastrowid

        return {
            "status": "success",
            "task_id": task_id,
            "message": "Task created successfully."
        }

    except sqlite3.Error:
        task_conn.rollback()
        raise


tools = [create_task]

llm_with_tools = llm.bind_tools(tools)


def chat_node(state: ChatState):
    messages = state["messages"]

    response = llm_with_tools.invoke(messages)

    return {
        "messages": [response]
    }


def execute_tool(state: ChatState, config: RunnableConfig):
    messages = state["messages"]
    last_message = messages[-1]

    tool_call = last_message.tool_calls[0]

    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_call_id = tool_call["id"]

    if tool_name != "create_task":
        return {
            "action_status": "error",
            "action_error": "Unknown tool requested.",
            "action_result": "",
            "retry_count": 0,
            "messages": [
                ToolMessage(
                    content="Tool execution failed: unknown tool.",
                    tool_call_id=tool_call_id
                )
            ]
        }

    thread_id = config["configurable"]["thread_id"]

    retry_count = 0
    max_retries = 1

    while retry_count <= max_retries:
        try:
            result = create_task.invoke({
                "title": tool_args.get("title"),
                "due_date": tool_args.get("due_date"),
                "thread_id": thread_id
            })

            if result["status"] == "error":
                return {
                    "action_status": "error",
                    "action_error": result["message"],
                    "action_result": "",
                    "retry_count": retry_count,
                    "messages": [
                        ToolMessage(
                            content=result["message"],
                            tool_call_id=tool_call_id
                        )
                    ]
                }

            return {
                "action_status": "success",
                "action_result": result["message"],
                "action_error": "",
                "retry_count": retry_count,
                "messages": [
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id
                    )
                ]
            }

        except Exception as error:
            retry_count += 1

            if retry_count > max_retries:
                return {
                    "action_status": "error",
                    "action_error": str(error),
                    "action_result": "",
                    "retry_count": retry_count,
                    "messages": [
                        ToolMessage(
                            content="Task creation failed after retry.",
                            tool_call_id=tool_call_id
                        )
                    ]
                }


def route_after_chat(state: ChatState):
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tool"

    return END


checkpointer = SqliteSaver(
    conn=checkpoint_conn
)


graph = StateGraph(ChatState)

graph.add_node("chat_node", chat_node)
graph.add_node("execute_tool", execute_tool)

graph.add_edge(START, "chat_node")

graph.add_conditional_edges(
    "chat_node",
    route_after_chat
)

graph.add_edge("execute_tool", "chat_node")


chatbot = graph.compile(
    checkpointer=checkpointer
)


CONFIG = {
    "configurable": {
        "thread_id": "thread-1"
    }
}


def retrieve_all_threads():
    threads = []

    for checkpoint in checkpointer.list(None):
        threads.append(
            checkpoint.config["configurable"]["thread_id"]
        )

    return sorted(set(threads))