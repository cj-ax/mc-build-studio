"""Single self-contained HTML file for one build (three.js, textures, data inline).

    python3 studio.py html cottage   ->  out/cottage/cottage.html

Opens from disk, no server needed. Build and Edit modes work; edits stay in the
page and can be downloaded as an edits JSON.
"""
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "viewer"


def _script(text):
    return "<script>\n" + text.replace("</script", "<\\/script") + "\n</script>"


def export_html(name):
    html = (VIEWER / "index.html").read_text()
    model = json.loads((ROOT / "out" / name / "model.json").read_text())
    palette = json.loads((ROOT / "blocks" / "palette.json").read_text())
    embed = {"palette": palette, "build": model, "world": None, "exported": time.strftime("%Y-%m-%d %H:%M")}
    scripts = [
        _script("window.STUDIO_EMBED = " + json.dumps(embed, separators=(",", ":")) + ";"),
        _script((VIEWER / "vendor" / "three.min.js").read_text()),
        _script((VIEWER / "js" / "textures.js").read_text()),
        _script((VIEWER / "js" / "mesher.js").read_text()),
        _script((VIEWER / "js" / "app.js").read_text()),
    ]
    out = re.sub(r"<!--SCRIPTS-->.*?<!--/SCRIPTS-->", lambda m: "\n".join(scripts), html, flags=re.S)
    out = out.replace("<title>Build Studio</title>", f"<title>{model['title']}</title>")
    path = ROOT / "out" / name / f"{name}.html"
    path.write_text(out)
    return path
