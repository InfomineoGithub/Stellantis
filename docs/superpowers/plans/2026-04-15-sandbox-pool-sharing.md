# Sandbox Pool Sharing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate K8s sandbox cold-start latency and allow multiple lead agents (and their subagents) to share sandbox Pods up to a configurable capacity limit.

**Architecture:** A pre-warm pool creates sandbox Pods speculatively in the background so new threads claim a hot container instead of waiting for provisioner cold-start. Reference counting on the provider ensures a sandbox is never moved to the warm pool while subagents still hold a reference to it. A slot-based acquisition mode (`max_threads_per_sandbox > 1`) lets multiple lead agents share one Pod, with each subagent inheriting its parent's sandbox via the existing `sandbox_state` passthrough.

**Tech Stack:** Python 3.12, `threading`, `AioSandboxProvider` (community aio_sandbox), Pydantic `SandboxConfig`, `pytest`, `ruff`

---

## File Map

| File | Change |
|------|--------|
| `backend/packages/harness/deerflow/config/sandbox_config.py` | Add `pre_warm_count` and `max_threads_per_sandbox` fields |
| `backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py` | Add ref counting, pre-warm pool, slot-based acquisition |
| `backend/packages/harness/deerflow/tools/builtins/task_tool.py` | Call `provider.hold()` before spawning subagent background task |
| `backend/tests/test_sandbox_pool.py` | New — unit tests for ref counting, pre-warm, and slot acquisition |
| `backend/tests/test_sandbox_task_tool.py` | New — unit tests for task_tool hold behaviour |

---

## Task 1: Add `pre_warm_count` and `max_threads_per_sandbox` to `SandboxConfig`

**Files:**
- Modify: `backend/packages/harness/deerflow/config/sandbox_config.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_sandbox_pool.py`:

```python
"""Tests for sandbox pool sharing: ref counting, pre-warm, slot-based acquisition."""
import threading
import time
from unittest.mock import MagicMock

import pytest

from deerflow.community.aio_sandbox.aio_sandbox_provider import (
    DEFAULT_MAX_THREADS_PER_SANDBOX,
    DEFAULT_PRE_WARM_COUNT,
    AioSandboxProvider,
)
from deerflow.community.aio_sandbox.sandbox_info import SandboxInfo


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_backend(sandbox_url: str = "http://localhost:9999") -> MagicMock:
    backend = MagicMock()
    backend.create.return_value = SandboxInfo(sandbox_id="test-box", sandbox_url=sandbox_url)
    backend.is_alive.return_value = True
    backend.discover.return_value = None
    return backend


def make_provider(backend: MagicMock, **config_overrides) -> AioSandboxProvider:
    """Build a provider with a mocked backend and no background threads."""
    p = AioSandboxProvider.__new__(AioSandboxProvider)
    p._lock = threading.Lock()
    p._sandboxes = {}
    p._sandbox_infos = {}
    p._thread_sandboxes = {}
    p._thread_locks = {}
    p._last_activity = {}
    p._warm_pool = {}
    p._prewarm_pool = {}
    p._ref_counts = {}
    p._slot_counts = {}
    p._shutdown_called = False
    p._idle_checker_stop = threading.Event()
    p._idle_checker_thread = None
    p._prewarm_thread = None
    p._config = {
        "image": "test-image",
        "port": 9999,
        "container_prefix": "test",
        "idle_timeout": 0,
        "replicas": 10,
        "mounts": [],
        "environment": {},
        "provisioner_url": "",
        "pre_warm_count": DEFAULT_PRE_WARM_COUNT,
        "max_threads_per_sandbox": DEFAULT_MAX_THREADS_PER_SANDBOX,
    }
    p._config.update(config_overrides)
    p._backend = backend
    return p


# ── Config defaults ───────────────────────────────────────────────────────────

def test_default_pre_warm_count():
    assert DEFAULT_PRE_WARM_COUNT == 0


def test_default_max_threads_per_sandbox():
    assert DEFAULT_MAX_THREADS_PER_SANDBOX == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py -v
```

