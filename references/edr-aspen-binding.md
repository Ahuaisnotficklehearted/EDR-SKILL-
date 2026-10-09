# EDR 与 Aspen Plus 的绑定（COM 卡片模式 + HeatX 评级卡 + 读回证明）

> 本文档定义"如何在 Aspen Plus 的 HeatX 块里真正绑定并证明 EDR 评级"，以及 COM 非 GUI 操作的证据要求。是"真 EDR"与"假 EDR"的判据来源。

---

## 1. 非 GUI EDR 证据

本地 Aspen EDR 自动化服务器可暴露的操作（依版本而异）：

```
BJACWIN.BJACApp
FileOpen / FileSaveAs
Run / Run2
CheckData / RefreshData
ImportPSF / TransferData / TransferResults
Scalars / Arrays
ResultScalars / ResultArrays
```

**方法可用 ≠ 验收证据**。必须捕获：
- COM 启动/服务器身份；
- 输入/输出文件路径；
- 运行返回值；
- 完整性状态（`IsComplete`）；
- XML `TascMsg` 的类别与文本；
- 物理结果字段；
- 输出文件哈希。

> **优先解析 XML `TascMsg`**，尤其当 COM 标量访问不完整时。对未解决的输入错误、操作失败、使结果失效的物性/工艺警告，一律判失败。

---

## 2. Aspen 壳管式评级卡片（HeatX 绑定模式）

用导出卡片 + 已安装示例证据确定当前 Aspen 版本的精确写法。一个已验证的项目评级卡结构上等价于：

```
BLOCK <位号> HEATX
    PARAM T-COLD=<目标> CALC-TYPE=RATING  &
        CALC-METHOD=TASCPLUS-RIG
    HETRAN-PARAM INPUT-FILE='<同设备>.EDR'
    BJAC-INPUTS FOUL-OPTION=PROGRAM METHOD=EDR-DEFAULT
    FEEDS HOT=<热侧入口> COLD=<冷侧入口>
    OUTLETS-HOT <热侧出口>
    OUTLETS-COLD <冷侧出口>
```

**工艺目标**可以是 duty、热侧温度、或气相分数，取决于被认可流程的需求。**保留来源目标，不要从示例里挑一个。**

---

## 3. 读回证明（Readback Proof）

SaveAs/复开/运行/导出之后，要求所有适用证据：

```
CALC-METHOD=TASCPLUS-RIG
CALC-TYPE 或 PROGRAM_MODE 匹配文件角色
INPUT_FILE 指向预期的同设备 .EDR
EDRBLK=1
EDR_PGM=TASCPLUS
report: THIS BLOCK RUNS WITH ASPEN EDR
report: SHELL&TUBE PROGRAM MODE RATING/DESIGN（按授权）
report: duty、required area、actual area、margin、U、pressure drops、vibration
```

---

## 4. 假阳性识别（False Positives）

以下**都不是** EDR 证据：
- `CALC-METHOD=DETAILED` 不是 EDR；
- `MODE=RIGOROUS` 导出前写了、复开后重置 → 不是证据；
- `NextIncomplete=('', 0)` 不是 EDR 身份证据；
- 干净的 `.his` 不是 EDR 身份证据；
- 保存了 .EDR 但没有有效结果 → 不是 EDR 验收；
- 评级文件放在模板/设计字段 → 不是有效 Design 案例。

---

## 5. 精确文件交付序列（Exact-File Delivery）

```
受保护候选文件
→ 无变异复开/运行/导出
→ EDR 读回 + 报告审计
→ Required Input + 全零历史
→ 工艺/产品/循环门
→ 复制到交付路径并哈希
→ 对复制文件再无变异复开/运行/导出
→ 重复每道门
```
