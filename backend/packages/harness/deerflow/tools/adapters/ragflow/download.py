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
        saved_paths.append(file_path.as_posix())

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
