# ICRA 开场：按 ICRA26 参考片重做（v11）

当前交付为 v11 配音字幕版：177.5 秒，最后一张结果页延长 3 秒，其余视觉时序沿用下述 v9。对照 LogoPlanner 改为 16:9、底部单行粗黑字/白描边、手工短语断句；重新润色英文并合成配音。详细字幕设计见 `ICRA_SUBTITLE_DESIGN.md`，实际讲述与依据见 `outputs/icra_submission/ENGLISH_SCRIPT.md`。以下 174.5 秒等参数描述未加音轨的视觉源。


## 参考片的实际结构

已逐帧查看 `outputs/final/ICRA26.mp4` 的前 13 秒（0–6 秒每 0.5 秒，之后每秒）。参考片从铺满画面的四格动态素材开始，完整标题叠在画面正中央；约 6 秒开始，背景拼屏缩小，露出更多场景。标题保持屏幕中心和固定字号。它不是左右分栏标题页，也不是两张版式交叉淡化。

当前按最新要求，开场恢复 10 秒，重新筛选持续移动的导航素材：

- 0–2.5 s：只展示真机 indoor 走廊，GEM 和完整副标题固定居中；左上角一个匹配 RGB 小窗。
- 2.5–5 s：以 indoor 为中心，从 3× 连续拉远到 1×；走廊保持九宫格中央。
- 标题和完整副标题从第一帧到最后一帧持续保留，不淡出。仅 RGB 小窗在 2.5–4 s 淡出。
- 中心点云使用完整 10 s，外围从 2.5 s 开始，用余下 7.5 s 生长。所有片段到开场最后一帧才完成，没有尾帧等待、循环或片尾白色淡出。
- 整片 174.5 s；10 秒开场保持不变，方法段 10–40 s，结果原表展示 40 s。

旧版的问题是中心在第 7 秒播完，而且短素材中存在停顿。v7 重新选择更长的原始导航窗口；按累计平移及转动选择递增源帧，压缩静止等待。中心约 35.5 s、7.07 m 的原始记录被剪辑为 10 s；外围源片段约 17–58 s。显示是非均匀加速的定性展示，不是同步试验或恒定倍速性能测量。

遥测/仿真轨迹仅用于素材选择和剪辑，重建仍只输入原始 RGB；未生成中间图像、改写规划或给模型输入 GT 位姿。新资产在 `montage_motion/`，旧版留作追溯。

## 候选轨迹来自实际规划记录

旧 v3/v4 主要使用 survey 或 RGB sweep；这些片段没有候选规划，不能由相机轨迹复制出扇形。v5 改用配套原始 RGB 与完整 NavDP 规划记录的片段。九段都具备真实候选轨迹和记录中的选中轨迹，没有绘制手工扇形、重新选择一条更好看的轨迹，或从其他时刻借规划。

视觉沿用已有最终版视频：

- 候选轨迹深灰色，宽度 1.9 tile px。
- 唯一选中轨迹为饱和蓝色，宽度 4.8 tile px，外加 7 px 白色描边。
- 已走轨迹为中性灰色，宽度 3.2 tile px，避免与选中规划混淆。
- 仿真局部轨迹投到固定估计地面，庭院长片段使用当前观测的有效地面高度；使用三维 ribbon 和点云共用 z-buffer。前景墙面、家具可遮挡轨迹。
- 仿真按 source step，真机按原始时间戳匹配最近已发生的规划；超过 3 秒的规划不继续显示。
- 局部坐标和截取比例沿用旧视频实现：灰色候选前 60%，蓝色选中前 80%。仿真 x forward / y left；真机按历史 ROS marker 的 x forward / y right 约定，与 `render_real_final.py` 一致。
- 从相机高度估计模型单位与米的显示比例，未把 GT pose 或 sensor depth 送入 LingBot。布局仅用于可视化，不作为精度评测。

## 当前九段来源

实际输入、源索引、规划来源与运动筛选指标见 `outputs/icra_submission/montage_motion/selection.json` 及各片段 manifest / plans.json。

