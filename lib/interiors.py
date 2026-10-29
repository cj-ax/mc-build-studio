"""Furniture and room recipes. A room is the inside floor area x1..x2, z1..z2 (inclusive)
with feet level y. Every recipe only fills empty cells and skips the cells in `keep`
(door approaches, stair runs, landings), so it never blocks a way through."""
import random

from lib.voxel import DIRV, OPP

WOOD = {"oak": "oak", "spruce": "spruce", "birch": "birch", "dark_oak": "dark_oak"}


class Room:
    def __init__(self, m, x1, z1, x2, z2, y, keep=(), seed=0, wood="spruce", ceil=3):
        self.m, self.x1, self.z1, self.x2, self.z2, self.y = m, x1, z1, x2, z2, y
        self.ceil = ceil              # free height from the floor to the ceiling block
        self.keep = set(keep)
        self.r = random.Random(seed)
        self.wood = wood

    def free(self, x, z, h=1):
        if (x, z) in self.keep or not (self.x1 <= x <= self.x2 and self.z1 <= z <= self.z2):
            return False
        return all(self.m.empty(x, self.y + dy, z) for dy in range(h))

    def put(self, x, z, key, dy=0, **props):
        if (x, z) in self.keep and dy < 2:
            return False
        if not self.m.empty(x, self.y + dy, z):
            return False
        self.m.put(x, self.y + dy, z, key, **props)
        return True

    @property
    def cx(self):
        return (self.x1 + self.x2) // 2

    @property
    def cz(self):
        return (self.z1 + self.z2) // 2

    def wall_cells(self, side):
        """Cells along one inside wall, in order."""
        if side == "north":
            return [(x, self.z1) for x in range(self.x1, self.x2 + 1)]
        if side == "south":
            return [(x, self.z2) for x in range(self.x1, self.x2 + 1)]
        if side == "west":
            return [(self.x1, z) for z in range(self.z1, self.z2 + 1)]
        return [(self.x2, z) for z in range(self.z1, self.z2 + 1)]


# ---------------------------------------------------------------- pieces
def table(room, x, z, top=None):
    """Fence post with a pressure-plate top (or a carpet / cake / candle on it)."""
    w = room.wood
    if not room.free(x, z, 2):
        return False
    room.put(x, z, f"{w}_fence")
    room.put(x, z, top or f"{w}_pressure_plate", dy=1)
    return True


def chair(room, x, z, faces):
    """A stair you sit on, looking `faces` (its back is the opposite side)."""
    if not room.free(x, z):
        return False
    return room.put(x, z, f"{room.wood}_stairs", facing=OPP[faces])


def dining(room, x, z, along="x", seats=True, top=None):
    """Two-seat table: table at (x, z) and chairs either side."""
    if not table(room, x, z, top):
        return False
    if seats:
        if along == "x":
            chair(room, x - 1, z, "east")
            chair(room, x + 1, z, "west")
        else:
            chair(room, x, z - 1, "south")
            chair(room, x, z + 1, "north")
    return True


def rug(room, x1, z1, x2, z2, color="red"):
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            if room.free(x, z):
                room.put(x, z, f"{color}_carpet")


def ceiling_lamp(room, x, z, height=None):
    """Hanging lantern from the ceiling block at y + height (default: the room's ceiling)."""
    m = room.m
    height = room.ceil if height is None else min(height, room.ceil)
    yy = room.y + height - 1
    if m.empty(x, yy, z) and not m.empty(x, yy + 1, z):
        m.put(x, yy, z, "lantern", hanging=True)
        return True
    return False


def along_wall(room, side, items, start=0, step=1, dy=0):
    """Place a list of (key, props) along an inside wall, skipping blocked cells."""
    cells = room.wall_cells(side)[start::step]
    i = 0
    for (x, z) in cells:
        if i >= len(items):
            break
        if room.free(x, z) or (dy and room.m.empty(x, room.y + dy, z)):
            key, props = items[i]
            if room.put(x, z, key, dy=dy, **props):
                i += 1
    return i


def facing_into(side):
    """Front of a block standing against `side` wall faces into the room."""
    return OPP[side]


# ---------------------------------------------------------------- rooms
def kitchen(room, side="east", extras=()):
    f = facing_into(side)
    items = [("furnace", {"facing": f}), ("smoker", {"facing": f}), ("barrel", {"facing": "up"}),
             ("cauldron", {}), ("crafting_table", {}), ("barrel", {"facing": "up"}), ("chest", {"facing": f})]
    items += [(k, {}) for k in extras]
    along_wall(room, side, items, start=1)
    # wall cabinets above the counter
    for (x, z) in room.wall_cells(side)[1:6]:
        if not room.m.empty(x, room.y, z) and room.m.empty(x, room.y + 2, z) and room.ceil >= 4:
            room.m.put(x, room.y + 2, z, f"{room.wood}_planks" if (x + z) % 2 else "barrel",
                       **({} if (x + z) % 2 else {"facing": f}))
    # table with chairs in the middle of this half
    dx = -2 if side == "east" else 2
    tx = (room.x2 if side == "east" else room.x1) + dx
    dining(room, tx, room.cz, along="z")
    ceiling_lamp(room, tx, room.cz)


