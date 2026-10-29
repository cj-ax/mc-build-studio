"""Roofs. All stairs are regular (bottom-half); the ridge runs along `ridge`."""
from lib.voxel import DIRV, OPP


def gable_roof(m, x1, z1, x2, z2, y, ridge="x", stairs="spruce_stairs", cap="spruce_slab",
               gable="oak_planks", overhang=1, gable_overhang=1):
    """Gable roof over the wall rectangle x1..x2, z1..z2 (inclusive).

    y is the height of the lowest (eave) stair row, normally wall top + 1.
    The gable ends (the walls the ridge points at) are filled with `gable`
    under the stairs. Returns the ridge height.
    """
    if ridge == "x":
        a1, a2, b1, b2 = z1, z2, x1, x2          # slope across z, run along x
        low_side, high_side = "north", "south"
    else:
        a1, a2, b1, b2 = x1, x2, z1, z2
        low_side, high_side = "west", "east"

    def P(a, b):  # (across, along) -> (x, z)
        return (b, a) if ridge == "x" else (a, b)

    start, end = a1 - overhang, a2 + overhang
    n = end - start + 1
    half = n // 2
    run = range(b1 - gable_overhang, b2 + gable_overhang + 1)
    with m.tag("roof"):
        for i in range(half):
            for b in run:
                # near slope rises toward high_side; far slope mirrors it
                x, z = P(start + i, b)
                m.put(x, y + i, z, stairs, facing=high_side)
                x, z = P(end - i, b)
                m.put(x, y + i, z, stairs, facing=low_side)
        top = y + half - 1
        if n % 2:  # odd width: a full ridge row, capped with a slab
            for b in run:
                x, z = P(start + half, b)
                m.put(x, y + half - 1, z, gable)
                m.put(x, y + half, z, cap)
            top = y + half
        elif cap:
            for b in run:
                for a in (start + half - 1, start + half):
                    x, z = P(a, b)
                    m.put(x, y + half, z, cap)
            top = y + half
    # gable triangles under the stairs, in the end walls
    for b in (b1, b2):
        for a in range(a1, a2 + 1):
            i = min(a - start, end - a)
            hi = y + i - 1 if (n % 2 == 0 or a != start + half) else y + half - 2
            for yy in range(y, hi + 1):
                x, z = P(a, b)
                m.put(x, yy, z, gable)
    return top


def shed_roof(m, x1, z1, x2, z2, y, rises="south", stairs="spruce_stairs", overhang=1, wall="oak_planks"):
    """Single slope rising toward `rises` over the wall rectangle x1..x2, z1..z2.

    y is the height of the lowest stair row (wall top + 1). The walls are raised
    with `wall` under the slope so the roof sits on them.
    """
    dx, dz = DIRV[rises]

    def rise(x, z):
        return (x - (x1 - overhang)) if dx > 0 else (x2 + overhang - x) if dx < 0 else \
            (z - (z1 - overhang)) if dz > 0 else (z2 + overhang - z)

    with m.tag("roof"):
        for x in range(x1 - overhang, x2 + overhang + 1):
            for z in range(z1 - overhang, z2 + overhang + 1):
                m.put(x, y + rise(x, z), z, stairs, facing=rises)
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            if x in (x1, x2) or z in (z1, z2):
                for yy in range(y, y + rise(x, z)):
                    m.put(x, yy, z, wall)
    return y + rise(x2 if dx > 0 else x1, z2 if dz > 0 else z1)


__all__ = ["gable_roof", "shed_roof", "OPP"]
