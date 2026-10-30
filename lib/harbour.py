"""Waterfront pieces that stand in a no-touch waterfront zone (no water is ever placed).

Decks sit at deck_y (default -1: level with the grass) on log piles that reach down to
`bottom` (default -6: five blocks below the land)."""
import random

from lib.roofs import shed_roof
from lib.voxel import OPP


def piles(m, cells, deck_y=-1, bottom=-6, pile="spruce_log"):
    for (x, z) in cells:
        for y in range(bottom, deck_y):
            m.put(x, y, z, pile, axis="y")


def wharf(m, x1, z1, x2, z2, deck_y=-1, bottom=-6, deck="spruce_planks", pile="spruce_log", every=4,
          rim="stripped_spruce_log", bollards="spruce_fence", bollard_every=5, sea_sides=("north", "east", "west")):
    """Plank deck on a grid of piles, log rim, bollards along the sea edges."""
    xa, xb = sorted((x1, x2))
    za, zb = sorted((z1, z2))
    xs = sorted(set(list(range(xa, xb + 1, every)) + [xb]))
    zs = sorted(set(list(range(za, zb + 1, every)) + [zb]))
    piles(m, [(x, z) for x in xs for z in zs], deck_y, bottom, pile)
    m.box(xa, deck_y, za, xb, deck_y, zb, deck)
    if rim:
        for x in range(xa, xb + 1):
            for z in (za, zb):
                m.put(x, deck_y, z, rim, axis="x")
        for z in range(za + 1, zb):
            for x in (xa, xb):
                m.put(x, deck_y, z, rim, axis="z")
    if bollards:
        edge = {"north": [(x, za) for x in range(xa, xb + 1)], "south": [(x, zb) for x in range(xa, xb + 1)],
                "west": [(xa, z) for z in range(za, zb + 1)], "east": [(xb, z) for z in range(za, zb + 1)]}
        for side in sea_sides:
            for i, (x, z) in enumerate(edge[side]):
                if i % bollard_every == 0:
                    m.put(x, deck_y + 1, z, bollards)


def finger_pier(m, x1, z1, x2, z2, deck_y=-1, bottom=-6, deck="spruce_planks", pile="spruce_log", every=3):
    wharf(m, x1, z1, x2, z2, deck_y, bottom, deck, pile, every, rim=None, bollard_every=4,
          sea_sides=("north", "east", "west", "south"))


def stage(m, x, z, w=9, d=10, deck_y=-1, bottom=-6, wall="red_terracotta", trim="spruce_planks", roof="spruce_stairs",
          door="spruce_door"):
    """Fishing stage: a shed on a stilt deck, door to the water (north), splitting table inside.
    (x, z) is the north-west corner of the deck; the shed sits on its back (south) part."""
    wharf(m, x, z, x + w - 1, z + d - 1, deck_y, bottom, rim="stripped_spruce_log", bollard_every=4,
          sea_sides=("north",))
    sx1, sz1, sx2, sz2 = x + 1, z + 3, x + w - 2, z + d - 2
    f = deck_y + 1
    for xx in range(sx1, sx2 + 1):
        for zz in range(sz1, sz2 + 1):
            if xx in (sx1, sx2) or zz in (sz1, sz2):
                corner = xx in (sx1, sx2) and zz in (sz1, sz2)
                for yy in range(f, f + 3):
                    m.put(xx, yy, zz, trim if corner else wall)
    dx = (sx1 + sx2) // 2
    m.door(dx, f, sz1, "south", key=door)
    for wx in (sx1 + 1, sx2 - 1):
        if wx != dx:
            m.put(wx, f + 1, sz1, "glass_pane")
    shed_roof(m, sx1, sz1, sx2, sz2, f + 3, rises="south", stairs=roof, wall=wall)
    # inside: splitting table, salt barrels, a lantern
    m.put(sx1 + 1, f, sz2 - 1, "crafting_table")
    m.put(sx2 - 1, f, sz2 - 1, "barrel", facing="up")
    m.put(sx2 - 1, f, sz2 - 2, "barrel", facing="up")
    m.put(sx1 + 1, f, sz1 + 1, "chest", facing="east")
    m.put(sx1 + 1, f + 1, sz2 - 1, "lantern")          # standing on the splitting table
    m.floor("stage", f, sx1 + 1, sz1 + 1, sx2 - 1, sz2 - 1)
    # lobster pots on the deck front
    for i, xx in enumerate(range(x + 1, x + w - 1, 2)):
        if m.empty(xx, f, z + 1):
            m.put(xx, f, z + 1, "barrel" if i % 2 else "composter")


