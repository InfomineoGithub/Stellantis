# Adapter Tool System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a path-based adapter layer over RAGFlow and Cloudflare MCP tools so the model works with file paths and the system handles all base64 encoding/decoding internally.

**Architecture:** A new `tools/adapters/` package in the harness provides self-contained adapter modules, each exposing `get_tools(adapter_config, mcp_tools) -> list[BaseTool]`. An `AdapterConfig` Pydantic model added to `ExtensionsConfig` drives which adapters are enabled and whether raw MCP tools are hidden. The loader is called from `get_available_tools()` after MCP tools are fetched.

**Path resolution:** The model always works with virtual paths (`/mnt/user-data/workspace`, `/mnt/user-data/outputs`). Actual host paths live in `runtime.state["thread_data"]` (populated by `ThreadDataMiddleware`). All adapter tools accept `runtime: ToolRuntime`, translate input paths via `replace_virtual_path(path, thread_data)` before use, and mask output paths back to virtual via `mask_local_paths_in_output(result, thread_data)` before returning. The `_do_*` implementation functions always receive and return actual host paths — only the `make_*_tool` wrappers do translation.

**Tech Stack:** Python 3.12, LangChain `BaseTool` + `@tool` decorator, Pydantic v2, FastAPI, httpx, Next.js (React Query + TypeScript), JSON config.

---

## File Map

**Create:**
- `backend/packages/harness/deerflow/tools/adapters/__init__.py` — adapter registry + `load_adapter_tools()`
- `backend/packages/harness/deerflow/tools/adapters/ragflow/__init__.py` — `get_tools()` for ragflow adapter
- `backend/packages/harness/deerflow/tools/adapters/ragflow/upload.py` — `_do_upload()` + `make_upload_tool()`
- `backend/packages/harness/deerflow/tools/adapters/ragflow/download.py` — `_do_download()` + `make_download_tool()`
- `backend/packages/harness/deerflow/tools/adapters/fetch_url/__init__.py` — `get_tools()` for fetch_url adapter
- `backend/packages/harness/deerflow/tools/adapters/fetch_url/tool.py` — `_detect_type()`, `_do_fetch()`, `make_fetch_url_tool()`
- `backend/app/gateway/routers/adapters.py` — GET/PUT `/api/adapters/config`
- `frontend/src/core/adapters/types.ts` — `AdapterConfig`, `AdaptersConfig`
- `frontend/src/core/adapters/api.ts` — `loadAdaptersConfig()`, `updateAdaptersConfig()`
- `frontend/src/core/adapters/hooks.ts` — `useAdaptersConfig()`, `useUpdateAdapter()`
- `backend/tests/test_adapter_config.py`
- `backend/tests/test_adapter_loader.py`
- `backend/tests/test_ragflow_upload_tool.py`
- `backend/tests/test_ragflow_download_tool.py`
- `backend/tests/test_fetch_url_tool.py`
- `backend/tests/test_adapters_router.py`

**Modify:**
- `backend/packages/harness/deerflow/config/extensions_config.py` — add `AdapterConfig`, `adapters` field
- `backend/packages/harness/deerflow/tools/tools.py` — call `load_adapter_tools()`
- `backend/app/gateway/app.py` — register adapters router
- `backend/app/gateway/routers/mcp.py` — preserve `adapters` key when writing config
- `frontend/src/components/workspace/settings/tool-settings-page.tsx` — render adapter cards
- `extensions_config.json` (project root) — add `adapters` section

---

## Task 1: Add `AdapterConfig` to `ExtensionsConfig`

**Files:**
- Modify: `backend/packages/harness/deerflow/config/extensions_config.py`
- Create: `backend/tests/test_adapter_config.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_adapter_config.py
import json
import pytest
from deerflow.config.extensions_config import ExtensionsConfig, AdapterConfig


def test_adapter_config_defaults():
    cfg = AdapterConfig()
    assert cfg.enabled is False
    assert cfg.wraps_server is None
    assert cfg.hide_wrapped_tools is False
    assert cfg.tool_mappings == {}


def test_extensions_config_parses_adapters():
    raw = {
        "mcpServers": {},
        "adapters": {
            "ragflow_builtin": {
                "enabled": True,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": False,
                "tool_mappings": {
                    "upload": "ragflow__upload_with_metadata",
                    "download": "ragflow__download_attachment",
                },
            }
        },
    }
    config = ExtensionsConfig.model_validate(raw)
    assert "ragflow_builtin" in config.adapters
    adapter = config.adapters["ragflow_builtin"]
    assert adapter.enabled is True
    assert adapter.wraps_server == "ragflow"
    assert adapter.tool_mappings["upload"] == "ragflow__upload_with_metadata"


def test_extensions_config_adapters_default_empty():
    raw = {"mcpServers": {}}
    config = ExtensionsConfig.model_validate(raw)
    assert config.adapters == {}
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend
PYTHONPATH=. uv run pytest tests/test_adapter_config.py -v
```

Expected: `FAILED` — `AdapterConfig` not defined yet.

- [ ] **Step 3: Add `AdapterConfig` and `adapters` field**

Open `backend/packages/harness/deerflow/config/extensions_config.py`. After the `SkillStateConfig` class (around line 52), add:

```python
class AdapterConfig(BaseModel):
    enabled: bool = False
    wraps_server: str | None = None
    hide_wrapped_tools: bool = False
    tool_mappings: dict[str, str] = Field(default_factory=dict)
```

In `ExtensionsConfig`, add the `adapters` field after the `skills` field:

```python
adapters: dict[str, AdapterConfig] = Field(default_factory=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

```
PYTHONPATH=. uv run pytest tests/test_adapter_config.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/config/extensions_config.py backend/tests/test_adapter_config.py
git commit -m "feat: add AdapterConfig to ExtensionsConfig"
```

---

## Task 2: Adapter loader `tools/adapters/__init__.py`

**Files:**
- Create: `backend/packages/harness/deerflow/tools/adapters/__init__.py`
- Create: `backend/tests/test_adapter_loader.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_adapter_loader.py
import importlib
from unittest.mock import MagicMock, patch
from deerflow.config.extensions_config import AdapterConfig, ExtensionsConfig


def _make_mcp_tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


def _make_config(adapters: dict) -> ExtensionsConfig:
    return ExtensionsConfig.model_validate({"mcpServers": {}, "adapters": adapters})


def test_load_adapter_tools_returns_empty_when_no_adapters():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config({})
    adapter_tools, visible_mcp = load_adapter_tools(config, [])
    assert adapter_tools == []
    assert visible_mcp == []