Expected: `ImportError` — `DEFAULT_PRE_WARM_COUNT` and `DEFAULT_MAX_THREADS_PER_SANDBOX` do not exist yet.

- [ ] **Step 3: Add fields to `SandboxConfig`**

Open `backend/packages/harness/deerflow/config/sandbox_config.py`. After the `idle_timeout` field (line 51), add:

```python
    pre_warm_count: int | None = Field(
        default=None,
        description="Number of sandbox Pods to pre-warm at startup (default: 0 = disabled). Pre-warmed Pods are served instantly to new threads, eliminating provisioner cold-start.",
    )
    max_threads_per_sandbox: int | None = Field(
        default=None,
        description="Maximum number of lead-agent threads that may share one sandbox Pod (default: 1 = dedicated pod per thread). All subagents of those threads share the same Pod.",
    )
```

- [ ] **Step 4: Add constants and wire config in `aio_sandbox_provider.py`**

Open `backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py`.

At the top, after the existing `DEFAULT_REPLICAS` constant (line 42), add:

```python
DEFAULT_PRE_WARM_COUNT = 0          # disabled by default
DEFAULT_MAX_THREADS_PER_SANDBOX = 1  # dedicated pod per thread by default
```

In `_load_config()`, after the `"provisioner_url"` key, add:

```python
            "pre_warm_count": getattr(sandbox_config, "pre_warm_count", None) or DEFAULT_PRE_WARM_COUNT,
            "max_threads_per_sandbox": getattr(sandbox_config, "max_threads_per_sandbox", None) or DEFAULT_MAX_THREADS_PER_SANDBOX,
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py::test_default_pre_warm_count tests/test_sandbox_pool.py::test_default_max_threads_per_sandbox -v
```

Expected: `2 passed`

- [ ] **Step 6: Lint and format**

```bash
cd backend
make lint
make format
```

- [ ] **Step 7: Commit**

```bash
git add backend/packages/harness/deerflow/config/sandbox_config.py \
        backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py \
        backend/tests/test_sandbox_pool.py
git commit -m "feat(sandbox): add pre_warm_count and max_threads_per_sandbox config fields"
```

---

## Task 2: Add Reference Counting to `AioSandboxProvider`

Prevents the idle checker from evicting a sandbox while subagents still hold a reference.

**Files:**
- Modify: `backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py`
- Modify: `backend/tests/test_sandbox_pool.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_sandbox_pool.py`:

```python
# ── Ref counting ──────────────────────────────────────────────────────────────

def test_hold_increments_ref_count():
    backend = make_mock_backend()
    p = make_provider(backend)
    p._sandboxes["abc12345"] = MagicMock()
    p._ref_counts["abc12345"] = 1

    p.hold("abc12345")

    assert p._ref_counts["abc12345"] == 2


def test_hold_noop_for_unknown_sandbox():
    backend = make_mock_backend()
    p = make_provider(backend)

    p.hold("nonexistent")  # must not raise

    assert p._ref_counts.get("nonexistent") is None


def test_release_decrements_ref_count_and_keeps_sandbox_active():
    backend = make_mock_backend()
    p = make_provider(backend)
    info = SandboxInfo(sandbox_id="abc12345", sandbox_url="http://localhost:9000")
    p._sandboxes["abc12345"] = MagicMock()
    p._sandbox_infos["abc12345"] = info
    p._ref_counts["abc12345"] = 2

    p.release("abc12345")

    assert p._ref_counts.get("abc12345") == 1
    assert "abc12345" in p._sandboxes  # still active, not warm-pooled


def test_release_moves_to_warm_pool_when_ref_count_reaches_zero():
    backend = make_mock_backend()
    p = make_provider(backend)
    info = SandboxInfo(sandbox_id="abc12345", sandbox_url="http://localhost:9000")
    p._sandboxes["abc12345"] = MagicMock()
    p._sandbox_infos["abc12345"] = info
    p._ref_counts["abc12345"] = 1

    p.release("abc12345")

    assert "abc12345" not in p._sandboxes
    assert "abc12345" in p._warm_pool
    assert p._ref_counts.get("abc12345") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py::test_hold_increments_ref_count tests/test_sandbox_pool.py::test_hold_noop_for_unknown_sandbox tests/test_sandbox_pool.py::test_release_decrements_ref_count_and_keeps_sandbox_active tests/test_sandbox_pool.py::test_release_moves_to_warm_pool_when_ref_count_reaches_zero -v
```

