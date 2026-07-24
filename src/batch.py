"""
批量视频处理模块。

从文本文件中读取视频 URL 列表，逐一调用流水线处理，
支持断点续跑、失败跳过、dry-run 预览和汇总报告生成。
"""

import os
import re
import time

try:
    from .pipeline import run as run_single
    from .utils import logger, extract_output_dirname
except ImportError:
    from pipeline import run as run_single
    from utils import logger, extract_output_dirname


def parse_batch_file(filepath: str) -> list[dict]:
    """
    解析批量输入文件。

    支持的格式：
        # 注释行（跳过）
        （空行，跳过）
        https://example.com/video.mp4
        https://example.com/video.mp4  --lang en --fps 2

    Args:
        filepath: 批量输入文件路径。

    Returns:
        视频条目列表，每项为 {"url": str, "params": dict}。
        params 中的键为 --lang, --fps, --report-model，
        值已转换为对应类型。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 文件为空或没有有效 URL。
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"批量输入文件不存在: {filepath}")

    entries = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            raw = line.strip()

            # 跳过空行和注释行
            if not raw or raw.startswith("#"):
                continue

            # 分离 URL 和可选参数
            url, params = _parse_line(raw, line_num)
            if url:
                entries.append({"url": url, "params": params})

    if not entries:
        raise ValueError(f"批量输入文件中没有有效的视频 URL: {filepath}")

    logger.info(f"从 {filepath} 解析到 {len(entries)} 个视频 URL")
    return entries


def _parse_line(raw: str, line_num: int) -> tuple[str | None, dict]:
    """
    解析一行输入，提取 URL 和覆盖参数。

    格式：
        <URL>
        <URL>  --lang zh --fps 2 --report-model qwen-max

    Args:
        raw: 原始行内容。
        line_num: 行号（用于错误提示）。

    Returns:
        (url, params_dict)，解析失败时返回 (None, {})。
    """
    params = {}

    # 按 " --" 分割，第一个是 URL，后续是参数
    # 注意：URL 本身可能不含空格，这里用 " --" 作为分隔标记
    if " --" in raw:
        parts = raw.split(" --", 1)
        url = parts[0].strip()
        params_str = " --" + parts[1]
        params = _parse_extended_params(params_str, line_num)
    else:
        url = raw.strip()

    # 验证 URL 格式
    if not url.startswith("http://") and not url.startswith("https://"):
        logger.warning(f"第 {line_num} 行不是有效的 URL，已跳过: {url}")
        return None, {}

    return url, params


def _parse_extended_params(params_str: str, line_num: int) -> dict:
    """
    解析扩展参数部分。

    支持的参数：
        --lang zh en        → {"lang": ["zh", "en"]}
        --fps 2             → {"fps": 2.0}
        --asr-model xxx     → {"asr_model": "xxx"}
        --vision-model xxx  → {"vision_model": "xxx"}
        --report-model xxx  → {"report_model": "xxx"}

    Args:
        params_str: 以 " --" 开头的参数字符串。
        line_num: 行号。

    Returns:
        参数字典，键为 run() 函数的参数名。
    """
    params = {}

    # 匹配 --key value 模式，值可含连字符（如模型名 qwen3.7-plus、fun-asr）
    # --lang 支持多个值（如 --lang zh en）
    pattern = r"--(\S+)\s+(.+?)(?=\s+--|$)"
    matches = re.findall(pattern, params_str)

    for key, value in matches:
        value = value.strip()
        if key == "lang":
            params["language_hints"] = value.split()
        elif key == "fps":
            try:
                params["fps"] = float(value)
            except ValueError:
                logger.warning(f"第 {line_num} 行 fps 参数无效: {value}，使用默认值")
        elif key == "asr-model":
            params["asr_model"] = value
        elif key == "vision-model":
            params["vision_model"] = value
        elif key == "report-model":
            params["report_model"] = value
        else:
            logger.warning(f"第 {line_num} 行未知参数: --{key}，已忽略")

    return params


def process_batch(
    urls_file: str,
    parent_output_dir: str = "./batch_output",
    fps: float = 1.0,
    language_hints: list[str] | None = None,
    asr_model: str = "fun-asr",
    vision_model: str = "qwen3.7-plus",
    report_model: str = "qwen3.7-max",
    dry_run: bool = False,
) -> dict:
    """
    批量处理视频列表。

    逐视频串行处理，每个视频输出到 {parent_output_dir}/{视频名称}/。

    特性：
    - 断点续跑：自动跳过已有 pipeline_debug.json 的输出目录
    - 失败继续：单个视频失败不中断批量任务
    - 生成 batch_summary.md 汇总报告

    Args:
        urls_file: 批量输入文件路径。
        parent_output_dir: 所有视频输出的父目录（默认 ./batch_output）。
        fps: 全局默认帧率。
        language_hints: 全局默认语言提示。
        asr_model: 全局默认语音识别模型。
        vision_model: 全局默认视觉理解模型。
        report_model: 全局默认报告模型。
        dry_run: True 时只预览，不实际调用 API。

    Returns:
        汇总字典：
        {
            "total": int,
            "succeeded": int,
            "skipped": int,
            "failed": int,
            "dry_run": bool,
            "results": [
                {
                    "url": str,
                    "output_dir": str,
                    "status": "success" | "skipped" | "failed",
                    "elapsed_sec": float | None,
                    "error": str | None,
                }
            ]
        }
    """
    entries = parse_batch_file(urls_file)

    total = len(entries)
    results = []
    succeeded = 0
    skipped = 0
    failed = 0

    logger.info("=" * 60)
    if dry_run:
        logger.info(f"🔍 批量处理 — 预览模式 (dry-run)")
    else:
        logger.info(f"📦 批量处理 — 共 {total} 个视频")
    logger.info(f"输入文件: {urls_file}")
    logger.info(f"父输出目录: {parent_output_dir}")
    logger.info("=" * 60)

    for i, entry in enumerate(entries, 1):
        url = entry["url"]
        overrides = entry["params"]

        # 合并参数：行级覆盖 > 全局默认
        vid_fps = overrides.get("fps", fps)
        vid_lang = overrides.get("language_hints", language_hints)
        vid_asr_model = overrides.get("asr_model", asr_model)
        vid_vision_model = overrides.get("vision_model", vision_model)
        vid_model = overrides.get("report_model", report_model)

        # 视频专属输出目录
        video_dirname = extract_output_dirname(url)
        output_dir = os.path.join(parent_output_dir, video_dirname)
        debug_file = os.path.join(output_dir, "pipeline_debug.json")

        logger.info("")
        logger.info(f"[{i}/{total}] {url}")
        logger.info(f"  输出目录: {output_dir}")

        if dry_run:
            # 预览模式：只打印信息
            logger.info(f"  fps: {vid_fps}, lang: {vid_lang}")
            logger.info(f"  asr: {vid_asr_model}, vision: {vid_vision_model}, report: {vid_model}")
            if os.path.exists(debug_file):
                logger.info(f"  ℹ️ 已有输出，将被跳过（断点续跑）")
            results.append({
                "url": url,
                "output_dir": output_dir,
                "status": "skipped" if os.path.exists(debug_file) else "pending",
                "elapsed_sec": None,
                "error": None,
            })
            if os.path.exists(debug_file):
                skipped += 1
            continue

        # 断点续跑：已有输出则跳过
        if os.path.exists(debug_file):
            logger.info(f"  ⏭️ 已有输出，跳过")
            results.append({
                "url": url,
                "output_dir": output_dir,
                "status": "skipped",
                "elapsed_sec": None,
                "error": None,
            })
            skipped += 1
            continue

        # 执行流水线
        start_time = time.time()
        try:
            run_single(
                video_url=url,
                output_dir=output_dir,
                fps=vid_fps,
                language_hints=vid_lang,
                asr_model=vid_asr_model,
                vision_model=vid_vision_model,
                report_model=vid_model,
            )
            elapsed = time.time() - start_time
            logger.info(f"  ✅ 完成 ({elapsed:.0f}s)")
            results.append({
                "url": url,
                "output_dir": output_dir,
                "status": "success",
                "elapsed_sec": elapsed,
                "error": None,
            })
            succeeded += 1
        except KeyboardInterrupt:
            logger.warning(f"  ⚠️ 用户中断")
            results.append({
                "url": url,
                "output_dir": output_dir,
                "status": "failed",
                "elapsed_sec": time.time() - start_time,
                "error": "用户中断",
            })
            failed += 1
            break  # 用户中断时立即停止
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ❌ 失败: {e}")
            results.append({
                "url": url,
                "output_dir": output_dir,
                "status": "failed",
                "elapsed_sec": elapsed,
                "error": str(e),
            })
            failed += 1

    # 生成汇总
    summary = {
        "total": total,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "dry_run": dry_run,
        "results": results,
    }

    if not dry_run:
        _generate_batch_summary(summary, parent_output_dir)

    # 打印摘要
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 批量处理汇总")
    logger.info(f"  总计: {total}  |  成功: {succeeded}  |  跳过: {skipped}  |  失败: {failed}")
    if not dry_run:
        logger.info(f"  汇总报告: {parent_output_dir}/batch_summary.md")
    logger.info("=" * 60)

    return summary


def _generate_batch_summary(summary: dict, parent_output_dir: str):
    """
    生成 batch_summary.md 汇总报告。

    Args:
        summary: process_batch() 返回的汇总字典。
        parent_output_dir: 父输出目录。
    """
    lines = [
        "# 批量处理汇总",
        "",
        f"**总计**: {summary['total']} 个视频  "
        f"| ✅ 成功: {summary['succeeded']}  "
        f"| ⏭️ 跳过: {summary['skipped']}  "
        f"| ❌ 失败: {summary['failed']}",
        "",
        "| # | 视频 | 状态 | 输出目录 | 耗时 | 备注 |",
        "|---|------|------|---------|------|------|",
    ]

    for i, r in enumerate(summary["results"], 1):
        status_icon = {"success": "✅ 成功", "skipped": "⏭️ 跳过", "failed": "❌ 失败", "pending": "⏳ 待处理"}

        # 从 URL 提取简短名称
        video_name = extract_output_dirname(r["url"])
        if len(video_name) > 50:
            video_name = video_name[:47] + "..."

        status = status_icon.get(r["status"], r["status"])
        out_dir = r["output_dir"] if r["status"] != "failed" else "—"
        elapsed = f"{r['elapsed_sec']:.0f}s" if r["elapsed_sec"] else "—"
        error_note = f"错误: {r['error'][:60]}" if r["error"] else ""

        lines.append(f"| {i} | {video_name} | {status} | {out_dir} | {elapsed} | {error_note} |")

    summary_path = os.path.join(parent_output_dir, "batch_summary.md")
    os.makedirs(parent_output_dir, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info(f"汇总报告已保存: {summary_path}")
