# EDR 换热器设计规范符合性校核清单

> 交付前必须逐项校核。本清单来自 E-6102 v5 优化实战（2026-09-30），
> v4 因「污垢未设 + 余量仅 0.8%」被判不合格，v5 修正后全部达标。

## 1. 必查项（任一 NG = 不可交付）

| # | 规范项 | 规范要求 | EDR 参数（COM 名） | 判定 |
|---|---|---|---|---|
| 1 | **污垢热阻** | 有机介质/轻烃 0.0001~0.0002 m²·K/W（每侧）；冷却水 0.00018~0.00035；含醋酸 0.0003~0.0005；蒸汽 0.00009~0.00017 | `FoulResCS`（冷侧）/`FoulResHS`（热侧） | 必须 >0 |
| 2 | **面积设计余量** | 常规 **30~50%**；再沸器/冷凝器 30~50% | `AreaRatioDirty` = `Area`/`AreaReqDirty` | (ratio-1)×100% 落在区间内 |
| 3 | 管侧流速 | 液 0.5~3 m/s；气 10~30 m/s | `VelExitBundleTS`（出口）/`VelEntBundleTS`（进口） | 气相出口 ≤30 |
| 4 | 壳侧流速 | 错流一般 <15 m/s | `VelCrossFlowMaxSS` | ≤15 |
| 5 | 管侧压降 | ≤允许值 `PresDropAlloTS`（常 0.5 bar） | `PresDropCalcTS` | ≤允许 |
| 6 | 壳侧压降 | ≤允许值 `PresDropAlloSS`（常 0.26 bar） | `PresDropCalcSS` | ≤允许 |
| 7 | 长径比 | 管长/壳径 = 3~15 | `TubeLng`/`ShlID` | 在区间内 |
| 8 | 物性覆盖 | 物性曲线须覆盖操作包络 | 见 property-import-and-freezing.md | 非空 |

## 2. 标准规格（选型必须取标准值，勿用任意值）

- **壳径（TEMA）**：6″=152、8″=203、10″=254、12″=305、**14″=337**、**16″=387**、18″=438、20″=489 mm
- **管长**：1500、2000、3000、**4500**、6000、9000 mm
- **管外径**：φ19.05（3/4″）最常用，φ25.4（1″）次之
- **管心距**：管径的 1.25 倍（φ19.05 → 23.8 mm）
- **壳体类型**：E（单程壳，最常用）、K（釜式再沸器）、U、X

> 非标准尺寸（如壳径 360 mm、管长 3600 mm）即使热工合格也不应交付——无法采购/制造。

## 3. 污垢生效的判定（易踩坑）

```
U_dirty < U_clean  →  污垢已生效 ✅
U_dirty = U_clean  →  污垢为 0，未生效 ❌（v4 的缺陷）
```
- `HeatTranRatClean` 与 `HeatTranRatDirty`：若相等说明 `FoulResCS/HS=0`。
- 注意：**EDR 污垢参数是 CS/HS（冷侧/热侧），不是 SS/TS（壳侧/管侧）**。
  `FoulResSS`/`FoulResTS` 在 COM 中**不可访问**（返回 None），必须用 `FoulResCS`/`FoulResHS`。

## 4. 优化流程（从 Design 结果到合规交付）

Design 模式（TascProgMode=1）EDR 自动定几何，**余量恒≈0**，必须转为 Rating 加余量：

```
① Aspen TASCPLUS-RIG 跑一次  → 得到含完整物性的 EDR（Design 基准）
② 复制副本（★只操作副本，FileOpen 会回写）
③ EDR COM FileOpen 副本
④ 设污垢：FoulResCS = FoulResHS = 0.0001
⑤ 改几何：ShlID / TubeLng / TubeNum 取标准规格
⑥ 切 Rating：TascProgMode = 2
⑦ Run → 读 AreaRatioDirty / 流速 / 压降校核
⑧ 迭代 ⑤~⑦ 直到余量落 30~50% 且各项达标
⑨ 交付：保留该副本为交付 .EDR（含物性+优化几何+校核结果）
```

### ★ 关键陷阱：Aspen 运行不写回 EDR 结果段
Aspen TASCPLUS-RIG 运行后，EDR 文件的**结果段是旧值**（不更新），
只有 Aspen 流股结果反映新几何。要拿到新几何下的面积/U/压降，**必须用 EDR COM 跑**（步骤③~⑦）。

## 5. 寻优策略

- 余量不足（<30%）→ 增大面积：加管数（同壳径）或加长管（标准档）。
- 余量超标（>50%）→ 减小面积：减管数或缩短管。
- 管侧气速超限（>30 m/s）→ 增加管数（降低单管流量）。
- 压降超限 → 增加管数、加大折流板间距、或改壳型。
- **目标：余量取 ~40%（规范中值）**，兼顾安全与经济性。

## 6. 交付前自检脚本思路

```python
checks = {
  '污垢>0': FoulResCS > 0 and FoulResHS > 0,
  '余量30~50%': 30 <= (AreaRatioDirty-1)*100 <= 50,
  '管侧气速<=30': VelExitBundleTS <= 30,
  '管压降<=允许': PresDropCalcTS <= PresDropAlloTS,
  '壳压降<=允许': PresDropCalcSS <= PresDropAlloSS,
  '长径比3~15': 3 <= TubeLng/ShlID <= 15,
  'U_dirty<U_clean': HeatTranRatDirty < HeatTranRatClean,
  '壳径标准': ShlID in [152,203,254,305,337,387,438,489],
  '管长标准': TubeLng in [1500,2000,3000,4500,6000,9000],
}
```

## 7. 参考规范

- **TEMA**（管壳式换热器制造商协会标准）：壳体类型、管径、折流板、污垢。
- **GB/T 151**（中国 热交换器）：设计、材料、制造、检验。
- **ASME Ⅷ**：压力容器（Mechanical 阶段）。
- 行业经验值见 `references/industry-standards-and-rules.md`。
