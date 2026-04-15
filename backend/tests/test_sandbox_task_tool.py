"""Tests that task_tool holds the sandbox ref count before spawning a subagent."""

from unittest.mock import MagicMock, patch


def make_provider_with_active_sandbox(sandbox_id: str = "abc12345") -> MagicMock:
    provider = MagicMock()
    provider.hold = MagicMock()
    return provider


def test_task_tool_calls_hold_when_sandbox_state_present():
    """task_tool must call provider.hold(sandbox_id) before execute_async."""
    from deerflow.tools.builtins.task_tool import task_tool

    sandbox_id = "abc12345"
    mock_runtime = MagicMock()
    mock_runtime.state = {"sandbox": {"sandbox_id": sandbox_id}, "thread_data": None}
    mock_runtime.context = {"thread_id": "thread-1"}
    mock_runtime.config = {"metadata": {}}

    mock_provider = make_provider_with_active_sandbox(sandbox_id)
    mock_executor = MagicMock()
    mock_executor.execute_async.return_value = "task-001"

    completed_status = MagicMock()
    completed_result = MagicMock()
    completed_result.status = completed_status
    completed_result.result = "done"
    completed_result.ai_messages = []

    mock_subagent_status = MagicMock()
    mock_subagent_status.COMPLETED = completed_status
    mock_subagent_status.FAILED = MagicMock()
    mock_subagent_status.TIMED_OUT = MagicMock()

    with (
        patch("deerflow.tools.builtins.task_tool.get_sandbox_provider", return_value=mock_provider),
        patch("deerflow.tools.builtins.task_tool.SubagentExecutor", return_value=mock_executor),
        patch("deerflow.tools.builtins.task_tool.get_background_task_result", return_value=completed_result),
        patch("deerflow.tools.builtins.task_tool.cleanup_background_task"),
        patch("deerflow.tools.builtins.task_tool.get_stream_writer", return_value=MagicMock()),
        patch("deerflow.tools.builtins.task_tool.get_subagent_config", return_value=MagicMock(system_prompt="", timeout_seconds=300, max_turns=10)),
        patch("deerflow.tools.get_available_tools", return_value=[]),
        patch("deerflow.tools.builtins.task_tool.get_skills_prompt_section", return_value=""),
        patch("deerflow.tools.builtins.task_tool.SubagentStatus", mock_subagent_status),
    ):
        task_tool.func(
            description="test task",
            prompt="do something",
            subagent_type="bash",
            runtime=mock_runtime,
            tool_call_id="call_123",
        )

    mock_provider.hold.assert_called_once_with(sandbox_id)


def test_task_tool_skips_hold_when_no_sandbox_state():
    """task_tool must not raise when sandbox_state is None."""
    from deerflow.tools.builtins.task_tool import task_tool

    mock_runtime = MagicMock()
    mock_runtime.state = {"sandbox": None, "thread_data": None}
    mock_runtime.context = {"thread_id": "thread-1"}
    mock_runtime.config = {"metadata": {}}

    mock_provider = MagicMock()
    mock_executor = MagicMock()
    mock_executor.execute_async.return_value = "task-001"

    completed_status = MagicMock()
    completed_result = MagicMock()
    completed_result.status = completed_status
    completed_result.result = "done"
    completed_result.ai_messages = []

    mock_subagent_status = MagicMock()
    mock_subagent_status.COMPLETED = completed_status
    mock_subagent_status.FAILED = MagicMock()
    mock_subagent_status.TIMED_OUT = MagicMock()

    with (
        patch("deerflow.tools.builtins.task_tool.get_sandbox_provider", return_value=mock_provider),
        patch("deerflow.tools.builtins.task_tool.SubagentExecutor", return_value=mock_executor),
        patch("deerflow.tools.builtins.task_tool.get_background_task_result", return_value=completed_result),
        patch("deerflow.tools.builtins.task_tool.cleanup_background_task"),
        patch("deerflow.tools.builtins.task_tool.get_stream_writer", return_value=MagicMock()),
        patch("deerflow.tools.builtins.task_tool.get_subagent_config", return_value=MagicMock(system_prompt="", timeout_seconds=300, max_turns=10)),
        patch("deerflow.tools.get_available_tools", return_value=[]),
        patch("deerflow.tools.builtins.task_tool.get_skills_prompt_section", return_value=""),
        patch("deerflow.tools.builtins.task_tool.SubagentStatus", mock_subagent_status),
    ):
        task_tool.func(
            description="test task",
            prompt="do something",
            subagent_type="bash",
            runtime=mock_runtime,
            tool_call_id="call_123",
        )

    mock_provider.hold.assert_not_called()
