"""Timber-frame buildings with floors, windows, a door and ladders."""
from lib.roofs import gable_roof
from lib.voxel import DIRV, OPP


def timber_frame(m, x1, z1, x2, z2, y0=0, storeys=(4, 4), frame="dark_oak_log",
                 infill="white_terracotta", floor="spruce_planks", plinth="cobblestone",
                 post_every=4, window="glass_pane", door_side="north", door_at=None,
                 door="spruce_door", ladder_at=None, roof=None, lanterns=True, step_names=None,
                 front_step="spruce_stairs"):
    """A timber-frame house on the wall rectangle x1..x2, z1..z2.

    y0 is the plinth row (stone ring + ground floor); each storey is `h` tall
    from its floor to the next floor/beam row. The ground floor stands at
    y0+1. A ladder runs up an inside wall to every upper floor.

    step_names: optional dict mapping 'frame', 'floors', 'roof', 'details'
    to model steps (otherwise everything goes in the current step).
    Returns info: floor ys, wall top, door position, ridge.
    """
    S = step_names or {}

    def in_step(name):
        return m.step(S[name]) if name in S else _null()

    info = {"floors": [], "rect": (x1, z1, x2, z2)}
    w_axis = {"north": "x", "south": "x", "east": "z", "west": "z"}
    if door_at is None:
        door_at = (x1 + x2) // 2 if door_side in ("north", "south") else (z1 + z2) // 2
    dx_, dz_ = DIRV[door_side]
    door_pos = {"north": (door_at, z1), "south": (door_at, z2),
                "west": (x1, door_at), "east": (x2, door_at)}[door_side]
    # ladder column: inside the wall opposite the door, near a corner
    if ladder_at is None:
        lx, lz = {"south": (x1 + 1, z1 + 1), "north": (x2 - 1, z2 - 1),
                  "west": (x2 - 1, z1 + 1), "east": (x1 + 1, z2 - 1)}[door_side]
        ladder_face = door_side   # faces away from the back wall it hangs on
    else:
        lx, lz, ladder_face = ladder_at
    bx, bz = DIRV[OPP[ladder_face]]
    ladder_back = (lx + bx, lz + bz)

    with in_step("frame"):
        # plinth ring and ground floor
        m.box(x1, y0, z1, x2, y0, z2, plinth, walls=True)
        fy = y0
        for si, h in enumerate(storeys):
            top = fy + h
            for x in range(x1, x2 + 1):
                for z in range(z1, z2 + 1):
                    edge_x, edge_z = x in (x1, x2), z in (z1, z2)
                    if not (edge_x or edge_z):
                        continue
                    corner = edge_x and edge_z
                    along = (x - x1) if edge_z else (z - z1)
                    post = corner or along % post_every == 0
                    for y in range(fy + 1, top):
                        if post:
                            m.put(x, y, z, frame, axis="y")
                        else:
                            m.put(x, y, z, infill)
                    # beam row: horizontal logs along each wall
                    if corner:
                        m.put(x, top, z, frame, axis="y")
                    else:
                        m.put(x, top, z, frame, axis="x" if edge_z else "z")
            # windows: 1 wide, 2 tall, centred in each panel between posts
            for side in ("north", "south", "east", "west"):
                cells = _wall_cells(x1, z1, x2, z2, side)
                for i in range(len(cells)):
                    if i % post_every != post_every // 2 or i in (0, len(cells) - 1):
                        continue
                    x, z = cells[i]
                    if (si == 0 and (x, z) == door_pos) or (x, z) == ladder_back:
                        continue
                    if si == 0 and side == door_side and abs(i - cells.index(door_pos)) <= 1:
                        continue
                    for y in (fy + 2, fy + 3) if h >= 4 else (fy + 2,):
                        m.put(x, y, z, window)
            info["floors"].append(fy + 1)
            fy = top
        info["wall_top"] = fy

    with in_step("floors"):
        fy = y0
        n = len(storeys)
        for si, h in enumerate(storeys):
            for x in range(x1 + 1, x2):
                for z in range(z1 + 1, z2):
                    if si > 0 and (x, z) == (lx, lz):
                        continue  # ladder hole
                    m.put(x, fy, z, floor)
            m.floor(f"storey {si + 1}", fy + 1, x1 + 1, z1 + 1, x2 - 1, z2 - 1)
            if si < n - 1:
                for y in range(fy + 1, fy + h + 1):
                    m.put(lx, y, lz, "ladder", facing=ladder_face)
            fy += h
        # attic / ceiling floor under the roof
        for x in range(x1 + 1, x2):
            for z in range(z1 + 1, z2):
                m.put(x, fy, z, floor)
        info["ladder"] = (lx, lz)

    with in_step("frame"):
        dx, dz = door_pos
        inward = OPP[door_side]
        m.door(dx, y0 + 1, dz, inward, key=door)
        info["door"] = (dx, y0 + 1, dz, inward)
        # front step up to the door from grade
        sx, sz = dx + dx_, dz + dz_
        if front_step:
            m.put(sx, y0, sz, front_step, facing=inward)

    if roof is not None:
        with in_step("roof"):
            r = dict(roof)
            info["ridge"] = gable_roof(m, x1, z1, x2, z2, info["wall_top"] + 1, **r)

    if lanterns:
        with in_step("details"):
            cx, cz = (x1 + x2) // 2, (z1 + z2) // 2
            fy = y0
            for h in storeys:
                if (cx, cz) != info["ladder"]:
                    m.put(cx, fy + h - 1, cz, "lantern", hanging=True)
                fy += h
            # lanterns either side of the door, hung from the beam
            for off in (-1, 1):
                ox, oz = (door_pos[0] + off, door_pos[1]) if w_axis[door_side] == "x" else (door_pos[0], door_pos[1] + off)
                lx2, lz2 = ox + dx_, oz + dz_
                m.put(lx2, y0 + 3, lz2, "torch", facing=door_side)
    return info


def _wall_cells(x1, z1, x2, z2, side):
    if side == "north":
        return [(x, z1) for x in range(x1, x2 + 1)]
    if side == "south":
        return [(x, z2) for x in range(x1, x2 + 1)]
    if side == "west":
        return [(x1, z) for z in range(z1, z2 + 1)]
    return [(x2, z) for z in range(z1, z2 + 1)]


class _null:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def chimney(m, x, z, y_from, y_to, key="cobblestone", fire=True):
    """1x1 stone chimney column with a campfire (smoke) on top."""
    for y in range(y_from, y_to + 1):
        m.put(x, y, z, key)
    if fire:
        m.put(x, y_to + 1, z, "campfire")
