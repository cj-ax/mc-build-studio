"""Mojang block/entity data loaded from data/ (bedrock-samples metadata)."""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


@lru_cache(maxsize=None)
def blocks():
    """{'minecraft:oak_stairs': {'weirdo_direction': [0,1,2,3], ...}, ...}"""
    raw = json.loads((DATA / "mojang-blocks.json").read_text())
    props = {p["name"]: [v["value"] for v in p["values"]] for p in raw["block_properties"]}
    return {
        item["name"]: {p["name"]: props[p["name"]] for p in item["properties"]}
        for item in raw["data_items"]
    }


@lru_cache(maxsize=None)
def entities():
    raw = json.loads((DATA / "mojang-entities.json").read_text())
    return {e["name"] for e in raw["data_items"]}


@lru_cache(maxsize=None)
def version():
    try:
        return json.loads((DATA / "version.json").read_text())["latest"]["version"]
    except (OSError, KeyError, ValueError):
        return "unknown"


def check_states(block_id, states):
    """Return a list of problems with a block id + states dict (empty when valid)."""
    known = blocks().get(block_id)
    if known is None:
        return [f"unknown block id {block_id}"]
    errs = []
    for name, value in states.items():
        if name not in known:
            errs.append(f"{block_id}: no state '{name}' (has {sorted(known)})")
        elif value not in known[name] or type(value) is not type(known[name][0]):
            errs.append(f"{block_id}: state {name}={value!r} not in {known[name]}")
    return errs
