# -*- coding: utf-8 -*-
"""EDR 换热器规范符合性优化（Design 结果 → Rating 加余量 → 规范校核）。

为什么需要它：Design 模式（TascProgMode=1）EDR 自动定几何，**面积余量恒≈0**
（实测 0.8%），不满足 30~50% 规范。且 Design 不设污垢。本脚本把 Design 基准
转为 Rating 校核：设污垢 + 取标准规格几何 + 寻优至余量达标。

流程（★ 关键：Aspen 不写回 EDR 结果段，必须用 EDR COM 跑）：
  Aspen TASCPLUS-RIG 推物性 → 复制副本 → EDR COM FileOpen 副本
  → 设污垢(FoulResCS/HS) + 改几何(ShlID/TubeLng/TubeNum) + TascProgMode=2
  → Run → 读结果校核（余量/流速/压降/长径比）

用法：
  python edr_spec_optimize.py --src base.EDR --cases "387,4500,160" "438,4500,190"
       [--foul 0.0001] [--workdir _opt]

规范目标（见 references/edr-design-spec-compliance.md）：
  污垢 >0、面积余量 30~50%、管侧气速 ≤30 m/s、压降 ≤允许、长径比 3~15、标准规格
"""
import argparse
import json
import os
import shutil
import socket
import sys

# TEMA 标准壳径(mm) 与 标准管长(mm)
STD_SHELL = {152: '6"', 203: '8"', 254: '10"', 305: '12"', 337: '14"',
             387: '16"', 438: '18"', 489: '20"'}
STD_TUBELNG = [1500, 2000, 3000, 4500, 6000, 9000]


def setup_license_env():
    h = os.environ.get("LSHOST", "").strip() or socket.gethostname()
    os.environ["LSHOST"] = h
    os.environ.setdefault("LSFORCEHOST", h)


def run_case(src, name, shl_id, tube_lng, tube_num, foul, wd):
    """跑一个几何方案：副本 → 设污垢/几何/Rating → Run → 读结果。"""
    import win32com.client
    work = os.path.join(wd, f"{name}.EDR")
    shutil.copy2(src, work)  # ★ 只操作副本（FileOpen 会回写）

    bjac = win32com.client.Dispatch("BJACCOM2.BJACApp")
    bjac.FileOpen(work)
    app = bjac.GetAppObject(work, "Tasc")
    sc = app.Scalars
    print(f"\n===== {name}: 壳{shl_id} 长{tube_lng} 管{tube_num} 污垢{foul} =====")

    def setv(nm, v, quiet=True):
        try:
            it = sc(nm)
            if it is None:
                return False
            it.Value = v
            return True
        except Exception as e:
            if not quiet:
                print(f"  设置 {nm} 失败 {str(e)[:60]}")
            return False

    # 污垢：★ 必须用 CS/HS（冷侧/热侧），不是 SS/TS
    setv('FoulResCS', foul)
    setv('FoulResHS', foul)
    # 几何 + Rating 模式
    setv('ShlID', shl_id)
    setv('TubeLng', tube_lng)
    setv('TubeNum', tube_num)
    setv('TascProgMode', 2)

    rc = bjac.Run("Tasc")
    err = bjac.ErrorDescription
    ok = rc == 0 and str(err).strip().rstrip(".").lower() == "normal operation"
    rrs = app.ResultScalars

    def g(nm):
        try:
            return rrs(nm).Value
        except Exception:
            return None

    ratio = g('AreaRatioDirty')
    margin = round((ratio - 1) * 100, 1) if ratio else None
    out = dict(name=name, ok=ok, ShlID=shl_id, TubeLng=tube_lng, TubeNum=tube_num,
               foul=foul, Area=g('Area'), AreaReq=g('AreaReqDirty'), margin_pct=margin,
               U_clean=g('HeatTranRatClean'), U_dirty=g('HeatTranRatDirty'),
               Q=g('HtLoadInit'), LMTD=g('LMTD'),
               dpSS=g('PresDropCalcSS'), dpSS_allo=g('PresDropAlloSS'),
               dpTS=g('PresDropCalcTS'), dpTS_allo=g('PresDropAlloTS'),
               velSS=g('VelCrossFlowMaxSS'), velTS_out=g('VelExitBundleTS'),
               velTS_in=g('VelEntBundleTS'))
    print(f"  Run {'OK' if ok else 'FAILED'}  面积 {out['Area']} / 所需 {out['AreaReq']}  余量={margin}%")
    print(f"  U clean={out['U_clean']} dirty={out['U_dirty']}  Q={out['Q']} LMTD={out['LMTD']}")
    print(f"  压降 壳={out['dpSS']}/{out['dpSS_allo']} 管={out['dpTS']}/{out['dpTS_allo']}")
    print(f"  流速 壳={out['velSS']} 管出={out['velTS_out']} 管入={out['velTS_in']}")
    sys.stdout.flush()
    return out


