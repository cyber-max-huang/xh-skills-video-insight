# 视频洞察技能

分析视频内容，生成字幕文件和综合理解报告。

## 功能概述

输入一个视频 URL，本技能将生成以下产物：

1. **SRT 字幕文件** — 完整语音转写，带逐句时间戳
2. **视频理解报告** — 综合音频与视觉内容的深度分析
3. **内容详情文章** — 将视频内容改写为纯文字知识文章，彻底去除视频格式痕迹
4. **视频合并文档** — 内容详情与理解报告的拼接（`---` 分隔），文件名 `[video] {视频名}.md`
5. **流水线调试数据** — 中间态 ASR + 视觉数据，便于调试

## 架构

流水线分三个阶段，均使用阿里云百炼模型：

### 阶段一 — 音频路径：语音识别
- **模型**：Fun-ASR（`fun-asr`）
- **功能**：从视频中提取全部语音内容，含词级时间戳
- **接口**：DashScope 异步转写（`dashscope.audio.asr.Transcription`）
- **输出**：结构化 JSON，含句子、词语、时间戳（毫秒级）
- **超时**：1800 秒（30 分钟），轮询间隔递增（3s → 6s → 10s）
- **重试**：指数退避重试（最多 3 次，2s → 4s → 8s），覆盖任务提交和状态查询

### 阶段二 — 视觉路径：视频画面理解
- **模型**：Qwen3.7-Plus（`qwen3.7-plus`）
- **功能**：分析视频帧，生成带时间戳的场景描述（中文输出）
- **接口**：OpenAI 兼容 chat completions，使用 `video_url` 输入类型
- **输出**：JSON 数组，每个元素含时间范围和场景描述
- **配置**：`max_tokens=8192`，`temperature=0.3`，FPS 可调
- **重试**：指数退避重试（最多 3 次，2s → 4s → 8s）

### 阶段三 — 合并与报告生成
- **功能**：将两条数据流按时间轴对齐，调用文本大模型生成最终报告
- **模型**：Qwen3.7-Max（`qwen3.7-max`）
- **配置**：`max_tokens=16384`，`temperature=0.3`
- **重试**：指数退避重试（最多 3 次，2s → 4s → 8s）
- **输出文件**：
  - `subtitles.srt` — 标准 SRT 字幕文件
  - `video_insight_report.md` — 结构化报告，含视频概要、分段详解、关键节点
  - `content_detail.md` — 纯文字知识文章，无任何视频格式词汇，按知识脉络组织
  - `[video] {视频名}.md` — 内容详情与理解报告的拼接文档（`---` 分隔）
  - `pipeline_debug.json` — 中间数据，供调试使用

## 使用方式

当用户要求分析视频、理解视频内容、提取字幕或生成视频报告时调用本技能。

### 前置条件

1. 阿里云百炼 API Key（在项目根目录 `.env` 文件中配置，参考 `.env.example`）
2. Python 3.9+ 及依赖包（`pip install -r requirements.txt`）

### 运行流水线

```bash
python3 src/pipeline.py --url "https://example.com/video.mp4"
```

可选参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--url` | 视频 URL（必填） | — |
| `--output, -o` | 输出目录 | 自动从视频文件名提取 |
| `--fps` | 视觉分析帧率 [0.1-10] | 1.0 |
| `--lang` | ASR 语言提示，如 `zh en` | zh en |
| `--asr-model` | 语音识别模型 | fun-asr |
| `--vision-model` | 视觉理解模型 | qwen3.7-plus |
| `--report-model` | 报告生成模型 | qwen3.7-max |

### 当用户要求分析视频时

1. 确认视频 URL 可公开访问
2. 运行：`python3 src/pipeline.py --url "<视频URL>"`
3. 告知用户生成的文件路径：`subtitles.srt`、`video_insight_report.md`、`content_detail.md`、`[video] {视频名}.md`
4. 主动询问是否需要展示或总结报告内容

## API Key 配置

推荐方式（项目级，不影响全局环境）：

```bash
cp .env.example .env
# 编辑 .env，将 sk-xxx 替换为你的真实 API Key
```

获取 API Key：[阿里云百炼控制台](https://bailian.console.aliyun.com/#/api-key)

## 关键说明

- 视频必须通过公开 URL 访问
- fun-asr 为异步处理，流水线自动轮询等待，最长 30 分钟
- 报告生成阶段通过 Prompt Engineering 将时间对齐后的语音和画面数据合并
- 视觉分析默认 `fps=1.0`（每秒一帧），平衡精度与成本
- 视觉场景描述统一使用中文输出（面向中文用户）；字幕保留原始语音语言
- 所有 API 调用均配备指数退避重试机制，应对瞬时网络故障
- 报告和内容详情生成使用 `max_tokens=16384`，确保长文输出不被截断
- 输出目录默认从视频 URL 中提取文件名，支持中英文及特殊字符的 URL 编解码处理

### 测试视频

```
https://cyber-public.tos-cn-beijing.volces.com/video/test/FMEA%20Explained%20The%20Key%20to%20Proactive%20Risk%20Management.mp4
```

该视频为制药行业 FMEA（失效模式与影响分析）教学视频，时长约 9 分 40 秒，英语讲解为主，末尾含少量中文。
