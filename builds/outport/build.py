"""Gannet Cove: a Newfoundland outport climbing a harbour shore. Painted clapboard
saltbox, gable and biscuit-box houses in jellybean colours on three terraces, a working
waterfront of fishing stages, a government wharf and finger piers standing on piles in
the (untouched) harbour strip, Water Street with a pub, a fish-and-chips shop, the general
store and post office, a B&B and the old merchant's house, the harbourmaster's office and
the fisheries co-op on the quay, a lighthouse on the point, a white church on the hill, and
at the top the school, the parish hall and a lookout gazebo over the whole cove."""
from lib import *

TITLE = "Gannet Cove"
SUBTITLE = "Newfoundland outport · Minecraft Bedrock build book · no water placed"
SUBJECT = "Cove"
FOOTPRINT = (172, 152)
MARKER = (-3, 0, 36)            # stand 3 blocks west of the town, on the line of Water Street
TEST_STRIP = (0, 155)           # test_blocks lays its strip behind the town
TARGET_BLOCKS = 85000
STEPS = [
    ("walls", "Seawall, terraces and steps", "Quay seawall, retaining walls, stone stairs, root cellars"),
    ("streets", "Streets and paths", "Quay paving, Water Street, Middle Street, Church Road, lanes"),
    ("wharf", "Wharf and piers", "Government wharf, finger piers, harbourmaster's float, breakwater"),
    ("stages", "Stages and net lofts", "Fishing stages on stilts, flakes, net lofts, the slipway"),
    ("harbourmaster", "Harbourmaster's office", "Two storeys, lookout cupola, flagpole"),
    ("fishplant", "Fisheries co-op", "The fish plant on the quay"),
    ("waterst_a", "Water Street west", "The pub, the fish-and-chips shop, the general store"),
    ("waterst_b", "Water Street east", "The B&B and the merchant's house"),
    ("point", "Lighthouse point", "Rocky point, lighthouse, keeper's cottage"),
    ("middle", "Middle Street houses", "Nine houses on the first terrace"),
    ("churchrd", "Church Road houses", "Seven houses on the top terrace"),
    ("church", "The church", "St. Brendan's, the bell tower and the graveyard"),
    ("hill", "Hill Road", "The school, the parish hall, four more houses and the lookout gazebo"),
    ("gardens", "Gardens and trees", "Picket fences, kitchen gardens, clotheslines, woodpiles, spruce, lupins"),
    ("life", "Lamps, boats and life", "Street lamps, dories, flags, cats and the harbourmaster"),
]
# terraces (feet level): Water Street and the quay stay at grade 0
GRADES = [dict(box=(0, 58, 171, 88), y=3, name="Middle Street"), dict(box=(0, 89, 171, 123), y=6, name="Church Road"),
          dict(box=(0, 124, 171, 151), y=9, name="Hill Road")]
KEEP_ZONES = [
    dict(box=(0, 0, 171, 19), what="water", surface=-2, depth=5, build_ok=True,
         note="harbour strip: your water goes here, never cleared or filled"),
]
LEVELS = [("Lamp", 24), ("Hill", 12), ("Church", 9), ("Middle", 6), ("Water St", 3), ("Ground", 0), ("Harbour", -2)]

LOTS_B = [(i * 19, i * 19 + 18) for i in range(8)] + [(152, 171)]
LOTS_C = [(45, 62), (63, 80), (81, 98), (99, 116), (117, 134), (135, 152), (153, 171)]
LOTS_D = [(81, 98), (99, 116), (117, 134), (135, 152)]

