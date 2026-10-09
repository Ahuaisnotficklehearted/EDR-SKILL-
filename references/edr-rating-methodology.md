# EDR 评级交付方法论（三权威 + 状态机 + 8 步工作流 + 验收门 + 停止/迁移规则）

> 本文档是 EDR-skill 的**工程治理层**，完整定义"如何判断一台换热器到底有没有做真实 EDR、如何逐级验收、何时停止"。这是从成熟化工设计工作库的方法论中**重建**而来，作为本 skill 的自包含规范。

---

## 1. 三个权威分离（核心治理原则）

做一台换热器，始终分清三个权威，各管各的，不越界：

| 权威 | 决定什么 | 来源 |
|---|---|---|
| **工艺权威 Process** | 冷热侧组成、流量、进出口温压、相态、热负荷、蒸发/冷凝率、压降约束 | 认可的 Aspen 案例 / 设计院条件表 |
| **EDR 权威 EDR** | 几何尺寸、面积、U、压降、流速/RhoV2、振动、物性范围 | 同设备 .EDR 真实运行结果 |
| **交付权威 Delivery** | Required Input 完整、零警告零错误、工艺目标不被动改 | 精确复开复算的最终文件 |

**铁律**：
- 不能用一次干净的 Aspen 运行掩盖 EDR 的工程失败；
- 不能用一份干净的 EDR 报告绕过 Aspen 交付门；
- 手算面积只作初筛，最终面积/压降/振动必须 EDR。

---

## 2. HeatX 分类状态机（判断"到底做没做真实 EDR"）

| 状态 | 含义 |
|---|---|
| `unverified` | 证据不足，无法确定 EDR 状态（缺项≠失败，未知门≠已失败） |
| `shortcut` | 仅流程级 shortcut 计算 |
| `detailed_non_edr` | Detailed 计算但**没走 EDR** |
| `edr_file_unaccepted` | .EDR 存在但消息/结果门失败 |
| `edr_unbound` | .EDR 通过但 Aspen 绑定丢失 |
| `edr_bound_diagnostic` | EDR 执行+绑定有证据，但工程/工艺/交付门失败 |
| `edr_accepted_for_simulation` | EDR + 精确 Aspen 交付门全过 |
| `vendor_mechanical_open` | 热力评级通过，但 SW6/厂家机械工作仍开放 |

**反例识别**（这些都不是 EDR 完成证据）：
- `CALC-METHOD=DETAILED` 不是 EDR；
- `Run2=0` 不是 EDR 完成；
- 干净 `.his` 不是 EDR 身份证据；
- 有 .EDR 文件名不等于有有效结果；
- `NextIncomplete=('', 0)` 不是 EDR 身份证据；
- 未执行的检查不能标为 `edr_unbound` 或失败。

---

## 3. 晋升阶梯（Promotion Ladder，不能跳级）

1. **文件存在**：仅文件名，不声称已算。
2. **EDR 计算通过**：同设备文件 + 消息/结果有效。
3. **Aspen 绑定通过**：EDR 复开存活 + 输出填充。
4. **Aspen 交付通过**：精确复制文件过 Required Input + 零警告 + 工艺门。
5. **工程设计通过**：面积/压降/振动/物性范围/材料闭合。
6. **机械/厂家通过**：SW6/图纸/制造/性能保证。

> **模型可能过第 4 级但面积余量/材料在第 5 级仍开放——不能塌缩这些级别。**

---

## 4. 8 步工作流（完整交付 SOP）

### 4.1 冻结覆盖范围
- 单设备任务 = 命名换热器；全流程 EDR = 每台合格换热器。
- 双流股 `HeatX` 块 → 进 EDR 覆盖台账；单流股 `Heater` 块除非授权加第二侧，否则不进 EDR。
- 记录：位号、块类型、冷热流股、工艺目标、当前方法、EDR 文件、证据、状态、下一步。
- 授权范围内任何合格 HeatX 缺失 → 停止声称"覆盖完成"。

### 4.2 分类起始状态
用当前同设备证据分类（见 §2），未知字段与已知事实**分开列出**，未知门 ≠ 已失败。

### 4.3 建/修同设备 EDR
- 只用当前项目的流股/物性/工艺证据。
- 用已安装 Aspen 示例探测本地版本枚举与文件角色。
- 有 `BJACWIN.BJACApp` 就用它做无 GUI open/run/save。
- 解析 `.EDR` XML 的 `TascMsg`，**不要只依赖 COM 返回值或不完整的标量读取**。
- 绑定前解决：输入错误、操作失败、物性曲线范围、非物理出口状态、压力一致性、几何、振动。
- 材料保持同设备且温度/腐蚀相关；改合金不扩展 Aspen 物性曲线。

### 4.4 用正确文件角色绑定
壳管式评级/校核文件，导出卡片应为本地等效的：
```
CALC-TYPE=RATING
CALC-METHOD=TASCPLUS-RIG
HETRAN-PARAM INPUT-FILE=<同设备 .EDR>
BJAC-INPUTS METHOD=<EDR-DEFAULT 或经论证的方法>
```
- Rating 文件就用 `RATING`，不要因任务要求"设计"就硬塞进 `DESIGN`；真正需要 Design 时重新生成设计模板。

### 4.5 复开后证明"真 EDR"
复开受保护候选文件（不做编辑），要求：
- 严格 EDR 模式与程序模式存活；
- 输入路径指向同设备 .EDR；
- `EDRBLK=1`、`EDR_PGM=TASCPLUS`；
- 报告出现 `THIS BLOCK RUNS WITH ASPEN EDR`；
- 程序模式 `RATING`（或授权替代）；
- EDR 的 duty/面积/U/压降/流速 RhoV2/振动结果已填充。

