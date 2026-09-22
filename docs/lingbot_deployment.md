> Canonical LingBot-Map operations handbook for this repo (copied from `AnchorScale/docs/lingbot_deployment.md` on 2026-09-22). Relative links are rewritten for `gem_demo/docs/`. Dated ICRA assembly notes live in [`PRODUCTION.md`](PRODUCTION.md); this file is the source of truth for how to run LingBot, how poses must be consumed, and why joint sessions exist.

# LingBot-Map 操作手册

**当前最终交付（2026-09-21）**：
[仿真](../outputs/final/simulation.mp4) ·
[室内真机](../outputs/final/realworld.mp4) ·
[户外真机](../outputs/final/outdoor.mp4) ·
[复现、验证与清理说明](history/FINAL_DELIVERY.md)。
已统一白底、加大加粗字体、分臂到达框和 Baseline 真灰度失败画面。
旧导出视频/预览已按用户要求清理；后文迭代记录里的旧媒体路径仅供历史说明，
当前交付路径以此处及 `FINAL_DELIVERY.md` 为准。原始数据和模型输出保留。

**完整 ICRA accompanying video**：[投稿版](../outputs/icra_submission/GEM_ICRA_submission.mp4) · [英文稿及字幕](../outputs/icra_submission/ENGLISH_SCRIPT.md) · [制作与验收](history/ICRA_VIDEO_DELIVERY.md)。当前 v24：178 秒、19.01 MB，1440×810 / 24 fps。1080p 母版仍只留在实验室磁盘（约 50 MB），不进 GitHub。

**用途**：在本机正确运行 LingBot-Map，把 RGB 序列重建成三维点云，并产出按时间
增量展示的视频。照本文件执行即可，不需要读历史日志。

**最后验证**：2026-09-20。适用范围为本机
`/home/asus/Research/lingbot-map`（HEAD `63fddb3`）+ 权重
`weights/lingbot-map-long.pt`。该仓库已有他人的 attention / camera-head /
streaming 调试修改，**不要 reset、覆盖或擅自改共享模型代码**。

2026-09-20 之前的排查过程、失败证据和已被推翻的结论移到
[`lingbot_deployment_history.md`](lingbot_deployment_history.md)，仅供追溯，
**不要从那里复制命令或结论**。

---

## 1. 环境

```bash
export PATH=/home/asus/miniconda3/envs/lingbot-map/bin:$PATH
export CUDA_HOME=/home/asus/miniconda3/envs/lingbot-map
export LIBRARY_PATH=/home/asus/miniconda3/envs/lingbot-map/targets/x86_64-linux/lib${LIBRARY_PATH:+:$LIBRARY_PATH}
```

这三行是必需的：FlashInfer 要 JIT 编译，缺 `PATH` 会报 `ninja` 找不到，缺后两个
会报链接器找不到 `-lcudart`。**装的东西本来就在，不要重装或改共享环境。**

- Python：`/home/asus/miniconda3/envs/lingbot-map/bin/python`
- Checkpoint：`/home/asus/Research/lingbot-map/weights/lingbot-map-long.pt`
  （本机唯一一个，适合长序列/大场景）
- GPU 可能有别人的任务，**不要批量 kill 进程**。

启动时 `pretrained_path: ''` 的报错来自构造器的空预训练路径，属正常；后续完整
checkpoint 会加载成功且无 missing/unexpected keys。不要把那一行单独解读成权重没加载。

---

## 2. 必须遵守的约定

### 2.1 位姿：导出的 extrinsic 怎么用，取决于你拿它干什么

`pose_encoding_to_extri_intri` 返回 OpenCV 的 w2c；`demo.py:286` 对它取了一次逆。
但**这不等于可以把导出矩阵当 c2w 直接用于点云**：

| 用途 | 正确做法 |
|---|---|
| **读相机轨迹 / 相机中心** | 导出矩阵可按 c2w 用（`point_cloud_viewer.py` 约 217 行即直接取逆生成轨迹） |
| **反投影出点云** | 必须走官方链路：`point_cloud_viewer.py:167` 把该 extrinsic 交给 `unproject_depth_map_to_point_map`，**该函数内部会再取一次逆** |

漏掉第二次变换的后果是明显的平移重影，而且**只在后半段发散**——前半段看着是对的，
所以很容易误判成"模型漂移"。判据：修正前后逐对重投影残差中位数从
**33.23 px 降到 1.45 px**（另一组间隔采样 41.18 → 1.53 px）。

### 2.2 后端：用默认 FlashInfer

**`--use_sdpa` 只在 `keyframe_interval = 1` 时可以替代 FlashInfer。**

当前 `lingbot_map/layers/attention.py` 的 `SDPAAttention.forward` 在 cache 标了
`_skip_append=True` 时**仍然追加 k/v**（独立小测试中缓存帧数从 1 变 2，本应保持 1）。
FlashInfer 的对应路径是 append → attention → rollback。而 `gct_stream.py` 确实会
为非关键帧设置该标志，所以长序列（interval 自动 >1）两者不等价。

