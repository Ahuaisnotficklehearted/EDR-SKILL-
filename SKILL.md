---
name: EDR-skill
description: 在 Windows 上通过 COM 接口自动化本地安装的 Aspen Exchanger Design & Rating (EDR)，用于从零设计/校核/交付换热器。覆盖：打开/新建/编辑/运行/另存 .EDR 案例（Shell&Tube/Tasc、AirCooled/Acol、Plate/Aple、PlateFin、CoilWound、FiredHeater/Fire）、设置几何与工艺输入、运行评级(Design/Rating)计算、读取结果（面积/U/热负荷/压降/余量/振动）、从 Aspen Plus 模型交接工艺与物性数据（ImportPFS）、多源输入校核、工程验收门、版本化交付。内置已验证的端到端工作流（输入校核 → Aspen Plus 物性底座 → EDR 选型建模 → 可选 Mechanical → 版本化交付）、行业设计规定（TEMA/GB151/ASME、污垢/压降/流速/余量）、三权威分离与验收门方法论、以及"只操作副本 / 打开即校验 / os._exit 防析构回写"的强制安全规则。含 E-6101 降膜再沸器与 E-6102 环己烷-甲醇冷凝蒸发器两个案例。（Aspen EDR V15 已验证）
---

# EDR-skill — Aspen EDR 换热器自动化技能

> **产品名：EDR-skill v1.0**
> **总纲：安全第一、校核先行、权威分离、物性一致、版本化输出。**
> EDR COM 有"打开即回写文件"的致命行为，任何操作前必须备份并核对；输入材料必须多源交叉校核；三个权威（工艺/EDR/交付）各司其职不越界；EDR 侧物性方法必须与工艺底座一致；每次输出放独立版本文件夹并同步说明文档。

---

## 0. 本 skill 能做什么 / 不能做什么

**能**：
- 用 COM 打开/新建/编辑/运行/另存 .EDR（六类换热器）换热器案例
- 从数据表 PDF / HTRI xls / 图纸 / 文本多源拆分校核输入
- 从 Aspen Plus 模型提取物性底座并保持一致（ImportPFS / 固化数组）
- 热力设计（评级 Rating / 设计 Design），输出带尺寸的换热器
- 读取结果（面积、U、热负荷、压降、余量、振动）并对照验收门
- 版本化交付 + 每次出说明文档（含溯源）

**不能（边界）**：
- 不替代化工专业判断——物性方法、污垢、余量取值仍需工程师确认
- 机械设计（强度/壁厚/法兰）需用户明确要求后才做，且需 TEMA/ASME/GB 规范依据
- 不保证 BEX 跨机链接有效（跨机传 EDR 需固化物性）
- 不提供商业软件本体，不把热工评级当作厂家机械设计批准

---

## 1. 铁律（每条都有事故/实测依据，违反 = 数据损坏）

