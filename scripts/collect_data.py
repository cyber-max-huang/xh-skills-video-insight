#!/usr/bin/env python3
"""
Video Insight — Data Collection.

Runs the first two stages of the video understanding pipeline:
  1. Speech recognition via Fun-ASR-MTL (audio path)
  2. Visual analysis via Qwen3.6-Plus (visual path)
  3. Time-align both data streams and save intermediate outputs

The downstream report and content-detail generation is handled by
Claude via the SKILL.md instructions.

Usage:
    python3 scripts/collect_data.py --url <video_url> [--output <output_dir>]

Environment:
    DASHSCOPE_API_KEY    Alibaba Cloud Bailian API key (required)
"""

import argparse
import os
import re
import sys
import time

try:
    from .asr import transcribe
    from .vision import analyze
    from .report import build_aligned_data, generate_srt, save_intermediate_data
    from .utils import logger
except ImportError:
    from asr import transcribe
    from vision import analyze
    from report import build_aligned_data, generate_srt, save_intermediate_data
    from utils import logger


def run(video_url: str, output_dir: str = "./video_insight_output",
        fps: float = 1.0, language_hints: list[str] = None) -> dict:
    """
    Run data collection: ASR + Vision → aligned data + SRT.

    Args:
        video_url: Publicly accessible video URL.
        output_dir: Directory to write output files.
        fps: Frame extraction rate for visual analysis (0.1 - 10).
        language_hints: Language codes for ASR, e.g. ['zh', 'en'].

    Returns:
        Dict with paths to generated files.
    """
    # Validate fps range
    if not 0.1 <= fps <= 10:
        raise ValueError(f"fps must be between 0.1 and 10, got {fps}")

    # Basic URL format check
    if not re.match(r'^https?://', video_url):
        raise ValueError(f"Video URL must start with http:// or https://, got: {video_url}")

    start_time = time.time()

    logger.info("=" * 60)
    logger.info("Video Insight — Data Collection")
    logger.info(f"Video URL: {video_url}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"FPS: {fps}, Languages: {language_hints}")
    logger.info("=" * 60)

    # Stage 1: Audio path — Speech Recognition via Fun-ASR-MTL
    logger.info("")
    logger.info("[Stage 1/2] Audio path: Speech recognition via Fun-ASR-MTL...")
    asr_result = transcribe(video_url, language_hints=language_hints)
    asr_text = asr_result.get("full_text", "")
    logger.info(f"[Stage 1/2] Done. Transcribed {len(asr_text)} characters, "
                f"{len(asr_result['sentences'])} sentences.")

    # Stage 2: Visual path — Video understanding via Qwen3.6-Plus
    logger.info("")
    logger.info("[Stage 2/2] Visual path: Video analysis via Qwen3.6-Plus...")
    vision_scenes = analyze(video_url, fps=fps)
    logger.info(f"[Stage 2/2] Done. Detected {len(vision_scenes)} scenes.")

    # Build aligned data + SRT
    logger.info("")
    logger.info("Building aligned data and generating SRT...")
    aligned_data = build_aligned_data(asr_result, vision_scenes)
    srt_content = generate_srt(asr_result)

    # Save all intermediate outputs
    logger.info("")
    logger.info("Saving intermediate outputs...")
    save_intermediate_data(output_dir, srt_content, asr_result, vision_scenes,
                           aligned_data, video_url)

    elapsed = time.time() - start_time
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Data collection complete in {elapsed:.1f}s")
    logger.info(f"Subtitles:     {output_dir}/subtitles.srt")
    logger.info(f"Aligned data:  {output_dir}/aligned_data.md")
    logger.info(f"Debug data:    {output_dir}/pipeline_debug.json")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next: Claude will generate the report and content detail from aligned_data.md")

    return {
        "srt_path": os.path.join(output_dir, "subtitles.srt"),
        "aligned_path": os.path.join(output_dir, "aligned_data.md"),
        "debug_path": os.path.join(output_dir, "pipeline_debug.json"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Video Insight — Collect ASR + vision data for downstream report generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/collect_data.py --url https://example.com/video.mp4
  python3 scripts/collect_data.py --url https://example.com/video.mp4 --output ./results
  python3 scripts/collect_data.py --url https://example.com/video.mp4 --fps 2 --lang zh

Environment:
  DASHSCOPE_API_KEY    Alibaba Cloud Bailian API key (required)
        """,
    )
    parser.add_argument(
        "--url", type=str, required=True,
        help="Publicly accessible video URL to analyze"
    )
    parser.add_argument(
        "--output", "-o", type=str, default="./video_insight_output",
        help="Output directory (default: ./video_insight_output)"
    )
    parser.add_argument(
        "--fps", type=float, default=1.0,
        help="Frame extraction rate for visual analysis [0.1-10] (default: 1.0)"
    )
    parser.add_argument(
        "--lang", type=str, nargs="+", default=None,
        help="Language hints for ASR, e.g. zh en (default: zh en)"
    )

    args = parser.parse_args()

    try:
        run(
            video_url=args.url,
            output_dir=args.output,
            fps=args.fps,
            language_hints=args.lang,
        )
    except (RuntimeError, ValueError) as e:
        logger.error(f"Data collection failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Data collection interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
