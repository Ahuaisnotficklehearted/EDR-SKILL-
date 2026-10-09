# -*- coding: utf-8 -*-
"""EDR 管壳式换热器设计桥 —— 从 Aspen Plus 物性/工艺 → EDR Design 模式跑设计。

已验证（2026-09-30，Aspen EDR V15 41.0.0.451）：
  1. EDR COM 全链路打通：FileOpen → 改标量 → 切 Design 模式 → Run → 读结果。
  2. 关键枚举（从 main_2014.db 挖出）：
     DBToBeUsed: 1=B-JAC, 2=Aspen Properties, 3=COMThermo, 4=User specified
     ApplType:   3=Phase Change（相变，蒸发/冷凝必设）
     VaporizerType: 1=Pool boiling, 2=Thermosiphon, 3=Forced circulation, 4=Falling film
     TascProgMode: 1=Design, 2=Rating, 3=Simulation
  3. 组分注入三大障碍（见 references/com-api-and-troubleshooting.md §3.8）：
     - COMThermo/BEX 缓存会锁定组分；CompSpc=1 会锁定组分规格；
     - FluidNam 纯组分名在无 GUI COM 下无法触发 B-Jac 库搜索（回退水 MW=18）。
     - 捷径：选官方示例里已用目标组分的模板，只改工艺不改组分；
       或走 ImportPFS（Aspen Plus PSF 导入）注入物性。

安全铁律（务必遵守）：
  1. 只操作副本（FileOpen 会回写文件，加载失败会把空壳写回）。
  2. 打开即校验已知标量（防空壳加载）。
  3. 退出统一 os._exit()（防 COM 析构回写）。
  4. Run 判定：rc==0 且 ErrorDescription=='Normal operation'（带句号）。

用法示例（用 KettleReboiler 模板做环己烷冷凝+甲醇蒸发设计）：
  python edr_design.py --template KettleReboiler_AKU.EDR \
    --fluid-cs METHANOL --fluid-hs CYCLOHEXANE \
    --temp-in-cs 80 --temp-in-hs 172 --vapfrc-out-cs 0.7 \
    --flra-cs 2.0 --pres-cs 5 --pres-hs 8 \
    --design --save out.EDR
"""
import argparse
import os
import shutil
import socket
import sys
import time

EXAMPLES = r"D:\software\anzhuang\Aspen Exchanger Design and Rating V15.0\Examples\Shell&Tube"

# 冷侧（CS，吸热侧）工艺默认值：环己烷-甲醇 E-6102
DEFAULTS = {
    "temp_in_cs": 80.0,       # 甲醇进口 80 C
    "temp_out_cs": 110.0,     # 甲醇出口 110 C（蒸发到 110）
    "vapfrc_out_cs": 0.7,     # 冷侧出口蒸发率 70%
    "vapfrc_in_cs": 0.0,
    "temp_in_hs": 172.0,      # 环己烷饱和蒸汽 172 C
    "vapfrc_in_hs": 1.0,      # 热侧进口饱和蒸汽
    "vapfrc_out_hs": 0.0,     # 热侧全冷凝
}


def setup_license_env():
    h = os.environ.get("LSHOST", "").strip() or socket.gethostname()
    os.environ["LSHOST"] = h
    os.environ.setdefault("LSFORCEHOST", h)


def c2f(c):
    return c * 9.0 / 5.0 + 32.0


def bar2psi(bar):
    return bar * 14.5038


def kgs2lbh(kgs):
    return kgs * 3600.0 * 2.20462


def set_scalar(sc, name, value):
    it = sc(name)
    old = it.Value
    it.Value = value
    return old


