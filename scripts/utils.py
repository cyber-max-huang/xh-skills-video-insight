"""
Shared utilities for the video insight pipeline.
"""

import os
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("video-insight")


def get_api_key() -> str:
    """Get API key from environment. Raise if not set."""
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError(
            "DASHSCOPE_API_KEY environment variable is not set.\n"
            "获取API Key: https://help.aliyun.com/zh/model-studio/get-api-key\n"
            "设置: export DASHSCOPE_API_KEY='sk-xxx'"
        )
    return key


def get_base_url() -> str:
    """Get base URL from environment, default to Beijing region."""
    return os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def get_dashscope_base_url() -> str:
    """Get DashScope API base URL from environment, default to Beijing region."""
    return os.getenv(
        "DASHSCOPE_BASE_HTTP_URL",
        "https://dashscope.aliyuncs.com/api/v1"
    )


def ms_to_hhmmss(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS format."""
    total_seconds = ms / 1000.0
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp format: HH:MM:SS,mmm"""
    total_seconds = ms / 1000.0
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    millis = int(total_seconds * 1000) % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def ms_to_seconds(ms: int) -> float:
    """Convert milliseconds to seconds (float)."""
    return ms / 1000.0


def save_text_file(path: str, content: str):
    """Save text content to a file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Saved: {path}")
