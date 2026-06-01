"""
Data alignment and SRT subtitle generation.

Aligns ASR sentences and vision scenes on the time axis, produces
SRT subtitles, and saves intermediate data for downstream processing.
"""

import json

try:
    from .utils import save_text_file, ms_to_srt_time, logger
except ImportError:
    from utils import save_text_file, ms_to_srt_time, logger


def build_aligned_data(asr_result: dict, vision_scenes: list[dict]) -> str:
    """
    将ASR语音和视觉场景在时间轴上对齐，生成格式化文本。

    每个视觉场景会找到重叠的ASR句子并将语音与画面交织呈现。
    未被任何视觉场景覆盖的ASR句子会追加在末尾。
    如果视觉场景为空，则只输出纯语音内容。
    """
    sentences = asr_result.get("sentences", [])

    if not vision_scenes:
        # 没有视觉数据时，只输出语音内容
        return _build_voice_only_view(sentences)

    lines = []
    matched_sentence_indices = set()

    for scene in vision_scenes:
        start_sec = scene["start_sec"]
        end_sec = scene["end_sec"]
        start_str = scene["start_time"]
        end_str = scene["end_time"]

        matched = [
            (i, s) for i, s in enumerate(sentences)
            if _overlaps(s["begin_sec"], s["end_sec"], start_sec, end_sec)
        ]

        lines.append(f"### [{start_str} - {end_str}]")

        if matched:
            lines.append(f"**语音**：{''.join(s['text'] for _, s in matched)}")
            for idx, _ in matched:
                matched_sentence_indices.add(idx)
        else:
            lines.append("**语音**：（无语音）")

        lines.append(f"**画面**：{scene['description']}")
        lines.append("")

    # 追加未被任何视觉场景覆盖的剩余句子
    leftover = [(i, s) for i, s in enumerate(sentences) if i not in matched_sentence_indices]
    if leftover:
        lines.append("### 补充语音片段（无对应画面）")
        for _, s in leftover:
            lines.append(f"**语音** [{ms_to_srt_time(s['begin_ms'])}]：{s['text']}")

    return "\n".join(lines)


def _build_voice_only_view(sentences: list[dict]) -> str:
    """当没有视觉场景数据时，构建纯语音的文本视图。"""
    if not sentences:
        return "（无语音数据）"

    lines = ["### 语音内容（无视觉数据）", ""]
    for s in sentences:
        ts = ms_to_srt_time(s["begin_ms"])
        lines.append(f"**语音** [{ts}]：{s['text']}")
    return "\n".join(lines)


def _overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    """Check if two time ranges overlap."""
    return a_start < b_end and b_start < a_end


def generate_srt(asr_result: dict) -> str:
    """
    Generate SRT subtitle content from ASR transcription.
    """
    sentences = asr_result.get("sentences", [])
    if not sentences:
        return "1\n00:00:00,000 --> 00:00:00,000\n(no transcription)\n"

    lines = []
    index = 1
    for s in sentences:
        text = s["text"].strip()
        if not text:
            continue

        lines.append(str(index))
        lines.append(f"{s['srt_begin']} --> {s['srt_end']}")
        lines.append(text)
        lines.append("")
        index += 1

    if not lines:
        return "1\n00:00:00,000 --> 00:00:00,000\n(no transcription)\n"

    return "\n".join(lines)


def save_intermediate_data(
    output_dir: str,
    srt_content: str,
    asr_result: dict,
    vision_scenes: list[dict],
    aligned_data: str,
    video_url: str,
):
    """
    Save SRT subtitles and intermediate data for downstream processing.

    Outputs:
        - subtitles.srt: Standard SRT subtitle file
        - aligned_data.md: Time-aligned ASR + vision data (input for report generation)
        - pipeline_debug.json: Full intermediate data for debugging
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # SRT subtitles
    save_text_file(os.path.join(output_dir, "subtitles.srt"), srt_content)

    # Aligned data for downstream report/content-detail generation
    if not aligned_data.strip():
        logger.warning("Aligned data is empty — report generation may be incomplete")
    save_text_file(os.path.join(output_dir, "aligned_data.md"), aligned_data)

    # Debug data
    debug_data = {
        "video_url": video_url,
        "asr_sentences": asr_result.get("sentences", []),
        "vision_scenes": vision_scenes,
        "asr_full_text": asr_result.get("full_text", ""),
    }
    save_text_file(os.path.join(output_dir, "pipeline_debug.json"),
                   json.dumps(debug_data, ensure_ascii=False, indent=2))

    logger.info(f"Intermediate data saved to: {output_dir}")
