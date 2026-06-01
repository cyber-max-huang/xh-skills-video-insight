"""
Audio path: Speech recognition via Fun-ASR-MTL.

Uses Alibaba Cloud Bailian's non-real-time speech recognition API
to transcribe audio from a video/audio file URL.

API reference: https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-api-reference/
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
    )
except ImportError:
    from utils import (
        get_api_key,
        get_dashscope_base_url,
        ms_to_seconds,
        ms_to_srt_time,
        logger,
    )


def transcribe(file_url: str, language_hints=None, timeout_seconds=600) -> dict:
    """
    Submit audio/video for non-real-time ASR transcription and wait for results.

    Args:
        file_url: Publicly accessible URL of the video or audio file.
        language_hints: Optional list of language codes, e.g. ['zh', 'en'].
        timeout_seconds: Maximum time to wait for the async task (default 10 min).

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

    logger.info(f"Submitting ASR task for: {file_url}")
    logger.info(f"Model: fun-asr-mtl, language_hints: {language_hints}")

    try:
        task_response = Transcription.async_call(
            model="fun-asr-mtl",
            file_urls=[file_url],
            language_hints=language_hints,
        )
    except Exception as e:
        raise RuntimeError(f"ASR task submission failed: {e}") from e

    task_id = task_response.output.task_id
    logger.info(f"ASR task submitted, task_id: {task_id}")

    # Poll for completion
    poll_interval = 3  # seconds
    elapsed = 0
    transcription_response = None

    while elapsed < timeout_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval

        transcription_response = Transcription.wait(task=task_id)

        if transcription_response.status_code == HTTPStatus.OK:
            # Check if all subtasks are done
            results = transcription_response.output.get("results", [])
            all_done = all(
                r.get("subtask_status") in ("SUCCEEDED", "FAILED")
                for r in results
            )
            if all_done:
                break
            logger.info(f"ASR tasks not yet complete, waiting... ({elapsed}s)")
        else:
            logger.warning(
                f"ASR query returned status {transcription_response.status_code}, retrying..."
            )

    if elapsed >= timeout_seconds:
        raise RuntimeError(f"ASR transcription timed out after {timeout_seconds}s")

    if transcription_response is None or transcription_response.status_code != HTTPStatus.OK:
        error_msg = getattr(transcription_response, "message", "Unknown error")
        raise RuntimeError(f"ASR transcription failed: {error_msg}")

    logger.info("ASR transcription complete, downloading results...")

    # Parse results
    parsed = _parse_transcription_results(transcription_response)
    logger.info(f"ASR result: {len(parsed['sentences'])} sentences, "
                f"{sum(len(s.get('words', [])) for s in parsed['sentences'])} words")
    return parsed


def _parse_transcription_results(response) -> dict:
    """Parse the raw API response into a structured format."""
    raw = response.output

    all_sentences = []
    all_text_parts = []

    for result_item in raw.get("results", []):
        subtask_status = result_item.get("subtask_status", "")
        if subtask_status != "SUCCEEDED":
            logger.warning(f"Subtask {result_item.get('file_url', '?')} status: {subtask_status}")
            continue

        transcription_url = result_item.get("transcription_url")
        if not transcription_url:
            logger.warning("No transcription_url in result, skipping")
            continue

        try:
            result_data = json.loads(
                request.urlopen(transcription_url).read().decode("utf-8")
            )
        except Exception as e:
            logger.error(f"Failed to download/parse transcription JSON: {e}")
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

    if not all_sentences:
        logger.warning("ASR completed but no sentences were extracted. "
                       "Check if the video has an audio track or try different language hints.")

    return {
        "full_text": "".join(all_text_parts),
        "sentences": all_sentences,
        "total_duration_sec": all_sentences[-1]["end_sec"] if all_sentences else 0,
        "raw": raw,
    }
