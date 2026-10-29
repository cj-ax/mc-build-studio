"""Top-down plan maps (PNG): area layout, roof-down view, and the shared world."""
from PIL import Image, ImageDraw, ImageFont

from lib.build import area_cells
from lib.palette import block

AREA_COLORS = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0",
               "#f032e6", "#bcf60c", "#008080", "#9a6324", "#800000"]


def _font(size=12):
    for f in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _rgb(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def build_plan(b, path, top_view=False, checks=None, s=16):
    """Areas (or the top-most block colours) on the footprint grid, with collisions in red."""
    W, D = b.footprint
    mx, my, mz = b.marker
    xs = [0, W - 1, mx] + [p[0] for p in b.model.cells]
    zs = [0, D - 1, mz] + [p[2] for p in b.model.cells]
    x0, x1, z0, z1 = min(xs) - 2, max(xs) + 2, min(zs) - 2, max(zs) + 2
    pad = 40
    img = Image.new("RGBA", ((x1 - x0 + 1) * s + pad * 2, (z1 - z0 + 1) * s + pad * 2 + 60), "#20242a")
    dr = ImageDraw.Draw(img, "RGBA")
    f = _font(11)

    def R(x, z, x2=None, z2=None):
        x2 = x if x2 is None else x2
        z2 = z if z2 is None else z2
        return (pad + (x - x0) * s, pad + (z - z0) * s, pad + (x2 - x0 + 1) * s - 1, pad + (z2 - z0 + 1) * s - 1)

    # grass + footprint
    dr.rectangle(R(x0, z0, x1, z1), fill="#4d6b34")
    dr.rectangle(R(0, 0, W - 1, D - 1), fill="#5f8a3e")
    if top_view:
        tops = {}
        for (x, y, z), c in b.model.cells.items():
            if c.key == "air":
                continue
            if (x, z) not in tops or y > tops[(x, z)][0]:
                tops[(x, z)] = (y, c.key)
        for (x, z), (y, key) in tops.items():
            r, g, bb, _ = _rgb(block(key)["color"])
            k = 0.75 + 0.25 * min(1, max(0, (y + 1) / 12))
            dr.rectangle(R(x, z), fill=(int(r * k), int(g * k), int(bb * k), 255))
    def keep_layer():
        for k in b.keep_zones:
            x1k, z1k, x2k, z2k = k["box"]
            a = R(x1k, z1k, x2k, z2k)
            w, h = a[2] - a[0] + 1, a[3] - a[1] + 1
            tile = Image.new("RGBA", (w, h), (60, 110, 220, 170) if k["what"] == "water" else (120, 120, 120, 170))
            td = ImageDraw.Draw(tile)
            for i in range(-h, w, 8):
                td.line((i, h, i + h, 0), fill=(255, 255, 255, 90), width=2)
            img.alpha_composite(tile, (a[0], a[1]))
            dr.rectangle(a, outline="#9fc3ff", width=2)
            dr.text((a[0] + 3, a[3] - 14), "KEEP: " + (k["note"] or k["what"]), fill="white", font=f,
                    stroke_width=2, stroke_fill="black")

    # grid
    for x in range(x0, x1 + 2):
        X = pad + (x - x0) * s
        dr.line((X, pad, X, pad + (z1 - z0 + 1) * s), fill=(0, 0, 0, 90 if (x - mx) % 5 else 170))
    for z in range(z0, z1 + 2):
        Z = pad + (z - z0) * s
        dr.line((pad, Z, pad + (x1 - x0 + 1) * s, Z), fill=(0, 0, 0, 90 if (z - mz) % 5 else 170))
    # areas
    acells = [area_cells(a) for a in b.areas]
    for i, a in enumerate(b.areas):
        c = _rgb(AREA_COLORS[i % len(AREA_COLORS)])
        ax1, az1, ax2, az2 = a["box"]
        if not top_view:
            for (x, z) in acells[i]:
                dr.rectangle(R(x, z), fill=c[:3] + (90,))
        dr.rectangle(R(ax1, az1, ax2, az2), outline=c[:3] + (255,), width=2)
        tx, ty = R(ax1, az1)[:2]
        if not a.get("ring"):
            dr.text((tx + 3, ty + 3), a["title"], fill="white", font=_font(12), stroke_width=2, stroke_fill="black")
    # collisions
    for i in range(len(b.areas)):
        for j in range(i + 1, len(b.areas)):
            for (x, z) in acells[i] & acells[j]:
                dr.rectangle(R(x, z), fill=(255, 0, 0, 200), outline="red")
    keep_layer()
    for (x, y, z), c in b.model.cells.items():
        if not (0 <= x < W and 0 <= z < D):
            dr.rectangle(R(x, z), fill=(255, 0, 0, 200))
    dr.rectangle(R(0, 0, W - 1, D - 1), outline="white", width=2)
    # marker + compass
    mxr = R(mx, mz)
    dr.ellipse((mxr[0] + 2, mxr[1] + 2, mxr[2] - 2, mxr[3] - 2), fill="#ffcc00", outline="black")
    dr.text((mxr[2] + 3, mxr[1]), "marker (0,0,0)", fill="#ffcc00", font=f, stroke_width=2, stroke_fill="black")
    dr.text((pad, 8), f"{b.title}  -  {W}x{D} footprint, front faces north (up)", fill="white", font=_font(14))
    for x in range(x0, x1 + 1):
        if (x - mx) % 5 == 0:
            dr.text((pad + (x - x0) * s + 2, pad - 14), str(x - mx), fill="#cccccc", font=f)
    for z in range(z0, z1 + 1):
        if (z - mz) % 5 == 0:
            dr.text((4, pad + (z - z0) * s + 2), str(z - mz), fill="#cccccc", font=f)
    y = img.height - 50
    errs = [c for c in (checks or []) if c["level"] == "error" and c["check"] in ("areas", "footprint", "keep-zone")]
    dr.text((pad, y), ("COLLISIONS: " + "; ".join(e["msg"] for e in errs)) if errs else "No area collisions.",
            fill="#ff6060" if errs else "#90ee90", font=_font(13))
    img.save(path)
    return path


def world_plan(world, path, s=4):
    t = world["terrain"]
    x1, z1, x2, z2 = t["bounds"]
    pad = 30
    img = Image.new("RGBA", ((x2 - x1 + 1) * s + pad * 2, (z2 - z1 + 1) * s + pad * 2 + 30), "#20242a")
    dr = ImageDraw.Draw(img, "RGBA")

    def R(a, b, c, d):
        return (pad + (a - x1) * s, pad + (b - z1) * s, pad + (c - x1 + 1) * s - 1, pad + (d - z1 + 1) * s - 1)

    dr.rectangle(R(x1, z1, x2, z2), fill="#5f8a3e")
    for w in t.get("water", []):
        dr.rectangle(R(*w["rect"]), fill="#3f76e4")
    for i, bld in enumerate(world["builds"]):
        c = _rgb(AREA_COLORS[i % len(AREA_COLORS)])
        dr.rectangle(R(*bld["rect"]), fill=c[:3] + (110,), outline=c[:3] + (255,), width=2)
        dr.text((R(*bld["rect"])[0] + 3, R(*bld["rect"])[1] + 3), f"{bld['title']} ({bld['facing']})",
                fill="white", font=_font(12), stroke_width=2, stroke_fill="black")
        ox, _, oz = bld["origin"]
        dr.ellipse((pad + (ox - x1) * s - 3, pad + (oz - z1) * s - 3, pad + (ox - x1) * s + 3, pad + (oz - z1) * s + 3),
                   fill="#ffcc00")
    for e in world.get("problems", []):
        if "rect" in e:
            dr.rectangle(R(*e["rect"]), fill=(255, 0, 0, 160), outline="red", width=2)
    dr.text((pad, img.height - 24), "; ".join(e["msg"] for e in world.get("problems", [])) or "No build collisions.",
            fill="#ff6060" if world.get("problems") else "#90ee90", font=_font(13))
    img.save(path)
    return path


def icon(b, path, size=128):
    """Pack icon: roof-down view of the build."""
    W, D = b.footprint
    tops = {}
    for (x, y, z), c in b.model.cells.items():
        if c.key != "air" and ((x, z) not in tops or y > tops[(x, z)][0]):
            tops[(x, z)] = (y, c.key)
    n = max(W, D)
    s = max(1, size // n)
    img = Image.new("RGBA", (size, size), "#5f8a3e")
    dr = ImageDraw.Draw(img)
    ox, oz = (size - W * s) // 2, (size - D * s) // 2
    for (x, z), (y, key) in tops.items():
        if 0 <= x < W and 0 <= z < D:
            dr.rectangle((ox + x * s, oz + z * s, ox + x * s + s - 1, oz + z * s + s - 1), fill=_rgb(block(key)["color"]))
    img.save(path)
    return path
