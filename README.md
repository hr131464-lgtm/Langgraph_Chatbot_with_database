# LangGraph Stateful Chatbot

This project is a stateful chatbot built using LangGraph, Streamlit, Groq, and SQLite.

As part of the extension, I added a small task creation workflow to show how the chatbot can handle an actual action, validate the input, retry a failed execution, and save the result.

## What was added

The chatbot can now create a task with:

- Task title
- Due date
- Conversation thread ID

The task is stored in SQLite after successful execution.

The workflow also handles invalid input and temporary execution failures.

## How the workflow works

User message
     ↓
Chat node
     ↓
LLM decides whether a tool is needed
     ↓
create_task
     ↓
Validate input
     ↓
Save task to SQLite
     ↓
Success / Error
     ↓
Update LangGraph state

If the message does not require a task action, the chatbot works like a normal conversational chatbot.

## Validation

Before saving a task, the following checks are performed:

- Task title is required.
- Task title cannot be longer than 200 characters.
- Due date must be in YYYY-MM-DD format.

If validation fails, the task is not inserted into the database and an error state is returned.

## Retry handling

The tool execution has a single retry for unexpected execution errors.

For example, if a temporary database or execution error occurs, the workflow tries the action one more time.

Validation errors are not retried because sending the same invalid input again would not solve the problem.

The workflow keeps track of:

- action_status
- action_result
- action_error
- retry_count

This makes it clear whether an action succeeded, failed, or required a retry.

## Persistence

SQLite is used for persistence.

There are two types of state:

Conversation state

LangGraph's SQLite checkpointer stores the conversation state for each thread.

Task state

Created tasks are stored in a separate tasks table with:

- Task ID
- Thread ID
- Title
- Due date
- Status
- Created time

The task database connection and LangGraph checkpoint connection are kept separate to avoid SQLite transaction conflicts during tool execution.

## Running the project

Install the dependencies:

pip install -r requirements.txt

Create a .env file and add the Groq API key:

GROQ_API_KEY=your_api_key

Start the Streamlit app:

streamlit run streamlit_frontend.py

## Running the tests

The task workflow has tests for successful execution, validation, and retry handling.

Run them with:

python -m unittest tests.test_task_workflow -v

Current test result:

Ran 3 tests

OK

## Design choice

I kept the implementation small and within the existing LangGraph structure instead of introducing additional services or a separate task system.

The main idea was to make the action workflow predictable:

1. The LLM decides when an action is needed.
2. The tool validates the input.
3. The action is executed and persisted.
4. Temporary execution errors can be retried once.
5. The final result is stored explicitly in the graph state.