HOUSES_B = [  # Middle Street (terrace +3)
    dict(key="keough", title="The Keough house", style="saltbox", wall="red_concrete", roof="deepslate",
         desc="Red saltbox. Ned Keough mends nets in the back room; his dory sits on blocks out back."),
    dict(key="doyle", title="Doyle's", style="gable", cross=True, wall="yellow_concrete", roof="dark_oak",
         desc="Mustard cross-gable. Bernadette Doyle bakes for the whole cove: cake on the table, bread in the smoker."),
    dict(key="pittman", title="The Pittman place", style="biscuit", wall="blue_concrete", roof="dark_oak",
         desc="Blue biscuit box. Skipper Pittman, retired, keeps charts on the parlour table."),
    dict(key="aunt_bride", title="Aunt Bride's", style="saltbox", wall="green_concrete", roof="spruce",
         desc="Green saltbox. Knitter, cat keeper, owner of the best root cellar on the hill."),
    dict(key="coady", title="The Coady house", style="gable", cross=True, wall="purple_concrete", roof="deepslate",
         desc="Purple cross-gable. Kitchen parties on Saturdays; the jukebox is never off."),
    dict(key="fitzgerald", title="Fitzgerald's", style="biscuit", wall="orange_concrete", roof="dark_oak",
         desc="Orange biscuit box. The harbourmaster's family home."),
    dict(key="hynes", title="The Hynes house", style="gable", cross=True, wall="light_blue_concrete", roof="spruce",
         desc="Sky-blue cross-gable. The schoolteacher's house, bookshelves in every room."),
    dict(key="murphy", title="Murphy's", style="gable", wall="red_concrete", roof="deepslate", w=15,
         desc="Big red gable house. Three generations of fishermen; woodpile out back."),
    dict(key="penney", title="The Penney house", style="biscuit", wall="yellow_concrete", roof="brick",
         desc="Yellow biscuit box. Built by the shopkeeper's grandfather."),
]
HOUSES_C = [  # Church Road (terrace +6)
    dict(key="rectory", title="The Rectory", style="saltbox", wall="white_concrete", trim="light_gray_concrete",
         roof="deepslate", desc="White saltbox beside the church; the priest's study faces the harbour."),
    dict(key="power", title="Power's", style="gable", wall="cyan_concrete", roof="spruce",
         desc="Teal gable house. Mick Power builds boats; there's always one in his yard."),
    dict(key="walsh", title="The Walsh house", style="gable", cross=True, wall="pink_concrete", roof="dark_oak",
         desc="Pink cross-gable with the cove's best flower garden."),
    dict(key="aylward", title="Aylward's", style="biscuit", wall="green_concrete", roof="dark_oak",
         desc="Green biscuit box. Lupins to the eaves in July."),
    dict(key="kelly", title="The Kelly house", style="saltbox", wall="blue_concrete", roof="deepslate", storeys=3,
         desc="Tall blue saltbox, three storeys, the widest view of the cove."),
    dict(key="brennan", title="Brennan's", style="gable", cross=True, wall="red_concrete", roof="brick",
         desc="Red cross-gable. The Brennans keep hens and the cove's only goat (not included)."),
    dict(key="tobin", title="Old Tobin's", style="gable", wall="yellow_concrete", roof="spruce",
         desc="Yellow gable at the top of the hill. Old Tobin watches every boat come in."),
]

HOUSES_D = [  # Hill Road (terrace +9)
    dict(key="doctor", title="The Doctor's house", style="biscuit", wall="white_concrete", trim="black_concrete",
         roof="dark_oak", storeys=3, desc="Three-storey white biscuit box. Surgery on the ground floor, the family above."),
    dict(key="squibb", title="Squibb's", style="saltbox", wall="lime_concrete", roof="spruce",
         desc="Lime-green saltbox. The Squibbs run the bakery van; the smoker is always going."),
    dict(key="mercer", title="The Mercer house", style="gable", cross=True, wall="magenta_concrete", roof="deepslate",
         desc="Magenta cross-gable. Painted the brightest colour on the hill, on purpose."),
    dict(key="brushett", title="Brushett's", style="gable", wall="orange_concrete", roof="brick",
         desc="Orange gable house. Mrs Brushett keeps the parish hall keys."),
]

