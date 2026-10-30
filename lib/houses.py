"""Outport buildings: clapboard houses and shops with real staircases and furnished rooms.

All of them face north (door in the north wall). (x, z) is the north-west corner of
the walls, y the ground feet level of the lot (terrace grade); the stone plinth sits at y
and the ground floor stands at y + 1.
"""
from lib import interiors as I
from lib.roofs import cross_gable, hip_roof, two_slope_roof

ROOFS = {
    "deepslate": ("deepslate_tile_stairs", "deepslate_tile_slab", "deepslate_tiles"),
    "dark_oak": ("dark_oak_stairs", "dark_oak_slab", "dark_oak_planks"),
    "spruce": ("spruce_stairs", "spruce_slab", "spruce_planks"),
    "stone": ("stone_brick_stairs", "stone_brick_slab", "stone_bricks"),
    "brick": ("brick_stairs", "brick_slab", "bricks"),
}


def clapboard_house(m, x, z, y, w, d, style="gable", wall="red_concrete", trim="white_concrete",
                    roof="deepslate", storeys=2, h=4, cross=False, plinth="cobblestone", floor="spruce_planks",
                    door="spruce_door", chimney="bricks", window="glass_pane", porch=True, interior="house",
                    seed=0, wood="spruce", rug="red", every=3, step_up=True, veranda=0):
    """A painted clapboard building. style: 'gable', 'saltbox' (long low back slope) or 'biscuit'
    (low hip roof). interior: house, pub, restaurant, shop, inn, office, plant, loft or None.
    Returns info with the door, floors and roof top."""
    x1, z1, x2, z2 = x, z, x + w - 1, z + d - 1
    y0, y_top = y, y + storeys * h
    stairs, cap, ridge = ROOFS[roof]
    door_x = x1 + w // 2

    # plinth, ground floor, walls with corner boards and a trim band at every floor line
    m.box(x1, y0, z1, x2, y0, z2, plinth, walls=True)
    m.box(x1 + 1, y0, z1 + 1, x2 - 1, y0, z2 - 1, floor)
    for xx in range(x1, x2 + 1):
        for zz in range(z1, z2 + 1):
            edge_x, edge_z = xx in (x1, x2), zz in (z1, z2)
            if not (edge_x or edge_z):
                continue
            corner = edge_x and edge_z
            for yy in range(y0 + 1, y_top + 1):
                band = (yy - y0) % h == 0
                m.put(xx, yy, zz, trim if (corner or band) else wall)
    for s in range(1, storeys + 1):
        m.box(x1 + 1, y0 + s * h, z1 + 1, x2 - 1, y0 + s * h, z2 - 1, floor)

    # roof
    if style == "biscuit":
        top = hip_roof(m, x1, z1, x2, z2, y_top + 1, stairs, cap, flat=ridge, rings=2) + 1

        def H(zz):
            return y_top + 1
    else:
        y_back = y_top + 1 - (h if style == "saltbox" else 0)
        H, top = two_slope_roof(m, x1, z1, x2, z2, y_top + 1, y_back, stairs, gable=wall, ridge=ridge, cap=cap)
        if style == "saltbox":   # walls and ceiling that would poke through the long back slope
            for xx in range(x1, x2 + 1):
                for zz in range(z1, z2 + 1):
                    for yy in range(H(zz), y_top + 1):
                        c = m.get(xx, yy, zz)
                        if c is not None and c.tag != "roof":
                            m.clear(xx, yy, zz)
    if cross and style != "biscuit":
        half = max(1, min(2, (w - 5) // 2))
        cross_gable(m, door_x, z1, y_top + 1, half, 3, stairs, wall, cap, window, ridge=ridge)

    # windows: 2 tall on every storey, every `every` cells, never next to a corner or the door
    for s in range(storeys):
        fy = y0 + s * h
        rows = (fy + 2, fy + 3) if h >= 4 else (fy + 2,)
        for side_cells in (
                [(xx, z1) for xx in range(x1, x2 + 1)], [(xx, z2) for xx in range(x1, x2 + 1)],
                [(x1, zz) for zz in range(z1, z2 + 1)], [(x2, zz) for zz in range(z1, z2 + 1)]):
            n = len(side_cells)
            for i in range(2, n - 2):
                if (i - 2) % every != 0 or (n - 1 - i) < 2:
                    continue
                xx, zz = side_cells[i]
                if s == 0 and zz == z1 and abs(xx - door_x) <= 1:
                    continue
                if all(m.is_key(xx, yy, zz, wall) for yy in rows):
                    for yy in rows:
                        m.put(xx, yy, zz, window)

    # front door, step, hood and lanterns
    m.door(door_x, y0 + 1, z1, "south", key=door)
    if step_up and not veranda:
        m.put(door_x, y0, z1 - 1, f"{wood}_stairs", facing="south")
    if veranda:
        # covered front veranda: plank deck at floor level, posts, railing, slab roof, lanterns
        vx1, vx2 = max(x1, door_x - veranda), min(x2, door_x + veranda)
        for xx in range(vx1, vx2 + 1):
            for zz in (z1 - 2, z1 - 1):
                m.put(xx, y0, zz, f"{wood}_planks")
                m.put(xx, y0 + 4, zz, cap)
            if xx in (vx1, vx2):
                for yy in range(y0 + 1, y0 + 4):
                    m.put(xx, yy, z1 - 2, f"{wood}_fence")
            elif xx != door_x:
                m.put(xx, y0 + 1, z1 - 2, f"{wood}_fence")
        if step_up:
            m.put(door_x, y0, z1 - 3, f"{wood}_stairs", facing="south")
        for xx in (door_x - 2, door_x + 2):
            if vx1 < xx < vx2:
                m.put(xx, y0 + 3, z1 - 1, "lantern", hanging=True)
        for xx in (vx1 + 1, vx2 - 1):                       # rocking chairs facing the harbour
            if abs(xx - door_x) > 1:
                m.put(xx, y0 + 1, z1 - 1, f"{wood}_stairs", facing="south")
    elif porch:
        for dx in (-1, 0, 1):
            m.put(door_x + dx, y0 + 3, z1 - 1, cap)
        for dx in (-1, 1):
            m.put(door_x + dx, y0 + 2, z1 - 1, "lantern", hanging=True)

    # staircases up the back wall, alternating direction each storey
    keep = {(door_x, z1 + 1), (door_x, z1 + 2)}
    keeps = {s: set(keep) if s == 0 else set() for s in range(storeys + 1)}
    zr = z2 - 1
    runs = []
    if storeys > 1 and w - 2 >= h + 3:
        for s in range(storeys - 1):
            fy = y0 + s * h
            west = s % 2 == 0
            xa = x2 - 1 if west else x1 + 1
            dx = -1 if west else 1
            for i in range(h):
                sx = xa + dx * i
                m.put(sx, fy + 1 + i, zr, f"{wood}_stairs", facing="west" if west else "east")
                for yy in range(fy + 1, fy + 1 + i):
                    m.put(sx, yy, zr, f"{wood}_planks")
                keeps[s] |= {(sx, zr), (sx, zr - 1)}
                if 1 <= i <= h - 2:
                    m.clear(sx, fy + h, zr)        # hole in the floor above for head room
                keeps[s + 1] |= {(sx, zr), (sx, zr - 1)}
            land = xa + dx * h
            keeps[s + 1] |= {(land, zr), (land, zr - 1), (land - dx, zr - 1)}
            keeps[s] |= {(xa - dx, zr - 1), (xa, zr - 1)}
            runs.append((s, xa, dx))
        m.floor_levels = getattr(m, "floor_levels", [])

    # interior chimney against the west wall, out through the roof
    zc = max(range(z1 + 1, z2), key=lambda zz: (H(zz), -abs(zz - (z1 + z2) // 2)))
    if chimney:
        for yy in range(y0 + 1, top + 2):
            m.put(x1 + 1, yy, zc, chimney)
        m.put(x1 + 1, top + 2, zc, "campfire")
        for s in keeps:
            keeps[s].add((x1 + 1, zc))

    # attic storage under the roof (not for saltbox backs or biscuit tops), ladder from the top storey
    if style == "gable" and storeys >= 1 and h >= 4 and interior in ("house", "inn", "shop", "pub", "restaurant"):
        top_y = y0 + (storeys - 1) * h
        az = z1 + 1
        H0 = H(az)
        # a column whose front-wall backing is solid all the way up (not a window)
        ax = next((xx for xx in range(x2 - 2, x1 + 2, -1)
                   if all(m.is_key(xx, yy, z1, wall, trim) for yy in range(top_y + 1, y_top + 1))
                   and m.empty(xx, y_top + 1, az) and m.empty(xx, y_top + 2, az)
                   and m.empty(xx, y_top + 1, az + 1) and m.empty(xx, y_top + 2, az + 1)), None)
        if ax is not None and H0 > y_top + 2:
            for yy in range(top_y + 1, y_top + 1):
                m.put(ax, yy, az, "ladder", facing="south")
            m.clear(ax, y_top, az)
            m.put(ax, y_top, az, "ladder", facing="south")
            keeps[storeys - 1] |= {(ax, az), (ax, az + 1)}
            for i, xx in enumerate(range(x1 + 2, x2 - 2, 2)):
                zz = (z1 + z2) // 2
                if m.empty(xx, y_top + 1, zz) and H(zz) > y_top + 2:
                    m.put(xx, y_top + 1, zz, "chest" if i % 3 == 0 else "barrel",
                          **({"facing": "south"} if i % 3 == 0 else {"facing": "up"}))
            m.floor("attic", y_top + 1, ax, az, ax, az + 1)

    # interior partition between the two halves, open at the front hall; a stone hearth at the chimney
    if interior == "house" and w >= 13:
        px = door_x
        for s_ in range(storeys):
            fy = y0 + s_ * h
            for zz in range(z1 + 3, z2):
                if (px, zz) in keeps[s_]:
                    continue
                for yy in range(fy + 1, fy + h):
                    if m.empty(px, yy, zz):
                        m.put(px, yy, zz, f"{wood}_planks")
    if chimney and interior in ("house", "pub", "inn"):
        for dz in (-1, 1):
            for yy in (y0 + 1, y0 + 2):
                if m.empty(x1 + 1, yy, zc + dz):
                    m.put(x1 + 1, yy, zc + dz, chimney)
        if m.empty(x1 + 2, y0 + 1, zc):
            m.put(x1 + 2, y0 + 1, zc, "furnace", facing="east")

    # walkable levels for the access check
    for s in range(storeys):
        m.floor(f"storey {s + 1}", y0 + s * h + 1, x1 + 1, z1 + 1, x2 - 1, z2 - 1)

    furnish(m, interior, x1, z1, x2, z2, y0, h, storeys, keeps, seed, wood, rug)
    return dict(rect=(x1, z1, x2, z2), door=(door_x, y0 + 1, z1), top=top, y_top=y_top, H=H)


def furnish(m, kind, x1, z1, x2, z2, y0, h, storeys, keeps, seed, wood, rug):
    if not kind:
        return
    cx = (x1 + x2) // 2

    def room(s, a, b, sd=0):
        return I.Room(m, a, z1 + 1, b, z2 - 1, y0 + s * h + 1, keeps.get(s, ()), seed + s * 7 + sd, wood, ceil=h - 1)

    full = lambda s: room(s, x1 + 1, x2 - 1)            # noqa: E731
    west = lambda s: room(s, x1 + 1, cx - 1, 1)          # noqa: E731
    east = lambda s: room(s, cx + 1, x2 - 1, 2)          # noqa: E731
    colors = ["light_blue", "pink", "yellow", "lime", "cyan", "orange", "magenta", "white"]
    bed_rugs = [colors[(seed + i) % len(colors)] for i in range(6)]

    if kind == "house":
        I.kitchen(east(0), "east")
        I.parlour(west(0), "west", rug, seed)
        for s in range(1, storeys):
            I.bedroom(west(s), "north", bed_rugs[s], ("chest",), seed)
            I.bedroom(east(s), "north", bed_rugs[s + 1], ("flower_pot",), seed + 1)
    elif kind == "pub":
        I.pub(full(0), "south")
        for s in range(1, storeys):
            I.bedroom(west(s), "north", bed_rugs[s])
            I.parlour(east(s), "east", rug, seed)
    elif kind == "restaurant":
        I.restaurant(full(0), "south")
        for s in range(1, storeys):
            I.bedroom(west(s), "north", bed_rugs[s])
            I.kitchen(east(s), "east")
    elif kind == "shop":
        I.shop(full(0), "south")
        for s in range(1, storeys):
            I.loft(full(s))
    elif kind == "inn":
        I.parlour(west(0), "west", rug, seed)
        I.restaurant(east(0), "east")
        for s in range(1, storeys):
            third = (x2 - x1) // 3
            for i, (a, b) in enumerate(((x1 + 1, x1 + third - 1), (x1 + third + 1, x2 - third - 1), (x2 - third + 1, x2 - 1))):
                I.bedroom(room(s, a, b, i), "north", bed_rugs[(s + i) % 6], ("chest",), seed + i)
    elif kind == "office":
        I.office(full(0), "south")
        for s in range(1, storeys):
            I.office(full(s), "south")
    elif kind == "plant":
        I.fish_plant(full(0))
    elif kind == "school":
        I.school(full(0), "north")
        for s in range(1, storeys):
            I.school(full(s), "north")
    elif kind == "hall":
        I.hall(full(0), "south")
    elif kind == "loft":
        I.loft(full(0))
        for s in range(1, storeys):
            I.loft(full(s))


def cupola(m, cx, cz, top, glass="glass_pane", corner="white_concrete", cap="brick_slab"):
    """3x3 glazed lookout (or bell cupola) sitting on a roof ridge whose highest block is `top`."""
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if dx or dz:
                for yy in (top + 1, top + 2):
                    m.put(cx + dx, yy, cz + dz, corner if (dx and dz) else glass)
            m.put(cx + dx, top + 3, cz + dz, cap)
    m.put(cx, top + 4, cz, "iron_bars")


def shed(m, x, z, y, w=5, d=4, wall="spruce_planks", roof="spruce"):
    """Small garden shed, door to the north."""
    return clapboard_house(m, x, z, y, w, d, style="gable", wall=wall, trim="dark_oak_planks", roof=roof, storeys=1,
                           h=3, interior=None, porch=False, chimney=None)


# ---------------------------------------------------------------- lots that can face any way
def lot_size(spec):
    """(claim width, claim depth) in the lot's own frame: house plus 2 around, 4 in front, 3 behind."""
    return spec["w"] + 4, spec["d"] + 7


def lot_frames(spec):
    w, d = spec["w"], spec["d"]
    return dict(claim=(-2, -4, w + 1, d + 2), pad=(-2, -4, w + 1, d + 2), walls=(0, 0, w - 1, d - 1))


def house_lot(m, X, Z, g, turns, spec, seed=0):
    """A house with its garden, built facing north in its own frame then turned `turns` quarter
    turns clockwise and stamped with its claim rect's north-west corner at (X, Z). The lot is
    flat at feet level g (the caller pads the ground). Returns placement info in world coords."""
    import random
    from lib.outdoor import TALL, crop_bed  # noqa: F401
    from lib.voxel import rect_through, stamp_transform
    from lib.landmarks import clothesline
    from lib.harbour import dory
    from lib.palette import rot_dir
    r = random.Random(seed)
    w, d = spec["w"], spec["d"]
    sub = m.sub()
    info = clapboard_house(sub, 0, 0, g, w, d, style=spec["style"], wall=spec["wall"],
                           trim=spec.get("trim", "white_concrete"), roof=spec["roof"],
                           storeys=spec.get("storeys", 2), h=spec.get("h", 5), cross=spec.get("cross", False),
                           interior=spec.get("interior", "house"), seed=seed, rug=spec.get("rug", "red"),
                           veranda=spec.get("veranda", 3), chimney=spec.get("chimney", "bricks"),
                           every=spec.get("every", 3))
    dx = info["door"][0]
    # front: fence with a gate, flowers
    if spec.get("fence", r.random() < 0.6):
        fence = spec.get("fence_key", r.choice(["birch_fence", "birch_fence", "spruce_fence", "oak_fence"]))
        gate = {"birch_fence": "birch_fence_gate", "spruce_fence": "spruce_fence_gate", "oak_fence": "oak_fence_gate"}[fence]
        for x in range(-2, w + 2):
            if x == dx:
                sub.put(x, g, -4, gate, facing="south")
            elif r.random() > 0.08:
                sub.put(x, g, -4, fence)
        for z in range(-3, d + 3):
            for x in (-2, w + 1):
                if r.random() > 0.15:
                    sub.put(x, g, z, fence)
    for x in range(-1, w + 1):
        if abs(x - dx) > 1 and sub.empty(x, g, -3) and r.random() < 0.55:
            sub.put(x, g - 1, -3, "grass_block")
            sub.put(x, g, -3, r.choice(["allium", "allium", "lilac", "blue_orchid", "poppy", "oxeye_daisy", "cornflower"]))
    for x in range(-1, w + 1):                    # replant any lilac as a proper two-block plant
        c = sub.get(x, g, -3)
        if c is not None and c.key in TALL:
            sub.clear(x, g, -3)
            if sub.empty(x, g + 1, -3):
                sub.tall_plant(x, g, -3, c.key)
    # back garden: two of veg bed / woodpile / clothesline / dory / shed
    kinds = spec.get("yard") or r.sample(["veg", "wood", "line", "dory", "shed", "veg"], 2)
    halves = [(0, w // 2 - 1), (w // 2, w - 1)]
    for (a, b), kind in zip(halves, kinds):
        zb = d + 1
        if kind == "veg" and b - a >= 3:
            crop_bed(sub, a, zb, b, zb + 1, crop=r.choice(["potatoes", "carrots", "beetroot"]), y=g,
                     water_rows=[zb])
        elif kind == "wood":
            for x in range(a, min(b, a + 4) + 1):
                for yy in (g, g + 1):
                    sub.put(x, yy, zb, "spruce_log", axis="x")
        elif kind == "line" and b - a >= 3:
            clothesline(sub, a, b, zb, g)
        elif kind == "dory" and b - a >= 4:
            sub.put(a, g, zb, "spruce_log", axis="x")
            sub.put(a + 4, g, zb, "spruce_log", axis="x")
            dory(sub, a, zb, y=g + 1, along="x", color=r.choice(["blue_concrete", "red_concrete", "yellow_concrete", "green_concrete"]))
        elif kind == "shed":
            for k, x in enumerate(range(a + 1, min(b, a + 4))):
                key = ["barrel", "composter", "barrel"][k % 3]
                sub.put(x, g, zb, key, **({"facing": "up"} if key == "barrel" else {}))
    fr = lot_frames(spec)
    T = stamp_transform(fr["claim"], X, Z, turns)
    m.stamp(sub, X, Z, turns, anchor=fr["claim"])
    out_dir = rot_dir("north", turns)
    return dict(claim=rect_through(T, fr["claim"]), pad=rect_through(T, fr["pad"]), walls=rect_through(T, fr["walls"]),
                door=T(*info["door"]), front=T(dx, g, -5), out=out_dir, g=g)