def test_load_adapter_tools_skips_disabled_adapters():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config(
        {"ragflow_builtin": {"enabled": False, "wraps_server": "ragflow", "tool_mappings": {}}}
    )
    mcp_tools = [_make_mcp_tool("ragflow__upload_with_metadata")]
    adapter_tools, visible_mcp = load_adapter_tools(config, mcp_tools)
    assert adapter_tools == []
    assert len(visible_mcp) == 1  # MCP tool not filtered when adapter disabled


def test_load_adapter_tools_hides_wrapped_tools_when_flag_set():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config(
        {
            "ragflow_builtin": {
                "enabled": True,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": True,
                "tool_mappings": {
                    "upload": "ragflow__upload_with_metadata",
                    "download": "ragflow__download_attachment",
                },
            }
        }
    )
    mcp_tools = [
        _make_mcp_tool("ragflow__upload_with_metadata"),
        _make_mcp_tool("ragflow__download_attachment"),
        _make_mcp_tool("cloudflare__browser_render_markdown"),
    ]

    with patch("deerflow.tools.adapters.ragflow.get_tools", return_value=[MagicMock()]):
        adapter_tools, visible_mcp = load_adapter_tools(config, mcp_tools)

    # ragflow__ tools filtered, cloudflare tool kept
    assert all(not t.name.startswith("ragflow__") for t in visible_mcp)
    assert any(t.name == "cloudflare__browser_render_markdown" for t in visible_mcp)


def test_load_adapter_tools_keeps_all_mcp_when_hide_false():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config(
        {
            "ragflow_builtin": {
                "enabled": True,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": False,
                "tool_mappings": {
                    "upload": "ragflow__upload_with_metadata",
                    "download": "ragflow__download_attachment",
                },
            }
        }
    )
    mcp_tools = [_make_mcp_tool("ragflow__upload_with_metadata")]

    with patch("deerflow.tools.adapters.ragflow.get_tools", return_value=[]):
        _, visible_mcp = load_adapter_tools(config, mcp_tools)

    assert len(visible_mcp) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
PYTHONPATH=. uv run pytest tests/test_adapter_loader.py -v
```

Expected: `FAILED` — module not found.

- [ ] **Step 3: Create `tools/adapters/__init__.py`**

```python
# backend/packages/harness/deerflow/tools/adapters/__init__.py
import importlib
from langchain.tools import BaseTool
from deerflow.config.extensions_config import ExtensionsConfig

ADAPTER_REGISTRY: dict[str, str] = {
    "ragflow_builtin": "deerflow.tools.adapters.ragflow",
    "fetch_url": "deerflow.tools.adapters.fetch_url",
}


def load_adapter_tools(
    extensions_config: ExtensionsConfig,
    mcp_tools: list[BaseTool],
) -> tuple[list[BaseTool], list[BaseTool]]:
    """Return (adapter_tools, visible_mcp_tools).

    visible_mcp_tools is mcp_tools with wrapped-server tools removed
    for any adapter that has hide_wrapped_tools=True.
    """
    adapter_tools: list[BaseTool] = []
    visible_mcp_tools: list[BaseTool] = list(mcp_tools)

    for adapter_name, adapter_config in extensions_config.adapters.items():
        if not adapter_config.enabled:
            continue

        module_path = ADAPTER_REGISTRY.get(adapter_name)
        if module_path is None:
            continue

        module = importlib.import_module(module_path)
        adapter_tools.extend(module.get_tools(adapter_config, mcp_tools))

        if adapter_config.hide_wrapped_tools and adapter_config.wraps_server:
            prefix = adapter_config.wraps_server + "__"
            visible_mcp_tools = [t for t in visible_mcp_tools if not t.name.startswith(prefix)]

    return adapter_tools, visible_mcp_tools
```

Also create placeholder `ragflow/__init__.py` and `fetch_url/__init__.py` so imports don't fail during loader tests:

```python
# backend/packages/harness/deerflow/tools/adapters/ragflow/__init__.py
from deerflow.config.extensions_config import AdapterConfig
from langchain.tools import BaseTool


def get_tools(adapter_config: AdapterConfig, mcp_tools: list[BaseTool]) -> list[BaseTool]:
    return []
```

```python
# backend/packages/harness/deerflow/tools/adapters/fetch_url/__init__.py
from deerflow.config.extensions_config import AdapterConfig
from langchain.tools import BaseTool


def get_tools(adapter_config: AdapterConfig, mcp_tools: list[BaseTool]) -> list[BaseTool]:
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

```
PYTHONPATH=. uv run pytest tests/test_adapter_loader.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/adapters/ backend/tests/test_adapter_loader.py
git commit -m "feat: add adapter loader with registry and hide_wrapped_tools filtering"
```

---

## Task 3: RAGFlow upload tool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/adapters/ragflow/upload.py`
- Create: `backend/tests/test_ragflow_upload_tool.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ragflow_upload_tool.py
import base64
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest


def _make_upload_mcp(return_value: str) -> MagicMock:
    mock = MagicMock()
    mock.invoke.return_value = return_value
    return mock


def test_upload_reads_file_and_encodes_base64(tmp_path):
    from deerflow.tools.adapters.ragflow.upload import _do_upload

    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"fake pdf content")
    mock_mcp = _make_upload_mcp(json.dumps({"id": "doc-123", "name": "report.pdf", "progress": 0.0}))

    result = _do_upload(
        path=str(test_file),
        dataset_id="ds-456",
        filename=None,
        metadata=None,
        upload_mcp=mock_mcp,
    )

    call_args = mock_mcp.invoke.call_args[0][0]
    assert call_args["dataset_id"] == "ds-456"
    assert call_args["filename"] == "report.pdf"
    assert base64.b64decode(call_args["file_content_base64"]) == b"fake pdf content"
    assert call_args["metadata"] is None
    assert json.loads(result)["id"] == "doc-123"


def test_upload_uses_custom_filename(tmp_path):
    from deerflow.tools.adapters.ragflow.upload import _do_upload

    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"data")
    mock_mcp = _make_upload_mcp(json.dumps({"id": "doc-999"}))

    _do_upload(str(test_file), "ds-1", filename="custom_name.pdf", metadata=None, upload_mcp=mock_mcp)

    call_args = mock_mcp.invoke.call_args[0][0]
    assert call_args["filename"] == "custom_name.pdf"


def test_upload_passes_metadata(tmp_path):
    from deerflow.tools.adapters.ragflow.upload import _do_upload

    test_file = tmp_path / "doc.txt"
    test_file.write_bytes(b"hello")
    mock_mcp = _make_upload_mcp(json.dumps({"id": "doc-1"}))
    meta = {"category": "finance", "year": 2024}

    _do_upload(str(test_file), "ds-1", filename=None, metadata=meta, upload_mcp=mock_mcp)

    call_args = mock_mcp.invoke.call_args[0][0]
    assert call_args["metadata"] == meta


def test_make_upload_tool_returns_basetool():
    from deerflow.tools.adapters.ragflow.upload import make_upload_tool
    from langchain.tools import BaseTool

    mock_mcp = MagicMock()
    tool = make_upload_tool(mock_mcp)
    assert isinstance(tool, BaseTool)
    assert tool.name == "ragflow_upload"
    # runtime is LangGraph-injected — must NOT appear in the LLM-visible schema
    assert "runtime" not in tool.args


def test_make_upload_tool_translates_virtual_path(tmp_path):
    """make_upload_tool wrapper must resolve /mnt/user-data/ virtual paths."""
    from types import SimpleNamespace
    from deerflow.tools.adapters.ragflow.upload import make_upload_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "doc.pdf"
    test_file.write_bytes(b"content")

    thread_data = {
        "workspace_path": str(workspace),
        "uploads_path": str(tmp_path / "uploads"),
        "outputs_path": str(tmp_path / "outputs"),
    }
    runtime = SimpleNamespace(state={"thread_data": thread_data}, context={})

    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = '{"id": "doc-1"}'
    tool = make_upload_tool(mock_mcp)

    # Tool is called with virtual path; should resolve to actual workspace file
    result = tool.func(
        runtime=runtime,
        path="/mnt/user-data/workspace/doc.pdf",
        dataset_id="ds-1",
    )

    call_args = mock_mcp.invoke.call_args[0][0]
    # Actual host path was passed to MCP — not the virtual path
    assert "/mnt/user-data" not in call_args.get("file_content_base64", "")
    assert result  # masked output returned
```