def main(argv=None):
    ap = argparse.ArgumentParser(description="EDR shell-and-tube design bridge")
    ap.add_argument("--template", required=True, help="官方示例文件名（如 KettleReboiler_AKU.EDR）")
    ap.add_argument("--fluid-cs", help="冷侧(吸热)流体名")
    ap.add_argument("--fluid-hs", help="热侧(放热)流体名")
    ap.add_argument("--flra-cs", type=float, help="冷侧流量 kg/s")
    ap.add_argument("--temp-in-cs", type=float, help="冷侧进口温度 C")
    ap.add_argument("--temp-out-cs", type=float, help="冷侧出口温度 C")
    ap.add_argument("--vapfrc-out-cs", type=float, help="冷侧出口蒸发率 0~1")
    ap.add_argument("--temp-in-hs", type=float, help="热侧进口温度 C")
    ap.add_argument("--pres-cs", type=float, help="冷侧操作压力 bar")
    ap.add_argument("--pres-hs", type=float, help="热侧操作压力 bar")
    ap.add_argument("--design", action="store_true", help="切换 Design 模式")
    ap.add_argument("--save", help="另存路径")
    ap.add_argument("--results", default="Area,AreaReqDirty,AreaRatioDirty,HtLoadInit,LMTD,HeatTranRatDirty",
                    help="逗号分隔的结果标量名")
    args = ap.parse_args(argv)

    setup_license_env()
    import win32com.client

    src = os.path.join(EXAMPLES, args.template)
    if not os.path.exists(src):
        sys.exit(f"模板不存在: {src}")

    workdir = os.path.dirname(os.path.abspath(args.save)) if args.save else os.getcwd()
    os.makedirs(workdir, exist_ok=True)
    work = os.path.join(workdir, "_edr_work_copy.EDR")
    shutil.copy2(src, work)

    bjac = win32com.client.Dispatch("BJACCOM2.BJACApp")
    app = doc = None
    try:
        bjac.FileOpen(work)
        app = bjac.GetAppObject(work, "Tasc")
        doc = bjac.GetDocument(work, False)
        sc = app.Scalars
        print(f"[open] {args.template}  Scalars={sc.Count}")

        # 组分（注意：受 COMThermo 缓存/CompSpc 锁定制约，见 skill §3.8）
        if args.fluid_cs:
            set_scalar(sc, "FluidNamCS", args.fluid_cs)
        if args.fluid_hs:
            set_scalar(sc, "FluidNamHS", args.fluid_hs)

        # 工艺（模板可能是英制，读 Uom 判断单位）
        def set_t(n, val_c, conv):
            it = sc(n)
            u = (it.Uom or "").lower()
            v = conv(val_c) if "f" in u or "psi" in u or "lb" in u else val_c
            it.Value = v
            print(f"[set] {n} = {v} [{it.Uom}]")

        if args.flra_cs is not None:
            it = sc("FlRaCS")
            if "lb" in (it.Uom or "").lower():
                it.Value = kgs2lbh(args.flra_cs)
            else:
                it.Value = args.flra_cs
        if args.temp_in_cs is not None:
            set_t("TempInCS", args.temp_in_cs, c2f)
        if args.temp_out_cs is not None:
            set_t("TempOutCS", args.temp_out_cs, c2f)
        if args.temp_in_hs is not None:
            set_t("TempInHS", args.temp_in_hs, c2f)
        if args.vapfrc_out_cs is not None:
            set_scalar(sc, "VapFrcOutCS", args.vapfrc_out_cs)
        if args.pres_cs is not None:
            set_t("PresOperInCS", args.pres_cs, bar2psi)
        if args.pres_hs is not None:
            set_t("PresOperInHS", args.pres_hs, bar2psi)
        set_scalar(sc, "VapFrcInCS", DEFAULTS["vapfrc_in_cs"])
        set_scalar(sc, "VapFrcInHS", DEFAULTS["vapfrc_in_hs"])
        set_scalar(sc, "VapFrcOutHS", DEFAULTS["vapfrc_out_hs"])

        if args.design:
            set_scalar(sc, "TascProgMode", 1)
            print("[mode] Design")

        print("[run] ...")
        rc = bjac.Run("Tasc")
        err = bjac.ErrorDescription
        ok = rc == 0 and str(err).strip().rstrip(".").lower() == "normal operation"
        print(f"[run] rc={rc} err={err!r} {'OK' if ok else 'FAILED'}")

        rs = app.ResultScalars
        for nm in [n.strip() for n in args.results.split(",") if n.strip()]:
            try:
                it = rs(nm)
                print(f"[result] {nm} = {it.Value} [{it.Uom}]")
            except Exception as e:
                print(f"[result] {nm} 读失败 {e!r}")

        if args.save and ok:
            doc.FileSaveAs(os.path.abspath(args.save))
            print(f"[save] {args.save}")
    finally:
        sys.stdout.flush()
        os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
