import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent

OPENVIKING_CONTEXT_GRPC_PORT = int(os.getenv("OPENVIKING_CONTEXT_GRPC_PORT", "5301"))

VIKING_DATA_DIR = Path(os.getenv("VIKING_DATA_DIR", str(BASE_DIR / "viking_data")))

# 本地没有 openviking 时可打开，用于先跑通服务链路。
MOCK_VIKING = os.getenv("MOCK_VIKING", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

DEFAULT_MAX_MESSAGES = int(os.getenv("DEFAULT_MAX_MESSAGES", "6"))
DEFAULT_TOKEN_BUDGET = int(os.getenv("DEFAULT_TOKEN_BUDGET", "2048"))
