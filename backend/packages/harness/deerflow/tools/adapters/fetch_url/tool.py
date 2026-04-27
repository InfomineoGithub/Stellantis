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
        return out_file.as_posix()

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

    return out_file.as_posix()


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