AREAS = [
    dict(key="stages", title="Fishing stages", box=(0, 0, 57, 19),
         desc="Three fishing stages on stilts over the water, with lobster pots on the decks."),
    dict(key="wharf", title="Government wharf", box=(58, 0, 113, 19),
         desc="The big public wharf on log piles, bollards, a crane and the harbourmaster's float."),
    dict(key="slips", title="Finger piers", box=(114, 0, 145, 19),
         desc="Two walkways with finger piers and a few dories tied up."),
    dict(key="breakwater", title="Breakwater", box=(146, 0, 171, 19),
         desc="A rough rock breakwater curling out from the point."),
    dict(key="netlofts", title="Net lofts", box=(0, 20, 57, 33),
         desc="Net lofts, fish flakes and the slipway with a boat on its cradle."),
    dict(key="harbourmaster", title="Harbourmaster", box=(58, 20, 85, 33),
         desc="Harbourmaster's office: ground-floor counter, upstairs charts, a lookout cupola and the flag."),
    dict(key="fishplant", title="Fisheries co-op", box=(86, 20, 145, 33),
         desc="Gannet Cove Fisheries Co-op: splitting tables, salt barrels, ice and the smoker line."),
    dict(key="waterst", title="Water Street", box=(0, 34, 145, 38), pill=False,
         desc="The harbour road: gravel and stone, lamp posts along the quay side."),
    dict(key="pub", title="The Gaff Topsail", box=(0, 39, 29, 54),
         desc="The pub: long bar of barrels, tables with candles, a jukebox, the publican's flat upstairs."),
    dict(key="chipper", title="Mary Ellen's", box=(30, 39, 57, 54),
         desc="Fish and chips: kitchen line of smokers and fryers, tables, a flat upstairs."),
    dict(key="store", title="Coady's store", box=(58, 39, 85, 54),
         desc="General store and post office: shelves of everything, a counter, the post office lectern."),
    dict(key="inn", title="Harbour View B&B", box=(86, 39, 115, 54),
         desc="Three-storey saltbox B&B: parlour and breakfast room, six guest rooms upstairs."),
    dict(key="merchant", title="Merchant's house", box=(116, 39, 145, 54),
         desc="The old merchant's house, three storeys, the grandest house on the harbour."),
    dict(key="point", title="Lighthouse point", box=(146, 20, 171, 57),
         desc="Rocky point with the red-and-white lighthouse and the keeper's cottage."),
    dict(key="steps", title="The steps", box=(0, 55, 145, 57), pill=False,
         desc="Stone stairs up to Middle Street, benches and flower beds under the wall."),
    dict(key="middle_st", title="Middle Street", box=(0, 58, 171, 62), pill=False,
         desc="Retaining wall and the gravel street along the first terrace."),
    *[dict(key=h["key"], title=h["title"], box=(a, 63, b, 84), desc=h["desc"], pill=False, label=False)
      for h, (a, b) in zip(HOUSES_B, LOTS_B)],
    dict(key="upper_steps", title="Upper steps", box=(0, 85, 171, 88), pill=False,
         desc="Back gardens' edge, stairs up to Church Road and the root cellars in the wall."),
    dict(key="church_rd", title="Church Road", box=(0, 89, 171, 93), pill=False,
         desc="Retaining wall and the cobbled road along the top terrace."),
    dict(key="church", title="St. Brendan's", box=(0, 94, 44, 123),
         desc="White clapboard church with stained glass, a bell tower and spire, and the graveyard."),
    *[dict(key=h["key"], title=h["title"], box=(a, 94, b, 123), desc=h["desc"], pill=False, label=False)
      for h, (a, b) in zip(HOUSES_C, LOTS_C)],
    dict(key="hill_rd", title="Hill Road", box=(0, 124, 171, 128), pill=False,
         desc="Retaining wall and the gravel road along the top terrace."),
    dict(key="school", title="School", box=(0, 129, 40, 151),
         desc="Two-storey schoolhouse with a bell cupola, two classrooms and a playground."),
    dict(key="hall", title="Parish hall", box=(41, 129, 80, 151),
         desc="The hall: a stage, rows of chairs, the kitchen corner. Dances, bingo, wakes."),
    *[dict(key=h["key"], title=h["title"], box=(a, 129, b, 151), desc=h["desc"], pill=False, label=False)
      for h, (a, b) in zip(HOUSES_D, LOTS_D)],
    dict(key="lookout", title="Lookout", box=(153, 129, 171, 151),
         desc="The gazebo at the top of the hill, benches and the flag. The best view of the cove."),
]
SECRETS = [
    dict(title="Tobin's rum cellar", pos=(110, 3, 91), xray=True,
         desc="One root cellar in the Church Road wall holds more than turnips: barrels, a still and a locked chest."),
    dict(title="The belfry chest", pos=(21, 19, 97),
         desc="Climb the ladder in the church tower: a chest sits under the bell."),
]
STATS = [("20", "houses"), ("31", "buildings")]

