# 视频洞察 Skill

这是一个 Claude Code Skill。完整的 Skill 定义、编排指令、报告生成提示词和输出格式规范请见 **SKILL.md**。

## 快速参考

- **Skill 名称**：`xh-skills-video-insight`
- **触发条件**：用户要求分析视频、提取字幕、生成视频报告
- **API 依赖**：`DASHSCOPE_API_KEY`（阿里云百炼）
- **入口脚本**：`python3 scripts/collect_data.py --url "<视频URL>" --output <输出目录>`
- **产出文件**：`subtitles.srt`、`aligned_data.md`、`video_insight_report.md`、`content_detail.md`

## 架构（两阶段）

```
视频URL
  ├─→ Fun-ASR-MTL ──→ 语音转录（句子 + 词级时间戳）
  ├─→ Qwen3.6-Plus ──→ 视觉场景描述（时间段 + 描述文本）
  └─→ 时间对齐 ──→ 中间数据
                       ↓
          Claude（按SKILL.md指令）──→ 视频理解报告 + 内容详情
```

- **阶段1**：Python脚本负责数据采集（ASR + 视觉 → 对齐数据 + SRT字幕）
- **阶段2**：Claude负责报告生成（读取对齐数据，按SKILL.md中的提示词生成报告和内容详情）
