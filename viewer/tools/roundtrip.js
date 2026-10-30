// End-to-end edit test against a running dev server (starts one if STUDIO_URL is unset):
//   place a block through the real pick/place path, check edits/<build>.json, wait for the
//   rebuild, check model.json + the exported function, then place+undo a second block.
// usage: node viewer/tools/roundtrip.js <build> <x> <y> <z> <block>   (places on top of x,y,z)
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");
const ROOT = path.resolve(__dirname, "..", "..");
const [name, X, Y, Z, key] = [process.argv[2], +process.argv[3], +process.argv[4], +process.argv[5], process.argv[6]];
const up = (u) => new Promise((r) => http.get(u, (s) => { s.resume(); r(s.statusCode === 200); }).on("error", () => r(false)));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const editsFile = path.join(ROOT, "edits", name + ".json");
const modelFile = path.join(ROOT, "out", name, "model.json");

(async () => {
  let base = process.env.STUDIO_URL, srv = null;
  if (!base) {
    const port = 8890 + Math.floor(Math.random() * 100);
    base = `http://127.0.0.1:${port}`;
    srv = spawn("python3", [path.join(ROOT, "studio.py"), "serve", "--port", String(port)], { cwd: ROOT, stdio: "ignore" });
    for (let i = 0; i < 120 && !(await up(base + "/api/builds")); i++) await sleep(500);
  }
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  await page.goto(`${base}/?build=${name}&mode=edit`);
  await page.waitForFunction(() => window.studio && window.studio.ready, null, { timeout: 120000 });
  const before = fs.existsSync(modelFile) ? fs.statSync(modelFile).mtimeMs : 0;

  // look straight down at the target block and place through the normal click path
  const placeOn = async (x, y, z, block) => page.evaluate(([x, y, z, block]) => {
    const s = window.studio;
    s.look(0, -Math.PI / 2 + 0.0001, [x + 0.5, y + 4, z + 0.5]);
    return s.frameNow().then(() => {
      const r = document.querySelector("#gl").getBoundingClientRect();
      const h = s.pickAt(r.left + r.width / 2, r.top + r.height / 2);
      if (!h || h.x !== x || h.y !== y || h.z !== z) return { error: "pick missed", h };
      s.setSlot(0, block);
      s.place(h);
      return { ok: true, h };
    });
  }, [x, y, z, block]);

  const r1 = await placeOn(X, Y, Z, key);
  console.log("place:", JSON.stringify(r1));
  await sleep(1500);
  const ed = JSON.parse(fs.readFileSync(editsFile, "utf8"));
  const put = ed.put.find((e) => e.pos.join() === [X, Y + 1, Z].join() && e.block === key);
  console.log("edits file has it:", !!put, put ? JSON.stringify(put) : "");
  for (let i = 0; i < 60 && (!fs.existsSync(modelFile) || fs.statSync(modelFile).mtimeMs === before); i++) await sleep(500);
  await sleep(500);
  const m = JSON.parse(fs.readFileSync(modelFile, "utf8"));
  let inModel = false, vi = -1;
  for (let i = 0; i < m.cells.length; i += 6)
    if (m.cells[i] === X && m.cells[i + 1] === Y + 1 && m.cells[i + 2] === Z && m.variants[m.cells[i + 3]][0] === key) { inModel = true; vi = m.cells[i + 3]; }
  console.log("rebuilt model has it:", inModel, "| edits merged:", JSON.stringify(m.edits), "| errors:", m.checks.filter((c) => c.level === "error").length);
  const f = m.world && m.world.facing || "north";
  const relx = X - m.marker[0], rely = Y + 1 - m.marker[1], relz = Z - m.marker[2];
  const cmds = JSON.parse(fs.readFileSync(path.join(ROOT, "out", name, "commands.json"), "utf8"));
  const allLines = Object.values(cmds.north).flat();
  console.log("north function places it:", allLines.some((l) => l.includes(`~${relx} ~${rely} ~${relz}`)));

  // second block: place, then undo -> must vanish from the edits file
  const r2 = await placeOn(X, Y + 1, Z, "torch");
  await sleep(800);
  const mid = JSON.parse(fs.readFileSync(editsFile, "utf8")).put.length;
  await page.evaluate(() => window.studio.undo());
  await sleep(1200);
  const after = JSON.parse(fs.readFileSync(editsFile, "utf8")).put.length;
  console.log("undo:", r2.ok ? `puts ${mid} -> ${after}` : JSON.stringify(r2));
  await page.screenshot({ path: path.join(ROOT, "out", name, "shots", "edit_mode.png") });
  if (errs.length) console.log("page errors:", errs);
  await browser.close();
  if (srv) srv.kill();
})().catch((e) => { console.error(e); process.exit(1); });
