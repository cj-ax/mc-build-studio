"""Landmarks and terrace pieces: lighthouse, church, flagpole, root cellar, retaining walls,
terrace stairs, roads, clotheslines, boulders."""
import random

from lib.roofs import hip_roof, two_slope_roof
from lib.voxel import OPP


def disk(cx, cz, r):
    return [(x, z) for x in range(cx - r, cx + r + 1) for z in range(cz - r, cz + r + 1)
            if (x - cx) ** 2 + (z - cz) ** 2 <= r * r + r]


def ring(cx, cz, r):
    inner = set(disk(cx, cz, r - 1))
    return [c for c in disk(cx, cz, r) if c not in inner]


# ---------------------------------------------------------------- lighthouse
def lighthouse(m, cx, cz, y, height=20, r=4, bands=("white_concrete", "red_concrete"), band=4,
               cap=("brick_stairs", "brick_slab", "bricks")):
    """Round tower in coloured bands, ladder inside, gallery with railing, glazed lantern room
    with a sea lantern, hipped cap. Door faces north."""
    wall = ring(cx, cz, r)
    inside = disk(cx, cz, r - 1)
    for (x, z) in disk(cx, cz, r):
        m.put(x, y, z, "stone_bricks")                      # base floor
    for yy in range(y + 1, y + height):
        b = bands[((yy - y - 1) // band) % len(bands)]
        for (x, z) in wall:
            m.put(x, yy, z, b)
    gy = y + height                                          # gallery floor
    for (x, z) in disk(cx, cz, r + 1):
        m.put(x, gy, z, "smooth_stone")
    # ladder up the inside of the south wall, through the gallery floor
    lz = cz + r - 1
    for yy in range(y + 1, gy + 1):
        m.put(cx, yy, lz, "ladder", facing="north")
    for (x, z) in ring(cx, cz, r + 1):
        m.put(x, gy + 1, z, "iron_bars")
    # lantern room: glass ring around a lamp (leaving a walkway where the ladder comes up), cap roof
    for (x, z) in ring(cx, cz, r - 2):
        for yy in range(gy + 1, gy + 4):
            m.put(x, yy, z, "glass_pane" if yy < gy + 3 else "iron_block")
    m.put(cx, gy + 1, cz, "iron_block")
    m.put(cx, gy + 2, cz, "sea_lantern")
    m.put(cx, gy + 3, cz, "glowstone")
    hip_roof(m, cx - r + 2, cz - r + 2, cx + r - 2, cz + r - 2, gy + 4, cap[0], cap[1], cap[2], overhang=0)
    m.put(cx, gy + 4 + r - 1, cz, "iron_bars")
    # door, windows
    m.door(cx, y + 1, cz - r, "south", key="spruce_door")
    m.put(cx, y, cz - r - 1, "stone_brick_stairs", facing="south")
    for yy in range(y + 5, gy - 1, 5):
        for (x, z) in ((cx + r, cz), (cx - r, cz)):
            m.put(x, yy, z, "glass_pane")
    m.floor("lighthouse", y + 1, cx - r + 1, cz - r + 1, cx + r - 1, cz + r - 1)
    m.floor("gallery", gy + 1, cx - r, cz - r, cx + r, cz + r)
    return gy


# ---------------------------------------------------------------- church
def church(m, x, z, y, w=13, d=26, wall="white_concrete", trim="light_gray_concrete", roof=("deepslate_tile_stairs",
           "deepslate_tile_slab", "deepslate_tiles"), h=7):
    """White clapboard church: nave with tall stained-glass windows, steep gable roof, a square
    bell tower at the north (front) end with belfry, bell and spire. Pews, aisle, altar."""
    stairs, cap, ridge = roof
    x1, z1, x2, z2 = x, z, x + w - 1, z + d - 1
    m.box(x1, y, z1, x2, y, z2, "stone_bricks", walls=True)
    m.box(x1 + 1, y, z1 + 1, x2 - 1, y, z2 - 1, "dark_oak_planks")
    for xx in range(x1, x2 + 1):
        for zz in range(z1, z2 + 1):
            if xx in (x1, x2) or zz in (z1, z2):
                corner = xx in (x1, x2) and zz in (z1, z2)
                for yy in range(y + 1, y + h + 1):
                    m.put(xx, yy, zz, trim if corner or yy == y + h else wall)
    # tall windows: 3 high, colours alternating
    glass = ["blue_glass_pane", "red_glass_pane", "yellow_glass_pane", "purple_glass_pane"]
    for i, zz in enumerate(range(z1 + 3, z2 - 1, 3)):
        for xx in (x1, x2):
            for yy in range(y + 2, y + 5):
                m.put(xx, yy, zz, glass[i % len(glass)] if yy > y + 2 else "white_glass_pane")
    m.box(x1 + 1, y + h, z1 + 1, x2 - 1, y + h, z2 - 1, "spruce_planks")
    H, top = two_slope_roof(m, x1, z1, x2, z2, y + h + 1, y + h + 1, stairs, gable=wall, ridge=ridge, cap=cap)
    # rose window in the back gable
    m.put((x1 + x2) // 2, y + h + 2, z2, "purple_glass_pane")
    # tower at the front
    tx1, tx2 = (x1 + x2) // 2 - 2, (x1 + x2) // 2 + 2
    tz1, tz2 = z1 - 5, z1 - 1
    th = h + 9
    m.box(tx1, y, tz1, tx2, y, tz2, "stone_bricks")
    for xx in range(tx1, tx2 + 1):
        for zz in range(tz1, tz2 + 1):
            if xx in (tx1, tx2) or zz in (tz1, tz2):
                corner = xx in (tx1, tx2) and zz in (tz1, tz2)
                for yy in range(y + 1, y + th + 1):
                    m.put(xx, yy, zz, trim if corner or yy in (y + h, y + th) else wall)
    tcx = (tx1 + tx2) // 2
    # open the tower into the nave and give it double doors at the front
    for yy in (y + 1, y + 2):
        m.clear(tcx, yy, tz2)
        m.clear(tcx, yy, z1)
    m.door(tcx, y + 1, tz1, "south", key="dark_oak_door")
    m.put(tcx, y, tz1 - 1, "stone_brick_stairs", facing="south")
    # belfry: floor, louvred openings, bell
    bf = y + th - 4
    m.box(tx1 + 1, bf, tz1 + 1, tx2 - 1, bf, tz2 - 1, "spruce_planks")
    for yy in range(bf + 1, bf + 3):
        for (xx, zz) in ((tcx, tz1), (tcx, tz2), (tx1, (tz1 + tz2) // 2), (tx2, (tz1 + tz2) // 2)):
            m.put(xx, yy, zz, "iron_bars")
    m.put(tcx, y + th - 1, (tz1 + tz2) // 2, "bell", hanging=True, facing="north")
    m.box(tx1 + 1, y + th, tz1 + 1, tx2 - 1, y + th, tz2 - 1, "spruce_planks")
    # ladder up the tower's east inner wall to the belfry
    for yy in range(y + 1, bf + 1):
        m.put(tx2 - 1, yy, tz1 + 2, "ladder", facing="west")
    m.clear(tx2 - 1, bf, tz1 + 2)
    m.put(tx2 - 1, bf, tz1 + 2, "ladder", facing="west")
    m.floor("belfry", bf + 1, tx1 + 1, tz1 + 1, tx2 - 1, tz2 - 1)
    # spire
    sp = hip_roof(m, tx1, tz1, tx2, tz2, y + th + 1, stairs, cap, ridge, overhang=0)
    m.put(tcx, sp + 1, (tz1 + tz2) // 2, "iron_bars")
    m.put(tcx, sp + 2, (tz1 + tz2) // 2, "iron_bars")
    # nave: pews facing the altar (south), aisle carpet, altar, candles
    ax = (x1 + x2) // 2
    for zz in range(z1 + 2, z2 - 5, 2):
        for xx in range(x1 + 2, x2 - 1):
            if abs(xx - ax) <= 0:
                continue
            m.put(xx, y + 1, zz, "dark_oak_stairs", facing="north")
    for zz in range(z1 + 1, z2 - 3):
        m.put(ax, y + 1, zz, "red_carpet")
    m.box(ax - 1, y + 1, z2 - 2, ax + 1, y + 1, z2 - 2, "smooth_quartz")
    m.put(ax - 1, y + 2, z2 - 2, "white_candle")
    m.put(ax + 1, y + 2, z2 - 2, "white_candle")
    m.put(ax, y + 1, z2 - 4, "lectern", facing="north")
    m.put(x1 + 1, y + 1, z2 - 1, "jukebox")
    for zz in range(z1 + 3, z2 - 1, 6):
        m.put(ax, y + h - 1, zz, "lantern", hanging=True)
    m.floor("nave", y + 1, x1 + 1, z1 + 1, x2 - 1, z2 - 1)
    return dict(tower=(tx1, tz1, tx2, tz2), top=sp + 2)


def graveyard(m, x1, z1, x2, z2, y, seed=0, fence="birch_fence"):
    r = random.Random(seed)
    for xx in range(x1 + 2, x2 - 1, 3):
        for zz in range(z1 + 2, z2 - 1, 3):
            if r.random() < 0.75:
                m.put(xx, y, zz, r.choice(["stone_brick_wall", "cobblestone_wall", "andesite"]))
                if r.random() < 0.3:
                    m.put(xx, y - 1, zz + 1, "grass_block")
                    m.put(xx, y, zz + 1, r.choice(["poppy", "oxeye_daisy", "cornflower"]))


# ---------------------------------------------------------------- small pieces
def flagpole(m, x, z, y, height=9, flag=("pink_wool", "white_wool", "green_wool")):
    """Pole with a three-stripe flag (Newfoundland pink, white and green)."""
    for yy in range(y, y + height):
        m.put(x, yy, z, "iron_bars" if yy > y else "stone_brick_wall")
    for i, colour in enumerate(flag):
        for k in range(3):
            m.put(x + 1 + i, y + height - 1 - k, z, colour)


def root_cellar(m, x, z, y, depth=4, width=3, door="spruce_door", seed=0):
    """Sod-roofed root cellar mound with its door facing north. (x, z) is the door cell."""
    hw = width // 2
    x1, x2, z1, z2 = x - hw - 1, x + hw + 1, z, z + depth + 1
    for xx in range(x1, x2 + 1):
        for zz in range(z1, z2 + 1):
            for yy in range(y, y + 3):
                inside = x1 < xx < x2 and z1 < zz < z2 and yy < y + 2
                if inside:
                    m.air(xx, yy, zz)
                else:
                    m.put(xx, yy, zz, "cobblestone" if yy < y + 2 else "moss_block")
    for xx in range(x1 + 1, x2):
        for zz in range(z1 + 1, z2):
            m.put(xx, y + 3, zz, "moss_block" if (xx + zz) % 2 else "grass_block")
    m.door(x, y, z, "south", key=door)
    r = random.Random(seed)
    for zz in range(z1 + 2, z2):            # barrels of potatoes and turnips down both sides
        for xx in (x1 + 1, x2 - 1):
            if xx != x:
                k = "barrel" if r.random() < 0.7 else "composter"
                m.put(xx, y, zz, k, **({"facing": "up"} if k == "barrel" else {}))
    m.put(x, y + 1, z2 - 1, "lantern", hanging=True)


def wall_cellar(m, x, z_wall, y, depth=3, half=1, door="spruce_door", seed=0, stash=False):
    """Root cellar dug into a retaining wall facing north: door in the wall at (x, y, z_wall),
    a stone-lined room behind it (inside the upper terrace), barrels of vegetables, a lantern.
    stash=True fills it with something more interesting than turnips."""
    r = random.Random(seed)
    zs = range(z_wall + 1, z_wall + depth + 2)
    for xx in range(x - half - 1, x + half + 2):
        for zz in zs:
            for yy in range(y - 1, y + 3):
                inside = abs(xx - x) <= half and zz <= z_wall + depth and y <= yy <= y + 1
                if inside:
                    m.air(xx, yy, zz)
                else:
                    m.put(xx, yy, zz, "cobblestone" if r.random() > 0.2 else "mossy_cobblestone")
    m.door(x, y, z_wall, "south", key=door)
    goods = (["barrel", "brewing_stand", "barrel", "chest"] if stash else ["barrel", "composter", "barrel"])
    i = 0
    for zz in range(z_wall + 2, z_wall + depth + 1):
        for xx in (x - half, x + half):
            if xx == x:
                continue
            k = goods[i % len(goods)]
            i += 1
            if k == "brewing_stand":
                m.put(xx, y, zz, "barrel", facing="up")
                m.put(xx, y + 1, zz, "brewing_stand")
            elif k == "chest":
                m.put(xx, y, zz, "chest", facing="east" if xx < x else "west")
            else:
                m.put(xx, y, zz, k, **({"facing": "up"} if k == "barrel" else {}))
    m.put(x, y, z_wall + depth, "barrel", facing="up")
    m.put(x, y + 1, z_wall + 1, "lantern", hanging=True)


def retaining_wall(m, x1, x2, z, y_lo, y_top, block="stone_bricks", parapet="stone_brick_wall", gaps=(), seed=0):
    """Stone wall facing north at row z: from y_lo up to y_top - 1 (the upper terrace's ground),
    parapet on top at y_top except at gaps (x ranges for stairs)."""
    r = random.Random(seed)
    gx = set()
    for a, b in gaps:
        gx |= set(range(a, b + 1))
    for x in range(x1, x2 + 1):
        for yy in range(y_lo, y_top):
            m.put(x, yy, z, block if r.random() > 0.12 else r.choice(["mossy_stone_bricks", "cracked_stone_bricks"]))
        if parapet and x not in gx:
            m.put(x, y_top, z, parapet)


def terrace_stairs(m, x, z_wall, y_lo, rise, width=3, key="stone_brick_stairs", support="stone_bricks"):
    """Stairs climbing south from the lower terrace through a retaining wall at row z_wall.
    The last stair is in the wall row; the upper terrace starts at z_wall + 1."""
    for i in range(rise):
        zz = z_wall - (rise - 1) + i
        for w in range(width):
            m.put(x + w, y_lo + i, zz, key, facing="south")
            for yy in range(y_lo, y_lo + i):
                m.put(x + w, yy, zz, support)
        # side walls for the stair cut
    return z_wall + 1


def road(m, x1, z1, x2, z2, y, key="gravel", mix=None, seed=0, over=True):
    """Road surface set into the ground layer at y (= grade - 1). over=False keeps blocks
    already there (e.g. the stone ceiling of a root cellar)."""
    r = random.Random(seed)
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            k = key
            for alt, frac in (mix or {}).items():
                if r.random() < frac:
                    k = alt
                    break
            if over or m.empty(x, y, z):
                m.put(x, y, z, k)


def clothesline(m, x1, x2, z, y, colours=("white_wool", "light_blue_wool", "red_wool")):
    for x in (x1, x2):
        m.put(x, y, z, "spruce_fence")
        m.put(x, y + 1, z, "spruce_fence")
    for x in range(x1 + 1, x2):
        m.put(x, y + 2, z, "iron_chain", axis="x")
    for x in (x1, x2):
        m.put(x, y + 2, z, "spruce_fence")


def boulder(m, x, z, y, size=2, seed=0, stones=("stone", "andesite", "tuff", "mossy_cobblestone")):
    r = random.Random(seed)
    for dx in range(-size, size + 1):
        for dz in range(-size, size + 1):
            hgt = size - max(abs(dx), abs(dz)) + (1 if r.random() < 0.4 else 0)
            for yy in range(y, y + hgt):           # solid columns: nothing hangs
                m.put(x + dx, yy, z + dz, r.choice(stones))


def gazebo(m, cx, cz, y, r=3, post="white_concrete", rail="birch_fence", roof=("dark_oak_stairs", "dark_oak_slab",
           "dark_oak_planks")):
    """Round-ish gazebo on a stone floor: posts, a low railing with an opening to the north,
    benches inside, a hipped roof."""
    for (x, z) in disk(cx, cz, r):
        m.put(x, y - 1, z, "stone_bricks")
    edge = ring(cx, cz, r)
    for (x, z) in edge:
        door = x == cx and z < cz
        corner = not door and (abs(x - cx) == abs(z - cz) or (x - cx in (-r, r) and z == cz) or
                               (z - cz in (-r, r) and x == cx))
        if corner:
            for yy in range(y, y + 3):
                m.put(x, yy, z, post)
        elif not door:
            m.put(x, y, z, rail)
    for (x, z) in edge:
        m.put(x, y + 3, z, roof[2])
    for (x, z) in disk(cx, cz, r - 1):
        m.put(x, y + 3, z, roof[2])
    hip_roof(m, cx - r, cz - r, cx + r, cz + r, y + 4, roof[0], roof[1], roof[2], overhang=0)
    for (x, z) in ((cx - 1, cz + r - 1), (cx, cz + r - 1), (cx + 1, cz + r - 1)):
        m.put(x, y, z, "dark_oak_stairs", facing="south")
    m.put(cx, y + 2, cz, "lantern", hanging=True)
    m.floor("gazebo", y, cx - r + 1, cz - r + 1, cx + r - 1, cz + r - 1)


def power_line(m, x1, x2, z, y, every=14, height=7, wire="iron_chain"):
    """Wooden telephone poles along x with a crossarm and two wires strung between them."""
    xs = list(range(x1, x2 + 1, every))
    if xs[-1] != x2:
        xs.append(x2)
    for x in xs:
        for yy in range(y, y + height):
            m.put(x, yy, z, "spruce_fence" if yy > y else "spruce_log", **({} if yy > y else {"axis": "y"}))
        for dz in (-1, 1):
            m.put(x, y + height - 1, z + dz, "spruce_fence")
    for a, b in zip(xs, xs[1:]):
        for x in range(a + 1, b):
            for dz in (-1, 1):
                m.put(x, y + height - 1, z + dz, wire, axis="x")


def awning(m, x1, x2, z, y, colours=("red_wool", "white_wool")):
    """Striped awning sticking out one block from a north wall at row z (wall at z + 1)."""
    for i, x in enumerate(range(x1, x2 + 1)):
        m.put(x, y, z, colours[i % len(colours)])


def pot_stack(m, x, z, y, n=3, seed=0):
    r = random.Random(seed)
    for i in range(n):
        for k in range(r.randint(1, 3)):
            m.put(x + i, y + k, z, "barrel" if (i + k) % 2 else "composter", **({"facing": "up"} if (i + k) % 2 else {}))
