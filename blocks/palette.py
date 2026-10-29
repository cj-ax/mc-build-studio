"""The block palette: every block key a build can use.

Each entry maps a short key (what build.py writes) to:
  id       Bedrock block id (validated against data/mojang-blocks.json)
  shape    how the viewer draws it and how checks treat it
  props    model-level properties with defaults (facing, half, axis, open, ...)
  map      how each prop value becomes a Bedrock state
  rotate   how each prop changes when the build is turned to another facing
  states   fixed Bedrock states always written
  derived  states the exporter computes from neighbours (stair corners,
           fence/pane/wall connections)
  color    average colour (plan maps, ghost blocks, picker)
  tex      procedural pixel texture per face: [pattern, colour, colour...]
  light    block light emitted (0-15)

Run `python3 studio.py palette` to rewrite blocks/palette.json (the viewer reads
it) and validate every entry in all four facings.
"""
import json
from pathlib import Path

DIR4 = ["north", "east", "south", "west"]
CARD = {d: d for d in DIR4}
WEIRDO = {"east": 0, "west": 1, "south": 2, "north": 3}
LADDER = {"north": 2, "south": 3, "west": 4, "east": 5}
BEDDIR = {"south": 0, "west": 1, "north": 2, "east": 3}
FACING6 = {"down": 0, "up": 1, "north": 2, "south": 3, "west": 4, "east": 5}
BOOL = {False: False, True: True}

# Shape -> behaviour flags used by the viewer and the checks.
#   full: fills the cell; opaque: blocks light and hides neighbour faces;
#   sturdy: ladders / wall torches can attach to its sides;
#   top: something can stand on it; walk: a player can occupy the cell;
#   climb: player can move up inside it; bottom: can hold a hanging lantern
SHAPES = {
    "cube":       dict(full=1, opaque=1, sturdy=1, top=1, walk=0, bottom=1),
    "log":        dict(full=1, opaque=1, sturdy=1, top=1, walk=0, bottom=1),
    "glass":      dict(full=1, opaque=0, sturdy=0, top=1, walk=0, bottom=1),
    "leaves":     dict(full=1, opaque=0, sturdy=0, top=1, walk=0, bottom=1),
    "slab":       dict(full=0, opaque=0, lightblock=1, sturdy=0, top=1, walk=0, bottom=1),
    "stair":      dict(full=0, opaque=0, lightblock=1, sturdy=0, top=1, walk=0, bottom=1),
    "path":       dict(full=1, opaque=1, sturdy=1, top=1, walk=0, bottom=1),
    "fence":      dict(full=0, opaque=0, sturdy=0, top=1, walk=0, bottom=1, tall=1),
    "wall":       dict(full=0, opaque=0, sturdy=0, top=1, walk=0, bottom=1, tall=1),
    "pane":       dict(full=0, opaque=0, sturdy=0, top=1, walk=0, bottom=0),
    "fence_gate": dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "door":       dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "trapdoor":   dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "plant":      dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "tall_plant": dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "crop":       dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "flat":       dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "carpet":     dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "ladder":     dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0, climb=1),
    "lantern":    dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "torch":      dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
    "chain":      dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=1),
    "water":      dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0, climb=1, liquid=1),
    "bed":        dict(full=0, opaque=0, sturdy=0, top=1, walk=0, bottom=0),
    "chest":      dict(full=0, opaque=0, sturdy=0, top=1, walk=0, bottom=0),
    "campfire":   dict(full=0, opaque=0, sturdy=0, top=1, walk=0, bottom=0),
    "pot":        dict(full=0, opaque=0, sturdy=0, top=0, walk=0, bottom=0),
    "air":        dict(full=0, opaque=0, sturdy=0, top=0, walk=1, bottom=0),
}

# What each shape needs to stay in place (checked by export/checks.py).
NEEDS = {
    "door": "below_top", "bed": "below_top", "carpet": "below_top", "pot": "below_top",
    "crop": "farmland", "ladder": "behind_sturdy", "torch": "torch", "lantern": "lantern",
    "flat": "water_or_top",
}

