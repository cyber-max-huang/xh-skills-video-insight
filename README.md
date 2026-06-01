# xh-skills-video-insight

Claude Code Skill —— 分析视频内容，提取SRT字幕，基于阿里云百炼模型生成综合视频理解报告。

## 快速开始

### 1. 前置条件

- Python 3.9+
- 阿里云百炼 API 密钥（[点此获取](https://bailian.console.aliyun.com/#/api-key)）

### 2. 安装

```bash
# 方式一：通过 npx 安装（推荐）
npx skills add xh-skills-video-insight -y

# 方式二：手动克隆安装
git clone <仓库地址>
cd xh-skills-video-insight
pip install -r requirements.txt

# 方式三：软链接到 Claude Code 的 skills 目录
ln -s $(pwd) ~/.claude/skills/xh-skills-video-insight
```

### 3. 设置 API 密钥

```bash
export DASHSCOPE_API_KEY="sk-你的密钥"
```

如需持久化，写入 `~/.zshrc`：

```bash
echo 'export DASHSCOPE_API_KEY="sk-你的密钥"' >> ~/.zshrc
source ~/.zshrc
```

### 4. 使用 Skill

在 Claude Code 中，直接自然语言描述即可触发：

> "帮我分析这个视频：https://example.com/video.mp4"

Skill 会自动完成：
1. 运行数据采集脚本（ASR 语音识别 + 视觉画面分析）
2. 生成视频理解报告（含分段详解和关键节点表格）
3. 生成纯文字内容详情文章

## 输出文件

| 文件 | 说明 |
|------|------|
| `subtitles.srt` | 标准SRT字幕文件，带时间戳 |
| `aligned_data.md` | 时间对齐的语音+画面数据（中间产物） |
| `video_insight_report.md` | 综合视频分析报告：概要、分段详解、关键节点表格 |
| `content_detail.md` | 纯文字知识文章，无视频格式痕迹 |
| `pipeline_debug.json` | 完整的中间数据，供调试使用 |

## 架构

```
视频URL
  ├─→ Fun-ASR-MTL ──→ 语音转录（句子 + 词级时间戳）
  ├─→ Qwen3.6-Plus ──→ 视觉场景描述（时间段 + 描述文本）
  └─→ 时间对齐 ──→ 中间数据（scripts/collect_data.py）
                       ↓
          Claude（按 SKILL.md 中的提示词生成）
          ├─→ video_insight_report.md（视频理解报告）
          └─→ content_detail.md（内容详情文章）
```

### 模型说明

| 阶段 | 模型 | API | 执行者 |
|------|------|-----|--------|
| 语音识别 | `fun-asr-mtl` | DashScope 异步 | Python 脚本 |
| 视觉分析 | `qwen3.6-plus` | OpenAI 兼容 | Python 脚本 |
| 报告 + 内容详情 | — | — | Claude（按 SKILL.md 指令） |

## 命令行参考

```bash
python3 scripts/collect_data.py --url <视频URL> [选项]

选项：
  --url URL           要分析的视频URL（必填）
  --output, -o DIR    输出目录（默认：./video_insight_output）
  --fps FLOAT         视觉分析帧率 [0.1-10]（默认：1.0）
  --lang LANG [LANG]  ASR语言提示（默认：zh en）
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云百炼 API 密钥 | （必填） |
| `DASHSCOPE_BASE_URL` | OpenAI 兼容接口地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `DASHSCOPE_BASE_HTTP_URL` | DashScope API 地址 | `https://dashscope.aliyuncs.com/api/v1` |
