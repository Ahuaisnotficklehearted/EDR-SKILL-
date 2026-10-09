# EDR COM 接口完整参考与故障排查手册

> 本文档沉淀 EDR COM 逆向工程的完整成果 + 全部事故教训。是 edr_bridge.py / edr_xml.py 背后的原理说明，也是换版本/换机器时重新验证接口的操作手册。

## 1. COM 对象模型（V15 实测）

### 1.1 ProgID 与主流程
```
ProgID: BJACCOM2.BJACApp       # 主控（应用级，可 Run / FileOpen / GetAppObject）
ProgID: BJACWIN.BJACApp        # 官方 .NET ShellApp（AspenTech.EDR.ShellApp.BJACApp，另一入口）
ProgID: BJACCOM2.Document      # 单文档（FileSaveAs / FileClose）
核心 DLL: <EDR安装>\XEQ\BJACCOM2.dll  (.NET，需 pywin32/win32com 经 COM interop 调用)
```
- **无 OpenDoc 方法**。打开用 `BJACApp.FileOpen(path)`，取对象用 `GetAppObject(path, "Tasc")`、`GetDocument(path, False)`。
- **两个 ProgID 均可 Dispatch**：`BJACWIN.BJACApp` 是官方 .NET ShellApp（更正式），`BJACCOM2.BJACApp` 是 COM 包装。二者方法集基本一致。
- **重要方法（2026-09-30 实测确认，含精确签名，来源 makepy 生成的 ATVInterfacesVB.tlb）**：
  - **`app.ImportPSF(psfMode: int)`** — app 层方法名是 **ImportPSF**（注意是 PSF 不是 PFS）；**第一个参数是 int（psfMode），不是文件路径**。`BJACApp` 主控层另有 `ImportPFS(parameters)`（.NET 参数对象，参数名 `parameters`）。
  - **`app.SetAspenAppContext(objAspenApp, fNameAspenApp, vaporizerType='')`** — 把运行中的 Aspen Plus COM 实例（objAspenApp，`Apwn.Document` 对象）+ Aspen 文件名（fNameAspenApp）+ 气化器类型串（vaporizerType）绑定到 EDR 上下文。实测恒返回 OK。
  - `app.CopyComponentNamesAndFormulas()`、`app.TransferData()`、`app.RefreshData()`、`app.SetUom()`、`app.HeatLoadCalc()`、`app.FlowrateCalc()`、`app.APropInterface`、`app.objAspenProp`、`app.LegacyAspenProperties` 等物性/数据方法。
- 程序名（application name）：Shell&Tube=**Tasc**、AirCooled=**Acol**、Plate=**Aple**、PlateFin=**PlateFin**、CoilWound=**CoilWound**、FiredHeater=**Fire**、Ensea=**Ensea**。

### 1.1b ImportPSF 的 psfMode 语义（2026-09-30 实测）

`app.ImportPSF(psfMode)` 的 psfMode 实测行为：
- **psfMode=2 = 真正触发从 Aspen Plus 拉取 PSF 物性**（内部调 PSFImport.dll 的 `GetPSF`）。
- psfMode=0/1/3/4/5/6 静默返回 OK，但**组分不变**（仍是模板默认值，如 ForcedVaporizer 的 Water）——这些模式不触发实际拉取。
- **纯 COM 无 GUI 下的硬缺口**：`ImportPSF(2)` 报「重载决策失败，因为没有可访问的 GetPSF 接受此数目的参数」。根因是 `GetPSF` 需要 Aspen Plus 侧的 EDR 桥（`Engine\Xeq\zetasc.dll`，原生代码）激活，该桥只在 Aspen Plus GUI「HeatX 块 → Send to Aspen EDR」集成模式下工作；`Apwn.Document` 纯 COM 打开不激活它。

**PSFImport.dll（`XEQ\AspenTech.EDR.Components.PSFImport.dll`）公开方法**（dnfile 元数据反编译）：`ImportPSF`、`ImportAspenPlus`、`ImportHYSYS`、`GetPSFPropertyDataMultiStream`、`DealWithPSFStream`、`ImportSingleStream`、`ImportMultiStream`。其中 **`ImportAspenPlus` 是"从 Aspen Plus 导入物性"的正统方法**（但同受 zetasc.dll 桥制约）。

