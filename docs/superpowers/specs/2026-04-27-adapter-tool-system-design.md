# Adapter Tool System — Design Spec

**Date:** 2026-04-27
**Status:** Approved

## Problem

RAGFlow and Cloudflare MCP tools use base64 as their wire format. This forces the model to:
1. Make extra tool calls to encode/decode files
2. Bloat the context window with base64 content
3. Handle multi-step pipelines (scrape → encode → upload) manually

Additionally, the model cannot batch-download multiple RAGFlow documents in one call, and there is no unified interface for fetching URLs (webpages, files) to the local workspace.

## Goal

Introduce a thin adapter layer — path-based built-in tools that wrap MCP tools internally — so the model works with file paths and the system handles all base64 encoding/decoding transparently. The raw MCP tools remain available but can be optionally hidden per adapter config.

---

## Architecture

### Directory Structure

```
backend/packages/harness/deerflow/tools/
  builtins/                    # Existing core tools (unchanged)
  adapters/
    __init__.py                # load_adapter_tools(config, mcp_tools) entry point
    ragflow/
      __init__.py              # get_tools(config, mcp_tools) -> list[BaseTool]
      upload.py                # RagflowUploadTool
      download.py              # RagflowDownloadTool
    fetch_url/
      __init__.py              # get_tools(config, mcp_tools) -> list[BaseTool]
      tool.py                  # FetchUrlTool
```

Each adapter package exposes a single `get_tools(adapter_config, mcp_tools)` function. The adapter loader calls this for every enabled adapter and returns the aggregated tool list plus the filtered MCP tool list.

---

## Config Schema

### `extensions_config.json` — new `adapters` key

```json
{
  "mcpServers": { ... },
  "adapters": {
    "ragflow_builtin": {
      "enabled": true,
      "wraps_server": "ragflow",
      "hide_wrapped_tools": false,
      "tool_mappings": {
        "upload": "ragflow__upload_with_metadata",
        "download": "ragflow__download_attachment"
      }
    },
    "fetch_url": {
      "enabled": true,
      "wraps_server": "cloudflare",
      "hide_wrapped_tools": false,
      "tool_mappings": {
        "webpage": "cloudflare__browser_render_markdown"
      }
    }
  }
}
```

### Pydantic Schema (additions to `config/extensions_config.py`)

```python
class AdapterConfig(BaseModel):
    enabled: bool = False
    wraps_server: str | None = None          # MCP server name to optionally suppress
    hide_wrapped_tools: bool = False          # If true, remove wraps_server tools from model list
    tool_mappings: dict[str, str] = {}        # Logical name → actual MCP tool name

class ExtensionsConfig(BaseModel):
    mcpServers: dict[str, McpServerConfig] = {}
    adapters: dict[str, AdapterConfig] = {}   # NEW
    ...
```

---

## Tool Interfaces

### `ragflow_upload`

| Field | Value |
|---|---|
| Args | `path: str`, `dataset_id: str`, `filename: str \| None` (default: basename of path), `metadata: dict \| None` |
| Internal call | `upload_with_metadata(dataset_id, filename, base64(file_bytes), metadata)` |
| Returns | JSON doc info from RAGFlow (id, name, progress, etc.) |
| Description | "Upload a local file to a RAGFlow dataset by path. Use this instead of upload_with_metadata — file must already exist in the agent workspace." |

**Flow:**
1. Read file bytes from `path`
2. Base64-encode
3. Invoke `upload_with_metadata` MCP tool (looked up by `tool_mappings.upload`)
4. Return raw JSON result

### `ragflow_download`

| Field | Value |
|---|---|
| Args | `doc_ids: list[str]`, `output_dir: str` |
| Internal call | `download_attachment(doc_id)` per ID |
| Returns | List of absolute paths where files were saved |
| Description | "Download one or more RAGFlow documents by ID to a local directory. Returns saved file paths." |

**Flow:**
1. For each `doc_id`: invoke `download_attachment` MCP tool
2. Parse `content_base64` from JSON response
3. Decode base64 → raw bytes
4. Infer filename: `download_attachment` does not return filename — caller must pass known filenames, or tool accepts optional `filenames: list[str] | None` parallel to `doc_ids`. Fall back to `doc_id` if not provided.
5. Write bytes to `output_dir/<filename>`
6. Return list of saved paths

### `fetch_url`

