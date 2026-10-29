"""Build checks: the game rules every build must satisfy, block counts, and the
replay of the exported commands against the model in all four facings."""
import random
from collections import deque

from export.core import FILL_MAX, FUNC_MAX, TICK_AREAS_MAX, commands_for, rel, site_rects, \
    split_volume
from export.sim import World, canon, run_file
from lib.blockdata import check_states, entities
from lib.build import area_cells
from lib.palette import FACINGS, block, states_for
from lib.voxel import DIRV, OPP

SOIL = {"grass_block", "dirt", "coarse_dirt", "podzol", "moss_block", "farmland", "mud", "dirt_path"}
GRAVITY = {"sand", "gravel"}
N6 = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


class Site:
    """Model + terrain (flat grade, raised terraces, keep-zones), in the build's local frame."""

    def __init__(self, b):
        self.b = b
        self.cells = b.model.cells
        self.step_ix = {s: i for i, s in enumerate(b.model.steps)}
        self.water = []
        for k in b.keep_zones:
            if k["what"] == "water":
                self.water.append((k["box"], k["surface"], k["depth"]))

    def keep_water(self, x, y, z):
        for (x1, z1, x2, z2), surf, depth in self.water:
            if x1 <= x <= x2 and z1 <= z <= z2 and surf - depth < y <= surf:
                return True
        return False

    def in_water_zone(self, x, z):
        return any(x1 <= x <= x2 and z1 <= z <= z2 for (x1, z1, x2, z2), _, _ in self.water)

    def ground(self, x, y, z):
        """Terrain at a cell the model leaves alone: 'grass_block', 'dirt', 'water' or None (air)."""
        if self.in_water_zone(x, z):
            for (x1, z1, x2, z2), surf, depth in self.water:
                if x1 <= x <= x2 and z1 <= z <= z2:
                    if y > surf:
                        return None
                    return "water" if y > surf - depth else "dirt"
        g = self.b.grade_at(x, z)
        if y >= g:
            return None
        return "grass_block" if y == g - 1 else "dirt"

    def at(self, p):
        """(key, props, flags, step index) or None for empty space."""
        c = self.cells.get(p)
        if c is not None:
            if c.key == "air":
                return None
            return c.key, c.props, block(c.key)["flags"], self.step_ix[c.step]
        key = self.ground(*p)
        if key is None:
            return None
        return key, {}, block(key)["flags"], -1

    def walk(self, p):
        a = self.at(p)
        return a is None or bool(a[2].get("walk"))

    def top(self, p):
        a = self.at(p)
        return a is not None and bool(a[2].get("top"))

    def climb(self, p):
        a = self.at(p)
        return a is not None and bool(a[2].get("climb"))

    def can_stand(self, p):
        x, y, z = p
        return self.walk(p) and self.walk((x, y + 1, z)) and \
            (self.top((x, y - 1, z)) or self.climb(p) or self.climb((x, y - 1, z)))


def add(out, level, check, msg, where=None):
    out.append(dict(level=level, check=check, msg=msg, where=where[:12] if where else None))


