"""Tests for sandbox pool sharing: ref counting, pre-warm, slot-based acquisition."""

import threading
from unittest.mock import MagicMock

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
