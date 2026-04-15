"""Tests for sandbox pool sharing: ref counting, pre-warm, slot-based acquisition."""

import threading
import time
from unittest.mock import MagicMock, patch

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

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True), patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths:
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        sid = p.acquire("thread-new")

    backend.create.assert_not_called()  # no cold start
    assert sid is not None
    assert sid in p._sandboxes
    assert len(p._prewarm_pool) == 0  # claimed from pool


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

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True), patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths:
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
