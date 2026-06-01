"""
音频路径：通过 Fun-ASR-MTL 进行语音识别。

使用阿里云百炼非实时语音识别 API，将视频/音频文件 URL 中的语音转为文字。

接口文档：https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-api-reference/
"""

import json
import time
from http import HTTPStatus
from urllib import request

import dashscope
from dashscope.audio.asr import Transcription

try:
    from .utils import (
        get_api_key,
        get_dashscope_base_url,
        ms_to_seconds,
        ms_to_srt_time,
        logger,
        retry_with_backoff,
    )
except ImportError:
    from utils import (
        get_api_key,
        get_dashscope_base_url,
        ms_to_seconds,
        ms_to_srt_time,
        logger,
        retry_with_backoff,
    )


def transcribe(file_url: str, language_hints=None, timeout_seconds=1800) -> dict:
    """
    Submit audio/video for non-real-time ASR transcription and wait for results.

    Args:
        file_url: Publicly accessible URL of the video or audio file.
        language_hints: Optional list of language codes, e.g. ['zh', 'en'].
        timeout_seconds: Maximum time to wait for the async task (default 30 min).

    Returns:
        Parsed transcription dict with structure:
        {
            "full_text": "complete transcribed text",
            "sentences": [
                {
                    "begin_sec": 0.76,
                    "end_sec": 3.24,
                    "text": "sentence text",
                    "words": [
                        {"begin_sec": 0.76, "end_sec": 1.0, "text": "Hello"}
                    ]
                }
            ],
            "raw": { ... original API response ... }
        }

    Raises:
        RuntimeError: If transcription task fails or times out.
    """
    api_key = get_api_key()
    dashscope.base_http_api_url = get_dashscope_base_url()

    if language_hints is None:
        language_hints = ["zh", "en"]

    logger.info(f"提交 ASR 任务: {file_url}")
    logger.info(f"模型: fun-asr-mtl, 语言提示: {language_hints}")

    # Submit ASR task with retry
    task_response = retry_with_backoff(
        func=lambda: Transcription.async_call(
            model="fun-asr-mtl",
            file_urls=[file_url],
            language_hints=language_hints,
        ),
        max_retries=3,
        base_delay=2.0,
        retryable_errors=(Exception,),
    )

    if task_response.output is None:
        raise RuntimeError(f"ASR 任务提交失败: {getattr(task_response, 'message', '未知错误')}")

    task_id = task_response.output.task_id
    logger.info(f"ASR 任务已提交, task_id: {task_id}")

    # Poll for completion with incremental intervals
    # Phase 1: first 10 polls every 3s; Phase 2: next 30 polls every 6s;
    # Phase 3: remaining every 10s
    elapsed = 0
    poll_count = 0
    transcription_response = None

    while elapsed < timeout_seconds:
        poll_count += 1
        if poll_count <= 10:
            poll_interval = 3
        elif poll_count <= 40:
            poll_interval = 6
        else:
            poll_interval = 10

        time.sleep(poll_interval)
        elapsed += poll_interval

        # Query task status with retry for transient failures
        try:
            transcription_response = retry_with_backoff(
                func=lambda: Transcription.wait(task=task_id),
                max_retries=2,
                base_delay=1.0,
                retryable_errors=(Exception,),
            )
        except RuntimeError:
            logger.warning(
                f"ASR query failed after retries, will retry on next poll... ({elapsed}s)"
            )
            continue

        if transcription_response.status_code == HTTPStatus.OK:
            # 检查所有子任务是否完成
            if transcription_response.output is None:
                logger.warning("ASR 查询返回空 output，等待下次轮询...")
                continue
            results = transcription_response.output.get("results", [])
            all_done = all(
                r.get("subtask_status") in ("SUCCEEDED", "FAILED")
                for r in results
            )
            if all_done:
                break
            logger.info(f"ASR 任务尚未完成，等待中... ({elapsed}s)")
        else:
            logger.warning(
                f"ASR 查询返回状态码 {transcription_response.status_code}，将重试..."
            )

    if elapsed >= timeout_seconds:
        raise RuntimeError(f"ASR transcription timed out after {timeout_seconds}s")

    if transcription_response is None or transcription_response.status_code != HTTPStatus.OK:
        error_msg = getattr(transcription_response, "message", "Unknown error")
        raise RuntimeError(f"ASR transcription failed: {error_msg}")

    logger.info("ASR 转写完成，正在下载结果...")

    # Parse results
    parsed = _parse_transcription_results(transcription_response)
    logger.info(f"ASR 结果: {len(parsed['sentences'])} 个句子, "
                f"{sum(len(s.get('words', [])) for s in parsed['sentences'])} 个词")
    return parsed


def _parse_transcription_results(response) -> dict:
    """Parse the raw API response into a structured format."""
    raw = response.output

    all_sentences = []
    all_text_parts = []

    for result_item in raw.get("results", []):
        subtask_status = result_item.get("subtask_status", "")
        if subtask_status != "SUCCEEDED":
            logger.warning(f"子任务 {result_item.get('file_url', '?')} 状态: {subtask_status}")
            continue

        transcription_url = result_item.get("transcription_url")
        if not transcription_url:
            logger.warning("结果中无 transcription_url，跳过")
            continue

        try:
            result_data = json.loads(
                request.urlopen(transcription_url).read().decode("utf-8")
            )
        except Exception as e:
            logger.error(f"下载/解析转写 JSON 失败: {e}")
            continue

        for transcript in result_data.get("transcripts", []):
            for sentence in transcript.get("sentences", []):
                s = {
                    "begin_sec": ms_to_seconds(sentence["begin_time"]),
                    "end_sec": ms_to_seconds(sentence["end_time"]),
                    "begin_ms": sentence["begin_time"],
                    "end_ms": sentence["end_time"],
                    "text": sentence["text"].strip(),
                    "srt_begin": ms_to_srt_time(sentence["begin_time"]),
                    "srt_end": ms_to_srt_time(sentence["end_time"]),
                    "words": [],
                }

                for word in sentence.get("words", []):
                    s["words"].append({
                        "begin_sec": ms_to_seconds(word["begin_time"]),
                        "end_sec": ms_to_seconds(word["end_time"]),
                        "begin_ms": word["begin_time"],
                        "end_ms": word["end_time"],
                        "text": word["text"],
                        "punctuation": word.get("punctuation", ""),
                    })

                all_sentences.append(s)
                all_text_parts.append(s["text"])

    # Sort by begin time
    all_sentences.sort(key=lambda s: s["begin_sec"])

    return {
        "full_text": "".join(all_text_parts),
        "sentences": all_sentences,
        "total_duration_sec": all_sentences[-1]["end_sec"] if all_sentences else 0,
        "raw": raw,
    }
