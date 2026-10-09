"""EDR 案例健康诊断脚本 —— 物性三查 + 完整性体检（只读，绝不写文件）。

针对 E-6101 事故沉淀出的诊断能力：在打开/运行前，先用本脚本判断一个 .EDR
是否"物性可用、可安全运行"。纯 XML 解析，不依赖 COM，不会触发 FileOpen 回写。

用法:
  python edr_diag.py <file.EDR>

输出:
  - 物性三查（AspenPropertySelection / BEX 存在性 / 物性数组非空）
  - 几何完整性（壳径/管径/管长/管数/折流板）
  - 工艺完整性（冷热侧流量/温压/相态）
  - 结论：可安全运行 / 物性缺失需重建 / 需补几何 等
"""
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edr_xml import application, input_scalars, input_arrays  # noqa: E402


def _get(scalars, name):
    for n, v, u in scalars:
        if n == name:
            return v
    return None


def _arr_rows(arrays, name):
    for n, r, c in arrays:
        if n == name:
            return r
    return 0


def diagnose(path):
    root = ET.parse(path).getroot()
    app = application(root)
    sc = input_scalars(app)
    ar = input_arrays(app)
    d = {}

    # ---- 物性三查 ----
    d['AspenPropertySelection'] = _get(sc, 'AspenPropertySelection')
    bex = _get(sc, 'BEXFilename') or ''
    d['BEXFilename'] = bex
    d['BEX_exists'] = bool(bex) and os.path.exists(bex)
    # 物性数组非空判定（关键物性数组行数）
    prop_arrs = ['NameOfComponents', 'CompMolecularWeight', 'LiquidDensity',
                 'LiquidViscosity', 'LiquidSpecificHeat', 'LiquidThermalConductivity']
    arr_rows = {a: _arr_rows(ar, a) for a in prop_arrs}
    d['prop_arrs'] = arr_rows
    d['prop_frozen'] = any(r > 0 for r in arr_rows.values())

    # ---- 几何 ----
    d['ShlID'] = _get(sc, 'ShlID')
    d['TubeOD'] = _get(sc, 'TubeOD')
    d['TubeLng'] = _get(sc, 'TubeLng')
    d['TubePassNum'] = _get(sc, 'TubePassNum')
    d['BafSpcCC'] = _get(sc, 'BafSpcCC')

    # ---- 工艺 ----
    d['FlRaCS'] = _get(sc, 'FlRaCS')
    d['TempInCS'] = _get(sc, 'TempInCS')
    d['TempOutCS'] = _get(sc, 'TempOutCS')
    d['VapFrcOutCS'] = _get(sc, 'VapFrcOutCS')
    d['PresOperInCS'] = _get(sc, 'PresOperInCS')
    d['PropMethodCSSTR'] = _get(sc, 'PropMethodCSSTR')
    d['PropMethodHSSTR'] = _get(sc, 'PropMethodHSSTR')
    return d


def report(d):
    print("=== EDR 案例健康诊断 ===")
    print(f"物性选择标记 AspenPropertySelection = {d['AspenPropertySelection']}"
          f"  ({'固化' if d['AspenPropertySelection']=='0' else 'BEX链接' if d['AspenPropertySelection']=='1' else '未知'})")
    print(f"BEX 文件 = {d['BEXFilename'] or '(空)'}  存在={d['BEX_exists']}")
    print(f"物性数组固化 = {d['prop_frozen']}  (行数: {d['prop_arrs']})")
    print(f"物性方法 冷侧={d['PropMethodCSSTR']}  热侧={d['PropMethodHSSTR']}")
    print(f"几何: 壳径={d['ShlID']}mm 管={d['TubeOD']}mm x {d['TubeLng']}mm "
          f"管程={d['TubePassNum']} 折流板间距={d['BafSpcCC']}mm")
    print(f"工艺: 冷侧流量={d['FlRaCS']}kg/h  {d['TempInCS']}→{d['TempOutCS']}℃ "
          f"出口蒸发率={d['VapFrcOutCS']}  入口压力={d['PresOperInCS']}kPa")

    # 结论
    prop_ok = d['prop_frozen'] or d['BEX_exists']
    print("\n--- 结论 ---")
    if d['BEX_exists'] and not d['prop_frozen']:
        print("⚠️  物性依赖 BEX 链接（文件非自包含）。跨机/跨会话可能断链 → 建议固化物性。")
    if not prop_ok:
        print("❌ 物性不可用（无 BEX 且物性数组为空）。Run 必报 1250，需先重建物性。")
    elif not d['PropMethodCSSTR'] and not d['PropMethodHSSTR']:
        print("⚠️  物性方法为空，需设置 PropMethod（与 Aspen Plus 底座一致）。")
    else:
        print("✅ 物性可用，可尝试 Run。运行后仍需验证 rc==0 且 ErrorDescription=='Normal operation'。")
    return prop_ok


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__)
        return 1
    d = diagnose(argv[0])
    ok = report(d)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