- [ ] **Step 2: Run test to verify it fails**

```
PYTHONPATH=. uv run pytest tests/test_ragflow_upload_tool.py -v
```

Expected: `FAILED` — module not found.

- [ ] **Step 3: Create `ragflow/upload.py`**

```python
# backend/packages/harness/deerflow/tools/adapters/ragflow/upload.py
import base64
import json
from pathlib import Path
from langchain.tools import BaseTool, tool, ToolRuntime


def _do_upload(
    path: str,
    dataset_id: str,
    filename: str | None,
    metadata: dict | None,
    upload_mcp: BaseTool,
) -> str:
    file_path = Path(path)
    resolved_filename = filename or file_path.name
    file_bytes = file_path.read_bytes()
    content_b64 = base64.b64encode(file_bytes).decode()
    result = upload_mcp.invoke(
        {
            "dataset_id": dataset_id,
            "filename": resolved_filename,
            "file_content_base64": content_b64,
            "metadata": metadata,
        }
    )
    return result if isinstance(result, str) else json.dumps(result)


def make_upload_tool(upload_mcp: BaseTool) -> BaseTool:
    @tool("ragflow_upload", parse_docstring=True)
    def ragflow_upload(
        runtime: ToolRuntime,
        path: str,
        dataset_id: str,
        filename: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Upload a local file to a RAGFlow dataset by file path.

        Use this instead of upload_with_metadata when the file already exists
        in the agent workspace. Handles base64 encoding internally.

        Args:
            path: Path to the file (use /mnt/user-data/workspace/... paths).
            dataset_id: Target RAGFlow dataset (knowledge base) ID.
            filename: Override filename sent to RAGFlow (defaults to the file's basename).
            metadata: Optional metadata dict (str/int/float/bool/list values only).

        Returns:
            JSON string with uploaded document info: id, name, progress (0.0–1.0), etc.
        """
        from deerflow.sandbox.tools import get_thread_data, replace_virtual_path, mask_local_paths_in_output

        thread_data = get_thread_data(runtime)
        actual_path = replace_virtual_path(path, thread_data)
        result = _do_upload(actual_path, dataset_id, filename, metadata, upload_mcp)
        return mask_local_paths_in_output(result, thread_data)

    return ragflow_upload
```

- [ ] **Step 4: Run tests to verify they pass**

```
PYTHONPATH=. uv run pytest tests/test_ragflow_upload_tool.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/adapters/ragflow/upload.py backend/tests/test_ragflow_upload_tool.py
git commit -m "feat: add ragflow_upload built-in tool with path-based interface"
```

---

## Task 4: RAGFlow download tool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/adapters/ragflow/download.py`
- Create: `backend/tests/test_ragflow_download_tool.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ragflow_download_tool.py
import base64
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest


def _make_download_mcp(content_bytes: bytes) -> MagicMock:
    mock = MagicMock()
    mock.invoke.return_value = json.dumps(
        {"content_base64": base64.b64encode(content_bytes).decode()}
    )
    return mock


def test_download_saves_file_to_output_dir(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    content = b"fake file content"
    mock_mcp = _make_download_mcp(content)
    output_dir = tmp_path / "downloads"

    result_str = _do_download(
        doc_ids=["doc-123"],
        output_dir=str(output_dir),
        filenames=["report.pdf"],
        download_mcp=mock_mcp,
    )

    saved_paths = json.loads(result_str)
    assert len(saved_paths) == 1
    saved = Path(saved_paths[0])
    assert saved.exists()
    assert saved.read_bytes() == content
    assert saved.name == "report.pdf"


def test_download_multiple_docs(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    mock_mcp = _make_download_mcp(b"data")
    output_dir = tmp_path / "out"

    result_str = _do_download(
        doc_ids=["doc-1", "doc-2"],
        output_dir=str(output_dir),
        filenames=["a.pdf", "b.docx"],
        download_mcp=mock_mcp,
    )

    saved_paths = json.loads(result_str)
    assert len(saved_paths) == 2
    assert mock_mcp.invoke.call_count == 2


def test_download_falls_back_to_doc_id_as_filename(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    mock_mcp = _make_download_mcp(b"data")
    output_dir = tmp_path / "out"

    result_str = _do_download(
        doc_ids=["doc-abc"],
        output_dir=str(output_dir),
        filenames=None,
        download_mcp=mock_mcp,
    )

    saved_paths = json.loads(result_str)
    assert Path(saved_paths[0]).name == "doc-abc"


def test_download_creates_output_dir_if_missing(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    mock_mcp = _make_download_mcp(b"x")
    output_dir = tmp_path / "nested" / "dir"
    assert not output_dir.exists()

    _do_download(["doc-1"], str(output_dir), ["f.txt"], mock_mcp)

    assert output_dir.exists()


def test_make_download_tool_returns_basetool():
    from deerflow.tools.adapters.ragflow.download import make_download_tool
    from langchain.tools import BaseTool

    tool = make_download_tool(MagicMock())
    assert isinstance(tool, BaseTool)
    assert tool.name == "ragflow_download"
    assert "runtime" not in tool.args


def test_make_download_tool_translates_virtual_output_dir(tmp_path):
    """make_download_tool wrapper must resolve /mnt/user-data/ virtual output_dir."""
    import base64
    import json
    from types import SimpleNamespace
    from deerflow.tools.adapters.ragflow.download import make_download_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    thread_data = {
        "workspace_path": str(workspace),
        "uploads_path": str(tmp_path / "uploads"),
        "outputs_path": str(tmp_path / "outputs"),
    }
    runtime = SimpleNamespace(state={"thread_data": thread_data}, context={})

    content = b"file bytes"
    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = json.dumps(
        {"content_base64": base64.b64encode(content).decode()}
    )
    tool = make_download_tool(mock_mcp)

    result = tool.func(
        runtime=runtime,
        doc_ids=["doc-1"],
        output_dir="/mnt/user-data/workspace",
        filenames=["report.pdf"],
    )

    # File must be saved inside actual workspace dir
    saved = workspace / "report.pdf"
    assert saved.exists()
    assert saved.read_bytes() == content
    # Returned path must be virtual (masked)
    assert "/mnt/user-data" in result
```