Expected: `AttributeError: 'AioSandboxProvider' object has no attribute '_ref_counts'` (or `hold` not found).

- [ ] **Step 3: Add `_ref_counts` and `_slot_counts` to `__init__`**

In `AioSandboxProvider.__init__` (around line 71, after `self._warm_pool`), add:

```python
        self._ref_counts: dict[str, int] = {}   # sandbox_id → active holder count
        self._slot_counts: dict[str, int] = {}  # sandbox_id → threads assigned (for max_threads_per_sandbox)
        self._prewarm_pool: dict[str, tuple[SandboxInfo, float]] = {}  # pre-warmed ready containers
```

- [ ] **Step 4: Add `hold()` method**

After the `_get_thread_lock` method, add:

```python
    def hold(self, sandbox_id: str) -> None:
        """Increment the ref count for an active sandbox without a full acquire.

        Call this when a subagent is about to use an inherited sandbox so the
        sandbox is not moved to the warm pool while the subagent is running.
        The matching release() call (from SandboxMiddleware.after_agent) will
        decrement the ref count.

        No-op if sandbox_id is not currently active.
        """
        with self._lock:
            if sandbox_id not in self._sandboxes:
                return
            self._ref_counts[sandbox_id] = self._ref_counts.get(sandbox_id, 0) + 1
            logger.debug(f"Sandbox {sandbox_id} ref count held → {self._ref_counts[sandbox_id]}")
```

- [ ] **Step 5: Make `acquire()` set ref count to 1**

In `_create_sandbox()`, inside the `with self._lock:` block that registers the new sandbox (around line 500), add after `self._last_activity[sandbox_id] = time.time()`:

```python
            self._ref_counts[sandbox_id] = self._ref_counts.get(sandbox_id, 0) + 1
```

Do the same inside `_discover_or_create_with_lock` in the two warm-pool reclaim blocks (the `_warm_pool.pop` paths) — add after each `self._last_activity[sandbox_id] = time.time()` line:

```python
                    self._ref_counts[sandbox_id] = self._ref_counts.get(sandbox_id, 0) + 1
```

And in the `_acquire_internal` Layer 1 (in-process cache hit) block, add after `self._last_activity[existing_id] = time.time()`:

```python
                        self._ref_counts[existing_id] = self._ref_counts.get(existing_id, 0) + 1
```

- [ ] **Step 6: Make `release()` ref-count-aware**

Replace the entire body of `release()` with:

```python
    def release(self, sandbox_id: str) -> None:
        """Release a sandbox from active use.

        Decrements the ref count. Only moves the sandbox to the warm pool
        when the ref count reaches zero, which means no subagents are still
        holding a reference to this sandbox.
        """
        with self._lock:
            count = self._ref_counts.get(sandbox_id, 0)
            if count > 1:
                self._ref_counts[sandbox_id] = count - 1
                logger.info(f"Sandbox {sandbox_id} ref count decremented to {count - 1}, keeping active")
                return
            # Count is 0 or 1 — proceed with actual release to warm pool
            self._ref_counts.pop(sandbox_id, None)

            self._sandboxes.pop(sandbox_id, None)
            info = self._sandbox_infos.pop(sandbox_id, None)
            thread_ids_to_remove = [tid for tid, sid in self._thread_sandboxes.items() if sid == sandbox_id]
            for tid in thread_ids_to_remove:
                del self._thread_sandboxes[tid]
            self._last_activity.pop(sandbox_id, None)
            self._slot_counts.pop(sandbox_id, None)
            if info and sandbox_id not in self._warm_pool:
                self._warm_pool[sandbox_id] = (info, time.time())

        logger.info(f"Released sandbox {sandbox_id} to warm pool (container still running)")
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 8: Run the full test suite to check for regressions**

```bash
cd backend
make test
```

Expected: all existing tests pass.

- [ ] **Step 9: Lint and format**

```bash
cd backend
make lint
make format
```

- [ ] **Step 10: Commit**

```bash
git add backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py \
        backend/tests/test_sandbox_pool.py
