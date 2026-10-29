"""Turn a build into Bedrock commands for one facing.

Coordinates in commands are relative (~) to the marker block: the player
stands on it, or uses `execute positioned X Y Z run function ...`.
"""
from lib.palette import FACINGS, block, rotate_pos, rotate_props, states_for
from lib.voxel import DIRV, LEFT, OPP

FILL_MAX = 32768          # Bedrock /fill volume limit
FUNC_MAX = 9000           # stay well under the 10,000 command function limit
TICK_CHUNKS_MAX = 100     # Bedrock ticking area size limit (chunks)
TICK_AREAS_MAX = 10       # Bedrock ticking areas per world
PREP_MARGIN = 1
HEADROOM = 4

PHASE = {  # placement order inside a step: supports first, attachments after, water last
    "air": 0, "cube": 1, "log": 1, "glass": 1, "leaves": 1, "path": 1,
    "slab": 2, "stair": 2, "fence": 2, "wall": 2, "pane": 2, "fence_gate": 2, "chest": 2,
    "campfire": 2, "chain": 2, "bed": 3, "door": 3, "trapdoor": 3, "plant": 3, "tall_plant": 3,
    "crop": 3, "flat": 3, "carpet": 3, "ladder": 3, "lantern": 3, "torch": 3, "pot": 3, "water": 4,
}


def turns_for(facing):
    return FACINGS.index(facing)


def placed(b, facing):
    """{rel_pos: cell-dict} for the build turned to `facing`, relative to the marker."""
    t = turns_for(facing)
    mx, my, mz = b.marker
    out = {}
    for (x, y, z), c in b.model.cells.items():
        rx, rz = rotate_pos(x - mx, z - mz, t)
        out[(rx, y - my, rz)] = dict(key=c.key, props=rotate_props(c.key, c.props, t),
                                     step=c.step, group=c.group, tag=c.tag)
    return out


def rel(b, facing, x, y, z):
    rx, rz = rotate_pos(x - b.marker[0], z - b.marker[2], turns_for(facing))
    return rx, y - b.marker[1], rz


def rect_rel(b, facing, x1, z1, x2, z2):
    ax, _, az = rel(b, facing, x1, 0, z1)
    bx, _, bz = rel(b, facing, x2, 0, z2)
    return min(ax, bx), min(az, bz), max(ax, bx), max(az, bz)


# ---------------------------------------------------------------- derived states
def _shape(cell):
    return block(cell["key"])["shape"] if cell else None


def _sturdy(cell):
    return bool(cell) and block(cell["key"])["flags"].get("sturdy")


def derive(world):
    """Exporter-computed states: stair corners and fence/pane/wall connections."""
    out = {}
    for pos, c in world.items():
        d = block(c["key"])["derived"]
        if not d:
            continue
        x, y, z = pos
        if "corner" in d:
            out[pos] = {"minecraft:corner": stair_corner(world, pos, c)}
            continue
        nb = {s: world.get((x + dx, y, z + dz)) for s, (dx, dz) in DIRV.items()}
        if "connections" in d:
            sh = _shape(c)
            out[pos] = {f"minecraft:connection_{s}": bool(_connects(sh, n, s)) for s, n in nb.items()}
        elif "walls" in d:
            above = world.get((x, y + 1, z))
            tall = bool(above) and block(above["key"])["flags"].get("full")
            conn = {s: bool(_connects("wall", n, s)) for s, n in nb.items()}
            st = {f"wall_connection_type_{s}": ("tall" if tall else "short") if v else "none"
                  for s, v in conn.items()}
            straight = (conn["north"] and conn["south"] and not conn["east"] and not conn["west"]) or \
                       (conn["east"] and conn["west"] and not conn["north"] and not conn["south"])
            st["wall_post_bit"] = (not straight) or bool(above)
            out[pos] = st
    return out


def _connects(shape, n, side):
    if not n:
        return False
    ns = _shape(n)
    if ns == "fence_gate":
        gate_axis = "z" if n["props"].get("facing") in ("north", "south") else "x"
        side_axis = "z" if side in ("north", "south") else "x"
        return shape in ("fence", "wall") and gate_axis != side_axis
    if shape == "fence":
        return ns == "fence" or _sturdy(n)
    if shape == "pane":
        return ns in ("pane", "glass", "wall") or _sturdy(n)
    if shape == "wall":
        return ns in ("wall", "pane") or _sturdy(n)
    return False