BLOCKS = {}


def add(key, id, shape="cube", name=None, cat="building", color="#888888", tex=None,
        props=None, map=None, rotate=None, states=None, derived=None, light=0,
        needs=None, item_cells=1):
    assert key not in BLOCKS, key
    props = dict(props or {})
    rotate = dict(rotate or {})
    for p in props:
        if p not in rotate:
            rotate[p] = {"facing": "dir4", "axis": "axis"}.get(p, "none")
    BLOCKS[key] = {
        "id": id if id.startswith("minecraft:") else "minecraft:" + id,
        "name": name or key.replace("_", " ").title(),
        "cat": cat, "shape": shape, "color": color,
        "tex": tex or {"all": ["noise", color]},
        "props": props, "map": {k: {"state": s, "values": v} for k, (s, v) in (map or {}).items()},
        "rotate": rotate, "states": dict(states or {}), "derived": list(derived or []),
        "light": light, "flags": SHAPES[shape], "needs": needs or NEEDS.get(shape),
        "item_cells": item_cells,
    }


# ---------------------------------------------------------------- wood
WOODS = {
    #  name       planks     bark       log top    stripped   leaves
    "oak":      ("#a2834f", "#6b5430", "#b39257", "#b08e57", "#4b7d2a"),
    "spruce":   ("#735531", "#3b2a17", "#75582f", "#77593a", "#3a5e3a"),
    "birch":    ("#c4b27a", "#d9d8d2", "#c1ab73", "#c5b07a", "#678c42"),
    "dark_oak": ("#4c3219", "#3a2c19", "#4f3a22", "#5f4a30", "#3c6a20"),
    "cherry":   ("#e3b5a7", "#3a1f27", "#d9a597", "#d8a49a", "#f0a9c9"),
    "jungle":   ("#a07351", "#574317", "#a37d4f", "#ab8455", "#3f8a21"),
    "acacia":   ("#a85a32", "#676157", "#a35a35", "#ae5d3b", "#5e8a24"),
}
STAIR_MAP = {"facing": ("weirdo_direction", WEIRDO), "half": ("upside_down_bit", {"bottom": False, "top": True})}
SLAB_MAP = {"half": ("minecraft:vertical_half", {"bottom": "bottom", "top": "top"})}
AXIS_MAP = {"axis": ("pillar_axis", {"x": "x", "y": "y", "z": "z"})}

