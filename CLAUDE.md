# Minecraft Build Studio

We design Minecraft **Bedrock** builds together, preview them in a browser voxel world,
and export each build as a behavior pack (`.mcpack`) of `/function`s. The user plays on
PS5 through a Realm; packs are imported on a phone or PC (`config.json` → `platform`,
`phone_os`) and activated on the Realm from there.

## Project map

| Path | What it is |
|---|---|
| `data/` | Mojang bedrock-samples metadata (blocks, entities, commands, version). `python3 data/fetch.py [tag]` refreshes it. Every block ID/state and entity ID is validated against it. |
| `blocks/palette.py` | The palette: block key → Bedrock id, shape, props + how they map to states, rotation rules, colour, procedural texture, light. Writes `blocks/palette.json` for the viewer. |
| `lib/voxel.py` | `Model`: `put/box/clear/get/empty/air`, steps (`with m.step(...)`), tags, markers (`door`, `bed`, `entity`), `tall_plant`, `floor` (declares a walkable level). |
| `lib/roofs.py`, `lib/buildings.py`, `lib/outdoor.py` | Helpers: `gable_roof`, `shed_roof`, `two_slope_roof` (gable/saltbox), `hip_roof`, `cross_gable`, `timber_frame`, `chimney`, `deck_on_piles`, `stair_run`, `oak_tree`, `spruce_tree`, `bush`, `path`, `fence_ring`, `crop_bed`, `flower_bed`, `lamp_post`, `bench`. All exported from `lib/__init__.py`. |
| `lib/houses.py`, `lib/interiors.py` | `clapboard_house` (gable / saltbox / biscuit box, cross gables, verandas, real staircases, attic ladder, partitions, hearth, chimney, furnished by `interior=` house, pub, restaurant, shop, inn, office, plant, loft, school, hall), `cupola`, `shed`; `interiors.Room` and the room recipes (kitchen, parlour, bedroom, pub, restaurant, shop, office, fish_plant, loft, school, hall) and pieces (table, chair, dining, rug, ceiling_lamp). |
| `lib/harbour.py`, `lib/landmarks.py` | Waterfront on piles (no water placed): `wharf`, `finger_pier`, `stage`, `flake`, `rock_pile`, `dory`, `longliner`, `slipway`. Landmarks and terraces: `lighthouse`, `church`, `graveyard`, `gazebo`, `flagpole`, `root_cellar`, `wall_cellar`, `retaining_wall`, `terrace_stairs`, `road`, `clothesline`, `boulder`, `power_line`, `awning`, `pot_stack`. |
| `lib/build.py` | Loads `builds/<name>/build.py`, merges `edits/<name>.json`. |
| `lib/world.py` | Places every build from `world/world.json` (position + facing) on the terrain; flags collisions. |
| `builds/<name>/build.py` | One file per build (see template below). |
| `world/world.json` | Terrain (`grade` = Y of the grass layer, `sea_level`, `bounds`, `water` areas) and each build's `pos` [x, z] of its marker and `facing`. |
| `edits/<name>.json` | Blocks placed/removed by hand in the viewer; merged on top of the generated model and included in counts, checks and the pack. |
| `export/core.py` | Commands per facing: `step01_site` (site prep), `step02_<key>`… (one per build step, split `_a/_b` when long), entities, setup (ticking area), test_blocks, cleanup, build wrapper. Greedy box merging, `/fill` ≤ 32,768, functions ≤ 9,000 lines, derived states (stair corners, fence/pane/wall connections). |
| `export/sim.py` | Replays the `.mcfunction` files into a simulated world. |
| `export/checks.py` | Game-rule checks, block counts, replay comparison in all four facings. |
| `export/pack.py`, `export/plan.py` | `.mcpack` writer (stable UUIDs, version bumps only when content changes, `export/versions.json`), plan maps and pack icon. |
| `viewer/` | "Build book" viewer: `index.html` + `js/` (three.js r158 and the Michroma / Inter / IBM Plex Mono fonts in `vendor/`), `server.py` (dev server, live reload, saves edits), `static.py` (single-file HTML, fonts inlined), `tools/shoot.js` (headless screenshots), `tools/roundtrip.js` (edit round-trip test). Lighting: shadowing sun, sky environment light, haze, ACES tone mapping, baked voxel sky/block light and AO. |
| `out/<name>/` | Generated: `model.json` (viewer data), `report.md`, `plan_areas.png`, `plan_top.png`, `pack/`, `<name>.mcpack`, `<name>.html`, `shots/`. `out/world.json`, `out/world_plan.png`. |

## Commands

