import logging
import os
import sys
from pathlib import Path


def _default_log_path():
    """返回当前系统的用户日志文件路径。"""
    if os.name == "nt":
        data_dir = Path(
            os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        )
    elif sys.platform == "darwin":
        data_dir = Path.home() / "Library" / "Application Support"
    else:
        data_dir = Path(
            os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
        )
    return data_dir / "AiTranslator" / "app.log"


LOG_PATH = _default_log_path()
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

try:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format=LOG_FORMAT,
        encoding="utf-8",
    )
except OSError:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

logger = logging.getLogger("ai_translator")