git commit -m "feat(sandbox): add ref counting to prevent premature sandbox warm-pooling"
```

---

## Task 3: Hold Ref Count in `task_tool` Before Spawning Subagent

When a subagent is dispatched, the parent sandbox must stay active until the subagent's `after_agent` releases it.

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/builtins/task_tool.py`
- Create: `backend/tests/test_sandbox_task_tool.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_sandbox_task_tool.py`:

```python
"""Tests that task_tool holds the sandbox ref count before spawning a subagent."""
import threading
from unittest.mock import MagicMock, patch

import pytest

from deerflow.community.aio_sandbox.sandbox_info import SandboxInfo


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

    completed_result = MagicMock()
    completed_result.status.value = "completed"
    completed_result.ai_messages = []

    from deerflow.subagents.executor import SubagentStatus
    completed_result.status = SubagentStatus.COMPLETED
    completed_result.result = "done"

    with patch("deerflow.tools.builtins.task_tool.get_sandbox_provider", return_value=mock_provider), \
         patch("deerflow.tools.builtins.task_tool.SubagentExecutor", return_value=mock_executor), \
         patch("deerflow.tools.builtins.task_tool.get_background_task_result", return_value=completed_result), \
         patch("deerflow.tools.builtins.task_tool.cleanup_background_task"), \
         patch("deerflow.tools.builtins.task_tool.get_stream_writer", return_value=MagicMock()), \
         patch("deerflow.tools.builtins.task_tool.get_subagent_config", return_value=MagicMock(system_prompt="", timeout_seconds=300, max_turns=10)), \
         patch("deerflow.tools.builtins.task_tool.get_available_tools", return_value=[]), \
         patch("deerflow.tools.builtins.task_tool.get_skills_prompt_section", return_value=""):
        task_tool.invoke(
            {"description": "test task", "prompt": "do something", "subagent_type": "bash"},
            config={"configurable": {}},
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

    from deerflow.subagents.executor import SubagentStatus
    completed_result = MagicMock()
    completed_result.status = SubagentStatus.COMPLETED
    completed_result.result = "done"
    completed_result.ai_messages = []

    with patch("deerflow.tools.builtins.task_tool.get_sandbox_provider", return_value=mock_provider), \
         patch("deerflow.tools.builtins.task_tool.SubagentExecutor", return_value=mock_executor), \
         patch("deerflow.tools.builtins.task_tool.get_background_task_result", return_value=completed_result), \
         patch("deerflow.tools.builtins.task_tool.cleanup_background_task"), \
         patch("deerflow.tools.builtins.task_tool.get_stream_writer", return_value=MagicMock()), \
         patch("deerflow.tools.builtins.task_tool.get_subagent_config", return_value=MagicMock(system_prompt="", timeout_seconds=300, max_turns=10)), \
         patch("deerflow.tools.builtins.task_tool.get_available_tools", return_value=[]), \
         patch("deerflow.tools.builtins.task_tool.get_skills_prompt_section", return_value=""):
        task_tool.invoke(
            {"description": "test task", "prompt": "do something", "subagent_type": "bash"},
            config={"configurable": {}},
        )

    mock_provider.hold.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_task_tool.py -v
```

Expected: `AssertionError: Expected call not found` — `hold` is not called yet.

- [ ] **Step 3: Add the hold call to `task_tool.py`**

Open `backend/packages/harness/deerflow/tools/builtins/task_tool.py`.

Add the import at the top (after existing imports):

```python
from deerflow.sandbox.sandbox_provider import get_sandbox_provider
```

In the `task_tool` function body, after the `executor = SubagentExecutor(...)` block (around line 113) and before `task_id = executor.execute_async(...)`, add:

