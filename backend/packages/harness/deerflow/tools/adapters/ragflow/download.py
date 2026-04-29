import asyncio
import base64
import json
from pathlib import Path

from langchain.tools import BaseTool, ToolRuntime, tool


def _save_file(file_path: Path, b64_data: str) -> str:
    raw_bytes = base64.b64decode(b64_data)
    file_path.write_bytes(raw_bytes)
    return file_path.as_posix()


async def _download_and_save_single(
    doc_id: str,
    output_path: Path,
    filename: str | None,
    download_mcp: BaseTool,
) -> str:
    result_str = await download_mcp.ainvoke({"doc_id": doc_id})
    result = json.loads(result_str) if isinstance(result_str, str) else result_str
    
    if isinstance(result, list):
        # Extract the JSON string from the "text" field if it exists in the MCP response format
        if len(result) > 0 and isinstance(result[0], dict) and "text" in result[0]:
            text_content = result[0]["text"]
            result = json.loads(text_content) if isinstance(text_content, str) else text_content
        else:
            result = result[0]

    fname = filename or result.get("filename", doc_id)
    file_path = output_path / fname
    
    return await asyncio.to_thread(_save_file, file_path, result["content_base64"])


async def _do_download(
    doc_ids: list[str],
    output_dir: str,
    filenames: list[str] | None,
    download_mcp: BaseTool,
) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    tasks = []
    for i, doc_id in enumerate(doc_ids):
        filename = filenames[i] if filenames and i < len(filenames) else None
        tasks.append(_download_and_save_single(doc_id, output_path, filename, download_mcp))
        
    saved_paths = await asyncio.gather(*tasks)
    return json.dumps(saved_paths)

def make_download_tool(download_mcp: BaseTool) -> BaseTool:
    @tool("ragflow_download", parse_docstring=True)
    async def ragflow_download(
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
        from deerflow.sandbox.tools import get_thread_data, mask_local_paths_in_output, replace_virtual_path

        thread_data = get_thread_data(runtime)
        actual_output_dir = replace_virtual_path(output_dir, thread_data)
        result = await _do_download(doc_ids, actual_output_dir, filenames, download_mcp)
        return mask_local_paths_in_output(result, thread_data)

    return ragflow_download
