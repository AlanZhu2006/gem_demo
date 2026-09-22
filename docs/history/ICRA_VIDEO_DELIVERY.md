# GEM ICRA accompanying video — v24

在 v23 的画面设计上补全旁白转场：开场引出室内记忆导航，演示引出共享几何机制，方法引出跨控制器评测。重新生成相关配音、字幕与按语音驱动的高亮；完整时间轴仍为 178 秒。

## 当前文件

- [完整投稿视频](outputs/icra_submission/GEM_ICRA_submission.mp4)
- [开场与室内段试听](outputs/icra_submission/GEM_voice_preview.mp4)
- [53 秒方法段预览](outputs/icra_submission/GEM_method_voiced_preview.mp4)
- [结果页预览](outputs/icra_submission/GEM_results_voiced_preview.mp4)
- [高清有声母版](outputs/icra_submission/GEM_ICRA_narrated_master.mp4)
- [实际英文稿及依据](outputs/icra_submission/ENGLISH_SCRIPT.md)
- [SRT](outputs/icra_submission/GEM_English.srt) / [ASS](outputs/icra_submission/GEM_English.ass)
- [方法布局说明](ICRA_METHOD_EXPLANATIONS.md)
- [验收](outputs/icra_submission/submission.verified.json)

## 时间轴

| 时间 | 内容 |
|---|---|
| 0–11 s | opening |
| 11–32 s | realworld |
| 32–56 s | outdoor |
| 56–61 s | environments |
| 61–82 s | simulation |
| 82–135 s | method |
| 135–178 s | results |

方法依次为 a 82–92、b 92–102、c 102–119、完整架构 119–135 秒。结果为 Table I 135–155、Table II(a) 155–167、Table II(c) 167–178 秒。

## 本轮修改

- 开场→室内：`We first show how this memory supports an indoor revisit…`，把前面的记忆概念落到图像目标任务。
- 真机→仿真：`We also evaluate in Habitat…`，说明评测范围的扩展。
- 演示→方法：`These revisits rely on shared geometry…`，从刚展示的行为转到实现机制。
- 方法→结果：`To test these benefits across controllers…`，明确 Table I 的评测目的。
- Table I→连续导航：`When we extend the evaluation to continuous navigation…`，解释 Table II 相对于前一实验增加的条件。
- 保留 v23 的核心图外说明、1/2/3 步骤、连续运镜、专业标题与室内玻璃墙标注。未新增屏幕说明句；承接由旁白和同步字幕完成。
- 根据新语音实际词时间戳重绘高亮；字幕仍按语义短语显示，连贯句内不额外插入停顿。

## 规格与验收

投稿版 **19,009,643 bytes（19.01 MB）**，178.006 秒，1440×810 / 24 fps / 4,272 帧，逐行 H.264 yuv420p + AAC 单声道。高清母版 1920×1080 / 30 fps / 5,340 帧。

音色 `en-US-AvaMultilingualNeural`。室内段生成速率 −8%，其余 +0%；局部时长适配最大 1.140×。字幕 54 条，保留单行短语显示；长句的语音仍连贯，不把字幕切换当作停顿。最终 AAC 响度 -16.09 LUFS，true peak -1.04 dBTP。

两版本全量解码、源视频与论文哈希、缩放布局对应、字幕可见性、失败灰屏和音轨检查通过；另抽查三处转场的最终压缩画面。符合用户提供的 ≤180 秒、≤20 MB、高度≥480、fps≥20 和逐行条件；未上传。音频技术检查不等于人工完整试听。

SHA256：`03017a4db14bc8e7eb214734a28f3267fb165ea09966d8d600b78c6b06937d2c`。

## 复现

1. 修改 `narration/script.json`，用 `/tmp/gem-voice-env/bin/python synthesize_icra_narration.py` 生成语音。
2. `python build_icra_voiceover.py`，先产生驱动动画所需的词时间戳。
3. 使用 lingbot-map Python 运行 `render_icra_submission.py`。环境变量 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`。
4. 再运行一次 `build_icra_voiceover.py`，记录新视觉母版哈希；然后 `encode_icra_voiceover.py`。
5. 使用 lingbot-map Python 运行 `verify_icra_voiceover.py`。

v23 回退副本位于 `outputs/icra_submission/before_transitions_v23/`。三个独立 finals、原始重建资产及实验记录不变。
