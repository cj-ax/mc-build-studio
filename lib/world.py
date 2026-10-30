"""The shared world: terrain + every build placed at its position and facing."""
import json
from pathlib import Path

from lib.build import load
from lib.palette import FACINGS, rotate_pos, rotate_props

ROOT = Path(__file__).resolve().parent.parent
WORLD = ROOT / "world" / "world.json"


def read():
    return json.loads(WORLD.read_text())


def write(data):
    WORLD.write_text(json.dumps(data, indent=2) + "\n")


def placement(world, entry):
    t = world["terrain"]
    x, z = entry["pos"]
    y = entry.get("y", t["grade"] + 1)
    return (x, y, z), entry.get("facing", "north")


def place_rect(b, origin, facing, x1, z1, x2, z2):
    t = FACINGS.index(facing)
    mx, _, mz = b.marker
    ax, az = rotate_pos(x1 - mx, z1 - mz, t)
    bx, bz = rotate_pos(x2 - mx, z2 - mz, t)
    return [origin[0] + min(ax, bx), origin[2] + min(az, bz), origin[0] + max(ax, bx), origin[2] + max(az, bz)]


def compile_world(builds=None):
    """Everything the viewer's world mode needs, with collision problems."""
    world = read()
    t = world["terrain"]
    variants, vix = [], {}
    out_builds, problems = [], []
    water = [dict(w) for w in t.get("water", [])]
    for entry in world.get("builds", []):
        name = entry["name"]
        try:
            b = builds[name] if builds and name in builds else load(name)
        except Exception as e:  # a broken build.py must not take the whole world down
            problems.append(dict(msg=f"{name}: failed to load ({e})"))
            continue
        origin, facing = placement(world, entry)
        turns = FACINGS.index(facing)
        mx, my, mz = b.marker
        flat = []
        for (x, y, z), c in b.model.cells.items():
            rx, rz = rotate_pos(x - mx, z - mz, turns)
            props = rotate_props(c.key, c.props, turns)
            k = (c.key, json.dumps(props, sort_keys=True))
            if k not in vix:
                vix[k] = len(variants)
                variants.append([c.key, props])
            flat += [origin[0] + rx, origin[1] + y - my, origin[2] + rz, vix[k]]
        W, D = b.footprint
        rect = place_rect(b, origin, facing, 0, 0, W - 1, D - 1)
        for k in b.keep_zones:
            if k["what"] == "water":
                water.append(dict(name=f"{name}: {k['note'] or 'keep-zone'}",
                                  rect=place_rect(b, origin, facing, *k["box"]),
                                  surface=origin[1] + k["surface"], depth=k["depth"], keep=True))
        grades = [dict(rect=place_rect(b, origin, facing, *g["box"]), y=origin[1] + g["y"] - 1) for g in b.grade_rects()]
        out_builds.append(dict(name=name, title=b.title, facing=facing, origin=list(origin), rect=rect,
                               cells=flat, count=len(flat) // 4, marker=list(b.marker), grades=grades,
                               keeps_water=any(k['what'] == 'water' for k in b.keep_zones)))
    bx1, bz1, bx2, bz2 = t["bounds"]
    for i, a in enumerate(out_builds):
        r = a["rect"]
        if r[0] < bx1 or r[1] < bz1 or r[2] > bx2 or r[3] > bz2:
            problems.append(dict(msg=f"{a['name']} footprint {r} is outside the terrain bounds", rect=r))
        for c in out_builds[i + 1:]:
            q = c["rect"]
            ix1, iz1, ix2, iz2 = max(r[0], q[0]), max(r[1], q[1]), min(r[2], q[2]), min(r[3], q[3])
            if ix1 <= ix2 and iz1 <= iz2:
                problems.append(dict(msg=f"{a['name']} and {c['name']} footprints overlap",
                                     rect=[ix1, iz1, ix2, iz2]))
        for w in t.get("water", []) if not a["keeps_water"] else []:
            q = w["rect"]
            if max(r[0], q[0]) <= min(r[2], q[2]) and max(r[1], q[1]) <= min(r[3], q[3]):
                problems.append(dict(msg=f"{a['name']} footprint overlaps water '{w.get('name', '')}' "
                                     "(declare a keep-zone or move it)", rect=r))
    terrain = dict(t, water=water)
    return dict(terrain=terrain, builds=out_builds, variants=variants, problems=problems)