该缺陷**未在共享仓库修复**，只记录并绕开。证据：
`gem_demo/outputs/sdpa_skip_append_audit.json`。

### 2.3 关键帧间隔：让 demo.py 自己选

`demo.py` streaming 会自动取：≤320 帧为 `1`，否则 `ceil(N/320)`（962 帧 → `4`）。
**不要自己写死**。`anchorscale` 旧 wrapper 硬编码为 1，是与官方行为的一处差异。

### 2.4 权重精度

`demo.py` 把 aggregator 权重转 **bf16**、heads 保持 **fp32**。旧 wrapper 与 batch
路径是保留 fp32 权重 + bf16 autocast。同一 320 帧窗口下，逐帧深度相对差异中位数的
中位数 0.133%，最大逐帧中位数 0.937%（这是两种实现的输出差异，不是对真值的误差）。

### 2.5 输入帧

- LingBot 是**流式**模型，要求帧间运动小。用稠密帧（平稳行走下 stride 1），
  **不要激进抽帧**。
- 模式：`streaming` 用于 ≤320 帧；`windowed` 只用于非常长（>320 缓存）的序列。
- Loader：`load_and_preprocess_images(mode="crop", image_size=518, patch_size=14)`。
- 图像边长必须能被 `patch_size`（14）整除。

### 2.6 单位与重力

**输出点云是模型单位，不是米**，且重建本身不给重力方向。在点云里拟合首帧地面
（`render_lingbot.py:floor_frame`）在本场景两次都失败，退化成 camera-up fallback。

**可用的替代做法（2026-09-20 验证）**：不要在点云里找地面，用**相机轨迹**找。
机器人以固定高度走在平地上，所以相机中心所在的平面平行于地面：

1. 对相机中心做平面拟合得到法向（用 c2w 的光轴 +y 方向定"下"）。
2. 沿法向下移一个标定的安装高度，即得地面平面。
3. 米制尺度用机身里程计对相机轨迹做 Umeyama 拟合得到。

实测（`gem_demo/ground_frames.json`）：

| run | 相机轨迹平面厚度 p95 | 尺度 | 里程计 Umeyama RMSE |
|---|---:|---:|---:|
| GEM `cec_090850` | 3.6 cm | 0.2008 单位/米 | 0.188 m |
| Baseline `base_091940` | 1.7 cm | 0.2076 单位/米 | 0.063 m |

校验：点云到该平面的高度分布 p95 = **+0.047 m**（几乎没有点落到平面以下），
±5 cm 内占 13.5%（地板），0.05–2 m 占 65.2%（墙与家具）——平面正好卡在点云底部。

尺度是为了画贴地轨迹单独拟合的，**没有回写进重建**。里程计不是真值，所以仍然
不要在视频上加米制刻度。

### 2.7 跨 session 不能合并（已实测）

两条 run 各自是独立的 LingBot session，有各自的坐标系和尺度。两者共享同一段机身
里程计，所以可以链式求 B→A 的相似变换，但**实测这条路不成立**：

| 步骤 | 重叠区最近邻距离 |
|---|---|
| 里程计链式初值 | 中位 29.7 cm |
| 带剔除的相似 ICP 精修 | 10 cm 门限内 2.8 万对应点降到 5.4 cm，**但整个重叠区仍为中位 25.8 cm、p90 53.2 cm** |

也就是说两次 session 的差异**不是一个相似变换能消掉的**，存在非刚性漂移。硬合并
会出现墙面重影。脚本 `gem_demo/register_runs.py`、`gem_demo/icp_refine.py`。

**正确做法不是事后配准，而是一开始就合成一次 session** —— 见 §2.9。

### 2.9 要把两条 run 放进同一张图：拼成一次 streaming session

两条 revisit 从**同一个释放位姿**出发，这给了一个天然的拼接点。把两条 run 的图像
接成一个序列喂给 LingBot，其中**第一条倒放**，接缝就落在两条 run 各自的第一帧之间
——同一地点、几乎同一视角。实测（`gem_demo/outputs/joint_rgb`，Baseline 倒放接
GEM 顺放，共 1749 帧）：

| 检验 | 结果 |
|---|---|
| 接缝处相机中心间距 | **4.2 cm**（相邻帧典型 2.9 cm）——模型没有在跳变处断掉 |
| GEM 腿对自身里程计 Umeyama RMSE | 0.174 m（独立 session 为 0.188 m） |
| Baseline 腿 | 0.082 m（独立 session 为 0.063 m） |
| 两腿相对共享地面平面的高度 | −0.6 cm / +0.6 cm，一致到 1 cm 以内 |
| **LK 重投影（独立几何核查）** | **中位 2.810 px**（113 对），反向约定对照 34.69 px；与 GEM 单独 session 的 2.873 px 持平 |

收益是**两条轨迹不再需要任何配准**：它们就是这次重建自己的相机位姿，同一坐标系，
构造上精确。里程计只用来定各自的播放时钟。

注意事项：

