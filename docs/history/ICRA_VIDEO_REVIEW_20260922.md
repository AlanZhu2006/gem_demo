# GEM 视频审查 — 2026-09-22 当前成片

审查文件：`outputs/icra_submission/GEM_ICRA_submission.mp4`，05:22 导出、encoding version 21。SHA256：`115d3afb49746f39d94fcdf418aded126b6993c8a91b50d155297d3d5a3db56c`。没有改动完整成片或其生成脚本。

## 总体判断

现有结构已经完整：先室内/户外展示收益，再说明跨目标记忆，接着解释方法，最后给定量结果。建议保持这一顺序、白底风格、单行字幕与现有总时长。方法段实际为 82–135 秒，共 53 秒；其最后一页为 119–135 秒，已有 16 秒。问题主要是画面中控制器接口的说明偏抽象，不需要继续增加方法时长或加入更多公式。

## 1. 方法末页：补两行具体接口说明，优先改这里

当前标题：`The controller stays frozen.`
当前副标题：`Verified recall uses the existing interface. Otherwise, native execution.`

后者没有让观众迅速看清“到底增加了哪个输入”。建议保留标题，把副标题替换为两行：

> NavDP: original goal image + verified bearing cue + current depth.
>
> ViNT / NoMaD: verified historical image as the goal.

这是论文 `sec/4_method.tex` 中 Sparse and Dense Readouts / Frozen Controller Interfaces 的直接归纳。NavDP 原目标图识别终点、bearing 给局部方向、depth 支持控制；ViNT/NoMaD 接收的是通过几何验证的历史图。无需再补 DINOv2、匹配器名称、阈值和公式。

当前旁白已经讲到缓存、两类控制器接口、验证失败回退。因此增加画面文字即可，不必把整段配音写得更长。失败回退的旁白/字幕建议把 `GEM preserves native execution` 润色为 `GEM keeps the controller's original inputs.`，表达更直接；此项不是必须重录的技术错误。

布局建议预览：`outputs/icra_submission/review_20260922/method_last_page_proposal.mp4`。16 秒，沿用原片声音、架构图和字幕，只把顶部说明改为两行。该预览用于评估文字量，尚未修改原片的高亮时序。

如果随后微调动画，按实际旁白词边界：119.40–123.90 秒强调缓存与 bearing；123.90–127.60 秒强调 NavDP；127.60–130.30 秒强调 ViNT/NoMaD；130.30–134.70 秒说明验证失败时保留原输入。当前末页很早就把 Dense/Sparse/Adapter 同时框住，后续缺少视觉分工。

## 2. 环境展示存在一处明确的来源标注错误

56–61 秒的六个房屋模型，生成脚本 `render_icra_navmesh_gallery.py` 的输入目录是 `datasets/mp3d_official_20260814/extracted/mp3d`；六个场景都从该目录读取，没有 HM3D 场景。

当前字幕 `These are complete Habitat scenes from HM3D and MP3D.` 把评测范围混同为画面素材来源。

最小修改：画面标题改为 `Example MP3D environments`；旁白改为 `We evaluate in Habitat on HM3D and MP3D.`。这样既正确说明论文评测范围，也准确标出当前示例的来源。无需重新渲染六个场景或更换素材。

## 3. 结果页高亮应稍晚切换，以匹配配音

Table I 当前高亮时间：Revisit 135–142 秒；增益 142–148 秒；Novel 148–155 秒。实际旁白在 147.98–151.02 秒才说 60.7–81.0，此时高亮已经跳到了 Novel。

建议时间：

| 时间 | 高亮 |
|---|---|
| 135–145.65 s | 先让观众阅读整表，不强调特定列 |
| 145.65–147.98 s | Revisit success |
| 147.98–151.02 s | ΔSR / gain |
| 151.02–155 s | Novel success |

Table II(c) 当前在 173 秒切到 Novel，Revisit 8→17 的旁白到 174.95 秒才结束。把这次切换延后到约 174.95 秒即可。Table II(a) 的链完成行持续框选可以保持。

这些调整不需要加时，也不需要再加文字。

## 已核对且无需继续增加内容的部分

- Table I：三个控制器、两个数据集、共享因果历史；Revisit +60.7–81.0 为百分点，Novel 保留/改善，符合论文。
- 三目标完成数 64 vs 12，以及共享两腿历史的 Revisit 8/20→17/20、Novel 4/20→4/20，符合 `tables/continual_meeting.tex`。
- 真机 25/30 vs 4/30、八个室内加两个室外设置，对应 `sec/5_realworld.tex`，不是从当前两个精选视频推导出的数字。
- 真实实验“同一起点、同一目标图、同一 teleoperated survey”与论文的配对协议一致。
- 终片 178.006 秒、19,081,152 bytes（19.08 MB）、1440×810 / 24 fps、逐行、AAC，满足用户提供的时长与格式限制。余量仅约 2 秒，不建议再延长章节。
- 最新文件哈希与 `submission.verified.json` 一致。本次重新全片解码通过。64 条字幕，最短约 1.35 秒、最高约 20.13 字符/秒；不存在必须通过大改语速才能解决的问题。

## 文档与审查范围

`ICRA_VIDEO_DELIVERY.md` 仍写 v13 的旧顺序、旧大小和旧哈希，不能作为当前成片的准确清单。README 和更早设计记录也存在历史信息。定稿时应按当前 `encoding.json` 和 `submission.verified.json` 同步一次，避免交付错版；这不影响当前视频本身。

本次查看全片每 2.5 秒一个画面，共 72 个抽样点，另外放大检查了 10 个方法/结果画面；核对字幕词时间戳、生成代码、来源与论文，并重新解码全片。证据位于 `outputs/icra_submission/review_20260922/`。这不等同于逐帧人工观看或完整人工试听，对声音自然度不作“已完整听审”的保证。