| Field | Value |
|---|---|
| Args | `url: str`, `output_dir: str`, `type: str \| None` (`"webpage"`, `"pdf"`, `"docx"`, `"xlsx"`, `"pptx"`) |
| Returns | Absolute path of saved file |
| Description | "Fetch a URL and save content to a local directory. Scrapes webpages to markdown, downloads binary files (PDF, DOCX, XLSX, PPTX) directly via HTTP. Omit type to auto-detect." |

**Type detection (when `type` omitted):**
1. Check URL path extension (`.pdf`, `.docx`, `.xlsx`, `.pptx` → file download)
2. If no extension or `.html`/`.htm` → webpage

**Flow — webpage:**
1. Invoke `browser_render_markdown(url=url)` MCP tool (looked up by `tool_mappings.webpage`)
2. Save markdown string as `<url-slug>.md` in `output_dir`
3. Return path

**Flow — file types:**
1. HTTP GET `url` with streaming
2. Determine filename from `Content-Disposition` header or URL basename
3. Stream bytes to `output_dir/<filename>`
4. Return path

**Video transcript (not yet supported):**
```python
# TODO: video transcript support
# Detect: YouTube URLs, .mp4/.webm extensions
# Call <cloudflare_video_transcript_tool_name> MCP tool when available
# Save transcript as <slug>.txt, return path
elif detected_type == "video":
    raise NotImplementedError(
        "Video transcript not yet supported. "
        "Add cloudflare video tool call here when available."
    )
```

---

## Tool Loader Integration

`tools/tools.py` — after MCP tools are loaded:

```python
from deerflow.tools.adapters import load_adapter_tools

mcp_tools = get_cached_mcp_tools()
adapter_tools, visible_mcp_tools = load_adapter_tools(
    extensions_config=extensions_config,
    mcp_tools=mcp_tools,
)
all_tools = builtin_tools + visible_mcp_tools + adapter_tools
```

`load_adapter_tools` logic:
1. Iterate `extensions_config.adapters`
2. For each enabled adapter: import adapter package, call `get_tools(adapter_config, mcp_tools)`
3. If `hide_wrapped_tools: true`: remove tools from `wraps_server` from `mcp_tools`
4. Return `(adapter_tools_list, filtered_mcp_tools_list)`

MCP tools are passed into adapters so they can call `.invoke()` directly in Python — no agent round-trip, no base64 in model context.

---

## Tool Disambiguation (when both visible)

When `hide_wrapped_tools: false`, both adapter tools and raw MCP tools are visible. Tool descriptions handle disambiguation:

- **Adapter tools** — descriptions say "Use this when file is in the workspace / for local paths"
- **Raw MCP tools** — descriptions from MCP server say "accepts base64-encoded content"

Model picks based on context. No middleware filtering needed.

---

## Frontend

Adapter settings surface in existing MCP server management UI (Gateway API + frontend).

### Gateway API (`app/`) — new endpoints

```
GET  /api/adapters              # List all adapters with config
PUT  /api/adapters/{name}       # Update adapter config (enabled, hide_wrapped_tools)
```

Mirrors existing `/api/mcp` pattern. Reads/writes `extensions_config.json`.

### Frontend UI

When a server has a matching `wraps_server` adapter, show adapter card below the server card in the MCP settings panel:
- Enable/disable toggle
- `hide_wrapped_tools` toggle
- Read-only `tool_mappings` display (for visibility, not editable in UI)

---

## Testing

### Unit tests (`backend/tests/`)

- `test_ragflow_upload_tool.py` — mock `upload_with_metadata` MCP tool, verify base64 encoding and return shape
- `test_ragflow_download_tool.py` — mock `download_attachment`, verify base64 decode + file write + path return
- `test_fetch_url_tool.py` — mock `browser_render_markdown` + httpx, verify type detection and file output
- `test_adapter_loader.py` — verify `load_adapter_tools` hides/shows tools correctly per `hide_wrapped_tools`

### Integration tests

- Ragflow upload→download roundtrip (requires ragflow MCP running)
- `fetch_url` webpage scrape end-to-end (requires cloudflare MCP running)

### Boundary test

`backend/tests/test_harness_boundary.py` already enforces no `app.*` imports inside harness. Adapters live inside harness — no new boundary rules needed.

---

## Constraints

- Adapters import only from `deerflow.*` — harness boundary enforced
- No base64 content ever returned to model context
- Adapter tools are excluded from model list when adapter is disabled
- `extensions_config.json` mtime invalidation (already in MCP cache) covers adapter config changes — same file, same mtime check, no extra mechanism needed
- MCP tool name prefix separator used by langchain-mcp-adapters must be confirmed at impl time (double underscore `__` is convention but verify against loaded tool names)
