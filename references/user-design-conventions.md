# 用户设计约定（E-6102 项目确认，2026-09-30）

> 以下 8 条由用户提出，经实测/规范审核后收录。标注 ✅ 为「采纳（符合规范或实测可行）」，
> ⚠️ 为「有条件采纳（需说明限制或补充意见）」。

## 1. 换热管长度优先 3 m 或 6 m — ✅ 采纳（补充选取意见）

TEMA 标准管长含 1.5/2/3/4.5/6/9/12 m，但**工程最常用 3 m 与 6 m**（备料、制造、运输最经济）。
若工况需要 4.5 m 等其他长度，属"特殊长度"，**必须与用户确认**。

同时给出选取意见，方便用户选型：

| 管长 | 特点 | 适用 |
|---|---|---|
| **3 m** | 壳径较大、压降低、占地短、厂房适应性好的"粗短型" | 场地受限、允许压降小、需大壳径多布管 |
| **6 m** | 壳径小、单台面积大、管数少的"细长型" | 场地充裕、允许压降较大、追求单台大换热面积 |

> E-6102 实测：EDR Design 自动选 3 m（壳 307 mm）；改 6 m 则面积翻倍、余量升至 ~40%（超标）。
> 建议：**优先 3 m**；若余量不足再评估 6 m 或双壳程。

## 2. 单位统一（全 SI 或全 Metric）— ✅ 采纳

避免混用英制/公制导致量纲错误。EDR 侧对应参数：
- `uomset`：1=英制(US)、2=公制(SI)
- `DesignDimUnits`：1=公制、2=英制

交付前确认两侧（壳侧/管侧）与几何单位一致；Aspen 侧 `IN-UNITS/OUT-UNITS` 同样统一为 SI。

## 3. 输出前消除 errors & warnings — ✅ 采纳（工程基本原则）

输出前必读 `app.GetCalculationMessage(i)` 逐条检查，尽量消除；无法消除的须在说明文档里
**逐条列出并说明原因与影响**。

常见可消除项与其对策：

| 警告 | 含义 | 对策 |
|---|---|---|
| 1063 | 未指定最大允许压降 | 设 `PresDropAlloSS/TS` |
| 1107 / 1291 | 管数与布管不一致 / 目标管数超壳径上限 | **不指定管数**，让 EDR 按壳径布管；或放大壳径 |
| 1132 / 1134 | 壳径/管数与 Tube Layout 不一致 | 改 `TubeLayoutOption` 让 EDR 重布管 |
| 1225 | 折流板区长度与管长不一致 | 调整折流板数/间距，使与管长匹配 |
| 1393 | 壳体壁厚小于 TEMA 最小（常为负值） | 壳径与布管不匹配所致 → 保持壳径与布管一致 |
| 1611 | 流体诱导振动问题 | 增大管数/缩小跨距/加支撑 |
| 1661 | 无支撑直管跨距超 TEMA 上限 1524 mm | 增加折流板数量 |

## 4. fluid name 简短直观 — ✅ 采纳（且可防报错）

`FluidNamCS`（冷侧）/ `FluidNamHS`（热侧）建议按流股信息取简短名，
如 `Methanol`、`Cyclohexane`（实测可用）。**避免过长或带特殊字符**（可能触发解析异常）。
实测：流体名为空（`''`）时虽能计算，但不利于交付可读性 → 必须填写。

## 5. 流股信息从 Aspen Plus 导入 — ✅ 采纳（本项目标准做法）

即 TASCPLUS-RIG 路径（见 com-api §6.6）：Aspen HeatX 设 `CALC-METHOD=TASCPLUS-RIG`
+ `HETRAN-PARAM INPUT-FILE`，运行 Aspen 自动把冷热流股物性推入 EDR。
实测流股无报错，物性自洽（组分 MW、密度、粘度等自动填充，`DBToBeUsed=4`）。

## 6. 不指定换热管数量，让 EDR 生成 — ✅ 采纳（重要）

**实测教训（关键）**：手动指定 `TubeNum` 极易与 EDR 布管冲突——
- 387 mm 壳径实测最大约 113 管；指定 160 管 → Warning 1291/1107（布不下）。
- 且 Aspen 生成的文件**布管（Tube Layout）被锁定**，Rating 模式改壳径后 EDR 不重布管，
  会出现"管数 vs Layout 管数不一致"与"壳体壁厚为负"等连锁警告。

正确做法：**Design 模式让 EDR 自动定壳径+管数+布管**；若需加余量，优先**加长管**
（3 m→6 m）或**放大壳径后让 EDR 重布管**（`TubeLayoutOption`），而非硬写管数。

## 7. Nominal Pipe Size 直接指定，EDR 配套管口尺寸 — ✅ 采纳

管口（Nozzle）只需指定公称直径（NPS），EDR 会自动给出配套的内外径/法兰等，
**不必手工设计管口细节**。相关参数族以 `Noz*` 开头（如 Nozzle 名义尺寸/内径）。

## 8. 输出 TEMA sheet + Setting plan 为 A3 PDF — ⚠️ 有条件采纳（COM 有限制）

用户要求：TEMA sheet 第 1 页、setting plan 第 2 页，A3 出图保存为 PDF。

**实测结论（EDR V15，无 GUI COM）**：
- 绘图 ID 已定位：**Setting plan = 1**（`TeamsDrawingList` 表），
  **TEMA Sheet ≈ 201.14**（`TASCPRINT` 表；另有 2=Material spec、3=Sectional plan、
  4=Bundle layout、5=Tube layout）。
- EDR COM **无 `ExportToPDF`**；仅有 `PrintDrawing(DrawingID, PrinterAssigned)`、
  `DisplayDrawing`、`ExportToDXF`。
- **无 GUI COM 下实测不可靠**：`ExportToDXF` 返回 False（不产出文件）；
  `PrintDrawing` 调用返回 None 但不生成 PDF（打印作业未落地）。
  这与 GetPSF 一致——**EDR 的 GUI 相关功能（绘图/打印/PSF 导入）在无 GUI COM 下均失效**。

**可行做法（推荐）**：
1. **EDR GUI 手动导出**（最可靠）：打开 .EDR → 打开 TEMA Sheet 与 Setting plan 图纸
   → 打印/导出为 PDF → 页面设置 A3 → 按"TEMA sheet 在首页、setting plan 次页"合并。
2. 若坚持自动化：需在有 GUI 的会话中运行，并用 PDF 虚拟打印机
 （本机可用：`Microsoft Print to PDF`、`PDF24`、`导出为WPS PDF`、`SmartPlant PDF Converter 603`），
  但**输出路径由打印机/对话框控制，脚本无法直接指定**。

> 交付时若 COM 不可得，应在说明文档中注明"图纸 PDF 需 GUI 导出"并给出操作步骤。