- 帧数翻倍，`keyframe_interval` 自动变大（1749 帧 → 6，缓存约 298 帧，仍在 320
  内）。要同时把 `--max_frame_num` 提到 2048，否则超出 3D RoPE 默认上限 1024。
- 把**重要的那条放在后面**（本例 GEM 在后），它能吃到完整上下文；前 7 帧是 warming
  没有输出，牺牲的是倒放那条的尾部。
- **仍然不要用一个 Umeyama 同时拟合两腿里程计**：实测 RMSE 0.460 m，两腿之间仍有
  约 5% 的相对尺度漂移。这只影响"用里程计画轨迹"的路线；直接用重建位姿就没这问题。
- 拼接前先确认两条 run 的首帧确实相似（全局灰度描述子相关本例 0.561，而 A 末尾对
  B 开头是 −0.142）。
- **位姿因果性要单独说明**：本例先处理 Baseline（录于 09:19）再处理 GEM（录于
  09:08），所以 GEM 的位姿是在模型已经看过"墙钟更晚"的帧之后估计出来的。作为离线
  重建这没问题，但渲染出来像在线建图，容易被误读。渲染器的
  `causal_visibility_pass` **只保证点云不早于自身时间戳出现，不保证位姿估计没有用到
  未来信息**。要严格因果就把那条 run 放在前面，代价是它的前 7 帧 warming 无输出。
  audit json 里记了 `pose_causality` 字段。

### 2.8 把轨迹画进点云（而不是画在上面）

要让轨迹看起来在同一图层，不能用 2D 折线叠加。做法：

1. 把轨迹按 §2.6 的地面平面展开成**稠密带状采样**（沿程和横向都按约半像素间距）。
2. 用**和点云完全相同的 splat + z-buffer** 光栅化，于是家具和绿植会正确遮住它。
3. z 测试加一个约 **16 cm** 的容差。地板点云在远处本身有十几厘米噪声，没有容差
   会把带子啄得断断续续；有了它，效果是"画在地板上"，真正在前面的物体照样遮挡。
4. 从俯视角渲染前必须**裁掉天花板**（按地面高度丢弃 >1.45 m 的点），否则天花板
   会盖住整个地面。
5. 深度图在物体边缘的插值会产生放射状拖影，从斜视角形成"帘子"。用 3×3 深度邻域
   平坦性判据（`spread < 0.035 * d`）滤掉，地图明显变干净。
6. **俯角与高度裁剪要一起调**：高度 h 的物体在俯角 θ 下会在其后方投下
   `h / tan(θ)` 的遮挡带。56° + 裁到 1.45 m 时隔断和绿植盖掉约 1 m 地面，轨迹
   被啄断；改成 **68° + 裁到 1.10 m** 后两条轨迹全程连续。
7. **遮挡只能用"高于地面"的几何**。拿整片点云（含地板）去挡轨迹，会被地板自身十几
   厘米的深度噪声随机啄断；靠加深度容差硬顶又会糊到低矮物体上。正解是另开一个只装
   "高于地面 0.25 m"几何的深度缓冲，轨迹只跟它比，容差归零。
8. **折线转角要用连续切线**。按源线段各自的切线算横向方向，拐弯处内侧缺口外侧凸起，
   呈毛毛虫状；改成对重采样后的中心线取梯度。
9. **路径要一次算好、播放时只截前缀**。每帧对全路径重做平滑和抽稀，新点一加整条的
   量化结果就变一遍，边缘全长闪烁。
10. **当前位置标记要落在画出来的那条平滑线上**。用原始相机中心会偏离平滑轨迹约
    3 cm（p95 6.7 cm）并随步态摆动，在平稳的带子上非常显眼；改后屏幕抖动从
    2.92 px 降到 0.59 px。
11. **播放倍速必须和素材抽帧率整除匹配**。第三人称按 10 fps 抽、×3 播放时每输出帧
    正好推进 1 帧；换成 ×2 就变成 33% 的帧原地不动、67% 跳一帧，看起来像卡顿——
    这不是手持抖动，调稳定器没用。按 30 fps 重抽后 ×2/×3 都均匀，重复帧从 8–17%
    降到 0%。另外，手持走动的抖动本身是带视差的三维运动，2D 仿射稳定只能去掉约 10%。

脚本 `gem_demo/render_indoor_final.py`。

---

## 3. 一次只改一个设置

2026-09 的对照里 SDPA→FlashInfer 同时改了**后端、权重精度、关键帧策略**三样，
所以无法把收益归因到单一原因。要下结论就做同精度、同后端、只改 interval 的消融。

**不要先用滤点掩盖重影**——先把几何和约定查清楚。

---

## 4. 标准流程：RGB → 增量点云视频

以 `gem_demo` 的实际接入为例，工作目录 `/home/asus/Research/pengyue/gem_demo`。

**第 1 步：从 MCAP 提取 RGB 和整数纳秒时间戳。**
只用 RGB，录制深度不进入重建；机身里程计仅用于事后独立诊断。
产物形如 `outputs/<run>_rgb/`：PNG + `manifest.json` + `telemetry_reference.npy`。

