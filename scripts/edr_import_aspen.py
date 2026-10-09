# -*- coding: utf-8 -*-
"""Aspen Plus -> EDR 物性导入桥（本轮 2026-09-30 逆向成果固化）。

解决的核心问题：
  EDR 冷/热侧物性（组分 + 热力学方法 + 物性曲线）独立于输入标量，通过
  BEX/COMThermo 导入。多组分 + 相变体系若直接在 EDR 手工填物性，极易缺
  流股参数。正确做法是用 Aspen Plus 跑完流程（流股 T/P/VFRAC/组成/焓完整
  自洽），再把物性导入 EDR。

逆向成果（makepy 类型库 ATVInterfacesVB.tlb 实测）：
  app.SetAspenAppContext(objAspenApp, fNameAspenApp, vaporizerType='')
      -- 把运行中的 Aspen Plus COM 实例 + 文件名绑定到 EDR 上下文。
  app.ImportPSF(psfMode:int)
      -- 触发物性导入。psfMode=2 才触发真正的 PSF 拉取（内部调 GetPSF）；
         0/1/3/4/5/6 静默成功但组分不变（仍是模板默认值）。

关键限制（务必知道）：
  ImportPSF(2) 内部调 PSFImport.dll 的 GetPSF，GetPSF 需要 Aspen Plus 侧的
  EDR 桥（Engine/Xeq/zetasc.dll，原生代码）激活，该桥只在 Aspen Plus GUI
  「HeatX 块 -> Send to Aspen EDR」集成模式下工作；Apwn.Document 纯 COM
  无 GUI 打开时桥不激活 -> ImportPSF(2) 报「重载决策失败 GetPSF」。

因此两条落地路径：
  路径 A（推荐，纯 COM 可行）：Aspen 算完 -> 读流股物性 -> 写 EDR 固化数组
      （DBToBeUsed=4 User specified + CompMolecularWeight/LiquidDensity 等），
      物性数据来源仍是 Aspen，保证准确，且自包含可交付。
  路径 B（需 GUI）：Aspen Plus GUI 里 HeatX 块绑 MODE=TASCPLUS-RIG +
      HETRAN-PARAM INPUT-FILE=*.EDR，运行时 Aspen 主动调 EDR 引擎（对标官方
      EDR-ShellTube.apwz）。纯 COM 需人工在 GUI 点一次绑定。

官方示例（Aspen Plus V15.0\\GUI\\Examples\\EDR\\EDR-ShellTube.apwz）物性形态：
  DBToBeUsedCS/HS=4 (User specified) + CompSpcCS/HS=1 + BEXFilename(临时.BEX)
  + 固化的物性数组：CompMolecularWeight / CompCriticalTemperature /
  LiquidDensity / LiquidViscosity / Comp01LiqMoleFrc~Comp14...（14 组分烃类）。

安全铁律（沿用 edr_bridge.py）：
  1. 只操作副本（FileOpen 会回写，加载失败会把空壳写回）。
  2. 打开即校验已知标量。
  3. EDR 退出统一 os._exit()（防 COM 析构回写）；Aspen 侧用 Quit() 正常关。
"""
import argparse
import os
import socket
import sys
import shutil
import time

EXAMPLES = r"D:\software\anzhuang\Aspen Exchanger Design and Rating V15.0\Examples\Shell&Tube"


def setup_license_env():
    h = os.environ.get("LSHOST", "").strip() or socket.gethostname()
    os.environ["LSHOST"] = h
    os.environ.setdefault("LSFORCEHOST", h)


def read_aspen_stream(app, stream, prop):
    """读 Aspen Plus 流股输出物性。返回 (value, unit)。"""
    n = app.Tree.FindNode(rf"\Data\Streams\{stream}\Output\{prop}")
    if n is None:
        return None, None
    return n.Value, n.UnitString


