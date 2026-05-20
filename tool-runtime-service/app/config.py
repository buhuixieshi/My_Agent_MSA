import os


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


TOOL_RUNTIME_HOST = os.getenv("TOOL_RUNTIME_HOST", "0.0.0.0")
TOOL_RUNTIME_PORT = env_int("TOOL_RUNTIME_PORT", 5303)

WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/app/workspace")
MAX_LIST_FILES = env_int("MAX_LIST_FILES", 500)
MAX_READ_BYTES = env_int("MAX_READ_BYTES", 1024 * 1024)
DEFAULT_TIMEOUT_SECONDS = env_int("DEFAULT_TIMEOUT_SECONDS", 30)

# 所有用户共用的技能安装目录，不按 user_id 分隔。
# 容器内路径默认 /app/workspace/skill，用于 OpenViking 导入和技能执行。
SKILL_ROOT_DIR = os.getenv("SKILL_ROOT_DIR", os.path.join(WORKSPACE_DIR, "skill"))
SKILL_VIKING_DATA_DIR = os.getenv("SKILL_VIKING_DATA_DIR", os.path.join(SKILL_ROOT_DIR, "viking_data"))

# clawhub 命令默认在容器外部虚拟机/WSL 执行，而不是在 tool-runtime 容器里执行。
# 下载指令默认形态：
#   clawhub install <skill> --dir /srv/nfs/my-agent/workspace/skill --force
# 外部机上的 /srv/nfs/my-agent/workspace/skill 必须和容器内 /app/workspace/skill 是同一份共享目录。
CLAW_DOWNLOAD_MODE = os.getenv("CLAW_DOWNLOAD_MODE", "external-vm").lower()
CLAW_EXTERNAL_VM_HOST = os.getenv("CLAW_EXTERNAL_VM_HOST", "")
CLAW_EXTERNAL_VM_USER = os.getenv("CLAW_EXTERNAL_VM_USER", "")
CLAW_EXTERNAL_VM_PORT = env_int("CLAW_EXTERNAL_VM_PORT", 22)
CLAW_EXTERNAL_VM_SSH_KEY = os.getenv("CLAW_EXTERNAL_VM_SSH_KEY", "")
CLAW_EXTERNAL_VM_SKILL_ROOT_DIR = os.getenv("CLAW_EXTERNAL_VM_SKILL_ROOT_DIR", "/srv/nfs/my-agent/workspace/skill")
CLAW_EXTERNAL_VM_CLAWHUB_BIN = os.getenv("CLAW_EXTERNAL_VM_CLAWHUB_BIN", "clawhub")
CLAW_EXTERNAL_VM_STRICT_HOST_KEY_CHECKING = env_bool("CLAW_EXTERNAL_VM_STRICT_HOST_KEY_CHECKING", False)

# 默认关闭任意 shell 执行，避免误用。需要时在 YAML 里显式打开。
ENABLE_SHELL_TOOLS = env_bool("ENABLE_SHELL_TOOLS", False)
