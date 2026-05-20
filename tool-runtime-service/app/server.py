from __future__ import annotations

import subprocess
import sys
from concurrent import futures
from pathlib import Path

import grpc

from app import config
from app.logger import log, debug
from app.workspace import delete_path, list_workspace, read_text, workspace_root, write_text

GENERATED_DIR = Path(__file__).parent / "generated"
if str(GENERATED_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATED_DIR))

try:
    import tool_runtime_pb2
    import tool_runtime_pb2_grpc
except ImportError as exc:
    raise RuntimeError("gRPC generated files not found. Run bash scripts/gen_proto.sh first.") from exc


class ToolRuntimeService(tool_runtime_pb2_grpc.ToolRuntimeServicer):
    def ExecuteTool(self, request, context):
        task_id = request.task_id or "-"
        tool_name = (request.tool_name or request.skill_name or "").strip()
        kwargs = dict(request.kwargs)
        args = list(request.args)
        timeout = request.timeout_seconds or config.DEFAULT_TIMEOUT_SECONDS

        try:
            root = workspace_root(request.workspace_dir or config.WORKSPACE_DIR)
            debug(f"ExecuteTool task_id={task_id} tool={tool_name} workspace={root}")

            output = self._dispatch(
                tool_name=tool_name,
                args=args,
                kwargs=kwargs,
                root=root,
                timeout=timeout,
            )

            return tool_runtime_pb2.ExecuteToolResponse(
                ok=True,
                output=output,
                logs=f"tool {tool_name} finished",
                error="",
            )

        except Exception as exc:
            log(f"ExecuteTool failed task_id={task_id} tool={tool_name}: {exc}")
            return tool_runtime_pb2.ExecuteToolResponse(
                ok=False,
                output="",
                logs="",
                error=str(exc),
            )

    def _dispatch(self, tool_name: str, args: list[str], kwargs: dict[str, str], root: Path, timeout: int) -> str:
        # 外部传入 - 自动转内部 _
        name = tool_name.lower().replace("-", "_")

        if name in {"", "help"}:
            return self._help()

        if name == "echo":
            return kwargs.get("text") or " ".join(args)

        # 工作空间文件工具
        if name in {"list_workspace", "list_files", "workspace_list", "ls"}:
            return list_workspace(root, config.MAX_LIST_FILES)

        if name in {"read_file", "cat", "file_read"}:
            rel = kwargs.get("path") or (args[0] if args else "")
            return read_text(root, rel, config.MAX_READ_BYTES)

        if name in {"write_file", "file_write"}:
            rel = kwargs.get("path") or (args[0] if args else "")
            text = kwargs.get("text") or (args[1] if len(args) > 1 else "")
            return write_text(root, rel, text)

        if name in {"delete_file", "remove_file", "rm"}:
            rel = kwargs.get("path") or (args[0] if args else "")
            return delete_path(root, rel)

        # Shell 执行
        if name in {"run_shell", "shell", "command"}:
            return self._run_shell(args=args, kwargs=kwargs, root=root, timeout=timeout)

        # 匹配你的规范工具名
        raise ValueError(
            f"unknown tool_name={tool_name!r}; supported: help, echo, list-workspace, file-read, file-write, delete-file"
            + (", shell" if config.ENABLE_SHELL_TOOLS else "")
        )

    def _run_shell(self, args: list[str], kwargs: dict[str, str], root: Path, timeout: int) -> str:
        if not config.ENABLE_SHELL_TOOLS:
            raise PermissionError("shell is disabled. Set ENABLE_SHELL_TOOLS=true to enable it.")

        command = kwargs.get("command") or " ".join(args)
        if not command:
            raise ValueError("missing command")

        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

        output = proc.stdout
        if proc.stderr:
            output += "\n[stderr]\n" + proc.stderr
        output += f"\n[exit_code] {proc.returncode}"
        return output

    def _help(self) -> str:
        return """tool-runtime-service tools:
- echo: args or kwargs.text
- list-workspace: list all files in workspace
- file-read: kwargs.path or args[0]
- file-write: kwargs.path + kwargs.text, or args[0] + args[1]
- delete-file: kwargs.path or args[0], file or empty directory only
- shell: run system command (disabled by default)
"""


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
    tool_runtime_pb2_grpc.add_ToolRuntimeServicer_to_server(ToolRuntimeService(), server)

    listen_addr = f"{config.TOOL_RUNTIME_HOST}:{config.TOOL_RUNTIME_PORT}"
    server.add_insecure_port(listen_addr)
    server.start()

    log(f"tool-runtime-service started on {listen_addr}")
    log(f"workspace dir: {config.WORKSPACE_DIR}")
    log(f"shell tools enabled: {config.ENABLE_SHELL_TOOLS}")

    server.wait_for_termination()


if __name__ == "__main__":
    serve()