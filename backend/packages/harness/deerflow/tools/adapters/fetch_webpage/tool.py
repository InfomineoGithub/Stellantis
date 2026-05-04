import json
import urllib.parse
from pathlib import Path

from langchain.tools import BaseTool, ToolRuntime, tool


def _slug_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    raw = parsed.netloc + parsed.path
    slug = raw.replace("/", "_").replace(".", "_").strip("_")
    return slug[:60] or "page"


def _extract_markdown(raw: object) -> str:
    """Extract markdown text from the serper webpage_scrape JSON response."""
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return raw
    else:
        parsed = raw

    # Unwrap MCP content block list: [{"type": "text", "text": "..."}]
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        parsed = parsed[0]

    if isinstance(parsed, dict):
        for key in ("markdown", "content", "text"):
            if key in parsed and isinstance(parsed[key], str):
                candidate = parsed[key]
                # The candidate string may itself be JSON (e.g. MCP wraps serper's
                # JSON payload in {"type": "text", "text": "<json>"}).
                # Try one level of nested parsing to reach "markdown"/"content".
                try:
                    inner = json.loads(candidate)
                    if isinstance(inner, dict):
                        for inner_key in ("markdown", "content", "text"):
                            if inner_key in inner and isinstance(inner[inner_key], str):
                                return inner[inner_key]
                except Exception:
                    pass
                return candidate
        return json.dumps(parsed, indent=2)

    return str(parsed)


async def _do_fetch_extended(
    url: str,
    output_dir: str,
    webpage_scrape_mcp: BaseTool,
) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    raw = await webpage_scrape_mcp.ainvoke({"url": url, "includeMarkdown": True})
    markdown = _extract_markdown(raw)
    out_file = output_path / f"{_slug_from_url(url)}.md"
    out_file.write_text(markdown, encoding="utf-8")
    return out_file.as_posix()


def make_fetch_webpage_tool(webpage_scrape_mcp: BaseTool) -> BaseTool:
    @tool("fetch_webpage", parse_docstring=True)
    async def fetch_webpage(
        runtime: ToolRuntime,
        url: str,
        output_dir: str,
    ) -> str:
        """Scrape a webpage and save its content as Markdown to a local directory.

        Uses the serper webpage_scrape tool to fetch and render the page as Markdown.
        Only supports public webpage URLs — do not use for binary files (PDF, DOCX, etc.).

        Args:
            url: The public webpage URL to scrape.
            output_dir: Directory to save the Markdown file into (use /mnt/user-data/workspace/... paths).

        Returns:
            Saved file path as a /mnt/user-data/... virtual path.
        """
        from deerflow.sandbox.tools import get_thread_data, mask_local_paths_in_output, replace_virtual_path

        thread_data = get_thread_data(runtime)
        actual_output_dir = replace_virtual_path(output_dir, thread_data)
        result = await _do_fetch_extended(url, actual_output_dir, webpage_scrape_mcp)
        return mask_local_paths_in_output(result, thread_data)

    return fetch_webpage
