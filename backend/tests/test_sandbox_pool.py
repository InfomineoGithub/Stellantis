"""Tests for sandbox pool: ref counting, pre-warm with thread-dir structure, reactive warmup."""

import threading
import time
from unittest.mock import MagicMock, patch

from deerflow.community.aio_sandbox.aio_sandbox_provider import (
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
    p._sandbox_placeholder = {}
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
    }
    p._config.update(config_overrides)
    p._backend = backend
    return p


def _setup_active_sandbox(p: AioSandboxProvider, sandbox_id: str, thread_id: str, url: str = "http://localhost:9010") -> None:
    """Helper: inject a live sandbox into a provider as if it was acquired."""
    info = SandboxInfo(sandbox_id=sandbox_id, sandbox_url=url)
    p._sandboxes[sandbox_id] = MagicMock()
    p._sandbox_infos[sandbox_id] = info
    p._thread_sandboxes[thread_id] = sandbox_id
    p._last_activity[sandbox_id] = time.time()
    p._ref_counts[sandbox_id] = 1


# ── Config defaults ───────────────────────────────────────────────────────────


def test_default_pre_warm_count():
    assert DEFAULT_PRE_WARM_COUNT == 0


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


# ── One sandbox per agent (no slot sharing) ───────────────────────────────────


def test_each_thread_gets_dedicated_sandbox():
    """Two different threads must never share a sandbox."""
    backend = make_mock_backend()
    backend.create.side_effect = [
        SandboxInfo(sandbox_id="box-1", sandbox_url="http://localhost:9010"),
        SandboxInfo(sandbox_id="box-2", sandbox_url="http://localhost:9011"),
    ]
    p = make_provider(backend)

    with (
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True),
        patch.object(AioSandboxProvider, "_get_extra_mounts", return_value=[]),
        patch.object(AioSandboxProvider, "_trigger_warmup_if_needed"),
        patch.object(AioSandboxProvider, "_discover_or_create_with_lock", side_effect=lambda thread_id, sandbox_id: p._create_sandbox(thread_id, sandbox_id)),
    ):
        sid1 = p.acquire("thread-1")
        sid2 = p.acquire("thread-2")

    assert sid1 != sid2
    assert backend.create.call_count == 2


# ── Pre-warm pool: 3-tuple (info, placeholder_thread_id, timestamp) ───────────


def test_prewarm_one_adds_to_prewarm_pool_with_placeholder():
    """_prewarm_one must store a 3-tuple (info, placeholder_thread_id, ts)."""
    backend = make_mock_backend()
    backend.create.return_value = SandboxInfo(sandbox_id="pw-aabbccdd", sandbox_url="http://localhost:9001")
    p = make_provider(backend)

    with (
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True),
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths,
        patch.object(AioSandboxProvider, "_get_skills_mount", return_value=None),
    ):
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        mock_paths.return_value.host_base_dir = MagicMock()
        p._prewarm_one()

    assert len(p._prewarm_pool) == 1
    sid = next(iter(p._prewarm_pool))
    info, placeholder_thread_id, ts = p._prewarm_pool[sid]
    assert info.sandbox_url == "http://localhost:9001"
    assert placeholder_thread_id.startswith("prewarm-")
    assert ts > 0


def test_prewarm_one_uses_thread_dir_structure(tmp_path):
    """_prewarm_one must create dirs under threads/{placeholder}/user-data/, not prewarm/."""
    from deerflow.community.aio_sandbox.local_backend import LocalContainerBackend
    from deerflow.config.paths import Paths

    local_backend = MagicMock(spec=LocalContainerBackend)
    local_backend.is_alive.return_value = True
    p = make_provider(local_backend)
    p._backend = local_backend

    real_paths = Paths(base_dir=tmp_path)

    def fake_create(thread_id, sandbox_id, extra_mounts=None):
        return SandboxInfo(sandbox_id=sandbox_id, sandbox_url="http://localhost:9050")

    local_backend.create.side_effect = fake_create

    with (
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=True),
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths", return_value=real_paths),
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.Paths", lambda base_dir: Paths(base_dir=base_dir)),
        patch.object(AioSandboxProvider, "_get_skills_mount", return_value=None),
    ):
        p._prewarm_one()

    assert len(p._prewarm_pool) == 1
    sid = next(iter(p._prewarm_pool))
    _info, placeholder_thread_id, _ts = p._prewarm_pool[sid]

    assert placeholder_thread_id.startswith("prewarm-")
    # Old-style prewarm/ dir must NOT exist
    assert not (tmp_path / "prewarm").exists()
    # Standard threads/{placeholder}/user-data/ structure must exist
    thread_user_data = tmp_path / "threads" / placeholder_thread_id / "user-data"
    assert (thread_user_data / "workspace").exists()
    assert (thread_user_data / "uploads").exists()
    assert (thread_user_data / "outputs").exists()


