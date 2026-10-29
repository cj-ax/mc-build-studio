"""Replay exported .mcfunction commands into a simulated world.

Supports exactly what the exporter writes: fill (incl. replace filter),
setblock, summon (optionally via execute align), tickingarea add/remove,
kill, say, function. Coordinates must be relative (~). Every placement is
checked against the /fill volume limit and against the ticking areas the
setup function added (so nothing lands in an unloaded chunk).
"""
import math
import re

from export.core import FILL_MAX

STATE_RE = re.compile(r'"([^"]+)"=("([^"]*)"|true|false|-?\d+)')


class SimError(Exception):
    pass


def parse_states(tok):
    if not (tok.startswith("[") and tok.endswith("]")):
        raise SimError(f"bad states {tok}")
    out = {}
    body = tok[1:-1]
    if not body:
        return out
    for m in STATE_RE.finditer(body):
        k, raw, s = m.group(1), m.group(2), m.group(3)
        out[k] = s if s is not None else True if raw == "true" else False if raw == "false" else int(raw)
    return out


def canon(bid, states):
    if not bid.startswith("minecraft:"):
        bid = "minecraft:" + bid
    if not states:
        return bid
    return bid + "[" + ",".join(f"{k}={states[k]!r}" for k in sorted(states)) + "]"


class World:
    def __init__(self, blocks=None):
        self.blocks = dict(blocks or {})      # (x,y,z) -> canon string; missing = air
        self.ticking = {}                     # name -> (x1,z1,x2,z2)
        self.entities = []
        self.log = []
        self.errors = []
        self.commands = 0

    def get(self, p):
        return self.blocks.get(p, "minecraft:air")

    def set(self, p, v):
        if v == "minecraft:air":
            self.blocks.pop(p, None)
        else:
            self.blocks[p] = v

    def loaded(self, x, z):
        for (x1, z1, x2, z2) in self.ticking.values():
            # chunk-level: a ticking area loads every chunk it touches
            if (x1 // 16) * 16 <= x <= (x2 // 16) * 16 + 15 and (z1 // 16) * 16 <= z <= (z2 // 16) * 16 + 15:
                return True
        return False


def coord(tok, base):
    if not tok.startswith("~"):
        raise SimError(f"absolute coordinate {tok!r} (exporter only writes ~ coordinates)")
    off = tok[1:]
    return base + (float(off) if off else 0.0)


def run_file(world, files, name, origin, depth=0, require_loaded=True):
    if depth > 8:
        raise SimError("function nesting too deep")
    if name not in files:
        raise SimError(f"function {name} not found")
    for ln, line in enumerate(files[name], 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            run_line(world, files, line, origin, depth, require_loaded)
        except SimError as e:
            world.errors.append(f"{name}:{ln}: {e} :: {line}")


def run_line(world, files, line, origin, depth, require_loaded):
    world.commands += 1
    t = line.split()
    ox, oy, oz = origin
    cmd = t[0]
    if cmd == "fill":
        a = [math.floor(coord(t[i], o)) for i, o in zip(range(1, 4), origin)]
        b = [math.floor(coord(t[i], o)) for i, o in zip(range(4, 7), origin)]
        bid, i = t[7], 8
        states = {}
        if i < len(t) and t[i].startswith("["):
            states, i = parse_states(t[i]), i + 1
        mode, flt = "replace", None
        if i < len(t):
            mode = t[i]
            i += 1
            if mode == "replace" and i < len(t):
                fs = {}
                fb = t[i]
                if i + 1 < len(t) and t[i + 1].startswith("["):
                    fs = parse_states(t[i + 1])
                flt = canon(fb, fs) if fs else canon(fb, {})
        lo = [min(p, q) for p, q in zip(a, b)]
        hi = [max(p, q) for p, q in zip(a, b)]
        vol = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
        if vol > FILL_MAX:
            raise SimError(f"fill volume {vol} > {FILL_MAX}")
        v = canon(bid, states)
        for x in range(lo[0], hi[0] + 1):
            for z in range(lo[2], hi[2] + 1):
                if require_loaded and not world.loaded(x, z):
                    raise SimError(f"fill touches unloaded column {x},{z}")
                for y in range(lo[1], hi[1] + 1):
                    p = (x, y, z)
                    if flt is not None:
                        cur = world.get(p)
                        if cur != flt and cur.split("[")[0] != flt:
                            continue
                    elif mode == "keep" and world.get(p) != "minecraft:air":
                        continue
                    world.set(p, v)
    elif cmd == "setblock":
        p = tuple(math.floor(coord(t[i], o)) for i, o in zip(range(1, 4), origin))
        states = parse_states(t[5]) if len(t) > 5 and t[5].startswith("[") else {}
        if require_loaded and not world.loaded(p[0], p[2]):
            raise SimError(f"setblock in unloaded column {p[0]},{p[2]}")
        world.set(p, canon(t[4], states))
    elif cmd == "execute":
        if t[1:4] != ["align", "xyz", "run"]:
            raise SimError("unsupported execute form")
        aligned = tuple(math.floor(c) for c in origin)
        run_line(world, files, " ".join(t[4:]), aligned, depth, require_loaded)
        world.commands -= 1
    elif cmd == "summon":
        rest = t[2:]
        name = None
        if rest and rest[0].startswith('"'):
            name = rest[0].strip('"')
            rest = rest[1:]
        pos = tuple(coord(rest[i], o) for i, o in zip(range(3), origin))
        world.entities.append(dict(id=t[1], name=name, pos=pos))
    elif cmd == "tickingarea":
        if t[1] == "add":
            a = [math.floor(coord(t[i], o)) for i, o in zip(range(2, 5), origin)]
            b = [math.floor(coord(t[i], o)) for i, o in zip(range(5, 8), origin)]
            if len(world.ticking) >= 10:
                raise SimError("more than 10 ticking areas")
            world.ticking[t[8]] = (min(a[0], b[0]), min(a[2], b[2]), max(a[0], b[0]), max(a[2], b[2]))
        elif t[1] == "remove":
            world.ticking.pop(t[2], None)
    elif cmd == "function":
        run_file(world, files, t[1].split("/", 2)[-1].split("/")[-1], origin, depth + 1, require_loaded)
    elif cmd in ("kill", "say"):
        pass
    else:
        raise SimError(f"unknown command {cmd}")