```python
    # Hold the sandbox ref count so the sandbox stays active while the
    # subagent runs in the background. SandboxMiddleware.after_agent in the
    # subagent will call release(), which decrements the count.
    if sandbox_state is not None:
        sandbox_id_to_hold = sandbox_state.get("sandbox_id")
        if sandbox_id_to_hold:
            get_sandbox_provider().hold(sandbox_id_to_hold)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_task_tool.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Run the full test suite**

```bash
cd backend
make test
```

Expected: all existing tests pass.

- [ ] **Step 6: Lint and format**

```bash
cd backend
make lint
make format
```

- [ ] **Step 7: Commit**

```bash
git add backend/packages/harness/deerflow/tools/builtins/task_tool.py \
        backend/tests/test_sandbox_task_tool.py
git commit -m "feat(sandbox): hold sandbox ref count in task_tool before spawning subagent"
```

---

## Task 4: Add Pre-Warm Pool with Background Thread

Creates sandbox Pods speculatively so new threads get a hot container with zero provisioner wait.

**Note on mounts:** The `RemoteSandboxBackend` (provisioner) ignores `extra_mounts` — it passes only `sandbox_id` and `thread_id` to the provisioner. Pre-warmed sandboxes are created with `thread_id=None`, which is safe: the provisioner Pod uses its own ephemeral filesystem for the workspace. This is the same as the current behaviour in provisioner mode.

**Files:**
- Modify: `backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py`
- Modify: `backend/tests/test_sandbox_pool.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_sandbox_pool.py`:

```python
# ── Pre-warm pool ─────────────────────────────────────────────────────────────

def test_prewarm_one_adds_to_prewarm_pool():
    backend = make_mock_backend()
    backend.create.return_value = SandboxInfo(sandbox_id="pw-aabbccdd", sandbox_url="http://localhost:9001")
    p = make_provider(backend)

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True):
        p._prewarm_one()

    assert len(p._prewarm_pool) == 1
    sid = next(iter(p._prewarm_pool))
    assert p._prewarm_pool[sid][0].sandbox_url == "http://localhost:9001"


def test_prewarm_one_destroys_sandbox_on_readiness_failure():
    backend = make_mock_backend()
    backend.create.return_value = SandboxInfo(sandbox_id="pw-fail", sandbox_url="http://localhost:9002")
    p = make_provider(backend)

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=False):
        p._prewarm_one()

    backend.destroy.assert_called_once()
    assert len(p._prewarm_pool) == 0


def test_acquire_claims_prewarmed_sandbox_without_cold_start():
    backend = make_mock_backend()
    p = make_provider(backend)
    prewarm_info = SandboxInfo(sandbox_id="pw-hotbox", sandbox_url="http://localhost:9003")
    p._prewarm_pool["pw-hotbox"] = (prewarm_info, time.time())

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True), \
         patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths:
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        sid = p.acquire("thread-new")

    backend.create.assert_not_called()  # no cold start
    assert sid is not None
    assert sid in p._sandboxes
    assert len(p._prewarm_pool) == 0  # claimed from pool
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py::test_prewarm_one_adds_to_prewarm_pool tests/test_sandbox_pool.py::test_prewarm_one_destroys_sandbox_on_readiness_failure tests/test_sandbox_pool.py::test_acquire_claims_prewarmed_sandbox_without_cold_start -v
```

Expected: `AttributeError` — `_prewarm_pool` or `_prewarm_one` not found.

- [ ] **Step 3: Implement `_prewarm_one()`**

In `aio_sandbox_provider.py`, after `_evict_oldest_warm()`, add:

```python
    # ── Pre-warm pool ────────────────────────────────────────────────────────

    def _prewarm_one(self) -> None:
        """Create one sandbox speculatively and park it in the pre-warm pool.

        Uses thread_id=None so the provisioner backend creates a Pod without
        thread-specific configuration. The Pod is claimed and re-keyed when
        a thread calls acquire().
        """
        sandbox_id = f"pw-{uuid.uuid4().hex[:8]}"
        try:
            info = self._backend.create(thread_id=None, sandbox_id=sandbox_id, extra_mounts=None)
            if wait_for_sandbox_ready(info.sandbox_url, timeout=120):
                with self._lock:
                    self._prewarm_pool[sandbox_id] = (info, time.time())
                logger.info(f"Pre-warmed sandbox {sandbox_id} ready at {info.sandbox_url}")
            else:
                self._backend.destroy(info)
                logger.warning(f"Pre-warmed sandbox {sandbox_id} failed readiness check, destroyed")
        except Exception as e:
            logger.error(f"Failed to pre-warm sandbox: {e}")

    def _prewarm_loop(self) -> None:
        target = self._config.get("pre_warm_count", DEFAULT_PRE_WARM_COUNT)
        while not self._idle_checker_stop.wait(timeout=5):
            try:
                with self._lock:
                    current = len(self._prewarm_pool)
                if current < target:
                    self._prewarm_one()
            except Exception as e:
                logger.error(f"Pre-warm loop error: {e}")

    def _start_prewarm(self) -> None:
        count = self._config.get("pre_warm_count", DEFAULT_PRE_WARM_COUNT)
        if count > 0:
            self._prewarm_thread = threading.Thread(
                target=self._prewarm_loop,
                name="sandbox-prewarm",
                daemon=True,
            )
            self._prewarm_thread.start()
            logger.info(f"Started pre-warm thread (target pool size: {count})")