- [ ] **Step 2: Run test to verify it fails**

```
PYTHONPATH=. uv run pytest tests/test_ragflow_download_tool.py -v
```

Expected: `FAILED` — module not found.

- [ ] **Step 3: Create `ragflow/download.py`**

```python
# backend/packages/harness/deerflow/tools/adapters/ragflow/download.py
import base64
import json
from pathlib import Path
from langchain.tools import BaseTool, tool, ToolRuntime


def _do_download(
    doc_ids: list[str],
    output_dir: str,
    filenames: list[str] | None,
    download_mcp: BaseTool,
) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []

    for i, doc_id in enumerate(doc_ids):
        result_str = download_mcp.invoke({"doc_id": doc_id})
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
        raw_bytes = base64.b64decode(result["content_base64"])
        fname = (filenames[i] if filenames and i < len(filenames) else None) or doc_id
        file_path = output_path / fname
        file_path.write_bytes(raw_bytes)
        saved_paths.append(str(file_path))

    return json.dumps(saved_paths)


def make_download_tool(download_mcp: BaseTool) -> BaseTool:
    @tool("ragflow_download", parse_docstring=True)
    def ragflow_download(
        runtime: ToolRuntime,
        doc_ids: list[str],
        output_dir: str,
        filenames: list[str] | None = None,
    ) -> str:
        """Download one or more RAGFlow documents by ID to a local directory.

        Use this instead of download_attachment when you need files saved to disk.
        Handles base64 decoding and file writing internally. To get document IDs,
        use list_docs or retrieve results from a prior ragflow_upload call.

        Args:
            doc_ids: List of RAGFlow document IDs to download.
            output_dir: Directory to save files into (use /mnt/user-data/workspace/... paths).
            filenames: Optional list of filenames parallel to doc_ids. If omitted,
                       the doc_id is used as the filename (no extension).

        Returns:
            JSON array of saved file paths (as /mnt/user-data/... virtual paths).
        """
        from deerflow.sandbox.tools import get_thread_data, replace_virtual_path, mask_local_paths_in_output

        thread_data = get_thread_data(runtime)
        actual_output_dir = replace_virtual_path(output_dir, thread_data)
        result = _do_download(doc_ids, actual_output_dir, filenames, download_mcp)
        return mask_local_paths_in_output(result, thread_data)

    return ragflow_download
```

- [ ] **Step 4: Run tests to verify they pass**

```
PYTHONPATH=. uv run pytest tests/test_ragflow_download_tool.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/adapters/ragflow/download.py backend/tests/test_ragflow_download_tool.py
git commit -m "feat: add ragflow_download built-in tool with batch download and base64 decoding"
```

---

## Task 5: Wire RAGFlow adapter `get_tools()`

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/adapters/ragflow/__init__.py`

- [ ] **Step 1: Update `ragflow/__init__.py` to look up MCP tools and return both adapter tools**

Replace the placeholder content with:

```python
# backend/packages/harness/deerflow/tools/adapters/ragflow/__init__.py
from langchain.tools import BaseTool
from deerflow.config.extensions_config import AdapterConfig
from deerflow.tools.adapters.ragflow.upload import make_upload_tool
from deerflow.tools.adapters.ragflow.download import make_download_tool


def get_tools(adapter_config: AdapterConfig, mcp_tools: list[BaseTool]) -> list[BaseTool]:
    mcp_by_name = {t.name: t for t in mcp_tools}

    upload_name = adapter_config.tool_mappings.get("upload")
    download_name = adapter_config.tool_mappings.get("download")

    tools: list[BaseTool] = []

    if upload_name and upload_name in mcp_by_name:
        tools.append(make_upload_tool(mcp_by_name[upload_name]))

    if download_name and download_name in mcp_by_name:
        tools.append(make_download_tool(mcp_by_name[download_name]))

    return tools
```

- [ ] **Step 2: Add integration test to `test_adapter_loader.py`**

Append to `backend/tests/test_adapter_loader.py`:

```python
def test_ragflow_adapter_get_tools_returns_two_tools():
    from deerflow.tools.adapters.ragflow import get_tools
    from deerflow.config.extensions_config import AdapterConfig

    cfg = AdapterConfig(
        enabled=True,
        wraps_server="ragflow",
        tool_mappings={
            "upload": "ragflow__upload_with_metadata",
            "download": "ragflow__download_attachment",
        },
    )
    mcp_tools = [
        _make_mcp_tool("ragflow__upload_with_metadata"),
        _make_mcp_tool("ragflow__download_attachment"),
    ]
    tools = get_tools(cfg, mcp_tools)
    tool_names = [t.name for t in tools]
    assert "ragflow_upload" in tool_names
    assert "ragflow_download" in tool_names


def test_ragflow_adapter_skips_missing_mcp_tools():
    from deerflow.tools.adapters.ragflow import get_tools
    from deerflow.config.extensions_config import AdapterConfig

    cfg = AdapterConfig(
        enabled=True,
        tool_mappings={"upload": "ragflow__upload_with_metadata"},
    )
    tools = get_tools(cfg, [])  # no MCP tools available
    assert tools == []
```

- [ ] **Step 3: Run tests**

```
PYTHONPATH=. uv run pytest tests/test_adapter_loader.py -v
```

Expected: all PASSED (previous 4 + new 2 = 6 PASSED).

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/deerflow/tools/adapters/ragflow/__init__.py backend/tests/test_adapter_loader.py
git commit -m "feat: wire ragflow adapter get_tools with upload and download"
```

---