```bash
python3 studio.py palette          # validate the palette (all props, all 4 facings) + write palette.json
python3 studio.py new <name>       # scaffold builds/<name>/build.py and add it to world.json
python3 studio.py plan <name>      # area plan map only: out/<name>/plan_areas.png
python3 studio.py build <name>     # model + checks + 4-facing export + replay + pack + report
python3 studio.py build --all
python3 studio.py world            # out/world.json + out/world_plan.png (build collisions)
python3 studio.py serve            # viewer at http://localhost:8765, rebuilds + reloads on change
python3 studio.py html <name>      # out/<name>/<name>.html, self-contained, opens from disk
python3 studio.py shoot <name> [views]   # out/<name>/shots/*.png (ui approach aerial front back plan night sunset world area:<key>)
node viewer/tools/roundtrip.js <name> <x> <y> <z> <block>   # place via the viewer, verify edits → rebuild → pack
```

`studio.py build` exits non-zero when any check is an error. Read `out/<name>/report.md`.
A build over ~9,000 commands is exported as `build_1`, `build_2`, … (Bedrock runs at most 10,000 commands
per call); `build` then just lists the parts. The replay runs exactly those parts. Big builds take minutes
to screenshot in headless software WebGL; run `shoot` in the background.

## Conventions

- **Local frame**: +x east, +z south, +y up. `y = 0` is the first layer above grade (feet level);
  `y = -1` is the grass layer. The build's **front faces north** (−z) in its own file; `world.json`
  `facing` turns it (north/east/south/west = 0/1/2/3 quarter turns clockwise).
- **Footprint** `(W, D)` covers cells `0..W-1`, `0..D-1`. Nothing may be placed outside it.
- **Marker** (default `(0, 0, -2)`): where the player stands (feet) to run the functions; every command
  is relative (`~`) to it. Viewer readouts are relative to it. World placement uses
  `/execute positioned X Y Z run function <name>/<facing>/...` with X Y Z = marker in world.json.
- **Props** are model-level and rotate with the build: `facing` (direction of ascent for stairs, the way
  you walk through a door/gate, the way a ladder/torch points away from its wall, the way a chest/furnace
  front looks), `half`, `axis`, `open`, `hinge`, `hanging`, `upper`, `head`, `age`.
- **Steps**: one function per step; every cell belongs to exactly one step. Site prep is always step 01
  (`step01_site`), so build step N is function `stepNN` with NN = N + 1, matching the viewer's numbering. Supports must be in the same
  or an earlier step. Within a step the exporter places solids → partial blocks → attachments → water.
- **Keep-zones**: `dict(box=(x1, z1, x2, z2), what="water"|"keep", depth=2, surface=-1, build_ok=False, note=...)`.
  Site prep skips them. Normally the build may not place anything inside; `build_ok=True` makes a waterfront
  zone the build may stand piers and decks in (still never cleared or filled; nothing becomes water).
  Water keep-zones show as water at `surface` in the viewer. Blocks tagged `afloat` (boats) are exempt from
  the floating check.
- **Terraces**: `GRADES = [dict(box=(x1, z1, x2, z2), y=3, name=...)]` raises the ground (feet level `y`)
  over a box; site prep clears above and fills below each terrace's own grade. Use `retaining_wall` +
  `terrace_stairs` at the terrace edges. `TEST_STRIP = (x, z)` moves the test_blocks strip off the site.
- **Natural ground**: `HEIGHTMAP = {(x, z): feet_level}` gives every cell its own ground height (overrides
  GRADES). Site prep clears the site above y=0, fills holes, then raises merged same-height rectangles.
  Build it with `lib/terrain.py`: `value_noise`, `relax` (no step over 1 block except deliberate cliffs;
  fixed pads never move), `cliff_faces`, `smooth_line` + `widen` for lanes, `surface`, `scatter`.
  Level a pad under every building so it sits flat, then relax the rest around it.
- **Turned buildings**: build a piece facing north in `m.sub()` at its own origin, then
  `m.stamp(sub, x, z, turns, anchor=rect)`; doors, beds, entities, floors and every directional prop turn
  with it. `house_lot` does this for a whole furnished house plus garden (`lot_size`, `lot_frames`).
- **Organic layouts** (see `builds/outport`): lay lanes first, seat lots along them facing the lane (or the
  water), infill the gaps with smaller buildings joined by footpaths, then scatter nature on what is left.
  Avoid grids and straight rows; the user prefers irregular, lived-in towns.
- **Areas**: `dict(key, title, box=(x1, z1, x2, z2), desc, ring=False, rest=False, pill=True, label=True)`;
  must not overlap (`ring=True` covers only the edge cells; `rest=True` covers whatever no other area does).
  They drive the plan map, info cards, view pills and labels.
- Adding a block: add it in `blocks/palette.py` (reuse a shape), run `python3 studio.py palette`;
  it must validate in all four facings before use. Adding a pattern for its texture: `viewer/js/textures.js`.

### build.py template

