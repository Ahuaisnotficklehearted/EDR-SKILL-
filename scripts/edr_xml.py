"""EDR 文件 (XML) 解析器 —— 只读解析，不依赖 COM，用于校核/提取/审计。

安全定位：本脚本绝不写文件，只读 .EDR 的 XML 结构，是"打开即校验"铁律的
文件侧实现（配合 edr_bridge.py 的 COM 侧校验）。可作为事故后审计的只读工具。

用法:
  python edr_xml.py dump <file.EDR>                 # 打印全部输入/结果标量与数组概要
  python edr_xml.py scalars <file.EDR>              # 只打印输入标量  name=value[uom]
  python edr_xml.py results <file.EDR>              # 只打印结果标量
  python edr_xml.py arrays <file.EDR>               # 只打印数组概要（名称+尺寸）
  python edr_xml.py find <file.EDR> <name>          # 按名查找标量/数组

.EDR 结构约定（V15 实测）:
  <HTEdata FileSignature="AspenTech/EDR V15 (41.0.0.451)" ...>
    <application name="Tasc">      # Tasc/Acol/Aple/PlateFin/CoilWound/Fire/Ensea
      <match>false</match>
      <result>101</result>         # 运行状态码: 0/正常? 101=未运行?（见 run 判定）
      <uomset>8</uomset>
      <scalars>   # 输入标量: <scalar name=..><uom/><value>..</value><source>User|Result</source>
      <arrays>    # 输入数组
      <scalars>   # 结果标量（第二个 scalars 块）
      <arrays>    # 结果数组（第二个 arrays 块）
      <objects>   # 设备/工艺对象（几何结构、物料成分等）
"""
import sys
import xml.etree.ElementTree as ET


def _text(el):
    """取 <value> 子元素文本；无则回退属性 value。"""
    if el is None:
        return None
    v = el.find("value")
    if v is not None and v.text is not None:
        return v.text.strip()
    return (el.get("value") or "").strip()


def _uom(el):
    if el is None:
        return ""
    u = el.find("uom")
    return (u.text or "").strip() if u is not None and u.text else ""


def load(path):
    return ET.parse(path).getroot()


def application(root):
    return root.find("application")


def input_scalars(app):
    blocks = app.findall("scalars")
    # 第一个 scalars 块是输入，第二个是结果（实测顺序固定）
    out = []
    for s in blocks[0].findall("scalar"):
        out.append((s.get("name"), _text(s), _uom(s)))
    return out


def result_scalars(app):
    blocks = app.findall("scalars")
    out = []
    if len(blocks) >= 2:
        for s in blocks[1].findall("scalar"):
            out.append((s.get("name"), _text(s), _uom(s)))
    return out


def _array_summary(blocks):
    out = []
    for b in blocks:
        for a in b.findall("array"):
            name = a.get("name")
            rows = a.findall("row")
            # 每行可能带 index，首行列数代表列数
            ncols = 0
            for r in rows:
                cols = r.findall("col")
                ncols = max(ncols, len(cols))
            out.append((name, len(rows), ncols))
    return out


def input_arrays(app):
    blocks = app.findall("arrays")
    return _array_summary([blocks[0]]) if blocks else []


def result_arrays(app):
    blocks = app.findall("arrays")
    return _array_summary([blocks[1]]) if len(blocks) >= 2 else []


def find(app, name):
    for kind, func in (("input scalar", input_scalars),
                       ("result scalar", result_scalars)):
        for n, v, u in func(app):
            if n.lower() == name.lower():
                return kind, n, v, u
    for kind, func in (("input array", input_arrays),
                       ("result array", result_arrays)):
        for n, r, c in func(app):
            if n.lower() == name.lower():
                return kind, n, f"{r}rows x {c}cols", ""
    return None


def _show_scalars(app, which):
    func = input_scalars if which == "in" else result_scalars
    for n, v, u in func(app):
        print(f"{n:28s} = {v:16s} [{u}]")


def _show_arrays(app, which):
    func = input_arrays if which == "in" else result_arrays
    for n, r, c in func(app):
        print(f"{n:32s}  {r:3d} rows x {c:2d} cols")


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, path = argv[0], argv[1]
    root = load(path)
    app = application(root)
    print(f"[file] {path}")
    print(f"[app]  {app.get('name')}  result_code={_text(app.find('result'))}")
    if cmd == "dump":
        print("\n--- INPUT SCALARS ---")
        _show_scalars(app, "in")
        print("\n--- INPUT ARRAYS ---")
        _show_arrays(app, "in")
        print("\n--- RESULT SCALARS ---")
        _show_scalars(app, "out")
        print("\n--- RESULT ARRAYS ---")
        _show_arrays(app, "out")
    elif cmd == "scalars":
        _show_scalars(app, "in")
    elif cmd == "results":
        _show_scalars(app, "out")
    elif cmd == "arrays":
        _show_arrays(app, "in")
        print("--- result arrays ---")
        _show_arrays(app, "out")
    elif cmd == "find":
        if len(argv) < 3:
            print("find 需要 <name>")
            return 1
        r = find(app, argv[2])
        print(r if r else f"未找到 {argv[2]}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