def flake(m, x1, z1, x2, z2, y, seed=0):
    """Fish flake: a low slatted drying platform on posts, with salt fish laid on it."""
    r = random.Random(seed)
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            if (x - x1) % 3 == 0 and (z - z1) % 3 == 0:
                m.put(x, y, z, "spruce_fence")
            m.put(x, y + 1, z, "spruce_slab")
            if r.random() < 0.45:
                m.put(x, y + 2, z, "white_carpet")


def rock_pile(m, cells, bottom=-6, seed=0, top=(-1, 1), stones=("stone", "andesite", "cobblestone", "mossy_cobblestone", "tuff")):
    """Rough breakwater / rocky point: columns of mixed stone from the seabed up."""
    r = random.Random(seed)
    for (x, z) in cells:
        h = r.randint(*top)
        for y in range(bottom, h + 1):
            m.put(x, y, z, r.choice(stones))


def dory(m, x, z, y=-2, along="x", color="red_concrete", seed=0):
    """A small open boat floating at the water surface (tagged afloat: exempt from 'floating')."""
    with m.tag("afloat"):
        if along == "x":
            m.put(x, y, z, "spruce_stairs", facing="west")
            m.put(x + 4, y, z, "spruce_stairs", facing="east")
            for xx in range(x + 1, x + 4):
                m.put(xx, y, z, "spruce_slab")
            for xx in range(x, x + 5):
                m.put(xx, y, z - 1, color) if xx in (x + 1, x + 2, x + 3) else None
                m.put(xx, y, z + 1, color) if xx in (x + 1, x + 2, x + 3) else None
        else:
            m.put(x, y, z, "spruce_stairs", facing="north")
            m.put(x, y, z + 4, "spruce_stairs", facing="south")
            for zz in range(z + 1, z + 4):
                m.put(x, y, zz, "spruce_slab")
                m.put(x - 1, y, zz, color)
                m.put(x + 1, y, zz, color)


def slipway(m, x, z1, z2, y_top=0, width=5, boat_color="blue_concrete"):
    """Log rails running down into the water from the quay, with a boat on a cradle."""
    n = z2 - z1 + 1
    for i in range(n):
        zz = z2 - i                # rails descend toward the water (north)
        yy = y_top - 1 - i // 3
        for xx in (x, x + width - 1):
            m.put(xx, yy, zz, "stripped_spruce_log", axis="z")
            for py in range(-6, yy):
                m.put(xx, py, zz, "spruce_log", axis="y")
    # boat on cradle near the top of the slip
    bz = z2 - 3
    cx = x + width // 2
    for zz in range(bz - 4, bz + 1, 2):                    # cradle posts down to the seabed
        piles(m, [(cx, zz)], y_top, -6)
    for zz in range(bz - 4, bz + 1):
        m.put(cx, y_top, zz, "spruce_planks" if zz not in (bz - 4, bz) else "spruce_stairs",
              **({"facing": "north" if zz == bz - 4 else "south"} if zz in (bz - 4, bz) else {}))
        for xx in (cx - 1, cx + 1):
            if zz not in (bz - 4, bz):
                m.put(xx, y_top, zz, boat_color)
                m.put(xx, y_top + 1, zz, "spruce_slab")


def longliner(m, x0, z0, length=18, hull="red_concrete", stripe="white_concrete", seed=0):
    """Inshore fishing boat (longliner) lying along x with its bow to the east, afloat at the
    water surface (y = -2): keel, painted hull, plank deck, wheelhouse aft, a mast with a light."""
    with m.tag("afloat"):
        for i in range(length):
            x = x0 + i
            hw = 2 if i < length - 4 else (2, 1, 1, 0)[i - (length - 4)]
            if 0 < i < length - 1:
                m.put(x, -3, z0, "dark_oak_planks")
            for dz in range(-hw, hw + 1):
                side = abs(dz) == hw
                m.put(x, -2, z0 + dz, hull if side else "dark_oak_planks")
                m.put(x, -1, z0 + dz, hull if side else "spruce_planks")
                if side:
                    m.put(x, 0, z0 + dz, stripe)
            if i == 0:
                for dz in range(-hw + 1, hw):
                    m.put(x, 0, z0 + dz, stripe)
        # wheelhouse aft (x0+2 .. x0+6)
        for x in range(x0 + 2, x0 + 7):
            for dz in (-1, 0, 1):
                edge = x in (x0 + 2, x0 + 6) or abs(dz) == 1
                for y in (0, 1, 2):
                    if edge:
                        win = y == 1 and (dz == 0 or x in (x0 + 3, x0 + 5))
                        m.put(x, y, z0 + dz, "glass_pane" if win else "white_concrete")
                m.put(x, 3, z0 + dz, "spruce_slab")
        m.clear(x0 + 6, 0, z0)
        m.clear(x0 + 6, 1, z0)
        m.put(x0 + 4, 0, z0, "spruce_stairs", facing="west")       # the skipper's seat
        m.put(x0 + 4, 2, z0, "lantern", hanging=True)
        for y in range(0, 7):                                       # mast
            m.put(x0 + 10, y, z0, "spruce_fence")
        m.put(x0 + 10, 7, z0, "lantern")
        for x in range(x0 + 8, x0 + 13):                            # boom
            m.put(x, 5, z0, "spruce_fence")
        for x in (x0 + 12, x0 + 13):                                # fish hold and gear
            m.put(x, 0, z0 - 1, "barrel", facing="up")
        m.put(x0 + 8, 0, z0 + 1, "chest", facing="west")