```

- [ ] **Step 4: Start the pre-warm thread in `__init__`**

In `__init__`, after `self._start_idle_checker()` call (end of `__init__`), add:

```python
        # Start pre-warm thread if enabled
        self._start_prewarm()
```

- [ ] **Step 5: Claim pre-warmed sandbox in `_acquire_internal`**

In `_acquire_internal`, add a new layer between Layer 1.5 (warm pool) and Layer 2 (backend discovery). After the warm pool block for `thread_id` (around line 383), add:

```python
        # ── Layer 1.75: Pre-warm pool (hot spare, no cold-start) ──
        if thread_id:
            with self._lock:
                if self._prewarm_pool:
                    # Claim the oldest pre-warmed sandbox
                    oldest_pw_id = min(self._prewarm_pool, key=lambda sid: self._prewarm_pool[sid][1])
                    info, _ = self._prewarm_pool.pop(oldest_pw_id)
                    sandbox = AioSandbox(id=oldest_pw_id, base_url=info.sandbox_url)
                    self._sandboxes[oldest_pw_id] = sandbox
                    self._sandbox_infos[oldest_pw_id] = info
                    self._last_activity[oldest_pw_id] = time.time()
                    self._ref_counts[oldest_pw_id] = 1
                    self._thread_sandboxes[thread_id] = oldest_pw_id
                    logger.info(f"Thread {thread_id} claimed pre-warmed sandbox {oldest_pw_id} at {info.sandbox_url}")
                    return oldest_pw_id
```

- [ ] **Step 6: Include `_prewarm_pool` in shutdown**

In the `shutdown()` method, after `warm_items = list(self._warm_pool.items())`, add:

```python
            prewarm_items = list(self._prewarm_pool.items())
            self._prewarm_pool.clear()
```

After the warm pool destruction loop, add:

```python
        for sandbox_id, (info, _) in prewarm_items:
            try:
                self._backend.destroy(info)
                logger.info(f"Destroyed pre-warmed sandbox {sandbox_id} during shutdown")
            except Exception as e:
                logger.error(f"Failed to destroy pre-warmed sandbox {sandbox_id} during shutdown: {e}")
```

- [ ] **Step 7: Run all sandbox pool tests**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Run the full test suite**

```bash
cd backend
make test
```

Expected: all existing tests pass.

- [ ] **Step 9: Lint and format**

```bash
cd backend
make lint
make format
```

- [ ] **Step 10: Commit**

```bash
git add backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py \
        backend/tests/test_sandbox_pool.py