复开若返回 `SHORTCUT`、`EDRBLK=0`、缺 EDR 结果、或 Required Input 不完整 → **隔离该分支**。

### 4.6 应用工程验收门（见 §5）

### 4.7 应用 Aspen 交付门（见 §6）

### 4.8 打包外部 EDR 文件（可移植）
- 严格 HeatX 依赖相对 .EDR 时，优先用 Aspen 复合 `.apwz` 单文件传输，或完全解压的文件夹/flat ZIP。
- 通过 Aspen COM `SaveAs(...apwz, True)` 构建 APWZ，同设备 EDR 文件以相对名一起打包。
- **绝不手改 APWZ 内部**；只读枚举成员 + 哈希作打包证据。
- 证明每个预期 EDR 成员都已嵌入且与认可的 sidecar 字节一致后再运行。
- Aspen Plus V14 标准自动化初始化可能无法直接打开 APWZ 包装；无 GUI QA 时先哈希 APWZ，安全解压到隔离目录（保留路径），打开内嵌 BKP/APW 不编辑。
- 运行 APWZ 审计时，包外不要放同名 EDR 文件（否则缺失的嵌入成员会被文件系统掩盖）。

---

## 5. 工程验收门（Engineering Acceptance Gates）

| 检查项 | 通过证据 | 常见失败 |
| --- | --- | --- |
| 热负荷 | EDR duty 匹配冻结工艺目标/容差 | EDR 静默改了工艺 duty |
| 面积 | 需要/实际面积都报告，余量可接受 | 负面积余量 |
| U/热阻 | 值填充且物理合理 | shortcut/默认 U 冒充 EDR |
| 压降 | 壳/管压降在允许内 | 真空侧/循环扰动 |
| 流速/RhoV2 | 无高 RhoV2 指示 | 进口/横流负荷过大 |
| 振动 | 无未解决振动警告 | 无支撑管/不良壳排列 |
| 物性范围 | 曲线覆盖全 T/P 包络 | APPDF 温度/压力越限 |
| 材料 | 温度/腐蚀/制造依据记录 | 从别的换热器照抄合金 |
| 工艺整合 | 相态/循环/产品/能力保持 | 干净 EDR 破坏下游 Aspen |

> **负面积余量 = 开放的工程动作，即使 Aspen 无警告。** 面积余量闭合或被项目权威明确接受前，该换热器标"EDR 已评级但不适合发厂家"。

---

## 6. Aspen 交付门（Aspen Delivery Gates）

对精确候选文件，再对精确复制的用户交付文件，逐条：

1. 无编辑复开。
2. 打开/ProcessInput/运行后检查 `Data.NextIncomplete()==('', 0)`。
3. 运行并抓真实 `.his`、`.sum`、`.rep` 证据。
4. 要求所有命名行与列按源验证版本/格式 schema 存在且全零；未知/不完整 schema 失败；绝不拆折行头或补零。
5. 扫原始历史里实际的 warning/error/severe 行。
6. 确认每台合格 HeatX 仍报 EDR。
7. 校验工艺 duty、相态、循环收敛、能力、产品门。
8. 哈希精确交付文件，被取代的分支保留为隔离（quarantine）。

---

## 7. 失败特征与决策（Failure Signatures）

| 特征 | 决策 |
| --- | --- |
| `DETAILED` 但无 EDR 输出 | 非 EDR |
| `Run2=0` + `IsComplete=false` | 失败/不完整 EDR |
| `TascMsg` 含 `Operation Failure` | 隔离 |
| 物性曲线低于操作温度 | 重新生成/扩展物性 |
| EDR 路径丢失或复开后模式重置 | 绑定失败 |
| `EDRBLK=0` | EDR 未执行 |
| 干净 Control Panel 但缺 EDR 结果 | Aspen 干净，EDR 缺席 |
| 负面积余量 | EDR 存在，工程动作开放 |
| 振动靠并联解决 | 重评级 + 重跑全部 Aspen 门 |
| EDR 改受保护 duty/循环/产品 | 拒绝或取得授权 |

---

## 8. 停止规则（Stop Rules，宁可隔离不可硬做）

出现以下任一，**停止并隔离**，不 improvise：
- 无同设备物性/热曲线依据；
- `TascMsg` 含未解决的输入错误或操作失败；
- 物性曲线不覆盖操作包络；
- 出口温度/相态/duty/压力非物理；
- EDR 绑定未经授权改了受保护工艺目标；
- Aspen 复开后 EDR 模式/文件角色被重置；
- Required Input 或最终 Run Status 警告/错误非零；
- 合格的 HeatX 未被覆盖。

---

## 9. 迁移规则（Transfer Rule，防数值污染）

**可迁移**：工作流、字段含义、失败特征、证据顺序、晋升门。

**禁止迁移**（除非有同设备证据）：另一台换热器的流股、duty、面积、几何、材料、污垢、压降、方法选择、串并联安排。

---

## 10. 返回契约（Return Contract，每次交付的固定输出格式）

```
Coverage: <已覆盖合格 HeatX>/<总合格 HeatX>
True EDR identity: <逐位号的 mode/file/readback>
Engineering gates: <面积/压降/RhoV2/振动/物性/材料状态>
Pressure-drop basis: <热侧 实际/允许; 冷侧 实际/允许; 来源或缺口>
Aspen delivery gate: <Required Input 与 Run Status/history>
Exact delivery file and SHA256:
Quarantined branches:
Open SW6/vendor actions:
```

> 冷/热侧压降必须分别与其允许压降限（同设备、同操作基准）对照；缺限值要列为"缺输入 + 来源待取"，**仅有一个实际 DP 值不能证明可接受**。
