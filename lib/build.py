"""Load builds/<name>/build.py, generate its model and merge edits/<name>.json."""
import importlib.util
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from lib.palette import block
from lib.voxel import Model

ROOT = Path(__file__).resolve().parent.parent
BUILDS = ROOT / "builds"
EDITS = ROOT / "edits"


@dataclass
class Build:
    name: str
    title: str
    description: str
    footprint: tuple
    marker: tuple
    target: int
    steps: list
    keep_zones: list
    areas: list
    model: Model
    book: dict = field(default_factory=dict)       # viewer presentation: subtitle, subject, stats, levels, secrets
    grades: list = field(default_factory=list)     # terraces: [{box, y}] feet level (grass top at y-1); default 0
    test_strip: tuple = None                       # local (x, z) where test_blocks lays its strip
    edit_log: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)

    heightmap: dict = None                         # {(x, z): feet level} from HEIGHTMAP (overrides GRADES)

    @property
    def gmap(self):
        if not hasattr(self, "_gmap"):
            self._gmap = {}
            for t in self.grades:
                x1, z1, x2, z2 = t["box"]
                for xx in range(x1, x2 + 1):
                    for zz in range(z1, z2 + 1):
                        self._gmap[(xx, zz)] = t["y"]
            if self.heightmap:
                self._gmap.update({k: v for k, v in self.heightmap.items()})
        return self._gmap

    def grade_at(self, x, z):
        """Feet level of the ground at (x, z): 0 unless a terrace / the heightmap raises it."""
        return self.gmap.get((x, z), 0)

    def grade_rects(self, include_zero=False):
        """The ground as non-overlapping rectangles of one grade: [{box, y}] (greedy merge)."""
        cells = {k: v for k, v in self.gmap.items() if include_zero or v != 0}
        return merge_grade_rects(cells)

    def keep_at(self, x, z):
        for k in self.keep_zones:
            x1, z1, x2, z2 = k["box"]
            if x1 <= x <= x2 and z1 <= z <= z2:
                return k
        return None


def names():
    return sorted(p.parent.name for p in BUILDS.glob("*/build.py"))


