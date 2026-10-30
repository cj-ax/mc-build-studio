"""Single self-contained HTML file for one build (three.js, textures, data inline).

    python3 studio.py html cottage   ->  out/cottage/cottage.html

Opens from disk, no server needed. Build and Edit modes work; edits stay in the
page and can be downloaded as an edits JSON.

Everything heavy is gzip + base64 and inflated in the page with DecompressionStream:
the model (cells as run-length rows of int32 columns), the scripts, and the command
text per facing (inflated only when the Commands tab opens).
"""
import base64
import gzip
import json
import re
import struct
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "viewer"

LOADER = """<script>
(async () => {
  const E = window.STUDIO_EMBED;
  const text = async (b64) => {
    const bin = atob(b64), u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  };
  try {
    for (const [name, b64] of E.scripts) (0, eval)((await text(b64)) + "\\n//# sourceURL=" + name);
  } catch (e) {
    document.getElementById("status").textContent = "error: " + e.message;
    window.studio = { error: String(e && e.stack || e) };
  }
})();
</script>"""


def _z(data):
    if isinstance(data, str):
        data = data.encode()
    return base64.b64encode(gzip.compress(data, 9, mtime=0)).decode()


def _fonts_css():
    """vendor/fonts.css with every woff2 inlined as a data URI."""
    css = (VIEWER / "vendor" / "fonts.css").read_text()

    def inline(m):
        data = base64.b64encode((VIEWER / "vendor" / m.group(1)).read_bytes()).decode()
        return f"url(data:font/woff2;base64,{data})"
    return re.sub(r"url\((fonts/[^)]+)\)", inline, css)


def encode_cells(flat):
    """[x, y, z, variant, step, group] * n (sorted by y, z, x) -> runs along x as int32 columns:
    count, then x, dy, dz, length, variant, step, dgroup (y, z and group delta-coded)."""
    runs = []
    i, n = 0, len(flat)
    while i < n:
        x, y, z, v, s, g = flat[i:i + 6]
        ln = 1
        while i + 6 * ln < n:
            j = i + 6 * ln
            if flat[j:j + 6] != [x + ln, y, z, v, s, g]:
                break
            ln += 1
        runs.append((x, y, z, ln, v, s, g))
        i += 6 * ln
    cols = [[] for _ in range(7)]
    py = pz = pg = 0
    for x, y, z, ln, v, s, g in runs:
        for c, val in zip(cols, (x, y - py, z - pz, ln, v, s, g - pg)):
            c.append(val)
        py, pz, pg = y, z, g
    out = [len(runs)] + [val for c in cols for val in c]
    return struct.pack(f"<{len(out)}i", *out)


def export_html(name):
    html = (VIEWER / "index.html").read_text()
    model = json.loads((ROOT / "out" / name / "model.json").read_text())
    commands = json.loads((ROOT / "out" / name / "commands.json").read_text())
    palette = json.loads((ROOT / "blocks" / "palette.json").read_text())
    cells = model.pop("cells")
    data = {"palette": palette, "build": model}
    embed = {
        "name": model["name"],
        "exported": time.strftime("%Y-%m-%d %H:%M"),
        "data": _z(json.dumps(data, separators=(",", ":"))),
        "cells": base64.b64encode(gzip.compress(encode_cells(cells), 9, mtime=0)).decode(),
        "commands": {f: _z(json.dumps(files, separators=(",", ":"))) for f, files in commands.items()},
        "scripts": [[n, _z(p.read_text())] for n, p in (
            ("three.min.js", VIEWER / "vendor" / "three.min.js"), ("textures.js", VIEWER / "js" / "textures.js"),
            ("mesher.js", VIEWER / "js" / "mesher.js"), ("app.js", VIEWER / "js" / "app.js"))],
    }
    scripts = "<script>window.STUDIO_EMBED = " + json.dumps(embed, separators=(",", ":")) + ";</script>\n" + LOADER
    out = re.sub(r"<!--SCRIPTS-->.*?<!--/SCRIPTS-->", lambda m: scripts, html, flags=re.S)
    out = re.sub(r"<!--FONTS-->.*?<!--/FONTS-->", lambda m: "<style>\n" + _fonts_css() + "</style>", out, flags=re.S)
    out = out.replace("<title>Build Studio</title>", f"<title>{model['title']}</title>")
    path = ROOT / "out" / name / f"{name}.html"
    path.write_text(out)
    return path
