# xh-skills-video-insight

Video insight skill for Claude Code — extract subtitles and generate comprehensive video understanding reports using Alibaba Cloud Bailian models.

## Quick Start

### 1. Prerequisites

- Python 3.9+
- Alibaba Cloud Bailian API key ([get one here](https://bailian.console.aliyun.com/#/api-key))

### 2. Install

```bash
# Via npx (recommended for Claude Code)
npx skills install xh-skills-video-insight

# Or manually
git clone <repo-url>
cd xh-skills-video-insight
pip install -r requirements.txt
```

### 3. Set API Key

```bash
export DASHSCOPE_API_KEY="sk-xxx"
```

### 4. Run

```bash
python3 src/pipeline.py --url "https://example.com/video.mp4"
```

## Output

The pipeline generates three files in the output directory:

| File | Description |
|------|-------------|
| `subtitles.srt` | Full speech transcription in SRT format with timestamps |
| `video_insight_report.md` | Comprehensive report: overview, segment analysis, key points |
| `pipeline_debug.json` | Intermediate data for debugging |

## Pipeline Architecture

```
Video URL
  │
  ├─→ Fun-ASR-MTL ──→ Speech transcription (sentences + word timestamps)
  │
  ├─→ Qwen3.6-Plus ──→ Visual scene descriptions (time ranges + descriptions)
  │
  └─→ Time-aligned merge ──→ Qwen-Plus ──→ Report (Markdown) + Subtitles (SRT)
```

### Models Used

| Stage | Model | API | Purpose |
|-------|-------|-----|---------|
| Audio | `fun-asr-mtl` | DashScope Async | Non-real-time speech recognition with word-level timestamps |
| Visual | `qwen3.6-plus` | OpenAI Compatible | Video frame analysis with timestamped scene descriptions |
| Report | `qwen-plus` | OpenAI Compatible | Merge audio + visual data to generate comprehensive report |

## CLI Options

```
python3 src/pipeline.py --url <VIDEO_URL> [OPTIONS]

Options:
  --url URL           Video URL to analyze (required)
  --output, -o DIR    Output directory (default: ./video_insight_output)
  --fps FLOAT         Frame rate for visual analysis [0.1-10] (default: 1.0)
  --lang LANG [LANG]  Language hints for ASR (default: zh en)
  --report-model M    Model for report generation (default: qwen-plus)
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DASHSCOPE_API_KEY` | Alibaba Cloud Bailian API key | (required) |
| `DASHSCOPE_BASE_URL` | OpenAI-compatible base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `DASHSCOPE_BASE_HTTP_URL` | DashScope API base URL | `https://dashscope.aliyuncs.com/api/v1` |