## Task 6: `fetch_url` tool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/adapters/fetch_url/tool.py`
- Create: `backend/tests/test_fetch_url_tool.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_fetch_url_tool.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


def test_detect_type_pdf():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type
    assert _detect_type("https://example.com/report.pdf") == "pdf"


def test_detect_type_docx():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type
    assert _detect_type("https://example.com/doc.docx") == "docx"


def test_detect_type_xlsx():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type
    assert _detect_type("https://example.com/sheet.xlsx") == "xlsx"


def test_detect_type_pptx():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type
    assert _detect_type("https://example.com/slide.pptx") == "pptx"


def test_detect_type_webpage_default():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type
    assert _detect_type("https://example.com/page") == "webpage"
    assert _detect_type("https://example.com/") == "webpage"
    assert _detect_type("https://example.com/page.html") == "webpage"


def test_fetch_webpage_saves_markdown(tmp_path):
    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = "# Hello\nSome content."
    output_dir = tmp_path / "out"

    result = _do_fetch(
        url="https://example.com/page",
        output_dir=str(output_dir),
        content_type=None,
        webpage_mcp=mock_mcp,
    )

    assert result.endswith(".md")
    assert Path(result).read_text() == "# Hello\nSome content."
    mock_mcp.invoke.assert_called_once_with({"url": "https://example.com/page"})


def test_fetch_webpage_type_hint_overrides_detection(tmp_path):
    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = "markdown content"

    # URL looks like PDF but type hint says webpage
    result = _do_fetch(
        url="https://example.com/report.pdf",
        output_dir=str(tmp_path),
        content_type="webpage",
        webpage_mcp=mock_mcp,
    )

    assert result.endswith(".md")
    mock_mcp.invoke.assert_called_once()


def test_fetch_file_download_saves_bytes(tmp_path):
    from deerflow.tools.adapters.fetch_url.tool import _do_fetch
    import httpx

    mock_mcp = MagicMock()
    output_dir = tmp_path / "files"

    mock_response = MagicMock()
    mock_response.headers = {}
    mock_response.content = b"pdf bytes here"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = _do_fetch(
            url="https://example.com/report.pdf",
            output_dir=str(output_dir),
            content_type="pdf",
            webpage_mcp=mock_mcp,
        )

    assert Path(result).name == "report.pdf"
    assert Path(result).read_bytes() == b"pdf bytes here"


def test_fetch_video_raises_not_implemented(tmp_path):
    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    with pytest.raises(NotImplementedError, match="Video transcript not yet supported"):
        _do_fetch(
            url="https://youtube.com/watch?v=abc",
            output_dir=str(tmp_path),
            content_type="video",
            webpage_mcp=MagicMock(),
        )


def test_make_fetch_url_tool_returns_basetool():
    from deerflow.tools.adapters.fetch_url.tool import make_fetch_url_tool
    from langchain.tools import BaseTool

    tool = make_fetch_url_tool(MagicMock())
    assert isinstance(tool, BaseTool)
    assert tool.name == "fetch_url"
    assert "runtime" not in tool.args


def test_make_fetch_url_tool_translates_virtual_output_dir(tmp_path):
    """make_fetch_url_tool wrapper must resolve /mnt/user-data/ virtual output_dir."""
    from types import SimpleNamespace
    from deerflow.tools.adapters.fetch_url.tool import make_fetch_url_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    thread_data = {
        "workspace_path": str(workspace),
        "uploads_path": str(tmp_path / "uploads"),
        "outputs_path": str(tmp_path / "outputs"),
    }
    runtime = SimpleNamespace(state={"thread_data": thread_data}, context={})

    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = "# Page content"
    tool = make_fetch_url_tool(mock_mcp)

    result = tool.func(
        runtime=runtime,
        url="https://example.com/page",
        output_dir="/mnt/user-data/workspace",
        type="webpage",
    )

    # File must be saved inside actual workspace dir
    saved_files = list(workspace.glob("*.md"))
    assert len(saved_files) == 1
    assert saved_files[0].read_text() == "# Page content"
    # Returned path must be virtual (masked)
    assert "/mnt/user-data" in result
```

- [ ] **Step 2: Run test to verify it fails**

```
PYTHONPATH=. uv run pytest tests/test_fetch_url_tool.py -v
```

Expected: `FAILED` — module not found.

- [ ] **Step 3: Create `fetch_url/tool.py`**

```python
# backend/packages/harness/deerflow/tools/adapters/fetch_url/tool.py
import urllib.parse
from pathlib import Path
from langchain.tools import BaseTool, tool, ToolRuntime

_FILE_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx"}


def _detect_type(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in _FILE_EXTENSIONS:
        if path.endswith(ext):
            return ext.lstrip(".")
    return "webpage"


def _slug_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    raw = parsed.netloc + parsed.path
    slug = raw.replace("/", "_").replace(".", "_").strip("_")
    return slug[:60] or "page"


def _do_fetch(
    url: str,
    output_dir: str,
    content_type: str | None,
    webpage_mcp: BaseTool,
) -> str:
    detected = content_type or _detect_type(url)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if detected == "webpage":
        markdown = webpage_mcp.invoke({"url": url})
        out_file = output_path / f"{_slug_from_url(url)}.md"
        out_file.write_text(markdown if isinstance(markdown, str) else str(markdown))
        return str(out_file)

    if detected == "video":
        # TODO: video transcript support
        # Detect: YouTube URLs, .mp4/.webm extensions
        # Call <cloudflare_video_transcript_tool_name> MCP tool when available
        # Save transcript as <slug>.txt, return path
        raise NotImplementedError(
            "Video transcript not yet supported. "
            "Add cloudflare video tool call here when the tool is available."
        )

    # File download (pdf, docx, xlsx, pptx)
    import httpx

    filename = Path(urllib.parse.urlparse(url).path).name or f"download.{detected}"

    with httpx.Client(follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        cd = response.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip().strip('"')
        out_file = output_path / filename
        out_file.write_bytes(response.content)

    return str(out_file)


def make_fetch_url_tool(webpage_mcp: BaseTool) -> BaseTool:
    @tool("fetch_url", parse_docstring=True)
    def fetch_url(
        runtime: ToolRuntime,
        url: str,
        output_dir: str,
        type: str | None = None,
    ) -> str:
        """Fetch a URL and save content to a local directory.

        Scrapes webpages to Markdown via browser rendering. Downloads binary files
        (PDF, DOCX, XLSX, PPTX) directly via HTTP. Auto-detects file type from URL
        extension when type is omitted.

        Args:
            url: The URL to fetch.
            output_dir: Directory to save into (use /mnt/user-data/workspace/... paths).
            type: Content type hint: "webpage", "pdf", "docx", "xlsx", "pptx".
                  Omit to auto-detect from URL extension (defaults to "webpage").

        Returns:
            Saved file path as a /mnt/user-data/... virtual path.
        """
        from deerflow.sandbox.tools import get_thread_data, replace_virtual_path, mask_local_paths_in_output

        thread_data = get_thread_data(runtime)
        actual_output_dir = replace_virtual_path(output_dir, thread_data)
        result = _do_fetch(url, actual_output_dir, type, webpage_mcp)
        return mask_local_paths_in_output(result, thread_data)

    return fetch_url
```