for w, (planks, bark, top, stripped, leaves) in WOODS.items():
    t = w.replace("_", " ").title()
    pl = {"all": ["planks", planks]}
    add(f"{w}_planks", f"{w}_planks", name=f"{t} Planks", cat="wood", color=planks, tex=pl)
    bark_pat = "birch_bark" if w == "birch" else "bark"
    add(f"{w}_log", f"{w}_log", "log", f"{t} Log", "wood", bark,
        {"side": [bark_pat, bark], "end": ["log_top", top, bark]}, {"axis": "y"}, AXIS_MAP)
    add(f"stripped_{w}_log", f"stripped_{w}_log", "log", f"Stripped {t} Log", "wood", stripped,
        {"side": ["stripped", stripped], "end": ["log_top", top, stripped]}, {"axis": "y"}, AXIS_MAP)
    add(f"{w}_wood", f"{w}_wood", "log", f"{t} Wood", "wood", bark,
        {"all": [bark_pat, bark]}, {"axis": "y"}, AXIS_MAP)
    add(f"{w}_stairs", f"{w}_stairs", "stair", f"{t} Stairs", "wood", planks, pl,
        {"facing": "north", "half": "bottom"}, STAIR_MAP, derived=["corner"])
    add(f"{w}_slab", f"{w}_slab", "slab", f"{t} Slab", "wood", planks, pl, {"half": "bottom"}, SLAB_MAP)
    add(f"{w}_fence", f"{w}_fence", "fence", f"{t} Fence", "wood", planks, pl, derived=["connections"])
    add(f"{w}_fence_gate", "fence_gate" if w == "oak" else f"{w}_fence_gate", "fence_gate",
        f"{t} Fence Gate", "wood", planks, pl, {"facing": "north", "open": False},
        {"facing": ("minecraft:cardinal_direction", CARD), "open": ("open_bit", BOOL)},
        states={"in_wall_bit": False})
    add(f"{w}_door", "wooden_door" if w == "oak" else f"{w}_door", "door", f"{t} Door", "wood", planks,
        {"all": ["door", planks]},
        {"facing": "north", "hinge": "left", "open": False, "upper": False},
        {"facing": ("minecraft:cardinal_direction", CARD), "hinge": ("door_hinge_bit", {"left": False, "right": True}),
         "open": ("open_bit", BOOL), "upper": ("upper_block_bit", BOOL)}, item_cells=2)
    add(f"{w}_trapdoor", "trapdoor" if w == "oak" else f"{w}_trapdoor", "trapdoor", f"{t} Trapdoor", "wood",
        planks, {"all": ["trapdoor", planks]}, {"facing": "north", "half": "bottom", "open": False},
        {"facing": ("direction", WEIRDO), "half": ("upside_down_bit", {"bottom": False, "top": True}),
         "open": ("open_bit", BOOL)})
    add(f"{w}_leaves", f"{w}_leaves", "leaves", f"{t} Leaves", "nature", leaves,
        {"all": ["leaves", leaves]}, states={"persistent_bit": True})

# ---------------------------------------------------------------- stone & masonry
STONES = [
    # key                 block id              stairs id                    slab id                    wall id                   colour     pattern
    ("cobblestone",       "cobblestone",        "stone_stairs",              "cobblestone_slab",        "cobblestone_wall",       "#7a7a7a", "cobble"),
    ("mossy_cobblestone", "mossy_cobblestone",  "mossy_cobblestone_stairs",  "mossy_cobblestone_slab",  "mossy_cobblestone_wall", "#6f7a5c", "mossy_cobble"),
    ("stone",             "stone",              "normal_stone_stairs",       "normal_stone_slab",       None,                     "#7f7f7f", "stone"),
    ("stone_bricks",      "stone_bricks",       "stone_brick_stairs",        "stone_brick_slab",        "stone_brick_wall",       "#7b7b7b", "stone_bricks"),
    ("mossy_stone_bricks", "mossy_stone_bricks", "mossy_stone_brick_stairs", "mossy_stone_brick_slab",  "mossy_stone_brick_wall", "#737b68", "mossy_bricks"),
    ("smooth_stone",      "smooth_stone",       None,                        "smooth_stone_slab",       None,                     "#a0a0a0", "smooth"),
    ("bricks",            "brick_block",        "brick_stairs",              "brick_slab",              "brick_wall",             "#966353", "bricks"),
    ("polished_andesite", "polished_andesite",  "polished_andesite_stairs",  "polished_andesite_slab",  None,                     "#868887", "smooth"),
    ("deepslate_tiles",   "deepslate_tiles",    "deepslate_tile_stairs",     "deepslate_tile_slab",     "deepslate_tile_wall",    "#3a3a3c", "tiles"),
    ("cobbled_deepslate", "cobbled_deepslate",  "cobbled_deepslate_stairs",  "cobbled_deepslate_slab",  "cobbled_deepslate_wall", "#505053", "cobble"),
    ("mud_bricks",        "mud_bricks",         "mud_brick_stairs",          "mud_brick_slab",          "mud_brick_wall",         "#8a6a50", "bricks_large"),
    ("tuff_bricks",       "tuff_bricks",        "tuff_brick_stairs",         "tuff_brick_slab",         "tuff_brick_wall",        "#626a5f", "stone_bricks"),
    ("sandstone",         "sandstone",          "sandstone_stairs",          "sandstone_slab",          "sandstone_wall",         "#d8cb9b", "sandstone"),
]
WALL_STATES = ["wall"]
for key, bid, stairs, slab, wall, color, pat in STONES:
    t = key.replace("_", " ").title()
    tx = {"all": [pat, color]}
    add(key, bid, name=t, cat="stone", color=color, tex=tx)
    base = key[:-1] if key.endswith("bricks") or key.endswith("tiles") else key
    if stairs:
        add(f"{base}_stairs", stairs, "stair", f"{t} Stairs", "stone", color, tx,
            {"facing": "north", "half": "bottom"}, STAIR_MAP, derived=["corner"])
    if slab:
        add(f"{base}_slab", slab, "slab", f"{t} Slab", "stone", color, tx, {"half": "bottom"}, SLAB_MAP)
    if wall:
        add(f"{base}_wall", wall, "wall", f"{t} Wall", "stone", color, tx, derived=["walls"])

