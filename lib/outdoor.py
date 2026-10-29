"""Outdoor helpers: decks on piles, stair runs, trees, paths, gardens, fences."""
import random

from lib.voxel import DIRV, OPP


# ---------------------------------------------------------------- decks & stairs
def deck_on_piles(m, x1, z1, x2, z2, y, deck="spruce_planks", pile="spruce_log", every=3,
                  bottom=-1, railing="spruce_fence", openings=()):
    """Plank deck at height y on log piles that run down to `bottom` (seabed or grade).

    openings: (x, z) cells on the edge left free of railing (for stairs / a gate).
    """
    xa, xb = sorted((x1, x2))
    za, zb = sorted((z1, z2))
    xs = sorted(set(list(range(xa, xb + 1, every)) + [xb]))
    zs = sorted(set(list(range(za, zb + 1, every)) + [zb]))
    for x in xs:
        for z in zs:
            for yy in range(bottom, y):
                m.put(x, yy, z, pile, axis="y")
    m.box(xa, y, za, xb, y, zb, deck)
    if railing:
        for x in range(xa, xb + 1):
            for z in range(za, zb + 1):
                if (x in (xa, xb) or z in (za, zb)) and (x, z) not in openings:
                    m.put(x, y + 1, z, railing)


def stair_run(m, x, y, z, direction, steps, width=1, key="spruce_stairs", support=None, across=None):
    """Stairs climbing `steps` blocks toward `direction`, starting at (x, y, z).

    support: block placed under each stair down to y (so nothing floats).
    across: direction the width extends (default: right of `direction`).
    """
    dx, dz = DIRV[direction]
    ax, az = DIRV[across or {"north": "east", "east": "south", "south": "west", "west": "north"}[direction]]
    for i in range(steps):
        for w in range(width):
            px, pz = x + dx * i + ax * w, z + dz * i + az * w
            m.put(px, y + i, pz, key, facing=direction)
            if support:
                for yy in range(y, y + i):
                    m.put(px, yy, pz, support)
    return x + dx * steps, y + steps, z + dz * steps


# ---------------------------------------------------------------- trees
def oak_tree(m, x, y, z, height=5, seed=0, log="oak_log", leaves="oak_leaves", radius=2):
    """Classic round-topped tree. (x, y, z) is the base of the trunk (y=0 on grass)."""
    r = random.Random(seed)
    top = y + height - 1
    for yy in range(y, top + 1):
        m.put(x, yy, z, log, axis="y")
    layers = [(top - 2, radius), (top - 1, radius), (top, radius - 1), (top + 1, radius - 1)]
    for ly, rad in layers:
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                corner = abs(dx) == rad and abs(dz) == rad
                if corner and (ly >= top or r.random() < 0.6):
                    continue
                if ly == top + 1 and (abs(dx) + abs(dz)) > 1:
                    continue
                if m.empty(x + dx, ly, z + dz):
                    m.put(x + dx, ly, z + dz, leaves)
    return top + 1


def spruce_tree(m, x, y, z, height=8, seed=0, log="spruce_log", leaves="spruce_leaves"):
    r = random.Random(seed)
    top = y + height - 1
    for yy in range(y, top):
        m.put(x, yy, z, log, axis="y")
    rad = 0
    for ly in range(top, y + 2, -1):
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                if abs(dx) + abs(dz) > rad + (1 if rad > 1 else 0):
                    continue
                if m.empty(x + dx, ly, z + dz):
                    m.put(x + dx, ly, z + dz, leaves)
        rad = rad + 1 if rad < 3 and (top - ly) % 2 == 0 else max(1, rad - (1 if r.random() < 0.4 else 0))
    m.put(x, top + 1, z, leaves)
    return top + 1


def bush(m, x, y, z, leaves="oak_leaves", size=1):
    for dx in range(-size + 1, size):
        for dz in range(-size + 1, size):
            m.put(x + dx, y, z + dz, leaves)
    if size > 1:
        m.put(x, y + 1, z, leaves)