```python
"""One paragraph: what it is, style, notable features."""
from lib import *

TITLE = "Harbour Inn"
FOOTPRINT = (30, 24)
MARKER = (0, 0, -2)
TARGET_BLOCKS = 2500
STEPS = [("foundation", "Foundation", "..."), ("walls", "Walls", "..."), ("roof", "Roof", "...")]
KEEP_ZONES = [dict(box=(20, 0, 29, 9), what="water", depth=3, note="existing bay")]
AREAS = [dict(key="inn", title="Inn", box=(2, 10, 18, 22), desc="...")]
# viewer presentation (all optional)
SUBTITLE = "Harbour inn and fish market · Minecraft Bedrock build book"   # header line under the title
SUBJECT = "Harbour"              # name of the areas tab and of the Faces control ("Harbour faces")
STATS = [("12", "rooms")]        # extra header stat tiles (default: number of steps)
LEVELS = [("Lamp", 22), ("Ground", 0), ("Water", -2)]   # named stops on the Cut slider (y shown up to)
SECRETS = [dict(title="Smugglers' cellar", pos=(5, -3, 12), desc="...")]   # Secrets tab, Focus = x-ray + cut
STEPS_HEADLINE = "Eight steps, grass to gazebo"   # Steps tab heading (default generated)

def build(m):
    with m.step("foundation"):
        ...
```

## Workflow (follow it for every build)

1. **Confirm first, before writing code**: what the build is, where it sits in the world (position next to
   the existing builds, which way the front faces), the style/materials, and the target block count.
   Ask if any of it is unclear. Do not guess the target.
2. **Lay out areas**: write `FOOTPRINT`, `KEEP_ZONES`, `AREAS` and a stub `build()`; add the build to
   `world/world.json`. Run `python3 studio.py plan <name>` and `python3 studio.py world`, look at
   `out/<name>/plan_areas.png` and `out/world_plan.png`, and fix every collision (areas overlapping each
   other, outside the footprint, onto keep-zones; footprints overlapping other builds or world water).
3. **Write build.py with the helpers.** When a pattern will repeat (a window style, a dock, a market stall),
   add a helper to `lib/` (export it in `lib/__init__.py`) instead of copy-pasting.
4. **Build the way the game needs**:
   - roofs from regular (bottom-half) stairs only; upside-down stairs never in a roof (`tag("roof")` cells);
   - nothing floating: every block connects to the ground (stair roof slopes count as connected);
   - ladders on a solid full block behind them; lanterns hang from a block above or stand on one;
     torches on a solid wall or a block below; crops on farmland; flowers on soil;
   - beacons with clear sky above (glass is fine) and a 3x3 metal base;
   - a way up to every upper floor (stairs or ladders), declared with `m.floor(...)` (timber_frame does this);
   - doors open onto walkable space on both sides (floor under each side, two blocks of head room);
   - no hidden underground fill counted toward the target (the counter excludes buried below-grade blocks);
   - keep-zones untouched; water fully enclosed so it cannot flow.
5. **Validate**: `python3 studio.py build <name>` checks every block ID and state in all four rotations,
   replays the export for all four facings into a messy simulated site (trees, holes, water) and compares
   against the model, confirms keep-zones are unchanged, every door/bed/entity marker lands in clear space,
   `/fill` volumes, function lengths and ticking areas. Fix every error; justify any warning.
6. **Screenshot and review**: `python3 studio.py shoot <name>` (full UI, approach, aerial, front, back, plan,
   night, sunset, world, each area). Open the images, look for anything wrong (floating bits, wrong stair direction, gaps,
   dark interiors with no light, missing ladders, odd textures) and fix it. Re-shoot after fixes.
7. **Report and deliver**: give per-step and total block counts against the target (from
   `out/<name>/report.md`), then deliver `out/<name>/<name>.mcpack` (and `<name>.html` if they want to
   share a preview), with the in-game commands for the chosen facing. Then commit and push to `main`
   on https://github.com/cj-ax/mc-build-studio (`out/` is git-ignored; `export/versions.json` and
   `edits/` are committed).

Edits: when the user edits in the viewer, the dev server saves `edits/<name>.json` and rebuilds. Treat
edits as part of the build: they go through every check; mention any errors they introduce.

## Things to confirm in game (not verifiable offline)

The data says which states exist, not exactly how each value looks. Assumptions to check with
`test_blocks` the first time a block family is used, then note the result here:
- doors: `minecraft:cardinal_direction` = the way you walk through from outside; `door_hinge_bit` false = left hinge.
- trapdoors: `direction` mapped like stairs (east 0, west 1, south 2, north 3).
- stairs: `minecraft:corner` uses Java's names/semantics (inner/outer left/right).
- torches: `torch_facing_direction` = the way the flame leans (attached to the opposite block).
- beds/doors are placed half by half (lower then upper, foot then head) with `setblock`.
- fences/panes/walls: connection states are written explicitly from neighbours.
- named mobs from `summon` are wild (a summoned cat will wander; tame it in game).