add("andesite", "andesite", name="Andesite", cat="stone", color="#888889", tex={"all": ["stone", "#888889"]})
add("calcite", "calcite", name="Calcite", cat="stone", color="#dfe0dc", tex={"all": ["smooth", "#dfe0dc"]})
add("packed_mud", "packed_mud", name="Packed Mud", cat="stone", color="#8e6b53", tex={"all": ["noise", "#8e6b53"]})
for col, hexc in [("white", "#d2b2a1"), ("light_gray", "#876a61"), ("orange", "#a1531d"), ("brown", "#4d3324")]:
    add(f"{col}_terracotta", f"{col}_terracotta", name=f"{col.replace('_', ' ').title()} Terracotta",
        color=hexc, tex={"all": ["flat", hexc]})
add("terracotta", "hardened_clay", name="Terracotta", color="#985e43", tex={"all": ["flat", "#985e43"]})
for col, hexc in [("white", "#e9ecec"), ("red", "#a12722"), ("light_gray", "#8e8e86"), ("brown", "#724728"),
                  ("yellow", "#f8c527"), ("blue", "#35399d"), ("green", "#546d1b"), ("lime", "#70b919")]:
    t = col.replace("_", " ").title()
    add(f"{col}_wool", f"{col}_wool", name=f"{t} Wool", cat="deco", color=hexc, tex={"all": ["wool", hexc]})
    add(f"{col}_carpet", f"{col}_carpet", "carpet", f"{t} Carpet", "deco", hexc, {"all": ["wool", hexc]})
for col, hexc in [("white", "#cfd5d6"), ("gray", "#373a3e")]:
    add(f"{col}_concrete", f"{col}_concrete", name=f"{col.title()} Concrete", color=hexc, tex={"all": ["flat", hexc]})

# ---------------------------------------------------------------- ground
add("grass_block", "grass_block", name="Grass Block", cat="nature", color="#7cb34a",
    tex={"top": ["grass_top", "#79b34a"], "side": ["grass_side", "#79b34a", "#86603f"], "bottom": ["dirt", "#86603f"]})
add("dirt", "dirt", name="Dirt", cat="nature", color="#86603f", tex={"all": ["dirt", "#86603f"]})
add("coarse_dirt", "coarse_dirt", name="Coarse Dirt", cat="nature", color="#77553b", tex={"all": ["gravel", "#77553b"]})
add("podzol", "podzol", name="Podzol", cat="nature", color="#5c3f1b",
    tex={"top": ["dirt", "#5c3f1b"], "side": ["grass_side", "#6a4a24", "#86603f"], "bottom": ["dirt", "#86603f"]})
add("dirt_path", "grass_path", "path", "Dirt Path", "nature", "#94793f",
    {"top": ["path", "#94793f"], "side": ["grass_side", "#94793f", "#86603f"], "bottom": ["dirt", "#86603f"]})
add("farmland", "farmland", "path", "Farmland", "nature", "#4f3420",
    {"top": ["farmland", "#4f3420"], "side": ["dirt", "#86603f"], "bottom": ["dirt", "#86603f"]},
    states={"moisturized_amount": 7})