### 1.2 app 对象（Tasc 程序）成员全集（V15 实测 dir() 枚举）

状态/结果判定：`IsComplete`、`HasResults`、`ResultStatus`、`RunID`、`Status`、`Run`、`Run2`。

标量/数组访问（**推荐用这些方法，比直接集合索引稳**）：
- `GetScalar(name)` / `GetResultScalar(name)`
- `GetArray(name)` / `GetResultArray(name)` / `GetRecapArray(name)`
- `Scalars` / `ResultScalars` / `Arrays` / `ResultArrays` / `RecapArrays` / `TempArrays` / `TempScalars`

数据校验：`CheckData`、`DoCheck`、`CanRun`、`AsyncCheckData`、`CCheck`/`CCheckArrayElement`。

单算：`FlowrateCalc`、`HeatLoadCalc`（可单独算流量/热负荷）。

组分/物性：`Objects`（.Item 访问，含设备/组分对象）、`CopyComponentNamesAndFormulas`、`ThermoInfoStatus`、`LegacyAspenProperties`、`objAspenProp`、`APropInterface`、`SetAspenAppContext`、`ImportPSF`。

消息：`GetCalculationMessage(index)`（运行后取错误详情，空串=无错）、`GetCalculationMessageWithGroupname`。

### 1.3 组分注入的已知线索（从零建纯组分，待最后一公里）
- 组分规格标量：`CompSpcCS`/`CompSpcHS`（=1 表示用户指定组分）、`DBToBeUsedCS`/`DBToBeUsedHS`（数据库选择，官方示例蒸发器用 1，E-6101 用 4/2，枚举含义待完全确认）。
- 组分符号/名称在数组 `BJacDBSymbol`/`NameOfComponents`/`CompositionHS`（XML 里为空，实际走 BEX 或 B-Jac 库动态填充）。
- 组分对象在 `Objects` 集合（Count>0，`.Item(i)` 访问）。
- 三条路径待打通：① `ImportPSF`（Aspen Plus PSF 导入）；② 直接写 `BJacDBSymbol` 数组 + `DBToBeUsed=内置库`；③ `CopyComponentNamesAndFormulas` 从模板拷贝。

### 1.2 标量/数组访问
```python
sc = app.Scalars            # 输入标量集合：sc.Count；sc("ShlID").Value；sc("ShlID").Uom
sc("TubeLng").Value = 6000  # 写输入（.Value 属性带 get/set）
rs = app.ResultScalars      # 结果标量：rs("Area").Value / .Uom（只读）
arr = app.Arrays            # 输入数组（成分、物性曲线、管口表）
rarr = app.ResultArrays     # 结果数组
```
- **数量**（V15）：输入标量 ~533 个、结果标量 ~871 个（全量可 dump 成 CSV 做变量字典）。
- **comtypes 有坑**：对带参属性（`Scalars(name)`）返回 NamedProperty，取不到值。**统一用 pywin32**（win32com 自动合并 METHOD|PROPERTYGET）。

### 1.3 运行与结果判定
```python
rc = bjac.Run("Tasc")                 # 运行指定程序
err = bjac.ErrorDescription           # 返回 'Normal operation.'（带句号！）
ok = (rc == 0 and err.strip().rstrip('.').lower() == 'normal operation')
```
- **rc==1250 = 计算失败**（收敛/物性/几何错误）。失败时 FileSaveAs 仍会保存出一个"无效结果文件"，**禁止以保存成功判定运行成功**。
- 保存：`doc.FileSaveAs(path)`；关闭：`doc.FileClose()`。

### 1.4 许可环境
- 与 Aspen Plus 同源（Sentinel RMS）。进程环境设：
  ```python
  os.environ['LSHOST'] = socket.gethostname()
  os.environ['LSFORCEHOST'] = socket.gethostname()
  ```

## 2. .EDR 文件格式（XML，可离线只读解析）

