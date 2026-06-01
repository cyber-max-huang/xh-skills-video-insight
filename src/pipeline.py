#!/usr/bin/env python3
"""
视频洞察流水线 — 主入口。

编排完整的视频理解工作流：
  1. 语音识别（Fun-ASR-MTL，音频路径）
  2. 视觉分析（Qwen3.6-Plus，视觉路径）
  3. 时间对齐合并两条数据流
  4. 生成 SRT 字幕和 Markdown 视频理解报告

单视频模式：
    python3 src/pipeline.py --url <视频URL> [--output <输出目录>]

批量模式：
    python3 src/pipeline.py --batch <URL列表文件> [--output <父输出目录>]
    python3 src/pipeline.py --batch <URL列表文件> --dry-run  # 预览模式

配置：
    在项目根目录 .env 文件中设置 DASHSCOPE_API_KEY（推荐）
    或设置环境变量 DASHSCOPE_API_KEY
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
    from .utils import logger, save_text_file, extract_output_dirname
except ImportError:
    from asr import transcribe
    from vision import analyze
    from report import generate_report, generate_srt, generate_content_detail, save_results
    from utils import logger, save_text_file, extract_output_dirname


def run(video_url: str, output_dir: str = None,
        fps: float = 1.0, language_hints: list[str] = None,
        report_model: str = "qwen3.7-max") -> dict:
    """
    运行完整的视频洞察流水线。

    Args:
        video_url: 视频的公开访问 URL。
        output_dir: 输出目录。默认从视频文件名自动生成。
        fps: 视觉分析帧提取率（0.1 - 10）。
        language_hints: ASR 语言代码，如 ['zh', 'en']。
        report_model: 报告生成的文本模型。

    Returns:
        包含生成文件路径的字典：
        {
            "srt_path": "...",
            "report_path": "...",
            "detail_path": "...",
            "debug_path": "..."
        }
    """
    start_time = time.time()

    # 未指定输出目录时，从视频 URL 自动提取文件名
    if output_dir is None:
        output_dir = extract_output_dirname(video_url)
        logger.info(f"输出目录自动生成: {output_dir}")

    logger.info("=" * 60)
    logger.info("视频洞察流水线 — 启动")
    logger.info(f"视频 URL: {video_url}")
    logger.info(f"输出目录: {output_dir}")
    logger.info("=" * 60)

    # 阶段一：音频路径 — Fun-ASR-MTL 语音识别
    logger.info("")
    logger.info("[阶段 1/3] 音频路径：Fun-ASR-MTL 语音识别...")
    asr_result = transcribe(video_url, language_hints=language_hints)
    asr_text = asr_result.get("full_text", "")
    logger.info(f"[阶段 1/3] 完成。转写 {len(asr_text)} 字符，"
                f"{len(asr_result['sentences'])} 个句子。")

    # 阶段二：视觉路径 — Qwen3.6-Plus 视频画面分析
    logger.info("")
    logger.info("[阶段 2/3] 视觉路径：Qwen3.6-Plus 视频画面分析...")
    vision_scenes = analyze(video_url, fps=fps)
    logger.info(f"[阶段 2/3] 完成。检测到 {len(vision_scenes)} 个场景。")

    # 阶段三：合并 — 生成 SRT 字幕 + 视频理解报告 + 内容详情
    logger.info("")
    logger.info("[阶段 3/3] 合并：生成 SRT 字幕、报告和内容详情...")
    srt_content = generate_srt(asr_result)
    report_content = generate_report(asr_result, vision_scenes, video_url,
                                     model=report_model)
    content_detail = generate_content_detail(asr_result, vision_scenes, video_url,
                                              model=report_model)

    # 保存所有输出
    logger.info("")
    logger.info("正在保存输出文件...")
    save_results(output_dir, srt_content, report_content, content_detail,
                 asr_result, vision_scenes, video_url)

    elapsed = time.time() - start_time
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"流水线完成，耗时 {elapsed:.1f} 秒")
    logger.info(f"字幕文件:     {output_dir}/subtitles.srt")
    logger.info(f"理解报告:     {output_dir}/video_insight_report.md")
    logger.info(f"内容详情:     {output_dir}/content_detail.md")
    logger.info(f"调试数据:     {output_dir}/pipeline_debug.json")
    logger.info("=" * 60)

    return {
        "srt_path": os.path.join(output_dir, "subtitles.srt"),
        "report_path": os.path.join(output_dir, "video_insight_report.md"),
        "detail_path": os.path.join(output_dir, "content_detail.md"),
        "debug_path": os.path.join(output_dir, "pipeline_debug.json"),
    }


def main():
    parser = argparse.ArgumentParser(
        description="视频洞察 — 从视频 URL 生成字幕和分析报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
单视频示例：
  python3 src/pipeline.py --url https://example.com/video.mp4
  python3 src/pipeline.py --url https://example.com/video.mp4 --output ./results --fps 2

批量示例：
  python3 src/pipeline.py --batch urls.txt
  python3 src/pipeline.py --batch urls.txt --output ./batch_output --fps 2
  python3 src/pipeline.py --batch urls.txt --dry-run    # 预览模式

批量输入文件格式：
  # 注释行和空行自动跳过
  https://example.com/video1.mp4
  https://example.com/video2.mp4  --lang en --fps 2     # 行级参数覆盖

配置：
  在项目根目录 .env 文件中设置 DASHSCOPE_API_KEY（推荐）
  或设置环境变量 export DASHSCOPE_API_KEY='sk-xxx'
        """,
    )

    # 互斥组：--url 和 --batch 二选一
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--url", type=str, default=None,
        help="待分析的单个视频 URL（必须可公开访问）"
    )
    mode_group.add_argument(
        "--batch", type=str, default=None,
        help="批量输入文件路径（每行一个视频 URL）"
    )

    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="输出目录：单视频模式默认为视频文件名；批量模式默认为 ./batch_output"
    )
    parser.add_argument(
        "--fps", type=float, default=1.0,
        help="视觉分析帧提取率 [0.1-10]（默认：1.0）"
    )
    parser.add_argument(
        "--lang", type=str, nargs="+", default=None,
        help="ASR 语言提示，如 zh en（默认：zh en）"
    )
    parser.add_argument(
        "--report-model", type=str, default="qwen3.7-max",
        help="报告生成模型（默认：qwen3.7-max）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="批量模式下只预览不执行（与 --batch 配合使用）"
    )

    args = parser.parse_args()

    # 参数校验
    if args.dry_run and not args.batch:
        parser.error("--dry-run 只能与 --batch 一起使用")

    try:
        if args.batch:
            # 批量模式 — 延迟导入避免循环依赖
            try:
                from .batch import process_batch
            except ImportError:
                from batch import process_batch

            batch_output_dir = args.output or "./batch_output"
            process_batch(
                urls_file=args.batch,
                parent_output_dir=batch_output_dir,
                fps=args.fps,
                language_hints=args.lang,
                report_model=args.report_model,
                dry_run=args.dry_run,
            )
        else:
            # 单视频模式
            run(
                video_url=args.url,
                output_dir=args.output,
                fps=args.fps,
                language_hints=args.lang,
                report_model=args.report_model,
            )
    except RuntimeError as e:
        logger.error(f"流水线失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("用户中断流水线")
        sys.exit(130)


if __name__ == "__main__":
    main()
