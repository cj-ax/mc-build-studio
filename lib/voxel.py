"""Voxel model for one build.

Local frame: +x east, +z south, +y up. y=0 is the first layer above grade
(where you stand); y=-1 is the grade layer (grass). The build's front faces
north (-z); world.json turns it to any facing.

Every cell carries the build step it belongs to. Doors, beds and entities are
markers so the checks can confirm they land in clear, walkable space.
"""
from contextlib import contextmanager

from lib.palette import block, full_props

DIRV = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}
LEFT = {"north": "west", "west": "south", "south": "east", "east": "north"}   # counter-clockwise
RIGHT = {v: k for k, v in LEFT.items()}


def stamp_transform(anchor, x, z, turns, dy=0):
    """(px, py, pz) -> world pos for a sub-model whose anchor rect lands NW-corner-first at (x, z)."""
    from lib.palette import rotate_pos
    ax1, az1, ax2, az2 = anchor
    corners = [rotate_pos(px, pz, turns) for px, pz in ((ax1, az1), (ax2, az1), (ax1, az2), (ax2, az2))]
    ox, oz = x - min(c[0] for c in corners), z - min(c[1] for c in corners)

    def T(px, py, pz):
        rx, rz = rotate_pos(px, pz, turns)
        return (rx + ox, py + dy, rz + oz)
    return T


def rect_through(T, rect):
    """World rect (x1, z1, x2, z2) of a sub-frame rect under transform T."""
    x1, z1, x2, z2 = rect
    a, b = T(x1, 0, z1), T(x2, 0, z2)
    return (min(a[0], b[0]), min(a[2], b[2]), max(a[0], b[0]), max(a[2], b[2]))


class Cell:
    __slots__ = ("key", "props", "step", "tag", "group")

    def __init__(self, key, props, step, tag=None, group=None):
        self.key, self.props, self.step, self.tag, self.group = key, props, step, tag, group

    def __repr__(self):
        return f"Cell({self.key}, {self.props}, step={self.step})"

    @property
    def shape(self):
        return block(self.key)["shape"]

    @property
    def flags(self):
        return block(self.key)["flags"]