- `.EDR` 是 XML：`<HTEdata FileSignature="AspenTech/EDR V15 (41.0.0.451)">` → `<application name="Tasc">`。
- application 内顺序固定：`match` → `result`(运行状态码) → `uomset` → **第一个 scalars(输入)** → **第一个 arrays(输入)** → **第二个 scalars(结果)** → **第二个 arrays(结果)** → `objects`。
- 标量结构：`<scalar name=".."><uom>..</uom><value>..</value><source>User|Result</source></scalar>`。
- **物性数据有两种存法**：
  1. **BEX 链接**（`AspenPropertySelection=1` + `BEXFilename` 指向临时 .BEX）：物性动态从 Aspen Plus 导入，数组（Comp*、LiquidDensity 等）为空。**BEX 丢失=文件加载失败=空壳覆盖事故的根源**。
  2. **固化数据**：物性数组直接写在 XML 里（`AspenPropertySelection=0` 或 OverwriteProperties）。
- 用 `edr_xml.py` 离线解析：`dump/scalars/results/arrays/find` 子命令。

## 3. 事故教训全集（每一条都是踩过的坑）

### 3.1 【P0】FileOpen 回写覆盖（数据丢失）
- 现象：E-6101-7.EDR 从 118KB 变成 656B 空壳。
- 机制：`FileOpen` 语义 = "加载新文件并回写被打开文件"。文件带失效 BEX 链接 → 加载失败 → 内存空文档被写回 → 覆盖原文件。
- 防护：**只操作副本**（先 copy2 备份）；FileOpen 后**立即校验** 2~3 个已知标量值（对比 XML 值），读到默认值=空壳，立即终止。

### 3.2 【P0】析构回写（进程强杀）
- 现象：timeout 强杀 COM 会话后，析构把内存文档回写到最后 FileOpen 的路径（好文件→528B 空壳二次发生）。
- 防护：**退出统一 `os._exit()`** 绕过析构（edr_bridge.py 已内置）；绝不用 sys.exit/raise 让析构有机会执行。

### 3.3 【P1】备份失效
- 现象：坏文件被备份后再"恢复"仍是坏的。
- 防护：备份后校验（XML scalar 数 ≥ 阈值）；恢复来源分层（本地备份 → 原始来源重取）。

### 3.4 【P1】FileSaveAs 间歇阻塞
- 现象：文件实际已保存但调用不返回。
- 防护：FileSaveAs 放最后一步 + 整体超时 + 以"目标文件生成且大小合理"判成功。

### 3.5 【P1】BEX 物性链接失效（E-6101 复现确认）
- 现象：`Failed to Load COMThermo from XML.`；Run 报 `Error code = 1250`。
- 根因：`AspenPropertySelection=1` + `BEXFilename` 指向 Temp 里已不存在的 .BEX。
- **实测确认（2026-09-29）**：恢复原件 FileOpen 后，`AspenPropertySelection` 从 1 被**静默置 0**、`BEXFilename` 清空、`PropMethodCSSTR` 清空；Comp*/LiquidDensity 等物性数组全 0 行。**几何/工艺标量仍在，但物性方法+数据全失 → Run 报 1250**。
- **关键补充（2026-09-30 修正）**：EDR 官方示例分两类——① `Examples\Shell&Tube\*.EDR`（如 TS-Condenser-Vertical_BEM.EDR）是 `AspenPropertySelection=1` + BEX 指向原作者机器路径，换机后 BEX 失效、物性数据不在 .EDR 里；② **Aspen Plus 自带的 `GUI\Examples\EDR\EDR-ShellTube.apwz`（内含 EDR-ShellTube.bkp + EDR-ST.EDR）是"Aspen→EDR 一体化"的官方范例**，其 EDR-ST.EDR 用 `DBToBeUsedCS/HS=4`(User specified) + `CompSpcCS/HS=1` + BEXFilename + **固化的物性数组**（`CompMolecularWeight`、`CompCriticalTemperature`、`LiquidDensity`、`Comp01LiqMoleFrc`~`Comp14...` 等 14 组分烃类混合物），物性数组直接写在 XML 里（`<array name="CompMolecularWeight" SizePerSet="50"><values><valueslist list="16.04276,30.06964,..."/>`）。**这是"从 Aspen 导入物性"落地后的自包含形态模板**。
- **本质**：物性是通过 BEX/COMThermo **独立于输入标量**导入的机制；链接断 = 物性全失，无法计算。
- **防护**：交付 EDR 前把物性**固化进 XML**（`AspenPropertySelection=0` + 组分/物性曲线数组非空）；跨机/跨会话传 EDR 时 BEX 链接必断，必须重导入或固化。**重建路径**：Aspen Plus（同物性方法）→ 重新导入 BEX 或固化数组。

