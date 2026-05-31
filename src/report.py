"""
Report generation: Align ASR and vision results, produce SRT subtitles
and a comprehensive Markdown video understanding report.
"""

import json
from openai import OpenAI

try:
    from .utils import get_api_key, get_base_url, save_text_file, ms_to_srt_time, logger
except ImportError:
    from utils import get_api_key, get_base_url, save_text_file, ms_to_srt_time, logger

# System prompt for the final video understanding report
REPORT_SYSTEM_PROMPT = """你是一个专业的视频内容分析助手。你会收到同一段视频的两份信息：

1. **字幕文本**：从视频语音中识别出的文字内容，带时间戳
2. **画面描述**：从视频画面中提取的场景描述，带时间戳

你的任务是综合这两份信息，生成一份完整的视频理解报告。

在分析时请遵循以下原则：
- 将字幕和画面在时间轴上对齐，同一个时间窗口里，说了什么、画面展现了什么，结合起来理解
- 如果字幕和画面存在呼应关系（比如说话内容在解释画面中的事物），请明确指出
- 对于没有字幕的时间段，仅根据画面内容进行描述

请严格按照以下结构输出报告（Markdown 格式），以 `# 视频理解报告` 开头：

# 视频理解报告

## 视频概要
- **视频主题**：[一句话概括]
- **视频时长**：[估算的总时长]
- **内容类型**：[教学/演讲/娱乐/新闻/Vlog/产品介绍/其他]
- **语言**：[语种]
- **整体风格**：[正式/轻松/专业/生活化等]

## 分段详解
（将视频按内容逻辑分成若干段落，每段包含以下信息）

### 段落 N：段落标题（[开始时间 - 结束时间]）
- **画面内容**：该时间段画面的整体描述
- **语音内容**：该时间段说话内容的概括（提炼要点，不必逐字复述）
- **综合理解**：结合画面和语音，说明这一段在表达什么，核心信息是什么
- **关键细节**：值得关注的画面细节、语气变化、场景切换等

## 关键节点
（列出视频中最重要的3-8个关键时刻）

| 时间戳 | 节点描述 | 重要性说明 |
|--------|---------|-----------|
| HH:MM:SS | 这个时刻发生了什么 | 为什么这是关键节点 |
| ... | ... | ... |"""


# System prompt for the "内容详情" article — pure text rewrite of video content
CONTENT_DETAIL_SYSTEM_PROMPT = """你是一个专业的内容写作者。你会收到一段视频的综合分析数据（包含语音转写和画面描述），你的任务是把这些信息改写为一篇纯文字文章。

要求：
1. **纯文字表达**：文章中不能出现"画面"、"视频"、"时间戳"、"镜头"、"屏幕"等与视频格式相关的词汇，就像在写一篇知识文章
2. **高度还原**：尽可能详细地还原视频中传达的所有知识点、观点、案例和数据，不要遗漏重要信息
3. **结构清晰**：按照以下结构组织文章：
   - 第一部分：主题概述（对应视频概要）
   - 第二部分：详细内容（对应分段详解，按内容的逻辑层次展开，不要分段标题中出现时间信息）
   - 第三部分：核心要点（对应关键节点，总结最核心的观点）
4. **语言风格**：以视频中的语言为主，保持专业准确的同时兼顾可读性

请以 Markdown 格式输出，文章标题用 `# 内容详情`。"""


def generate_content_detail(
    asr_result: dict,
    vision_scenes: list[dict],
    video_url: str,
    model: str = "qwen-plus",
) -> str:
    """
    Generate a pure-text article rewriting the video content.

    Args:
        asr_result: Parsed ASR transcription from asr.transcribe().
        vision_scenes: Scene descriptions from vision.analyze().
        video_url: The original video URL (for reference).
        model: Text model to use for generation.

    Returns:
        Markdown article string.
    """
    api_key = get_api_key()
    base_url = get_base_url()

    logger.info("Building aligned data for content detail article...")
    aligned_text = _build_aligned_view(asr_result, vision_scenes)

    logger.info(f"Generating content detail article using model: {model}")
    client = OpenAI(api_key=api_key, base_url=base_url)

    user_prompt = f"""以下是一段视频的逐时间窗口对齐数据，包含语音转写和画面描述：

---
{aligned_text}
---

请根据以上信息，生成内容详情文章。记住：纯文字表达，不要出现画面/视频/时间戳等词汇，尽量详细还原所有知识点。"""

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CONTENT_DETAIL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    article = completion.choices[0].message.content
    logger.info(f"Content detail article generated: {len(article)} characters")
    return article