def stair_corner(world, pos, c):
    """Java's stair shape rule (Bedrock uses the same names)."""
    x, y, z = pos
    f, half = c["props"]["facing"], c["props"]["half"]

    def stair_at(d):
        dx, dz = DIRV[d]
        n = world.get((x + dx, y, z + dz))
        if n and _shape(n) == "stair" and n["props"]["half"] == half:
            return n
        return None

    def axis(d):
        return "z" if d in ("north", "south") else "x"

    def can_take(d):
        n = stair_at(d)
        return not (n and n["props"]["facing"] == f)

    back = stair_at(f)
    if back and axis(back["props"]["facing"]) != axis(f) and can_take(OPP[back["props"]["facing"]]):
        return "outer_left" if back["props"]["facing"] == LEFT[f] else "outer_right"
    front = stair_at(OPP[f])
    if front and axis(front["props"]["facing"]) != axis(f) and can_take(front["props"]["facing"]):
        return "inner_left" if front["props"]["facing"] == LEFT[f] else "inner_right"
    return "none"


# ---------------------------------------------------------------- formatting
def fmt_states(states):
    if not states:
        return ""
    parts = []
    for k in sorted(states):
        v = states[k]
        if isinstance(v, bool):
            v = "true" if v else "false"
        elif isinstance(v, str):
            v = f'"{v}"'
        parts.append(f'"{k}"={v}')
    return "[" + ",".join(parts) + "]"


def block_str(bid, states):
    return bid + (" " + fmt_states(states) if states else "")


def p3(x, y, z):
    return f"~{x} ~{y} ~{z}"


def merge_boxes(cells):
    """Greedy merge of a set of positions into boxes (x, y, z, x2, y2, z2), each <= FILL_MAX."""
    left = set(cells)
    boxes = []
    for (x, y, z) in sorted(cells, key=lambda p: (p[1], p[2], p[0])):
        if (x, y, z) not in left:
            continue
        x2 = x
        while (x2 + 1, y, z) in left and (x2 + 2 - x) <= FILL_MAX:
            x2 += 1
        z2 = z
        while all((xx, y, z2 + 1) in left for xx in range(x, x2 + 1)) and \
                (x2 - x + 1) * (z2 + 2 - z) <= FILL_MAX:
            z2 += 1
        y2 = y
        while all((xx, y2 + 1, zz) in left for xx in range(x, x2 + 1) for zz in range(z, z2 + 1)) and \
                (x2 - x + 1) * (z2 - z + 1) * (y2 + 2 - y) <= FILL_MAX:
            y2 += 1
        for xx in range(x, x2 + 1):
            for yy in range(y, y2 + 1):
                for zz in range(z, z2 + 1):
                    left.discard((xx, yy, zz))
        boxes.append((x, y, z, x2, y2, z2))
    return boxes


def fill_or_set(box, bs):
    x, y, z, x2, y2, z2 = box
    if (x, y, z) == (x2, y2, z2):
        return f"setblock {p3(x, y, z)} {bs}"
    return f"fill {p3(x, y, z)} {p3(x2, y2, z2)} {bs}"