def parlour(room, side="west", rug_color="red", seed=0):
    r = random.Random(seed)
    f = facing_into(side)
    shelves = [("bookshelf", {})] * 2 + [("flower_pot", {})] + [("bookshelf", {})]
    along_wall(room, side, shelves, start=1)
    # two armchairs facing the wall shelves / stove, a rug and a side table
    ax = (room.x1 if side == "west" else room.x2) + (2 if side == "west" else -2)
    rug(room, min(ax, ax + (1 if side == "west" else -1)) - 1, room.cz - 1, max(ax, ax + 1) + 1, room.cz + 1,
        r.choice([rug_color, "brown", "blue", "green", "gray"]))
    chair(room, ax, room.cz - 1, side)   # armchairs face the shelves wall
    chair(room, ax, room.cz + 1, side)
    table(room, ax + (1 if side == "west" else -1), room.cz, "flower_pot")
    ceiling_lamp(room, ax, room.cz)


def bedroom(room, bed_wall="south", rug_color="light_blue", extras=("chest",), seed=0):
    m = room.m
    r = random.Random(seed)
    # bed with its head against bed_wall, in the middle of that wall
    d = DIRV[bed_wall]
    cells = room.wall_cells(bed_wall)
    order = sorted(cells, key=lambda c: abs(c[0] - room.cx) + abs(c[1] - room.cz))
    for (hx, hz) in order:
        fx, fz = hx - d[0], hz - d[1]
        if room.free(hx, hz, 2) and room.free(fx, fz, 2):
            m.bed(fx, room.y, fz, bed_wall)
            # chest / extras beside the bed head
            for side in (1, -1):
                sx, sz = (hx + side, hz) if bed_wall in ("north", "south") else (hx, hz + side)
                if room.free(sx, sz):
                    k = extras[0] if extras else "chest"
                    if k == "chest":
                        room.put(sx, sz, "chest", facing=OPP[bed_wall])
                    elif k == "flower_pot":
                        room.put(sx, sz, "flower_pot")
                    else:
                        room.put(sx, sz, k)
                    extras = extras[1:] or ("flower_pot",)
                    break
            rug(room, fx - 1, fz - 1, fx + 1, fz + 1, rug_color) if bed_wall in ("north", "south") else None
            break
    # wardrobe and washstand on the far wall
    far = OPP[bed_wall]
    along_wall(room, far, [("bookshelf", {}) if r.random() < 0.3 else (f"{room.wood}_planks", {}), ("cauldron", {}), ("flower_pot", {})], start=1, step=2)
    ceiling_lamp(room, room.cx, room.cz)


def pub(room, bar_wall="south"):
    """Bar counter of barrels with a brewing stand, stools, tables, a jukebox."""
    f = facing_into(bar_wall)
    cells = room.wall_cells(bar_wall)
    n = 0
    for i, (x, z) in enumerate(cells[1:-1]):
        if room.free(x, z):
            room.put(x, z, "barrel", facing=f if f != "up" else "up")
            if i % 3 == 1:
                room.put(x, z, "brewing_stand", dy=1)
            n += 1
    # a counter row one in from the wall, with stools in front
    d = DIRV[f]
    for (x, z) in cells[2:-2:2]:
        cx, cz = x + d[0] * 2, z + d[1] * 2
        if room.free(cx, cz):
            room.put(cx, cz, f"{room.wood}_slab", half="top")
            sx, sz = cx + d[0], cz + d[1]
            if room.free(sx, sz):
                room.put(sx, sz, f"{room.wood}_stairs", facing=f)
    # tables
    for x in range(room.x1 + 2, room.x2 - 1, 4):
        for z in range(room.z1 + 2, room.z2 - 3, 4):
            dining(room, x, z, along="x", top="white_candle")
    along_wall(room, "west" if bar_wall != "west" else "east", [("jukebox", {}), ("barrel", {"facing": "up"})], start=1)
    for x in range(room.x1 + 2, room.x2 - 1, 5):
        ceiling_lamp(room, x, room.cz)


def restaurant(room, kitchen_wall="south"):
    f = facing_into(kitchen_wall)
    along_wall(room, kitchen_wall, [("smoker", {"facing": f}), ("furnace", {"facing": f}), ("cauldron", {}),
                                    ("barrel", {"facing": "up"}), ("smoker", {"facing": f}), ("crafting_table", {}),
                                    ("barrel", {"facing": "up"}), ("blast_furnace", {"facing": f})], start=1)
    for x in range(room.x1 + 2, room.x2 - 1, 4):
        for z in range(room.z1 + 1, room.z2 - 3, 3):
            dining(room, x, z, along="x", top="white_candle" if (x + z) % 2 else "cake")
    for x in range(room.x1 + 2, room.x2 - 1, 5):
        ceiling_lamp(room, x, room.cz)


