"""Dev server: serves the viewer, saves edits, rebuilds on change, pushes live reloads.

    python3 studio.py serve            # http://localhost:8765

Watches builds/, lib/, blocks/, export/, edits/ and world/world.json. A change
rebuilds the affected builds (in a fresh interpreter) and every open viewer
reloads. Build output written by `studio.py build` from a terminal also reloads.
"""
import json
import mimetypes
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "viewer"
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT))

from lib import build as B  # noqa: E402

mimetypes.add_type("font/woff2", ".woff2")

clients = []
clients_lock = threading.Lock()
rebuild_lock = threading.Lock()


def broadcast(ev):
    data = json.dumps(ev)
    with clients_lock:
        for q in list(clients):
            q.put(data)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def file(self, path):
        path = path.resolve()
        if not path.is_file() or ROOT not in path.parents:
            return self.send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send(200, path.read_bytes(), ctype)

    def do_GET(self):
        u = urlparse(self.path).path
        if u in ("/", "/index.html"):
            return self.file(VIEWER / "index.html")
        if u.startswith("/js/") or u.startswith("/vendor/"):
            return self.file(VIEWER / u.lstrip("/"))
        if u == "/blocks/palette.json":
            return self.file(ROOT / "blocks" / "palette.json")
        if u.startswith("/out/"):
            return self.file(OUT / u[5:])
        if u == "/api/builds":
            return self.send(200, B.names())
        if u.startswith("/api/edits/"):
            return self.send(200, B.read_edits(u.rsplit("/", 1)[-1]))
        if u == "/api/events":
            return self.events()
        self.send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path).path
        if u.startswith("/api/edits/"):
            name = u.rsplit("/", 1)[-1]
            if name not in B.names():
                return self.send(404, {"error": "no such build"})
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            saved = B.write_edits(name, data)
            broadcast({"type": "status", "text": f"edits saved ({len(saved['put'])} placed, {len(saved['remove'])} removed)"})
            return self.send(200, {"ok": True, "put": len(saved["put"]), "remove": len(saved["remove"])})
        self.send(404, {"error": "not found"})

    def events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        q = queue.Queue()
        with clients_lock:
            clients.append(q)
        try:
            self.wfile.write(b'data: {"type":"status","text":"live"}\n\n')
            self.wfile.flush()
            while True:
                try:
                    data = q.get(timeout=15)
                    self.wfile.write(f"data: {data}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with clients_lock:
                clients.remove(q)


# ---------------------------------------------------------------- watching
def snapshot():
    files = {}
    pats = [("builds", "**/*.py"), ("lib", "*.py"), ("blocks", "*.py"), ("export", "*.py"),
            ("edits", "*.json"), ("world", "world.json"), ("out", "*/model.json")]
    for d, pat in pats:
        for p in (ROOT / d).glob(pat):
            try:
                files[p] = p.stat().st_mtime
            except OSError:
                pass
    return files


def affected(changed):
    builds, world, outputs, everything = set(), False, set(), False
    for p in changed:
        rel = p.relative_to(ROOT).parts
        if rel[0] == "builds":
            builds.add(rel[1])
        elif rel[0] == "edits":
            builds.add(p.stem)
        elif rel[0] == "world":
            world = True
        elif rel[0] == "out":
            outputs.add(rel[1])
        else:
            everything = True
    if everything:
        builds = set(B.names())
    return builds & set(B.names()), world, outputs


def rebuild(names, world):
    with rebuild_lock:
        ok = True
        for n in sorted(names):
            broadcast({"type": "status", "text": f"rebuilding {n}…"})
            r = subprocess.run([sys.executable, str(ROOT / "studio.py"), "build", n], cwd=ROOT,
                               capture_output=True, text=True)
            print(r.stdout.strip() or r.stderr.strip()[-2000:])
            ok = ok and r.returncode == 0
        if names or world:
            r = subprocess.run([sys.executable, str(ROOT / "studio.py"), "world"], cwd=ROOT, capture_output=True, text=True)
            print(r.stdout.strip() or r.stderr.strip()[-2000:])
        return ok


def watch():
    seen = snapshot()
    while True:
        time.sleep(0.5)
        now = snapshot()
        changed = [p for p, t in now.items() if seen.get(p) != t] + [p for p in seen if p not in now]
        if not changed:
            continue
        time.sleep(0.3)                      # let editors finish writing
        builds, world, outputs = affected(changed)
        ok = rebuild(builds, world) if (builds or world) else True
        seen = snapshot()
        names = sorted(builds | outputs)
        broadcast({"type": "rebuilt", "names": names, "world": world or bool(names), "ok": ok})


def serve(port=None):
    cfg = json.loads((ROOT / "config.json").read_text()) if (ROOT / "config.json").exists() else {}
    port = port or cfg.get("port", 8765)
    print("building everything first…")
    rebuild(set(B.names()), True)
    threading.Thread(target=watch, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    srv.daemon_threads = True
    print(f"Build Studio viewer: http://localhost:{port}/   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else None)