**第 2 步：跑官方 demo 入口并导出逐帧数组。**

```bash
python audit_demo_entrypoint.py \
  --reference outputs/<已有reconstruction目录> \
  --out outputs/<新输出目录> --backend flashinfer --export
```

该脚本直接执行真实的 `demo.main`，保留原版的模型加载、精度转换、推理和后处理，
**只把"启动 web 服务器的 viewer 构造器"替换成导出器**，并按官方 viewer 的几何
约定导出相机位姿。默认后端仍是 SDPA，**FlashInfer 必须显式指定**。

> 已知限制：该脚本目前仍要求 `--reference` 指向一个既有 reconstruction 作为
> 时间戳来源，还没改成只读原始 manifest 的通用入口。

**第 3 步：诊断。**

```bash
python inspect_lingbot.py --input outputs/<新输出目录> \
  --compare-input outputs/<对照目录>                      # PLY + 里程计诊断
python audit_pose_convention.py --input outputs/<新输出目录>   # LK 独立重投影
```

**第 4 步：渲染增量视频。**

```bash
python render_lingbot.py --input outputs/<新输出目录> \
  --out outputs/<名字>.mp4
```

产出 MP4、同名四时刻预览 `.jpg`、以及 `.audit.json`（含时间可见性审计）。
默认 15 FPS、2× 播放、1280×720。

**增量展示的时间因果性**：点云严格按原始 ROS log 时间戳加入；前 8 帧是共同的
尺度锚点，所以第一份点云从第 8 帧才显示，避免把初始化用到的未来观测提前画出来。
渲染日志末尾必须出现 `causal visibility PASS`。

> 显示策略：置信度保留 **top 35%**、pixel stride **4**。这是当前视频的选择，
> **不是**原版 viewer 的默认值。

### 新场次入口（不需要既有 reconstruction）

`audit_demo_entrypoint.py` 把 `--reference` 同时当作图像来源、时间戳来源和对照
基准，所以跑不了新场次。新增 `gem_demo/run_lingbot_manifest.py` 只读 RGB
manifest：

```bash
python run_lingbot_manifest.py \
  --manifest outputs/<run>_rgb/manifest.json \
  --out outputs/<run>_demo_flashinfer --backend flashinfer
```

同样直接执行真实 `demo.main`，只替换 viewer 构造器；导出格式与
`audit_demo_entrypoint.py --export` 一致，`reconstruction.json` 可直接喂给
`render_lingbot.py`。默认后端为 FlashInfer。

### 官方离线入口（另一条路，仅取数据时用）

```bash
python lingbot-map/demo_render/batch_demo.py \
    --video_path X.mp4   # 或 --input_folder DIR
    --model_path lingbot-map/weights/lingbot-map-long.pt \
    --output_folder OUT --target_frames 150 --image_stride 1 \
    --no_render --save_predictions
```

保存逐帧 NPZ：`pose_enc, depth, depth_conf, extrinsic, intrinsic, images (0..1 RGB)`。
消费 `extrinsic` 前先读 §2.1。

**它自带的 flythrough 渲染器有 `world_points_from_depth` 缺陷**，所以这里带
`--no_render`，直接消费 NPZ。长序列**不要**加 `--use_sdpa`（见 §2.2）。

---

## 5. 怎么确认自己没接错

这四项都不依赖里程计做真值，可以独立自证：

1. **LK 重投影**（`audit_pose_convention.py`）：图像前后向光流跟踪，cycle error
   <1 px，用模型深度和内参做逐对重投影。接对了应在个位数 px；33 px 那个量级
   说明位姿约定错了。
2. **与官方 viewer 抽样对照**：调用原版 viewer 的几何函数处理同一输入，比较点
   坐标。接对了差异在 **1e-7 模型单位**量级。
3. **轨迹 Sim(3) 诊断**（`inspect_lingbot.py`）：对机身里程计做最佳 Sim(3) 拟合。
   **里程计不是真值，相机/机身杆臂未标定**，所以这个数只能横向比较不同配置，
   **不能当作重建精度**，更不能拿它去修正点云。
4. **causal visibility**：渲染器自查，确认没有提前显示后续时刻的点云。

---

## 6. 实测参考数字（2026-09-20，962 帧 / 62.30 s 室内序列）

| 路径 | 轨迹诊断 RMSE | 重投影残差中位数 |
|---|---:|---:|
| 旧 wrapper / SDPA / interval 1（已修正位姿解释） | 2.389 m | 6.594 px |
| 实际 demo.py / SDPA / 自动 interval 4 | 0.967 m | 6.264 px |
| **实际 demo.py / FlashInfer / 自动 interval 4** | **0.187 m** | **2.873 px** |

再强调一次：轨迹列是对机身里程计的 Sim(3) 拟合，不是精度指标。

**当前采用**：最后一行。单条 run 的成片
`gem_demo/outputs/gem_lingbot_demo_flashinfer.mp4`（31.27 s，1280×720，2×，
469 视频帧，955 点云时刻，causal visibility PASS），已验收。

