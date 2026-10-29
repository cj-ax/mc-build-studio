"""Write a Bedrock behavior pack (.mcpack) for a build: all four facings."""
import hashlib
import json
import shutil
import uuid
import zipfile
from pathlib import Path

from lib.palette import FACINGS

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = ROOT / "export" / "versions.json"
CONFIG = ROOT / "config.json"


def config():
    try:
        return json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}


def pack_uuids(name):
    ns = uuid.uuid5(uuid.NAMESPACE_URL, f"https://mc-build-studio.local/{name}")
    return str(uuid.uuid5(ns, "header")), str(uuid.uuid5(ns, "data"))


def next_version(name, digest):
    """Bump the patch number only when the pack content changes (Realms cache by version)."""
    try:
        vs = json.loads(VERSIONS.read_text())
    except (OSError, ValueError):
        vs = {}
    cur = vs.get(name)
    if cur and cur["hash"] == digest:
        return cur["version"]
    ver = [1, 0, (cur["version"][2] + 1) if cur else 1]
    vs[name] = {"hash": digest, "version": ver}
    VERSIONS.write_text(json.dumps(vs, indent=1, sort_keys=True))
    return ver


def write_pack(b, sets, out_dir, icon_png=None):
    """sets: {facing: (files, meta)}. Returns path to the .mcpack."""
    cfg = config()
    pack = out_dir / "pack"
    if pack.exists():
        shutil.rmtree(pack)
    fn_root = pack / "functions" / b.name
    h = hashlib.sha256()
    for f in FACINGS:
        files, _ = sets[f]
        d = fn_root / f
        d.mkdir(parents=True, exist_ok=True)
        for name, lines in sorted(files.items()):
            text = "\n".join(lines) + "\n"
            (d / f"{name}.mcfunction").write_text(text)
            h.update(f"{f}/{name}\n{text}".encode())
    readme = how_to_text(b, sets, cfg)
    (pack / "functions" / b.name / "README.txt").write_text(readme)
    ver = next_version(b.name, h.hexdigest())
    hu, du = pack_uuids(b.name)
    prefix = cfg.get("pack_prefix", "Studio")
    manifest = {
        "format_version": 2,
        "header": {
            "name": f"{prefix}: {b.title}",
            "description": f"{b.title} - /function {b.name}/<facing>/build  (v{'.'.join(map(str, ver))})",
            "uuid": hu, "version": ver, "min_engine_version": [1, 21, 0],
        },
        "modules": [{"type": "data", "uuid": du, "version": ver}],
        "metadata": {"authors": [cfg.get("author", "Minecraft Build Studio")],
                     "generated_with": {"mc_build_studio": ["1.0.0"]}},
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, indent=2))
    if icon_png and Path(icon_png).exists():
        shutil.copy(icon_png, pack / "pack_icon.png")
    mcpack = out_dir / f"{b.name}.mcpack"
    with zipfile.ZipFile(mcpack, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(pack.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(pack).as_posix())
    return mcpack, ver


def install_steps(cfg):
    plat = cfg.get("platform", "phone")
    if plat == "pc":
        get = ["On your PC (Windows), double-click the .mcpack. Minecraft opens and shows "
               "'Import Started' then 'Successfully imported'."]
    else:
        os_ = cfg.get("phone_os", "ios")
        if os_ == "android":
            get = ["On your Android phone, open the .mcpack from Files/Downloads and choose Minecraft. "
                   "Minecraft shows 'Successfully imported'."]
        else:
            get = ["On your iPhone, save the .mcpack to Files, tap it, then Share > Minecraft. "
                   "Minecraft shows 'Successfully imported'."]
    realm = cfg.get("realm", True)
    if realm:
        apply = ["In Minecraft on that device: Play > Realms > your Realm's pencil (Edit Realm) > "
                 "Behavior Packs > find the pack under 'Available' > Activate. Confirm the upload/restart.",
                 "In the same Edit Realm screen, Game settings: turn on 'Activate Cheats' (needed for /function).",
                 "Join the Realm from your PS5; the pack downloads automatically.",
                 "Updating a build later: import the new .mcpack (its version number goes up), then "
                 "in Behavior Packs deactivate the old one and activate the new one."]
    else:
        apply = ["Edit your world > Behavior Packs > Available > Activate, and turn on cheats."]
    return get + apply


def how_to_text(b, sets, cfg):
    ns = b.name
    lines = [f"{b.title}", "=" * len(b.title), "", "INSTALL"]
    lines += [f"  {i}. {s}" for i, s in enumerate(install_steps(cfg), 1)]
    lines += ["", "BUILD (in game, chat)",
              "  Pick the facing you want the front of the build to look toward:",
              "  north, east, south or west. Then stand on the marker spot "
              "(or use execute positioned X Y Z run ...):",
              f"   1. /function {ns}/<facing>/setup        (loads the site; wait ~5 seconds)",
              f"   2. /function {ns}/<facing>/test_blocks  (optional: one of every block, in front of you)",
              f"   3. /function {ns}/<facing>/build        (every step + entities)",
              f"      or one step at a time: step01_site, step02_..., step03_..., then entities",
              f"   4. /function {ns}/<facing>/cleanup      (test strip, dropped items, ticking area)", ""]
    f0 = FACINGS[0]
    files, meta = sets[f0]
    lines += ["STEPS"] + [f"  {n}" for n in meta["run_order"]]
    return "\n".join(lines) + "\n"