def split_volume(x1, y1, z1, x2, y2, z2):
    """Split a box into pieces of at most FILL_MAX blocks (slices along y, then x)."""
    w, d = x2 - x1 + 1, z2 - z1 + 1
    if w * d > FILL_MAX:
        step = max(1, FILL_MAX // d)
        for xs in range(x1, x2 + 1, step):
            yield from split_volume(xs, y1, z1, min(x2, xs + step - 1), y2, z2)
        return
    layers = max(1, FILL_MAX // (w * d))
    for ys in range(y1, y2 + 1, layers):
        yield (x1, ys, z1, x2, min(y2, ys + layers - 1), z2)


def subtract_rect(r, hole):
    """r minus hole, as up to four rects (x1, z1, x2, z2), inclusive."""
    x1, z1, x2, z2 = r
    hx1, hz1, hx2, hz2 = hole
    if hx1 > x2 or hx2 < x1 or hz1 > z2 or hz2 < z1:
        return [r]
    out = []
    if hz1 > z1:
        out.append((x1, z1, x2, hz1 - 1))
    if hz2 < z2:
        out.append((x1, hz2 + 1, x2, z2))
    mz1, mz2 = max(z1, hz1), min(z2, hz2)
    if hx1 > x1:
        out.append((x1, mz1, hx1 - 1, mz2))
    if hx2 < x2:
        out.append((hx2 + 1, mz1, x2, mz2))
    return out


# ---------------------------------------------------------------- per-facing command sets
def site_rects(b, facing):
    """Prep regions (relative) as [(rect, grade)]: the site minus keep-zones, split by terrace grade."""
    w, d = b.footprint
    mg = PREP_MARGIN
    holes = [k["box"] for k in b.keep_zones]
    base = [(-mg, -mg, w - 1 + mg, d - 1 + mg)]
    out = []
    for g in b.grades:
        base = [piece for r in base for piece in subtract_rect(r, g["box"])]
        rects = [tuple(g["box"])]
        for h in holes:
            rects = [piece for r in rects for piece in subtract_rect(r, h)]
        out += [(r, g["y"]) for r in rects]
    for h in holes:
        base = [piece for r in base for piece in subtract_rect(r, h)]
    out = [(r, 0) for r in base] + out
    return [(rect_rel(b, facing, *r), g) for r, g in out]


def commands_for(b, facing):
    """Everything for one facing: {function name: [lines]} plus metadata."""
    world = placed(b, facing)
    derived = derive(world)
    bstr = {}
    for pos, c in world.items():
        bid, st = states_for(c["key"], c["props"], derived.get(pos))
        bstr[pos] = block_str(bid, st)
    top = max([p[1] for p in world] + [0])
    clear_top = top + HEADROOM
    ns = b.name
    files = {}

    # site extents (for the ticking area)
    w, d = b.footprint
    site = rect_rel(b, facing, -PREP_MARGIN, -PREP_MARGIN, w - 1 + PREP_MARGIN, d - 1 + PREP_MARGIN)
    strip_lines, strip_rect = test_strip(b, facing, world, derived)
    xs = [site[0], site[2], strip_rect[0], strip_rect[2], 0]
    zs = [site[1], site[3], strip_rect[1], strip_rect[3], 0]
    for (x, y, z) in world:
        xs.append(x)
        zs.append(z)
    load = (min(xs), min(zs), max(xs), max(zs))
    tick = tick_areas(ns, facing, load, clear_top)

    files["setup"] = [f"# {b.title} ({facing}): keep the whole site loaded. Wait ~5 s before building.",
                      *[f"tickingarea add {p3(a[0], -8, a[1])} {p3(a[2], clear_top, a[3])} {name} true"
                        for name, a in tick],
                      "SETUP_NEXT"]

    prep = [f"# Step 1: Clear and level the land - clear above grade, fill holes below grade "
            "(terraces raised to their own grade). Keep-zones untouched."]
    for (x1, z1, x2, z2), g in site_rects(b, facing):
        if g:
            prep.append(f"# terrace at +{g}")
        for bx in split_volume(x1, g, z1, x2, clear_top, z2):
            prep.append(f"fill {p3(*bx[:3])} {p3(*bx[3:])} minecraft:air")
        for bx in split_volume(x1, min(-3, g - 4), z1, x2, g - 2, z2):
            for src in ("minecraft:air", "minecraft:water", "minecraft:flowing_water"):
                prep.append(f"fill {p3(*bx[:3])} {p3(*bx[3:])} minecraft:dirt replace {src}")
        for bx in split_volume(x1, g - 1, z1, x2, g - 1, z2):
            for src in ("minecraft:air", "minecraft:water", "minecraft:flowing_water"):
                prep.append(f"fill {p3(*bx[:3])} {p3(*bx[3:])} minecraft:grass_block replace {src}")
    files["step01_site"] = prep

    step_files = []
    for si, s in enumerate(b.steps, 1):
        lines = [f"# Step {si + 1}: {s['title']}" + (f" - {s['desc']}" if s["desc"] else "")]
        cells = {p: c for p, c in world.items() if c["step"] == s["key"]}
        lines += step_commands(cells, bstr)
        base = f"step{si + 1:02d}_{s['key']}"
        chunks = [lines[i:i + FUNC_MAX] for i in range(0, len(lines), FUNC_MAX)] or [lines]
        if len(chunks) == 1:
            files[base] = lines
            step_files.append(base)
        else:
            for ci, ch in enumerate(chunks):
                nm = f"{base}_{'abcdefghij'[ci]}"
                files[nm] = ch
                step_files.append(nm)

    ent = ["# Entities (summoned at block centres)"]
    for g, mk in b.model.markers.items():
        if mk["type"] != "entity":
            continue
        x, y, z = rel(b, facing, *mk["pos"])
        name = f' "{mk["name"]}"' if mk.get("name") else ""
        if name:
            ent.append(f"execute align xyz run summon {mk['id']}{name} ~{x + 0.5:g} ~{y} ~{z + 0.5:g}")
        else:
            ent.append(f"execute align xyz run summon {mk['id']} ~{x + 0.5:g} ~{y} ~{z + 0.5:g}")
    files["entities"] = ent

    run_order = ["step01_site"] + step_files + ["entities"]
    total = sum(len(files[f]) for f in run_order)
    # one call may run at most ~10,000 commands (functionCommandLimit): group the steps into
    # build (if it all fits) or build_1, build_2, ... each under FUNC_MAX
    groups, cur, n = [], [], 0
    for f in run_order:
        k = len(files[f]) + 1
        if cur and n + k + 2 > FUNC_MAX:
            groups.append(cur)
            cur, n = [], 0
        cur.append(f)
        n += k
    if cur:
        groups.append(cur)
    build_parts = ["build"] if len(groups) == 1 else [f"build_{i + 1}" for i in range(len(groups))]
    for i, (name, g) in enumerate(zip(build_parts, groups)):
        cmds = sum(len(files[f]) for f in g)
        nxt = (f"Next: /function {ns}/{facing}/{build_parts[i + 1]}" if i + 1 < len(groups)
               else f"Done. Run /function {ns}/{facing}/cleanup when you're happy.")
        files[name] = [f"# Part {i + 1} of {len(groups)}: {', '.join(g)} ({cmds} commands)."] + \
                      [f"function {ns}/{facing}/{f}" for f in g] + [f"say {b.title}: part {i + 1}/{len(groups)} built. {nxt}"]
    areas = f"{len(tick)} ticking area{'s' if len(tick) > 1 else ''}"
    files["setup"][-1] = f"say {b.title}: site loaded ({areas}). Next: /function {ns}/{facing}/{build_parts[0]}"
    if len(groups) > 1:
        files["build"] = [f"# {total} commands is more than one call can run; run the parts in order:"] + \
                         [f"say /function {ns}/{facing}/{p}" for p in build_parts]

    files["test_blocks"] = ["# One of every block variant this build uses, in a strip in front of the marker."] + strip_lines
    placed_cells = []
    for ln in strip_lines:
        t = ln.split()
        if t[0] == "setblock" and t[1:4] not in placed_cells:
            placed_cells.append(t[1:4])
    files["cleanup"] = [
        "# Remove the test strip (only the cells test_blocks placed), dropped items and the ticking area.",
        *[f"setblock {' '.join(c)} minecraft:air" for c in reversed(placed_cells)],
        f"kill @e[type=item,x=~{load[0]},y=~-8,z=~{load[1]},dx={load[2] - load[0] + 1},dy={clear_top + 9},dz={load[3] - load[1] + 1}]",
        *[f"tickingarea remove {name}" for name, _ in tick],
    ]
    meta = dict(run_order=run_order, step_files=step_files, total=total, tick=tick, build_parts=build_parts,
                clear_top=clear_top, site=site, strip=strip_rect, load=load)
    return files, meta, world, derived, bstr


def step_commands(cells, bstr):
    lines = []
    groups = {}
    singles = []
    for pos, c in cells.items():
        ph = PHASE[block(c["key"])["shape"]]
        if c["group"] is not None:
            singles.append((ph, pos))
        else:
            groups.setdefault((ph, bstr[pos]), []).append(pos)
    by_phase = {}
    for (ph, bs), plist in groups.items():
        by_phase.setdefault(ph, []).extend(fill_or_set(bx, bs) for bx in merge_boxes(plist))
    for ph in sorted(set(by_phase) | {p for p, _ in singles}):
        lines += sorted(by_phase.get(ph, []), key=_cmd_sort)
        # doors / beds / tall plants: lower before upper, foot before head
        sg = sorted((pos for p, pos in singles if p == ph),
                    key=lambda p: (cells[p]["group"], p[1], bool(cells[p]["props"].get("head"))))
        lines += [f"setblock {p3(*pos)} {bstr[pos]}" for pos in sg]
    return lines


def _cmd_sort(line):
    parts = line.split()
    return int(parts[2][1:]), line   # by lowest y first


def test_strip(b, facing, world, derived):
    """Lay every distinct block string on a stone base, 16 per row, in front of the marker."""
    seen = {}
    for pos, c in world.items():
        if c["key"] == "air":
            continue
        bid, st = states_for(c["key"], c["props"], derived.get(pos))
        k = block_str(bid, st)
        if k not in seen:
            seen[k] = (c, bid)
    # local frame: rows run along +x from the marker, stepping away from the build (-z)
    mx, my, mz = b.marker
    sx0, z0, zstep = mx, min([p[2] for p in b.model.cells] + [0]) - 4, -4
    if b.test_strip:
        sx0, z0 = b.test_strip
        zstep = 4 if z0 >= b.footprint[1] else -4
    lines, cells = [], []
    items = [(k, v) for k, v in sorted(seen.items())
             if not v[0]["props"].get("upper") and not v[0]["props"].get("head")]
    for i, (k, (c, bid)) in enumerate(items):
        lx, lz = sx0 + (i % 16) * 3, z0 + (i // 16) * zstep
        sh = block(c["key"])["shape"]
        base = "minecraft:farmland" if sh == "crop" else "minecraft:grass_block" if sh in ("plant", "tall_plant") else "minecraft:stone"
        R = lambda x, y, z: rel(b, facing, x, y, z)  # noqa: E731
        lines.append(f"setblock {p3(*R(lx, 0, lz))} {base}")
        cells.append((lx, lz))
        props = c["props"]
        if sh in ("ladder",) or (sh == "torch" and props.get("facing") != "up"):
            # support behind, in the local frame (props are already turned, so turn back)
            back = OPP[_unturn(props["facing"], facing)]
            dx, dz = DIRV[back]
            lines.append(f"setblock {p3(*R(lx + dx, 1, lz + dz))} minecraft:stone")
            cells.append((lx + dx, lz + dz))
        if sh == "lantern" and props.get("hanging"):
            lines.append(f"setblock {p3(*R(lx, 2, lz))} minecraft:stone")
        if sh == "water":
            for dx, dz in DIRV.values():
                lines.append(f"setblock {p3(*R(lx + dx, 1, lz + dz))} minecraft:stone")
                cells.append((lx + dx, lz + dz))
        if sh == "flat" and c["key"] == "lily_pad":
            continue
        lines.append(f"setblock {p3(*R(lx, 1, lz))} {k}")
        if sh == "bed":
            dx, dz = DIRV[_unturn(props["facing"], facing)]
            hbid, hst = states_for(c["key"], dict(props, head=True))
            lines.append(f"setblock {p3(*R(lx + dx, 0, lz + dz))} {base}")
            lines.append(f"setblock {p3(*R(lx + dx, 1, lz + dz))} {block_str(hbid, hst)}")
            cells.append((lx + dx, lz + dz))
        if sh in ("door", "tall_plant") and not props.get("upper"):
            up = dict(props, upper=True)
            ubid, ust = states_for(c["key"], up)
            lines.append(f"setblock {p3(*R(lx, 2, lz))} {block_str(ubid, ust)}")
    if not cells:
        cells = [(sx0, z0)]
    xs = [x for x, _ in cells]
    zs = [z for _, z in cells]
    r = rect_rel(b, facing, min(xs) - 1, min(zs) - 1, max(xs) + 1, max(zs) + 1)
    return lines, r


def _unturn(d, facing):
    from lib.palette import rot_dir
    return rot_dir(d, -turns_for(facing))


def tick_areas(ns, facing, rect, top):
    """Split the load rect into ticking areas of <= 100 chunks (assuming worst-case alignment)."""
    x1, z1, x2, z2 = rect

    def chunks(a, b):
        return (b - a) // 16 + 2   # worst case: span straddles one extra chunk

    areas = []
    span_x = x2 - x1 + 1
    n = 1
    while chunks(0, (span_x + n - 1) // n - 1) * chunks(z1, z2) > TICK_CHUNKS_MAX:
        n += 1
    w = (span_x + n - 1) // n
    for i in range(n):
        ax1 = x1 + i * w
        ax2 = min(x2, ax1 + w - 1)
        areas.append((f"{ns}_{facing}_{i + 1}", (ax1, z1, ax2, z2)))
    return areas
