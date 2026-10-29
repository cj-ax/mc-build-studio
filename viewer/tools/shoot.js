// Headless screenshots of the viewer: node viewer/tools/shoot.js <build> [view ...]
// Views: overview front back left right top rear night sunset world area:<key> ... (default: a full set)
// Starts its own dev server on a spare port unless STUDIO_URL is set. Writes out/<build>/shots/*.png
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

const ROOT = path.resolve(__dirname, "..", "..");
const name = process.argv[2];
if (!name) { console.error("usage: node viewer/tools/shoot.js <build> [views...]"); process.exit(2); }
const model = JSON.parse(fs.readFileSync(path.join(ROOT, "out", name, "model.json"), "utf8"));
let views = process.argv.slice(3);
if (!views.length) views = ["ui", "approach", "aerial", "front", "back", "plan", "night", "sunset", "world",
  ...model.areas.filter((a) => !a.ring).map((a) => "area:" + a.key)];
const outDir = path.join(ROOT, "out", name, "shots");
fs.mkdirSync(outDir, { recursive: true });

function up(url) {
  return new Promise((res) => http.get(url, (r) => { r.resume(); res(r.statusCode === 200); }).on("error", () => res(false)));
}

(async () => {
  let base = process.env.STUDIO_URL, srv = null;
  if (!base) {
    const port = 8790 + Math.floor(Math.random() * 100);
    base = `http://127.0.0.1:${port}`;
    srv = spawn("python3", [path.join(ROOT, "studio.py"), "serve", "--port", String(port)], { cwd: ROOT, stdio: "ignore" });
    for (let i = 0; i < 120 && !(await up(base + "/api/builds")); i++) await new Promise((r) => setTimeout(r, 500));
  }
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.setDefaultTimeout(600000);          // big builds take a while in software WebGL
  page.setDefaultNavigationTimeout(600000);
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  const open = async (q) => {
    await page.goto(`${base}/?${q}`);
    await page.waitForFunction(() => window.studio && (window.studio.ready || window.studio.error), null, { timeout: 600000 });
    const err = await page.evaluate(() => window.studio.error);
    if (err) throw new Error(err);
  };
  await open(`build=${name}&mode=build&ui=0`);
  for (const v of views) {
    if (v === "world") {
      await open(`mode=world&ui=0`);
      await page.evaluate((n) => window.studio.viewPreset("build:" + n), name);
    } else if (v === "ui") {
      await open(`build=${name}&mode=build`);
      await page.evaluate(() => { window.studio.setTime("day"); window.studio.viewPreset("aerial"); });
    } else {
      if (!page.url().includes("ui=0") || page.url().includes("mode=world")) await open(`build=${name}&mode=build&ui=0`);
      await page.evaluate((v) => {
        const s = window.studio;
        s.setTime(v === "night" ? "night" : v === "sunset" ? "sunset" : "day");
        s.viewPreset(v === "night" || v === "sunset" ? "aerial" : v);
      }, v);
    }
    await page.waitForTimeout(700);
    const file = path.join(outDir, v.replace(":", "_") + ".png");
    await page.screenshot({ path: file });
    console.log("shot", path.relative(ROOT, file));
  }
  if (errors.length) console.log("console errors:\n  " + errors.slice(0, 10).join("\n  "));
  await browser.close();
  if (srv) srv.kill();
})().catch((e) => { console.error(e); process.exit(1); });
