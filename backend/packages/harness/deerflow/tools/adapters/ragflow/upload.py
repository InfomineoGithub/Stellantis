import base64
import json
from pathlib import Path

from langchain.tools import BaseTool, ToolRuntime, tool


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
        from deerflow.sandbox.tools import get_thread_data, mask_local_paths_in_output, replace_virtual_path

        thread_data = get_thread_data(runtime)
        actual_path = replace_virtual_path(path, thread_data)
        result = _do_upload(actual_path, dataset_id, filename, metadata, upload_mcp)
        return mask_local_paths_in_output(result, thread_data)

    return ragflow_upload