1. **只操作副本**：`FileOpen` 会回写被打开文件。加载失败时把空壳写回原文件（E-6101-7.EDR 118KB→656B 已发生）。`edr_bridge.py` 已内置自动备份；手工脚本必须 `shutil.copy2` 后打开。
2. **打开即校验**：FileOpen 后立即读 2~3 个已知输入标量与 XML 值比对，读到默认值 = 空壳加载，立即终止。根因：文件带失效 Aspen Plus 物性链接（`AspenPropertySelection=1` + `BEXFilename` 指向不存在的 Temp .BEX）。
3. **运行成功判定**：`rc==0` **且** `ErrorDescription=='Normal operation'`（带句号，比较 rstrip('.')）。rc=1250 失败；失败时 FileSaveAs 仍会保存，禁止以保存成功判定运行成功。
4. **防析构回写**：退出统一 `os._exit()` 绕过析构（edr_bridge.py 已实现）；备份本身要校验（XML scalar 数）。
5. **FileSaveAs 可能间歇阻塞**：放最后一步 + 整体超时 + 以"目标文件生成且大小合理"判成功。
6. **版本化输出**：每次产出放独立文件夹（`<项目>_v<N>/`），改动复制旧版到 `_v<N+1>`，永不改旧版；文件夹名只用字母数字下划线连字符（无空格、无中文、无特殊字符）。
6b. **输出成品统一放 `输出成品/` 文件夹**（2026-09-30 新增规则）：所有交付成品（Aspen Plus 模型 apwz/bkp、EDR 文件、报告 rep、说明文档等）**一律放入项目根的 `输出成品/` 文件夹**，其中每次交付建一个带版本号的小文件夹（如 `输出成品/E6102_环己烷甲醇换热器_v5/`），内放该版全部成品。这样方便直接查看结果与版本演进，源文件/过程文件不混入。
7. **物性方法一致 + 物性可用三查**：EDR 侧 PropMethod 必须与 Aspen Plus 底座一致；打开后三查物性（`AspenPropertySelection==0` 或 BEX 存在 + 物性数组非空），任一不过 = Run 必报 1250（详见 references/property-import-and-freezing.md）。
8. **纯组分走内置库，勿用 BEX**：纯组分（环己烷/甲醇/水/蒸汽）用 EDR 内置 B-Jac 库（`DBToBeUsed=1`）+ 组分符号 + 物性方法，让 EDR 自生物性，规避 BEX 断链风险；只有自定义混合物/电解质才需 Aspen Plus 链接。`DBToBeUsed` 精确枚举（SQLite main_2014.db 实测）：1=B-JAC、2=Aspen Properties、3=COMThermo、4=User specified properties、5=User spec + heat loads（从 Aspen 导入物性落地后常为 4）。
9. **物性导入首选 TASCPLUS-RIG**：Aspen HeatX 块设 `CALC-METHOD=TASCPLUS-RIG` + `HETRAN-PARAM INPUT-FILE=*.EDR`，运行 Aspen 即自动算物性推给 EDR（`DBToBeUsed=4`），多组分/相变也不缺流股参数——这是"先跑 Aspen 再导入 EDR"的正统做法，纯 COM 全自动可跑通（`edr_tascplus_design.py`）。物性曲线是 EDR 最薄弱环节，清空后 EDR **不会**自动从 B-Jac 库重新生成，必须显式提供（Aspen 推或固化）。
10. **读 Aspen 生成的 EDR 用 XML 解析，绝不用 FileOpen**：Aspen TASCPLUS-RIG 生成的完整 .EDR 若用 COM FileOpen 读，会被回写成 529 字节空壳（Aspen 写的格式 EDR 引擎不完全认）。读结果用正则/XML 解析。
11. **交付前必须通过规范符合性校核**（详见 references/edr-design-spec-compliance.md）：污垢热阻 >0（有机介质 0.0001~0.0002 m²·K/W）、面积余量 30~50%、管侧气速 ≤30 m/s、压降 ≤允许值、长径比 3~15、壳径/管长/管径取 TEMA 标准规格。**Design 模式余量恒≈0，必须转 Rating 加余量后才可交付**。
12. **污垢参数是 CS/HS 不是 SS/TS**：EDR 污垢热阻用 `FoulResCS`（冷侧）/`FoulResHS`（热侧）；`FoulResSS`/`FoulResTS`（壳侧/管侧）在 COM 中不可访问。判定生效：`U_dirty < U_clean`（相等=污垢为 0）。
13. **用户设计约定（8 条，详见 references/user-design-conventions.md）**：① 管长优先 **3 m/6 m**（特殊长度须确认并给选型意见）；② 单位统一（全 SI 或全 Metric）；③ **输出前消除 errors & warnings**（用 `GetCalculationMessage`）；④ `FluidNamCS/HS` 取简短直观名；⑤ 流股信息从 Aspen 导入（TASCPLUS-RIG）；⑥ **不指定管数让 EDR 生成**（硬写管数会与布管冲突）；⑦ NPS 直接指定、EDR 配套管口尺寸；⑧ 图纸 PDF（TEMA sheet+setting plan，A3）——**无 GUI COM 下不可靠，需 GUI 导出**。

> 完整事故记录与根因见 `references/com-api-and-troubleshooting.md` §3，`examples/E6101_v1/04_过程记录/事故报告_EDR原文件损坏.md`。

---

## 2. 环境与前置