def read_aspen_streams(app, streams=("S1", "S2", "S3", "S4")):
    """读 Aspen 冷热侧流股完整物性（温度/压力/相分率/分子量/密度/粘度/比热/导热/焓/表面张力）。"""
    props = ("RES_TEMP", "RES_PRES", "RES_VFRAC", "RES_MW", "RES_RHO",
             "RES_MU", "RES_CP", "RES_KMX", "RES_HMX", "RES_SIGMA")
    out = {}
    for s in streams:
        row = {}
        for p in props:
            try:
                v, u = read_aspen_stream(app, s, p)
                row[p] = (v, u)
            except Exception:
                row[p] = (None, None)
        out[s] = row
    return out


def try_import_psf(app, aspen, aspen_file):
    """尝试 SetAspenAppContext + ImportPSF 全链路，返回诊断信息。

    返回 dict：{phase, error}，phase 指示断在哪一步。
    实测：SetAspenAppContext 恒成功；ImportPSF(2) 在纯 COM 下报 GetPSF 失败。
    """
    import win32com.client
    diag = {}
    try:
        app.SetAspenAppContext(aspen, aspen_file, "")
        diag["SetAspenAppContext"] = "OK"
    except Exception as e:
        diag["SetAspenAppContext"] = f"ERR {e}"
        return diag

    # psfMode=2 是唯一触发真正拉取的（实测 0/1/3/4/5/6 静默成功无效果）
    try:
        app.ImportPSF(2)
        diag["ImportPSF(2)"] = "OK"
    except Exception as e:
        diag["ImportPSF(2)"] = f"ERR {str(e)[:200]}"
    return diag


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aspen Plus -> EDR 物性导入桥")
    ap.add_argument("--aspen", required=True, help="Aspen Plus 模型 .bkp/.apwz（含已跑通的 HeatX 块）")
    ap.add_argument("--template", default="ForcedVaporizer_BEM.EDR",
                    help="EDR 模板（官方示例名）")
    ap.add_argument("--read-streams", action="store_true",
                    help="读取 Aspen 冷热侧流股物性并打印（路径 A 的数据来源）")
    ap.add_argument("--try-import", action="store_true",
                    help="尝试 SetAspenAppContext + ImportPSF(2)（路径 B，纯 COM 有缺口）")
    args = ap.parse_args(argv)

    setup_license_env()
    import win32com.client

    # --- Aspen 侧 ---
    aspen = win32com.client.Dispatch("Apwn.Document")
    try:
        aspen.InitFromFile2(os.path.abspath(args.aspen), True)
        if args.read_streams or args.try_import:
            aspen.Run2(False)
            print("[aspen] Run2 OK")

        if args.read_streams:
            print("\n=== Aspen 流股物性（路径 A 固化数据来源）===")
            data = read_aspen_streams(aspen)
            for s, row in data.items():
                t = row.get("RES_TEMP", (None, None))[0]
                v = row.get("RES_VFRAC", (None, None))[0]
                mw = row.get("RES_MW", (None, None))[0]
                rho = row.get("RES_RHO", (None, None))[0]
                cp = row.get("RES_CP", (None, None))[0]
                print(f"  {s}: T={t} VFRAC={v} MW={mw} rho={rho} Cp={cp}")

        # --- EDR 侧 ---
        if args.try_import:
            src = os.path.join(EXAMPLES, args.template)
            work = os.path.join(os.getcwd(), "_aspen_import.EDR")
            shutil.copy2(src, work)
            bjac = win32com.client.Dispatch("BJACCOM2.BJACApp")
            bjac.FileOpen(work)
            app = bjac.GetAppObject(work, "Tasc")
            sc = app.Scalars
            print(f"\n=== EDR {args.template} ===")
            print("  导入前 FluidNamCS/HS =",
                  sc("FluidNamCS").Value, sc("FluidNamHS").Value)
            diag = try_import_psf(app, aspen, os.path.abspath(args.aspen))
            print("  诊断:", diag)
            print("  导入后 FluidNamCS/HS =",
                  sc("FluidNamCS").Value, sc("FluidNamHS").Value)
            sys.stdout.flush()
            os._exit(0)  # EDR 侧必须 os._exit，防析构回写
    finally:
        try:
            aspen.Quit()  # Aspen 侧正常关闭
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