### 3.7 【P1】纯组分体系应走 EDR 内置库，勿用 BEX
- 纯组分（如环己烷、甲醇、水、蒸汽）在 EDR 内置 B-Jac 数据库里都有，`DBToBeUsed=1` 即 B-Jac 库（**实测枚举：1=B-JAC、2=Aspen Properties、3=COMThermo、4=User specified properties**，见 §6）。
- 设组分符号（BJacDBSymbol）+ 物性方法（PropMethodCSSTR/HSSTR），让 EDR 自生物性曲线，**规避 BEX 断链风险**。
- 只有**自定义混合物/电解质**（如酯化体系）才需要 Aspen Plus BEX 链接。

### 3.8 【P1】组分注入三大障碍（2026-09-30 实测，纯组分 E-6102 从零设计卡点）
纯组分（环己烷/甲醇）通过 COM 注入组分的实测结论：
- **COMThermo/BEX 缓存会锁定组分**：带 `AspenPropertySelection=1`+`BEXFilename` 的模板（如 KettleReboiler、TS-Condenser）打开时报 `Failed to Load COMThermo from XML`，改 `FluidNam` 后组分**仍是缓存的旧组分**（改 METHANOL 仍返回 Hexane 的 MW=86）。
- **`CompSpcCS/HS=1` 会锁定组分规格**：ForcedVaporizer 模板 `CompSpc=1`，改 `FluidNam` 后任何纯组分名都回退到 Water（MW=18）。
- **`FluidNam` 文本在 FileOpen 时解析**，COM 运行期改标量不触发重新解析；纯组分名（Methanol/Cyclohexane/Hexane）在无 GUI 环境下无法通过 FluidNam 触发 B-Jac 库搜索（但模板里预置的 Methane/Hexane/Water/Steam 能正确解析出 MW=16/86/18）。
- **三条路径现状（2026-09-30 更新）**：① `ImportPSF(psfMode=2)`（Aspen Plus PSF 导入，签名已定位：`ImportPSF(int)`，但纯 COM 下 GetPSF 桥缺口，见 §1.1b）；② 直接写 `BJacDBSymbol` 数组 + `DBToBeUsed=1`(B-JAC)；③ `CopyComponentNamesAndFormulas`（实测返回 (0,n) 但不改组分）。
- **实测有效捷径**：找官方示例里**已用目标组分**的文件（如 Gas-Gas 用 Methane、Kettle 用 Hexane、TS-Condenser 用 Water/Methanol 混合物）作为模板，只改工艺参数不改组分。
- **新发现：`Arrays` 集合有 `Add` 方法**（可动态添加数组），`Objects` 集合可访问组分对象——这是路径②"直接写组分数组"的入口，待打通。

### 3.6 【P2】错误判定字符串
- ErrorDescription 返回带句号的 'Normal operation.'，比较必须 rstrip('.')。

## 4. 接口再验证方法（换版本/换机器时）

1. **枚举 ProgID**：`winreg` 遍历 `HKCR`（沙箱可能拦截 reg.exe，用 Python winreg 模块）。
2. **静态枚举接口成员**：对 `ATVInterfacesVB.dll` 用 `dnfile` 解析，枚举 IATVApp/IATVScalars/IATVScalar 成员。
3. **运行时 dump**：comtypes `CreateObject("BJACCOM2.BJACApp")` 后 `dir(type(obj))`。
4. **冒烟测试**：用官方示例（如 `TS-Thermosiphon-Vertical_BEM.EDR`）走一遍 open→verify→run→results→save，确认接口与判定逻辑在目标版本成立。