- Aspen EDR V15（`<盘>:\...\Aspen Exchanger Design and Rating V15.0\`，本机 `D:\software\anzhuang\`），核心 DLL `XEQ\BJACCOM2.dll`。
- 许可与 Aspen Plus 同源（Sentinel RMS）：设 `LSHOST=主机名`、`LSFORCEHOST=主机名`。
- Python 用 **pywin32（win32com）**。comtypes 对此 COM 带参属性有坑（NamedProperty 取不到值）。

---

## 3. COM 接口速查（详见 references/com-api-and-troubleshooting.md）

```python
import win32com.client
bjac = win32com.client.Dispatch("BJACCOM2.BJACApp")
bjac.FileOpen(path)                                  # 加载（会回写！先备份）
app  = bjac.GetAppObject(path, "Tasc")               # 程序对象
doc  = bjac.GetDocument(path, False)                 # 文档对象
sc   = app.Scalars; sc("ShlID").Value                # 输入标量
sc("TubeLng").Value = 6000                           # 写输入
rs   = app.ResultScalars; rs("Area").Value; rs("Area").Uom
rc = bjac.Run("Tasc")                                # rc==0 且 err=='Normal operation' 才成功
doc.FileSaveAs(newpath); doc.FileClose()
```

**程序名映射**：Shell&Tube=**Tasc**、AirCooled=**Acol**、Plate=**Aple**、PlateFin=**PlateFin**、CoilWound=**CoilWound**、FiredHeater=**Fire**、Ensea=**Ensea**。

**两个 ProgID 均可**：`BJACCOM2.BJACApp`（COM 包装）、`BJACWIN.BJACApp`（官方 .NET ShellApp `AspenTech.EDR.ShellApp.BJACApp`）。

**.EDR = XML**：可用 `scripts/edr_xml.py` 离线只读解析（`dump/scalars/results/arrays/find`），不依赖 COM、绝不写文件——是"打开即校验"的文件侧实现。

---

## 4. 快速开始

```powershell
# ① 离线只读解析（安全，先了解文件里有什么）
python scripts/edr_xml.py scalars "case.EDR"
python scripts/edr_xml.py find "case.EDR" ShlID

# ② COM 全流程（自动：备份→打开→校验→写→运行→读→另存）
python scripts/edr_bridge.py --open "case.EDR" --app Tasc `
  --verify ShlID=1900 TubeOD=32 `
  --set TubeLng=6000 --run `
  --results Area,AreaReqClean,AreaRatioDirty `
  --save case_run1.EDR