class Model:
    def __init__(self, steps):
        self.steps = [s[0] if isinstance(s, (tuple, list)) else s for s in steps]
        self.cells = {}
        self.markers = {}      # group id -> marker dict (doors, beds, entities)
        self.floors = []       # declared walkable levels for the reachability check
        self._step = self.steps[0]
        self._tag = None
        self._gid = 0

    # ------------------------------------------------------------ context
    @contextmanager
    def step(self, key):
        if key not in self.steps:
            raise KeyError(f"step '{key}' not declared in STEPS {self.steps}")
        old, self._step = self._step, key
        try:
            yield self
        finally:
            self._step = old

    @contextmanager
    def tag(self, tag):
        old, self._tag = self._tag, tag
        try:
            yield self
        finally:
            self._tag = old

    # ------------------------------------------------------------ basics
    def put(self, x, y, z, key, step=None, **props):
        self._remove_group_at((x, y, z))
        c = Cell(key, full_props(key, props), step or self._step, self._tag)
        self.cells[(x, y, z)] = c
        return c

    def box(self, x1, y1, z1, x2, y2, z2, key, hollow=False, walls=False, **props):
        """Fill an inclusive box. hollow: shell only; walls: four sides only (no top/bottom)."""
        xa, xb = sorted((x1, x2))
        ya, yb = sorted((y1, y2))
        za, zb = sorted((z1, z2))
        for x in range(xa, xb + 1):
            for z in range(za, zb + 1):
                side = x in (xa, xb) or z in (za, zb)
                for y in range(ya, yb + 1):
                    if walls and not side:
                        continue
                    if hollow and not (side or y in (ya, yb)):
                        continue
                    self.put(x, y, z, key, **props)

    def clear(self, x1, y1, z1, x2=None, y2=None, z2=None):
        """Remove cells from the model (they are simply not placed)."""
        x2, y2, z2 = (x1 if x2 is None else x2), (y1 if y2 is None else y2), (z1 if z2 is None else z2)
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    self._remove_group_at((x, y, z))
                    self.cells.pop((x, y, z), None)

    def air(self, x1, y1, z1, x2=None, y2=None, z2=None):
        """Explicit air: exported as air (carves terrain). Not counted."""
        x2, y2, z2 = (x1 if x2 is None else x2), (y1 if y2 is None else y2), (z1 if z2 is None else z2)
        self.box(x1, y1, z1, x2, y2, z2, "air")

    def get(self, x, y, z):
        return self.cells.get((x, y, z))

    def empty(self, x, y, z):
        c = self.cells.get((x, y, z))
        return c is None or c.key == "air"

    def is_key(self, x, y, z, *keys):
        c = self.cells.get((x, y, z))
        return c is not None and c.key in keys

    # ------------------------------------------------------------ multi-cell things
    def _new_group(self):
        self._gid += 1
        return self._gid

    def _remove_group_at(self, pos):
        c = self.cells.get(pos)
        if c is None or c.group is None:
            return
        g = c.group
        for p in [p for p, cc in self.cells.items() if cc.group == g]:
            del self.cells[p]
        self.markers.pop(g, None)

    def door(self, x, y, z, facing, key="oak_door", hinge="left", open=False, step=None):
        """Two-high door. facing = the direction you walk to go through it from outside."""
        self.clear(x, y, z, x, y + 1, z)
        g = self._new_group()
        for dy, upper in ((0, False), (1, True)):
            c = Cell(key, full_props(key, dict(facing=facing, hinge=hinge, open=open, upper=upper)),
                     step or self._step, self._tag, g)
            self.cells[(x, y + dy, z)] = c
        self.markers[g] = dict(type="door", key=key, pos=[x, y, z], facing=facing)
        return g

    def bed(self, x, y, z, facing, key="red_bed", step=None):
        """Bed with its foot at (x,y,z) and head one block toward `facing`."""
        dx, dz = DIRV[facing]
        self.clear(x, y, z)
        self.clear(x + dx, y, z + dz)
        g = self._new_group()
        for (px, pz), head in (((x, z), False), ((x + dx, z + dz), True)):
            self.cells[(px, y, pz)] = Cell(key, full_props(key, dict(facing=facing, head=head)),
                                           step or self._step, self._tag, g)
        self.markers[g] = dict(type="bed", key=key, pos=[x, y, z], facing=facing)
        return g

    def tall_plant(self, x, y, z, key, step=None):
        self.clear(x, y, z, x, y + 1, z)
        g = self._new_group()
        for dy in (0, 1):
            self.cells[(x, y + dy, z)] = Cell(key, full_props(key, dict(upper=dy == 1)),
                                              step or self._step, self._tag, g)
        return g

    def entity(self, x, y, z, entity_id, name=None, step=None):
        """Summoned at the end of the build. Position is the block the mob stands in."""
        if not entity_id.startswith("minecraft:"):
            entity_id = "minecraft:" + entity_id
        g = self._new_group()
        self.markers[g] = dict(type="entity", id=entity_id, pos=[x, y, z], name=name,
                               step=step or self._step)
        return g

    def floor(self, name, y, x1, z1, x2, z2):
        """Declare a walkable level (y = feet level). Checks require a way to reach it."""
        self.floors.append(dict(name=name, y=y, box=[min(x1, x2), min(z1, z2), max(x1, x2), max(z1, z2)]))

    # ------------------------------------------------------------ sub-models
    def sub(self):
        """An empty model sharing this one's steps and current step/tag (build a piece, then stamp it)."""
        s = Model(self.steps)
        s._step, s._tag = self._step, self._tag
        return s

    def stamp(self, sub, x, z, turns=0, anchor=None, dy=0):
        """Copy `sub` into this model turned `turns` quarter turns clockwise. The anchor rect
        (x1, z1, x2, z2 in sub coords; default: everything) lands with its north-west corner at
        (x, z). Doors, beds, entities and floors come along. Returns the transform (x, y, z) -> pos."""
        from lib.palette import rot_dir, rotate_props
        if anchor is None:
            xs = [p[0] for p in sub.cells] or [0]
            zs = [p[2] for p in sub.cells] or [0]
            anchor = (min(xs), min(zs), max(xs), max(zs))
        T = stamp_transform(anchor, x, z, turns, dy)

        gmap = {}
        for (px, py, pz), c in sub.cells.items():
            g = None
            if c.group is not None:
                g = gmap.setdefault(c.group, self._new_group())
            pos = T(px, py, pz)
            self._remove_group_at(pos)
            self.cells[pos] = Cell(c.key, rotate_props(c.key, c.props, turns), c.step, c.tag, g)
        for gid, mk in sub.markers.items():
            mk = dict(mk)
            mk["pos"] = list(T(*mk["pos"]))
            if "facing" in mk:
                mk["facing"] = rot_dir(mk["facing"], turns)
            self.markers[gmap.get(gid) or self._new_group()] = mk
        for f in sub.floors:
            x1, z1, x2, z2 = f["box"]
            a, b = T(x1, 0, z1), T(x2, 0, z2)
            self.floor(f["name"], f["y"] + dy, a[0], a[2], b[0], b[2])
        return T

    def rotated_rect(self, rect, x, z, turns):
        """Where a sub-model rect ends up for stamp(..., x, z, turns, anchor=rect): (x1, z1, x2, z2)."""
        x1, z1, x2, z2 = rect
        w, d = x2 - x1, z2 - z1
        if turns % 2:
            w, d = d, w
        return (x, z, x + w, z + d)

    # ------------------------------------------------------------ info
    def bounds(self):
        if not self.cells:
            return (0, 0, 0, 0, 0, 0)
        xs, ys, zs = zip(*self.cells)
        return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)

    def solid_at(self, x, y, z):
        c = self.cells.get((x, y, z))
        return c is not None and c.key != "air" and not c.flags.get("walk")