## 5. 变量字典构建方法

```python
# dump 全量输入/结果标量到 CSV，建立变量字典
sc = app.Scalars
for i in range(sc.Count):
    it = sc.Item(i)   # 或 sc(i) 按索引
    print(it.Name, it.Value, it.Uom)
# 结果同理 ResultScalars
```
- 官方文档另有 `B-Jac variables` 完整清单，可按类型（几何/工艺/结果）分类建档。

## 6. 关键枚举与数据库逆向（2026-09-30 实测，从 SQLite 数据库挖出）

EDR 的枚举定义**直接存在 SQLite 数据库**里，可离线查询：
`<EDR安装>\Dat\SQLiteDB\main_2014.db`（主库，含全部枚举表）与 `FrequentUseComponents.db`（常用组分）。

### 6.1 核心枚举（表名 → 取值）
| 表 | 取值（Index → 含义） |
|---|---|
| `HTFSDBToBeUsed` | **1=B-JAC Databank、2=Aspen Properties、3=COMThermo、4=User specified、5=User spec+heat loads** |
| `HTFSApplType` / `HTFSApplicationType` | 0=Program、1=Liquid无相变、2=Gas无相变、**3=Phase Change(相变)** |
| `VaporizerType` / `HTFSVaporizerType` | 1=Pool boiling(釜式)、2=Thermosiphon、3=Forced circulation、4=Falling film |
| `CondenserType` / `HTFSCondenserType` | 1=Normal、2=Knockback reflux |
| `FlashOption` | 1=V-L、2=V-L-L、3=V-L-FreeWater |
| `CompositionType` | 1=重量流量/%、2=摩尔流量/%、3=体积流量/% |
| `ComponentTypeCS` | 0=Program、1=Inert |
| `ComponentTypeHS` | 0=Program、1=Noncondensable、2=Immiscible condensable、3=Condensable |
| `ChemDBSource` | 1=Databank、2=User |

### 6.2 组分数据库查询（BJACChemDBIndex 表）
```python
import sqlite3
con = sqlite3.connect(r"<EDR>\Dat\SQLiteDB\main_2014.db")
cur = con.cursor()
cur.execute("SELECT Name, SearchName, Synonym, Formula, MW, DID, BID FROM BJACChemDBIndex WHERE Name LIKE '%CYCLOHEX%'")
```
- **环己烷**：Name=`Cyclohexane`、SearchName=`Cyclohexane`、Synonym=`CYCLOHEX`、Formula=C6H12、MW=84.16、DID=D137、BID=B57
- **甲醇**：Name=`Methanol`、Synonym=`METHANOL`、Formula=CH4O、MW=32.04、DID=D1101、BID=B14
- **正己烷**：Name=`n-Hexane`、SearchName=`Hexane`、Synonym=`N-HEXANE`、MW=86.18、BID=None（注意 Name 是 n-Hexane 不是 Hexane）
- **水**：Name=`Water`、MW=18.01、BID=B1；**蒸汽**：Name=`Steam`、MW=18.01、BID=B2

### 6.3 B-Jac 纯组分库（D_IDBJAC.PDA，定长文本）
`<EDR>\Dat\PDA\D_IDBJAC.PDA` 每行格式：`BID | 0 | Formula | FULLNAME | SYNONYM | ID`
```
B57   0   C6H12   CYCLOHEXANE   CYCLOHEX   57
B14   0   CH4O    METHANOL      METHANOL   14
B13   0          N-HEXANE      HEXANE     13
```
- **FluidNam 应填 FULLNAME 或 SYNONYM**（大写），但实测无 GUI COM 下纯组分 FluidNam 解析仍受 COMThermo 缓存/CompSpc 锁定制约（见 §3.8）。

### 6.4 设计/评级模式与单位
- `TascProgMode`：1=Design(设计)、2=Rating/Check(校核)、3=Simulation(模拟)。切 `TascProgMode=1` 即设计模式，EDR 自动定几何。
- `uomset`：1=英制(US)、2=公制(SI)。`DesignDimUnits`=1=公制、2=英制。切换单位可用 app 的 `SetUom()`。
- 冷侧 CS = 吸热流体（再沸器=蒸发物料），热侧 HS = 放热流体（蒸汽/冷凝介质）。`LocFluidHS`=1=热侧在管侧、2=热侧在壳侧。

