"""Single self-contained HTML file for one build (three.js, textures, data inline).

    python3 studio.py html cottage   ->  out/cottage/cottage.html

Opens from disk, no server needed. Build and Edit modes work; edits stay in the
page and can be downloaded as an edits JSON.
"""
import base64
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "viewer"


def _script(text):
    return "<script>\n" + text.replace("</script", "<\\/script") + "\n</script>"


def _fonts_css():
    """vendor/fonts.css with every woff2 inlined as a data URI."""
    css = (VIEWER / "vendor" / "fonts.css").read_text()

    def inline(m):
        data = base64.b64encode((VIEWER / "vendor" / m.group(1)).read_bytes()).decode()
        return f"url(data:font/woff2;base64,{data})"
    return re.sub(r"url\((fonts/[^)]+)\)", inline, css)


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
    out = re.sub(r"<!--FONTS-->.*?<!--/FONTS-->", lambda m: "<style>\n" + _fonts_css() + "</style>", out, flags=re.S)
    out = out.replace("<title>Build Studio</title>", f"<title>{model['title']}</title>")
    path = ROOT / "out" / name / f"{name}.html"
    path.write_text(out)
    return path