def judge(r):
    """规范验收判定。"""
    checks = {}
    m = r.get('margin_pct')
    checks['余量30~50%'] = (m is not None and 30 <= m <= 50)
    v = r.get('velTS_out')
    checks['管侧气速<=30'] = (v is None or v <= 30)
    d, da = r.get('dpTS'), r.get('dpTS_allo')
    checks['管压降<=允许'] = (d is None or da is None or d <= da)
    ds, dsa = r.get('dpSS'), r.get('dpSS_allo')
    checks['壳压降<=允许'] = (ds is None or dsa is None or ds <= dsa)
    uc, ud = r.get('U_clean'), r.get('U_dirty')
    checks['污垢生效'] = (uc is None or ud is None or ud < uc)
    lng, shl = r.get('TubeLng'), r.get('ShlID')
    checks['长径比3~15'] = (lng and shl and 3 <= lng / shl <= 15)
    checks['壳径标准'] = (shl in STD_SHELL)
    checks['管长标准'] = (lng in STD_TUBELNG)
    return checks


def main(argv=None):
    ap = argparse.ArgumentParser(description="EDR 规范符合性优化")
    ap.add_argument("--src", required=True, help="基准 .EDR（已含物性，通常来自 TASCPLUS-RIG）")
    ap.add_argument("--cases", nargs="+", required=True,
                    metavar="SHELL,LNG,NUM", help="候选几何，如 387,4500,160")
    ap.add_argument("--foul", type=float, default=0.0001, help="污垢热阻（每侧）m2*K/W")
    ap.add_argument("--workdir", default="_spec_opt")
    args = ap.parse_args(argv)

    setup_license_env()
    wd = os.path.abspath(args.workdir)
    os.makedirs(wd, exist_ok=True)

    results = []
    for i, c in enumerate(args.cases):
        try:
            shl, lng, num = [float(x) for x in c.split(",")]
            nm = f"C{i+1}_{int(shl)}_{int(lng)}_{int(num)}"
            results.append(run_case(args.src, nm, shl, lng, num, args.foul, wd))
        except Exception as e:
            print(f"  方案 {c} 异常: {str(e)[:150]}")

    json.dump(results, open(os.path.join(wd, "results.json"), "w"), indent=2, default=str)

    print("\n=== 规范验收汇总 ===")
    passed = []
    for r in results:
        ch = judge(r)
        bad = [k for k, v in ch.items() if not v]
        tag = "PASS ✅" if not bad else "NG: " + ",".join(bad)
        print(f"  {r['name']}: 余量{r.get('margin_pct')}% 面积{r['Area']} "
              f"管出速{r['velTS_out']} → {tag}")
        if not bad:
            passed.append(r)
    if passed:
        # 取余量最接近 20%（规范中值）者为最优
        best = min(passed, key=lambda r: abs((r.get('margin_pct') or 0) - 20))
        print(f"\n推荐最优: {best['name']}  余量{best['margin_pct']}%  面积{best['Area']} m²")
        print(f"  几何: 壳{best['ShlID']}mm({STD_SHELL.get(int(best['ShlID']), '?')}) "
              f"管长{best['TubeLng']}mm 管数{best['TubeNum']}")
    else:
        print("\n无方案全部达标，需扩大搜索范围（调整壳径/管长/管数组合）。")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
