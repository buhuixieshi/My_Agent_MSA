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
SKILL_ROOT_DIR = os.getenv("SKILL_ROOT_DIR", os.path.join(WORKSPACE_DIR, "skill"))
SKILL_VIKING_DATA_DIR = os.getenv("SKILL_VIKING_DATA_DIR", os.path.join(SKILL_ROOT_DIR, "viking_data"))

# 默认关闭任意 shell 执行，避免误用。需要时在 YAML 里显式打开。
ENABLE_SHELL_TOOLS = env_bool("ENABLE_SHELL_TOOLS", False)