git commit -m "feat(sandbox): add pre-warm pool to eliminate provisioner cold-start"
```

---

## Task 5: Slot-Based Multi-Thread Sandbox Sharing

Allows up to `max_threads_per_sandbox` distinct lead agents to share one Pod.

**Files:**
- Modify: `backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py`
- Modify: `backend/tests/test_sandbox_pool.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_sandbox_pool.py`:

```python
# ── Slot-based sharing ────────────────────────────────────────────────────────

def _setup_active_sandbox(p: AioSandboxProvider, sandbox_id: str, thread_id: str, url: str = "http://localhost:9010") -> None:
    """Helper: inject a live sandbox into a provider as if it was acquired."""
    info = SandboxInfo(sandbox_id=sandbox_id, sandbox_url=url)
    p._sandboxes[sandbox_id] = MagicMock()
    p._sandbox_infos[sandbox_id] = info
    p._thread_sandboxes[thread_id] = sandbox_id
    p._last_activity[sandbox_id] = time.time()
    p._ref_counts[sandbox_id] = 1
    p._slot_counts[sandbox_id] = 1


def test_second_thread_shares_sandbox_when_below_max_slots():
    backend = make_mock_backend()
    p = make_provider(backend, max_threads_per_sandbox=2)
    _setup_active_sandbox(p, "shared-box", "thread-1")

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths:
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        sid = p.acquire("thread-2")

    assert sid == "shared-box"
    assert p._slot_counts["shared-box"] == 2
    assert p._ref_counts["shared-box"] == 2


def test_third_thread_gets_new_sandbox_when_max_slots_reached():
    backend = make_mock_backend()
    backend.create.return_value = SandboxInfo(sandbox_id="new-box", sandbox_url="http://localhost:9011")
    p = make_provider(backend, max_threads_per_sandbox=2)
    _setup_active_sandbox(p, "shared-box", "thread-1")
    # Simulate thread-2 already sharing shared-box
    p._thread_sandboxes["thread-2"] = "shared-box"
    p._slot_counts["shared-box"] = 2
    p._ref_counts["shared-box"] = 2

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True), \
         patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths:
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        sid = p.acquire("thread-3")

    assert sid != "shared-box"  # got a different sandbox
    backend.create.assert_called_once()


def test_slot_count_decremented_on_release():
    backend = make_mock_backend()
    p = make_provider(backend, max_threads_per_sandbox=2)
    _setup_active_sandbox(p, "shared-box", "thread-1")
    p._slot_counts["shared-box"] = 2
    p._ref_counts["shared-box"] = 2

    p.release("shared-box")

    # ref count went from 2 → 1, sandbox stays active
    assert p._ref_counts.get("shared-box") == 1
    assert "shared-box" in p._sandboxes
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py::test_second_thread_shares_sandbox_when_below_max_slots tests/test_sandbox_pool.py::test_third_thread_gets_new_sandbox_when_max_slots_reached tests/test_sandbox_pool.py::test_slot_count_decremented_on_release -v
```

Expected: first two tests fail (slot logic not implemented), third may pass already.

- [ ] **Step 3: Track slot count in `_create_sandbox`**

In `_create_sandbox()`, inside the `with self._lock:` block that registers the sandbox (around line 500), add:

```python
            self._slot_counts[sandbox_id] = self._slot_counts.get(sandbox_id, 0) + 1
```

- [ ] **Step 4: Add `_find_available_slot()` and wire into `_acquire_internal`**

After `_evict_oldest_warm()`, add:

```python
    def _find_available_slot(self) -> str | None:
        """Find an active sandbox with a free slot for multi-thread sharing.

        Returns the sandbox_id of the first active sandbox whose slot count is
        below max_threads_per_sandbox, or None if all are full (or sharing is disabled).
        """
        max_slots = self._config.get("max_threads_per_sandbox", DEFAULT_MAX_THREADS_PER_SANDBOX)
        if max_slots <= 1:
            return None
        with self._lock:
            for sid, slot_count in self._slot_counts.items():
                if slot_count < max_slots and sid in self._sandboxes:
                    return sid
        return None
