#!/usr/bin/env python3
"""Minecraft Build Studio command line.

  python3 studio.py palette            validate blocks/palette.py, write blocks/palette.json
  python3 studio.py new <name>         scaffold builds/<name>/build.py and add it to the world
  python3 studio.py plan <name>        area plan map only (catch collisions before building)
  python3 studio.py build <name>|--all generate, check, export .mcpack, report, viewer data
  python3 studio.py world              compile world/world.json for the viewer + world plan
  python3 studio.py serve [--port N]   viewer + dev server (auto rebuild, live reload)
  python3 studio.py html <name>        single self-contained HTML viewer for sharing
  python3 studio.py shoot <name>       headless screenshots into out/<name>/shots/
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib import build as B  # noqa: E402
from lib.palette import FACINGS, validate_palette, write_json  # noqa: E402

OUT = ROOT / "out"


def cmd_palette(_a=None):
    errs = validate_palette()
    p = write_json()
    if errs:
        print("\n".join(errs))
        print(f"palette: {len(errs)} problems")
        return 1
    print(f"palette ok ({p.relative_to(ROOT)})")
    return 0


def compile_build(name, quiet=False):
    from export.checks import counts, full_validation
    from export.pack import config, install_steps, write_pack
    from export.plan import build_plan, icon

    t0 = time.time()
    write_json()
    b = B.load(name)
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    checks, sets = full_validation(b)
    cnt = counts(b)
    if b.target:
        lo, hi = int(b.target * 0.85), int(b.target * 1.15)
        ok = lo <= cnt["total"] <= hi
        checks.append(dict(level="ok" if ok else "warn", check="target", where=None,
                           msg=f"{cnt['total']} blocks vs target {b.target} ({cnt['total'] - b.target:+d}, "
                               f"{100 * (cnt['total'] - b.target) / b.target:+.0f}%)"))
    build_plan(b, out / "plan_areas.png", checks=checks)
    build_plan(b, out / "plan_top.png", top_view=True, checks=checks)
    icon(b, out / "pack_icon.png")
    mcpack, ver = write_pack(b, sets, out, out / "pack_icon.png")

    # viewer data
    variants, vix, flat = [], {}, []
    for (x, y, z), c in sorted(b.model.cells.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        k = (c.key, json.dumps(c.props, sort_keys=True))
        if k not in vix:
            vix[k] = len(variants)
            variants.append([c.key, c.props])
        flat += [x, y, z, vix[k], b.model.steps.index(c.step), c.group or 0]
    wj = _world()
    world_entry = next((dict(e) for e in wj.get("builds", []) if e["name"] == name), None)
    if world_entry is not None:
        world_entry.setdefault("facing", "north")
        world_entry["grade"] = wj.get("terrain", {}).get("grade", 64)
    data = dict(
        name=b.name, title=b.title, description=b.description, footprint=list(b.footprint),
        marker=list(b.marker), target=b.target, steps=b.steps, keep_zones=b.keep_zones, areas=b.areas,
        floors=b.model.floors, markers=list(b.model.markers.values()), variants=variants, cells=flat,
        counts=cnt, checks=checks, edits=b.edit_log, book=b.book, grades=b.grades,
        height=max([y for (_, y, _), c in b.model.cells.items() if c.key != "air"] + [0]) + 1, pack_version=".".join(map(str, ver)),
        mcpack=str(mcpack.relative_to(ROOT)), world=world_entry,
        commands={f: dict(files=sets[f][0], run_order=sets[f][1]["run_order"],
                          total=sets[f][1]["total"]) for f in FACINGS},
        install=install_steps(config()), config=config(), built=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    (out / "model.json").write_text(json.dumps(data, separators=(",", ":")))
    (out / "report.md").write_text(report(b, cnt, checks, ver, mcpack))
    errs = [c for c in checks if c["level"] == "error"]
    warns = [c for c in checks if c["level"] == "warn"]
    if not quiet:
        print(f"{name}: {cnt['total']} blocks (target {b.target}), {len(errs)} errors, {len(warns)} warnings, "
              f"pack v{'.'.join(map(str, ver))} -> {mcpack.relative_to(ROOT)}  [{time.time() - t0:.1f}s]")
        for c in errs + warns:
            print(f"  {c['level'].upper():5} {c['check']}: {c['msg']}" +
                  (f"  e.g. {c['where'][:3]}" if c.get("where") else ""))
    return len(errs)


def report(b, cnt, checks, ver, mcpack):
    L = [f"# {b.title}", "", f"Pack `{mcpack.name}` v{'.'.join(map(str, ver))}. "
         f"Footprint {b.footprint[0]}x{b.footprint[1]}, marker {list(b.marker)}.", ""]
    L += ["## Blocks per step", "", "| # | Step | Blocks |", "|---|---|---|"]
    for i, s in enumerate(b.steps, 1):
        L.append(f"| {i} | {s['title']} | {cnt['by_step'][s['key']]} |")
    pct = f" ({100 * (cnt['total'] - b.target) / b.target:+.0f}% vs target {b.target})" if b.target else ""
    L += [f"| | **Total** | **{cnt['total']}**{pct} |", "",
          f"Hidden below-grade fill not counted: {cnt['hidden']}.", "", "## Inventory (items)", ""]
    L += [f"- {k}: {n}" + (f" ({n // 64} stacks + {n % 64})" if n >= 64 else "") for k, n in
          sorted(cnt["items"].items(), key=lambda kv: -kv[1])]
    L += ["", "## Checks", ""]
    for c in checks:
        L.append(f"- **{c['level']}** `{c['check']}` {c['msg']}")
    return "\n".join(L) + "\n"


def _world():
    p = ROOT / "world" / "world.json"
    return json.loads(p.read_text()) if p.exists() else {"builds": []}


def cmd_build(a):
    names = B.names() if a.all or not a.name else [a.name]
    bad = 0
    for n in names:
        bad += compile_build(n)
    cmd_world(None)
    return 1 if bad else 0


def cmd_world(_a):
    from export.plan import world_plan
    from lib.world import compile_world
    w = compile_world()
    OUT.mkdir(exist_ok=True)
    (OUT / "world.json").write_text(json.dumps(w, separators=(",", ":")))
    world_plan(w, OUT / "world_plan.png")
    for p in w["problems"]:
        print("  WORLD", p["msg"])
    print(f"world: {len(w['builds'])} builds -> out/world.json, out/world_plan.png")
    return 1 if w["problems"] else 0


def cmd_plan(a):
    from export.checks import run_checks
    from export.plan import build_plan
    b = B.load(a.name)
    out = OUT / a.name
    out.mkdir(parents=True, exist_ok=True)
    checks = [c for c in run_checks(b) if c["check"] in ("areas", "footprint", "keep-zone")]
    p = build_plan(b, out / "plan_areas.png", checks=checks)
    for c in checks:
        print(f"  {c['level'].upper()} {c['msg']}")
    print(f"plan -> {p.relative_to(ROOT)}")
    return 0


TEMPLATE = '''"""{title}: one-line description of the build."""
from lib import *

TITLE = "{title}"
FOOTPRINT = (20, 20)          # x (east) by z (south), cells 0..W-1 / 0..D-1; front faces north
MARKER = (0, 0, -2)           # where you stand to run the functions (local coords)
TARGET_BLOCKS = 1000
STEPS = [
    ("foundation", "Foundation", "Plinth and ground floor"),
    ("walls", "Walls", "Frame and walls"),
    ("roof", "Roof", "Roof and chimney"),
    ("details", "Details", "Lighting, furniture, garden"),
]
KEEP_ZONES = [
    # dict(box=(x1, z1, x2, z2), what="water", depth=2, note="existing pond"),
]
AREAS = [
    dict(key="main", title="Main building", box=(2, 2, 17, 17), desc="What happens here"),
]


def build(m):
    with m.step("foundation"):
        m.box(2, 0, 2, 17, 0, 17, "cobblestone")
'''


def cmd_new(a):
    d = ROOT / "builds" / a.name
    if (d / "build.py").exists():
        print(f"builds/{a.name}/build.py already exists")
        return 1
    d.mkdir(parents=True)
    (d / "build.py").write_text(TEMPLATE.format(title=a.name.replace("_", " ").title()))
    w = _world()
    if not any(e["name"] == a.name for e in w["builds"]):
        w["builds"].append(dict(name=a.name, pos=[0, 0], facing="north"))
        (ROOT / "world" / "world.json").write_text(json.dumps(w, indent=2) + "\n")
    print(f"created builds/{a.name}/build.py (set its position in world/world.json)")
    return 0


def cmd_serve(a):
    from viewer.server import serve
    serve(a.port)


def cmd_html(a):
    from viewer.static import export_html
    for n in (B.names() if a.name == "--all" else [a.name]):
        if not (OUT / n / "model.json").exists():
            compile_build(n)
        p = export_html(n)
        print(f"static viewer -> {p.relative_to(ROOT)}")
    return 0


def cmd_shoot(a):
    return subprocess.call(["node", str(ROOT / "viewer" / "tools" / "shoot.js"), a.name] + (a.views or []))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("palette").set_defaults(fn=cmd_palette)
    p = sub.add_parser("new")
    p.add_argument("name")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("plan")
    p.add_argument("name")
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser("build")
    p.add_argument("name", nargs="?")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_build)
    sub.add_parser("world").set_defaults(fn=cmd_world)
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=None)
    p.set_defaults(fn=cmd_serve)
    p = sub.add_parser("html")
    p.add_argument("name")
    p.set_defaults(fn=cmd_html)
    p = sub.add_parser("shoot")
    p.add_argument("name")
    p.add_argument("views", nargs="*")
    p.set_defaults(fn=cmd_shoot)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