**最终 indoor 成片**：`gem_demo/outputs/gem_indoor_joint.mp4`
（31.9 s，1920×1080，2×，causal visibility PASS）。**一张联合重建、两条路径**
（§2.9），轨迹直接取重建的相机轨迹并按 §2.8 贴地绘制，无需配准。脚本
`gem_demo/render_indoor_joint.py`。

片中标出了成败依据：角落放目标图；GEM 在 **+61.4 s** 由其自身的 RGB 到达模块自动
锁定（82 条锁定消息），此时给它的第三人称加绿框，并在地面上它宣布到达的位姿画一个
金色双环；Baseline 全程 **0 次**锁定、人工判失败，结束时变暗且无标记。
**那个环标的是"该 run 自己宣布到达的位姿"，不是独立测绘的目标位置**——本场景的
survey 没有配准进这个坐标系。锁定发生在最后一帧导出位姿之后 0.14 s（它正是终止该
run 的原因），所以触发条件写成"该 run 结束且已锁定"，并留 3 s 尾巴让最终状态停留。

上一版 `gem_indoor_lingbot_final.mp4` 是两行各自独立重建的版本，保留作对照。
两行的播放时钟以**实际起动**为零点（GEM +1.68 s、Baseline +1.48 s），并剪掉
"被指令前进但原地不动"的段落（Baseline 15.2 s，GEM 0 s），避免一行走另一行冻住。
Baseline 的重建用 §4 的新入口跑出（780 帧，FlashInfer）。

---

## 7. 已知未解决项

- SDPA `_skip_append` 缺陷未在共享仓库修复（§2.2）。
- 点云仍是模型单位，重力未标定（§2.6）。
- 收益无法归因到单一参数（§3）。
- 源图像 sensor timestamp 单调但间隔不均：中位 33.36 ms、p90 133.42 ms、
  p99 314.06 ms、最大 834.66 ms，**58 处 >200 ms**。尚未与重投影异常的位置做关联。
  证据：`gem_demo/outputs/source_timing_audit.json`。
- 全程逐段的局部几何一致性尚未逐一核查。
- 目前是推理完成后的增量回放，没有实时前端。
- ~~GEM / Baseline / 手机第三视角的组合视频尚未恢复~~ —— 已完成，见 §6 最终成片。
  跨 session 注册做了但**结论是不可合并**（§2.7）。
- Baseline **单独**那条重建只做了里程计 Sim(3) 诊断（0.063 m），未做 LK 重投影核查；
  但最终成片用的是联合重建，它的 LK 核查已完成（**2.810 px**，见 §2.9）。
- 联合重建里两腿仍有约 5% 相对尺度漂移（联合 Umeyama 0.460 m vs 分腿 0.174/0.082 m），
  所以一条腿的轨迹带宽与规划扇面尺度略有偏差；**不要拿视频量距离**。
- 成片里没有任何单位提示。按 §2.6 不能加米制刻度，但读者可能误以为是米。
- §2.6 的地面/尺度是为绘图单独拟合的，未回写进 `reconstruction.json`。

---

## 8. 写新结论时必须遵守

这几条是从 2026-09 的返工里总结的，违反任何一条都会让下一个人重复踩坑：

1. **结论必须带适用范围。** 写「已修复 / 已验证」时，说清是在**哪条消费路径**上
   验证的。「位姿已修复」对读轨迹成立，不代表对点云成立。
2. **字段简写不能替代链路说明。** 凡是写「导出字段 = 某约定」，必须紧跟一句
   「下游还有谁会再变换一次」。
3. **「等价」必须写出验证时的配置。** 没测过的配置不要让读者以为已覆盖。
4. **一次只改一个设置**，否则无法归因。
5. **不要用滤点掩盖几何问题。**

---

## 9. 相关文件

- 本手册：`docs/lingbot_deployment.md`
- 历史日志存档：[`lingbot_deployment_history.md`](lingbot_deployment_history.md)
- 本轮审计证据与脚本：[`docs/history/DEPLOYMENT_AUDIT.md`](history/DEPLOYMENT_AUDIT.md)
- 视频进度与交接：[`docs/history/VIDEO_PROGRESS_HANDOFF.md`](history/VIDEO_PROGRESS_HANDOFF.md)
- 本地脚本（均在 `gem_demo/`）：
  `audit_demo_entrypoint.py`（真实 demo.main + 导出）、
  `audit_pose_convention.py`（LK 重投影）、
  `inspect_lingbot.py`（PLY 与里程计诊断）、
  `render_lingbot.py`（视频与审计）、
  `lingbot_incremental.py`（提取 + 旧 wrapper，位姿选项必须显式给出）


## 7. 仿真 NNR 视频：到达判定与任务筛选（2026-09-20）

仿真视频的导航成功与 LingBot 重建是两个独立环节。仍通过
`gem_demo/run_lingbot_manifest.py` 调用实际 `demo.py`，使用本手册的
FlashInfer、精度和官方 viewer 位姿约定。不要为了对齐目标而拉伸轨迹或
用 GT 替代预测轨迹；视频中的到达圈应绑定实际 RGB latch 帧。