def load_module(name):
    path = BUILDS / name / "build.py"
    spec = importlib.util.spec_from_file_location(f"builds_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def norm_steps(steps):
    out = []
    for s in steps:
        if isinstance(s, str):
            s = (s,)
        key = s[0]
        out.append(dict(key=key, title=s[1] if len(s) > 1 else key.replace("_", " ").title(),
                        desc=s[2] if len(s) > 2 else ""))
    return out


def norm_keep(zones):
    out = []
    for z in zones or []:
        z = dict(z) if isinstance(z, dict) else dict(box=z)
        z.setdefault("y", (-8, 48))
        z.setdefault("what", "keep")
        z.setdefault("depth", 2)
        z.setdefault("surface", -1)        # y of the top water block (water keep-zones, viewer + checks)
        z.setdefault("build_ok", False)    # True: the build may stand piers/decks in it (still never prepped)
        z.setdefault("note", "")
        z["box"] = list(z["box"])
        z["y"] = list(z["y"])
        out.append(z)
    return out


def norm_areas(areas):
    out = []
    for a in areas or []:
        a = dict(a)
        a.setdefault("title", a["key"].replace("_", " ").title())
        a.setdefault("desc", "")
        a["box"] = list(a["box"])
        out.append(a)
    return out


def merge_grade_rects(cells):
    """{(x, z): y} -> [{box: [x1, z1, x2, z2], y}] covering exactly those cells."""
    left = dict(cells)
    out = []
    for (x, z) in sorted(cells, key=lambda p: (p[1], p[0])):
        if (x, z) not in left:
            continue
        y = left[(x, z)]
        x2 = x
        while left.get((x2 + 1, z)) == y:
            x2 += 1
        z2 = z
        while all(left.get((xx, z2 + 1)) == y for xx in range(x, x2 + 1)):
            z2 += 1
        for xx in range(x, x2 + 1):
            for zz in range(z, z2 + 1):
                del left[(xx, zz)]
        out.append(dict(box=[x, z, x2, z2], y=y))
    return out


def area_cells(a, others=()):
    """(x, z) cells an area covers. ring=True: only the edge of its box. rest=True: everything in
    its box not covered by the other (non-rest) areas."""
    if a.get("rest"):
        box = a["box"]
        taken = set()
        for o in others:
            if o is not a and not o.get("rest"):
                taken |= area_cells(o)
        return {(x, z) for x in range(box[0], box[2] + 1) for z in range(box[1], box[3] + 1)} - taken
    return _area_cells(a)


def _area_cells(a):
    """(x, z) cells an area covers. ring=True areas cover only the edge of their box."""
    x1, z1, x2, z2 = a["box"]
    return {(x, z) for x in range(x1, x2 + 1) for z in range(z1, z2 + 1)
            if not a.get("ring") or x in (x1, x2) or z in (z1, z2)}


def load(name, with_edits=True):
    mod = load_module(name)
    steps = norm_steps(mod.STEPS)
    m = Model([s["key"] for s in steps])
    mod.build(m)
    b = Build(
        name=name,
        title=getattr(mod, "TITLE", name.title()),
        description=(mod.__doc__ or "").strip(),
        footprint=tuple(mod.FOOTPRINT),
        marker=tuple(getattr(mod, "MARKER", (0, 0, -2))),
        target=int(getattr(mod, "TARGET_BLOCKS", 0)),
        steps=steps,
        keep_zones=norm_keep(getattr(mod, "KEEP_ZONES", [])),
        areas=norm_areas(getattr(mod, "AREAS", [])),
        model=m,
        book=dict(
            subtitle=getattr(mod, "SUBTITLE", ""),
            subject=getattr(mod, "SUBJECT", "Areas"),
            stats=[list(x) for x in getattr(mod, "STATS", [])],
            levels=[list(x) for x in getattr(mod, "LEVELS", [])],
            secrets=[dict(x) for x in getattr(mod, "SECRETS", [])],
            steps_headline=getattr(mod, "STEPS_HEADLINE", ""),
            steps_intro=getattr(mod, "STEPS_INTRO", ""),
            views=[dict(x) for x in getattr(mod, "VIEWS", [])],
        ),
        grades=[dict(box=list(g["box"]), y=int(g["y"]), name=g.get("name", "")) for g in getattr(mod, "GRADES", [])],
        heightmap=dict(getattr(mod, "HEIGHTMAP", None) or {}),
        test_strip=tuple(getattr(mod, "TEST_STRIP", ())) or None,
    )
    if with_edits:
        b.edit_log = apply_edits(b, read_edits(name))
    return b


# ---------------------------------------------------------------- edits
def edits_path(name):
    return EDITS / f"{name}.json"


def read_edits(name):
    p = edits_path(name)
    if not p.exists():
        return {"put": [], "remove": []}
    return json.loads(p.read_text())


def write_edits(name, data):
    EDITS.mkdir(exist_ok=True)
    data = {"build": name, "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "put": data.get("put", []), "remove": data.get("remove", [])}
    edits_path(name).write_text(json.dumps(data, indent=1))
    return data


def apply_edits(b, edits):
    """Removals first, then puts. Doors/beds/tall plants expand to their full shape."""
    m = b.model
    last = m.steps[-1]
    log = {"put": 0, "remove": 0, "errors": []}
    for pos in edits.get("remove", []):
        m.clear(*pos)
        log["remove"] += 1
    for e in edits.get("put", []):
        x, y, z = e["pos"]
        key, props = e["block"], dict(e.get("props") or {})
        step = e.get("step") if e.get("step") in m.steps else last
        try:
            shape = block(key)["shape"]
            with m.step(step):
                if shape == "door":
                    if props.get("upper"):
                        continue
                    m.door(x, y, z, props.get("facing", "north"), key=key,
                           hinge=props.get("hinge", "left"), open=props.get("open", False))
                elif shape == "bed":
                    if props.get("head"):
                        continue
                    m.bed(x, y, z, props.get("facing", "north"), key=key)
                elif shape == "tall_plant":
                    if props.get("upper"):
                        continue
                    m.tall_plant(x, y, z, key)
                else:
                    m.put(x, y, z, key, **props)
            log["put"] += 1
        except (KeyError, ValueError) as ex:
            log["errors"].append(f"edit at {e['pos']}: {ex}")
    b.problems += log["errors"]
    return log
