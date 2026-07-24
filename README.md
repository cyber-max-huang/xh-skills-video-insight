# 视频洞察技能（Video Insight）

基于阿里云百炼模型，从视频 URL 自动提取字幕并生成综合视频理解报告。支持单视频分析和批量处理。

## 快速开始

### 1. 前置条件

- Python 3.9+
- 阿里云百炼 API Key（[在此获取](https://bailian.console.aliyun.com/#/api-key)）

### 2. 安装

```bash
cd xh-skills-video-insight
pip install -r requirements.txt
```

### 3. 配置 API Key（推荐方式）

```bash
cp .env.example .env
# 编辑 .env，将 sk-xxx 替换为你的真实 API Key
```

此方式仅对当前项目生效，不会影响系统全局环境变量。你也可以用传统的 `export DASHSCOPE_API_KEY='sk-xxx'` 方式设置。

### 4. 运行

```bash
# 单个视频
python3 src/pipeline.py --url "https://example.com/video.mp4"

# 批量处理
python3 src/pipeline.py --batch urls.txt

# 批量预览（不调用 API，只确认输出路径）
python3 src/pipeline.py --batch urls.txt --dry-run
```

## 输出文件

每个视频生成 5 个文件，存放在以视频文件名命名的目录中：

| 文件 | 说明 |
|------|------|
| `subtitles.srt` | 完整语音转写，标准 SRT 字幕格式，逐句带时间戳 |
| `video_insight_report.md` | 综合视频理解报告（概要 → 分段详解 → 关键节点） |
| `content_detail.md` | 纯文字知识文章，无任何视频格式痕迹，按知识脉络组织 |
| `[video] {视频名}.md` | 内容详情与理解报告的拼接文档（`---` 分隔） |
| `pipeline_debug.json` | 中间态数据（ASR 句子 + 视觉场景），供调试使用 |

## 流水线架构

```
视频 URL
  │
  ├─ 阶段一 ──→ Fun-ASR ──→ 语音转写（句子 + 词级时间戳）
  │
  ├─ 阶段二 ──→ Qwen3.7-Plus ──→ 视觉场景描述（时间范围 + 中文描述）
  │
  └─ 阶段三 ──→ 时间对齐合并 ──→ Qwen3.7-Max ──→ 报告 + 内容详情 + 字幕
```

### 阶段三详解：对齐数据的作用

阶段三的核心是 **时间对齐**：将同一条时间轴上「画面在展示什么」和「语音在说什么」合并为结构化文本，然后喂给大模型。

```
ASR 语音句子（带时间戳）  ─┐
                            ├── _build_aligned_view() ──→ 对齐文本（内存中）
Vision 场景描述（带时间戳）─┘                                  │
                                                    ┌────────┴────────┐
                                                    ▼                  ▼
                                          视频理解报告.md        内容详情.md
```

对齐逻辑：以视觉场景的时间窗口为主轴，找出与每个场景时间段有交叠的 ASR 句子，格式化为：

```
### [00:00:26 - 00:02:01]
**语音**：讲者解释了FMEA是一种系统化的方法...
**画面**：幻灯片标题"What is FMEA"，右侧展示定义文本...
```

这段对齐文本是**纯中间数据**，直接嵌入 Prompt 发给大模型生成报告，调用结束后不落盘。如需排查报告质量问题，可查看 `pipeline_debug.json`（含原始 ASR 句子和视觉场景的完整 JSON），人工还原对齐过程。

### 模型一览

| 阶段 | 模型 | 接口类型 | 用途 |
|------|------|---------|------|
| 语音识别 | `fun-asr` | DashScope 异步 | 非实时语音识别，词级时间戳，最长支持 12 小时音频 |
| 视觉理解 | `qwen3.7-plus` | OpenAI 兼容 | 视频帧分析，每秒 1 帧采样，生成中文场景描述 |
| 报告生成 | `qwen3.7-max` | OpenAI 兼容 | 综合音频+视觉对齐数据，生成结构化报告和内容文章 |

## 命令行参考

### 单视频模式

```bash
python3 src/pipeline.py --url <视频URL> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--url` | 视频 URL（必填，与 `--batch` 互斥） | — |
| `--output, -o` | 输出目录 | 自动从视频文件名提取 |
| `--fps` | 视觉分析帧率 [0.1-10] | 1.0 |
| `--lang` | ASR 语言提示，空格分隔多个值 | zh en |
| `--asr-model` | 语音识别模型 | fun-asr |
| `--vision-model` | 视觉理解模型 | qwen3.7-plus |
| `--report-model` | 报告生成模型 | qwen3.7-max |

### 批量模式

```bash
python3 src/pipeline.py --batch <URL列表文件> [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--batch` | 批量输入文件路径（必填，与 `--url` 互斥） | — |
| `--output, -o` | 所有视频的父输出目录 | ./batch_output |
| `--dry-run` | 预览模式：只解析 URL 和输出路径，不调用 API | — |
| `--fps` | 全局默认帧率（可被行级参数覆盖） | 1.0 |
| `--lang` | 全局默认语言提示（可被行级参数覆盖） | zh en |
| `--asr-model` | 全局默认语音识别模型（可被行级参数覆盖） | fun-asr |
| `--vision-model` | 全局默认视觉理解模型（可被行级参数覆盖） | qwen3.7-plus |
| `--report-model` | 全局默认报告模型（可被行级参数覆盖） | qwen3.7-max |

### 批量输入文件格式

纯文本文件，每行一个 URL。`#` 开头为注释，空行自动跳过。支持行级参数覆盖：

```
# 制药质量系列
https://example.com/FMEA.mp4
https://example.com/CAPA.mp4  --lang en --fps 2

# 设备操作系列
https://example.com/Isolator.mp4  --report-model qwen-max
```

行级支持的覆盖参数：

| 参数 | 示例 |
|------|------|
| `--lang` | `--lang en` 或 `--lang zh en` |
| `--fps` | `--fps 2` |
| `--asr-model` | `--asr-model fun-asr` |
| `--vision-model` | `--vision-model qwen3.7-plus` |
| `--report-model` | `--report-model qwen-max` |

### 批量模式特性

- **断点续跑**：自动跳过已有 `pipeline_debug.json` 的输出目录。如需重新处理某个视频，删除对应目录后重新运行即可
- **失败继续**：单个视频处理失败不会中断整个批量任务，最后统一汇总
- **汇总报告**：全部完成后自动生成 `batch_summary.md`，包含每个视频的状态、输出目录和耗时

批量输出目录结构：

```
batch_output/
├── batch_summary.md          # 汇总报告
├── 5 Why Analysis .../
│   ├── subtitles.srt
│   ├── video_insight_report.md
│   ├── content_detail.md
│   ├── [video] 5 Why Analysis ....md
│   └── pipeline_debug.json
├── FMEA Explained .../
│   └── (5 files)
└── ...
```

## 输出目录命名规则

未指定 `--output` 时，输出目录名自动从视频 URL 中提取：

| URL | 输出目录 |
|-----|---------|
| `https://.../FMEA%20Explained.mp4` | `FMEA Explained/` |
| `https://.../%E6%88%91%E7%9A%84%E8%A7%86%E9%A2%91.mp4` | `我的视频/` |
| `https://.../video.mp4?token=xxx` | `video/` |

处理逻辑：URL 解析 → 取路径末段 → URL 解码 → 去扩展名 → 过滤非法字符 → 限长 200 字符 → 空值回退时间戳。

## 容错机制

所有 API 调用均配备**指数退避重试**（最多 3 次，等待间隔 2s → 4s → 8s）：

| 阶段 | 重试场景 |
|------|---------|
| ASR 提交 | 网络波动、服务瞬时不可用 |
| ASR 轮询 | 单次查询失败不计入重试，等下一轮继续 |
| 视觉分析 | 网络波动、5xx、超时 |
| 报告生成 | 网络波动、5xx |

Ctrl+C 可随时中断流水线，不会被重试机制吞掉。

ASR 异步任务的超时时间为 **30 分钟**（1800 秒），轮询间隔递增（前 10 次 3s → 接下来 30 次 6s → 之后 10s），平衡响应速度与 API 调用频率。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key（**推荐在 `.env` 文件中配置**） | （必填） |
| `DASHSCOPE_BASE_URL` | OpenAI 兼容接口地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `DASHSCOPE_BASE_HTTP_URL` | DashScope 原生接口地址 | `https://dashscope.aliyuncs.com/api/v1` |

## 测试视频

项目提供 4 个制药行业培训视频用于测试（见 `test_batch_input.txt`）：

| 视频 | 时长 | 典型耗时 |
|------|------|---------|
| FMEA Explained: The Key to Proactive Risk Management | ~10 分钟 | ~4 分钟 |
| 5 Why Analysis: A Commonly Used Investigation Tool Explained | ~8 分钟 | ~3 分钟 |
| FMEA, the 10 Step Process to do an FMEA (PFMEA or DFMEA) | ~15 分钟 | ~5 分钟 |
| The 7 Quality Control (QC) Tools Explained with an Example! | ~12 分钟 | ~5 分钟 |