- [ ] **Step 4: Run tests to verify they pass**

```
PYTHONPATH=. uv run pytest tests/test_fetch_url_tool.py -v
```

Expected: 9 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/adapters/fetch_url/tool.py backend/tests/test_fetch_url_tool.py
git commit -m "feat: add fetch_url tool with webpage markdown scrape and HTTP file download"
```

---

## Task 7: Wire `fetch_url` adapter `get_tools()`

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/adapters/fetch_url/__init__.py`

- [ ] **Step 1: Replace placeholder with real implementation**

```python
# backend/packages/harness/deerflow/tools/adapters/fetch_url/__init__.py
from langchain.tools import BaseTool
from deerflow.config.extensions_config import AdapterConfig
from deerflow.tools.adapters.fetch_url.tool import make_fetch_url_tool


def get_tools(adapter_config: AdapterConfig, mcp_tools: list[BaseTool]) -> list[BaseTool]:
    mcp_by_name = {t.name: t for t in mcp_tools}
    webpage_name = adapter_config.tool_mappings.get("webpage")

    if not webpage_name or webpage_name not in mcp_by_name:
        return []

    return [make_fetch_url_tool(mcp_by_name[webpage_name])]
```

- [ ] **Step 2: Add test to `test_adapter_loader.py`**

Append to `backend/tests/test_adapter_loader.py`:

```python
def test_fetch_url_adapter_get_tools_returns_one_tool():
    from deerflow.tools.adapters.fetch_url import get_tools
    from deerflow.config.extensions_config import AdapterConfig

    cfg = AdapterConfig(
        enabled=True,
        wraps_server="cloudflare",
        tool_mappings={"webpage": "cloudflare__browser_render_markdown"},
    )
    mcp_tools = [_make_mcp_tool("cloudflare__browser_render_markdown")]
    tools = get_tools(cfg, mcp_tools)
    assert len(tools) == 1
    assert tools[0].name == "fetch_url"


def test_fetch_url_adapter_returns_empty_when_mcp_missing():
    from deerflow.tools.adapters.fetch_url import get_tools
    from deerflow.config.extensions_config import AdapterConfig

    cfg = AdapterConfig(
        enabled=True,
        tool_mappings={"webpage": "cloudflare__browser_render_markdown"},
    )
    tools = get_tools(cfg, [])
    assert tools == []
```

- [ ] **Step 3: Run tests**

```
PYTHONPATH=. uv run pytest tests/test_adapter_loader.py tests/test_fetch_url_tool.py -v
```

Expected: all PASSED.

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/deerflow/tools/adapters/fetch_url/__init__.py backend/tests/test_adapter_loader.py
git commit -m "feat: wire fetch_url adapter get_tools with webpage MCP tool lookup"
```

---

## Task 8: Integrate adapter loader into `tools.py`

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/tools.py`

- [ ] **Step 1: Read current `get_available_tools()` to know exact insertion point**

Open `backend/packages/harness/deerflow/tools/tools.py`. Find the line that builds the return value — it currently reads:

```python
return loaded_tools + builtin_tools + mcp_tools
```

Also find where `extensions_config` / `ExtensionsConfig.from_file()` is called to get the config object that has the `mcp_servers`. You'll use the same config object for `load_adapter_tools`.

- [ ] **Step 2: Add import and modify `get_available_tools()`**

At the top of `tools.py`, add import:

```python
from deerflow.tools.adapters import load_adapter_tools
```

Locate the block that gets MCP tools. It looks like:

```python
extensions_config = ExtensionsConfig.from_file()
mcp_tools = get_cached_mcp_tools() if extensions_config.get_enabled_mcp_servers() else []
```

Immediately after `mcp_tools` is assigned, add:

```python
adapter_tools, mcp_tools = load_adapter_tools(extensions_config, mcp_tools)
```

Change the return to:

```python
return loaded_tools + builtin_tools + mcp_tools + adapter_tools
```

- [ ] **Step 3: Run full backend test suite**

```
cd backend
PYTHONPATH=. uv run pytest tests/ -v --tb=short
```

Expected: all PASSED. Pay attention to `test_harness_boundary.py` — it must still pass (adapters only import from `deerflow.*`).

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/deerflow/tools/tools.py
git commit -m "feat: integrate adapter loader into get_available_tools"
```

---

## Task 9: Update `extensions_config.json` with adapter defaults

**Files:**
- Modify: `extensions_config.json` (project root)

- [ ] **Step 1: Read current `extensions_config.json`**

Open project root `extensions_config.json`. It currently ends with `"skills": {}`.

- [ ] **Step 2: Add `adapters` section (both adapters disabled by default)**

Add after the `"skills"` key:

```json
"adapters": {
  "ragflow_builtin": {
    "enabled": false,
    "wraps_server": "ragflow",
    "hide_wrapped_tools": false,
    "tool_mappings": {
      "upload": "ragflow__upload_with_metadata",
      "download": "ragflow__download_attachment"
    }
  },
  "fetch_url": {
    "enabled": false,
    "wraps_server": "cloudflare",
    "hide_wrapped_tools": false,
    "tool_mappings": {
      "webpage": "cloudflare__browser_render_markdown"
    }
  }
}
```

> **Note on tool name prefix:** The prefix format (`ragflow__`) matches `langchain-mcp-adapters` convention of `{server_name}__{tool_name}`. If the actual loaded tool names differ (verify with `print([t.name for t in get_cached_mcp_tools()])`), update these values accordingly before enabling the adapters.

- [ ] **Step 3: Verify config loads cleanly**

```bash
cd backend
PYTHONPATH=. uv run python -c "
from deerflow.config.extensions_config import ExtensionsConfig
cfg = ExtensionsConfig.from_file()
print('adapters:', list(cfg.adapters.keys()))
print('OK')
"
```

Expected output:
```
adapters: ['ragflow_builtin', 'fetch_url']
OK
```

- [ ] **Step 4: Commit**

```bash
git add extensions_config.json
git commit -m "config: add adapter defaults (disabled) to extensions_config.json"
```

---

## Task 10: Gateway API `/api/adapters/config`

**Files:**
- Create: `backend/app/gateway/routers/adapters.py`
- Modify: `backend/app/gateway/app.py`
- Modify: `backend/app/gateway/routers/mcp.py` (preserve `adapters` key on MCP PUT)
- Create: `backend/tests/test_adapters_router.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_adapters_router.py
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from deerflow.config.extensions_config import AdapterConfig, ExtensionsConfig


