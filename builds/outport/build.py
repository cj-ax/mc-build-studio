"""Gannet Cove: a Newfoundland outport grown up a rocky hillside around its harbour. Lanes wind
up from Water Street between jellybean saltboxes, gable houses and biscuit boxes set at every
angle on their own levelled lots, with spruce, scrub and bare rock in between. Below, the
waterfront is a tangle of fishing stages on stilts, crooked walkways, a government wharf with
the fish plant, a marina of finger piers, a boathouse, a pub out over the water, a rock islet with
its own stage, a lighthouse on a cliff headland, and boats everywhere. The church, the school
and a lookout sit at the top of the hill. No water is placed: the piers stand in your harbour."""
import math
import random

from lib import *
from lib.palette import FACINGS
from lib.voxel import rect_through, stamp_transform

TITLE = "Gannet Cove"
SUBTITLE = "Newfoundland outport · Minecraft Bedrock build book · no water placed"
SUBJECT = "Cove"
W, D = 200, 172
SHORE = 40                          # first land row; z < SHORE is the harbour (never touched)
FOOTPRINT = (W, D)
MARKER = (-3, 0, 45)                # stand 3 blocks west of the town, on the line of Water Street
TEST_STRIP = (0, D + 3)
TARGET_BLOCKS = 85000
STEPS = [
    ("rocks", "Rock and shore", "Cliff headland, the islet, rocky points, rocks awash, rock faces, the beach"),
    ("lanes", "Lanes", "Water Street and the lanes winding up the hill"),
    ("wharves", "Wharves and piers", "Government wharf, the co-op float, marina walkways, finger piers, mooring posts"),
    ("stages", "Stages and walkways", "Fishing stages on stilts, crooked walkways, the islet stage, flakes, the slipway"),
    ("quay", "Fish plant and harbourmaster", "The fish plant on the wharf, the harbourmaster's office, the boathouse"),
    ("pub", "The Gaff Topsail", "The pub on its deck out over the water"),
    ("waterst", "Water Street", "Coady's store, Mary Ellen's, the B&B, the merchant's house"),
    ("lower", "Lower houses", "Houses on the lower slopes"),
    ("upper", "Upper houses", "Houses up the hill"),
    ("church", "Church and school", "St. Brendan's and its graveyard, the school, root cellars"),
    ("light", "Lighthouse point", "Lighthouse, keeper's house, oil house, fog light on the rocks"),
    ("wild", "Spruce, rock and scrub", "Spruce stands, birches, boulders, barrens, berries, lupins"),
    ("life", "Boats, lamps and life", "Longliners and dories, lamp posts, cats, fishermen"),
]
KEEP_ZONES = [
    dict(box=(0, 0, W - 1, SHORE - 1), what="water", surface=-2, depth=5, build_ok=True,
         note="harbour: your water goes here, never cleared or filled"),
]
LEVELS = [("Light", 36), ("Hilltop", 17), ("Upper", 12), ("Middle", 8), ("Shore", 3), ("Ground", 0), ("Harbour", -2)]
STEPS_HEADLINE = "Fourteen steps, rock to rooftops"

R = random.Random(709)
N1, N2, N3 = terrain.value_noise(11, 34), terrain.value_noise(12, 13), terrain.value_noise(13, 21)


# ====================================================================== the hill
def base_h(x, z):
    d = z - SHORE
    rise = 15.5 * (1 - math.exp(-d / 46))
    head = 11 * math.exp(-((x - 186) ** 2 / 420 + (z - 52) ** 2 / 300))          # headland
    dip = -3 * math.exp(-((x - 16) ** 2 / 520 + (z - 46) ** 2 / 160))            # low beach corner
    knoll = 4 * math.exp(-((x - 150) ** 2 / 240 + (z - 151) ** 2 / 240))        # lookout knoll
    n = (N1(x, z) - 0.5) * 6 + (N2(x, z) - 0.5) * 2.2
    taper = min(1.0, (x + 1) / 16, (W - x) / 16, (D - z) / 13)
    return max(0.0, (rise + head + dip + knoll + n * min(1.0, d / 10)) * max(0.0, taper))


H0 = {(x, z): base_h(x, z) for x in range(W) for z in range(SHORE, D)}
FIXED = {}                          # (x, z) -> pad height
CLAIMS = set()                      # land cells taken by lots / specials
PLACED = []                         # (kind, info) in placement order