GB, GC, GD = 3, 6, 9
STAIRS_B = [14, 72, 128, 158]          # x of each 3-wide stair up to Middle Street
STAIRS_C = [36, 94, 151]                # ... and up to Church Road
STAIRS_D = [66, 120]                    # ... and up to Hill Road
CELLARS = [20, 60, 110, 132]            # root cellars in the Church Road wall
YARD = ["dory", "bake", "chart", "cats", "party", "flag", "books", "woodpile", "shop"]


def veg_bed(m, x1, z1, x2, z2, g, crop="potatoes"):
    crop_bed(m, x1, z1, x2, z2, crop=crop, y=g)


def house_lot(m, h, a, b, z_front, z_house, z_back, g, i, d=12):
    """Front fence and walk, the house (with a veranda unless it is a biscuit box), a back
    garden with something of the owner's."""
    w = h.get("w", 15 if b - a >= 18 else 14)
    x = a + (b - a + 1 - w) // 2
    d = h.get("d", d)
    info = clapboard_house(m, x, z_house, g, w, d, style=h["style"], wall=h["wall"], trim=h.get("trim", "white_concrete"),
                           roof=h["roof"], storeys=h.get("storeys", 2), h=5, cross=h.get("cross", False),
                           interior="house", seed=i * 11 + 3, rug=["red", "blue", "green", "brown", "gray", "orange"][i % 6],
                           veranda=0 if h["style"] == "biscuit" else 3)
    door_x = info["door"][0]
    with m.step("gardens"):
        for xx in range(a, b + 1):
            if xx == door_x:
                m.put(xx, g, z_front, "birch_fence_gate", facing="south")
            else:
                m.put(xx, g, z_front, "birch_fence")
        for zz in range(z_front + 1, z_house - 1):
            m.put(door_x, g - 1, zz, "dirt_path")
        flower_bed(m, a + 1, z_front + 1, door_x - 2, z_house - 2, flowers=("allium", "blue_orchid", "poppy", "oxeye_daisy"),
                   density=0.6, seed=i, y=g)
        flower_bed(m, door_x + 2, z_front + 1, b - 1, z_house - 2, flowers=("allium", "lilac", "cornflower", "dandelion"),
                   density=0.6, seed=i + 50, y=g)
        zb1 = z_house + d + 1
        for xx in range(a, b + 1):
            if xx == (a + b) // 2:
                m.put(xx, g, z_back, "birch_fence_gate", facing="south")     # out to the back lane
            else:
                m.put(xx, g, z_back, "birch_fence")
        for zz in range(zb1, z_back):
            m.put(b, g, zz, "birch_fence")
        veg_bed(m, a + 1, zb1 + 1, a + 6, zb1 + 3, g, crop=["potatoes", "carrots", "beetroot"][i % 3])
        clothesline(m, a + 8, b - 2, z_back - 1, g)
        kind = h.get("yard", YARD[i % len(YARD)])
        if kind == "woodpile":
            for xx in range(b - 5, b - 2):
                for yy in (g, g + 1):
                    m.put(xx, yy, zb1 + 2, "spruce_log", axis="x")
        elif kind == "dory":
            m.put(b - 5, g, zb1 + 2, "spruce_log", axis="x")
            m.put(b - 2, g, zb1 + 2, "spruce_log", axis="x")
            dory(m, b - 6, zb1 + 2, y=g + 1, along="x", color="blue_concrete")
        else:
            shed(m, b - 6, zb1, g, wall=["spruce_planks", "red_terracotta", "white_concrete"][i % 3])
    return info


