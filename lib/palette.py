"""Palette access: prop defaults, rotation and Bedrock state resolution."""
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blocks.palette import BLOCKS, DIR4, write_json  # noqa: E402
from lib.blockdata import check_states  # noqa: E402

FACINGS = ["north", "east", "south", "west"]   # build facing -> quarter turns clockwise


def block(key):
    try:
        return BLOCKS[key]
    except KeyError:
        raise KeyError(f"unknown block key '{key}' (not in blocks/palette.py)") from None


def full_props(key, props):
    """Defaults merged with given props; raises on unknown props/values."""
    b = block(key)
    out = dict(b["props"])
    for p, v in (props or {}).items():
        if p not in b["props"]:
            raise ValueError(f"{key}: unknown prop '{p}' (has {sorted(b['props'])})")
        m = b["map"].get(p)
        if m and v not in m["values"]:
            raise ValueError(f"{key}: {p}={v!r} not one of {list(m['values'])}")
        out[p] = v
    return out


def rot_dir(d, turns):
    if d in DIR4:
        return DIR4[(DIR4.index(d) + turns) % 4]
    return d


def rotate_props(key, props, turns):
    """Props after turning the build `turns` quarter turns clockwise (viewed from above)."""
    if turns % 4 == 0 or not props:
        return props
    b = block(key)
    out = dict(props)
    for p, rule in b["rotate"].items():
        if p not in out:
            continue
        if rule == "dir4":
            out[p] = rot_dir(out[p], turns)
        elif rule == "axis" and turns % 2 == 1:
            out[p] = {"x": "z", "z": "x"}.get(out[p], out[p])
    return out


def rotate_pos(x, z, turns):
    """Rotate (x, z) clockwise around the origin: north (0,-1) -> east (1,0)."""
    for _ in range(turns % 4):
        x, z = -z, x
    return x, z


def states_for(key, props, derived=None):
    """Bedrock (id, states) for a block key + full props (+ exporter-computed states)."""
    b = block(key)
    states = dict(b["states"])
    for p, v in props.items():
        m = b["map"].get(p)
        if m:
            states[m["state"]] = m["values"][v]
    if derived:
        states.update(derived)
    return b["id"], states


def validate_palette():
    """Check every block, every prop combination, in all four facings."""
    errors = []
    for key, b in BLOCKS.items():
        names = list(b["props"])
        choices = [list(b["map"][p]["values"]) if p in b["map"] else [b["props"][p]] for p in names]
        for combo in itertools.product(*choices) if names else [()]:
            props = dict(zip(names, combo))
            for turns in range(4):
                rp = rotate_props(key, props, turns)
                bid, st = states_for(key, rp, sample_derived(b))
                for e in check_states(bid, st):
                    errors.append(f"[{key} turn {turns}] {e}")
    return sorted(set(errors))


def sample_derived(b):
    d = {}
    if "corner" in b["derived"]:
        d["minecraft:corner"] = "outer_left"
    if "connections" in b["derived"]:
        d.update({f"minecraft:connection_{s}": True for s in ("north", "east", "south", "west")})
    if "walls" in b["derived"]:
        d.update({f"wall_connection_type_{s}": "short" for s in ("north", "east", "south", "west")})
        d["wall_post_bit"] = True
    return d


if __name__ == "__main__":
    errs = validate_palette()
    print("\n".join(errs) or f"palette ok: {len(BLOCKS)} blocks")
    write_json()