当前较长 NNR 重做**已完成并验证**：
[`sim_visual_arrival_nnr_joint.mp4`](../outputs/sim_visual_arrival_nnr_joint.mp4)，
56.567 秒、1080p/30 FPS、1697 帧全部解码通过。基于正式 003 的新演示，
GEM 三段 RGB 到达、实走 18.663 m；Baseline 在 C 的 568 步因 stuck 终止。
其剩余尾段明确标注 2.689×，压缩为 3 秒。归档 Table II 的距离成功
不能直接改称 RGB 到达。进度与失败记录见
[`SIM_VIDEO_PROGRESS.md`](history/SIM_VIDEO_PROGRESS.md) 和
[`selection.md`](../outputs/nnr_selection/selection.md)。旧的 NRR
成片保留。新结果的参数、原始到达误差及完整验证均单独记录。

此次发现历史深度 PNG 在 6.5535 m 饱和，会低估曾见过的远处表面，进而
把已见目标误筛成 Novel。253 的一个候选实测：PNG 历史最大共视率 0，
按真实历史位姿重渲染的全精度深度为 0.3645。新的本地 demo 构造器
`construct_visual_goals.py` 因此用全精度重渲染深度检查 N/R 历史支持；
原阈值保持不变，共享 benchmark 代码未修改。该 GT 信息只用于任务生成，
不能进入策略控制或到达条件。每次构造均保存实际执行源码和校验值。

仿真 `aligned-v2` 是真机 RGB verifier 的显式参数变体：scale 0.85–1.12、
center offset ≤0.10、coverage ≥0.20、inlier ratio ≥0.60，两种方法一致。
它通过了 0.456/0.478 m 近目标画面以及 2.461 m 过早到达画面的校准检查，
但这不是独立导航验证，也不保证精确重合世界位姿。不得称为“真机原阈值”。

Baseline 尾段可用 `--baseline-tail-seconds 3` 对共同显示时钟明确加速；
界面显示加速倍数，保留真实终止原因及到达帧。不能为缩短视频提前宣告失败。


新 NNR 两条独立官方重建的 245 帧共同输入产生 238 组完全相同的位姿/深度，
两者最大差均为 0；无跨方法配准。联合单次相似变换的轨迹 RMSE 为 0.175 m，
P95 为 0.323 m，原始轨迹和深度不变。GEM A/B/C 的 GT 位置误差仍是
1.267 / 0.883 / 0.348 m；arrival 圈标记真实 RGB 锁存帧，不代表 GT 位姿重合。

运行注意：不要把完整策略评测和官方重建同时放在此 GPU 上。一次并发尝试
曾导致本次任务自己的 memory server 显存不足；该尝试已作废并完整重跑，
不是导航失败。最终配对结果和后续重建串行执行。已完成的 GEM 筛选重建仅在
691 帧 RGB、位姿及时间戳与完整配对严格一致的检查通过后复用；证据位于
`visual_pair_formal003_aligned2_retry/gem_screen_reproduction.json` 及合并校验中。


## 8. 2026-09-21：仿真地图左侧黑区是地面裁剪误删

`gem_demo/outputs/sim_visual_arrival_nnr_joint.mp4` 的大块缺地板，已通过同视角
消融确认主要来自显示过滤：照搬真机 `height > -0.08 m` 下限，但仿真的深度
地板与基于 GT/位姿的参考地面有偏差。249 个抽样观测保持视角、置信度、平滑
过滤一致，下限改为 -0.30 m 后，左半幅有点云的像素从 100,569 增到 387,911；
全图从 350,955 增到 813,901。再放宽到 -0.60 m，抽样结果无变化。

修复：`render_table2_joint.py --floor-min-height -0.30`（现为仿真默认）；
上限仍 1.10 m，保留 top 35% confidence、stride 3 和原始预测深度/位姿。
没有填充 GT mesh 或假地板。真机 `JointMap` 默认值不改。
新视频：`gem_demo/outputs/sim_visual_arrival_nnr_floorfixed.mp4`。
证据：`gem_demo/outputs/cloud_display_audit/height_ablation.{jpg,json}`；
复现：在 gem_demo 下用 lingbot-map 环境运行 `audit_cloud_display.py`。

**验证教训**：相机轨迹 RMSE、已显示帧数、arrival latch 正确，不代表地面点云
完整；需检查同视角原始点云/过滤后点云及覆盖像素。-0.30 m 是这条序列的显示
容差，不是重建精度声明，也不应未经验证套到所有场景。真机第三人称画面和
轨迹样式与仿真仍有差异；倒序拼接推理与独立正序推理也不是同一个设置。


## 9. 2026-09-21：可选增量表面融合，减少点云重影

仿真 `render_table2_joint.py --cloud-mode tsdf` 使用现有 LingBot 预测做展示层
TSDF 融合：体素 2.5 cm、截断 10 cm、最大深度 12 m，每三个 source step
融合一次，同一共享前缀预测只融合一次。保留原置信度和深度平滑过滤，融合时
使用过滤后的全分辨率深度。仅使用当前已播放观测，不预先融合未来帧。

