# Video Insight Skill

Analyze video content and generate comprehensive understanding reports with subtitles.

## What it does

This skill takes a video URL and produces:
1. **SRT subtitle file** — full speech transcription with timestamps
2. **Markdown video understanding report** — comprehensive analysis combining audio and visual content

## Architecture

The pipeline has three stages using Alibaba Cloud Bailian models:

### Stage 1 — Audio Path: Speech Recognition
- **Model**: Fun-ASR-MTL (`fun-asr-mtl`)
- **What**: Extracts all spoken content from the video with word-level timestamps
- **API**: DashScope async transcription (`dashscope.audio.asr.Transcription`)
- **Output**: Structured JSON with sentences, words, timestamps (milliseconds)

### Stage 2 — Visual Path: Video Understanding
- **Model**: Qwen3.6-Plus (`qwen3.6-plus`)
- **What**: Analyzes video frames to produce timestamped scene descriptions
- **API**: OpenAI-compatible chat completions with `video_url` input type
- **Output**: JSON array of scene segments with time ranges and descriptions

### Stage 3 — Merge & Report Generation
- **What**: Time-aligns the two data streams, then calls a text LLM to produce the final report
- **Model**: Qwen-Plus (`qwen-plus`) for report generation
- **Outputs**:
  - `subtitles.srt` — standard SRT subtitle file
  - `video_insight_report.md` — structured report with:
    - Video overview (topic, duration, type, language, style)
    - Segment-by-segment detailed analysis (visual + audio + combined understanding)
    - Key points summary
  - `pipeline_debug.json` — intermediate data for debugging

## How to use

Invoke when the user asks to analyze a video, understand video content, extract subtitles, or generate a video report.

### Prerequisites
1. Alibaba Cloud Bailian API key (set as `DASHSCOPE_API_KEY` environment variable)
2. Python 3.9+ with dependencies installed (`pip install -r requirements.txt`)

### Running the pipeline

```bash
python3 src/pipeline.py --url "https://example.com/video.mp4" --output ./output
```

Optional parameters:
- `--fps 2` — frame rate for visual analysis (default: 1.0, range: 0.1-10)
- `--lang zh en` — language hints for speech recognition (default: zh en)
- `--report-model qwen-max` — model for report generation (default: qwen-plus)

### When the user asks to analyze a video

1. Confirm the video URL is publicly accessible
2. Run: `python3 src/pipeline.py --url "<video_url>" --output ./video_insight_output`
3. Report the paths to generated `subtitles.srt` and `video_insight_report.md`
4. Offer to show or summarize the report contents

## Important notes

- The video must be accessible via a public URL
- Fun-ASR-MTL processes audio asynchronously — the pipeline handles polling automatically
- The report generation step uses prompt engineering to merge time-aligned speech and visual data
- Visual analysis uses `fps=1.0` by default (one frame per second) for detailed coverage