def test_prewarm_one_destroys_sandbox_on_readiness_failure():
    backend = make_mock_backend()
    backend.create.return_value = SandboxInfo(sandbox_id="pw-fail", sandbox_url="http://localhost:9002")
    p = make_provider(backend)

    with (
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.wait_for_sandbox_ready", return_value=False),
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths,
        patch.object(AioSandboxProvider, "_get_skills_mount", return_value=None),
    ):
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        mock_paths.return_value.host_base_dir = MagicMock()
        p._prewarm_one()

    backend.destroy.assert_called_once()
    assert len(p._prewarm_pool) == 0


def test_acquire_claims_prewarmed_sandbox_without_cold_start():
    backend = make_mock_backend()
    p = make_provider(backend)
    prewarm_info = SandboxInfo(sandbox_id="pw-hotbox", sandbox_url="http://localhost:9003")
    # 3-tuple: (info, placeholder_thread_id, timestamp)
    p._prewarm_pool["pw-hotbox"] = (prewarm_info, "prewarm-deadbeef", time.time())

    with (
        patch.object(AioSandboxProvider, "_migrate_prewarm_dirs"),
        patch.object(AioSandboxProvider, "_trigger_warmup_if_needed"),
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths,
    ):
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        sid = p.acquire("thread-new")

    backend.create.assert_not_called()  # no cold start
    assert sid == "pw-hotbox"
    assert sid in p._sandboxes
    assert len(p._prewarm_pool) == 0  # claimed from pool


def test_acquire_calls_migrate_on_prewarm_claim():
    """Claiming a pre-warmed sandbox must call _migrate_prewarm_dirs."""
    backend = make_mock_backend()
    p = make_provider(backend)
    prewarm_info = SandboxInfo(sandbox_id="pw-migrate", sandbox_url="http://localhost:9004")
    p._prewarm_pool["pw-migrate"] = (prewarm_info, "prewarm-abc12345", time.time())

    with (
        patch.object(AioSandboxProvider, "_migrate_prewarm_dirs") as mock_migrate,
        patch.object(AioSandboxProvider, "_trigger_warmup_if_needed"),
        patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths") as mock_paths,
    ):
        mock_paths.return_value.thread_dir.return_value = MagicMock()
        mock_paths.return_value.ensure_thread_dirs.return_value = None
        p.acquire("thread-real")

    mock_migrate.assert_called_once_with("prewarm-abc12345", "thread-real", "pw-migrate")


# ── Cleanup of dead pre-warm containers ───────────────────────────────────────


def test_cleanup_dead_prewarm_removes_dead_entries(tmp_path):
    """Dead pre-warm pool entries must be removed and placeholder dirs cleaned up."""
    from deerflow.config.paths import Paths

    backend = make_mock_backend()
    backend.is_alive.return_value = False
    p = make_provider(backend)

    real_paths = Paths(base_dir=tmp_path)
    placeholder = "prewarm-deadtest"
    prewarm_info = SandboxInfo(sandbox_id="pw-dead", sandbox_url="http://localhost:9005")
    p._prewarm_pool["pw-dead"] = (prewarm_info, placeholder, time.time())

    placeholder_dir = real_paths.thread_dir(placeholder)
    placeholder_dir.mkdir(parents=True, exist_ok=True)

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths", return_value=real_paths):
        p._cleanup_dead_prewarm()

    assert len(p._prewarm_pool) == 0
    backend.destroy.assert_called_once_with(prewarm_info)
    assert not placeholder_dir.exists()


# ── Reactive warmup trigger ────────────────────────────────────────────────────


def test_trigger_warmup_fires_when_below_replicas():
    backend = make_mock_backend()
    p = make_provider(backend, pre_warm_count=2, replicas=3)
    _setup_active_sandbox(p, "box-1", "thread-1")

    fired = []

    def fake_thread(*args, **kwargs):
        t = MagicMock()
        fired.append(kwargs.get("target") or (args[0] if args else None))
        return t

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.threading.Thread", side_effect=fake_thread):
        p._trigger_warmup_if_needed()

    assert len(fired) == 1


def test_trigger_warmup_does_not_fire_at_replicas_limit():
    backend = make_mock_backend()
    p = make_provider(backend, pre_warm_count=2, replicas=2)
    _setup_active_sandbox(p, "box-1", "thread-1")
    _setup_active_sandbox(p, "box-2", "thread-2")

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.threading.Thread") as mock_thread:
        p._trigger_warmup_if_needed()

    mock_thread.assert_not_called()


def test_trigger_warmup_does_not_fire_when_warm_pool_fills_replicas():
    """Warm-pool containers count toward the replica limit."""
    backend = make_mock_backend()
    p = make_provider(backend, pre_warm_count=2, replicas=2)
    # 1 active + 1 warm = 2 total = replicas → must NOT fire
    _setup_active_sandbox(p, "box-1", "thread-1")
    warm_info = SandboxInfo(sandbox_id="box-warm", sandbox_url="http://localhost:9020")
    import time as _time

    p._warm_pool["box-warm"] = (warm_info, _time.time())

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.threading.Thread") as mock_thread:
        p._trigger_warmup_if_needed()

    mock_thread.assert_not_called()