def _make_config_with_adapters():
    return ExtensionsConfig.model_validate({
        "mcpServers": {},
        "adapters": {
            "ragflow_builtin": {
                "enabled": False,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": False,
                "tool_mappings": {"upload": "ragflow__upload_with_metadata"},
            }
        },
    })


def test_get_adapters_config_returns_adapter_list(tmp_path):
    from app.gateway.app import app

    mock_config = _make_config_with_adapters()
    with patch("app.gateway.routers.adapters.get_extensions_config", return_value=mock_config), \
         patch("app.gateway.dependencies.get_current_user", return_value={"id": "user-1"}):
        client = TestClient(app)
        response = client.get("/api/adapters/config")

    assert response.status_code == 200
    data = response.json()
    assert "ragflow_builtin" in data["adapters"]
    assert data["adapters"]["ragflow_builtin"]["enabled"] is False


def test_put_adapters_config_writes_file(tmp_path):
    from app.gateway.app import app

    config_file = tmp_path / "extensions_config.json"
    config_file.write_text(json.dumps({
        "mcpServers": {},
        "skills": {},
        "adapters": {
            "ragflow_builtin": {
                "enabled": False,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": False,
                "tool_mappings": {},
            }
        },
    }))
    mock_config = _make_config_with_adapters()

    with patch("app.gateway.routers.adapters.get_extensions_config", return_value=mock_config), \
         patch("app.gateway.routers.adapters.reload_extensions_config", return_value=mock_config), \
         patch("app.gateway.routers.adapters.ExtensionsConfig.resolve_config_path", return_value=config_file), \
         patch("app.gateway.dependencies.get_current_user", return_value={"id": "user-1"}):
        client = TestClient(app)
        response = client.put(
            "/api/adapters/config",
            json={
                "adapters": {
                    "ragflow_builtin": {
                        "enabled": True,
                        "wraps_server": "ragflow",
                        "hide_wrapped_tools": False,
                        "tool_mappings": {"upload": "ragflow__upload_with_metadata"},
                    }
                }
            },
        )

    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend
PYTHONPATH=. uv run pytest tests/test_adapters_router.py -v
```

Expected: `FAILED` — router not found.

- [ ] **Step 3: Create `routers/adapters.py`**

```python
# backend/app/gateway/routers/adapters.py
import json
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.gateway.dependencies import get_current_user
from deerflow.config.extensions_config import (
    AdapterConfig,
    ExtensionsConfig,
    get_extensions_config,
    reload_extensions_config,
)

router = APIRouter(prefix="/api")


class AdapterConfigResponse(BaseModel):
    enabled: bool
    wraps_server: str | None
    hide_wrapped_tools: bool
    tool_mappings: dict[str, str]


class AdaptersConfigResponse(BaseModel):
    adapters: dict[str, AdapterConfigResponse]


class AdaptersConfigUpdateRequest(BaseModel):
    adapters: dict[str, AdapterConfigResponse]


@router.get("/adapters/config", response_model=AdaptersConfigResponse)
async def get_adapters_configuration(
    _user: dict = Depends(get_current_user),
) -> AdaptersConfigResponse:
    config = get_extensions_config()
    return AdaptersConfigResponse(
        adapters={
            name: AdapterConfigResponse(**adapter.model_dump())
            for name, adapter in config.adapters.items()
        }
    )


@router.put("/adapters/config", response_model=AdaptersConfigResponse)
async def update_adapters_configuration(
    request: AdaptersConfigUpdateRequest,
    _user: dict = Depends(get_current_user),
) -> AdaptersConfigResponse:
    config_path = ExtensionsConfig.resolve_config_path()
    if config_path is None:
        config_path = Path.cwd().parent / "extensions_config.json"

    current = get_extensions_config()
    config_data = {
        "mcpServers": {
            name: server.model_dump()
            for name, server in current.mcp_servers.items()
        },
        "skills": {
            name: {"enabled": skill.enabled}
            for name, skill in current.skills.items()
        },
        "adapters": {
            name: adapter.model_dump()
            for name, adapter in request.adapters.items()
        },
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    reloaded = reload_extensions_config()
    return AdaptersConfigResponse(
        adapters={
            name: AdapterConfigResponse(**adapter.model_dump())
            for name, adapter in reloaded.adapters.items()
        }
    )
```

- [ ] **Step 4: Register router in `app.py`**

Open `backend/app/gateway/app.py`. Add import alongside other router imports:

```python
from app.gateway.routers import adapters
```

Add include_router call alongside others:

```python
app.include_router(adapters.router)
```

- [ ] **Step 5: Fix MCP PUT to preserve `adapters` key**

Open `backend/app/gateway/routers/mcp.py`. In `update_mcp_configuration()`, find the `config_data` dict construction. It currently writes `mcpServers` and `skills`. Add `adapters` preservation:

```python
config_data = {
    "mcpServers": {name: server.model_dump() for name, server in request.mcp_servers.items()},
    "skills": {name: {"enabled": skill.enabled} for name, skill in current_config.skills.items()},
    "adapters": {
        name: adapter.model_dump()
        for name, adapter in current_config.adapters.items()
    },
}
```

- [ ] **Step 6: Run tests**

```
PYTHONPATH=. uv run pytest tests/test_adapters_router.py tests/ -v --tb=short
```

Expected: all PASSED.

- [ ] **Step 7: Commit**

```bash
git add backend/app/gateway/routers/adapters.py backend/app/gateway/app.py backend/app/gateway/routers/mcp.py backend/tests/test_adapters_router.py
git commit -m "feat: add /api/adapters/config GET+PUT endpoints and preserve adapters on MCP PUT"
```

---

## Task 11: Frontend adapter settings UI

**Files:**
- Create: `frontend/src/core/adapters/types.ts`
- Create: `frontend/src/core/adapters/api.ts`
- Create: `frontend/src/core/adapters/hooks.ts`
- Modify: `frontend/src/components/workspace/settings/tool-settings-page.tsx`

- [ ] **Step 1: Create types**

```typescript
// frontend/src/core/adapters/types.ts
export interface AdapterConfig {
  enabled: boolean;
  wraps_server: string | null;
  hide_wrapped_tools: boolean;
  tool_mappings: Record<string, string>;
}

export interface AdaptersConfig {
  adapters: Record<string, AdapterConfig>;
}
```

- [ ] **Step 2: Create API functions**

```typescript
// frontend/src/core/adapters/api.ts
import { getBackendBaseURL } from "~/core/api/utils";
import { fetchWithAuth } from "~/core/api/auth";
import type { AdaptersConfig } from "./types";

export async function loadAdaptersConfig(): Promise<AdaptersConfig> {
  const response = await fetchWithAuth(
    `${getBackendBaseURL()}/api/adapters/config`,
  );
  return response.json() as Promise<AdaptersConfig>;
}

export async function updateAdaptersConfig(
  config: AdaptersConfig,
): Promise<AdaptersConfig> {
  const response = await fetchWithAuth(
    `${getBackendBaseURL()}/api/adapters/config`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    },
  );
  return response.json() as Promise<AdaptersConfig>;
}
```

- [ ] **Step 3: Create hooks**

```typescript
// frontend/src/core/adapters/hooks.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { loadAdaptersConfig, updateAdaptersConfig } from "./api";
import type { AdaptersConfig } from "./types";

