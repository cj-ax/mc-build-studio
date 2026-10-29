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


def two_slope_roof(m, x1, z1, x2, z2, y_front, y_back, stairs="deepslate_tile_stairs", gable="white_concrete",
                   ridge="deepslate_tiles", cap="deepslate_tile_slab", overhang=1, gable_overhang=1, fill_gables=True):
    """Ridge along x. The front (north) slope starts at y_front over the front eave, the back
    slope at y_back over the back eave; each rises one block per row until they meet.
    y_front == y_back is a plain gable; y_back = y_front - storey height is a saltbox.
    Returns (H, top): H(z) = height of the roof surface block over row z.
    """
    zf, zb = z1 - overhang, z2 + overhang

    def H(z):
        return min(y_front + (z - zf), y_back + (zb - z))

    xs = range(x1 - gable_overhang, x2 + gable_overhang + 1)
    top = -10 ** 9
    with m.tag("roof"):
        for z in range(zf, zb + 1):
            hf, hb = y_front + (z - zf), y_back + (zb - z)
            for x in xs:
                if hf < hb:
                    m.put(x, hf, z, stairs, facing="south")
                elif hb < hf:
                    m.put(x, hb, z, stairs, facing="north")
                else:
                    m.put(x, hf, z, ridge)
                    if cap:
                        m.put(x, hf + 1, z, cap)
            top = max(top, min(hf, hb))
        # back-to-back stairs at an even ridge get a slab cap too
        if cap:
            for z in range(zf, zb):
                if y_front + (z - zf) < y_back + (zb - z) and y_back + (zb - (z + 1)) < y_front + (z + 1 - zf):
                    for x in xs:
                        if m.empty(x, H(z) + 1, z):
                            m.put(x, H(z) + 1, z, cap)
                        if m.empty(x, H(z + 1) + 1, z + 1):
                            m.put(x, H(z + 1) + 1, z + 1, cap)
    if fill_gables:
        for x in (x1, x2):
            for z in range(z1, z2 + 1):
                for y in range(min(y_front, y_back), H(z)):
                    if m.empty(x, y, z):
                        m.put(x, y, z, gable)
    return H, top + (1 if cap else 0)


def hip_roof(m, x1, z1, x2, z2, y, stairs="deepslate_tile_stairs", cap="deepslate_tile_slab", flat="deepslate_tiles",
             overhang=1, rings=None):
    """Hip roof: rings of stairs rising inward from all four sides (corners form themselves).
    rings limits the height (a low 'biscuit box' top); the middle is closed with `flat` + `cap`."""
    ax1, az1, ax2, az2 = x1 - overhang, z1 - overhang, x2 + overhang, z2 + overhang
    k = 0
    with m.tag("roof"):
        while ax2 - ax1 >= 2 and az2 - az1 >= 2 and (rings is None or k < rings):
            yy = y + k
            for x in range(ax1, ax2 + 1):
                m.put(x, yy, az1, stairs, facing="south")
                m.put(x, yy, az2, stairs, facing="north")
            for z in range(az1 + 1, az2):
                m.put(ax1, yy, z, stairs, facing="east")
                m.put(ax2, yy, z, stairs, facing="west")
            ax1, az1, ax2, az2 = ax1 + 1, az1 + 1, ax2 - 1, az2 - 1
            k += 1
        yy = y + k - 1
        for x in range(ax1, ax2 + 1):
            for z in range(az1, az2 + 1):
                m.put(x, yy, z, flat)
                if cap:
                    m.put(x, yy + 1, z, cap)
    return y + k


def cross_gable(m, cx, z_front, y, half, depth, stairs="deepslate_tile_stairs", wall="white_concrete",
                cap="deepslate_tile_slab", window="glass_pane", overhang=1, ridge="deepslate_tiles"):
    """Small gable facing north on the front of a roof: ridge along z, centred on cx.
    y is the eave height (same as the main front eave); half = half width of the gable wall.
    The front wall (row z_front) rises into a triangle with a window in it."""
    zs = range(z_front - overhang, z_front + depth)
    with m.tag("roof"):
        for z in zs:
            for dx in range(-half - overhang, half + overhang + 1):
                x = cx + dx
                h = y + (half + overhang - abs(dx))
                if dx < 0:
                    m.put(x, h, z, stairs, facing="east")
                elif dx > 0:
                    m.put(x, h, z, stairs, facing="west")
                else:
                    m.put(x, h, z, ridge)
                    if cap:
                        m.put(x, h + 1, z, cap)
    for dx in range(-half, half + 1):
        h = y + (half + overhang - abs(dx))
        for yy in range(y - 1, h):
            m.put(cx + dx, yy, z_front, wall)
    m.put(cx, y + 1, z_front, window)
    m.put(cx, y + 2, z_front, window)


__all__ = ["gable_roof", "shed_roof", "two_slope_roof", "hip_roof", "cross_gable", "OPP"]