def run_checks(b):
    out = []
    s = Site(b)
    m = b.model
    W, D = b.footprint
    cells = {p: c for p, c in m.cells.items() if c.key != "air"}

    for e in b.problems:
        add(out, "error", "edits", e)

    # -- footprint & keep-zones & areas
    outside = [list(p) for p in cells if not (0 <= p[0] < W and 0 <= p[2] < D)]
    if outside:
        add(out, "error", "footprint", f"{len(outside)} blocks outside the {W}x{D} footprint", outside)
    for k in b.keep_zones:
        if k["build_ok"]:
            continue
        x1, z1, x2, z2 = k["box"]
        y1, y2 = k["y"]
        hit = [list(p) for p in m.cells if x1 <= p[0] <= x2 and z1 <= p[2] <= z2 and y1 <= p[1] <= y2]
        if hit:
            add(out, "error", "keep-zone", f"{len(hit)} blocks inside keep-zone {k['box']} ({k['note']})", hit)
    for i, g in enumerate(b.grades):
        for h in b.grades[i + 1:]:
            if max(g["box"][0], h["box"][0]) <= min(g["box"][2], h["box"][2]) and \
                    max(g["box"][1], h["box"][1]) <= min(g["box"][3], h["box"][3]):
                add(out, "error", "grades", f"terraces {g['box']} and {h['box']} overlap")
    areas = b.areas
    acells = [area_cells(a) for a in areas]
    for i, a in enumerate(areas):
        ax1, az1, ax2, az2 = a["box"]
        if ax1 < 0 or az1 < 0 or ax2 >= W or az2 >= D:
            add(out, "error", "areas", f"area '{a['key']}' extends outside the footprint")
        for j in range(i + 1, len(areas)):
            both = acells[i] & acells[j]
            if both:
                add(out, "error", "areas", f"areas '{a['key']}' and '{areas[j]['key']}' overlap "
                    f"({len(both)} cells)", [[x, 0, z] for x, z in sorted(both)])
    if areas:
        allc = set().union(*acells)
        loose = [list(p) for p in cells if (p[0], p[2]) not in allc]
        if loose:
            add(out, "warn", "areas", f"{len(loose)} blocks are outside every declared area", loose)

    # -- nothing floating: every block connects to the ground through other blocks
    grounded = set()
    q = deque()
    for p, c in cells.items():
        x, y, z = p
        # seeds: blocks touching solid ground (seabed, terrace earth, grade) the model does not replace
        for dx, dy, dz in N6:
            n = (x + dx, y + dy, z + dz)
            if n not in m.cells and s.ground(*n) in ("grass_block", "dirt"):
                grounded.add(p)
                q.append(p)
                break
    def links(p):
        x, y, z = p
        out = [(x + dx, y + dy, z + dz) for dx, dy, dz in N6]
        c = cells[p]
        if c.shape == "stair":     # a roof slope: each stair meets the next one up along its facing
            fx, fz = DIRV[c.props["facing"]]
            for n in ((x + fx, y + 1, z + fz), (x - fx, y - 1, z - fz)):
                nc = cells.get(n)
                if nc is not None and nc.shape == "stair" and nc.props["facing"] == c.props["facing"]:
                    out.append(n)
        return out

    while q:
        p = q.popleft()
        cp = cells.get(p)
        for n in links(p):
            # plants, crops, carpets, torches, lanterns, doors... cannot hold up a block above them
            if cp is not None and n == (p[0], p[1] + 1, p[2]) and cp.flags.get("walk") and \
                    not (cp.group is not None and cells.get(n) is not None and cells[n].group == cp.group):
                continue
            if n in cells and n not in grounded and cells[n].key != "water":
                grounded.add(n)
                q.append(n)
    floating = [list(p) for p, c in cells.items() if p not in grounded and c.key != "water" and c.tag != "afloat"]
    if floating:
        add(out, "error", "floating", f"{len(floating)} blocks are not connected to the ground", floating)

    # -- sand and gravel fall unless something solid is under them
    falls = []
    for p, c in cells.items():
        if c.key in GRAVITY:
            a = s.at((p[0], p[1] - 1, p[2]))
            if a is None or a[2].get("walk"):
                falls.append(list(p))
    if falls:
        add(out, "error", "gravity", f"{len(falls)} sand/gravel blocks have nothing solid under them", falls)

    # -- supports (and the support exists by the same step)
    bad, late = [], []
    for p, c in cells.items():
        need = block(c.key)["needs"]
        if not need:
            continue
        x, y, z = p
        sup = None
        if c.shape in ("door", "tall_plant") and c.props.get("upper"):
            continue
        if need == "below_top":
            sup = (x, y - 1, z)
            ok = s.top(sup)
        elif need == "soil":
            sup = (x, y - 1, z)
            a = s.at(sup)
            ok = a is not None and a[0] in SOIL
        elif need == "farmland":
            sup = (x, y - 1, z)
            a = s.at(sup)
            ok = a is not None and a[0] == "farmland"
        elif need == "behind_sturdy":
            dx, dz = DIRV[c.props["facing"]]
            sup = (x - dx, y, z - dz)
            a = s.at(sup)
            ok = a is not None and bool(a[2].get("sturdy"))
        elif need == "torch":
            if c.props["facing"] == "up":
                sup = (x, y - 1, z)
                ok = s.top(sup)
            else:
                dx, dz = DIRV[c.props["facing"]]
                sup = (x - dx, y, z - dz)
                a = s.at(sup)
                ok = a is not None and bool(a[2].get("sturdy"))
        elif need == "lantern":
            if c.props.get("hanging"):
                sup = (x, y + 1, z)
                a = s.at(sup)
                ok = a is not None and bool(a[2].get("bottom")) and not \
                    (a[2] is block("oak_slab")["flags"] and a[1].get("half") == "top")
            else:
                sup = (x, y - 1, z)
                ok = s.top(sup)
        elif need == "water_or_top":
            sup = (x, y - 1, z)
            a = s.at(sup)
            ok = a is not None and (a[0] == "water" if c.key == "lily_pad" else bool(a[2].get("top")))
        else:
            continue
        if not ok:
            bad.append([*p, c.key])
        elif sup is not None:
            a = s.at(sup)
            if a and a[3] > s.step_ix[c.step]:
                late.append([*p, c.key])
    if bad:
        add(out, "error", "support", f"{len(bad)} blocks lack the support they need "
            "(ladder/torch backing, lantern above/below, soil, farmland, floor)", bad)
    if late:
        add(out, "error", "step-order", f"{len(late)} blocks are placed in an earlier step than "
            "the block holding them up", late)

    # -- roofs from regular stairs
    ud_roof = [list(p) for p, c in cells.items() if c.shape == "stair" and c.props.get("half") == "top"
               and c.tag == "roof"]
    ud = [list(p) for p, c in cells.items() if c.shape == "stair" and c.props.get("half") == "top"
          and c.tag != "roof"]
    if ud_roof:
        add(out, "error", "roof", f"{len(ud_roof)} upside-down stairs in a roof", ud_roof)
    if ud:
        add(out, "warn", "stairs", f"{len(ud)} upside-down stairs (trim only; not for roofs)", ud)

    # -- beacons need sky
    top_y = max([p[1] for p in cells] + [0])
    for p, c in cells.items():
        if c.key != "beacon":
            continue
        x, y, z = p
        blocked = [yy for yy in range(y + 1, top_y + 1)
                   if (x, yy, z) in cells and block(cells[(x, yy, z)].key)["shape"] not in ("glass", "air")]
        if blocked:
            add(out, "error", "beacon", f"beacon at {list(p)} has no sky access (blocked at y={blocked[0]})", [list(p)])
        base = [(x + dx, y - 1, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
        if not all(s.at(q) and s.at(q)[0] in ("iron_block", "gold_block") for q in base):
            add(out, "warn", "beacon", f"beacon at {list(p)} has no 3x3 iron/gold base under it", [list(p)])

    # -- water stays put
    leaks = []
    for p, c in cells.items():
        if c.key != "water":
            continue
        x, y, z = p
        for dx, dy, dz in [(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)]:
            a = s.at((x + dx, y + dy, z + dz))
            if a is None or (not a[2].get("full") and a[0] != "water"):
                leaks.append(list(p))
                break
    if leaks:
        add(out, "error", "water", f"{len(leaks)} water blocks can flow out (open side or below)", leaks)

    # -- a way up to every floor
    reach = reachable(s, b)
    for f in m.floors:
        x1, z1, x2, z2 = f["box"]
        ok = any((x, f["y"], z) in reach for x in range(x1, x2 + 1) for z in range(z1, z2 + 1))
        add(out, "ok" if ok else "error", "access",
            f"floor '{f['name']}' (y={f['y']}) " + ("is reachable on foot/ladder" if ok else "cannot be reached"))

    # -- doors, beds, entities in clear space
    for g, mk in m.markers.items():
        x, y, z = mk["pos"]
        if mk["type"] == "door":
            dx, dz = DIRV[mk["facing"]]
            sides = [(x - dx, y, z - dz), (x + dx, y, z + dz)]
            ok = all(s.can_stand(q) for q in sides)
            add(out, "ok" if ok else "error", "door",
                f"door at {mk['pos']} " + ("opens onto walkable space both sides" if ok else
                                           "is blocked or has no floor on one side"), [mk["pos"]])
            if ok and not any(q in reach for q in sides):
                add(out, "warn", "door", f"door at {mk['pos']} is not reachable from outside", [mk["pos"]])
        elif mk["type"] == "bed":
            hx, hz = x + DIRV[mk["facing"]][0], z + DIRV[mk["facing"]][1]
            ok = all(s.walk((px, y + 1, pz)) for px, pz in ((x, z), (hx, hz)))
            add(out, "ok" if ok else "error", "bed", f"bed at {mk['pos']} " +
                ("has head room" if ok else "has a block on top of it"), [mk["pos"]])
        elif mk["type"] == "entity":
            ok_id = mk["id"] in entities()
            ok = s.can_stand((x, y, z)) or s.at((x, y, z)) and s.at((x, y, z))[0] == "water"
            add(out, "ok" if ok and ok_id else "error", "entity",
                f"{mk['id']} at {mk['pos']} " + ("unknown entity id" if not ok_id else
                                                "has clear space" if ok else "is stuck in a block / no floor"),
                [mk["pos"]])
    return out


def reachable(s, b):
    """Positions a player can stand in, starting on the grass outside the footprint."""
    W, D = b.footprint
    xs = [p[0] for p in s.cells] + [0, W - 1]
    zs = [p[2] for p in s.cells] + [0, D - 1]
    x1, x2, z1, z2 = min(xs) - 3, max(xs) + 3, min(zs) - 3, max(zs) + 3
    ytop = max([p[1] for p in s.cells] + [0]) + 2
    seen, q = set(), deque()
    for x in range(x1, x2 + 1):
        for z in (z1, z2):
            if s.can_stand((x, 0, z)):
                seen.add((x, 0, z))
                q.append((x, 0, z))
    for z in range(z1, z2 + 1):
        for x in (x1, x2):
            if s.can_stand((x, 0, z)):
                seen.add((x, 0, z))
                q.append((x, 0, z))

    def tall(p):
        a = s.at(p)
        return a is not None and a[2].get("tall")

    while q:
        x, y, z = q.popleft()
        nxt = []
        for dx, dz in DIRV.values():
            nx, nz = x + dx, z + dz
            if not (x1 <= nx <= x2 and z1 <= nz <= z2):
                continue
            if s.can_stand((nx, y, nz)):
                nxt.append((nx, y, nz))
            elif s.walk((nx, y, nz)) and s.walk((nx, y + 1, nz)):
                for yy in range(y - 1, max(-3, y - 24), -1):    # walk off an edge and fall
                    if not s.walk((nx, yy, nz)):
                        break
                    if s.can_stand((nx, yy, nz)):
                        nxt.append((nx, yy, nz))
                        break
            # step up one block: onto stairs/slabs you just walk, anything else needs jump head room;
            # fences and walls are too tall
            if s.can_stand((nx, y + 1, nz)) and not tall((nx, y, nz)):
                below = s.at((nx, y, nz))
                stepped = below is not None and block(below[0])["shape"] in ("stair", "slab")
                if stepped or s.walk((x, y + 2, z)):
                    nxt.append((nx, y + 1, nz))
        if (s.climb((x, y, z)) or s.climb((x, y - 1, z))) and s.can_stand((x, y + 1, z)):
            nxt.append((x, y + 1, z))
        if s.can_stand((x, y - 1, z)) and (s.climb((x, y - 1, z)) or s.climb((x, y - 2, z))):
            nxt.append((x, y - 1, z))
        for n in nxt:
            if n not in seen and n[1] <= ytop:
                seen.add(n)
                q.append(n)
    return seen


# ---------------------------------------------------------------- counts
def counts(b):
    s = Site(b)
    cells = {p: c for p, c in b.model.cells.items() if c.key != "air"}
    hidden = []
    for p, c in cells.items():
        # only full blocks buried below the local ground (grade or terrace) count as hidden fill
        if not c.flags.get("opaque") or p[1] >= b.grade_at(p[0], p[2]):
            continue
        x, y, z = p
        exposed = False
        for dx, dy, dz in N6:
            a = s.at((x + dx, y + dy, z + dz))
            if a is None or not a[2].get("opaque"):
                exposed = True
                break
        if not exposed:
            hidden.append(p)
    hid = set(hidden)
    by_step = {st["key"]: 0 for st in b.steps}
    by_block = {}
    by_step_block = {st["key"]: {} for st in b.steps}
    for p, c in cells.items():
        if p in hid:
            continue
        by_step[c.step] += 1
        by_block[c.key] = by_block.get(c.key, 0) + 1
        sb = by_step_block[c.step]
        sb[c.key] = sb.get(c.key, 0) + 1
    total = sum(by_step.values())
    items = {k: -(-n // block(k)["item_cells"]) for k, n in by_block.items()}
    return dict(total=total, by_step=by_step, by_block=dict(sorted(by_block.items(), key=lambda kv: -kv[1])),
                by_step_block=by_step_block, items=items, hidden=len(hidden),
                hidden_cells=[list(p) for p in hidden[:50]], target=b.target)


# ---------------------------------------------------------------- export validation
def validate_export(b, facing, files, meta, world, derived, bstr):
    """States valid, limits respected, replay matches the model."""
    out = []
    # block states (every placed variant, this facing)
    errs = set()
    for pos, c in world.items():
        bid, st = states_for(c["key"], c["props"], derived.get(pos))
        errs.update(check_states(bid, st))
    if errs:
        add(out, "error", "states", f"[{facing}] invalid block states: " + "; ".join(sorted(errs)[:6]))
    # limits
    for name, lines in files.items():
        if len(lines) > FUNC_MAX:
            add(out, "error", "limits", f"[{facing}] {name} has {len(lines)} lines (> {FUNC_MAX})")
    if len(meta["tick"]) > TICK_AREAS_MAX:
        add(out, "error", "limits", f"[{facing}] needs {len(meta['tick'])} ticking areas (max {TICK_AREAS_MAX})")

    # replay into a messy simulated site
    origin = (1000, 64, -2000)
    ox, oy, oz = origin
    rnd = random.Random(7)
    init = {}
    lx1, lz1, lx2, lz2 = meta["load"]
    for x in range(lx1 - 2, lx2 + 3):
        for z in range(lz1 - 2, lz2 + 3):
            for y in range(-4, 0):
                init[(ox + x, oy + y, oz + z)] = "minecraft:grass_block" if y == -1 else "minecraft:dirt"
            r = rnd.random()
            if r < 0.04:
                init[(ox + x, oy - 1, oz + z)] = "minecraft:air"           # holes
                init[(ox + x, oy - 2, oz + z)] = "minecraft:water[liquid_depth=0]"
            elif r < 0.10:
                for y in range(0, rnd.randint(1, 6)):
                    init[(ox + x, oy + y, oz + z)] = "minecraft:oak_log[pillar_axis='y']"
            elif r < 0.25:
                init[(ox + x, oy, oz + z)] = "minecraft:short_grass"
    keep_cells = {}
    for k in b.keep_zones:
        x1, z1, x2, z2 = k["box"]
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                rx, _, rz = rel(b, facing, x, 0, z)
                for y in range(k["y"][0], k["y"][1] + 1):
                    surf = k["surface"]
                    if k["what"] == "water" and surf - k["depth"] < y <= surf:
                        v = "minecraft:water[liquid_depth=0]"
                    elif k["what"] == "water" and y <= surf - k["depth"]:
                        v = "minecraft:dirt"
                    elif k["what"] == "water":
                        v = "minecraft:air"
                    elif k["what"] != "water" and y in (0, 1):
                        v = "minecraft:mossy_cobblestone"       # stand-in for "whatever is there"
                    else:
                        v = init.get((ox + rx, oy + y, oz + rz), "minecraft:air")
                    p = (ox + rx, oy + y, oz + rz)
                    if v == "minecraft:air":
                        init.pop(p, None)
                    else:
                        init[p] = v
                    keep_cells[p] = v
    w = World(init)
    for f in ("setup", *meta["run_order"]):
        run_file(w, files, f, origin)
    for e in w.errors[:8]:
        add(out, "error", "replay", f"[{facing}] {e}")

    # compare
    mismatch, extra = [], []
    expect = {}
    for pos, c in world.items():
        bid, st = states_for(c["key"], c["props"], derived.get(pos))
        expect[(ox + pos[0], oy + pos[1], oz + pos[2])] = canon(bid, st)
    for p, v in expect.items():
        if w.get(p) != v:
            mismatch.append([p[0] - ox, p[1] - oy, p[2] - oz, w.get(p), v])
    for (x1, z1, x2, z2), g in site_rects(b, facing):
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                for y in range(g, meta["clear_top"] + 1):
                    p = (ox + x, oy + y, oz + z)
                    if p not in expect and w.get(p) != "minecraft:air":
                        extra.append([x, y, z, w.get(p)])
                for y in range(g - 3, g):
                    p = (ox + x, oy + y, oz + z)
                    if p not in expect and w.get(p).split("[")[0] in ("minecraft:air", "minecraft:water"):
                        extra.append([x, y, z, "hole: " + w.get(p)])
    touched = [list(p) for p, v in keep_cells.items() if w.get(p) != v and p not in expect]
    if mismatch:
        add(out, "error", "replay", f"[{facing}] {len(mismatch)} cells differ from the model after replay", mismatch)
    if extra:
        add(out, "error", "replay", f"[{facing}] {len(extra)} leftover blocks/holes in the cleared site", extra)
    if touched:
        add(out, "error", "keep-zone", f"[{facing}] replay changed {len(touched)} keep-zone cells", touched)

    # markers land in clear space in the replayed world
    def wget(x, y, z):
        return w.get((ox + x, oy + y, oz + z)).split("[")[0][10:]

    for g, mk in b.model.markers.items():
        x, y, z = rel(b, facing, *mk["pos"])
        if mk["type"] == "door":
            if not (wget(x, y, z) == wget(x, y + 1, z) == block(mk["key"])["id"][10:]):
                add(out, "error", "replay", f"[{facing}] door at {mk['pos']} incomplete after replay")
        if mk["type"] == "bed":
            if wget(x, y, z) != "bed":
                add(out, "error", "replay", f"[{facing}] bed at {mk['pos']} missing after replay")
        if mk["type"] == "entity":
            ok = any(abs(e["pos"][0] - (ox + x + 0.5)) < 1e-6 and abs(e["pos"][2] - (oz + z + 0.5)) < 1e-6
                     for e in w.entities)
            here = wget(x, y, z)
            head = wget(x, y + 1, z)
            clear = all(block_walk(k) for k in (here, head))
            if not ok or not clear:
                add(out, "error", "replay", f"[{facing}] {mk['id']} at {mk['pos']} not summoned into clear space")
    if not [o for o in out if o["level"] == "error"]:
        add(out, "ok", "replay", f"[{facing}] replay matches the model: {len(expect)} blocks, "
            f"{w.commands} commands, keep-zones untouched")
    # test strip replays cleanly too
    t = World(dict(init))
    run_file(t, files, "setup", origin)
    run_file(t, files, "test_blocks", origin)
    run_file(t, files, "cleanup", origin)
    if t.errors:
        add(out, "error", "replay", f"[{facing}] test_blocks/cleanup: {t.errors[0]}")
    return out


def block_walk(bid):
    if bid in ("air", ""):
        return True
    from blocks.palette import BLOCKS
    for k, v in BLOCKS.items():
        if v["id"] == "minecraft:" + bid:
            return bool(v["flags"].get("walk"))
    return False


def full_validation(b):
    """Structural checks + every facing's export. Returns (checks, per-facing command sets)."""
    checks = run_checks(b)
    sets = {}
    for f in FACINGS:
        files, meta, world, derived, bstr = commands_for(b, f)
        checks += validate_export(b, f, files, meta, world, derived, bstr)
        sets[f] = (files, meta)
    return checks, sets
