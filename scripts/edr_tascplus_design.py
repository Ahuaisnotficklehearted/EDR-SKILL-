# -*- coding: utf-8 -*-
"""Aspen Plus → EDR 一体化管壳式设计（纯 COM 全自动，TASCPLUS-RIG 路径）。

【核心突破 2026-09-30】这是 Aspen→EDR 物性导入的「正统」路径，实测全自动打通：

  Aspen HeatX 块设 CALC-METHOD=TASCPLUS-RIG + HETRAN-PARAM INPUT-FILE=*.EDR，
  运行 Aspen 时引擎自动：① 算冷热流股物性（组分/密度/粘度/比热/导热/焓随温压）；
  ② 把物性写进 .EDR 的固化数组（CompMolecularWeight/LiquidDensity/VaporDensity 等，
  DBToBeUsed 自动置 4=User specified）；③ 调 EDR 引擎做 Design，几何+面积+U 回传。

  这正好回答了「为什么先跑 Aspen 再导入 EDR」——多组分/相变体系的物性曲线
  由 Aspen 自洽算出，比在 EDR 手工填物性可靠得多。

对比：纯 COM 无 Aspen 时，EDR 的 ImportPSF(2) 报 GetPSF 桥缺口（需 GUI），
且 XML 手写物性曲线数组极易缺列/错位。TASCPLUS-RIG 绕开了这些坑。

用法：
  python edr_tascplus_design.py --edr-template CS_Fixed_Tubesheet_SI.EDT \
      --edr-out E6102.EDR --apwz-out E6102.apwz --rep-out E6102.rep

安全铁律（沿用 edr_bridge.py）：
  1. Aspen 侧用 Quit() 正常关（Aspen 无析构回写风险；EDR 侧才用 os._exit()）。
  2. Aspen 用 DispatchEx 强制新实例，避免连到孤儿 AspenPlus.exe（Run2 报 RPC 失败）。
  3. Run 判定 Aspen：Run2 返回 + 读流股出口温度确认确实冷凝/蒸发。
"""
import argparse
import os
import socket
import sys
import shutil

# EDR 空模板（几何骨架，物性/工艺由 Aspen 填充）
EDR_TEMPLATE_DIR = r"D:\software\anzhuang\Aspen Exchanger Design and Rating V15.0\Dat\Template"

# 环己烷-甲醇冷凝蒸发器 E-6102 默认工艺
DEFAULTS = {
    "hot_name": "CYCLO-01", "hot_formula": "C6H12-1",
    "cold_name": "METHA-01", "cold_formula": "CH4O",
    "hot_temp": 172.0, "hot_pres": 8.0, "hot_flow": 19440.0,  # kg/h 环己烷饱和蒸汽
    "cold_temp": 80.0, "cold_pres": 5.0, "cold_flow": 7200.0,  # kg/h 甲醇过冷液
    "vapfrac_cold": 0.70,  # 冷侧蒸发 70%
}


def build_inp(hot_name, hot_formula, cold_name, cold_formula, p, edr_filename):
    return f"""TITLE 'HeatX TASCPLUS-RIG -> EDR design'

IN-UNITS SI TEMP=C PRES=BAR MOLE-FLOW='KMOL/HR' MASS-FLOW='KG/HR' ENTHALPY-FLO='WATT'
OUT-UNITS SI TEMP=C PRES=BAR MOLE-FLOW='KMOL/HR' MASS-FLOW='KG/HR' ENTHALPY-FLO='WATT'

DEF-STREAMS CONVEN ALL

COMPONENTS
    {hot_name} {hot_formula} /
    {cold_name} {cold_formula}

PROPERTIES PENG-ROB

FLOWSHEET
    BLOCK B1 IN=S1 S2 OUT=S3 S4

STREAM S1
    SUBSTREAM MIXED TEMP={p['hot_temp']} PRES={p['hot_pres']} MASS-FLOW={p['hot_flow']}
    MASS-FRAC {hot_name} 1.0

STREAM S2
    SUBSTREAM MIXED TEMP={p['cold_temp']} PRES={p['cold_pres']} MASS-FLOW={p['cold_flow']}
    MASS-FRAC {cold_name} 1.0

BLOCK B1 HEATX
    PARAM VFRAC-COLD={p['vapfrac_cold']} CALC-TYPE=DESIGN CALC-METHOD=TASCPLUS-RIG
    HETRAN-PARAM INPUT-FILE="{edr_filename}"
    BJAC-INPUTS FOUL-OPTION=PROGRAM
    FEEDS HOT=S1 COLD=S2
    OUTLETS-HOT S3
    OUTLETS-COLD S4
    HOT-SIDE DP-OPTION=CONSTANT DPPARMOPT=NO
    COLD-SIDE DP-OPTION=CONSTANT DPPARMOPT=NO

STREAM-REPOR MOLEFLOW MASSFLOW
"""


