"""
视觉路径：通过 Qwen3.6-Plus 进行视频画面理解。

使用阿里云百炼视觉理解模型分析视频帧，生成带时间戳的场景描述。

接口文档：https://help.aliyun.com/zh/model-studio/vision
"""

import json
import re

from openai import OpenAI

try:
    from .utils import get_api_key, get_base_url, logger, retry_with_backoff
except ImportError:
    from utils import get_api_key, get_base_url, logger, retry_with_backoff

# Prompt template for structured video analysis
VISION_PROMPT = """请详细分析这个视频的内容。按时间顺序描述每个主要场景或事件段落。

要求：
1. 以JSON数组格式输出，每个元素代表一个场景段落
2. 每个场景段落包含以下字段：
   - "start_time": 开始时间，格式为 HH:MM:SS
   - "end_time": 结束时间，格式为 HH:MM:SS
   - "description": 该时间段的画面内容描述（中文，简洁明了）
3. 覆盖整个视频，不要遗漏重要场景
4. 描述中关注：场景变化、人物动作、关键物体、文字信息、画面氛围等

输出格式示例：
```json
[
  {"start_time": "00:00:00", "end_time": "00:00:05", "description": "..."},
  {"start_time": "00:00:05", "end_time": "00:00:12", "description": "..."}
]
```

请直接输出JSON数组，不要输出其他内容。"""


def analyze(video_url: str, fps: float = 1.0) -> list[dict]:
    """
    Analyze video content using Qwen3.6-Plus visual model.

    Args:
        video_url: Publicly accessible video URL.
        fps: Frame extraction rate (frames per second). Range [0.1, 10].
             Default 1.0 for detailed analysis.

    Returns:
        List of scene descriptions with timestamps:
        [
            {"start_time": "00:00:00", "end_time": "00:00:05",
             "start_sec": 0.0, "end_sec": 5.0,
             "description": "..."},
            ...
        ]
    """
    api_key = get_api_key()
    base_url = get_base_url()

    logger.info(f"提交视频视觉分析: {video_url}")
    logger.info(f"模型: qwen3.6-plus, fps: {fps}, max_tokens: 8192")

    client = OpenAI(api_key=api_key, base_url=base_url)

    def _call_vision_api():
        return client.chat.completions.create(
            model="qwen3.6-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {"url": video_url},
                            "fps": fps,
                        },
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ],
            max_tokens=8192,
            temperature=0.3,
        )

    completion = retry_with_backoff(
        func=_call_vision_api,
        max_retries=3,
        base_delay=2.0,
        retryable_errors=(Exception,),
    )

    if not completion.choices or not completion.choices[0].message.content:
        raise RuntimeError("视觉模型返回了空结果，请检查视频是否可访问或重试")

    raw_text = completion.choices[0].message.content
    logger.info(f"视觉模型返回 {len(raw_text)} 字符")

    scenes = _parse_scene_json(raw_text)
    logger.info(f"解析到 {len(scenes)} 个场景段落")

    return scenes


def _parse_scene_json(text: str) -> list[dict]:
    """Extract and parse JSON array from model response."""
    # Try direct JSON parse first
    text = text.strip()

    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        raw_scenes = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON array from text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            logger.error(f"无法将视觉响应解析为 JSON。原始文本:\n{text[:500]}")
            return [{"start_time": "00:00:00", "end_time": "00:00:00",
                     "start_sec": 0, "end_sec": 0,
                     "description": text}]
        try:
            raw_scenes = json.loads(match.group())
        except json.JSONDecodeError:
            logger.error(f"无法解析提取的 JSON。原始文本:\n{text[:500]}")
            return [{"start_time": "00:00:00", "end_time": "00:00:00",
                     "start_sec": 0, "end_sec": 0,
                     "description": text}]

    # Normalize and add numeric timestamps
    scenes = []
    for item in raw_scenes:
        scene = {
            "start_time": item.get("start_time", "00:00:00"),
            "end_time": item.get("end_time", "00:00:00"),
            "description": item.get("description", ""),
        }
        scene["start_sec"] = _parse_time(scene["start_time"])
        scene["end_sec"] = _parse_time(scene["end_time"])
        scenes.append(scene)

    return scenes


def _parse_time(time_str: str) -> float:
    """Parse HH:MM:SS to seconds."""
    time_str = time_str.strip()
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0.0
