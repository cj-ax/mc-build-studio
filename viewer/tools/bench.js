// Headless viewer benchmark over a static export (software WebGL, so absolute frame times are slow;
// compare runs on the same machine).
//   node viewer/tools/bench.js out/outport/outport.html [--shots DIR] [--json FILE] [--label NAME]
// Prints: time to ready, draw calls over 5 idle seconds, ms for setStep / setCut / toggle ghost /
// one edit / undo, cut-slider drag rate, triangles per frame, JS heap, HTML size.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const args = process.argv.slice(2);
const file = path.resolve(args[0] || "out/outport/outport.html");
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const at = (opt("--at") || "100,100").split(",").map(Number);
const shotDir = opt("--shots"), jsonOut = opt("--json"), label = opt("--label") || path.basename(file);

// counts every draw call and triangle the page submits to WebGL
const HOOK = () => {
  const C = (window.__gl = { calls: 0, tris: 0 });
  for (const P of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) {
    if (!P) continue;
    const p = P.prototype;
    const wrap = (name, countArg) => {
      const f = p[name];
      if (!f) return;
      p[name] = function (mode, ...a) {
        C.calls++;
        let n = a[countArg];
        if (name.endsWith("Instanced")) n *= a[a.length - 1];
        if (mode === 4) C.tris += n / 3;
        return f.call(this, mode, ...a);
      };
    };
    wrap("drawElements", 0); wrap("drawArrays", 1);
    wrap("drawElementsInstanced", 0); wrap("drawArraysInstanced", 1); wrap("drawRangeElements", 2);
  }
};

