#!/usr/bin/env python3
"""
Video Insight Pipeline — Main entry point.

Orchestrates the full video understanding workflow:
  1. Speech recognition via Fun-ASR-MTL (audio path)
  2. Visual analysis via Qwen3.6-Plus (visual path)
  3. Time-aligned merging of both data streams
  4. Generate SRT subtitles and Markdown video understanding report

Usage:
    python3 src/pipeline.py --url <video_url> [--output <output_dir>]

Environment:
    DASHSCOPE_API_KEY    Alibaba Cloud Bailian API key (required)
"""

import argparse
import os
import sys
import time

# Handle both direct script execution and package import
try:
    from .asr import transcribe
    from .vision import analyze
    from .report import generate_report, generate_srt, generate_content_detail, save_results
    from .utils import logger, save_text_file
except ImportError:
    from asr import transcribe
    from vision import analyze
    from report import generate_report, generate_srt, generate_content_detail, save_results
    from utils import logger, save_text_file


def run(video_url: str, output_dir: str = "./video_insight_output",
        fps: float = 1.0, language_hints: list[str] = None,
        report_model: str = "qwen-plus") -> dict:
    """
    Run the complete video insight pipeline.

    Args:
        video_url: Publicly accessible video URL.
        output_dir: Directory to write output files.
        fps: Frame extraction rate for visual analysis (0.1 - 10).
        language_hints: Language codes for ASR, e.g. ['zh', 'en'].
        report_model: Text model for final report generation.

    Returns:
        Dict with paths to generated files:
        {
            "srt_path": "...",
            "report_path": "...",
            "debug_path": "..."
        }
    """
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("Video Insight Pipeline - Starting")
    logger.info(f"Video URL: {video_url}")
    logger.info(f"Output dir: {output_dir}")
    logger.info("=" * 60)

    # Step 1: Audio path — Speech Recognition via Fun-ASR-MTL
    logger.info("")
    logger.info("[Step 1/3] Audio path: Speech recognition via Fun-ASR-MTL...")
    asr_result = transcribe(video_url, language_hints=language_hints)
    asr_text = asr_result.get("full_text", "")
    logger.info(f"[Step 1/3] Done. Transcribed {len(asr_text)} characters, "
                f"{len(asr_result['sentences'])} sentences.")

    # Step 2: Visual path — Video understanding via Qwen3.6-Plus
    logger.info("")
    logger.info("[Step 2/3] Visual path: Video analysis via Qwen3.6-Plus...")
    vision_scenes = analyze(video_url, fps=fps)
    logger.info(f"[Step 2/3] Done. Detected {len(vision_scenes)} scenes.")

    # Step 3: Merge — Generate SRT + Report + Content Detail
    logger.info("")
    logger.info("[Step 3/3] Merging: Generating SRT subtitles, report, and content detail...")
    srt_content = generate_srt(asr_result)
    report_content = generate_report(asr_result, vision_scenes, video_url,
                                     model=report_model)
    content_detail = generate_content_detail(asr_result, vision_scenes, video_url,
                                              model=report_model)

    # Save all outputs
    logger.info("")
    logger.info("Saving outputs...")
    save_results(output_dir, srt_content, report_content, content_detail,
                 asr_result, vision_scenes, video_url)

    elapsed = time.time() - start_time
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Pipeline complete in {elapsed:.1f}s")
    logger.info(f"Subtitles:      {output_dir}/subtitles.srt")
    logger.info(f"Report:         {output_dir}/video_insight_report.md")
    logger.info(f"Content Detail: {output_dir}/content_detail.md")
    logger.info(f"Debug data:     {output_dir}/pipeline_debug.json")
    logger.info("=" * 60)

    return {
        "srt_path": os.path.join(output_dir, "subtitles.srt"),
        "report_path": os.path.join(output_dir, "video_insight_report.md"),
        "detail_path": os.path.join(output_dir, "content_detail.md"),
        "debug_path": os.path.join(output_dir, "pipeline_debug.json"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Video Insight — Generate subtitles and analysis report from a video URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 src/pipeline.py --url https://example.com/video.mp4
  python3 src/pipeline.py --url https://example.com/video.mp4 --output ./results
  python3 src/pipeline.py --url https://example.com/video.mp4 --fps 2 --lang zh

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
    parser.add_argument(
        "--report-model", type=str, default="qwen-plus",
        help="Text model for report generation (default: qwen-plus)"
    )

    args = parser.parse_args()

    try:
        run(
            video_url=args.url,
            output_dir=args.output,
            fps=args.fps,
            language_hints=args.lang,
            report_model=args.report_model,
        )
    except RuntimeError as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