原始 depth/c2w、导航轨迹、arrival latch 不改；米制换算使用已有 scale。
表面点按体素的投影大小显示，下限 -0.30 m 的地面容差保留。
颜色与表面平均可减少重叠条纹，但会柔化纹理，且不能消除系统性的位姿误差；
不应描述成原始模型重建精度提升。4 cm 体素对照细节损失偏大，选用 2.5 cm。

实现：`gem_demo/cloud_surface_fusion.py`；合成平面验证：
`gem_demo/test_cloud_surface_fusion.py`；完整输出：
`gem_demo/outputs/sim_visual_arrival_nnr_fused.mp4`。每帧融合计数/最后观测步
记录在 `.audit.json`，随原有视频时序一起检查。原始点云版本保留；默认
`--cloud-mode raw`，需要融合时显式指定 `tsdf`。


## 10. 2026-09-21：回到 floor-fixed 点云，统一 joint 风格与 NavDP 局部轨迹

用户选择保留原始 floor-fixed 点云，TSDF 仅作为对照实验。新命令采用
`render_table2_joint.py --presentation joint --cloud-mode raw`，完整结果为
`gem_demo/outputs/sim_visual_arrival_nnr_joint_style.mp4`。真机地图布局、色带亮色
中心线、金框目标图与绿色到达边框复用；仿真左栏只放第一人称原比例画面。

NavDP 数据来自这次实际运行两臂的 `evaluation/full_plan_outputs.jsonl`，按
各 leg 的 diffusion seed 映射到 source step，核对 selected trajectory 的
float64 SHA256 与规划时 GT 位姿。显示几何用规划发出时 LingBot 位姿/朝向，
不使用 GT 重画路线；x 向前、y 向左，第三列是 yaw。仿真的左向量必须为
`cross(up, forward)`，不可将第三列当高度。

局部候选轨迹与选中轨迹投影到统一参考地面上方 2 cm，通过现有障碍深度缓冲
遮挡。候选前 60% 用淡灰线，选中前 80% 用亮色线；最长显示 30 source steps，
切换 leg、到达或终止后停显。参考地面不是逐点真实地形，原始重建误差仍在。
审计含每帧 local plan 的 source step；验证器检查无未来规划、无跨 leg 保留。
原布局可用 `--presentation legacy` 重现，旧视频均保留。


## 11. 2026-09-21：白底目标卡片与 2× 展示

新版 `gem_demo/outputs/sim_visual_arrival_nnr_white_2x.mp4` 使用
`--theme white --presentation joint --cloud-mode raw --steps-per-second 20`。
20 observations/s 相对显式 10 Hz demo 时钟是 2×；保留到达停顿、3 秒尾段和
结束停留，因此不是将旧视频整体时长减半。旧黑底 joint 可用 `--theme dark`。

右上方独立目标卡片带取代左栏底部文字状态行：A/Novel、B/Novel、C/Revisit。
目标尚未发出时只显示占位；当前目标金色，双臂均到达后绿框。GEM/Base 各自
状态条独立变绿，Baseline 未到达不会被 GEM 成功误染绿。左栏保留 FPV、方法
标签与简短状态角标。地图空白依据深度缓冲无几何掩码设为白色，不把真实黑色
物体染白。floor-fixed 点云、NavDP 局部轨迹与贴地遮挡逻辑保留。


## 12. 2026-09-21：精简版式、取消到达停顿

新版输出 `gem_demo/outputs/sim_visual_arrival_nnr_refined_2x.mp4`：
`--theme refined --steps-per-second 20 --arrival-hold 0 --end-hold 1
--baseline-tail-seconds 3 --gem-track-width .20 --baseline-track-width .27`。
白底与 floor-fixed 原始点云继续保留。Lato 字体、紧凑对齐的 FPV 面板、画面外
的方法名/状态、三张目标卡片的分臂状态图标替代较碎的文字与粗边框。
轨迹中心线 8.5 cm，NavDP 候选/选中轨迹的来源、坐标和贴地逻辑不改。

按用户最新要求，到达不再额外暂停；成功状态持续保留在目标卡片上，结尾只
停留 1 秒。30 fps 正常采样产生的相邻重复源帧不等同于插入到达停顿。
之前 white/dark 版式及视频均保留。主体 UI 在 `refined_sim_style.py`。


## 13. 2026-09-21：进一步减法，minimal 版式

用户觉得 refined 仍复杂，当前选用 `--theme minimal`，输出
`gem_demo/outputs/sim_visual_arrival_nnr_minimal_2x.mp4`。删除标题、副标题、图例、
计时卡片、目标卡容器、重复状态行、地图标签底框/引线和候选轨迹扇形。
保留两路 FPV、三张 Novel/Revisit 目标图、floor-fixed 点云及真实选中 local
trajectory。到达改为小单环。目标绿边跟随 GEM；Baseline 是否到达只由自身
FPV 边框/Arrived/Stopped 表示，不能把目标绿边解释为双方成功。