add("sand", "sand", name="Sand", cat="nature", color="#dbcfa3", tex={"all": ["noise", "#dbcfa3"]})
add("gravel", "gravel", name="Gravel", cat="nature", color="#857f7d", tex={"all": ["gravel", "#857f7d"]})
add("moss_block", "moss_block", name="Moss Block", cat="nature", color="#596e2d", tex={"all": ["noise", "#596e2d"]})
add("moss_carpet", "moss_carpet", "carpet", "Moss Carpet", "nature", "#596e2d", {"all": ["noise", "#596e2d"]})
add("clay", "clay", name="Clay", cat="nature", color="#a0a6b3", tex={"all": ["smooth", "#a0a6b3"]})
add("mud", "mud", name="Mud", cat="nature", color="#3c393c", tex={"all": ["noise", "#3c393c"]})
add("water", "water", "water", "Water", "nature", "#3f76e4", {"all": ["water", "#3f76e4"]},
    states={"liquid_depth": 0})
add("hay_block", "hay_block", "log", "Hay Bale", "nature", "#c0a21c",
    {"side": ["hay_side", "#c0a21c"], "end": ["hay_top", "#c0a21c"]}, {"axis": "y"}, AXIS_MAP)
add("pumpkin", "pumpkin", name="Pumpkin", cat="nature", color="#c87a17",
    tex={"top": ["pumpkin_top", "#c87a17"], "side": ["pumpkin_side", "#c87a17"]},
    props={"facing": "north"}, map={"facing": ("minecraft:cardinal_direction", CARD)})
add("melon", "melon_block", name="Melon", cat="nature", color="#6f9c25",
    tex={"top": ["noise", "#8d9c2b"], "side": ["melon", "#6f9c25"]})

# ---------------------------------------------------------------- plants
PLANTS = [  # key, id, colours (stem, petal, centre)
    ("short_grass", "short_grass", ["grass_plant", "#6aa84f"]),
    ("fern", "fern", ["fern", "#5f9a46"]),
    ("poppy", "poppy", ["flower", "#3f7a24", "#d7302a", "#2a1a10"]),
    ("dandelion", "dandelion", ["flower", "#4f8a2a", "#f2d32b", "#e8a515"]),
    ("cornflower", "cornflower", ["flower", "#3f7a24", "#4a6ee0", "#2a3a8a"]),
    ("oxeye_daisy", "oxeye_daisy", ["flower", "#4f8a2a", "#f2f2ea", "#e8c515"]),
    ("azure_bluet", "azure_bluet", ["flower", "#4f8a2a", "#dde8f0", "#e8d515"]),
    ("allium", "allium", ["flower_ball", "#4f8a2a", "#b46ce0", "#d79af5"]),
    ("red_tulip", "red_tulip", ["tulip", "#4f8a2a", "#d33a2a", "#a02010"]),
    ("pink_tulip", "pink_tulip", ["tulip", "#4f8a2a", "#efb3c8", "#d38aa5"]),
    ("orange_tulip", "orange_tulip", ["tulip", "#4f8a2a", "#ef8a2a", "#c56010"]),
    ("lily_of_the_valley", "lily_of_the_valley", ["flower", "#3f7a24", "#ffffff", "#ffffff"]),
    ("bush", "bush", ["bush", "#4f8a2a"]),
]
for key, bid, tx in PLANTS:
    add(key, bid, "plant", cat="plants", color=tx[2] if len(tx) > 2 else tx[1], tex={"all": tx}, needs="soil")
add("sweet_berry_bush", "sweet_berry_bush", "plant", cat="plants", color="#2f5a2a",
    tex={"all": ["berry_bush", "#2f5a2a", "#b0202a"]}, states={"growth": 3}, needs="soil")
add("sugar_cane", "reeds", "plant", cat="plants", color="#8fc06a", tex={"all": ["cane", "#8fc06a"]},
    states={"age": 0}, needs="soil")