def pad_level(rect):
    x1, z1, x2, z2 = rect
    vals = sorted(H0[(x, z)] for x in range(x1, x2 + 1) for z in range(z1, z2 + 1) if (x, z) in H0)
    return int(round(vals[len(vals) // 2])) if vals else 0


def fix(rect, g):
    x1, z1, x2, z2 = rect
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            if (x, z) in H0:
                FIXED[(x, z)] = g


def claim(rect):
    x1, z1, x2, z2 = rect
    CLAIMS.update((x, z) for x in range(x1, x2 + 1) for z in range(z1, z2 + 1))


def free(rect, blocked):
    x1, z1, x2, z2 = rect
    if x1 < 1 or z1 < SHORE + 2 or x2 > W - 2 or z2 > D - 2:
        return False
    return not any((x, z) in blocked for x in range(x1, x2 + 1) for z in range(z1, z2 + 1))


def expand(rect, l, t, r, b):
    x1, z1, x2, z2 = rect
    return (x1 - l, z1 - t, x2 + r, z2 + b)


# ---------------------------------------------------------------- lanes
LANE_POINTS = {
    "water_st": ([(0, 45), (18, 44), (36, 49), (58, 46), (80, 44), (100, 45), (120, 47), (140, 46), (158, 49),
                  (170, 52), (180, 44), (186, 43)], 3),
    "a": ([(24, 45), (22, 62), (30, 80), (20, 98), (30, 116), (24, 136), (30, 158)], 2),
    "b": ([(68, 46), (64, 66), (76, 86), (68, 104), (80, 124), (97, 139)], 2),
    "c": ([(120, 47), (126, 68), (114, 88), (124, 108), (118, 128), (130, 146)], 2),
    "d": ([(152, 48), (150, 70), (160, 90), (150, 112), (156, 132), (150, 148)], 2),
    "x1": ([(30, 80), (52, 77), (76, 86), (100, 84), (126, 68)], 2),
    "x3": ([(124, 108), (140, 100), (160, 90)], 2),
    "x4": ([(30, 116), (52, 127), (80, 124)], 2),
    "x6": ([(118, 128), (138, 136), (156, 132)], 2),
}
LANE_LINES = {k: terrain.smooth_line(pts) for k, (pts, _) in LANE_POINTS.items()}
LANES = set()
for k, (pts, w) in LANE_POINTS.items():
    LANES |= {c for c in terrain.widen(LANE_LINES[k], w) if (c in H0)}
LANE_BLOCK = terrain.widen(LANES, 3)            # houses keep a block clear of every lane

# ---------------------------------------------------------------- hand-placed buildings
SPECIALS = {}


def special(key, walls, front=4, sides=2, back=2, **extra):
    """Reserve a north-facing building's walls rect: pad around it, claim one block more."""
    pad = expand(walls, sides, front, sides, back)
    g = extra.pop("g", None)
    g = pad_level(pad) if g is None else g
    fix(pad, g)
    claim(expand(pad, 1, 1, 1, 1))
    SPECIALS[key] = dict(walls=walls, pad=pad, g=g, claim=expand(pad, 1, 1, 1, 1), **extra)
    return SPECIALS[key]


special("store", (84, 52, 105, 64), title="Coady's store", desc="General store and post office: shelves of everything, "
        "the counter, the post office lectern. A flat upstairs.")
special("chipper", (112, 53, 129, 64), title="Mary Ellen's", desc="Fish and chips: a kitchen line of smokers and fryers, "
        "tables with candles, striped awnings.")
special("bnb", (136, 55, 157, 68), title="Harbour View B&B", desc="Three-storey sky-blue saltbox: parlour, breakfast "
        "room, six guest rooms upstairs.")
special("merchant", (40, 55, 59, 67), title="Merchant's house", desc="The old merchant's house, white with black trim, "
        "three storeys, the grandest house on the harbour.")
special("school", (40, 132, 63, 142), front=3, back=8, title="School", desc="Two-storey schoolhouse with a bell cupola, "
        "two classrooms, swings and a sandbox out back.")
special("church", (90, 146, 104, 167), front=7, back=1, title="St. Brendan's", desc="White clapboard church at the top "
        "of the hill: stained glass, a bell tower and spire, pews, the altar.")
special("graveyard", (111, 148, 126, 166), front=1, back=1, sides=1, title="Graveyard", desc="Old stones in the grass "
        "behind a birch fence, looking out over the harbour.", pill=False)
special("light", (180, 43, 192, 56), front=1, back=1, sides=1, title="Lighthouse",
        desc="Red-and-white lighthouse on the cliff top: ladder to the gallery and the lamp room.")
special("oilhouse", (172, 62, 176, 66), front=2, back=1, sides=1, title="Oil house", pill=False, label=False,
        desc="Stone oil house for the lamp.")
special("lookout", (146, 148, 154, 156), front=1, back=1, sides=1, title="Lookout",
        desc="The gazebo on the knoll: benches, the flag, the whole cove below.")
for i, (x, z) in enumerate(((10, 104), (70, 114), (172, 112), (79, 155))):
    special(f"cellar{i}", (x - 2, z, x + 2, z + 6), front=1, back=1, sides=1, title="Root cellar", pill=False, label=False,
            desc="Sod-roofed root cellar: potatoes, turnips, carrots in barrels." if i != 1 else
            "Old Tobin's root cellar. Not all the barrels hold turnips.")
SPECIALS["cellar1"]["stash"] = True

# shore landings stay at sea level: the beach, the wharf head, the stage walkways, the pub deck
for rect in ((0, 40, 34, 45), (70, 40, 118, 42), (5, 40, 9, 42), (16, 40, 20, 42), (46, 40, 50, 42), (134, 40, 138, 42),
             (150, 40, 168, 42), (36, 40, 40, 43), (120, 40, 128, 42)):
    fix(rect, 0)

# ---------------------------------------------------------------- houses along the lanes
NAMES = ["Keough", "Doyle", "Pittman", "Hynes", "Murphy", "Penney", "Power", "Walsh", "Aylward", "Kelly", "Brennan",
         "Tobin", "Squibb", "Mercer", "Brushett", "Dalton", "Hiscock", "Snook", "Parsons", "Rideout", "Strickland",
         "Hollett", "Noseworthy", "Pardy", "Pike", "Quinlan", "Ryan", "Tilley", "Whelan", "Bartlett", "Abbott", "Gosse",
         "Fudge", "Kearley", "Mullowney", "Sheppard", "Vokey", "Jeans"]
COLOURS = [("red_concrete", "red"), ("yellow_concrete", "mustard"), ("blue_concrete", "blue"), ("green_concrete", "green"),
           ("purple_concrete", "purple"), ("orange_concrete", "orange"), ("light_blue_concrete", "sky-blue"),
           ("cyan_concrete", "teal"), ("pink_concrete", "pink"), ("lime_concrete", "lime"), ("magenta_concrete", "magenta"),
           ("white_concrete", "white"), ("red_concrete", "barn-red"), ("yellow_concrete", "butter-yellow")]
FLAVOUR = ["Nets drying on the fence, a dory turned over out back.", "The kettle's always on; the door's never locked.",
           "Kitchen parties on Saturdays.", "Grandmother's quilts on every bed.", "Woodpile taller than the shed.",
           "Charts of the bay on the parlour wall.", "The best potato garden on the hill.",
           "Built by hand in 1932, added to ever since.", "Lupins to the windowsills in July.",
           "A boat half-built in the yard for six years.", "The cove's accordion player lives here.",
           "Hens, a clothesline and a view of the narrows.", "Three generations under one roof.",
           "Mussel shells along the path.", "Painted a new colour every spring."]


def cardinal(dx, dz):
    if abs(dx) > abs(dz):
        return "east" if dx > 0 else "west"
    return "south" if dz > 0 else "north"


def house_spec(i, r):
    style = r.choices(["saltbox", "gable", "biscuit"], [0.36, 0.38, 0.26])[0]
    wall, colour = COLOURS[i % len(COLOURS)]
    storeys = 2 if r.random() < 0.82 else (3 if style != "saltbox" else 2)
    w, d = r.randint(11, 15), r.randint(9, 12)
    if storeys == 3:
        w, d = max(w, 13), max(d, 11)
    return dict(style=style, wall=wall, colour=colour, w=w, d=d, storeys=storeys, h=5,
                roof=r.choice(["deepslate", "dark_oak", "spruce", "brick"] if style != "biscuit" else ["dark_oak", "brick", "deepslate"]),
                cross=style == "gable" and r.random() < 0.55, chimney=r.choice(["bricks", "bricks", "cobblestone", "stone_bricks"]),
                veranda=0 if style == "biscuit" or r.random() < 0.35 else 3,
                trim="black_concrete" if wall == "white_concrete" else "white_concrete",
                rug=r.choice(["red", "blue", "green", "brown", "gray", "orange"]))


HOUSES = []
blocked = set(CLAIMS) | LANE_BLOCK
order = ["water_st", "a", "b", "c", "d", "x1", "x3", "x4", "x6"]
hr = random.Random(4)
for lane in order:
    line = LANE_LINES[lane]
    i = 8
    while i < len(line) - 6 and len(HOUSES) < 34:
        (ax, az), (bx, bz) = line[i - 4], line[i + 4]
        tx, tz = bx - ax, bz - az
        n = math.hypot(tx, tz) or 1
        nx, nz = -tz / n, tx / n
        px, pz = line[i]
        sides = [1, -1]
        hr.shuffle(sides)
        if lane == "water_st":
            sides = [1 if nz > 0 else -1]          # only the uphill side of Water Street
        placed = False
        tries = [(side, shrink, extra, lat) for side in sides for shrink in (0, 1) for extra in (0, 2)
                 for lat in (0, 3, -3)]
        for (side, shrink, extra, lat) in tries:
            spec = house_spec(len(HOUSES), random.Random(len(HOUSES) * 101 + 7))
            if shrink:
                spec["w"], spec["d"] = 11, 9
                spec["storeys"] = min(spec["storeys"], 2)
            ox, oz = -side * nx, -side * nz           # from the house toward the lane
            face = cardinal(ox, oz)
            turns = FACINGS.index(face)
            cw, cd = lot_size(spec)
            rw, rd = (cw, cd) if turns % 2 == 0 else (cd, cw)
            dist = cd / 2 + 3.5 + extra
            cx, cz = px - ox * dist + (-oz) * lat, pz - oz * dist + ox * lat
            X, Z = int(round(cx - rw / 2)), int(round(cz - rd / 2))
            rect = (X, Z, X + rw - 1, Z + rd - 1)
            if not free(rect, blocked):
                continue
            fr = lot_frames(spec)
            T = stamp_transform(fr["claim"], X, Z, turns)
            pad = rect_through(T, fr["pad"])
            g = pad_level(pad)
            fix(pad, g)
            claim(rect)
            blocked |= {(x, z) for x in range(rect[0], rect[2] + 1) for z in range(rect[1], rect[3] + 1)}
            name = NAMES[len(HOUSES) % len(NAMES)]
            spec.update(name=name, X=X, Z=Z, turns=turns, g=g, rect=rect, lane=lane, face=face,
                        flavour=FLAVOUR[len(HOUSES) % len(FLAVOUR)])
            HOUSES.append(spec)
            placed = True
            break
        i += hr.randint(9, 14) if placed else 2

# ---------------------------------------------------------------- infill: houses dotted up the hill, each with a footpath
LANE_LIST = sorted(LANES)


def nearest_lane(x, z):
    return min(LANE_LIST, key=lambda c: (c[0] - x) ** 2 + (c[1] - z) ** 2)


FOOTPATHS = []
ir = random.Random(23)
cands = [(x + ir.randint(-2, 2), z + ir.randint(-2, 2)) for z in range(SHORE + 14, D - 8, 7) for x in range(6, W - 6, 7)]
ir.shuffle(cands)
for (px, pz) in cands:
    if len(HOUSES) >= 32:
        break
    if (px, pz) in blocked:
        continue
    spec = house_spec(len(HOUSES), random.Random(len(HOUSES) * 101 + 7))
    lx, lz = nearest_lane(px, pz)
    if ir.random() < 0.6:
        face = "north"                                   # look down at the harbour
    else:
        face = cardinal(lx - px, lz - pz)                # or turn toward the lane
    turns = FACINGS.index(face)
    for shrink in (0, 1):
        if shrink:
            spec["w"], spec["d"], spec["storeys"] = 11, 9, min(spec["storeys"], 2)
        cw, cd = lot_size(spec)
        rw, rd = (cw, cd) if turns % 2 == 0 else (cd, cw)
        X, Z = px - rw // 2, pz - rd // 2
        rect = (X, Z, X + rw - 1, Z + rd - 1)
        if free(rect, blocked):
            break
    else:
        continue
    fr = lot_frames(spec)
    T = stamp_transform(fr["claim"], X, Z, turns)
    pad = rect_through(T, fr["pad"])
    g = pad_level(pad)
    fix(pad, g)
    claim(rect)
    blocked |= {(x, z) for x in range(rect[0], rect[2] + 1) for z in range(rect[1], rect[3] + 1)}
    name = NAMES[len(HOUSES) % len(NAMES)]
    front = T(fr["walls"][0] + spec["w"] // 2, 0, -5)
    spec.update(name=name, X=X, Z=Z, turns=turns, g=g, rect=rect, lane="footpath", face=face,
                flavour=FLAVOUR[len(HOUSES) % len(FLAVOUR)])
    HOUSES.append(spec)
    FOOTPATHS.append(terrain.smooth_line([(front[0], front[2]), nearest_lane(front[0], front[2])]))

# ---------------------------------------------------------------- settle the ground
H = {k: (FIXED[k] if k in FIXED else int(round(v))) for k, v in H0.items()}
terrain.relax(H, FIXED, edge=lambda x, z: None if z < SHORE else 0)
HEIGHTMAP = H


def gh(x, z):
    """Feet level of the ground at (x, z) (0 off the land)."""
    return H.get((x, z), 0)


# ====================================================================== areas
AREAS = [
    dict(key="stages", title="Fishing stages", box=(0, 0, 50, SHORE - 1),
         desc="Four stages on stilts, crooked walkways out to the rock islet and its stage, dories tied up."),
    dict(key="point", title="Rocky point", box=(51, 0, 67, SHORE - 1),
         desc="A low rocky point with a navigation light, and the slipway."),
    dict(key="wharf", title="Government wharf", box=(68, 0, 119, SHORE - 1),
         desc="The public wharf on log piles with the fish plant, the co-op float, the harbourmaster's office, a crane."),
    dict(key="marina", title="Marina", box=(120, 0, 149, SHORE - 1),
         desc="The boathouse and a crooked walkway with finger piers; boats tied up all along."),
    dict(key="pub", title="The Gaff Topsail", box=(150, 0, 168, SHORE - 1),
         desc="The pub on its own deck over the water: long bar, tables, the publican's flat upstairs, a terrace."),
    dict(key="headland", title="Headland", box=(169, 0, W - 1, SHORE - 1),
         desc="Cliffs of grey rock dropping into the harbour, a fog light on the outermost rocks."),
]
for k, s in SPECIALS.items():
    AREAS.append(dict(key=k, title=s["title"], box=s["claim"], desc=s["desc"],
                      **{f: s[f] for f in ("pill", "label") if f in s}))
for h in HOUSES:
    AREAS.append(dict(key=h["name"].lower(), title=f"The {h['name']} house", box=h["rect"], pill=False, label=False,
                      desc=f"{h['colour'].capitalize()} {('cross-gable' if h['cross'] else h['style']).replace('biscuit', 'biscuit box')}, "
                           f"{h['storeys']} storeys, facing {h['face']}. {h['flavour']}"))
AREAS.append(dict(key="hillside", title="Hillside", box=(0, SHORE, W - 1, D - 1), rest=True, pill=False, label=False,
                  desc="Lanes, rock, spruce and scrub between the lots."))

SECRETS = [
    dict(title="Old Tobin's cellar", pos=(SPECIALS["cellar1"]["walls"][0] + 1, SPECIALS["cellar1"]["g"],
                                         SPECIALS["cellar1"]["walls"][1] + 3),
         desc="One root cellar on the hill holds more than turnips: barrels, a still and a locked chest."),
    dict(title="The islet cache", pos=(32, 1, 13), desc="Behind the islet stage, a chest hidden in the rocks."),
    dict(title="The belfry chest", pos=(96, SPECIALS["church"]["g"] + 13, 142),
         desc="Climb the ladder in the church tower: a chest sits under the bell."),
]
STATS = [(str(len(HOUSES)), "houses"), (str(len(HOUSES) + 13), "buildings")]


# ====================================================================== building
def stone_choice(r):
    return r.choice(["stone", "stone", "andesite", "andesite", "cobblestone", "tuff", "granite", "mossy_cobblestone"])


def blob(cx, cz, rx, rz, seed, rough=0.35):
    r = terrain.value_noise(seed, 5)
    out = []
    for x in range(int(cx - rx - 2), int(cx + rx + 3)):
        for z in range(int(cz - rz - 2), int(cz + rz + 3)):
            d = ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2
            if d < 1 + (r(x, z) - 0.5) * rough * 2:
                out.append((x, z, d))
    return out


def build(m):
    r = random.Random(17)
    water = lambda x, z: 0 <= x < W and 0 <= z < SHORE        # noqa: E731
    taken_water = set()                                       # water cells used by structures

    def reserve(x1, z1, x2, z2):
        taken_water.update((x, z) for x in range(x1, x2 + 1) for z in range(z1, z2 + 1))

    # structures in the water, reserved first so rocks keep clear of them
    STAGES = [(3, 24, 9, 11, "red_terracotta", "spruce_planks"), (15, 17, 10, 11, "spruce_planks", "dark_oak_planks"),
              (40, 22, 9, 12, "white_concrete", "spruce_planks"), (26, 2, 9, 9, "yellow_terracotta", "spruce_planks")]
    for (x, z, w, d, *_ ) in STAGES:
        reserve(x - 1, z - 1, x + w, z + d)
    reserve(70, 8, 120, 39)          # wharf, arm, float
    reserve(120, 2, 152, 39)         # boathouse + marina
    reserve(150, 20, 168, 39)        # pub deck
    reserve(34, 26, 40, 39)          # slipway

    # ------------------------------------------------------------ rock and shore
    with m.step("rocks"):
        # cliff headland: rock rising from the outer rocks up to the clifftop at the shore
        tops = {}
        for (x, z, d) in blob(186, 30, 17, 27, seed=5):
            if not water(x, z) or (x, z) in taken_water:
                continue
            land = gh(min(max(x, 0), W - 1), SHORE) - 1
            k = max(0.0, min(1.0, (z - 8) / (SHORE - 8)))
            t = round(-1 + (land + 1) * (k ** 1.4) * (1.1 - 0.5 * d) + (N2(x, z) - 0.5) * 3)
            tops[(x, z)] = max(-1, min(land, t))
        rock_mass(m, tops, seed=5)
        # the rock islet
        tops = {(x, z): max(-1, round(2 - 3 * d + (N2(x, z) - 0.5) * 2)) for (x, z, d) in blob(31, 10, 7, 6, seed=6)
                if water(x, z)}
        for (x, z) in list(tops):
            if 26 <= x <= 34 and 2 <= z <= 10:
                tops[(x, z)] = min(tops[(x, z)], -2)              # under the islet stage: the stage stands on it
        rock_mass(m, tops, seed=6)
        m.put(33, 1, 13, "chest", facing="north")                  # the islet cache
        # low rocky point
        tops = {(x, z): max(-1, round(1 - 2.5 * d + (N2(x, z) - 0.5) * 2)) for (x, z, d) in blob(59, 34, 7, 9, seed=7)
                if water(x, z) and (x, z) not in taken_water}
        rock_mass(m, tops, seed=7)
        for y in range(1, 5):
            m.put(59, y, 30, "stone_brick_wall")
        m.put(59, 5, 30, "lantern")
        # rocks awash and shore rocks
        for k in range(26):
            cx, cz = r.randint(2, W - 3), r.randint(4, SHORE - 1)
            pts = [(x, z, d) for (x, z, d) in blob(cx, cz, r.uniform(1, 2.6), r.uniform(1, 2.2), seed=100 + k)
                   if water(x, z) and (x, z) not in taken_water]
            if len(pts) < 3 or any((x, z) in taken_water for (x, z, _) in pts):
                continue
            rock_mass(m, {(x, z): r.choice([-2, -1, -1, 0]) if d < 0.6 else -2 for (x, z, d) in pts}, seed=100 + k)
        for x in range(0, W):
            if r.random() < 0.3 and (x, SHORE - 1) not in taken_water:
                t = gh(x, SHORE) - 1
                rock_mass(m, {(x, SHORE - 1): t, **({(x, SHORE - 2): t - 1} if r.random() < 0.5 and (x, SHORE - 2) not in taken_water else {})},
                          seed=x)
        # the beach: gravel, sand and stones down at the water's edge
        for x in range(0, 35):
            for z in range(SHORE, SHORE + 6):
                if (x, z) not in LANES:
                    m.put(x, gh(x, z) - 1, z, r.choice(["gravel", "gravel", "andesite", "sand", "stone", "gravel"]))
        terrain.cliff_faces(m, H, seed=8)

    # ------------------------------------------------------------ lanes
    with m.step("lanes"):
        for k, (pts, w) in LANE_POINTS.items():
            cells = {c for c in terrain.widen(LANE_LINES[k], w) if c in H}
            if k == "water_st":
                terrain.surface(m, cells, H, "gravel", {"andesite": 0.2, "cobblestone": 0.15, "coarse_dirt": 0.08}, seed=1)
            else:
                terrain.surface(m, cells, H, "dirt_path", {"gravel": 0.25, "coarse_dirt": 0.2, "andesite": 0.05}, seed=sum(map(ord, k)))

    # ------------------------------------------------------------ wharves and piers
    with m.step("wharves"):
        wharf(m, 70, 22, 104, 39, sea_sides=("north", "west"))
        wharf(m, 104, 10, 118, 30, sea_sides=("north", "east", "west"))
        wharf(m, 90, 12, 103, 21, rim=None, sea_sides=("north", "west"))           # co-op float
        for y in range(0, 7):                                                     # crane on the arm
            m.put(116, y, 26, "spruce_log", axis="y")
        for x in range(110, 116):
            m.put(x, 6, 26, "spruce_log", axis="x")
        for y in (5, 4):
            m.put(110, y, 26, "iron_chain")
        for (x, z, n) in ((72, 24, 3), (86, 23, 2), (106, 28, 3), (112, 12, 2), (92, 14, 3)):
            pot_stack(m, x, z, 0, n=n, seed=x)
        # marina: a crooked main walkway with finger piers
        main = terrain.widen(terrain.smooth_line([(136, 39), (136, 30), (142, 22), (142, 4)]), 2)
        walkway(m, sorted(main, key=lambda c: -c[1]))
        for line in ([(135, 33), (127, 33)], [(135, 26), (129, 26)], [(143, 18), (151, 18)], [(143, 11), (150, 11)],
                     [(141, 7), (132, 7)]):
            walkway(m, terrain.widen(terrain.smooth_line(line), 2), every=3)
        for (x, z) in ((126, 34), (151, 17), (150, 10), (131, 6), (128, 25)):
            mooring_post(m, x, z)
        for k in range(10):
            x, z = r.randint(4, W - 30), r.randint(4, SHORE - 6)
            if all((x + dx, z + dz) not in taken_water for dx in (-1, 0, 1) for dz in (-1, 0, 1)) and m.empty(x, -2, z):
                mooring_post(m, x, z)

    # ------------------------------------------------------------ stages, walkways, flakes, slipway
    with m.step("stages"):
        for (x, z, w, d, wall, trim) in STAGES:
            stage(m, x, z, w, d, wall=wall, trim=trim)
        for line in ([(7, 35), (7, 39)], [(19, 28), (18, 33), (18, 39)], [(44, 34), (47, 37), (48, 39)],
                     [(16, 16), (22, 13), (28, 11)], [(40, 21), (36, 14), (35, 11)]):
            walkway(m, terrain.smooth_line(line), every=2)
        flake(m, 4, 41, 15, 44, 0, seed=4)
        flake(m, 20, 41, 30, 44, 0, seed=5)
        slipway(m, 35, 27, 41, y_top=0, width=5, boat_color="yellow_concrete")
        for (x, z) in ((12, 46), (27, 45)):
            dory(m, x, z, y=gh(x, z), along="x", color=r.choice(["red_concrete", "blue_concrete", "green_concrete"]))

    # ------------------------------------------------------------ fish plant, harbourmaster, boathouse
    with m.step("quay"):
        clapboard_house(m, 74, 29, 0, 27, 10, style="gable", wall="light_gray_concrete", trim="white_concrete",
                        roof="spruce", storeys=1, h=6, interior="plant", porch=False, chimney=None, every=4, seed=6)
        hm = clapboard_house(m, 107, 14, 0, 10, 9, style="gable", cross=True, wall="white_concrete", trim="red_concrete",
                             roof="brick", storeys=2, interior="office", seed=5)
        cupola(m, 110, max(range(15, 22), key=hm["H"]), hm["top"])
        flagpole(m, 117, 12, 0)
        boathouse(m, 120, 27, 9, 13, wall="red_terracotta")

    # ------------------------------------------------------------ the pub over the water
    with m.step("pub"):
        wharf(m, 150, 22, 168, 39, sea_sides=("north", "east", "west"))
        clapboard_house(m, 152, 28, 0, 15, 11, style="gable", cross=True, wall="green_concrete", storeys=2, h=5,
                        interior="pub", seed=7, porch=True, chimney="bricks")
        rm = interiors.Room(m, 151, 23, 167, 26, 0, (), 7, "spruce")
        for x in (153, 157, 163, 166):
            interiors.dining(rm, x, 24, along="x", top="white_candle")
        for x in (151, 167):
            lamp_post(m, x, 0, 23, height=2)
        awning(m, 154, 158, 27, 4, ("green_wool", "white_wool"))
        awning(m, 162, 166, 27, 4, ("green_wool", "white_wool"))

    # ------------------------------------------------------------ Water Street
    with m.step("waterst"):
        S = SPECIALS
        x1, z1, x2, z2 = S["store"]["walls"]
        clapboard_house(m, x1, z1, S["store"]["g"], x2 - x1 + 1, z2 - z1 + 1, style="gable", cross=True, wall="red_concrete",
                        storeys=2, h=5, interior="shop", seed=9, veranda=4)
        x1, z1, x2, z2 = S["chipper"]["walls"]
        g = S["chipper"]["g"]
        clapboard_house(m, x1, z1, g, x2 - x1 + 1, z2 - z1 + 1, style="biscuit", wall="yellow_concrete", roof="dark_oak",
                        storeys=2, h=5, interior="restaurant", seed=8)
        awning(m, x1 + 2, x1 + 6, z1 - 1, g + 4, ("blue_wool", "white_wool"))
        awning(m, x2 - 6, x2 - 2, z1 - 1, g + 4, ("blue_wool", "white_wool"))
        x1, z1, x2, z2 = S["bnb"]["walls"]
        clapboard_house(m, x1, z1, S["bnb"]["g"], x2 - x1 + 1, z2 - z1 + 1, style="saltbox", wall="light_blue_concrete",
                        storeys=3, h=5, interior="inn", seed=10, veranda=4)
        x1, z1, x2, z2 = S["merchant"]["walls"]
        clapboard_house(m, x1, z1, S["merchant"]["g"], x2 - x1 + 1, z2 - z1 + 1, style="biscuit", wall="white_concrete",
                        trim="black_concrete", roof="dark_oak", storeys=3, h=5, interior="house", seed=11, rug="blue")

    # ------------------------------------------------------------ houses
    for i, h in enumerate(HOUSES):
        with m.step("lower" if h["Z"] < 100 else "upper"):
            info = house_lot(m, h["X"], h["Z"], h["g"], h["turns"], h, seed=31 + i * 7)
            # path from the gate to the lane
            fx, _, fz = info["front"]
            dx, dz = DIRV[info["out"]]
            for k in range(8):
                c = (fx + dx * k, fz + dz * k)
                if c in LANES or c not in H:
                    break
                y = gh(*c) - 1
                cell = m.get(c[0], y, c[1])
                if cell is None or cell.key in ("grass_block", "dirt"):
                    m.put(c[0], y, c[1], "dirt_path")

        # footpaths from the hillside houses down to the nearest lane
        for fp in FOOTPATHS:
            cells = [c for c in fp if c in H and c not in LANES]
            terrain.surface(m, cells, H, "dirt_path", {"coarse_dirt": 0.3, "gravel": 0.1}, seed=len(cells),
                            keep=lambda x, z: (x, z) in CLAIMS and not any((x, z) == c for c in fp[:6]))

    # ------------------------------------------------------------ church, school, cellars
    with m.step("church"):
        S = SPECIALS
        x1, z1, x2, z2 = S["church"]["walls"]
        church(m, x1, z1, S["church"]["g"], w=x2 - x1 + 1, d=z2 - z1 + 1)
        m.put(96, S["church"]["g"] + 13, 142, "chest", facing="south")
        gx1, gz1, gx2, gz2 = S["graveyard"]["walls"]
        gg = S["graveyard"]["g"]
        fence_ring(m, gx1, gz1, gx2, gz2, y=gg, key="birch_fence", gates=[(gx1, (gz1 + gz2) // 2, "east")])
        graveyard(m, gx1, gz1, gx2, gz2, gg, seed=3)
        x1, z1, x2, z2 = S["school"]["walls"]
        g = S["school"]["g"]
        sc = clapboard_house(m, x1, z1, g, x2 - x1 + 1, z2 - z1 + 1, style="gable", cross=True, wall="white_concrete",
                             trim="red_concrete", roof="deepslate", storeys=2, h=5, interior="school", seed=21)
        zr = max(range(z1 + 1, z2), key=sc["H"])
        cupola(m, x1 + 6, zr, sc["top"], glass="iron_bars")
        m.put(x1 + 6, sc["top"] + 2, zr, "bell", hanging=True, facing="north")
        for x in (x1 + 1, x1 + 9):                                                   # swings
            for y in range(g, g + 4):
                m.put(x, y, z2 + 5, "spruce_fence")
        for x in range(x1 + 1, x1 + 10):
            m.put(x, g + 4, z2 + 5, "spruce_log", axis="x")
        for x in (x1 + 4, x1 + 6):
            m.put(x, g + 3, z2 + 5, "iron_chain")
            m.put(x, g + 2, z2 + 5, "iron_chain")
            m.put(x, g + 1, z2 + 5, "spruce_slab", half="top")
        for i in range(4):
            c = S[f"cellar{i}"]
            x1, z1, x2, z2 = c["walls"]
            root_cellar(m, (x1 + x2) // 2, z1, c["g"], depth=4, width=3, seed=i)
            if c.get("stash"):
                m.put(x1 + 1, c["g"], z1 + 3, "chest", facing="east")
                m.put(x2 - 1, c["g"] + 1, z1 + 3, "brewing_stand")

    # ------------------------------------------------------------ lighthouse point
    with m.step("light"):
        S = SPECIALS
        x1, z1, x2, z2 = S["light"]["walls"]
        lighthouse(m, (x1 + x2) // 2, (z1 + z2) // 2 + 1, S["light"]["g"], height=20, r=4)
        x1, z1, x2, z2 = S["oilhouse"]["walls"]
        clapboard_house(m, x1, z1, S["oilhouse"]["g"], 5, 5, style="gable", wall="stone_bricks", trim="stone_bricks",
                        roof="brick", storeys=1, h=3, interior=None, porch=False, chimney=None)
        for y in range(-1, 5):                                                     # fog light on the outer rocks
            for (x, z) in ((186, 9), (187, 9), (186, 10), (187, 10)):
                m.put(x, y, z, "white_concrete" if y % 3 else "red_concrete")
        m.put(186, 5, 9, "lantern")
        x1, z1, x2, z2 = S["lookout"]["walls"]
        g = S["lookout"]["g"]
        gazebo(m, (x1 + x2) // 2, (z1 + z2) // 2, g, r=3)
        flagpole(m, x2 - 1, z1, g)

    # ------------------------------------------------------------ spruce, rock and scrub
    with m.step("wild"):
        lanes = terrain.widen(LANES, 2)
        busy = lambda x, z: (x, z) in CLAIMS or (x, z) in lanes or (x, z) not in H     # noqa: E731
        trees = []
        for (x, z) in sorted(H):
            if busy(x, z) or z < SHORE + 4:
                continue
            edge = min(x, W - 1 - x, D - 1 - z)
            p = 0.012 + (0.05 if N3(x, z) > 0.6 else 0) + (0.04 if edge < 12 else 0) + (0.02 if z > 120 else 0)
            if r.random() < p and all(abs(x - a) + abs(z - b) > 4 for a, b in trees[-40:]):
                if any(busy(x + dx, z + dz) for dx in (-3, 0, 3) for dz in (-3, 0, 3)):
                    continue
                trees.append((x, z))
                if r.random() < 0.15:
                    oak_tree(m, x, gh(x, z), z, height=r.randint(5, 7), seed=x * 31 + z, log="birch_log",
                             leaves="birch_leaves", radius=2)
                else:
                    spruce_tree(m, x, gh(x, z), z, height=r.randint(6, 11), seed=x * 17 + z)
        for k in range(70):
            x, z = r.randint(2, W - 3), r.randint(SHORE + 2, D - 3)
            if not any(busy(x + dx, z + dz) for dx in (-2, 0, 2) for dz in (-2, 0, 2)):
                boulder(m, x, z, gh(x, z), size=r.choice([1, 1, 1, 2]), seed=500 + k)
        barrens = [c for c in H if not busy(*c) and N2(*c) > 0.74 and c[1] > SHORE + 3]
        terrain.surface(m, barrens, H, "stone", {"andesite": 0.3, "gravel": 0.15, "moss_block": 0.2, "coarse_dirt": 0.1}, seed=9)
        ground = [c for c in H if not busy(*c) and c[1] > SHORE + 1]
        terrain.scatter(m, ground, H, [("short_grass", 40), ("fern", 10), ("tall_grass", 6), ("sweet_berry_bush", 3),
                                       ("bush", 3), ("dandelion", 1), ("oxeye_daisy", 1)], 0.16, seed=10)
        lupins = [c for c in ground if N1(c[0] * 2.3, c[1] * 2.3) > 0.66]
        terrain.scatter(m, lupins, H, [("allium", 5), ("lilac", 2), ("blue_orchid", 1), ("cornflower", 1)], 0.55, seed=11)

    # ------------------------------------------------------------ boats, lamps, life
    with m.step("life"):
        longliner(m, 74, 15, hull="red_concrete")
        longliner(m, 152, 13, hull="blue_concrete", stripe="yellow_concrete")
        longliner(m, 2, 8, hull="green_concrete")
        for (x, z, col) in ((10, 21, "red_concrete"), (52, 22, "blue_concrete"), (128, 29, "yellow_concrete"),
                            (128, 21, "green_concrete"), (144, 14, "orange_concrete"), (133, 3, "red_concrete"),
                            (98, 9, "white_concrete"), (24, 30, "orange_concrete")):
            cells = [(x + i, z + j) for i in range(-1, 6) for j in (-1, 0, 1)]
            if all(m.empty(a, -2, b) and m.empty(a, -1, b) for a, b in cells):
                dory(m, x, z, y=-2, along="x", color=col)
        line = LANE_LINES["water_st"]
        for i in range(6, len(line), 13):
            x, z = line[i]
            for (a, b) in ((x, z - 3), (x, z + 3)):
                if (a, b) in H and (a, b) not in LANES and (a, b) not in CLAIMS and m.empty(a, gh(a, b), b) \
                        and m.empty(a, gh(a, b) + 1, b):
                    lamp_post(m, a, gh(a, b), b, height=3)
                    break
        for (x, z) in ((70, 22), (104, 10), (118, 10), (104, 22)):
            lamp_post(m, x, 0, z, height=2)
        for lane in ("a", "b", "c", "d"):
            l = LANE_LINES[lane]
            for i in range(10, len(l), 18):
                x, z = l[i]
                a, b = x + 2, z
                if (a, b) in H and (a, b) not in LANES and (a, b) not in CLAIMS and m.empty(a, gh(a, b), b):
                    lamp_post(m, a, gh(a, b), b, height=3)
        m.entity(33, gh(33, 47), 47, "cat", name="Skipper")
        m.entity(100, 0, 26, "villager_v2", name="Ned Keough")
        m.entity(110, 1, 17, "villager_v2", name="Harbourmaster Fitzgerald")
        m.entity(160, 0, 25, "cat", name="Duff")
        h = HOUSES[len(HOUSES) // 2]
        m.entity(h["rect"][0] + 1, h["g"], h["rect"][1] + 1, "cat", name="Bride's Tom")
