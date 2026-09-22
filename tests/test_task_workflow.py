import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

from langgraph_backend import create_task, execute_tool


class FakeTool:

    def __init__(self, results):
        self.results = results
        self.calls = 0

    def invoke(self, args):
        result = self.results[self.calls]
        self.calls += 1

        if isinstance(result, Exception):
            raise result

        return result


class TestTaskWorkflow(unittest.TestCase):

    def test_valid_task(self):
        result = create_task.invoke({
            "title": "Test interview task",
            "due_date": "2026-10-01",
            "thread_id": "test-thread"
        })

        self.assertEqual(result["status"], "success")

    def test_invalid_date(self):
        result = create_task.invoke({
            "title": "Invalid date task",
            "due_date": "2026-99-99",
            "thread_id": "test-thread"
        })

        self.assertEqual(result["status"], "error")
        self.assertIn("YYYY-MM-DD", result["message"])

    def test_retry_after_temporary_error(self):

        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "create_task",
                    "args": {
                        "title": "Retry test task",
                        "due_date": "2026-10-02"
                    },
                    "id": "test-tool-call"
                }
            ]
        )

        state = {
            "messages": [message]
        }

        config = {
            "configurable": {
                "thread_id": "retry-test-thread"
            }
        }

        successful_result = {
            "status": "success",
            "task_id": 999,
            "message": "Task created successfully."
        }

        fake_tool = FakeTool([
            Exception("Temporary database issue"),
            successful_result
        ])

        with patch(
            "langgraph_backend.create_task",
            fake_tool
        ):
            result = execute_tool(state, config)

        self.assertEqual(result["action_status"], "success")
        self.assertEqual(result["retry_count"], 1)


if __name__ == "__main__":
    unittest.main()