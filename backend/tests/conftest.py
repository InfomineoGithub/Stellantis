"""Test configuration for the backend test suite.

Sets up sys.path and pre-mocks modules that would cause circular import
issues when unit-testing lightweight config/registry code in isolation.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Force auth bypass for all tests so they don't need a valid JWT token
os.environ["BYPASS_AUTH"] = "true"

# On Windows, fcntl is not available. Provide a minimal stub so that
# aio_sandbox_provider (which uses fcntl for cross-process locking) can be
# imported in unit tests without running on a Unix host.
if sys.platform == "win32" and "fcntl" not in sys.modules:
    _fcntl_mock = MagicMock()
    _fcntl_mock.LOCK_EX = 2
    _fcntl_mock.LOCK_UN = 8
    sys.modules["fcntl"] = _fcntl_mock

# Make 'app' and 'deerflow' importable from any working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

# Break the circular import chain that exists in production code:
#   deerflow.subagents.__init__
#     -> .executor (SubagentExecutor, SubagentResult)
#       -> deerflow.agents.thread_state
#         -> deerflow.agents.__init__
#           -> lead_agent.agent
#             -> subagent_limit_middleware
#               -> deerflow.subagents.executor  <-- circular!
#
# By injecting a mock for deerflow.subagents.executor *before* any test module
# triggers the import, __init__.py's "from .executor import ..." succeeds
# immediately without running the real executor module.
_executor_mock = MagicMock()
_executor_mock.SubagentExecutor = MagicMock
_executor_mock.SubagentResult = MagicMock
_executor_mock.SubagentStatus = MagicMock
_executor_mock.MAX_CONCURRENT_SUBAGENTS = 3
_executor_mock.get_background_task_result = MagicMock()

sys.modules["deerflow.subagents.executor"] = _executor_mock
