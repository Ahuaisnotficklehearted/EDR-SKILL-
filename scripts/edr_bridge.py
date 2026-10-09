"""Aspen EDR (Exchanger Design & Rating) COM 自动化桥接脚本。

已验证环境: Aspen EDR V15 (41.0.0.451)，ProgID BJACCOM2.BJACApp / BJACCOM2.Document。

安全设计（吸取 2026-09-29 E-6101 原文件被覆盖事故教训）:
  1. open 前自动做备份副本 <file>.bak-<时间戳>.EDR；
  2. 打开后若提供 --verify NAME=VALUE，先核对已知标量，不符则恢复备份并终止；
  3. run 后检查返回码 rc==0 且 ErrorDescription=='Normal operation'，否则报错；
  4. 结果只写入 --save 指定的新文件，绝不回写原路径。

用法示例:
  python edr_bridge.py --open case.EDR --verify ShlID=1900 --set TubeLng=6000 \
      --run --results Area,AreaReqClean,DutyCalc --save case_run1.EDR
"""
import argparse
import os
import shutil
import socket
import sys
import time

# 各换热器类型的 COM 程序名（从官方示例 XML 实测）
PROGRAM_NAMES = {
    "shell&tube": "Tasc", "tasc": "Tasc",
    "aircooled": "Acol", "acol": "Acol",
    "plate": "Aple", "aple": "Aple",
    "platefin": "PlateFin",
    "coilwound": "CoilWound",
    "firedheater": "Fire", "fire": "Fire",
    "ensea": "Ensea",
}


def setup_license_env():
    h = os.environ.get("LSHOST", "").strip() or socket.gethostname()
    os.environ["LSHOST"] = h
    os.environ.setdefault("LSFORCEHOST", h)


def connect():
    import win32com.client
    return win32com.client.Dispatch("BJACCOM2.BJACApp")


def open_case(bjac, path, appname):
    """打开案例（自动备份）并返回 (app, doc)。"""
    backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}.EDR"
    shutil.copy2(path, backup)
    print(f"[backup] {backup}")
    ok = bjac.FileOpen(path)
    if not ok:
        raise RuntimeError(f"FileOpen 返回 {ok}")
    app = bjac.GetAppObject(os.path.abspath(path), appname)
    doc = bjac.GetDocument(os.path.abspath(path), False)
    return app, doc, backup


def verify_case(app, checks, tol=1e-4):
    """打开后核对已知标量，防止'空壳加载'。checks: [(name, value)]"""
    sc = app.Scalars
    bad = []
    for name, expect in checks:
        try:
            got = float(sc(name).Value)
        except Exception as e:
            bad.append(f"{name}: 读取失败 {e!r}")
            continue
        if abs(got - float(expect)) > tol * max(1.0, abs(float(expect))):
            bad.append(f"{name}: 期望 {expect} 实际 {got}")
    return bad


def run_case(bjac, doc, appname):
    rc = bjac.Run(appname)
    err = bjac.ErrorDescription
    ok = (rc == 0 and str(err).strip().rstrip(".").lower() == "normal operation")
    return rc, err, ok


def get_results(app, names):
    rs = app.ResultScalars
    out = {}
    for n in names:
        try:
            it = rs(n)
            out[n] = (it.Value, it.Uom)
        except Exception as e:
            out[n] = (f"ERR:{e!r}", "")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aspen EDR COM bridge")
    ap.add_argument("--open", required=True, help="EDR 文件（将自动备份；建议先手动复制工作副本）")
    ap.add_argument("--app", default="Tasc", help="程序名: Tasc/Acol/Aple/PlateFin/CoilWound/Fire 或类型名")
    ap.add_argument("--verify", action="append", default=[], metavar="NAME=VALUE",
                    help="打开后核对输入标量（防空壳加载），可多次")
    ap.add_argument("--set", dest="sets", action="append", default=[], metavar="NAME=VALUE",
                    help="写输入标量，可多次")
    ap.add_argument("--run", action="store_true", help="运行计算")
    ap.add_argument("--results", default="", help="逗号分隔的结果变量名")
    ap.add_argument("--save", default="", help="另存为新文件（不回写原路径）")
    args = ap.parse_args(argv)

    setup_license_env()
    appname = PROGRAM_NAMES.get(args.app.lower().strip(), args.app)
    path = os.path.abspath(args.open)

    bjac = connect()
    app, doc, backup = open_case(bjac, path, appname)
    print(f"[open] {path}  app={appname}  Scalars={app.Scalars.Count} "
          f"ResultScalars={app.ResultScalars.Count}")

    if args.verify:
        checks = []
        for v in args.verify:
            n, _, val = v.partition("=")
            checks.append((n.strip(), float(val)))
        bad = verify_case(app, checks)
        if bad:
            print("[verify] 失败！疑似空壳加载：", "; ".join(bad))
            # 恢复备份后用 os._exit 绕过 COM 析构——析构会把内存空文档回写文件！
            shutil.copy2(backup, path)
            print(f"[restore] 已从备份恢复 {path}（os._exit 防止析构回写）")
            sys.stdout.flush()
            os._exit(2)
        print("[verify] 通过")

    for v in args.sets:
        n, _, val = v.partition("=")
        it = app.Scalars(n.strip())
        old = it.Value
        it.Value = float(val)
        print(f"[set] {n}: {old} -> {it.Value} [{it.Uom}]")

    if args.run:
        rc, err, ok = run_case(bjac, doc, appname)
        print(f"[run] rc={rc} err={err!r} {'OK' if ok else 'FAILED'}")
        if not ok:
            return 3

    if args.results:
        names = [n.strip() for n in args.results.split(",") if n.strip()]
        for n, (v, u) in get_results(app, names).items():
            print(f"[result] {n} = {v} [{u}]")

    if args.save:
        ok2 = doc.FileSaveAs(os.path.abspath(args.save))
        print(f"[save] {args.save} -> {ok2}")

    sys.stdout.flush()
    # 用 os._exit 结束：避免 COM 析构把内存文档回写文件（实测会覆盖！）
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