轨迹宽度 `.18/.24 m`，中心 `.085 m`，只隐藏候选线，不改选中规划几何。
`--steps-per-second 20 --arrival-hold 0 --end-hold 1 --baseline-tail-seconds 3`。
保持白底、连续播放、增量可见性与地面遮挡。旧视频保留。


## 14. 2026-09-21：保留简洁布局，恢复候选线与分臂到达框

最新输出 `gem_demo/outputs/sim_visual_arrival_nnr_minimal_arrival_2x.mp4`。
`minimal` 布局恢复真实 NavDP 候选扇形；若需隐藏，显式加
`--hide-local-candidates`。目标图独立显示 GEM 外层蓝框、Baseline 内层珊瑚框，
颜色与轨迹一致。两臂均到达显示双细框，C 只有 GEM 到达则只有蓝框。
终止不等于到达，Baseline stuck 不触发珊瑚框。替代前版 GEM-only 绿框语义。

已对实际绘制像素检查 A/B 双框、C 仅蓝框；预览
`gem_demo/outputs/goal_arrival_border_preview.jpg`。2×、到达不停顿、结尾 1 秒、
Baseline 尾段 3 秒等设置不变，旧视频保留。


## 15. 2026-09-21：真机地板稀疏不完全等同于仿真裁剪问题

最终真机同视角、291 个观测抽样：地面下限 -0.08 → -0.30 m，覆盖像素
189,001 → 209,139（+10.7%），到 -0.60 m 无新增可见覆盖。固定 -0.30 m，
置信度由保留 top35% 放宽至 top60%，保持平滑过滤，得到 248,552（相对当前
+31.5%）。取消平滑或置信度单项，分别得到 279,175 / 292,656；全部质量过滤
取消为 416,854，但可见噪点/不稳定表面增多。以上都是抽样屏幕覆盖，不是精度。

结论：有少量相同的地面裁剪损失，但质量过滤也显著影响真机缺口，不能照搬
仿真的解释。最终视频未覆盖修改。证据：`gem_demo/outputs/real_floor_audit/`；
复现 `audit_real_floor.py`。后续应验证地面局部过滤与多帧一致性，而非全局放开。


## 16. 2026-09-21：真机地面补点的保守实现

`gem_demo/real_floor_cloud.py` 保留原严格过滤点和原相机取景，仅对高度
[-0.30,+0.20] m 附近补充候选点：置信度分位阈值 40，保留原 3.5% 局部深度
平滑条件；要求两个同一条运行的过去观测（0.18–1.6 秒，相机平移至少 3 cm）
重投影深度误差不超过 max(5 cm, 1% 距离)。不修改预测点位置，不压平地板。
这里是高度带筛选，不是语义地面分割；多帧一致也不保证绝对几何正确。

完整 1,741 个观测，615,547 个额外候选中保留 114,200 个，最终地图占用像素
280,114 → 292,290（+4.35%）。改善有限，大片空白和既有重影仍存在。
与第 15 节抽样统计口径不同。对比和报告在 `gem_demo/outputs/real_floor_audit/`。
Baseline 按播放时间正序验证，不按反向推理文件顺序取支持；原模型推理时序限制不变。
`render_real_final.py` 默认 `--floor-cloud supported`，`--floor-cloud original`
可恢复原显示。设计、轨迹、arrival latch、2× 及灰屏语义不变。


## 17. 2026-09-21：gem_outdoor / p035 户外统一 final

户外原素材对应 p035，原始帧、NavDP、arrival 和遥测已保存于
`gem_demo/outputs/outdoor_inputs`；GEM arrival_latched，Baseline 未到达。
双第一人称、白底、同款字号及目标到达框、贴地候选轨迹；失败后灰屏，2×、
到达不加停顿、结尾 1 秒。输出 `gem_demo/outputs/final/outdoor.mp4`，2153 帧，71.767 秒。

实际调用官方 demo.py + FlashInfer，3714 张连续 RGB，auto interval12，max4096。
比较两种联合顺序后，选 GEM 倒放 → Baseline 顺放，产物
`outputs/outdoor_joint_reverse`。两路尺度估计从初版相差约52%降至约5%，
GEM 里程计拟合 RMSE 0.678→0.288m；Baseline 0.279→0.366m，略变差。
地面参考面的相机轨迹厚度 p95 0.180→0.076m。里程计不是几何真值。

接缝重投影中位数在 PnP 内点上为5.79px，初版为2.08px；选择依据是全程
尺度/形状，不宣称所有指标都更好。两次释放视角有差异，未强行对齐或拉伸点云。
播放按原时间增量显露，模型推理顺序本身不是在线双流对比。
地面采用原质量过滤 + [-0.30,+1.10]m floor-fixed 裁剪，不做 TSDF/虚构补面。
细节、限制、复现与诊断见 `gem_demo/OUTDOOR_VIDEO_PROGRESS.md`。