def setup_license_env():
    h = os.environ.get("LSHOST", "").strip() or socket.gethostname()
    os.environ["LSHOST"] = h
    os.environ.setdefault("LSFORCEHOST", h)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aspen Plus -> EDR TASCPLUS-RIG 设计")
    ap.add_argument("--edr-template", default="CS_Fixed_Tubesheet_SI.EDT", help="EDR 空模板名")
    ap.add_argument("--edr-out", default="design.EDR")
    ap.add_argument("--apwz-out", default="design.apwz")
    ap.add_argument("--rep-out", default="design.rep")
    ap.add_argument("--workdir", default=os.getcwd())
    args = ap.parse_args(argv)

    setup_license_env()
    import win32com.client

    wd = os.path.abspath(args.workdir)
    os.makedirs(wd, exist_ok=True)
    edr_file = os.path.join(wd, args.edr_out)
    edr_tmpl = os.path.join(EDR_TEMPLATE_DIR, args.edr_template)
    if not os.path.exists(edr_tmpl):
        sys.exit(f"模板不存在: {edr_tmpl}")

    # 1. 预置 EDR 空模板（几何骨架）
    shutil.copy2(edr_tmpl, edr_file)
    print(f"[1] EDR 骨架: {edr_file}")

    # 2. 写 inp
    inp = os.path.join(wd, "_tascplus.inp")
    open(inp, 'w', encoding='ascii').write(
        build_inp(DEFAULTS["hot_name"], DEFAULTS["hot_formula"],
                  DEFAULTS["cold_name"], DEFAULTS["cold_formula"],
                  DEFAULTS, args.edr_out))
    print(f"[2] inp: {inp}")

    # 3. Aspen 打开 + 运行（DispatchEx 强制新实例，避免孤儿进程 RPC 失败）
    aspen = win32com.client.DispatchEx('Apwn.Document')
    try:
        aspen.InitFromFile2(inp, True)
        print("[3] InitFromFile2 OK")
        inc = aspen.Tree.FindNode(r"\Data").NextIncomplete("")
        print(f"[3] NextIncomplete = {inc}")
        aspen.Run2(False)
        print("[4] Run2 OK")

        # 读冷热流股出口（确认确实冷凝/蒸发）
        for s in ("S1", "S3", "S2", "S4"):
            t = aspen.Tree.FindNode(rf"\Data\Streams\{s}\Output\RES_TEMP").Value
            v = aspen.Tree.FindNode(rf"\Data\Streams\{s}\Output\RES_VFRAC").Value
            print(f"    {s}: T={t} VFRAC={v}")

        # 保存 Aspen 模型 + 导出 rep
        aspen.SaveAs2(os.path.join(wd, args.apwz_out), True)
        print(f"[5] Aspen 模型: {args.apwz_out}")
        try:
            aspen.Export(2, os.path.join(wd, args.rep_out))  # 2 = .rep
            print(f"[5] 报告: {args.rep_out}")
        except Exception as e:
            print(f"[5] rep 导出失败 {str(e)[:60]}")
    finally:
        try:
            aspen.Quit()
        except Exception:
            pass

    # 4. 读 EDR 设计结果（用 XML 解析，绝不 FileOpen——FileOpen 会把 Aspen 写的
    #    完整 EDR 回写成空壳，这是本 skill 最致命的坑之一）
    print("\n[6] EDR 设计结果:")
    import re
    s = open(edr_file, encoding='utf-8-sig', errors='replace').read()
    for nm in ["Area", "AreaRatioDirty", "HtLoadInit", "LMTD", "HeatTranRatDirty",
               "TubeNum", "TubeOD", "TubeLng", "ShlID", "BafNum"]:
        m = re.search(r'<scalar name="' + nm + r'">.*?<value>(.*?)</value>', s, re.S)
        print(f"    {nm} = {m.group(1).strip() if m else '读失败'}")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