for key, bid, tx in [("tall_grass", "tall_grass", ["grass_plant", "#6aa84f"]),
                     ("large_fern", "large_fern", ["fern", "#5f9a46"]),
                     ("lilac", "lilac", ["flower_ball", "#4f8a2a", "#c38ad1", "#e3b2ee"]),
                     ("rose_bush", "rose_bush", ["flower_ball", "#3f7a24", "#c8282a", "#e05050"]),
                     ("peony", "peony", ["flower_ball", "#4f8a2a", "#e8b5e5", "#f5d3f0"]),
                     ("sunflower", "sunflower", ["sunflower", "#4f8a2a", "#f2c51b", "#5a3a10"])]:
    add(key, bid, "tall_plant", cat="plants", color=tx[2] if len(tx) > 2 else tx[1], tex={"all": tx},
        props={"upper": False}, map={"upper": ("upper_block_bit", BOOL)}, needs="soil", item_cells=2)
for key, bid, col in [("wheat", "wheat", "#c9b23a"), ("carrots", "carrots", "#e8902a"),
                      ("potatoes", "potatoes", "#c8b060"), ("beetroot", "beetroot", "#a0303a")]:
    add(key, bid, "crop", cat="plants", color=col, tex={"all": ["crop", "#5aa03a", col]},
        props={"age": 7}, map={"age": ("growth", {i: i for i in range(8)})})
add("lily_pad", "waterlily", "flat", "Lily Pad", "plants", "#208030", {"all": ["lily", "#208030"]})
add("pink_petals", "pink_petals", "flat", "Pink Petals", "plants", "#f5a8c8", {"all": ["petals", "#f5a8c8"]},
    props={"facing": "north"}, map={"facing": ("minecraft:cardinal_direction", CARD)},
    states={"growth": 3}, needs="below_top")

# ---------------------------------------------------------------- glass & openings
add("glass", "glass", "glass", "Glass", "deco", "#cfe8ec", {"all": ["glass", "#cfe8ec"]})
add("glass_pane", "glass_pane", "pane", "Glass Pane", "deco", "#cfe8ec", {"all": ["glass", "#cfe8ec"]},
    derived=["connections"])
add("light_blue_glass_pane", "light_blue_stained_glass_pane", "pane", "Light Blue Glass Pane", "deco",
    "#8fb8e8", {"all": ["glass_tint", "#8fb8e8"]}, derived=["connections"])
add("iron_bars", "iron_bars", "pane", "Iron Bars", "deco", "#7a7a7a", {"all": ["bars", "#8a8c8c"]},
    derived=["connections"])
add("ladder", "ladder", "ladder", "Ladder", "utility", "#8a6a3a", {"all": ["ladder", "#9a7a45"]},
    {"facing": "north"}, {"facing": ("facing_direction", LADDER)})

# ---------------------------------------------------------------- light
add("lantern", "lantern", "lantern", "Lantern", "light", "#4a4f58", {"all": ["lantern", "#4a4f58", "#ffd27a"]},
    {"hanging": False}, {"hanging": ("hanging", BOOL)}, light=15)
add("soul_lantern", "soul_lantern", "lantern", "Soul Lantern", "light", "#4a4f58",
    {"all": ["lantern", "#4a4f58", "#7ae8f0"]}, {"hanging": False}, {"hanging": ("hanging", BOOL)}, light=10)
add("torch", "torch", "torch", "Torch", "light", "#ffcf5a", {"all": ["torch", "#6b5430", "#ffcf5a"]},
    {"facing": "up"}, {"facing": ("torch_facing_direction",
                                  {"up": "top", "north": "north", "south": "south", "east": "east", "west": "west"})},
    light=14)