def generate_report(
    asr_result: dict,
    vision_scenes: list[dict],
    video_url: str,
    model: str = "qwen-plus",
) -> str:
    """
    Generate a comprehensive video understanding report.

    Args:
        asr_result: Parsed ASR transcription from asr.transcribe().
        vision_scenes: Scene descriptions from vision.analyze().
        video_url: The original video URL (for reference).
        model: Text model to use for report generation.

    Returns:
        Markdown report string.
    """
    api_key = get_api_key()
    base_url = get_base_url()

    logger.info("Aligning ASR and vision data on time axis...")
    aligned_text = _build_aligned_view(asr_result, vision_scenes)

    logger.info(f"Generating report using model: {model}")
    client = OpenAI(api_key=api_key, base_url=base_url)

    user_prompt = f"""以下是一段视频的逐时间窗口对齐数据，包含语音转写和画面描述：

---
{aligned_text}
---

请根据以上信息，生成视频理解报告。"""

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    report = completion.choices[0].message.content
    logger.info(f"Report generated: {len(report)} characters")
    return report


def _build_aligned_view(asr_result: dict, vision_scenes: list[dict]) -> str:
    """
    Build a time-aligned text view merging ASR and vision data.

    For each time window, interleave what was spoken and what was shown.
    """
    sentences = asr_result.get("sentences", [])

    # Create time windows from vision scenes
    lines = []
    for i, scene in enumerate(vision_scenes):
        start_sec = scene["start_sec"]
        end_sec = scene["end_sec"]
        start_str = scene["start_time"]
        end_str = scene["end_time"]

        # Find overlapping ASR sentences
        matched_sentences = [
            s for s in sentences
            if _overlaps(s["begin_sec"], s["end_sec"], start_sec, end_sec)
        ]

        lines.append(f"### [{start_str} - {end_str}]")

        # Voice content
        if matched_sentences:
            lines.append(f"**语音**：{''.join(s['text'] for s in matched_sentences)}")
        else:
            lines.append("**语音**：（无语音）")

        # Visual content
        lines.append(f"**画面**：{scene['description']}")
        lines.append("")

    # Append any leftover sentences not covered by vision scenes
    if vision_scenes and sentences:
        last_scene_end = vision_scenes[-1]["end_sec"]
        leftover = [s for s in sentences if s["begin_sec"] >= last_scene_end]
        if leftover:
            lines.append("### 补充语音片段")
            for s in leftover:
                lines.append(f"**语音** [{ms_to_srt_time(s['begin_ms'])}]：{s['text']}")

    return "\n".join(lines)


def _overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    """Check if two time ranges overlap."""
    return a_start < b_end and b_start < a_end


def generate_srt(asr_result: dict) -> str:
    """
    Generate SRT subtitle content from ASR transcription.

    Args:
        asr_result: Parsed ASR transcription from asr.transcribe().

    Returns:
        SRT formatted string.
    """
    sentences = asr_result.get("sentences", [])
    if not sentences:
        return "1\n00:00:00,000 --> 00:00:00,000\n(no transcription)\n"

    lines = []
    for i, s in enumerate(sentences, start=1):
        begin = s["srt_begin"]
        end = s["srt_end"]
        text = s["text"].strip()
        if not text:
            continue

        lines.append(str(i))
        lines.append(f"{begin} --> {end}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def save_results(
    output_dir: str,
    srt_content: str,
    report_content: str,
    content_detail: str,
    asr_result: dict,
    vision_scenes: list[dict],
    video_url: str,
):
    """
    Save all pipeline outputs to the output directory.

    Args:
        output_dir: Directory to write outputs to.
        srt_content: SRT subtitle text.
        report_content: Markdown report text.
        content_detail: Content detail article text.
        asr_result: Parsed ASR results.
        vision_scenes: Parsed vision results.
        video_url: Source video URL.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Save SRT subtitle file
    save_text_file(os.path.join(output_dir, "subtitles.srt"), srt_content)

    # Save video understanding report
    report_path = os.path.join(output_dir, "video_insight_report.md")
    save_text_file(report_path, report_content)

    # Save content detail article
    detail_path = os.path.join(output_dir, "content_detail.md")
    save_text_file(detail_path, content_detail)

    # Save intermediate data for debugging/reuse
    debug_data = {
        "video_url": video_url,
        "asr_sentences": asr_result.get("sentences", []),
        "vision_scenes": vision_scenes,
        "asr_full_text": asr_result.get("full_text", ""),
    }
    debug_path = os.path.join(output_dir, "pipeline_debug.json")
    save_text_file(debug_path, json.dumps(debug_data, ensure_ascii=False, indent=2))

    logger.info(f"All outputs saved to: {output_dir}")