def build(m):
    W, D = FOOTPRINT

    # ------------------------------------------------------------ walls, terraces, steps, cellars
    with m.step("walls"):
        for x in range(0, 146):
            for y in range(-6, 0):
                m.put(x, y, 20, "stone_bricks" if y < -1 else "smooth_stone")
        retaining_wall(m, 0, W - 1, 58, 0, GB, gaps=[(x, x + 2) for x in STAIRS_B], seed=1)
        retaining_wall(m, 0, W - 1, 89, GB, GC, gaps=[(x, x + 2) for x in STAIRS_C], seed=2)
        for x in STAIRS_B:
            terrace_stairs(m, x, 58, 0, GB)
        for x in STAIRS_C:
            terrace_stairs(m, x, 89, GB, GC - GB)
        retaining_wall(m, 0, W - 1, 124, GC, GD, gaps=[(x, x + 2) for x in STAIRS_D], seed=3)
        for x in STAIRS_D:
            terrace_stairs(m, x, 124, GC, GD - GC)
        for (z1, z2, g) in ((58, 88, GB), (89, 123, GC), (124, 151, GD)):          # terrace ends
            for z in range(z1, z2 + 1):
                for x in (0, W - 1):
                    for y in range(0, g):
                        m.put(x, y, z, "stone_bricks" if (x + y + z) % 7 else "mossy_stone_bricks")
        for x in range(0, W):                                                          # back of the hill
            for y in range(0, GD):
                m.put(x, y, 151, "stone_bricks" if (x + y) % 7 else "mossy_stone_bricks")
        for i, x in enumerate(CELLARS):
            wall_cellar(m, x, 89, GB, depth=3, seed=i, stash=(x == 110))

    # ------------------------------------------------------------ streets
    with m.step("streets"):
        road(m, 0, 21, 145, 33, -1, "cobblestone", {"stone": 0.25, "andesite": 0.2, "mossy_cobblestone": 0.08}, seed=1)
        road(m, 0, 34, 145, 38, -1, "gravel", {"andesite": 0.2, "coarse_dirt": 0.1}, seed=2)
        road(m, 0, 59, W - 1, 62, GB - 1, "gravel", {"coarse_dirt": 0.15, "andesite": 0.1}, seed=3)
        road(m, 0, 90, W - 1, 93, GC - 1, "cobblestone", {"mossy_cobblestone": 0.2, "stone_bricks": 0.1}, seed=4,
             over=False)                                                               # keeps the cellar ceilings
        road(m, 0, 125, W - 1, 128, GD - 1, "gravel", {"coarse_dirt": 0.15, "andesite": 0.1}, seed=9)
        road(m, 146, 34, 157, 38, -1, "gravel", {"coarse_dirt": 0.2}, seed=5)       # out to the point
        road(m, 154, 39, 156, 40, -1, "gravel", seed=6)
        road(m, 157, 24, 158, 33, -1, "gravel", seed=8)
        for x in STAIRS_B:                                                             # landings at the stair feet
            road(m, x, 54, x + 2, 55, -1, "stone_bricks")

    # ------------------------------------------------------------ wharf, piers, breakwater
    with m.step("wharf"):
        wharf(m, 60, 6, 100, 19)
        wharf(m, 102, 5, 112, 19)                                                      # co-op wharf
        clapboard_house(m, 104, 8, 0, 8, 7, style="gable", wall="white_concrete", trim="spruce_planks", roof="spruce",
                        storeys=1, h=4, interior="loft", porch=False, chimney=None, seed=32)
        longliner(m, 70, 3, hull="red_concrete")
        longliner(m, 8, 5, hull="blue_concrete", stripe="yellow_concrete")
        for y in range(0, 6):                                                          # crane
            m.put(96, y, 8, "spruce_log", axis="y")
        for x in range(91, 96):
            m.put(x, 5, 8, "spruce_log", axis="x")
        m.put(91, 4, 8, "iron_chain")
        m.put(91, 3, 8, "iron_chain")
        for (x, z) in ((66, 15), (67, 15), (66, 16), (84, 7), (85, 7), (90, 14)):
            m.put(x, 0, z, "barrel", facing="up")
        m.put(66, 1, 15, "barrel", facing="up")
        finger_pier(m, 116, 2, 118, 19)
        finger_pier(m, 133, 2, 135, 19)
        for z in (4, 10, 15):
            finger_pier(m, 119, z, 128, z + 1)
        for z in (6, 12):
            finger_pier(m, 136, z, 144, z + 1)
        cells = set()
        for x in range(146, W):
            zc = 19 - int((x - 146) * 0.55)
            for z in range(zc - 2, zc + 3):
                cells.add((x, z))
            for z in range(17, 20):
                cells.add((x, z))
        rock_pile(m, sorted(cells), seed=3, top=(-1, 2))
        for (x, z) in ((70, 10), (71, 10), (70, 11), (88, 16), (89, 16), (106, 16), (107, 16), (106, 17)):
            m.put(x, 0, z, "barrel", facing="up")                                      # fish tubs and crates
        # bait shed on the wharf
        clapboard_house(m, 84, 11, 0, 9, 7, style="gable", wall="red_terracotta", trim="spruce_planks", roof="spruce",
                        storeys=1, h=4, interior="loft", porch=False, chimney=None, seed=31)

    # ------------------------------------------------------------ stages, flakes, net lofts, slipway
    with m.step("stages"):
        stage(m, 3, 9, 9, 11, wall="red_terracotta")
        stage(m, 15, 9, 9, 11, wall="spruce_planks", trim="dark_oak_planks")
        stage(m, 27, 9, 9, 11, wall="white_concrete", trim="spruce_planks", roof="dark_oak_stairs")
        stage(m, 47, 9, 9, 11, wall="yellow_terracotta", trim="spruce_planks")
        flake(m, 50, 22, 56, 31, 0, seed=4)
        slipway(m, 41, 8, 31, y_top=0, width=5)
        for i, (x, wall) in enumerate(((4, "red_terracotta"), (16, "spruce_planks"), (28, "light_gray_concrete"))):
            clapboard_house(m, x, 23, 0, 9, 8, style="gable", wall=wall, trim="dark_oak_planks", roof="spruce",
                            storeys=2, h=4, interior="loft", porch=False, chimney=None, seed=40 + i)
        for i, x in enumerate((13, 25, 37)):
            pot_stack(m, x, 31, 0, n=3, seed=i)

    # ------------------------------------------------------------ harbourmaster
    with m.step("harbourmaster"):
        hm = clapboard_house(m, 64, 22, 0, 16, 10, style="gable", cross=True, wall="white_concrete",
                             trim="red_concrete", roof="brick", storeys=2, interior="office", seed=5)
        zr = max(range(23, 31), key=hm["H"])
        cupola(m, 68, zr, hm["top"])
        flagpole(m, 82, 24, 0)
        bench(m, 79, 0, 32, "north", length=3)

    # ------------------------------------------------------------ fish plant
    with m.step("fishplant"):
        clapboard_house(m, 90, 22, 0, 42, 11, style="gable", wall="light_gray_concrete", trim="white_concrete",
                        roof="spruce", storeys=1, h=6, interior="plant", porch=False, chimney=None, every=4, seed=6)
        for dx in (98, 123):
            m.door(dx, 1, 22, "south", key="spruce_door")
            m.put(dx, 0, 21, "spruce_stairs", facing="south")
        # co-op office upstairs at the east end, over an outside stair
        for x in range(124, 132):
            for z in range(22, 33):
                edge = x in (124, 131) or z in (22, 32)
                if edge:
                    for y in range(7, 11):
                        m.put(x, y, z, "white_concrete" if (y == 10 or x in (124, 131) and z in (22, 32)) else
                              "light_gray_concrete")
                if not edge:
                    m.put(x, 10, z, "light_gray_concrete")
        for x in (126, 129):
            m.put(x, 8, 22, "glass_pane")
            m.put(x, 9, 22, "glass_pane")
        two_slope_roof(m, 124, 22, 131, 32, 11, 11, "spruce_stairs", gable="light_gray_concrete",
                       ridge="spruce_planks", cap="spruce_slab")
        I_room = interiors.Room(m, 125, 23, 130, 31, 7, (), 33, "spruce", ceil=3)
        interiors.office(I_room, "south")
        m.door(131, 7, 27, "west", key="spruce_door")
        stair_run(m, 139, 0, 27, "west", 7, width=1, key="spruce_stairs", support="spruce_planks")
        for x in range(132, 133):
            m.put(x, 6, 27, "spruce_planks")                                           # landing
        m.floor("co-op office", 7, 125, 23, 130, 31)
        for x in range(136, 139):                                                     # fuel tanks
            for z in range(24, 26):
                for y in range(0, 3):
                    m.put(x, y, z, "iron_block")

    # ------------------------------------------------------------ Water Street
    with m.step("waterst_a"):
        clapboard_house(m, 3, 40, 0, 24, 14, style="gable", cross=True, wall="green_concrete", storeys=2, h=5,
                        interior="pub", seed=7, rug="red")
        clapboard_house(m, 33, 40, 0, 21, 13, style="biscuit", wall="yellow_concrete", roof="dark_oak", storeys=2, h=5,
                        interior="restaurant", seed=8)
        awning(m, 36, 41, 39, 4, ("blue_wool", "white_wool"))
        awning(m, 45, 50, 39, 4, ("blue_wool", "white_wool"))
        awning(m, 63, 69, 39, 4)
        awning(m, 73, 80, 39, 4)
        clapboard_house(m, 61, 40, 0, 22, 14, style="gable", cross=True, wall="red_concrete", storeys=2, h=5,
                        interior="shop", seed=9)
    with m.step("waterst_b"):
        clapboard_house(m, 89, 40, 0, 24, 14, style="saltbox", wall="light_blue_concrete", storeys=3, interior="inn",
                        seed=10)
        clapboard_house(m, 120, 40, 0, 22, 14, style="biscuit", wall="white_concrete", trim="black_concrete",
                        roof="dark_oak", storeys=3, h=5, interior="house", seed=11, rug="blue")

    # ------------------------------------------------------------ lighthouse point
    with m.step("point"):
        for (x, z, size) in ((150, 23, 2), (169, 31, 1), (167, 38, 2), (149, 31, 1), (168, 52, 1), (163, 55, 1)):
            boulder(m, x, z, 0, size=size, seed=x)
        lighthouse(m, 159, 31, 0, height=20, r=4)
        clapboard_house(m, 165, 24, 0, 5, 5, style="gable", wall="stone_bricks", trim="stone_bricks", roof="brick",
                        storeys=1, h=3, interior=None, porch=False, chimney=None)           # oil house
        for x in range(152, 171):
            for z in (22, 40):
                if not (z == 22 and 156 <= x <= 160) and x != 157 and m.empty(x, 0, z):
                    m.put(x, 0, z, "cobblestone_wall")
        for z in range(23, 40):
            for x in (152, 170):
                if m.empty(x, 0, z):
                    m.put(x, 0, z, "cobblestone_wall")
        clapboard_house(m, 150, 42, 0, 11, 9, style="gable", wall="white_concrete", trim="red_concrete", roof="brick",
                        storeys=2, interior="house", seed=12, rug="green")

    # ------------------------------------------------------------ houses
    with m.step("middle"):
        for i, (h, (a, b)) in enumerate(zip(HOUSES_B, LOTS_B)):
            house_lot(m, h, a, b, 63, 67, 84, GB, i, d=11)
    with m.step("churchrd"):
        for i, (h, (a, b)) in enumerate(zip(HOUSES_C, LOTS_C)):
            house_lot(m, h, a, b, 94, 98, 121, GC, i + 9)

    # ------------------------------------------------------------ Hill Road: school, hall, houses, lookout
    with m.step("hill"):
        sc = clapboard_house(m, 4, 131, GD, 30, 12, style="gable", cross=True, wall="white_concrete", trim="red_concrete",
                             roof="deepslate", storeys=2, h=5, interior="school", seed=21)
        zr = max(range(132, 142), key=sc["H"])
        cupola(m, 10, zr, sc["top"], glass="iron_bars")
        m.put(10, sc["top"] + 2, zr, "bell", hanging=True, facing="north")
        for x in (5, 13):                                                              # swings
            for y in range(GD, GD + 4):
                m.put(x, y, 147, "spruce_fence")
        for x in range(5, 14):
            m.put(x, GD + 4, 147, "spruce_log", axis="x")
        for x in (8, 10):
            m.put(x, GD + 3, 147, "iron_chain")
            m.put(x, GD + 2, 147, "iron_chain")
            m.put(x, GD + 1, 147, "spruce_slab", half="top")
        for x in range(18, 23):                                                        # sandbox
            for z in range(145, 150):
                edge = x in (18, 22) or z in (145, 149)
                if edge:
                    m.put(x, GD, z, "oak_log", axis="x")
                else:
                    m.put(x, GD - 1, z, "sand")
        clapboard_house(m, 44, 131, GD, 34, 14, style="gable", wall="white_concrete", trim="green_concrete",
                        roof="deepslate", storeys=1, h=6, interior="hall", seed=22, chimney=None)
        for i, (h, (a, b)) in enumerate(zip(HOUSES_D, LOTS_D)):
            house_lot(m, h, a, b, 129, 133, 150, GD, i + 16, d=11)
        gazebo(m, 162, 140, GD, r=3)
        bench(m, 156, GD, 146, "north", length=3)
        flagpole(m, 156, 132, GD)
        spruce_tree(m, 169, GD, 133, height=8, seed=31)
        spruce_tree(m, 167, GD, 149, height=7, seed=32)
        boulder(m, 157, 149, GD, size=1, seed=33)

    # ------------------------------------------------------------ church
    with m.step("church"):
        church(m, 15, 101, GC, w=15, d=23)
        graveyard(m, 2, 98, 13, 121, GC, seed=1)
        graveyard(m, 32, 98, 42, 121, GC, seed=2)
        fence_ring(m, 1, 94, 43, 122, y=GC, key="birch_fence", gates=[(22, 94, "south")])
        m.put(21, 19, 97, "chest", facing="south")

    # ------------------------------------------------------------ gardens, trees, lupins
    with m.step("gardens"):
        for x0 in (0, 34, 92, 112):
            flower_bed(m, x0 + 1, 55, x0 + 11, 57, flowers=("allium", "lilac", "blue_orchid", "allium"), density=0.7,
                       seed=x0, y=0)
        for x in (40, 100, 140):
            bench(m, x, 0, 56, "north", length=2)
        for i, (x, z, g) in enumerate(((5, 116, GC), (40, 117, GC), (60, 119, GC), (90, 118, GC), (126, 119, GC),
                                       (165, 117, GC), (168, 80, GB), (3, 79, GB), (150, 54, 0), (167, 45, 0))):
            spruce_tree(m, x, g, z, height=7 + i % 3, seed=i)
        for (x, z) in ((44, 56), (88, 56), (120, 56)):
            bush(m, x, 0, z, "spruce_leaves")
        # lupins along the terrace edges
        for (x1, x2, z, g) in ((1, 13, 57, 0), (45, 69, 57, 0), (75, 127, 57, 0), (1, 35, 88, 3), (39, 93, 88, 3),
                               (97, 150, 88, 3), (154, 170, 88, 3), (1, 65, 123, 6), (69, 119, 123, 6),
                               (123, 170, 123, 6)):
            flower_bed(m, x1, z, x2, z, flowers=("allium", "lilac", "blue_orchid", "allium", "cornflower"),
                       density=0.75, seed=x1 + z, y=g)
        for i, (x, z, g) in enumerate(((10, 87, GB), (49, 86, GB), (83, 87, GB), (140, 86, GB), (52, 122, GC),
                                       (88, 122, GC), (142, 122, GC), (100, 148, GD), (30, 147, GD))):
            spruce_tree(m, x, g, z, height=6 + i % 3, seed=60 + i)
        for i, (x, z, g, sz) in enumerate(((147, 56, 0, 1), (2, 86, GB, 1), (169, 86, GB, 1), (44, 122, GC, 1),
                                           (169, 122, GC, 1), (1, 141, GD, 1))):
            boulder(m, x, z, g, size=sz, seed=80 + i)

    # ------------------------------------------------------------ lamps, boats, life
    with m.step("life"):
        for x in range(6, 146, 14):
            lamp_post(m, x, 0, 34, height=3)
        for x in range(9, W, 19):
            lamp_post(m, x, GB, 59, height=3)
            lamp_post(m, x + 9, GC, 90, height=3) if x + 9 < W else None
        for x in range(9, W, 19):
            lamp_post(m, x, GD, 125, height=3)
        power_line(m, 2, 144, 38, 0, every=13)
        power_line(m, 2, 169, 62, GB, every=14)
        power_line(m, 2, 169, 93, GC, every=14)
        power_line(m, 2, 169, 128, GD, every=14)
        for (x, z) in ((60, 6), (100, 6), (60, 19), (112, 5)):
            lamp_post(m, x, 0, z, height=2)
        for y in range(-6, 1):                                                        # light at the breakwater end
            m.put(170, y, 6, "stone_bricks")
        lamp_post(m, 170, 1, 6, height=2)
        for (x, z, along, col) in ((120, 8, "x", "red_concrete"), (121, 13, "x", "yellow_concrete"),
                                   (137, 10, "x", "green_concrete"), (6, 4, "x", "blue_concrete"),
                                   (104, 2, "x", "orange_concrete")):
            dory(m, x, z, y=-2, along=along, color=col)
        m.entity(45, 0, 36, "cat", name="Skipper")
        m.entity(63, GB, 61, "cat", name="Duff")
        m.entity(101, GC, 91, "cat", name="Bride's Tom")
        m.entity(68, 1, 24, "villager_v2", name="Harbourmaster Fitzgerald")