| 内部名称 | 环境 / 导航记录 | 源帧窗口（末端不含） | 路程 |
|---|---|---|---:|
| gallery | 759xd9YjKW5 / visual_pair_138_aligned1 | 80–560 | 15.98 m |
| hall | 1pXnuDYAj8r / screen_253_A40_aligned1 | 0–174 | 6.00 m |
| garden | VVfe2KiqLaN / visual_pair_113_seed2 | 0–240 | 8.03 m |
| stage | PX4nDJXEHrG / visual_pair_011_v1（替换旧 VFuaQ6m2Qom） | 180–580 | 14.13 m |
| terrace | EDJbREhghzL / formal_038 leg A | 0–230 | 7.85 m |
| living | 1LXtFkjw3qL / expansion_241 leg A | 0–350 | 11.99 m |
| courtyard | demo_p035_gem 真机庭院 | 660–1560 | 9.48 m |
| atrium | demo_p037_gem 真机中庭 | 900–1500 | 3.50 m |
| indoor | demo_n_cec2 真机室内，中心场景 | 375–930 | 7.07 m |

六个不同仿真环境与三处真机环境片段；不代表三座不同建筑。路程用于素材选择，不是模型估计精度；真机为记录遥测的近似值。上述窗口内再进行运动采样，精确保留索引在 manifest。

新片段均重新用官方 demo.py 重建；不再截成旧版 65/75/110 个有效预测。每段使用全部有效预测，生成 300 张前缀 tile，点云按观测顺序累计；反光地面仍可能稀疏，不额外补面。

## 方法段与结果页：论文汇报 PPT（v9）

保留论文 Fig. 1 的镜头顺序；页标题改为 System Overview、Memory State and Causal Writing、Localizing an ImageGoal from History、Frozen Controller Interfaces。正文要点直接取自 `sec/4_method.tex`；不再用 One index / History bridges / Remember. Revisit. 等概括性口号。方法页由 20 s 延长至 30 s，各阶段为 10–16、16–22.6、22.6–33.55、33.55–40 s。

结果段由 7 s 扩展为 40 s，直接裁切已确认论文 PDF 第 5 页 Table I/II：Table I 18 s，Table II(a) 11 s，Table II(b,c) 11 s。原表中的全部列和行保留；蓝框按讲述切换行/列，辅助条目只解释论文结论。表格数值对照对应 TeX 文件，当前结果文字依据 main.tex 实际包含的 `sec_lg/5_experiments.tex`。

为保证阅读时间，仿真、室内、户外 demo 统一再加速 1.5 倍，常规段总计 3×并更新角标；两臂保持同一时间轴。章节前 12 帧叠化，目标卡/到达/失败顺序保留。原素材不改写，输出帧到原帧映射保存到 audit。

详细页面内容、表 II 分母与共享历史条件、可选讲述稿和精确时间轴见 `outputs/icra_submission/ENGLISH_SCRIPT.md`。不录制配音；真机 Offline reconstruction 仍不显示，来源说明保留在文档。

## 复现与验证

用 lingbot-map Python，设置 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`：

1. `prepare_icra_motion_montage.py` 索引 RGB 和逐条原样导出规划。
2. `run_icra_montage_reconstruction.py --selection outputs/icra_submission/montage_motion/selection.json` 使用部署文档环境调用官方 demo.py。复用已有同一 RGB 的有效重建。
3. `render_icra_planning_tiles.py --selection outputs/icra_submission/montage_motion/selection.json` 生成点云、灰色候选、粗蓝色选中轨迹；另存不带轨迹的 clean tiles。
4. `verify_icra_planning_montage.py --root outputs/icra_submission/montage_motion` 核对原始候选/选中数组完全相等、只使用过去规划、点云递增和源 RGB 哈希。
5. `render_icra_submission.py`、`encode_icra_submission.py`、`verify_icra_submission.py` 合成与检查完整视频。

复现新的 archive 输入时，先从 `outputs/table2_inventory/formal_038.tar.gz` / `expansion_241.tar.gz` 提取 cec/evaluation 的 history_before_B RGB、full_plan_outputs.jsonl 和 leg_A/actual_trace.json 到 `montage_plans/sources/<archive>/`，保留 tar 内 task/ 层级。

### 长片段的贴地显示

庭院长片段的模型尺度与估计地面存在局部变化，固定一张初始地面会把后半段计划埋入点云。v7 庭院局部规划使用当前 RGB 预测得到的近水平地面高度；无有效地面时沿用最近已观测的有效估计，不把有噪声的平面斜率外推到远处。显示世界坐标与点云保持刚性、不变形，路径仍与点云共用 z-buffer，不使用置顶穿墙绘制。其余八段仍用原固定地面。中心选用生长及轨迹更清晰的室内走廊；中庭改为 900–1500 的后续导航窗口，淘汰先前朝门的稀疏重建。

方法动画实现：`icra_paper_method.py`。边界检查包含进入帧与退出帧的连续性、叠化后与原片比较、论文原图及图注哈希。
