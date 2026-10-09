# EDR 物性导入与固化（最容易翻车的环节）

> EDR 的物性（组分+热力学方法+物性曲线）是通过 BEX/COMThermo **独立于输入标量**导入的。这是 EDR 自动化最薄弱、最易翻车的环节——E-6101 事故的根因就在这。

## 1. 物性在 EDR 里的三种存在形态

| 形态 | 标识 | 物性数据位置 | 稳定性 |
|---|---|---|---|
| **BEX 动态链接** | `AspenPropertySelection=1` + `BEXFilename=*.BEX` | Temp 目录 .BEX 文件 | ❌ 跨机/跨会话必断 |
| **固化数据** | `AspenPropertySelection=0` | XML 内 Comp* / Liquid* / Vapor* 数组 | ✅ 自包含，可跨机 |
| **EDR 自带数据库** | `DBToBeUsedCS/HS` 指向内置 DB | EDR 数据库 | ✅ 但对混合极性体系精度不足 |

## 2. 判断一个 .EDR 的物性是否可用（离线三查）

用 `edr_xml.py` 检查：
1. `AspenPropertySelection` 是否为 0（0=固化，1=链接）；
2. `BEXFilename` 指向的 .BEX 是否真实存在（`os.path.exists`）；
3. 物性数组（`LiquidDensity`、`LiquidViscosity`、`CompMolecularWeight`、`NameOfComponents` 等）行数是否 > 0。

**三条任一不满足 = 物性不可用 = Run 必报 1250**（E-6101 三查全不过）。

## 3. 物性导入的两条路径

### 3.0 首选：Aspen HeatX TASCPLUS-RIG（2026-09-30 实测全自动打通 ✅）
**这是物性导入的正统路径，纯 COM 全自动可跑通**，脚本 `scripts/edr_tascplus_design.py`。

Aspen HeatX 块设 `CALC-METHOD=TASCPLUS-RIG` + `HETRAN-PARAM INPUT-FILE=*.EDR`，运行 Aspen
时引擎自动：算冷热流股物性 → 写进 .EDR 固化数组（`DBToBeUsed=4`）→ EDR 做 Design。
物性由 Aspen 自洽算出，多组分/相变也不缺流股参数。详见
com-api-and-troubleshooting.md §6.6。

### 3.1 链接法（Aspen Plus → EDR，推荐，物性最准）
1. Aspen Plus 里建好 HeatX 块（或用现有换热器模型），物性方法设为目标（如 ELECNRTL）。
2. 从 HeatX 块导出 EDR 输入（Aspen Plus GUI 的 EDR 集成，或 COM 的 SimInterface）。
3. EDR COM：`BJACApp.ImportPFS(parameters)`（V15 已注册 `SimInterface.APlus2Tasc`，**具体参数签名待实测**）。
4. 导入后立即 Run + 校验收敛。

> **2026-09-30 实测更新**：方法签名已定位——app 层是 `ImportPSF(psfMode:int)`，主控层是 `ImportPFS(parameters对象)`；绑定上下文用 `SetAspenAppContext(objAspenApp, fNameAspenApp, vaporizerType='')`。但**纯 COM 无 GUI 下 `ImportPSF(2)` 报 GetPSF 桥缺口**（详见 com-api-and-troubleshooting.md §1.1b/§6.6）。链接法在 GUI 下可靠，纯 COM 自动化需走 TASCPLUS-RIG（§3.0）或固化法。

### 3.2 固化法（把物性曲线写进 XML，可跨机交付）
1. 用 Aspen Plus 算出冷/热侧的物性曲线（密度/粘度/比热/导热/汽化焓/表面张力 vs 温度压力，覆盖操作区间）。
2. 写回 EDR XML 对应数组：
   - `NameOfComponents` / `AspenDBComposition`：组分清单
   - `LiquidDensity` / `LiquidViscosity` / `LiquidSpecificHeat` / `LiquidThermalConductivity` / `LiquidSurfaceTension`：液相物性
   - `Vapor*` 同族：气相物性
   - `CompMolecularWeight` / `CompCriticalTemperature` 等：组分常数
3. 设 `AspenPropertySelection=0`，`PropMethodCSSTR/HSSTR` 设为对应方法名。
4. FileOpen 复检数组非空 → Run 校验收敛。
5. **固化法的坑**：EDR 物性数组列数与曲线点数有固定格式（NumPtsOnCrvHS 等），需对照官方含物性数据的示例（如 TS-Thermosiphon-Vertical_BEM.EDR 若带数据）逐列对齐。

## 4. 物性方法一致性（铁律）

| Aspen Plus | EDR PropMethodSTR | 备注 |
|---|---|---|
| ELECNRTL | ELECNRTL | 电解质（酯化/吸收/含醋酸水） |
| PENG-ROB | PENG-ROB | 烃类/非极性 |
| NRTL | NRTL | 极性非电解质 |
| STEAM-TA | STEAM-TA | 游离水 |

**E-6101 教训**：原 EDR 冷侧写 PENG-ROB，但 Aspen Plus 底座是 ELECNRTL（酯化电解质）→ 方法不一致，重建必须统一为 ELECNRTL。

## 5. 运行失败 1250 的排查顺序

1. 先三查物性（§2）——**90% 的 1250 是物性缺失**（BEX 断链）。
2. 查物性方法是否设了（`PropMethodCSSTR/HSSTR` 非空）。
3. 查几何是否完整（管数/管长/壳径/折流板）。
4. 查工艺输入是否物理自洽（进出口温压、相态、蒸发率）。
5. 查许可（LSHOST）——许可问题常报不同错误码。

## 6. 交付前检查清单（避免把坏文件交给用户）

- [ ] 物性三查通过（固化或链接有效）
- [ ] Run rc==0 且 ErrorDescription=='Normal operation'
- [ ] 结果合理（U 值、Q、压降在经验区间，见 industry-standards-and-rules.md §3）
- [ ] 保存为自包含文件（若链接法，说明需同机同 Aspen Plus 环境）
