"""Timber cottage with a garden: a two-storey half-timbered cottage (dark oak frame,
white terracotta infill, spruce roof) in a fenced garden with vegetable beds, a gravel
path, flowers, two oak trees, a back yard by an existing pond (kept untouched) and a cat."""
from lib import *

TITLE = "Timber Cottage"
FOOTPRINT = (25, 23)          # x (east) by z (south); front (gate) faces north
MARKER = (0, 0, -2)           # stand here: 2 blocks north of the north-west fence corner
TARGET_BLOCKS = 1150
STEPS = [
    ("frame", "Timber frame", "Stone plinth, posts and beams, infill walls, windows, door"),
    ("floors", "Floors & ladder", "Ground floor, loft floor, attic ceiling, ladder"),
    ("roof", "Roof & chimney", "Spruce gable roof with planked gables, stone chimney"),
    ("interior", "Interior", "Kitchen corner, bookshelf, loft bedroom"),
    ("garden", "Garden", "Fence and gate, path, vegetable beds, flowers, trees, back yard"),
    ("lighting", "Lighting & life", "Lanterns, door torches, lamp posts, the cat"),
]
KEEP_ZONES = [
    dict(box=(19, 17, 23, 21), what="water", depth=2, note="existing pond"),
]
AREAS = [
    dict(key="fence", title="Garden fence", box=(0, 0, 24, 22), ring=True,
         desc="Oak fence all the way round, gate on the north side."),
    dict(key="house", title="Cottage", box=(6, 8, 18, 18),
         desc="11x9 timber-frame cottage, two storeys. Ladder in the back-right corner to the loft. "
              "Cobblestone chimney against the east gable with a smoking campfire on top."),
    dict(key="veg", title="Vegetable beds", box=(1, 1, 10, 7),
         desc="Carrots and wheat on farmland, each bed watered by a centre channel."),
    dict(key="path", title="Front path", box=(11, 1, 13, 7),
         desc="Gravelly dirt path from the gate to the front step, lamp posts at the gate."),
    dict(key="flowers", title="Flower garden", box=(14, 1, 23, 7),
         desc="Mixed flower bed. The cat lives here."),
    dict(key="orchard", title="Orchard", box=(1, 8, 5, 21),
         desc="Two oak trees and a bush on the west side."),
    dict(key="yard", title="Back yard", box=(7, 19, 18, 21),
         desc="Hay, composter, barrel and a bench looking at the pond."),
    dict(key="pond", title="Pond (kept)", box=(19, 15, 23, 21),
         desc="The existing pond. Site prep and the build never touch it."),
]


def build(m):
    # house: walls x 7..17, z 9..17; ground floor stands at y=1, loft at y=5
    info = timber_frame(
        m, 7, 9, 17, 17, y0=0, storeys=(4, 3), frame="dark_oak_log", infill="white_terracotta",
        floor="spruce_planks", plinth="cobblestone", door_side="north", door="spruce_door",
        roof=dict(ridge="x", stairs="spruce_stairs", cap="spruce_slab", gable="spruce_planks"),
        step_names=dict(frame="frame", floors="floors", roof="roof", details="lighting"),
    )

    with m.step("roof"):
        # against the east gable wall, rising through the roof overhang
        chimney(m, 18, 13, 0, 14)
        m.put(18, 0, 12, "cobblestone")       # wider base
        m.put(18, 0, 14, "cobblestone")
        m.put(18, 1, 12, "cobblestone_stairs", facing="south")
        m.put(18, 1, 14, "cobblestone_stairs", facing="north")

    with m.step("interior"):
        # ground floor (y=1): kitchen along the west wall, bookshelf by the door
        m.put(8, 1, 10, "crafting_table")
        m.put(8, 1, 11, "furnace", facing="east")
        m.put(8, 1, 12, "smoker", facing="east")
        m.put(8, 1, 13, "barrel", facing="up")
        m.put(8, 1, 16, "chest", facing="east")
        m.put(16, 1, 10, "bookshelf")
        m.put(16, 2, 10, "bookshelf")
        m.put(15, 1, 10, "bookshelf")
        bench(m, 13, 1, 13, "north", length=2)          # seat facing the table
        m.put(13, 1, 12, "spruce_fence")                 # table
        m.put(14, 1, 12, "spruce_fence")
        m.put(13, 2, 12, "white_carpet")
        m.put(14, 2, 12, "white_carpet")
        m.put(11, 1, 15, "red_carpet")
        m.put(12, 1, 15, "red_carpet")
        m.put(11, 1, 14, "red_carpet")
        m.put(12, 1, 14, "red_carpet")
        # loft (y=5): bed, chest, rug
        m.bed(9, 5, 15, "south")
        m.put(8, 5, 16, "chest", facing="east")
        m.put(10, 5, 16, "flower_pot")
        for x in range(10, 14):
            m.put(x, 5, 12, "light_gray_carpet")
            m.put(x, 5, 13, "light_gray_carpet")

    with m.step("garden"):
        fence_ring(m, 0, 0, 24, 22, key="oak_fence", gates=[(12, 0, "south")])
        path(m, [(12, 1), (12, 7)], key="dirt_path", mix={"gravel": 0.25, "coarse_dirt": 0.15}, seed=4)
        crop_bed(m, 2, 2, 5, 6, crop="carrots")
        crop_bed(m, 7, 2, 10, 6, crop="wheat")
        flower_bed(m, 15, 2, 22, 5, flowers=("poppy", "dandelion", "cornflower", "oxeye_daisy",
                                             "allium", "pink_tulip", "lilac", "peony"), density=0.7, seed=11)
        for x in list(range(7, 12)) + list(range(13, 18)):
            if x % 2:
                m.put(x, -1, 8, "grass_block")
                m.put(x, 0, 8, "azure_bluet" if x % 4 == 1 else "red_tulip")
        oak_tree(m, 3, 0, 12, height=5, seed=2)
        oak_tree(m, 3, 0, 18, height=6, seed=5)
        bush(m, 2, 0, 9)
        # back yard
        m.put(8, 0, 20, "hay_block")
        m.put(9, 0, 20, "hay_block", axis="x")
        m.put(8, 1, 20, "hay_block")
        m.put(10, 0, 20, "composter")
        m.put(11, 0, 20, "barrel", facing="up")
        m.put(12, 0, 21, "pumpkin", facing="north")
        bench(m, 18, 0, 19, "east", length=2)
        path(m, [(13, 19), (17, 19)], key="dirt_path", seed=9)

    with m.step("lighting"):
        lamp_post(m, 11, 0, 1, height=2)
        lamp_post(m, 13, 0, 1, height=2)
        lamp_post(m, 7, 0, 21, height=2)
        m.entity(17, 0, 6, "cat", name="Biscuit")