### 6.5 官方示例模板速查（Shell&Tube，做设计选模板）
| 文件 | 冷侧/热侧 | 用途 |
|---|---|---|
| ForcedVaporizer_BEM | Water(加热)/Water(蒸汽冷凝) | 强制气化器，BEM固定管板，最通用 |
| KettleReboiler_AKU | Hexane(蒸发90%)/Steam(冷凝) | 釜式再沸器，K型壳，公制，冷侧蒸发模板 |
| FallingFilmEvaporator_AEL | Brine(蒸发20%)/Steam | 降膜蒸发器 |
| TS-Thermosiphon-Vertical_BEM | 烃混合物(蒸发21%)/Steam | 立式热虹吸 |
| TS-Condenser-Vertical_BEM | Water/Water60%+Methanol40% | 立式冷凝器，含混合物 |
| Gas-Gas_AFM | Methane/Methane | 气-气，Methane 纯组分有效 |
| Liquid-Liquid_AEL | Water/Water | 液-液 |

> 空模板（极简，只含 DesignDimUnits+ShlType）在 `<EDR>\Dat\Template\`：`CS_Fixed_Tubesheet_SI.EDT`（碳钢固定管板公制）、`CS_Kettle_Reboiler_SI.EDT` 等。

### 6.6 Aspen Plus ↔ EDR 一体化集成（2026-09-30 实测全自动打通 ✅）

**这是 Aspen→EDR 物性导入的「正统」路径，实测纯 COM 全自动跑通**（脚本 `scripts/edr_tascplus_design.py`）。

**Aspen 侧 HeatX 块 inp 语法（实测正确版）**：
```
BLOCK B1 HEATX
    PARAM VFRAC-COLD=0.70 CALC-TYPE=DESIGN CALC-METHOD=TASCPLUS-RIG
    HETRAN-PARAM INPUT-FILE="<同设备>.EDR"
    BJAC-INPUTS FOUL-OPTION=PROGRAM
    FEEDS HOT=S1 COLD=S2
    OUTLETS-HOT S3
    OUTLETS-COLD S4
    HOT-SIDE DP-OPTION=CONSTANT DPPARMOPT=NO
    COLD-SIDE DP-OPTION=CONSTANT DPPARMOPT=NO