add("glowstone", "glowstone", name="Glowstone", cat="light", color="#e0b05a", tex={"all": ["glow", "#e0b05a"]}, light=15)
add("sea_lantern", "sea_lantern", name="Sea Lantern", cat="light", color="#c0d8d0", tex={"all": ["glow", "#c8e0d8"]}, light=15)
add("campfire", "campfire", "campfire", "Campfire", "light", "#6b5430",
    {"top": ["campfire_top", "#6b5430", "#ffa030"], "side": ["log_side_dark", "#5b4428"]},
    {"facing": "north"}, {"facing": ("minecraft:cardinal_direction", CARD)}, states={"extinguished": False}, light=15)
add("iron_chain", "iron_chain", "chain", "Chain", "light", "#3a3f48", {"all": ["chain", "#3a3f48"]},
    {"axis": "y"}, AXIS_MAP)

# ---------------------------------------------------------------- furniture & utility
add("chest", "chest", "chest", "Chest", "utility", "#a0702c",
    {"all": ["chest", "#a0702c", "#3a3a3a"]}, {"facing": "north"}, {"facing": ("minecraft:cardinal_direction", CARD)})
add("barrel", "barrel", "cube", "Barrel", "utility", "#8a6538",
    {"top": ["barrel_top", "#8a6538"], "bottom": ["barrel_top", "#8a6538"], "side": ["barrel_side", "#8a6538"]},
    {"facing": "up"}, {"facing": ("facing_direction", FACING6)}, states={"open_bit": False})
add("crafting_table", "crafting_table", name="Crafting Table", cat="utility", color="#9a6c3a",
    tex={"top": ["crafting_top", "#9a6c3a"], "side": ["crafting_side", "#9a6c3a"], "bottom": ["planks", "#a2834f"]})
add("furnace", "furnace", name="Furnace", cat="utility", color="#6e6e6e",
    tex={"all": ["smooth", "#6e6e6e"], "front": ["furnace_front", "#6e6e6e"]},
    props={"facing": "north"}, map={"facing": ("minecraft:cardinal_direction", CARD)})
add("smoker", "smoker", name="Smoker", cat="utility", color="#5a5048",
    tex={"all": ["smooth", "#5a5048"], "front": ["furnace_front", "#5a5048"]},
    props={"facing": "north"}, map={"facing": ("minecraft:cardinal_direction", CARD)})
add("bookshelf", "bookshelf", name="Bookshelf", cat="utility", color="#7a5a35",
    tex={"top": ["planks", "#a2834f"], "side": ["bookshelf", "#a2834f"]})
add("composter", "composter", "chest", "Composter", "utility", "#7a5530", {"all": ["planks", "#7a5530"]},
    states={"composter_fill_level": 0})
add("flower_pot", "flower_pot", "pot", "Flower Pot", "deco", "#7a4030", {"all": ["noise", "#7a4030"]},
    states={"update_bit": False})
add("red_bed", "bed", "bed", "Bed", "utility", "#a12722", {"top": ["bed", "#a12722", "#e9ecec"], "side": ["wool", "#a12722"]},
    {"facing": "north", "head": False}, {"facing": ("direction", BEDDIR), "head": ("head_piece_bit", BOOL)},
    states={"occupied_bit": False}, item_cells=2)
add("iron_block", "iron_block", name="Iron Block", cat="utility", color="#d8d8d8", tex={"all": ["metal", "#d8d8d8"]})
add("gold_block", "gold_block", name="Gold Block", cat="utility", color="#f5d84a", tex={"all": ["metal", "#f5d84a"]})
add("beacon", "beacon", "glass", "Beacon", "light", "#7ae0e0", {"all": ["glow", "#9af0e8"]}, light=15)

# Explicit air: carves terrain / existing blocks. Never counted.
add("air", "air", "air", "Air", "utility", "#000000", {"all": ["flat", "#000000"]})


def palette():
    return BLOCKS


def write_json(path=None):
    from lib.blockdata import version
    path = Path(path or Path(__file__).with_name("palette.json"))
    data = {"data_version": version(), "shapes": SHAPES, "blocks": BLOCKS}
    path.write_text(json.dumps(data, indent=1))
    return path