def shop(room, counter_wall="south", post_office=True):
    for side in ("east", "west"):
        along_wall(room, side, [("bookshelf", {}), ("barrel", {"facing": "up"}), ("chest", {"facing": OPP[side]}),
                                ("barrel", {"facing": "up"}), ("bookshelf", {}), ("barrel", {"facing": "up"})], start=1)
    f = facing_into(counter_wall)
    d = DIRV[f]
    cells = room.wall_cells(counter_wall)
    for (x, z) in cells[2:-2]:
        cx, cz = x + d[0] * 2, z + d[1] * 2
        if room.free(cx, cz):
            room.put(cx, cz, "spruce_slab", half="top")
    along_wall(room, counter_wall, [("barrel", {"facing": "up"}), ("chest", {"facing": f})] * 3, start=1, step=2)
    if post_office:
        room.put(room.x1 + 1, room.z1 + 1, "lectern", facing="south")
        room.put(room.x1 + 2, room.z1 + 1, "cartography_table")
    for x in range(room.x1 + 2, room.x2 - 1, 5):
        ceiling_lamp(room, x, room.cz)


def office(room, desk_wall="south"):
    f = facing_into(desk_wall)
    along_wall(room, desk_wall, [("cartography_table", {}), ("lectern", {"facing": f}), ("chest", {"facing": f}),
                                 ("bookshelf", {}), ("barrel", {"facing": "up"})], start=1)
    along_wall(room, "west", [("bookshelf", {}), ("bookshelf", {}), ("flower_pot", {})], start=1)
    table(room, room.cx, room.cz, "white_candle")
    chair(room, room.cx, room.cz + 1, "north")
    ceiling_lamp(room, room.cx, room.cz)


def fish_plant(room):
    """Splitting tables, salt barrels, ice, cauldrons and a smoker line."""
    for x in range(room.x1 + 1, room.x2, 3):
        for z in (room.z1 + 3, room.z2 - 3):
            if room.free(x, z):
                if x % 2:
                    room.put(x, z, "smithing_table")
                else:
                    room.put(x, z, "stonecutter", facing="north")
    along_wall(room, "south", [("barrel", {"facing": "up"}), ("packed_ice", {}), ("barrel", {"facing": "up"}),
                               ("cauldron", {}), ("blue_ice", {}), ("barrel", {"facing": "up"})] * 4, start=1)
    along_wall(room, "west", [("smoker", {"facing": "east"})] * 3 + [("chest", {"facing": "east"})], start=1)
    for x in range(room.x1 + 2, room.x2 - 1, 6):
        ceiling_lamp(room, x, room.cz)


def loft(room, kind="nets"):
    """Net loft / store: barrels, cobweb 'nets', chests, a loom."""
    along_wall(room, "south", [("barrel", {"facing": "up"}), ("loom", {"facing": "north"}), ("barrel", {"facing": "up"}),
                               ("chest", {"facing": "north"})], start=0)
    along_wall(room, "east", [("cobweb", {}), ("barrel", {"facing": "up"}), ("cobweb", {})], start=1)
    ceiling_lamp(room, room.cx, room.cz)


def school(room, board_wall="north"):
    """Classroom: chalkboard along the front wall, rows of desks facing it, the teacher's lectern."""
    m = room.m
    for (x, z) in room.wall_cells(board_wall)[1:-1]:
        for dy in (1, 2):
            if m.empty(x, room.y + dy, z) and (x, z) not in room.keep:
                m.put(x, room.y + dy, z, "black_concrete")
    d = 1 if board_wall == "north" else -1
    zs = range(room.z1 + 3, room.z2, 2) if d == 1 else range(room.z2 - 3, room.z1, -2)
    for z in zs:
        for x in range(room.x1 + 1, room.x2, 3):
            if table(room, x, z):
                chair(room, x, z + d, board_wall)
    room.put(room.cx, room.z1 + 1 if d == 1 else room.z2 - 1, "lectern", facing=OPP[board_wall])
    along_wall(room, "west", [("bookshelf", {}), ("bookshelf", {}), ("chest", {"facing": "east"})], start=2)
    for x in range(room.x1 + 2, room.x2 - 1, 5):
        ceiling_lamp(room, x, room.cz)


def hall(room, stage_wall="south"):
    """Parish hall: a raised stage, rows of chairs facing it, tables along the sides, a kitchen hatch."""
    cells = room.wall_cells(stage_wall)
    d = -1 if stage_wall == "south" else 1
    for (x, z) in cells:
        for k in range(3):
            room.put(x, z + d * k, "spruce_slab", half="top")
    room.put(room.cx, cells[0][1], "jukebox", dy=1)
    zs = range(room.z2 - 5, room.z1 + 2, -2) if stage_wall == "south" else range(room.z1 + 5, room.z2 - 2, 2)
    for z in zs:
        for x in range(room.x1 + 2, room.x2 - 1):
            if x != room.cx:
                chair(room, x, z, stage_wall)
    along_wall(room, "west", [("barrel", {"facing": "up"}), ("smoker", {"facing": "east"}), ("cauldron", {}),
                              ("barrel", {"facing": "up"}), ("crafting_table", {})], start=2)
    for x in range(room.x1 + 2, room.x2 - 1, 5):
        ceiling_lamp(room, x, room.cz)