(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist", "--enable-precise-memory-info", "--js-flags=--expose-gc"] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  page.setDefaultTimeout(900000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.addInitScript(HOOK);
  const cdp = await page.context().newCDPSession(page);

  const R = { label, html_bytes: fs.statSync(file).size };
  // memory: V8 heap plus array buffer backing stores (typed arrays live there), peak sampled while loading
  const mem = async () => {
    const h = await cdp.send("Runtime.getHeapUsage");
    return (h.usedSize + (h.backingStorageSize || 0)) / 1048576;
  };
  const load = () => page.goto("file://" + file + "?ui=0", { timeout: 900000 }).then(() =>
    page.waitForFunction(() => window.studio && (window.studio.ready || window.studio.error), null, { timeout: 900000, polling: 25 }));
  // 1) peak memory while loading (a heap sampler polls the page, so this load is not timed)
  let peak = 0, loading = true;
  const sampler = (async () => { while (loading) { try { peak = Math.max(peak, await mem()); } catch (e) { } await new Promise((r) => setTimeout(r, 150)); } })();
  await load();
  loading = false;
  await sampler;
  R.peak_load_mb = +Math.max(peak, await mem()).toFixed(1);
  // 2) timed load on a fresh page: ready polled on a timer, not on animation frames
  await page.goto("about:blank");
  await page.waitForTimeout(5000);
  const t0 = Date.now();
  await load();
  R.ready_ms = Date.now() - t0;
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  R.first_frame_ms = Date.now() - t0;
  const err = await page.evaluate(() => window.studio.error);
  if (err) throw new Error(err);
  R.load_parts = await page.evaluate(() => window.studio.perf && window.studio.perf().parts);
  R.mesh_stats = await page.evaluate(() => window.studio.meshStats && window.studio.meshStats());

  const frames = (n) => page.evaluate((n) => new Promise((r) => { let k = 0; const f = () => (++k >= n ? r() : requestAnimationFrame(f)); requestAnimationFrame(f); }), n);
  const settle = async () => { await frames(3); await page.waitForTimeout(300); };
  await page.evaluate(() => { const s = window.studio; s.setTime("day"); s.viewPreset("aerial"); });
  await page.waitForTimeout(1500);

  // idle: nothing moves for 5 s
  await page.evaluate(() => { window.__gl.calls = 0; window.__gl.tris = 0; });
  await page.waitForTimeout(5000);
  R.idle_draw_calls_5s = await page.evaluate(() => window.__gl.calls);

  // one camera-move frame: triangles and draw calls actually submitted
  R.frame = await page.evaluate(() => new Promise((res) => {
    const s = window.studio;
    requestAnimationFrame(() => {
      s.look(-Math.PI * 0.75 + 0.01, -0.58, null);   // turn the camera a hair
      if (s.requestRender) s.requestRender();
      window.__gl.calls = 0; window.__gl.tris = 0;
      const t = performance.now();
      requestAnimationFrame(() => requestAnimationFrame(() => res({ calls: window.__gl.calls, tris: Math.round(window.__gl.tris), ms: performance.now() - t })));
    });
  }));

  // timed operations: JS time of the call itself, then the time until the next frame is on screen
  const timed = (fn) => page.evaluate((src) => new Promise((res) => {
    const s = window.studio;
    const f = new Function("s", src);
    const t = performance.now();
    f(s);
    const call = performance.now() - t;
    const P = s.perf ? s.perf() : {};
    requestAnimationFrame(() => requestAnimationFrame(() => res({ call: +call.toFixed(1), frame: +(performance.now() - t).toFixed(1), parts: P.parts, view: P.view })));
  }), fn);
  const nSteps = await page.evaluate(() => window.studio.S.b.steps.length);
  const yTop = await page.evaluate(() => window.studio.S.bounds.y2);
  const ops = {};
  const run = async (name, src) => { await settle(); ops[name] = await timed(src); };
  await run("setStep (mid)", `s.setStep(${Math.floor(nSteps / 2)})`);
  await run("setStep (all)", `s.setStep(${nSteps})`);
  await run("setCut (y 4)", "s.setCut(4)");
  await run("setCut (all)", `s.setCut(${yTop})`);
  await run("toggle ghost", "s.toggle('ghost')");
  await run("toggle ghost back", "s.toggle('ghost')");
  await run("toggle x-ray", "s.toggle('xray')");
  await run("toggle x-ray back", "s.toggle('xray')");

  // cut slider drag: one input event per frame for 30 frames
  await settle();
  R.cut_drag = await page.evaluate((yTop) => new Promise((res) => {
    const inp = document.querySelector("#cut");
    let k = 0, js = 0;
    const t0 = performance.now();
    const f = () => {
      if (k >= 30) {
        const total = performance.now() - t0;
        return res({ events: k, fps: +(k / (total / 1000)).toFixed(1), js_ms_per_event: +(js / k).toFixed(1) });
      }
      inp.value = String(yTop - (k % 20));
      const t = performance.now();
      inp.dispatchEvent(new Event("input", { bubbles: true }));
      js += performance.now() - t;
      k++;
      requestAnimationFrame(f);
    };
    requestAnimationFrame(f);
  }), yTop);
  await page.evaluate((y) => window.studio.setCut(y), yTop);

  // one edit through the normal pick + place path, then undo
  await settle();
  const pickRes = await page.evaluate((at) => {
    const s = window.studio;
    s.look(0, -Math.PI / 2 + 0.0001, [at[0] + 0.5, 60, at[1] + 0.5]);
    return s.frameNow().then(() => {
      const r = document.querySelector("#gl").getBoundingClientRect();
      const h = s.pickAt(r.left + r.width / 2, r.top + r.height / 2);
      s.setSlot(0, "oak_planks");
      window.__hit = h;
      return h && [h.x, h.y, h.z];
    });
  }, at);
  R.edit_at = pickRes;
  await settle();
  ops["edit (place)"] = await timed("s.place(window.__hit)");
  await settle();
  ops["undo"] = await timed("s.undo()");
  await settle();
  ops["redo"] = await timed("s.redo()");
  await settle();
  ops["undo again"] = await timed("s.undo()");
  // steady state: five more place + undo pairs, median of each
  const pl = [], un = [];
  for (let k = 0; k < 5; k++) {
    await settle(); pl.push(await timed("s.place(window.__hit)"));
    await settle(); un.push(await timed("s.undo()"));
  }
  const med = (a) => { const c = a.map((o) => o.call).sort((x, y) => x - y); const f = a.map((o) => o.frame).sort((x, y) => x - y); return { call: c[2], frame: f[2] }; };
  ops["edit (median of 5)"] = med(pl);
  ops["undo (median of 5)"] = med(un);
  R.ops = ops;

  // heap after a full GC
  await cdp.send("HeapProfiler.collectGarbage");
  const heap = await cdp.send("Runtime.getHeapUsage");
  R.heap_mb = +(heap.usedSize / 1048576).toFixed(1);
  R.heap_with_buffers_mb = +((heap.usedSize + (heap.backingStorageSize || 0)) / 1048576).toFixed(1);

  if (shotDir) {
    fs.mkdirSync(shotDir, { recursive: true });
    const shot = async (n, src) => {
      await page.evaluate(new Function(src));
      await frames(3);
      await page.waitForTimeout(1200);
      await page.screenshot({ path: path.join(shotDir, n + ".png") });
    };
    const reset = `const s = window.studio; s.toggle('ghost', true); s.toggle('xray', false); s.setStep(${nSteps}); s.setCut(${yTop});`;
    await shot("day", reset + "s.setTime('day'); s.viewPreset('aerial');");
    await shot("sunset", reset + "s.setTime('sunset'); s.viewPreset('aerial');");
    await shot("night", reset + "s.setTime('night'); s.viewPreset('aerial');");
    await shot("mid_step_ghosts", reset + `s.setTime('day'); s.setStep(${Math.floor(nSteps / 2)}); s.viewPreset('aerial');`);
    await shot("cutaway", reset + "s.setTime('day'); s.viewPreset('area:pub'); s.setCut(3);");
    await shot("xray_secret", reset + "s.setTime('day'); s.toggle('xray', true); s.viewPreset('area:cellar0');");
    await page.evaluate(() => window.studio.toggle("xray", false));
    const [ex, ey, ez] = pickRes;
    await shot("edit", reset + `s.setTime('day'); s.place(window.__hit); s.look(-0.6, -0.55, [${ex + 6.5}, ${ey + 7}, ${ez + 9.5}]);`);
    await page.evaluate(() => window.studio.undo());
  }
  await browser.close();

  if (errors.length) R.errors = errors.slice(0, 10);
  const row = (k, v) => console.log(k.padEnd(28) + v);
  console.log(`\n${label}`);
  row("HTML size", (R.html_bytes / 1048576).toFixed(2) + " MB");
  row("time to ready", R.ready_ms + " ms");
  row("first frame on screen", R.first_frame_ms + " ms");
  if (args.includes("--parts")) console.log("   load", JSON.stringify(R.load_parts), JSON.stringify(R.mesh_stats));
  row("idle draw calls (5 s)", R.idle_draw_calls_5s);
  row("frame: draw calls", R.frame.calls);
  row("frame: triangles", R.frame.tris.toLocaleString("en-US"));
  row("frame: time on screen", R.frame.ms.toFixed(0) + " ms (software WebGL)");
  for (const [k, v] of Object.entries(ops)) row(k, `${v.call} ms  (next frame ${v.frame} ms)`);
  if (args.includes("--parts")) for (const [k, v] of Object.entries(ops)) console.log("  ", k, JSON.stringify(v.parts), JSON.stringify(v.view));
  row("cut drag", `${R.cut_drag.fps} fps, ${R.cut_drag.js_ms_per_event} ms JS per input`);
  row("JS heap after GC", R.heap_mb + " MB (with typed arrays " + R.heap_with_buffers_mb + " MB)");
  row("peak while loading", R.peak_load_mb + " MB (heap + typed arrays)");
  if (R.errors) console.log("errors:", R.errors);
  if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(R, null, 1));
})().catch((e) => { console.error(e); process.exit(1); });