def test_trigger_warmup_disabled_when_pre_warm_count_zero():
    backend = make_mock_backend()
    p = make_provider(backend, pre_warm_count=0, replicas=5)

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.threading.Thread") as mock_thread:
        p._trigger_warmup_if_needed()

    mock_thread.assert_not_called()


# ── Migrate prewarm dirs (local backend) ──────────────────────────────────────


def test_migrate_prewarm_dirs_renames_tree(tmp_path):
    """_migrate_prewarm_dirs must create a symlink/junction threads/{real}/ → threads/{placeholder}/."""
    import sys

    from deerflow.community.aio_sandbox.local_backend import LocalContainerBackend
    from deerflow.config.paths import Paths

    local_backend = MagicMock(spec=LocalContainerBackend)
    p = make_provider(local_backend)
    p._backend = local_backend

    real_paths = Paths(base_dir=tmp_path)
    placeholder = "prewarm-migrate1"
    real_thread = "real-thread-abc"

    real_paths.ensure_thread_dirs(placeholder)
    src_workspace = real_paths.sandbox_work_dir(placeholder)
    (src_workspace / "test.txt").write_text("hello")

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths", return_value=real_paths):
        p._migrate_prewarm_dirs(placeholder, real_thread, "pw-abc123")

    # Placeholder dir must still exist (container bind mounts point there)
    assert real_paths.thread_dir(placeholder).exists()
    # The real thread dir must exist (as symlink or junction)
    dst = real_paths.thread_dir(real_thread)
    assert dst.exists() or dst.is_symlink()
    # Files must be accessible via the real thread path
    if sys.platform == "win32":
        # Junction: files directly accessible
        assert (real_paths.sandbox_work_dir(real_thread) / "test.txt").read_text() == "hello"
    else:
        # Symlink: files accessible via resolved path
        assert dst.is_symlink()
        assert (dst / "user-data" / "workspace" / "test.txt").read_text() == "hello"
    # Mapping must be recorded
    assert "pw-abc123" in p._sandbox_placeholder
    assert p._sandbox_placeholder["pw-abc123"] == (placeholder, real_thread)


def test_migrate_prewarm_dirs_skips_when_dst_exists(tmp_path):
    """_migrate_prewarm_dirs must not error when destination already exists."""
    from deerflow.community.aio_sandbox.local_backend import LocalContainerBackend
    from deerflow.config.paths import Paths

    local_backend = MagicMock(spec=LocalContainerBackend)
    p = make_provider(local_backend)
    p._backend = local_backend

    real_paths = Paths(base_dir=tmp_path)
    placeholder = "prewarm-skip1"
    real_thread = "real-thread-exists"

    real_paths.ensure_thread_dirs(placeholder)
    real_paths.ensure_thread_dirs(real_thread)

    with patch("deerflow.community.aio_sandbox.aio_sandbox_provider.get_paths", return_value=real_paths):
        p._migrate_prewarm_dirs(placeholder, real_thread, "pw-skip")  # must not raise

    assert real_paths.thread_dir(real_thread).exists()
    # No placeholder mapping recorded when dst already existed
    assert "pw-skip" not in p._sandbox_placeholder


def test_migrate_prewarm_dirs_calls_reassign_for_remote_backend():
    """_migrate_prewarm_dirs must call backend.reassign() for remote backends."""
    backend = make_mock_backend()
    p = make_provider(backend)
    backend.reassign = MagicMock()

    p._migrate_prewarm_dirs("prewarm-remote1", "thread-real", "pw-remote")

    backend.reassign.assert_called_once_with("pw-remote", "thread-real")


def test_migrate_prewarm_dirs_tolerates_reassign_failure():
    """_migrate_prewarm_dirs must log a warning (not raise) when reassign fails."""
    backend = make_mock_backend()
    p = make_provider(backend)
    backend.reassign = MagicMock(side_effect=RuntimeError("provisioner unavailable"))

    p._migrate_prewarm_dirs("prewarm-err", "thread-real", "pw-err")  # must not raise


# ── Pre-warm skips when total >= pre_warm_count ───────────────────────────────


def test_prewarm_skips_when_active_sandbox_exists():
    """_cleanup_dead_prewarm should not create new containers (that is trigger's job)."""
    backend = make_mock_backend()
    p = make_provider(backend, pre_warm_count=1, replicas=5)
    _setup_active_sandbox(p, "pw-claimed", "thread-1")

    p._cleanup_dead_prewarm()
    with p._lock:
        current_prewarm = len(p._prewarm_pool)
        current_active = len(p._sandboxes)

    assert current_prewarm + current_active >= 1
    backend.create.assert_not_called()