def walkway(m, cells, deck_y=-1, bottom=-6, every=3, deck="spruce_planks", pile="spruce_log", posts=0.15, seed=0):
    """Narrow stilt walkway over the water along ordered cells (a path from smooth_line/widen)."""
    r = random.Random(seed)
    cells = list(cells)
    # make it 4-connected: a diagonal step gets a corner plank
    joined = []
    for c in cells:
        if joined:
            px, pz = joined[-1]
            if abs(c[0] - px) == 1 and abs(c[1] - pz) == 1:
                joined.append((c[0], pz))
        joined.append(c)
    cells = joined
    for i, (x, z) in enumerate(cells):
        m.put(x, deck_y, z, deck)
        if i % every == 0:
            piles(m, [(x, z)], deck_y, bottom, pile)
    return cells


def mooring_post(m, x, z, top=0, bottom=-6):
    for y in range(bottom, top):
        m.put(x, y, z, "spruce_log", axis="y")
    m.put(x, top, z, "spruce_fence")


def rock_mass(m, tops, bottom=-6, seed=0, stones=("stone", "stone", "andesite", "cobblestone", "tuff", "mossy_cobblestone"),
              moss=0.15):
    """Columns of mixed rock from the seabed to a per-cell top height: {(x, z): top_y}."""
    r = random.Random(seed)
    for (x, z), t in tops.items():
        for y in range(bottom, t + 1):
            m.put(x, y, z, r.choice(stones))
        if t >= -1 and r.random() < moss:
            m.put(x, t, z, "moss_block")


def boathouse(m, x, z, w=9, d=12, deck_y=-1, bottom=-6, wall="red_terracotta", roof="spruce_stairs", boat="blue_concrete",
              seed=0):
    """Boathouse on piles: the water (north) end is open, a slip down the middle, a dory inside,
    side walkways and a back door to the land (south)."""
    x2, z2 = x + w - 1, z + d - 1
    xs = sorted({x, x2, x + w // 2 - 2, x + w // 2 + 2})
    piles(m, [(xx, zz) for xx in xs for zz in range(z, z2 + 1, 3)], deck_y, bottom)
    cx = x + w // 2
    for xx in range(x, x2 + 1):
        for zz in range(z, z2 + 1):
            if abs(xx - cx) >= 2 or zz == z2:
                m.put(xx, deck_y, zz, "spruce_planks")
    f = deck_y + 1
    for xx in range(x, x2 + 1):
        for zz in range(z, z2 + 1):
            edge = xx in (x, x2) or zz == z2
            open_front = zz == z and abs(xx - cx) <= 1
            if (edge or zz == z) and not open_front:
                for yy in range(f, f + 4):
                    corner = xx in (x, x2) and zz in (z, z2)
                    m.put(xx, yy, zz, "spruce_planks" if corner else wall)
            if open_front:
                m.put(xx, f + 3, zz, wall)
    for zz in range(z, z2 + 1):
        for xx in (x, x2):
            if zz % 3 == 1 and zz not in (z, z2):
                m.put(xx, f + 1, zz, "glass_pane")
    _boathouse_roof(m, x, z, x2, z2, f + 4, roof, wall)
    m.door(cx - 2, f, z2, "north", key="spruce_door")          # back door onto the side walkway
    dory(m, cx, z + 2, y=-2, along="z", color=boat)
    m.put(x + 1, f, z2 - 1, "barrel", facing="up")
    m.put(x2 - 1, f, z2 - 1, "chest", facing="west")
    m.put(x2 - 1, f, z + 1, "lantern")
    m.floor("boathouse", f, x + 1, z + 1, x + 1, z2 - 1)


def _boathouse_roof(m, x, z, x2, z2, y, roof, wall):
    """Gable roof with the ridge running out over the water (north-south)."""
    from lib.roofs import gable_roof
    gable_roof(m, x, z, x2, z2, y, ridge="z", stairs=roof, cap="spruce_slab", gable=wall, overhang=1, gable_overhang=1)