# ---------------------------------------------------------------- paths
def line(p, q):
    """Grid cells from p to q (Bresenham), inclusive."""
    (x0, z0), (x1, z1) = p, q
    dx, dz = abs(x1 - x0), -abs(z1 - z0)
    sx, sz = (1 if x1 > x0 else -1), (1 if z1 > z0 else -1)
    err = dx + dz
    out = []
    while True:
        out.append((x0, z0))
        if (x0, z0) == (x1, z1):
            return out
        e2 = 2 * err
        if e2 >= dz:
            err += dz
            x0 += sx
        if e2 <= dx:
            err += dx
            z0 += sz


def path(m, points, width=1, key="dirt_path", y=-1, mix=None, seed=1):
    """Path through (x, z) points, set into the grade layer.

    mix: {block: fraction} sprinkled in, e.g. {"gravel": 0.15, "coarse_dirt": 0.1}.
    Cells with something standing on them (y+1 occupied) keep grass instead.
    """
    r = random.Random(seed)
    cells = []
    for a, b in zip(points, points[1:]):
        cells += line(a, b)
    out = set()
    for (x, z) in cells:
        for dx in range(width):
            for dz in range(width):
                out.add((x + dx - width // 2, z + dz - width // 2))
    for (x, z) in sorted(out):
        k = key
        for alt, frac in (mix or {}).items():
            if r.random() < frac:
                k = alt
                break
        if m.empty(x, y + 1, z) or k != "dirt_path":
            m.put(x, y, z, k)
    return out


# ---------------------------------------------------------------- garden
def fence_ring(m, x1, z1, x2, z2, y=0, key="oak_fence", gates=(), gate="oak_fence_gate", skip=()):
    """Fence around a rectangle. gates: [(x, z, facing)] gate cells (facing = way through)."""
    gate_cells = {(gx, gz): f for gx, gz, f in gates}
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            if not (x in (x1, x2) or z in (z1, z2)) or (x, z) in skip:
                continue
            if (x, z) in gate_cells:
                m.put(x, y, z, gate, facing=gate_cells[(x, z)])
            else:
                m.put(x, y, z, key)


def crop_bed(m, x1, z1, x2, z2, crop="wheat", water_rows=None, age=7, rim=None, y=0):
    """Farmland at grade with crops on top and a water channel (keeps it hydrated).

    water_rows: z (or x, if the bed is taller than wide) indices of water channels;
    default: one through the middle. rim: optional block ringing the bed at grade.
    """
    wide = (x2 - x1) >= (z2 - z1)
    if water_rows is None:
        water_rows = [(z1 + z2) // 2] if wide else [(x1 + x2) // 2]
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            row = z if wide else x
            if row in water_rows:
                m.put(x, y - 1, z, "water")
            else:
                m.put(x, y - 1, z, "farmland")
                m.put(x, y, z, crop, age=age)
    if rim:
        for x in range(x1 - 1, x2 + 2):
            for z in range(z1 - 1, z2 + 2):
                if x in (x1 - 1, x2 + 1) or z in (z1 - 1, z2 + 1):
                    m.put(x, y - 1, z, rim)


TALL = {"lilac", "rose_bush", "peony", "sunflower", "tall_grass", "large_fern"}


def flower_bed(m, x1, z1, x2, z2, flowers=("poppy", "dandelion", "cornflower", "oxeye_daisy"),
               density=0.8, seed=3, soil="grass_block", y=0):
    """Flowers on grass. soil: block written under each flower so it always has soil."""
    r = random.Random(seed)
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            if r.random() > density or not m.empty(x, y, z) or not m.empty(x, y + 1, z):
                continue
            f = r.choice(flowers)
            if soil:
                m.put(x, y - 1, z, soil)
            if f in TALL:
                m.tall_plant(x, y, z, f)
            else:
                m.put(x, y, z, f)


def lamp_post(m, x, y, z, height=3, post="oak_fence", lantern="lantern", base=None):
    """Fence post with a lantern standing on top."""
    if base:
        m.put(x, y, z, base)
        y += 1
    for yy in range(y, y + height):
        m.put(x, yy, z, post)
    m.put(x, y + height, z, lantern, hanging=False)


def bench(m, x, y, z, facing, length=2, key="spruce_stairs"):
    """Stair bench you sit on facing `facing` (backs to OPP[facing])."""
    dx, dz = DIRV[{"north": "east", "south": "east", "east": "south", "west": "south"}[facing]]
    for i in range(length):
        m.put(x + dx * i, y, z + dz * i, key, facing=OPP[facing])