```
> ⚠️ 关键字是 **`CALC-METHOD=TASCPLUS-RIG`**（不是 `MODE="TASCPLUS-RIG"`——那是官方
> .bkp 内部格式，写进手写 .inp 会报 2041 打不开）。官方 .bkp 里另有
> `PROGRAM-MODE=... MODE="TASCPLUS-RIG"` + `HETRAN-PARAM ... SAV-HOT-STRM=YES SAV-CLD-STRM=YES`。

**机制（实测确认）**：Aspen 引擎跑 HeatX 时自动：① 算冷热流股物性（组分/密度/粘度/比热/
导热/焓随温压）；② 把物性写进 .EDR 固化数组（`CompMolecularWeight`/`LiquidDensity`/
`VaporDensity` 等，`DBToBeUsed` 自动置 **4=User specified**）；③ 调 EDR 引擎做 Design，
几何+面积+U 回传 Aspen。**这一步绕开了纯 COM `ImportPSF(2)` 的 GetPSF 桥缺口**。

**实测案例 E-6102 结果**：环己烷(热侧全凝 172→161.3℃)+甲醇(冷侧蒸发70% 80→107.5℃)，
Q=1699 kW，LMTD=62.6℃，U=1779 W/m²·K，Area=15.57 m²，89 根管(φ19.05×3m)，壳 φ307mm。

**方向二**（EDR 拉 Aspen）：EDR 侧 `SetAspenAppContext(AspenApp, file, vaporizerType)` + `ImportPSF(2)`（见 §1.1b），纯 COM 下有 GetPSF 桥缺口——**不推荐，用方向一**。

**Aspen Plus COM 侧关键点**：
- ProgID `Apwn.Document`（`InitFromFile2` 打开 / `Run2` 运行 / `Tree.FindNode` 读写 / `SaveAs2` 保存 / `Export(2, .rep)` 导报告）。
- **Aspen 侧没有直接的"导出 EDR 输入" COM 方法**——EDR 集成靠 GUI 菜单「HeatX 块 → Send to Aspen EDR」触发，底层是原生桥 `Engine\Xeq\zetasc.dll`（非 .NET，COM 不暴露）。
- **`Tree` 对象的 `PFSSelectModel`/`PFSClearSelection` 是"PFS 视图"（Process Flowsheet）的模型选择，与物性 PSF 无关，勿混淆**。
- **孤儿进程坑**：Aspen Plus COM 用 `os._exit()` 退出会遗留孤儿 `AspenPlus.exe`（内存仅 ~48-52K 空壳），锁住引擎 RPC 通道，导致后续 `Dispatch` 的 `Run2` 报「远程过程调用失败 (-2147023170)」。Aspen 侧应**用 `DispatchEx` 强制新实例 + `Quit()` 正常关闭**；EDR 侧才用 `os._exit()`。

### 6.7 【P0】FileOpen 回写覆盖 Aspen 生成的 EDR（2026-09-30 新增事故）
- 现象：Aspen TASCPLUS-RIG 运行后生成的完整 .EDR（~300KB，含物性+设计结果），再用
  EDR COM `FileOpen` 读结果，文件被回写成 **529 字节空壳**（只剩 `<HTEdata><application>`
  + `<result>1</result>`，物性/几何/结果全丢）。
- 根因：`FileOpen` 语义="加载并回写"。Aspen 写的 EDR 与 EDR 引擎自身保存格式有细微差异，
  加载后回写把内存（未完整解析的）状态覆盖原文件。
- 防护：**读 Aspen 生成的 EDR 结果，用 XML 正则解析（不 FileOpen）**。只有操作 EDR 引擎
  自己保存的 .EDR 时，才 FileOpen 且先 copy2 备份。

### 6.8 参数命名陷阱：CS/HS vs SS/TS（2026-09-30 实测）
EDR 同一物理量常有两套后缀，用错会拿到 None：
- **CS/HS**（冷侧 Cold Side / 热侧 Hot Side）：**组分与污垢**用这套——
  `FluidNamCS/HS`、`FoulResCS/HS`（污垢热阻）、`CompSpcCS/HS`、`DBToBeUsedCS/HS`、`VapFrcOutCS`。
- **SS/TS**（壳侧 Shell Side / 管侧 Tube Side）：**流动与结果**用这套——
  `PresDropCalcSS/TS`（压降）、`Vel*SS/TS`（流速）、`FoulMaxSS/TS`（污垢上限）。

**实测坑**：`FoulResSS`/`FoulResTS` 在 COM 中返回 None（不可访问），设污垢必须用
**`FoulResCS`/`FoulResHS`**。XML 里两个名字都在，但 COM 只认 CS/HS。

### 6.9 Aspen TASCPLUS-RIG 不写回 EDR 结果段（2026-09-30 实测）
- 现象：用 XML 改了 EDR 的几何（ShlID/TubeLng/TubeNum）后跑 Aspen TASCPLUS-RIG，
  Aspen 流股结果确实随新几何变化（S4 出口温度不同），但 **EDR 文件结果段仍是旧值**
  （Area/U/压降没更新）。
- 结论：Aspen 只把结果给自己的流股，**不回写 EDR 结果段**。要拿到新几何下的完整校核结果
  （面积余量/U/压降/流速），必须走：**Aspen 推物性 → 复制副本 → EDR COM FileOpen 副本 →
  改几何 → TascProgMode=2(Rating) → Run → 读 ResultScalars**。
- 另：Design 模式（TascProgMode=1）EDR 自动定几何，**面积余量恒≈0**（本次实测 0.8%），
  要满足 30~50% 规范余量必须转 Rating 并手动放大几何（见 edr-design-spec-compliance.md）。
