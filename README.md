# EDR-skill v1.4 — Aspen EDR 换热器自动化技能（成品包）

> 面向 Aspen EDR / Aspen Plus 的管壳式换热器**自动化建模、物性导入、规范校核、交付**技能包。
> 全部内容均在 Windows + Aspen Plus V15 / Aspen EDR V15 实测验证。

## 一、这个包能做什么

- **一体化设计（推荐主流程）**：Aspen Plus HeatX 设 `TASCPLUS-RIG` 绑定 EDR，运行 Aspen 时
  自动把冷热流股物性推入 EDR，EDR 完成管壳式设计 → 纯 COM 全自动，无需 GUI。
- **规范符合性校核**：污垢、面积余量(30~50%)、流速、压降、长径比、TEMA 标准规格逐项验收。
- **物性导入与固化**：解决多组分/相变体系"直接在 EDR 填物性导致流股参数缺失"的问题。
- **COM 接口逆向参考**：ImportPSF/SetAspenAppContext 精确签名、CS/HS 与 SS/TS 参数命名规则、事故全集。
- **版本化交付**：按项目约定输出到 `输出成品/` 下的带版本号文件夹。

## 二、快速开始

```powershell
# ① 一体化设计（Aspen 物性 → EDR Design，纯 COM 全自动）
python scripts/edr_tascplus_design.py --edr-out E6102.EDR `
       --apwz-out E6102.apwz --rep-out E6102.rep --workdir <输出目录>

# ② 规范校核与优化（Design→Rating 加余量、设污垢、标准规格寻优）
python scripts/edr_spec_optimize.py --src base.EDR `
       --cases "387,4500,160" "438,4500,190" --foul 0.0001

# ③ 离线只读解析 .EDR（安全，不写文件）
python scripts/edr_xml.py scalars case.EDR
```

环境要求：Windows、Aspen Plus V15 + Aspen EDR V15（COM）、Python 3.13 + pywin32。
许可变量：`LSHOST` / `LSFORCEHOST` 设为主机名（脚本已内置）。

## 三、目录结构

```
EDR-skill-v1.4-成品包/
├── SKILL.md                      # 技能总纲：铁律13条、工作流、脚本与参考索引、版本历史
├── scripts/
│   ├── edr_tascplus_design.py    # ★ Aspen→EDR 一体化设计（TASCPLUS-RIG，推荐）
│   ├── edr_spec_optimize.py      # 规范符合性优化（加余量、设污垢、寻优、验收）
│   ├── edr_bridge.py             # COM 全流程桥（备份/校验/写/运行/读/另存）
│   ├── edr_import_aspen.py       # 物性导入桥（ImportPSF 签名/缺口/读流股物性）
│   ├── edr_xml.py                # .EDR XML 离线只读解析
│   ├── edr_diag.py               # 案例健康诊断（物性三查 + 几何/工艺完整性）
│   └── edr_design.py             # 设计桥（模板改工艺 + Design）
└── references/
    ├── user-design-conventions.md   # 用户设计约定 8 条（含审核结论）
    ├── edr-design-spec-compliance.md # ★ 规范校核清单 + 优化流程 + 寻优策略
    ├── com-api-and-troubleshooting.md # ★ COM 接口完整参考 + 事故全集（§6.6/6.8/6.9）
    ├── property-import-and-freezing.md # 物性导入与固化
    ├── industry-standards-and-rules.md # 行业规定速查
    ├── edr-aspen-binding.md       # EDR 与 Aspen Plus 绑定
    ├── edr-rating-methodology.md  # 评级交付方法论（三权威/验收门）
    ├── engineering-authority-and-gates.md
    ├── heat-transfer-principles.md
    ├── standard-workflow.md
    ├── case-e6101-reboiler.md     # E-6101 酯化再沸器案例
    └── case-e6102-cyclohexane-methanol.md # E-6102 环己烷-甲醇案例
```

## 四、核心铁律速记（违反可能损坏数据）

1. **只操作副本**：EDR `FileOpen` 会回写文件，加载失败会把空壳写回（有过 118KB→656B 事故）。
2. **读 Aspen 生成的 EDR 用 XML 解析，绝不用 FileOpen**（会回写成 529 字节空壳）。
3. **Aspen 侧 `Quit()` + `DispatchEx`**；EDR 侧 `os._exit()`（防析构回写）。
4. **污垢参数是 `FoulResCS/HS`**（冷/热侧），不是 `FoulResSS/TS`；判定生效：`U_dirty < U_clean`。
5. **不指定管数让 EDR 生成**（硬写管数会与布管冲突 → 连锁警告）。
6. **Design 模式余量恒≈0**，必须转 Rating 加余量后才可交付。
7. **输出前消除 errors & warnings**（`GetCalculationMessage`），无法消除须逐条说明。
8. **PDF/图纸导出**：无 GUI COM 下不可靠，需 EDR GUI 操作（Setting plan=1、TEMA Sheet≈201.14）。

## 五、版本历史

- v1.0（2026-09-29）初始正式版：COM 桥脚本、安全铁律、行业规定、两个案例。
- v1.1（2026-09-30）物性导入逆向：ImportPSF/SetAspenAppContext 精确签名、GetPSF 缺口。
- v1.2（2026-09-30）**TASCPLUS-RIG 一体化设计打通**：纯 COM 全自动，E-6102 v4 交付。
- v1.3（2026-09-30）**规范校核 + 输出成品文件夹规则**：修正 v4 污垢未设/余量不足 → v5（余量 23%）。
- v1.4（2026-09-30）**用户设计约定 8 条入库 + 警告归因**：布管锁定机制、绘图 ID、PDF 限制。
