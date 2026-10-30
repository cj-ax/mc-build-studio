"""Natural ground: value noise, slope relaxation (no step over 1 block unless it is a cliff),
cliff faces, winding lanes and scattered nature. Heights are feet levels (grass top at h-1)."""
import math
import random

from lib.voxel import DIRV


def value_noise(seed, scale):
    """Smooth 2D value noise in 0..1 with features about `scale` blocks across."""
    def g(i, j):
        return random.Random(seed * 1000003 + i * 7919 + j * 104729).random()

    def f(x, z):
        fx, fz = x / scale, z / scale
        i, j = math.floor(fx), math.floor(fz)
        tx, tz = fx - i, fz - j
        sx, sz = tx * tx * (3 - 2 * tx), tz * tz * (3 - 2 * tz)
        a = g(i, j) + (g(i + 1, j) - g(i, j)) * sx
        b = g(i, j + 1) + (g(i + 1, j + 1) - g(i, j + 1)) * sx
        return a + (b - a) * sz
    return f


def relax(H, fixed, edge=0, passes=80):
    """Clamp every non-fixed cell to within 1 block of its neighbours. Cells missing from H
    count as `edge` (a number, None to ignore them, or a function (x, z) -> number/None).
    Fixed cells (pads) never move."""
    keys = sorted(H)
    edge_fn = edge if callable(edge) else (lambda x, z: edge)
    for _ in range(passes):
        changed = False
        for k in keys:
            if k in fixed:
                continue
            x, z = k
            nb = []
            for dx, dz in DIRV.values():
                n = (x + dx, z + dz)
                nb.append(H[n] if n in H else edge_fn(*n))
            nb = [n for n in nb if n is not None]
            if not nb:
                continue
            lo, hi = max(nb) - 1, min(nb) + 1
            h = H[k]
            nh = (lo + hi) // 2 if lo > hi else min(max(h, lo), hi)
            if nh != h:
                H[k] = nh
                changed = True
        if not changed:
            break


def cliff_faces(m, H, stones=("stone", "andesite", "tuff", "granite", "cobblestone"), seed=0, skip=None):
    """Wherever the ground drops 2 or more blocks to a neighbour, face the drop with rock."""
    r = random.Random(seed)
    for (x, z), h in H.items():
        low = min(H.get((x + dx, z + dz), h) for dx, dz in DIRV.values())
        if h - low >= 2 and not (skip and skip(x, z)):
            for y in range(low - 1, h):
                if m.empty(x, y, z):
                    m.put(x, y, z, r.choice(stones))


def smooth_line(points, step=0.35):
    """Catmull-Rom through the points, rasterised to unique cells in order."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        seg = max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]), 1)
        n = int(seg / step) + 1
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            z = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            c = (round(x), round(z))
            if not out or out[-1] != c:
                out.append(c)
    if out[-1] != tuple(points[-1]):
        out.append(tuple(points[-1]))
    return out


def widen(cells, width):
    """A centre line of cells widened to a `width` x `width` brush."""
    out = set()
    lo, hi = -(width // 2), width - width // 2
    for (x, z) in cells:
        for dx in range(lo, hi):
            for dz in range(lo, hi):
                out.add((x + dx, z + dz))
    return out


def surface(m, cells, H, key="gravel", mix=None, seed=0, keep=None):
    """Lay a surface block into the grass layer (y = H - 1) of each cell."""
    r = random.Random(seed)
    for (x, z) in sorted(cells):
        if (x, z) not in H or (keep and keep(x, z)):
            continue
        k = key
        for alt, frac in (mix or {}).items():
            if r.random() < frac:
                k = alt
                break
        y = H[(x, z)] - 1
        c = m.get(x, y, z)
        if c is None or c.key in ("grass_block", "dirt"):
            m.put(x, y, z, k)


def scatter(m, cells, H, choices, density, seed=0, soil="grass_block", blocked=None):
    """Plants on grass: choices = [(key, weight)]. Tall plants take two blocks."""
    from lib.outdoor import TALL
    r = random.Random(seed)
    keys = [k for k, _ in choices]
    weights = [w for _, w in choices]
    n = 0
    for (x, z) in sorted(cells):
        if r.random() > density or (blocked and blocked(x, z)):
            continue
        y = H[(x, z)]
        if not (m.empty(x, y, z) and m.empty(x, y + 1, z)):
            continue
        below = m.get(x, y - 1, z)
        if below is not None and below.key not in ("grass_block", "dirt", "moss_block", "podzol"):
            continue
        k = r.choices(keys, weights)[0]
        if k in TALL:
            m.tall_plant(x, y, z, k)
        else:
            m.put(x, y, z, k)
        n += 1
    return n