export function useAdaptersConfig() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["adaptersConfig"],
    queryFn: loadAdaptersConfig,
  });
  return { config: data, isLoading, error };
}

export function useUpdateAdapter() {
  const queryClient = useQueryClient();
  const { config } = useAdaptersConfig();

  return useMutation({
    mutationFn: async ({
      adapterName,
      patch,
    }: {
      adapterName: string;
      patch: Partial<AdaptersConfig["adapters"][string]>;
    }) => {
      if (!config) throw new Error("Adapters config not loaded");
      return updateAdaptersConfig({
        adapters: {
          ...config.adapters,
          [adapterName]: {
            ...config.adapters[adapterName]!,
            ...patch,
          },
        },
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["adaptersConfig"] });
    },
  });
}
```

- [ ] **Step 4: Add adapter cards to `tool-settings-page.tsx`**

Open `frontend/src/components/workspace/settings/tool-settings-page.tsx`.

Add imports at top (alongside existing MCP imports):

```typescript
import { useAdaptersConfig, useUpdateAdapter } from "~/core/adapters/hooks";
import type { AdaptersConfig } from "~/core/adapters/types";
```

Add `AdapterCard` component before `MCPServerList` (or at end of file):

```typescript
function AdapterCard({
  adapterName,
  config,
}: {
  adapterName: string;
  config: AdaptersConfig["adapters"][string];
}) {
  const { mutate: updateAdapter } = useUpdateAdapter();

  return (
    <Item className="ml-4 w-full border-l-2 border-dashed" variant="outline">
      <ItemContent>
        <ItemTitle>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground text-xs">adapter</span>
            <span>{adapterName}</span>
          </div>
        </ItemTitle>
        <ItemDescription>
          {config.hide_wrapped_tools
            ? "Hides raw MCP tools from the model."
            : "Raw MCP tools remain visible alongside this adapter."}
        </ItemDescription>
      </ItemContent>
      <ItemActions className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground text-xs">hide raw</span>
          <Switch
            checked={config.hide_wrapped_tools}
            onCheckedChange={(checked) =>
              updateAdapter({
                adapterName,
                patch: { hide_wrapped_tools: checked },
              })
            }
          />
        </div>
        <Switch
          checked={config.enabled}
          onCheckedChange={(checked) =>
            updateAdapter({ adapterName, patch: { enabled: checked } })
          }
        />
      </ItemActions>
    </Item>
  );
}
```

In `MCPServerList`, add adapters query and render adapter cards under matching servers:

```typescript
function MCPServerList({ servers }: { servers: Record<string, MCPServerConfig> }) {
  const { mutate: enableMCPServer } = useEnableMCPServer();
  const { config: adaptersConfig } = useAdaptersConfig();

  return (
    <div className="flex w-full flex-col gap-4">
      {Object.entries(servers).map(([name, config]) => (
        <div key={name} className="flex flex-col gap-2">
          <Item className="w-full" variant="outline">
            <ItemContent>
              <ItemTitle>
                <div className="flex items-center gap-2">
                  <div>{name}</div>
                </div>
              </ItemTitle>
              <ItemDescription className="line-clamp-4">
                {config.description}
              </ItemDescription>
            </ItemContent>
            <ItemActions>
              <Switch
                checked={config.enabled}
                disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
                onCheckedChange={(checked) =>
                  enableMCPServer({ serverName: name, enabled: checked })
                }
              />
            </ItemActions>
          </Item>
          {adaptersConfig &&
            Object.entries(adaptersConfig.adapters)
              .filter(([, adapterCfg]) => adapterCfg.wraps_server === name)
              .map(([adapterName, adapterCfg]) => (
                <AdapterCard
                  key={adapterName}
                  adapterName={adapterName}
                  config={adapterCfg}
                />
              ))}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run frontend type check**

```
cd frontend
pnpm check
```

Expected: no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/core/adapters/ frontend/src/components/workspace/settings/tool-settings-page.tsx
git commit -m "feat: add adapter settings UI cards under MCP server entries"
```

---

## Task 12: End-to-end smoke test

- [ ] **Step 1: Start dev environment**

```powershell
.\start-dev.ps1
```

Wait for all services to be ready at http://localhost:2026.

- [ ] **Step 2: Verify MCP tool name prefix**

In a new terminal:

```bash
cd backend
PYTHONPATH=. uv run python -c "
from deerflow.mcp.cache import get_cached_mcp_tools
import asyncio

async def main():
    tools = await asyncio.to_thread(get_cached_mcp_tools)
    ragflow = [t.name for t in tools if 'ragflow' in t.name or 'upload' in t.name or 'download' in t.name]
    cloudflare = [t.name for t in tools if 'cloudflare' in t.name or 'browser' in t.name or 'markdown' in t.name]
    print('ragflow tools:', ragflow)
    print('cloudflare tools:', cloudflare)

asyncio.run(main())
"
```

**If the printed names differ from `ragflow__upload_with_metadata` etc.**, update `extensions_config.json` `tool_mappings` to match the actual names before proceeding.

- [ ] **Step 3: Enable adapters via settings UI**

Open http://localhost:2026, navigate to Settings → Tools. Verify:
- `ragflow_builtin` adapter card appears under the `ragflow` MCP server entry
- `fetch_url` adapter card appears under the `cloudflare` MCP server entry
- Enable toggles work (page reloads adapter state correctly)

- [ ] **Step 4: Verify adapter tools appear in agent**

Enable `ragflow_builtin` adapter. Open a new chat thread and ask:

> "List the tools you have available."

Expected: `ragflow_upload` and `ragflow_download` appear in the response. `upload_with_metadata` and `download_attachment` appear or not depending on `hide_wrapped_tools` setting.

- [ ] **Step 5: Run full test suite one final time**

```bash
cd backend
PYTHONPATH=. uv run pytest tests/ -v --tb=short
```

Expected: all PASSED.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete adapter tool system — ragflow_upload, ragflow_download, fetch_url with config-driven adapter loader"
```