```

In `_acquire_internal`, between Layer 1 (in-process cache) and Layer 1.5 (warm pool), add:

```python
        # ── Layer 1.2: Multi-thread slot sharing ──
        if thread_id:
            shared_id = self._find_available_slot()
            if shared_id is not None:
                with self._lock:
                    # Re-verify under lock (another thread may have filled the slot)
                    max_slots = self._config.get("max_threads_per_sandbox", DEFAULT_MAX_THREADS_PER_SANDBOX)
                    if self._slot_counts.get(shared_id, 0) < max_slots and shared_id in self._sandboxes:
                        self._slot_counts[shared_id] = self._slot_counts.get(shared_id, 0) + 1
                        self._ref_counts[shared_id] = self._ref_counts.get(shared_id, 0) + 1
                        self._thread_sandboxes[thread_id] = shared_id
                        self._last_activity[shared_id] = time.time()
                        logger.info(f"Thread {thread_id} joined shared sandbox {shared_id} (slots: {self._slot_counts[shared_id]}/{max_slots})")
                        return shared_id
```

- [ ] **Step 5: Run all sandbox pool tests**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_sandbox_pool.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run the full test suite**

```bash
cd backend
make test
```

Expected: all existing tests pass.

- [ ] **Step 7: Lint and format**

```bash
cd backend
make lint
make format
```

- [ ] **Step 8: Commit**

```bash
git add backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py \
        backend/tests/test_sandbox_pool.py
git commit -m "feat(sandbox): slot-based multi-thread sandbox sharing with max_threads_per_sandbox"
```

---

## Task 6: Document New Config Options in `config.example.yaml`

**Files:**
- Modify: `config.example.yaml` (project root)

- [ ] **Step 1: Find the sandbox section**

```bash
grep -n "sandbox:" config.example.yaml | head -5
```

- [ ] **Step 2: Add the two new fields under `sandbox:`**

In `config.example.yaml`, locate the `sandbox:` block and add after `idle_timeout`:

```yaml
  # Number of sandbox Pods to pre-warm at startup.
  # Pre-warmed Pods are served instantly to new threads (no provisioner wait).
  # Set to 0 (default) to disable. Recommended: 2-3 for provisioner/K8s mode.
  pre_warm_count: 0

  # Maximum number of lead-agent threads that may share one sandbox Pod.
  # All subagents of those threads share the same Pod automatically.
  # Set to 1 (default) for dedicated-pod-per-thread (original behaviour).
  # Set to 3 to allow up to 3 lead agents (and all their subagents) per Pod.
  max_threads_per_sandbox: 1
```

- [ ] **Step 3: Commit**

```bash
git add config.example.yaml
git commit -m "docs(sandbox): document pre_warm_count and max_threads_per_sandbox in config.example.yaml"
```

---

## Task 7: Final Regression Pass

- [ ] **Step 1: Run the full test suite one last time**

```bash
cd backend
make test
```

Expected: all tests pass. If any fail, read the error output and fix before continuing.

- [ ] **Step 2: Lint and format**

```bash
cd backend
make lint
make format
```

- [ ] **Step 3: Verify no new imports from `app.*` leaked into harness**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_harness_boundary.py -v
```

Expected: `1 passed`

- [ ] **Step 4: Commit if anything was auto-fixed by format**

```bash
git diff --name-only
# only commit if format changed something
git add -u
git commit -m "style: apply ruff format after sandbox pool implementation"
```

---

## Configuration Reference

After implementation, to enable both features in `config.yaml`:

```yaml
sandbox:
  use: deerflow.community.aio_sandbox:AioSandboxProvider
  provisioner_url: http://provisioner:8002
  pre_warm_count: 2          # keep 2 hot Pods ready at all times
  max_threads_per_sandbox: 3 # up to 3 lead agents share one Pod
  idle_timeout: 600
  replicas: 5
```

With `pre_warm_count: 2` and `max_threads_per_sandbox: 3`, the system serves up to `replicas × max_threads_per_sandbox = 15` concurrent lead agents from `replicas = 5` Pods, with 2 always pre-warmed for instant assignment.
