"""
视频洞察流水线 — 共享工具模块。
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import unquote, urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("video-insight")

# 项目根目录（用于定位 .env 文件）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """加载项目根目录下的 .env 文件（如存在）。"""
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            logger.warning(
                "python-dotenv 未安装，无法加载 .env 文件。"
                "请执行: pip install python-dotenv"
            )


# 模块加载时自动读取 .env
_load_dotenv()


def get_api_key() -> str:
    """
    获取阿里云百炼 API Key。

    优先级：
    1. 项目根目录 .env 文件中的 DASHSCOPE_API_KEY
    2. 系统环境变量 DASHSCOPE_API_KEY
    """
    key = os.getenv("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError(
            "未设置 DASHSCOPE_API_KEY。\n"
            "方式一：复制 .env.example 为 .env，填入你的 API Key\n"
            "方式二：设置环境变量 export DASHSCOPE_API_KEY='sk-xxx'\n"
            "获取 API Key: https://help.aliyun.com/zh/model-studio/get-api-key"
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


def parse_hhmmss(time_str: str) -> float:
    """Parse HH:MM:SS or HH:MM:SS.mmm string to seconds (float)."""
    # Clean the string
    time_str = time_str.strip()
    # Try HH:MM:SS or HH:MM:SS.mmm
    match = re.match(r"(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?", time_str)
    if match:
        h, m, s, ms = match.groups()
        total = int(h) * 3600 + int(m) * 60 + int(s)
        if ms:
            total += float(f"0.{ms}")
        return total
    raise ValueError(f"Unable to parse time string: '{time_str}'")


def ms_to_seconds(ms: int) -> float:
    """Convert milliseconds to seconds (float)."""
    return ms / 1000.0


def load_json_file(path: str) -> dict:
    """Load and parse a JSON file. Returns empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load JSON from {path}: {e}")
        return {}


def save_text_file(path: str, content: str):
    """将文本内容写入文件，自动创建父目录。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"已保存: {path}")


def extract_output_dirname(video_url: str) -> str:
    """
    从视频 URL 中提取文件名作为输出目录名。

    处理逻辑：
    1. 解析 URL，提取路径最后一段（文件名）
    2. URL 解码（处理 %20、中文编码等）
    3. 去除文件扩展名（.mp4、.avi 等）
    4. 过滤文件系统非法字符
    5. 限制长度（最多 200 字符）
    6. 空结果时回退到时间戳命名

    示例：
        https://example.com/video/FMEA%20Explained.mp4
        → "FMEA Explained"

        https://example.com/视频/我的视频.mp4?token=xxx
        → "我的视频"

    Args:
        video_url: 视频 URL。

    Returns:
        适合作为目录名的字符串。
    """
    try:
        parsed = urlparse(video_url)
        # 取路径最后一段
        path_segments = [s for s in parsed.path.split("/") if s]
        if not path_segments:
            raise ValueError("URL 路径中未找到文件名")

        filename = path_segments[-1]
    except Exception:
        logger.warning(f"无法从 URL 解析文件名: {video_url}")
        filename = ""

    # URL 解码（处理 %20、%E4%B8%AD%E6%96%87 等）
    decoded = unquote(filename)

    # 去除文件扩展名
    name_without_ext = re.sub(r"\.[^.]+$", "", decoded) if "." in decoded else decoded

    if not name_without_ext:
        # 回退：使用时间戳
        import datetime
        name_without_ext = f"video_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.warning(f"文件名为空，使用回退名称: {name_without_ext}")

    # 过滤文件系统非法字符（保留字母、数字、中文、空格、常用标点）
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", name_without_ext)
    # 合并多个空格/下划线
    safe_name = re.sub(r"[\s_]+", " ", safe_name).strip()
    # 去掉首尾的点号和连字符
    safe_name = safe_name.strip(".-_ ")

    # 限制长度（大多数文件系统的路径组件限制为 255 字节）
    if len(safe_name) > 200:
        safe_name = safe_name[:200].rsplit(" ", 1)[0]
        logger.warning(f"目录名过长，已截断至: {safe_name}")

    if not safe_name:
        import datetime
        safe_name = f"video_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.warning(f"处理后名称为空，使用回退名称: {safe_name}")

    return safe_name


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
    retryable_errors: tuple = (Exception,),
    max_delay: float = 60.0,
):
    """
    指数退避重试执行函数。

    Args:
        func: 待执行的可调用对象。
        max_retries: 首次失败后最大重试次数（默认 3）。
        base_delay: 首次重试前等待秒数（默认 2）。
        backoff_factor: 连续延迟的倍乘系数（默认 2）。
        retryable_errors: 触发重试的异常类型元组。
        max_delay: 重试间最大等待秒数（默认 60）。

    Returns:
        func 的返回值。

    Raises:
        RuntimeError: 所有重试均已耗尽。
        KeyboardInterrupt: 用户中断，不重试。
    """
    # 不可重试的异常：用户中断和系统退出
    NON_RETRYABLE = (KeyboardInterrupt, SystemExit)

    last_exception = None
    delay = base_delay

    for attempt in range(max_retries + 1):
        try:
            return func()
        except NON_RETRYABLE:
            raise
        except retryable_errors as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"第 {attempt + 1}/{max_retries + 1} 次尝试失败: {e}。"
                    f"{delay:.1f} 秒后重试..."
                )
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(
                    f"全部 {max_retries + 1} 次尝试均失败。最后错误: {e}"
                )

    raise RuntimeError(
        f"操作在 {max_retries + 1} 次尝试后仍失败。"
        f"最后错误: {last_exception}"
    )