# ③ 运行前自检（物性三查 + 几何/工艺完整性）
python scripts/edr_diag.py "case.EDR"
```

---

## 5. 标准工作流（详见 references/standard-workflow.md）

0. **输入拆解归档** → `01_校核后的输入材料/`（PDF/图片/xls/EDR 拆分 + 多源交叉校核表）
1. **Aspen Plus 物性底座** → `02_AspenPlus物性/`（0 error/warning 模型，提取组成/方法/曲线）
2. **EDR 建模与热力设计** → `03_EDR模型/`（选型→模板/链接→输入→运行→校验→出尺寸）
3. **Mechanical**（询问用户后）→ 强度/壁厚/法兰/管板
4. **输出** → 版本文件夹 + `说明文档.md`（工艺说明置顶→基础信息→过程记录→溯源）

**每阶段主动保存**（FileSaveAs + 更新说明文档），不等到全流程结束才存。

---

## 6. 行业规定速查（详见 references/industry-standards-and-rules.md）

- **冷/热侧**：CS=冷侧（再沸器=管侧蒸发物料）、HS=热侧（壳侧蒸汽）。
- **再沸器硬指标**：冷侧蒸发率、进出口温度、管侧压降（≤10 kPa）先锁定。
- **污垢热阻**：冷却水 0.00018~0.00035、含醋酸 0.0003~0.0005、蒸汽 0.00009~0.00017 m²·K/W。
- **设计余量**：常规 30~50%，再沸器/冷凝器 30~50%（93% 属异常偏高，勿照抄）。
- **流速**：液体 0.5~3、气体 10~30 m/s。
- **规范**：TEMA（BEM/BEU 分类、膨胀节）、GB/T 151、ASME Ⅷ。

---

## 7. 案例库（详见 references/case-*.md）

- **E-6101 丙酯酯化再沸器**（立式降膜，BEM，Zr-3）：冷侧 990000 kg/h、150→155℃、蒸发率 12%，热侧蒸汽 250→150℃冷凝，Q=14.394 MW，面积 ~1046 m²。本 skill 首个完整实战 + 全部安全规则来源。
- **E-6102 环己烷-甲醇冷凝蒸发器**（从零设计）：热侧环己烷 5.4 kg/s 饱和蒸汽 172℃冷凝，冷侧甲醇 2.0 kg/s 过冷液 80℃→109.5℃ 蒸发 70%，Q=1.53 MW，面积量级 25~67 m²。纯组分体系，验证"EDR 内置库直建、无 BEX 依赖"路径。

---

## 8. 工程方法论（详见 references/engineering-authority-and-gates.md）

- **三权威分离**：工艺权威（组成/温压/负荷/相态）、EDR 权威（面积/U/压降/振动/物性范围）、交付权威（Required Input + 零警告 + 工艺目标不动），各司其职。
- **参数权威等级**：U 值和面积**只能 EDR**，手册经验值只作 sanity check；手算面积只作初筛。
- **验收门**：热负荷/面积余量/压降/流速 RhoV2/振动/物性范围/材料 逐项闭合。
- **停止规则**：物性曲线不覆盖包络、TascMsg 含操作失败、出口非物理、负面积余量未授权 → 隔离而非硬做。
- **迁移规则**：方法可迁移，另一台设备的数值一律不迁移。

---

## 9. 脚本与参考索引

| 文件 | 用途 |
|---|---|
| `scripts/edr_bridge.py` | COM 全流程桥（备份/校验/写/运行/读/另存，os._exit 防析构） |
| `scripts/edr_tascplus_design.py` | **Aspen→EDR 一体化设计（TASCPLUS-RIG，纯 COM 全自动，推荐）** |
| `scripts/edr_spec_optimize.py` | 规范符合性优化（Design→Rating 加余量、设污垢、标准规格寻优、规范验收） |
| `scripts/edr_import_aspen.py` | Aspen Plus → EDR 物性导入桥（SetAspenAppContext+ImportPSF 签名/psfMode=2 缺口/读 Aspen 流股物性） |
| `scripts/edr_xml.py` | .EDR XML 离线只读解析（校核/审计/提取） |
| `scripts/edr_diag.py` | 案例健康诊断（物性三查 + 几何/工艺完整性，运行前自检） |
| `references/user-design-conventions.md` | **用户设计约定 8 条**（管长3/6m、单位统一、消除警告、fluid name、不指定管数、NPS、图纸PDF 限制） |
| `references/edr-design-spec-compliance.md` | **设计规范符合性校核清单**（污垢/余量/流速/压降/长径比/标准规格 + 优化流程） |
| `references/industry-standards-and-rules.md` | 行业规定与设计规范（流股/选型/经验值/规范） |
| `references/engineering-authority-and-gates.md` | 工程方法论与权威边界（三权威/验收门/状态机/停止规则） |
| `references/edr-rating-methodology.md` | EDR 评级交付完整方法论（三权威+状态机+8步工作流+验收门+停止/迁移规则） |
| `references/edr-aspen-binding.md` | EDR 与 Aspen Plus 绑定（HeatX 评级卡/读回证明/假阳性识别/精确交付序列） |
| `references/com-api-and-troubleshooting.md` | COM 接口完整参考 + 故障排查 + 事故教训全集 |
| `references/property-import-and-freezing.md` | 物性导入与固化（BEX 链接/固化数组/1250 排查） |
| `references/standard-workflow.md` | 端到端标准工作流 SOP |
| `references/heat-transfer-principles.md` | 传热与换热器化工原理（热阻网络/LMTD/设计校核边界） |
| `references/case-e6101-reboiler.md` | E-6101 黄金案例复盘 |
| `references/case-e6102-cyclohexane-methanol.md` | E-6102 环己烷-甲醇从零设计案例 |

---

## 10. 版本历史

- **v1.0**（2026-09-29）：正式版，正式命名为 **EDR-skill**（原名 aspen-edr-automation / EDR-HX Engine）。整合为一个自包含技能：
  - 全部 COM 桥接/XML 解析/诊断脚本（edr_bridge.py / edr_xml.py / edr_diag.py）；
  - 八条安全铁律（含物性一致三查、纯组分走内置库）；
  - 行业规定、工程方法论（三权威分离 + 验收门 + 状态机 + 停止/迁移规则）、物性导入固化、标准工作流；
  - 新增"传热与换热器化工原理"（热阻网络、LMTD、设计/校核边界、U 非通用常数）；
  - 新增"EDR 评级交付方法论"（三权威+状态机+8步工作流+验收门）与"EDR 与 Aspen Plus 绑定"（HeatX 评级卡/读回证明/假阳性识别）两篇完整 reference；
  - **版本化输出规范**：每次输出成果 = 一个版本文件夹（Aspen Plus 模型 apwz/bkp + EDR 文件 + 说明文档，统一带版本号，源文件不动）；
  - 两个案例（E-6101 再沸器 + E-6102 环己烷-甲醇从零设计）。
- **v1.1**（2026-09-30）：补全"Aspen Plus → EDR 物性导入"逆向成果：
  - 精确定位 `ImportPSF(psfMode:int)` / `ImportPFS(parameters)` / `SetAspenAppContext(objAspenApp, fNameAspenApp, vaporizerType)` 签名（makepy 生成 ATVInterfacesVB.tlb）；
  - 确认 `ImportPSF(2)` 才触发真正 PSF 拉取，纯 COM 无 GUI 下有 GetPSF 桥缺口（zetasc.dll 未激活）；
  - 揭示官方一体化范例 `Aspen Plus V15.0\GUI\Examples\EDR\EDR-ShellTube.apwz` 的绑定语法（MODE=TASCPLUS-RIG + HETRAN-PARAM INPUT-FILE）与固化格式（DBToBeUsed=4 + CompMolecularWeight 数组）；
  - 修正铁律 8 枚举错误（纯组分 DBToBeUsed=1 而非 4）；新增脚本 edr_import_aspen.py；
  - 记录 Aspen Plus COM 孤儿进程坑（Aspen 侧用 Quit()，勿用 os._exit()）。
- **v1.2**（2026-09-30）：**Aspen→EDR 一体化设计纯 COM 全自动打通**（E-6102 案例跑通）：
  - 确立 **TASCPLUS-RIG 为物性导入正统路径**（`CALC-METHOD=TASCPLUS-RIG` + `HETRAN-PARAM INPUT-FILE`，Aspen 自动推物性给 EDR，DBToBeUsed=4），新增脚本 `edr_tascplus_design.py`；
  - 打通 XML 编辑注入纯组分（`NameOfComponents` 用化学式 C6H12/CH4O + 组分常数固化 + 数据库索引数组一致 + 清空 COMThermoInfoCS 对象）；
  - 新增铁律 9（物性曲线不会自动生成，须显式提供）、铁律 10（读 Aspen 生成的 EDR 用 XML 解析，绝不用 FileOpen 防 529 字节空壳事故）；
  - 新增 §6.7 FileOpen 回写覆盖 Aspen EDR 事故教训；
  - E-6102 v4 交付：Area=15.57 m²、U=1779 W/m²·K、Q=1699 kW、LMTD=62.6℃、89 根管 φ19.05×3m、壳 φ307mm。
- **v1.3**（2026-09-30）：**规范符合性优化 + 输出成品文件夹规则**：
  - 新增铁律 11（交付前必须通过规范校核：污垢>0、余量30~50%、气速≤30、压降≤允许、长径比3~15、标准规格）、铁律 12（污垢参数是 CS/HS 不是 SS/TS，判定 U_dirty<U_clean）；
  - 新增铁律 6b：**所有交付成品统一放项目根 `输出成品/` 文件夹**，每次交付建带版本号的小文件夹；
  - 新增 reference `edr-design-spec-compliance.md`（规范校核清单 + 优化流程 + 寻优策略 + 自检脚本）；
  - 修正 v4 缺陷（污垢未设 + 余量仅0.8%）：E-6102 v5 优化后 **余量 23.0%**、污垢 0.0001/0.0001、U_dirty=795、面积 42.35 m²、壳 387mm(16″标准)、管长 4500mm(标准)、160 管 φ19.05，全项达标；
  - 关键发现：Aspen TASCPLUS-RIG **不写回 EDR 结果段**，新几何结果必须用 EDR COM 跑；Design 模式余量恒≈0 需转 Rating 加余量。
- **v1.4**（2026-09-30）：**收录用户设计约定 8 条 + 消除警告实战**：
  - 新增 reference `user-design-conventions.md`（8 条约定的审核结论与落地方法）；新增铁律 13；
  - v6 优化实战：**诊断并归因 v5 的 11 条警告**（布局不一致 1132/1134、管数超布管上限 1291/1107、
    壳厚为负 1393、折流板长度 1225、振动 1611、跨距 1661）；
  - 关键机制发现：**Aspen 生成文件的布管（Tube Layout）被锁定**，Rating 改壳径后 EDR 不重布管 →
    改壳径会连锁产生"管数不一致 + 壳厚为负"；故**不指定管数、让 EDR 生成**是正确做法（用户第 6 条）；
  - 绘图 ID 定位：Setting plan=1、TEMA Sheet≈201.14；**无 GUI COM 下 PDF/DXF 导出不可靠**
    （ExportToDXF→False、PrintDrawing 不产出文件），需 GUI 导出；
  - φ25.4 管可显著改善管侧流速（37.7→24.8 m/s）与压降（0.443→0.185 bar）。
