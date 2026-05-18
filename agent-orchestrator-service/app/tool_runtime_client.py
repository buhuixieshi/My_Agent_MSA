import sys
from pathlib import Path

import grpc

from app import config
from app.logger import debug_log

GENERATED_DIR = Path(__file__).parent / "generated"
if str(GENERATED_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATED_DIR))

try:
    import tool_runtime_pb2
    import tool_runtime_pb2_grpc
except ImportError:
    tool_runtime_pb2 = None
    tool_runtime_pb2_grpc = None


class ToolRuntimeClient:
    def __init__(self):
        self._stub = None

    def _get_stub(self):
        if self._stub is None:
            channel = grpc.insecure_channel(config.TOOL_RUNTIME_TARGET)
            self._stub = tool_runtime_pb2_grpc.ToolRuntimeStub(channel)
        return self._stub

    def execute_tool(self, task_id: str, tool_name: str, args: list[str]):
        if tool_runtime_pb2 is None:
            raise RuntimeError("tool_runtime protobuf is not generated")

        try:
            request = tool_runtime_pb2.ExecuteToolRequest(
                task_id=task_id,
                tool_name=tool_name,
                skill_name=tool_name,
                args=args,
                kwargs={},
                workspace_dir=str(config.WORKSPACE_DIR / "tasks" / task_id),
                timeout_seconds=config.TOOL_TIMEOUT_SECONDS,
            )
            response = self._get_stub().ExecuteTool(
                request,
                timeout=config.TOOL_TIMEOUT_SECONDS + 10,
            )
            return {
                "ok": response.ok,
                "output": response.output,
                "artifacts": [
                    {
                        "type": artifact.type,
                        "local_path": artifact.local_path,
                        "asset_url": artifact.asset_url,
                    }
                    for artifact in response.artifacts
                ],
                "logs": response.logs,
                "error": response.error,
            }
        except Exception as exc:
            debug_log(f"ExecuteTool failed: {exc}")
            return {
                "ok": False,
                "output": "",
                "artifacts": [],
                "logs": "",
                "error": str(exc),
            }
