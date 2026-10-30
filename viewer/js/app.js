// Build Studio viewer, "build book" layout: world mode, build mode (steps, named cut-away,
// layers, inventory, commands, setup, areas, secrets, checks) and edit mode (place/break,
// undo, saved to edits/). Lit with a shadowing sun, sky environment light, haze and baked
// voxel light (sky/block light + ambient occlusion).
(function () {
  const MC = window.MC;
  const EMBED = window.STUDIO_EMBED || null;      // set by the static single-file export
  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (k === "html") e.innerHTML = v;
      else e.setAttribute(k, v);
    }
    for (const k of kids) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(k));
    return e;
  };
  const FACINGS = ["north", "east", "south", "west"];
  const rotXZ = (x, z, t) => { for (let i = 0; i < ((t % 4) + 4) % 4; i++) [x, z] = [-z, x]; return [x, z]; };
  const pad2 = (n) => String(n).padStart(2, "0");
  const fmt = (n) => Number(n).toLocaleString("en-US");
  const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"];
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  // light presets. sun direction: elevation / azimuth in degrees (azimuth from north, clockwise)
  const TIMES = {
    day: { el: 50, az: 292, sun: 0xfff0dc, sunI: 2.3, sky: 0xcfe2f4, ground: 0x8c7d62, hemiI: 0.5, env: 0.55, block: 0xffc27a, blockI: 0.6,
      top: 0x5b98de, horizon: 0xd3e4ef, fog: 0xcfe0ea, exposure: 0.95, disc: 0xfff6d8 },
    sunset: { el: 9, az: 255, sun: 0xffa463, sunI: 2.4, sky: 0xf1c3a0, ground: 0x5a4436, hemiI: 0.4, env: 0.45, block: 0xffb766, blockI: 1.2,
      top: 0x4a5f9e, horizon: 0xf5ae7f, fog: 0xecc0a0, exposure: 1.0, disc: 0xffc68a },
    night: { el: 40, az: 200, sun: 0x9db4ff, sunI: 0.3, sky: 0x24345c, ground: 0x0b0c10, hemiI: 0.28, env: 0.16, block: 0xffae55, blockI: 2.4,
      top: 0x03050d, horizon: 0x13204a, fog: 0x0f1a34, exposure: 1.1, disc: 0xdfe6ff, stars: true },
  };

  const S = {
    mode: "world", time: "day", step: 0, cut: 99, facing: "north",
    ghost: true, xray: false, labels: true, tab: null,
    cells: new Map(), edits: { put: new Map(), remove: new Set() }, undo: [], redo: [],
    hotbar: ["oak_planks", "cobblestone", "spruce_stairs", "spruce_slab", "glass_pane", "lantern", "oak_fence", "poppy", "torch"],
    slot: 0, rot: 0, measure: { on: false, a: null, b: null }, hover: null, keys: new Set(), speed: 12,
    yaw: -Math.PI * 0.75, pitch: -0.45, pos: new THREE.Vector3(0, 20, 0), ready: false,
  };
  window.studio = { S, ready: false };

  // ---------------------------------------------------------------- data
  const api = {
    async json(url) {
      const r = await fetch(url, { cache: "no-store" });
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    },
    palette() { return EMBED ? EMBED.palette : api.json("/blocks/palette.json"); },
    world() { return EMBED ? EMBED.world : api.json("/out/world.json"); },
    builds() { return EMBED ? [EMBED.build.name] : api.json("/api/builds"); },
    build(name) { return EMBED ? EMBED.build : api.json(`/out/${name}/model.json`); },
    async saveEdits(name, data) {
      if (EMBED) return;
      const r = await fetch(`/api/edits/${name}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      if (!r.ok) throw new Error("save failed " + r.status);
      return r.json();
    },
    editsFile(name) { return EMBED ? Promise.resolve({ put: [], remove: [] }) : api.json(`/api/edits/${name}`); },
  };

  // ---------------------------------------------------------------- renderer
  const canvas = $("#gl");
  const stage = $("#stage");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0xd9e6ec, 100, 600);
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 3000);
  camera.rotation.order = "YXZ";
  const atlas = new MC.Atlas();
  let pal = null;

  const hemi = new THREE.HemisphereLight(0xcfe2f4, 0x8c7d62, 0.5);
  const sun = new THREE.DirectionalLight(0xffffff, 2.6);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  sun.shadow.bias = -0.0003;
  sun.shadow.normalBias = 0.035;
  scene.add(hemi, sun, sun.target);

  // voxel material: standard PBR lighting x baked sky occlusion / AO, plus block light and step highlight
  const U = {
    uBlock: { value: new THREE.Color(0xffc27a) }, uBlockStr: { value: 0.5 }, uIndoor: { value: 0.22 },
    uTime: { value: 0 }, uHl: { value: new THREE.Color(0xe08a4c) },
  };
  function voxelMat(params) {
    const m = new THREE.MeshStandardMaterial(Object.assign({ roughness: 0.93, metalness: 0 }, params));
    m.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, U);
      sh.vertexShader = sh.vertexShader
        .replace("#include <common>", "#include <common>\nattribute vec3 light; attribute float hl; varying vec3 vVox; varying float vHl;")
        .replace("#include <begin_vertex>", "#include <begin_vertex>\nvVox = light; vHl = hl;");
      sh.fragmentShader = sh.fragmentShader
        .replace("#include <common>", "#include <common>\nuniform vec3 uBlock; uniform float uBlockStr; uniform float uIndoor; uniform float uTime; uniform vec3 uHl; varying vec3 vVox; varying float vHl;")
        .replace("#include <opaque_fragment>", `
          float skyL = clamp(vVox.x, 0.0, 1.0), blkL = clamp(vVox.y, 0.0, 1.0);
          outgoingLight *= vVox.z * mix(uIndoor, 1.0, smoothstep(0.05, 0.85, skyL));
          outgoingLight += diffuseColor.rgb * uBlock * uBlockStr * blkL * blkL * blkL * blkL * vVox.z;
          if (vHl > 0.5) {
            float pulse = 0.5 + 0.5 * sin(uTime * 3.0);
            outgoingLight = mix(outgoingLight, uHl * (0.75 + 0.35 * pulse), 0.38) + uHl * 0.06;
          }
          #include <opaque_fragment>`);
    };
    return m;
  }
  const solidMat = voxelMat({ map: atlas.three(), alphaTest: 0.5 });
  const waterMat = voxelMat({ color: 0x2f93c8, transparent: true, opacity: 0.7, roughness: 0.08, depthWrite: false, envMapIntensity: 0.9 });
  const ghostMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.17, depthWrite: false, fog: false });
  const xrayMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.22, depthWrite: false });
  const beamMat = new THREE.MeshBasicMaterial({ color: 0xd8fbff, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending,
    depthWrite: false, fog: false, toneMapped: false });

  // build root: rotates the build about its marker for the chosen facing
  const root = new THREE.Group();
  const inner = new THREE.Group();
  root.add(inner);
  scene.add(root);
  const meshes = { solid: null, water: null, ghost: null, xray: null };
  const beams = new THREE.Group();
  inner.add(beams);
  function setRoot(turns, pivot) {
    root.position.set(pivot[0], 0, pivot[1]);
    inner.position.set(-pivot[0], 0, -pivot[1]);
    root.rotation.y = -turns * Math.PI / 2;
    root.updateMatrixWorld(true);
    S.turns = turns;
  }
  const toWorld = (x, y, z) => inner.localToWorld(new THREE.Vector3(x, y, z));
  function localRay(o, d) {
    inner.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(inner.matrixWorld).invert();
    return { o: o.clone().applyMatrix4(inv), d: d.clone().transformDirection(inv) };
  }

  // hover outline, measure line, area box, marker, check marks
  const outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.004, 1.004, 1.004)),
    new THREE.LineBasicMaterial({ color: 0x0a1a1f, transparent: true, opacity: 0.85 }));
  outline.visible = false;
  const measureLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: 0x3fd1ae, depthTest: false }));
  measureLine.visible = false;
  measureLine.renderOrder = 10;
  const areaBox = new THREE.Box3Helper(new THREE.Box3(), 0x3fd1ae);
  areaBox.visible = false;
  const markerMesh = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.06, 0.6), new THREE.MeshBasicMaterial({ color: 0xffcc33 }));
  const checkMarks = new THREE.Group();
  inner.add(outline, measureLine, areaBox, markerMesh, checkMarks);

  // sky: gradient dome, sun/moon disc, stars (all follow the camera); same dome lights the environment map
  function makeDome(r) {
    const g = new THREE.SphereGeometry(r, 32, 16);
    g.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 3), 3));
    const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, depthWrite: false, fog: false }));
    m.userData.r = r;
    return m;
  }
  function paintDome(d, top, horizon) {
    const a = new THREE.Color(top), b = new THREE.Color(horizon), c = new THREE.Color();
    const pos = d.geometry.attributes.position, col = d.geometry.attributes.color;
    for (let i = 0; i < pos.count; i++) {
      const t = Math.max(0, Math.min(1, pos.getY(i) / d.userData.r));
      c.copy(b).lerp(a, Math.pow(t, 0.42));
      if (pos.getY(i) < 0) c.copy(b).lerp(a, 0.25);
      col.setXYZ(i, c.r, c.g, c.b);
    }
    col.needsUpdate = true;
  }
  const dome = makeDome(1400);
  dome.renderOrder = -10;
  const disc = new THREE.Mesh(new THREE.CircleGeometry(38, 32), new THREE.MeshBasicMaterial({ color: 0xfff6d8, fog: false, toneMapped: false }));
  const starGeo = new THREE.BufferGeometry();
  {
    const p = [];
    let r = 12345;
    const rnd = () => ((r = (r * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    for (let i = 0; i < 1200; i++) {
      const th = rnd() * Math.PI * 2, ph = Math.acos(rnd() * 0.95);
      p.push(Math.sin(ph) * Math.cos(th) * 1300, Math.cos(ph) * 1300, Math.sin(ph) * Math.sin(th) * 1300);
    }
    starGeo.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  }
  const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 2, sizeAttenuation: false, fog: false }));
  const sky = new THREE.Group();
  sky.add(dome, disc, stars);
  scene.add(sky);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envScene = new THREE.Scene();
  const envDome = makeDome(50);
  const envSun = new THREE.Mesh(new THREE.SphereGeometry(3, 16, 8), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  envScene.add(envDome, envSun);
  let envRT = null;

  function sunDir(T) {
    const e = (T.el * Math.PI) / 180, a = (T.az * Math.PI) / 180;
    return new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e));
  }
  function setTime(t) {
    S.time = t;
    const T = TIMES[t];
    paintDome(dome, T.top, T.horizon);
    paintDome(envDome, T.top, T.horizon);
    envSun.material.color.set(T.disc).multiplyScalar(t === "night" ? 0.3 : 6);
    envSun.position.copy(sunDir(T)).multiplyScalar(40);
    if (envRT) envRT.dispose();
    envRT = pmrem.fromScene(envScene, 0.035);
    scene.environment = envRT.texture;
    scene.background = new THREE.Color(T.horizon);
    scene.fog.color.set(T.fog);
    hemi.color.set(T.sky); hemi.groundColor.set(T.ground); hemi.intensity = T.hemiI;
    sun.color.set(T.sun); sun.intensity = T.sunI;
    solidMat.envMapIntensity = T.env;
    U.uBlock.value.set(T.block); U.uBlockStr.value = T.blockI;
    renderer.toneMappingExposure = T.exposure;
    disc.material.color.set(T.disc);
    stars.visible = !!T.stars;
    fitShadow();
    document.querySelectorAll("#times button").forEach((b) => b.classList.toggle("on", b.dataset.time === t));
  }

  let shadowBox = null;   // world-space [min, max]
  function fitShadow(box) {
    if (box) shadowBox = box;
    if (!shadowBox) return;
    const [mn, mx] = shadowBox;
    const c = new THREE.Vector3((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, (mn.z + mx.z) / 2);
    const R = Math.max(8, mn.distanceTo(mx) / 2 + 2);
    const d = sunDir(TIMES[S.time]);
    sun.position.copy(c).addScaledVector(d, R * 2.5);
    sun.target.position.copy(c);
    sun.target.updateMatrixWorld();
    const cam = sun.shadow.camera;
    cam.left = -R; cam.right = R; cam.top = R; cam.bottom = -R; cam.near = 0.5; cam.far = R * 5;
    cam.updateProjectionMatrix();
    sun.shadow.needsUpdate = true;
  }

  function resize() {
    const w = stage.clientWidth || 1, h = stage.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(stage);

  // ---------------------------------------------------------------- volumes & meshes
  let vol = null;
  function clearMeshes() {
    for (const k of Object.keys(meshes)) if (meshes[k]) { inner.remove(meshes[k]); meshes[k].geometry.dispose(); meshes[k] = null; }
    beams.clear();
  }
  function setMeshes(geo, ghostCells, xrayCells) {
    clearMeshes();
    meshes.solid = new THREE.Mesh(geo.solid, solidMat);
    meshes.solid.castShadow = meshes.solid.receiveShadow = true;
    meshes.water = new THREE.Mesh(geo.water, waterMat);
    meshes.water.receiveShadow = true;
    meshes.water.renderOrder = 2;
    inner.add(meshes.solid, meshes.water);
    if (ghostCells && ghostCells.length) {
      meshes.ghost = new THREE.Mesh(MC.ghostMesh(ghostCells, pal), ghostMat);
      meshes.ghost.renderOrder = 3;
      inner.add(meshes.ghost);
    }
    if (xrayCells && xrayCells.length) {
      meshes.xray = new THREE.Mesh(MC.ghostMesh(xrayCells, pal), xrayMat);
      meshes.xray.renderOrder = 4;
      inner.add(meshes.xray);
    }
    // beacon beams
    const bk = pal.variants.filter((v) => v.key === "beacon").map((v) => v.id);
    if (bk.length) {
      for (let i = 0; i < vol.ids.length; i++) {
        if (!bk.includes(vol.ids[i] - 1)) continue;
        const x = (i % vol.sx) + vol.x0, z = (((i / vol.sx) | 0) % vol.sz) + vol.z0, y = ((i / (vol.sx * vol.sz)) | 0) + vol.y0;
        const b = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 400, 10, 1, true), beamMat);
        b.position.set(x + 0.5, y + 1 + 200, z + 0.5);
        beams.add(b);
      }
    }
  }

  // grade: number, or function (x, z) -> y of the grass block
  function terrainInto(v, x1, z1, x2, z2, grade, water, decorRects, decor) {
    const gradeAt = typeof grade === "function" ? grade : () => grade;
    const g = pal.variant("grass_block"), d = pal.variant("dirt"), w = pal.variant("water"), sand = pal.variant("sand");
    const deco = decor ? ["short_grass", "short_grass", "short_grass", "poppy", "dandelion", "short_grass", "fern"].map((k) => pal.variant(k)) : [];
    let seed = 99;
    const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
    for (let x = x1; x <= x2; x++) for (let z = z1; z <= z2; z++) {
      let wa = null;
      for (const a of water) if (x >= a.rect[0] && x <= a.rect[2] && z >= a.rect[1] && z <= a.rect[3]) wa = a;
      const gy = gradeAt(x, z);
      for (let y = Math.min(gy, 0) - 4; y <= gy; y++) v.set(x, y, z, y === gy ? g : d);
      if (wa) {
        const surf = wa.surface, bottom = surf - wa.depth + 1;
        for (let y = bottom; y <= gy; y++) v.clear(x, y, z);
        for (let y = bottom; y <= surf; y++) v.set(x, y, z, w);
        v.set(x, bottom - 1, z, sand);
        continue;
      }
      const r = rnd();
      if (decor && r < decor && !decorRects.some((q) => x >= q[0] - 1 && x <= q[2] + 1 && z >= q[1] - 1 && z <= q[3] + 1))
        v.set(x, gy + 1, z, deco[(rnd() * deco.length) | 0]);
    }
  }

  // ---------------------------------------------------------------- world mode
  async function openWorld() {
    S.mode = "world";
    S.b = null;
    const w = (S.world = await api.world());
    setRoot(0, [0, 0]);
    const t = w.terrain;
    const [x1, z1, x2, z2] = t.bounds;
    let ymax = t.grade + 6, ymin = t.grade - 8;
    for (const b of w.builds) for (const g of b.grades || []) ymax = Math.max(ymax, g.y + 4);
    for (const b of w.builds) for (let i = 1; i < b.cells.length; i += 4) { ymax = Math.max(ymax, b.cells[i] + 3); ymin = Math.min(ymin, b.cells[i] - 2); }
    for (const a of t.water) ymin = Math.min(ymin, a.surface - a.depth - 2);
    vol = new MC.Vol(x1, ymin, z1, x2 - x1 + 1, ymax - ymin + 1, z2 - z1 + 1);
    const wg = new Map();
    for (const b of w.builds) for (const g of b.grades || [])
      for (let x = g.rect[0]; x <= g.rect[2]; x++) for (let z = g.rect[1]; z <= g.rect[3]; z++) wg.set(x + "," + z, g.y);
    terrainInto(vol, x1, z1, x2, z2, (x, z) => { const g = wg.get(x + "," + z); return g == null ? t.grade : g; },
      t.water, w.builds.map((b) => b.rect), t.decor || 0);
    const vmap = w.variants.map(([k, p]) => pal.variant(k, p));
    const air = pal.variant("air");
    for (const b of w.builds) {
      for (let i = 0; i < b.cells.length; i += 4) {
        const vid = vmap[b.cells[i + 3]];
        if (vid === air) vol.clear(b.cells[i], b.cells[i + 1], b.cells[i + 2]);
        else vol.set(b.cells[i], b.cells[i + 1], b.cells[i + 2], vid, 1);
      }
    }
    setMeshes(MC.mesh(vol, pal, MC.computeLight(vol, pal), {}));
    markerMesh.visible = false;
    areaBox.visible = false;
    fitShadow([new THREE.Vector3(x1, t.grade - 4, z1), new THREE.Vector3(x2 + 1, ymax, z2 + 1)]);
    scene.fog.near = 120; scene.fog.far = 520;
    if (!S.keepCamera) { S.lastView = "aerial"; viewPreset("aerial"); }
    S.keepCamera = false;
    syncUI();
  }

  // ---------------------------------------------------------------- build mode
  async function openBuild(name, mode = "build") {
    const b = await api.build(name);
    const first = !S.b || S.b.name !== name;
    S.b = b;
    S.book = b.book || {};
    S.mode = mode;
    S.cells = new Map();
    S.vmap = b.variants.map(([k, p]) => pal.variant(k, p));
    for (let i = 0; i < b.cells.length; i += 6)
      S.cells.set(b.cells[i] + "," + b.cells[i + 1] + "," + b.cells[i + 2],
        { v: S.vmap[b.cells[i + 3]], step: b.cells[i + 4] + 1, group: b.cells[i + 5] });
    if (first) {
      S.step = b.steps.length;
      S.facing = (b.world && b.world.facing) || "north";
      S.undo = []; S.redo = [];
      const ed = await api.editsFile(name).catch(() => ({ put: [], remove: [] }));
      S.edits = { put: new Map((ed.put || []).map((e) => [e.pos.join(","), e])), remove: new Set((ed.remove || []).map((p) => p.join(","))) };
    }
    S.bounds = boundsOf();
    if (first) S.cut = S.bounds.y2;
    S.step = Math.min(S.step, b.steps.length);
    setRoot(FACINGS.indexOf(S.facing), [b.marker[0] + 0.5, b.marker[2] + 0.5]);
    remesh();
    if (first && !S.keepCamera) { S.lastView = "aerial"; viewPreset("aerial"); }
    S.keepCamera = false;
    syncUI();
  }

  function boundsOf() {
    const b = S.b;
    let x1 = Math.min(0, b.marker[0]), z1 = Math.min(0, b.marker[2]), x2 = Math.max(b.footprint[0] - 1, b.marker[0]),
      z2 = Math.max(b.footprint[1] - 1, b.marker[2]), y1 = -1, y2 = 1;
    for (const k of S.cells.keys()) {
      const [x, y, z] = k.split(",").map(Number);
      x1 = Math.min(x1, x); x2 = Math.max(x2, x); z1 = Math.min(z1, z); z2 = Math.max(z2, z);
      y1 = Math.min(y1, y); y2 = Math.max(y2, y);
    }
    return { x1, y1, z1, x2, y2, z2 };
  }
  function levels() {
    const b = S.b, B = S.bounds;
    const out = [["All", B.y2]];
    const L = (S.book.levels && S.book.levels.length) ? S.book.levels :
      [...b.floors.slice().reverse().map((f) => [cap(f.name), f.y + 1]), ["Ground", 0],
        ...(b.keep_zones.some((k) => k.what === "water") ? [["Water", -1]] : [])];
    for (const [n, y] of L) out.push([n, y == null ? B.y2 : y]);
    return out;
  }

  function remesh() {
    const b = S.b, B = S.bounds, m = 6;
    const x0 = B.x1 - m, z0 = B.z1 - m, y0 = Math.min(B.y1, -4) - 2;
    const sx = B.x2 - B.x1 + 1 + 2 * m, sy = B.y2 - y0 + 6, sz = B.z2 - B.z1 + 1 + 2 * m;
    vol = new MC.Vol(x0, y0, z0, sx, sy, sz);
    const water = b.keep_zones.filter((k) => k.what === "water").map((k) => ({ rect: k.box, surface: k.surface == null ? -1 : k.surface, depth: k.depth }));
    const gmap = new Map();
    for (const g of b.grades || []) for (let x = g.box[0]; x <= g.box[2]; x++) for (let z = g.box[1]; z <= g.box[3]; z++) gmap.set(x + "," + z, g.y - 1);
    const gfn = (x, z) => { const g = gmap.get(x + "," + z); return g == null ? -1 : g; };
    const xray = [];
    const waterId = pal.variant("water"), air = pal.variant("air");
    if (S.xray) {
      const tv = new MC.Vol(x0, y0, z0, sx, sy, sz);
      terrainInto(tv, x0, z0, x0 + sx - 1, z0 + sz - 1, gfn, water, [], 0);
      for (let i = 0; i < tv.ids.length; i++) {
        const id = tv.ids[i] - 1;
        if (id < 0) continue;
        if (id === waterId) { vol.ids[i] = tv.ids[i]; continue; }
        const x = (i % sx) + x0, z = (((i / sx) | 0) % sz) + z0, y = ((i / (sx * sz)) | 0) + y0;
        if (!S.cells.has(x + "," + y + "," + z)) xray.push([x, y, z, id]);
      }
    } else terrainInto(vol, x0, z0, x0 + sx - 1, z0 + sz - 1, gfn, water, [], 0);
    const ghost = [];
    for (const [k, c] of S.cells) {
      const [x, y, z] = k.split(",").map(Number);
      if (y > S.cut) continue;
      if (c.step <= S.step) {
        if (c.v === air) vol.clear(x, y, z);
        else vol.set(x, y, z, c.v, c.step, c.group);
      } else if (S.ghost && c.v !== air) ghost.push([x, y, z, c.v]);
    }
    if (S.cut < B.y2) for (let y = S.cut + 1; y < vol.y0 + vol.sy; y++)
      for (let z = vol.z0; z < vol.z0 + vol.sz; z++) for (let x = vol.x0; x < vol.x0 + vol.sx; x++) vol.clear(x, y, z);
    const light = MC.computeLight(vol, pal);
    setMeshes(MC.mesh(vol, pal, light, { highlightStep: S.step }), ghost, xray);
    markerMesh.visible = true;
    markerMesh.position.set(b.marker[0] + 0.5, b.marker[1] + 0.03, b.marker[2] + 0.5);
    fitShadow(worldBox([B.x1 - 3, -4, B.z1 - 3], [B.x2 + 4, B.y2 + 1, B.z2 + 4]));
    const R = Math.hypot(B.x2 - B.x1, B.z2 - B.z1, B.y2 - B.y1);
    scene.fog.near = R * 2.2; scene.fog.far = R * 9 + 200;
    updateStepUI();
  }
  function worldBox(mn, mx) {
    const a = new THREE.Vector3(Infinity, Infinity, Infinity), b = new THREE.Vector3(-Infinity, -Infinity, -Infinity);
    for (const x of [mn[0], mx[0]]) for (const y of [mn[1], mx[1]]) for (const z of [mn[2], mx[2]]) {
      const p = toWorld(x, y, z);
      a.min(p); b.max(p);
    }
    return [a, b];
  }

  // ---------------------------------------------------------------- camera
  function dirVec(yaw = S.yaw, pitch = S.pitch) {
    return new THREE.Vector3(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
  }
  // frame a local-space box. yaw is given in the build's own frame (front = north) and turned with it
  function frame(min, max, yaw, pitch, tight = 1, worldFixed = false) {
    const [a, b] = worldBox(min, [max[0] + 1, max[1] + 1, max[2] + 1]);
    const c = a.clone().add(b).multiplyScalar(0.5);
    const r = a.distanceTo(b) / 2;
    const fov = (camera.fov * Math.PI) / 180;
    const dist = ((r / Math.sin(fov / 2)) * 0.8 * tight) / Math.min(1, camera.aspect);
    S.yaw = worldFixed ? yaw : yaw - ((S.turns || 0) * Math.PI) / 2;
    S.pitch = pitch;
    S.pos.copy(c).addScaledVector(dirVec(), -dist);
  }
  function viewPreset(name) {
    areaBox.visible = false;
    S.areaOn = null;
    if (S.mode === "world" || !S.b) {
      const t = S.world.terrain;
      if (name.startsWith("build:")) {
        const bb = S.world.builds.find((b) => b.name === name.slice(6));
        if (bb) frame([bb.rect[0], t.grade, bb.rect[1]], [bb.rect[2], t.grade + 14, bb.rect[3]], -Math.PI * 0.75, -0.5);
        return;
      }
      const [x1, z1, x2, z2] = t.bounds;
      frame([x1, t.grade - 2, z1], [x2, t.grade + 12, z2], -Math.PI * 0.75, -0.55, 0.72);
      return;
    }
    const B = S.bounds;
    const min = [B.x1, Math.max(B.y1, -1), B.z1], max = [B.x2, B.y2, B.z2];
    // aerial is fixed to the world (from the north-west) so turning the build with Faces is visible
    if (name === "aerial" || name === "overview") frame(min, max, -Math.PI * 0.75, -0.58, 1, true);
    else if (name === "approach") frame([B.x1, 0, B.z1], [B.x2, Math.max(4, B.y2 * 0.7), B.z2], Math.PI * 0.92, -0.16, 0.82);
    else if (name === "front") frame(min, max, Math.PI, -0.25);
    else if (name === "back") frame(min, max, 0, -0.25);
    else if (name === "left") frame(min, max, -Math.PI / 2, -0.25);
    else if (name === "right") frame(min, max, Math.PI / 2, -0.25);
    else if (name === "top" || name === "plan") frame(min, max, 0, -1.5, 0.92);
    else if (name === "rear") frame(min, max, Math.PI * 0.25, -0.45);
    else if (name.startsWith("area:")) focusArea(name.slice(5));
    else if (name.startsWith("secret:")) focusSecret(+name.slice(7));
  }
  function focusArea(key) {
    const a = S.b.areas.find((q) => q.key === key);
    if (!a) return;
    let y1 = 0, y2 = 2;
    for (const k of S.cells.keys()) {
      const [x, y, z] = k.split(",").map(Number);
      if (x >= a.box[0] && x <= a.box[2] && z >= a.box[1] && z <= a.box[3]) { y1 = Math.min(y1, y); y2 = Math.max(y2, y); }
    }
    y1 = Math.max(y1, -1);
    // look from outside the footprint toward its centre, so the area is not hidden behind the rest
    const fx = S.b.footprint[0] / 2, fz = S.b.footprint[1] / 2;
    const ax = (a.box[0] + a.box[2] + 1) / 2, az = (a.box[1] + a.box[3] + 1) / 2;
    const dx = fx - ax, dz = fz - az;
    let yaw = -Math.PI * 0.75, pitch = -0.6;
    if (!a.ring && Math.hypot(dx, dz) > 2) yaw = Math.atan2(-dx, -dz);
    else if (!a.ring) pitch = -0.75;
    frame([a.box[0], y1, a.box[1]], [a.box[2], y2, a.box[3]], yaw, pitch, a.ring ? 0.8 : 1.2);
    areaBox.box.set(new THREE.Vector3(a.box[0], y1, a.box[1]), new THREE.Vector3(a.box[2] + 1, y2 + 1, a.box[3] + 1));
    areaBox.visible = true;
    S.areaOn = key;
  }
  function focusSecret(i) {
    const s = (S.book.secrets || [])[i];
    if (!s) return;
    const [x, y, z] = s.pos;
    if (y < 0 || s.xray) { S.xray = true; S.cut = y + 1; remesh(); renderPills(); }   // underground: see through, cut down to it
    // approach from the nearest outside edge of the footprint
    const dx = S.b.footprint[0] / 2 - (x + 0.5), dz = S.b.footprint[1] / 2 - (z + 0.5);
    const yaw = Math.hypot(dx, dz) > 2 ? Math.atan2(-dx, -dz) : -Math.PI * 0.75;
    frame([x - 3, y - 1, z - 3], [x + 3, y + 3, z + 3], yaw, -0.72, 1.6);
    areaBox.box.set(new THREE.Vector3(x, y, z), new THREE.Vector3(x + 1, y + 1, z + 1));
    areaBox.visible = true;
  }

  let drag = null;
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  canvas.addEventListener("pointerdown", (e) => {
    canvas.focus();
    drag = { x: e.clientX, y: e.clientY, moved: false, button: e.button };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    S.mouse = { x: e.clientX, y: e.clientY };
    if (drag) {
      if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 4) drag.moved = true;
      if (drag.moved) {
        S.yaw -= (e.movementX || 0) * 0.0045;
        S.pitch = Math.max(-1.55, Math.min(1.55, S.pitch - (e.movementY || 0) * 0.0045));
      }
    }
  });
  canvas.addEventListener("pointerup", (e) => { if (drag && !drag.moved) click(drag.button, e); drag = null; });
  canvas.addEventListener("pointerleave", () => { S.mouse = null; outline.visible = false; $("#readout").innerHTML = measureText(); });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    S.speed = Math.max(2, Math.min(150, S.speed * (e.deltaY > 0 ? 0.85 : 1.18)));
    toast(`speed ${S.speed.toFixed(0)}`);
  }, { passive: false });
  window.addEventListener("keydown", (e) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName) && e.target.type !== "range") return;
    const k = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && k === "z") { e.preventDefault(); return e.shiftKey ? redo() : undo(); }
    if ((e.ctrlKey || e.metaKey) && k === "y") { e.preventDefault(); return redo(); }
    S.keys.add(e.code);
    if ($("#picker").classList.contains("open")) { if (k === "e" || k === "escape") { e.preventDefault(); togglePicker(false); } return; }
    if (k === "f") viewPreset("aerial");
    else if (k === "l") toggle("labels");
    else if (k === "m") toggleMeasure();
    else if (k === "x" && S.b) toggle("xray");
    else if (k === "g" && S.b) toggle("ghost");
    else if (k === "h") $("#help").classList.toggle("open");
    else if (k === "[" && S.b) setStep(S.step - 1);
    else if (k === "]" && S.b) setStep(S.step + 1);
    else if (k === "," && S.b) setCut(S.cut - 1);
    else if (k === "." && S.b) setCut(S.cut + 1);
    else if (S.mode === "edit") {
      if (k === "e") { e.preventDefault(); togglePicker(true); }
      else if (k === "r") { S.rot = (S.rot + 1) % 4; toast("rotate +" + S.rot * 90 + "°"); }
      else if (/^[1-9]$/.test(k)) { S.slot = +k - 1; renderHotbar(); }
    }
  });
  window.addEventListener("keyup", (e) => S.keys.delete(e.code));
  window.addEventListener("blur", () => S.keys.clear());

  function moveCamera(dt) {
    const f = dirVec(S.yaw, 0), r = new THREE.Vector3(-f.z, 0, f.x), v = new THREE.Vector3();
    const K = S.keys;
    if (K.has("KeyW") || K.has("ArrowUp")) v.add(f);
    if (K.has("KeyS") || K.has("ArrowDown")) v.sub(f);
    if (K.has("KeyD") || K.has("ArrowRight")) v.add(r);
    if (K.has("KeyA") || K.has("ArrowLeft")) v.sub(r);
    if (K.has("Space")) v.y += 1;
    if (K.has("ShiftLeft") || K.has("ShiftRight")) v.y -= 1;
    if (v.lengthSq()) S.pos.addScaledVector(v.normalize(), S.speed * dt * (K.has("ControlLeft") ? 3 : 1));
    camera.position.copy(S.pos);
    camera.rotation.set(S.pitch, S.yaw, 0);
  }

  // ---------------------------------------------------------------- picking
  const ray = new THREE.Raycaster();
  let lastRay = null;
  function pick(mx, my) {
    if (!vol) return null;
    const r = canvas.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((mx - r.left) / r.width) * 2 - 1, -((my - r.top) / r.height) * 2 + 1), camera);
    const lr = localRay(ray.ray.origin, ray.ray.direction);
    lastRay = lr;
    return MC.raycast(vol, pal, lr.o, lr.d, 600);
  }
  function cellInfo(x, y, z) {
    const id = vol.get(x, y, z);
    return id >= 0 ? pal.v(id) : null;
  }
  function worldOrigin(b) {
    const w = b.world;
    const grade = w.grade != null ? w.grade : S.world ? S.world.terrain.grade : 64;
    return [w.pos[0], w.y != null ? w.y : grade + 1, w.pos[1]];
  }
  function relCoords(x, y, z) {
    const b = S.b, m = b.marker;
    const dx = x - m[0], dy = y - m[1], dz = z - m[2];
    const [rx, rz] = rotXZ(dx, dz, FACINGS.indexOf(S.facing));
    let abs = null;
    if (b.world) {
      const [wx, wz] = rotXZ(dx, dz, FACINGS.indexOf(b.world.facing));
      const o = worldOrigin(b);
      abs = [o[0] + wx, o[1] + dy, o[2] + wz];
    }
    return { local: [dx, dy, dz], cmd: [rx, dy, rz], abs };
  }
  function updateHover() {
    const ro = $("#readout");
    if (!S.mouse || (drag && drag.moved)) return;
    const h = pick(S.mouse.x, S.mouse.y);
    S.hover = h;
    if (!h) { outline.visible = false; ro.innerHTML = measureText(); return; }
    outline.visible = true;
    outline.position.set(h.x + 0.5, h.y + 0.5, h.z + 0.5);
    const v = cellInfo(h.x, h.y, h.z);
    if (S.mode === "world" || !S.b) {
      const bld = buildAt(h.x, h.z);
      ro.innerHTML = `<b>${v ? v.def.name : ""}</b> &nbsp; X ${h.x} Y ${h.y} Z ${h.z}` + (bld ? `<br>${bld.title}: click to open` : "");
      return;
    }
    const rc = relCoords(h.x, h.y, h.z);
    const props = v && Object.keys(v.props).length ? " " + Object.entries(v.props).map(([a, b]) => `${a}=${b}`).join(" ") : "";
    const c = S.cells.get(h.x + "," + h.y + "," + h.z);
    const step = c ? `${pad2(c.step + 1)} ${S.b.steps[c.step - 1].title}` : "ground";
    ro.innerHTML = `<b>${v ? v.def.name : "?"}</b><span style="color:var(--dim)">${props}</span><br>` +
      `from marker <b>${rc.local.join(", ")}</b> (x east, y up, z south)<br>` +
      `command (${S.facing}) <code>~${rc.cmd[0]} ~${rc.cmd[1]} ~${rc.cmd[2]}</code>` +
      (rc.abs ? `<br>world ${rc.abs.join(" ")}` : "") + `<br>step ${step}` + measureText(true);
  }
  function buildAt(x, z) {
    return S.world && S.world.builds.find((b) => x >= b.rect[0] && x <= b.rect[2] && z >= b.rect[1] && z <= b.rect[3]);
  }

  // ---------------------------------------------------------------- measure
  function toggleMeasure() {
    S.measure = { on: !S.measure.on, a: null, b: null };
    measureLine.visible = false;
    renderPills();
    toast(S.measure.on ? "Measure: click two blocks" : "Measure off");
  }
  function measureText(br) {
    const M = S.measure;
    if (!M.on) return "";
    const pre = br ? "<br>" : "";
    if (!M.a) return pre + "measure: click the first block";
    if (!M.b) return pre + `measure: from ${M.a.join(",")}, click the second block`;
    const d = M.b.map((v, i) => v - M.a[i]);
    return pre + `measure Δ ${d.join(", ")} · span ${d.map((v) => Math.abs(v) + 1).join(" × ")} · ${Math.hypot(...d).toFixed(2)} m`;
  }
  function measureClick(h) {
    const M = S.measure;
    const p = [h.x, h.y, h.z];
    if (!M.a || M.b) { M.a = p; M.b = null; measureLine.visible = false; }
    else {
      M.b = p;
      measureLine.geometry.setFromPoints([new THREE.Vector3(M.a[0] + 0.5, M.a[1] + 0.5, M.a[2] + 0.5), new THREE.Vector3(p[0] + 0.5, p[1] + 0.5, p[2] + 0.5)]);
      measureLine.visible = true;
    }
    updateHover();
  }

  // ---------------------------------------------------------------- clicks & editing
  function click(button, e) {
    const h = pick(e.clientX, e.clientY);
    if (S.measure.on) { if (h) measureClick(h); return; }
    if (S.mode === "world") {
      if (!h) return;
      const b = buildAt(h.x, h.z);
      if (b) navigate(b.name, "build");
      return;
    }
    if (S.mode !== "edit" || !h) return;
    if (button === 0) breakBlock(h);
    else if (button === 2) placeBlock(h);
    else if (button === 1) {
      const v = cellInfo(h.x, h.y, h.z);
      if (v && v.key !== "air") { S.hotbar[S.slot] = v.key; renderHotbar(); }
    }
  }
  const K3 = (x, y, z) => x + "," + y + "," + z;
  let localGroup = -1;
  function snapshot() { return { put: new Map(S.edits.put), remove: new Set(S.edits.remove) }; }
  function changeCells(changes, label) {
    const before = { edits: snapshot(), cells: changes.map(([k]) => [k, S.cells.get(k) || null]) };
    for (const [k, c] of changes) {
      const pos = k.split(",").map(Number);
      if (c) {
        S.cells.set(k, c);
        S.edits.put.set(k, { pos, block: pal.v(c.v).key, props: pal.v(c.v).props, step: S.b.steps[c.step - 1].key });
      } else {
        S.cells.delete(k);
        S.edits.put.delete(k);
        S.edits.remove.add(k);
      }
    }
    S.undo.push({ before, after: { edits: snapshot(), cells: changes }, label });
    S.redo = [];
    commitEdits(label);
  }
  function restore(state) {
    S.edits = { put: new Map(state.edits.put), remove: new Set(state.edits.remove) };
    for (const [k, c] of state.cells) { if (c) S.cells.set(k, c); else S.cells.delete(k); }
  }
  function undo() { const a = S.undo.pop(); if (!a) return; restore(a.before); S.redo.push(a); commitEdits("undo " + a.label); }
  function redo() { const a = S.redo.pop(); if (!a) return; restore(a.after); S.undo.push(a); commitEdits("redo " + a.label); }
  let saveTimer = null;
  function commitEdits(label) {
    S.bounds = boundsOf();
    remesh();
    toast(label);
    syncPane();
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      const data = { put: [...S.edits.put.values()], remove: [...S.edits.remove].map((k) => k.split(",").map(Number)) };
      try {
        setStatus("saving edits…");
        await api.saveEdits(S.b.name, data);
        setStatus(EMBED ? "edits kept in this page (download from the Edit tab)" : "edits saved · rebuilding…");
      } catch (err) { setStatus("save failed: " + err.message); }
    }, 250);
  }
  function groupCells(k) {
    const c = S.cells.get(k);
    if (!c || !c.group) return [k];
    return [...S.cells.entries()].filter(([, v]) => v.group === c.group).map(([kk]) => kk);
  }
  function curStep() { return Math.max(1, Math.min(S.step, S.b.steps.length)); }
  function breakBlock(h) {
    const k = K3(h.x, h.y, h.z);
    if (S.cells.has(k)) changeCells(groupCells(k).map((kk) => [kk, null]), "break");
    else if (h.y < 0) changeCells([[k, { v: pal.variant("air"), step: curStep(), group: 0 }]], "dig");
  }
  function lookDir() {
    // camera heading turned back into the build's own frame
    const d = dirVec(S.yaw + ((S.turns || 0) * Math.PI) / 2, 0);
    let f = Math.abs(d.x) > Math.abs(d.z) ? (d.x > 0 ? "east" : "west") : d.z > 0 ? "south" : "north";
    for (let i = 0; i < S.rot; i++) f = FACINGS[(FACINGS.indexOf(f) + 1) % 4];
    return f;
  }
  function placeBlock(h) {
    const key = S.hotbar[S.slot];
    const def = pal.def(key);
    if (!def) return;
    const n = h.n;
    const x = h.x + n[0], y = h.y + n[1], z = h.z + n[2];
    const free = (xx, yy, zz) => { const v = cellInfo(xx, yy, zz); return !v || (v.flags.walk && v.shape !== "door" && v.shape !== "ladder"); };
    if (!free(x, y, z)) return toast("blocked");
    const props = {};
    const look = lookDir();
    const faceDir = n[0] > 0 ? "east" : n[0] < 0 ? "west" : n[2] > 0 ? "south" : n[2] < 0 ? "north" : n[1] > 0 ? "up" : "down";
    const hitY = lastRay ? (() => { const p = lastRay.o.clone().addScaledVector(lastRay.d, h.t); return p.y - Math.floor(p.y); })() : 0.25;
    const P = def.props;
    if ("facing" in P) {
      if (def.shape === "ladder" || def.shape === "torch") {
        if (faceDir === "down" || (def.shape === "ladder" && faceDir === "up")) return toast("can't attach there");
        props.facing = faceDir;
      } else if (key === "barrel") props.facing = "up";
      else if (["chest", "cube", "campfire"].includes(def.shape)) props.facing = MC.OPP[look];
      else props.facing = look;
    }
    if ("half" in P) props.half = faceDir === "down" || (faceDir !== "up" && hitY > 0.5) ? "top" : "bottom";
    if ("axis" in P) props.axis = faceDir === "up" || faceDir === "down" ? "y" : faceDir === "east" || faceDir === "west" ? "x" : "z";
    if ("hanging" in P) props.hanging = faceDir === "down";
    const step = curStep();
    const g = localGroup--;
    const changes = [];
    if (def.shape === "door" || def.shape === "tall_plant") {
      if (!free(x, y + 1, z)) return toast("needs two blocks of space");
      changes.push([K3(x, y, z), { v: pal.variant(key, Object.assign({}, props, { upper: false })), step, group: g }],
        [K3(x, y + 1, z), { v: pal.variant(key, Object.assign({}, props, { upper: true })), step, group: g }]);
    } else if (def.shape === "bed") {
      const d = MC.DIRV[props.facing];
      if (!free(x + d[0], y, z + d[1])) return toast("needs two blocks of space");
      changes.push([K3(x, y, z), { v: pal.variant(key, Object.assign({}, props, { head: false })), step, group: g }],
        [K3(x + d[0], y, z + d[1]), { v: pal.variant(key, Object.assign({}, props, { head: true })), step, group: g }]);
    } else changes.push([K3(x, y, z), { v: pal.variant(key, props), step, group: 0 }]);
    changeCells(changes, "place " + def.name);
  }

  // ---------------------------------------------------------------- picker & hotbar
  function renderHotbar() {
    const hb = $("#hotbar");
    hb.innerHTML = "";
    S.hotbar.forEach((k, i) => {
      const v = pal.v(pal.variant(k));
      hb.append(el("div", { class: "slot" + (i === S.slot ? " sel" : ""), title: v.def.name, onclick: () => { S.slot = i; renderHotbar(); } },
        atlas.swatch(v.tiles[4], 32), el("span", { class: "num" }, String(i + 1))));
    });
  }
  let pkCat = "all";
  function togglePicker(open) {
    $("#picker").classList.toggle("open", open);
    if (open) { renderPicker(); $("#pk-search").focus(); } else canvas.focus();
  }
  function renderPicker() {
    const cats = ["all", ...new Set(Object.values(pal.blocks).map((b) => b.cat))];
    const pc = $("#pk-cats");
    pc.innerHTML = "";
    for (const c of cats) pc.append(el("button", { class: c === pkCat ? "on" : "", onclick: () => { pkCat = c; renderPicker(); } }, c));
    const q = $("#pk-search").value.toLowerCase();
    const grid = $("#pk-grid");
    grid.innerHTML = "";
    for (const [k, b] of Object.entries(pal.blocks)) {
      if (k === "air" || (pkCat !== "all" && b.cat !== pkCat) || (q && !(k.includes(q) || b.name.toLowerCase().includes(q)))) continue;
      const v = pal.v(pal.variant(k));
      grid.append(el("div", {
        class: "slot" + (S.hotbar[S.slot] === k ? " sel" : ""), title: b.name,
        onmouseenter: () => ($("#pk-name").textContent = `${b.name}  (${b.id})`),
        onclick: () => { S.hotbar[S.slot] = k; renderHotbar(); renderPicker(); },
      }, atlas.swatch(v.tiles[4], 32)));
    }
  }
  $("#pk-search").addEventListener("input", renderPicker);
  $("#pk-search").addEventListener("keydown", (e) => { if (e.key === "Escape") togglePicker(false); });

  // ---------------------------------------------------------------- header, bar, pills, cut, step navigator
  function setStatus(t, live) { const s = $("#status"); s.textContent = t; s.classList.toggle("live", !!live); }
  let toastT = null;
  function toast(t) {
    const e = $("#toast");
    e.textContent = t; e.style.display = "block";
    clearTimeout(toastT);
    toastT = setTimeout(() => (e.style.display = "none"), 1400);
  }
  function setStep(s) { if (!S.b) return; S.step = Math.max(0, Math.min(S.b.steps.length, s)); remesh(); syncPane(); }
  function setCut(c) { if (!S.b) return; S.cut = Math.max(S.bounds.y1, Math.min(S.bounds.y2, c)); remesh(); syncPane(); }
  function toggle(what) {
    S[what] = !S[what];
    if (S.b && S.mode !== "world" && (what === "xray" || what === "ghost")) remesh();
    renderPills();
  }
  function stepTitle(i) { return i === 0 ? "Clear and level the land" : S.b.steps[i - 1].title; }
  function updateStepUI() {
    if (!S.b) return;
    const N = S.b.steps.length;
    $("#step-num").textContent = pad2(S.step + 1);
    $("#step-title").textContent = stepTitle(S.step);
    const segs = $("#segs");
    if (segs.children.length !== N + 1) {
      segs.innerHTML = "";
      for (let i = 0; i <= N; i++) segs.append(el("button", { title: `${pad2(i + 1)} ${stepTitle(i)}`, onclick: () => setStep(i) }));
    }
    [...segs.children].forEach((b, i) => { b.className = i === S.step ? "on" : i < S.step ? "done" : ""; });
    const ct = $("#cut");
    ct.min = S.bounds.y1; ct.max = S.bounds.y2; ct.value = S.cut;
    const marks = $("#cut-marks");
    marks.innerHTML = "";
    for (const [n, y] of levels()) marks.append(el("button", { class: S.cut === y ? "on" : "", title: `${n}: show up to y=${y}`, onclick: () => setCut(y) }, n));
    $("#cut-label").textContent = S.cut >= S.bounds.y2 ? "all" : `y ${S.cut}`;
  }
  $("#cut").addEventListener("input", (e) => setCut(+e.target.value));
  $("#prev").addEventListener("click", () => setStep(S.step - 1));
  $("#next").addEventListener("click", () => setStep(S.step + 1));
  document.querySelectorAll("#times button").forEach((b) => b.addEventListener("click", () => setTime(b.dataset.time)));
  document.querySelectorAll("#faces button").forEach((b) => b.addEventListener("click", () => setFacing(b.dataset.f)));
  document.querySelectorAll("#modes button").forEach((b) => b.addEventListener("click", () => {
    const m = b.dataset.mode;
    if (m === "world") navigate(null, "world");
    else if (S.b) { S.mode = m; navigate(S.b.name, m, true); }
    else { const n = $("#build-select").value || (S.world && S.world.builds[0] && S.world.builds[0].name); if (n) navigate(n, m); }
  }));
  $("#t-help").addEventListener("click", () => $("#help").classList.toggle("open"));
  $("#build-select").addEventListener("change", (e) => e.target.value && navigate(e.target.value, S.mode === "edit" ? "edit" : "build"));

  function setFacing(f) {
    if (!S.b) return;
    S.facing = f;
    setRoot(FACINGS.indexOf(f), [S.b.marker[0] + 0.5, S.b.marker[2] + 0.5]);
    remesh();
    viewPreset(S.lastView || "aerial");
    syncUI();
  }

  function renderPills() {
    const p = $("#pills");
    p.innerHTML = "";
    const pill = (label, on, fn, title) => p.append(el("button", { class: "pill" + (on ? " on" : ""), title, onclick: fn }, label));
    const view = (name) => () => { S.lastView = name; viewPreset(name); renderPills(); };
    if (S.mode === "world" || !S.b) {
      pill("Aerial", S.lastView === "aerial", view("aerial"));
      if (S.world) for (const b of S.world.builds) pill(b.title, S.lastView === "build:" + b.name, view("build:" + b.name));
      pill("Labels", S.labels, () => toggle("labels"));
      pill("Measure", S.measure.on, toggleMeasure);
      return;
    }
    pill("Approach", S.lastView === "approach", view("approach"), "Eye level, from the front");
    pill("Aerial", S.lastView === "aerial", view("aerial"));
    for (const a of S.b.areas) if (!a.ring && !a.rest && a.pill !== false) pill(a.title, S.lastView === "area:" + a.key, view("area:" + a.key), a.desc);
    pill("Plan", S.lastView === "plan", view("plan"), "Straight down, front at the top");
    pill("X-ray ground", S.xray, () => toggle("xray"), "See through the ground (X)");
    pill("Ghost later steps", S.ghost, () => toggle("ghost"), "Show what comes after this step (G)");
    pill("Labels", S.labels, () => toggle("labels"), "Area labels (L)");
    pill("Measure", S.measure.on, toggleMeasure, "Click two blocks (M)");
  }

  function renderHeader() {
    const b = S.b;
    const st = $("#stats");
    st.innerHTML = "";
    const stat = (v, l) => st.append(el("div", { class: "stat" }, el("b", {}, v), el("span", {}, l)));
    if (S.mode === "world" || !b) {
      $("#title").textContent = "World";
      const w = S.world;
      $("#subtitle").textContent = w ? `Shared world · grass at Y ${w.terrain.grade} · sea level ${w.terrain.sea_level}` : "";
      if (w) {
        const [x1, z1, x2, z2] = w.terrain.bounds;
        stat(`${x2 - x1 + 1}×${z2 - z1 + 1}`, "Terrain, blocks");
        stat(String(w.builds.length), "Builds");
        stat(fmt(w.builds.reduce((a, q) => a + q.count, 0)), "Blocks placed");
        stat(String(w.problems.length), "Collisions");
      }
      document.title = "World · Build Studio";
      return;
    }
    $("#title").textContent = b.title;
    $("#subtitle").textContent = S.book.subtitle || (b.description || "").split(/\.\s/)[0];
    stat(`${b.footprint[0]}×${b.footprint[1]}`, "Site, blocks");
    stat(String(b.height), "Height");
    stat(fmt(b.counts.total), "Blocks to place");
    if (S.book.stats && S.book.stats.length) for (const [v, l] of S.book.stats) stat(String(v), l);
    else stat(String(b.steps.length + 1), "Steps");
    document.title = b.title;
  }

  function navigate(name, mode, keep) {
    const u = new URL(location.href);
    if (name) u.searchParams.set("build", name); else u.searchParams.delete("build");
    u.searchParams.set("mode", mode);
    history.pushState({}, "", u);
    route(keep);
  }
  window.addEventListener("popstate", () => route());
  async function route(keep) {
    const u = new URL(location.href);
    const name = u.searchParams.get("build") || (EMBED ? EMBED.build.name : null);
    const mode = u.searchParams.get("mode") || (name ? "build" : "world");
    if ((!name || mode === "world") && !EMBED) return openWorld();
    if (keep && S.b && S.b.name === name) { S.mode = mode; syncUI(); remesh(); return; }
    await openBuild(name, mode === "edit" ? "edit" : "build");
  }

  function syncUI() {
    document.querySelectorAll("#modes button").forEach((b) => {
      b.classList.toggle("on", b.dataset.mode === S.mode);
      if (EMBED && b.dataset.mode === "world") b.style.display = "none";
    });
    const inBuild = S.mode !== "world" && !!S.b;
    $("#faces").style.display = $("#faces-lbl").style.display = inBuild ? "" : "none";
    if (inBuild) {
      $("#faces-lbl").textContent = `${S.book.subject || "Front"} faces`;
      document.querySelectorAll("#faces button").forEach((b) => b.classList.toggle("on", b.dataset.f === S.facing));
    }
    $("#cutbox").style.display = $("#stepnav").style.display = inBuild ? "" : "none";
    $("#hotbar").classList.toggle("on", S.mode === "edit");
    if (S.mode === "edit") renderHotbar();
    if (S.b) $("#build-select").value = S.b.name;
    renderHeader();
    renderPills();
    if (inBuild) updateStepUI();
    renderTabs();
  }

  // ---------------------------------------------------------------- side panel
  function tabsFor() {
    if (S.mode === "world" || !S.b) return ["Builds", "World"];
    const t = ["Steps", S.book.subject || "Areas"];
    if (S.book.secrets && S.book.secrets.length) t.push("Secrets");
    t.push("Blocks", "Layers", "Commands", "Setup", "Checks");
    if (S.mode === "edit") t.unshift("Edit");
    return t;
  }
  function renderTabs() {
    const tabs = tabsFor();
    if (!tabs.includes(S.tab)) S.tab = tabs[0];
    const t = $("#tabs");
    t.innerHTML = "";
    for (const name of tabs) t.append(el("button", { class: name === S.tab ? "on" : "", onclick: () => { S.tab = name; renderTabs(); } }, name));
    syncPane();
  }
  function syncPane() {
    const p = $("#pane");
    const keep = p.dataset.tab === S.tab ? p.scrollTop : 0;
    p.innerHTML = "";
    p.dataset.tab = S.tab;
    const key = S.b && S.mode !== "world" && S.tab === (S.book.subject || "Areas") ? "Subject" : S.tab;
    if (PANES[key]) PANES[key](p);
    p.scrollTop = keep;
    if (S.b && S.mode !== "world") updateStepUI();
  }
  const swatchFor = (key) => {
    const c = atlas.swatch(pal.v(pal.variant(key)).tiles[4], 20);
    c.className = "sw";
    return c;
  };
  function areaCount(a) {
    let n = 0;
    for (const [k, c] of S.cells) {
      const [x, , z] = k.split(",").map(Number);
      const inside = x >= a.box[0] && x <= a.box[2] && z >= a.box[1] && z <= a.box[3] &&
        (!a.ring || x === a.box[0] || x === a.box[2] || z === a.box[1] || z === a.box[3]);
      if (inside && pal.v(c.v).key !== "air") n++;
    }
    return n;
  }
  const PANES = {
    Builds(p) {
      p.append(el("h2", {}, "Builds in the world"),
        el("p", {}, "Every build sits on the shared terrain at its world.json position and facing. Click one in the view, or open it here."));
      for (const b of S.world.builds) {
        p.append(el("div", { class: "card" },
          el("div", { class: "row space" }, el("b", {}, b.title),
            el("span", { class: "row" }, el("button", { class: "btn", onclick: () => { S.lastView = "build:" + b.name; viewPreset("build:" + b.name); renderPills(); } }, "Fly to"),
              el("button", { class: "btn on", onclick: () => navigate(b.name, "build") }, "Open"))),
          el("div", { class: "meta" }, `${b.name} · faces ${b.facing} · marker at ${b.origin.join(" ")} · ${fmt(b.count)} cells`)));
      }
    },
    World(p) {
      const t = S.world.terrain;
      p.append(el("h2", {}, "Terrain"),
        el("div", { class: "card" }, `Grass at Y ${t.grade} · sea level ${t.sea_level} · bounds ${t.bounds.join(", ")}`),
        el("h4", {}, "Water"), ...t.water.map((w) => el("div", { class: "card" }, `${w.name}: ${w.rect.join(", ")} · surface ${w.surface} · depth ${w.depth}`)),
        el("h4", {}, "Collisions"), ...(S.world.problems.length ? S.world.problems.map((q) => el("div", { class: "card lvl-error" }, q.msg)) :
          [el("div", { class: "card lvl-ok" }, "No collisions between builds.")]),
        el("p", {}, "Edit world/world.json to move or turn builds; the view reloads."));
    },
    Steps(p) {
      const b = S.b, N = b.steps.length;
      const head = S.book.steps_headline || `${cap(WORDS[N + 1] || String(N + 1))} steps, site work to ${b.steps[N - 1].title.toLowerCase()}`;
      p.append(el("h2", {}, head), el("p", { class: "intro" }, S.book.steps_intro ||
        "Each step is one function in the pack (big ones are split into parts). Pick a step to see the build up to that point; new blocks glow copper."));
      const card = (i, title, count, desc) => el("div", { class: "card stepcard" + (S.step === i ? " on" : ""), onclick: () => setStep(i) },
        el("span", { class: "num" }, pad2(i + 1)), el("span", { class: "t" }, title), el("span", { class: "c" }, count),
        desc && S.step === i ? el("span", { class: "d" }, desc) : null);
      const keep = b.keep_zones.length ? ` Keep-zones are left alone: ${b.keep_zones.map((k) => k.note || k.what).join(", ")}.` : "";
      p.append(card(0, "Clear and level the land", "site work", "Clears everything above grade over the site, fills holes below it and lays grass." + keep));
      b.steps.forEach((s, i) => p.append(card(i + 1, s.title, fmt(b.counts.by_step[s.key]), s.desc)));
      const tot = b.counts.total, pct = b.target ? ((100 * (tot - b.target)) / b.target).toFixed(0) : 0;
      p.append(el("div", { class: "card row space" }, el("b", {}, "Total"), el("span", { style: "font-family:var(--mono);color:var(--dim)" },
        `${fmt(tot)} · target ${fmt(b.target)} (${pct >= 0 ? "+" : ""}${pct}%)`)),
        el("p", {}, `Buried below-grade fill is not counted (${b.counts.hidden}). Hand edits merged: ${b.edits.put || 0} placed, ${b.edits.remove || 0} removed. Built ${b.built}.`));
    },
    Subject(p) {
      const b = S.b;
      p.append(el("h2", {}, b.title), el("p", {}, b.description || ""));
      for (const a of b.areas) {
        if (a.rest) continue;
        const w = a.box[2] - a.box[0] + 1, d = a.box[3] - a.box[1] + 1;
        p.append(el("div", { class: "card" + (S.areaOn === a.key ? " on" : "") },
          el("div", { class: "row space" }, el("b", {}, a.title),
            a.ring ? null : el("button", { class: "btn", onclick: () => { S.lastView = "area:" + a.key; focusArea(a.key); renderPills(); syncPane(); } }, "Focus")),
          el("div", { style: "margin:4px 0" }, a.desc),
          el("div", { class: "meta" }, `${w} × ${d}${a.ring ? " edge" : ""} · ${fmt(areaCount(a))} blocks · from marker ${a.box[0] - b.marker[0]},${a.box[1] - b.marker[2]} to ${a.box[2] - b.marker[0]},${a.box[3] - b.marker[2]}`)));
      }
      if (b.keep_zones.length) {
        p.append(el("h4", {}, "Keep-zones (never touched)"));
        for (const k of b.keep_zones) p.append(el("div", { class: "card" }, `${k.note || k.what}: ${k.box.join(", ")}`));
      }
    },
    Secrets(p) {
      p.append(el("h2", {}, "Secrets"), el("p", {}, "Hidden things in the build. Focus turns on x-ray when they are underground."));
      S.book.secrets.forEach((s, i) => {
        const rc = relCoords(...s.pos);
        p.append(el("div", { class: "card" },
          el("div", { class: "row space" }, el("b", {}, s.title), el("button", { class: "btn", onclick: () => focusSecret(i) }, "Focus")),
          el("div", { style: "margin:4px 0" }, s.desc),
          el("div", { class: "meta" }, `from marker ${rc.local.join(", ")} · command ~${rc.cmd.join(" ~")}`)));
      });
    },
    Blocks(p) {
      const b = S.b;
      const which = S.blocksView || "total";
      p.append(el("h2", {}, "Blocks"),
        el("div", { class: "row", style: "margin-bottom:12px" }, ...["total", "this step"].map((w) =>
          el("button", { class: "btn" + (w === which ? " on" : ""), onclick: () => { S.blocksView = w; syncPane(); } }, w))));
      const s = S.step > 0 ? b.steps[S.step - 1] : null;
      const counts = which === "total" ? b.counts.by_block : s ? b.counts.by_step_block[s.key] : {};
      const tb = el("table", {}, el("tr", {}, el("th"), el("th", {}, which === "total" ? "All steps" : `Step ${pad2(S.step + 1)}: ${stepTitle(S.step)}`),
        el("th", { class: "n" }, "Blocks"), el("th", { class: "n" }, "Items"), el("th", { class: "n" }, "Stacks")));
      let total = 0;
      for (const [k, n] of Object.entries(counts).sort((a, c) => c[1] - a[1])) {
        const items = Math.ceil(n / (pal.def(k).item_cells || 1));
        total += n;
        tb.append(el("tr", {}, el("td", {}, swatchFor(k)), el("td", {}, pal.def(k).name), el("td", { class: "n" }, fmt(n)),
          el("td", { class: "n" }, fmt(items)), el("td", { class: "n" }, items >= 64 ? `${(items / 64) | 0}+${items % 64}` : "")));
      }
      tb.append(el("tr", {}, el("td"), el("td", {}, el("b", {}, "Total")), el("td", { class: "n" }, el("b", {}, fmt(total))), el("td"), el("td")));
      p.append(tb, el("p", { style: "margin-top:12px" }, "Doors, beds and tall flowers take two cells per item. Counts come from the last rebuild (edits included)."));
    },
    Layers(p) {
      const B = S.bounds;
      const y = Math.min(S.cut, B.y2);
      p.append(el("h2", {}, `Layer y ${y}`),
        el("p", {}, "One layer at a time, front at the top. Faded cells are below this layer. The layer is the cut height."));
      const sl = el("input", { type: "range", class: "h", min: B.y1, max: B.y2, value: y });
      sl.addEventListener("input", (e) => setCut(+e.target.value));
      p.append(el("div", { class: "row", style: "margin-bottom:10px" }, el("button", { class: "btn", onclick: () => setCut(S.cut - 1) }, "▼"),
        el("div", { style: "flex:1" }, sl), el("button", { class: "btn", onclick: () => setCut(S.cut + 1) }, "▲")));
      const w = B.x2 - B.x1 + 3, d = B.z2 - B.z1 + 3;
      const s = Math.max(4, Math.floor(560 / Math.max(w, d)));
      const c = el("canvas", { id: "plan-canvas", width: w * s, height: d * s });
      const g = c.getContext("2d");
      g.fillStyle = "#24402c"; g.fillRect(0, 0, c.width, c.height);
      const X = (x) => (x - B.x1 + 1) * s, Z = (z) => (z - B.z1 + 1) * s;
      const tops = new Map();
      for (const [k, cc] of S.cells) {
        const [x, yy, z] = k.split(",").map(Number);
        if (cc.step > S.step || yy > y) continue;
        const v = pal.v(cc.v);
        if (v.key === "air") continue;
        const kk = x + "," + z, prev = tops.get(kk);
        if (!prev || yy > prev.y) tops.set(kk, { y: yy, v });
      }
      for (const [kk, t] of tops) {
        const [x, z] = kk.split(",").map(Number);
        const col = atlas.avg[t.v.tiles[2]];
        const f = t.y === y ? 1 : Math.max(0.22, 0.55 - (y - t.y) * 0.06);
        g.fillStyle = `rgb(${(col[0] * f) | 0},${(col[1] * f) | 0},${(col[2] * f) | 0})`;
        g.fillRect(X(x), Z(z), s, s);
      }
      for (const k of S.b.keep_zones) { g.fillStyle = "rgba(80,170,220,0.45)"; g.fillRect(X(k.box[0]), Z(k.box[1]), (k.box[2] - k.box[0] + 1) * s, (k.box[3] - k.box[1] + 1) * s); }
      const m = S.b.marker;
      for (let x = B.x1 - 1; x <= B.x2 + 2; x++) { g.strokeStyle = (x - m[0]) % 5 ? "rgba(0,0,0,0.22)" : "rgba(0,0,0,0.55)"; g.beginPath(); g.moveTo(X(x), 0); g.lineTo(X(x), c.height); g.stroke(); }
      for (let z = B.z1 - 1; z <= B.z2 + 2; z++) { g.strokeStyle = (z - m[2]) % 5 ? "rgba(0,0,0,0.22)" : "rgba(0,0,0,0.55)"; g.beginPath(); g.moveTo(0, Z(z)); g.lineTo(c.width, Z(z)); g.stroke(); }
      g.strokeStyle = "#3fd1ae"; g.lineWidth = 2;
      g.strokeRect(X(0), Z(0), S.b.footprint[0] * s, S.b.footprint[1] * s);
      g.fillStyle = "#ffcc33"; g.beginPath(); g.arc(X(m[0]) + s / 2, Z(m[2]) + s / 2, s / 2.4, 0, 7); g.fill();
      g.fillStyle = "#fff"; g.font = "12px 'IBM Plex Mono', monospace"; g.fillText("front ↑", 6, 14);
      const info = el("div", { class: "meta", style: "margin-top:8px;font-family:var(--mono)" }, "hover the layer for coordinates");
      c.addEventListener("mousemove", (e) => {
        const r = c.getBoundingClientRect();
        const x = Math.floor((((e.clientX - r.left) / r.width) * c.width) / s) + B.x1 - 1;
        const z = Math.floor((((e.clientY - r.top) / r.height) * c.height) / s) + B.z1 - 1;
        const cc = S.cells.get(x + "," + y + "," + z);
        const rc = relCoords(x, y, z);
        info.innerHTML = `from marker <b>${rc.local.join(", ")}</b> · <code>~${rc.cmd.join(" ~")}</code> · ${cc ? pal.v(cc.v).def.name : "empty"}`;
      });
      p.append(c, info);
    },
    Commands(p) {
      const b = S.b;
      const c = b.commands[S.facing];
      p.append(el("h2", {}, "Commands"),
        el("p", {}, `Facing ${S.facing}: ${fmt(c.total)} commands to build. Functions live in ${b.name}/${S.facing}/ inside the pack.`));
      for (const f of ["setup", "test_blocks", ...c.run_order, ...new Set(["build", ...(c.build_parts || [])]), "cleanup"]) {
        const lines = c.files[f];
        if (!lines) continue;
        const pre = el("pre", { style: "display:none" }, lines.join("\n"));
        const call = `/function ${b.name}/${S.facing}/${f}`;
        p.append(el("div", { class: "card" },
          el("div", { class: "row space" }, el("code", {}, call),
            el("span", { class: "row" }, el("span", { class: "meta", style: "font-family:var(--mono)" }, `${lines.filter((l) => l && !l.startsWith("#")).length} cmds`),
              el("button", { class: "btn", onclick: () => (pre.style.display = pre.style.display === "none" ? "block" : "none") }, "show"),
              el("button", { class: "btn", onclick: () => copy(call) }, "copy"))), pre));
      }
    },
    Setup(p) {
      const b = S.b;
      const plat = b.config.platform === "pc" ? "PC" : `phone (${b.config.phone_os || "ios"})`;
      p.append(el("h2", {}, "Into your Realm"),
        el("p", {}, `Import on your ${plat} (config.json "platform"). Pack: ${b.mcpack} v${b.pack_version}.`));
      const ol = el("ol", {});
      for (const s of b.install) ol.append(el("li", {}, s));
      p.append(ol, el("h4", {}, `Build it in game · faces ${S.facing}`));
      const ns = `${b.name}/${S.facing}`;
      const order = b.commands[S.facing].run_order;
      const steps = [
        ["Stand on the marker (the yellow square), or use the positioned commands below.", null],
        ["Load the site, then wait about 5 seconds:", `/function ${ns}/setup`],
        ["Optional: one of every block appears in a strip in front of you:", `/function ${ns}/test_blocks`],
        ...((b.commands[S.facing].build_parts || ["build"]).length > 1
          ? [[`Build everything, in ${b.commands[S.facing].build_parts.length} parts (one call can run at most 10,000 commands). Run each after the last one says it's done:`,
              b.commands[S.facing].build_parts.map((f) => `/function ${ns}/${f}`).join("\n")]]
          : [["Build everything:", `/function ${ns}/build`]]),
        ["Or one step at a time:", order.map((f) => `/function ${ns}/${f}`).join("\n")],
        ["Tidy up (test strip, dropped items, ticking area):", `/function ${ns}/cleanup`],
      ];
      for (const [t, cmd] of steps)
        p.append(el("div", { class: "card" }, t, cmd ? el("pre", {}, cmd) : null, cmd ? el("button", { class: "btn", onclick: () => copy(cmd) }, "copy") : null));
      if (b.world) {
        const o = worldOrigin(b);
        const cmd = `/execute positioned ${o.join(" ")} run function ${b.name}/${b.world.facing}/setup\n/execute positioned ${o.join(" ")} run function ${b.name}/${b.world.facing}/build`;
        p.append(el("h4", {}, "At its world.json spot"),
          el("div", { class: "card" }, `Marker at ${o.join(" ")}, faces ${b.world.facing} (as in the World view):`, el("pre", {}, cmd),
            el("button", { class: "btn", onclick: () => copy(cmd) }, "copy")));
      }
      p.append(el("p", {}, "Cheats must be on. The marker is where the player's feet are."));
    },
    Checks(p) {
      const b = S.b;
      const errs = b.checks.filter((c) => c.level === "error").length, warns = b.checks.filter((c) => c.level === "warn").length;
      p.append(el("h2", {}, "Checks"), el("p", { class: errs ? "lvl-error" : warns ? "lvl-warn" : "lvl-ok" },
        errs ? `${errs} errors, ${warns} warnings` : warns ? `${warns} warnings` : "Every check passes."));
      for (const c of b.checks) {
        const card = el("div", { class: "card" }, el("span", { class: "lvl-" + c.level, style: "font-family:var(--mono)" }, c.level.toUpperCase()), " ",
          el("b", {}, c.check), " ", c.msg);
        if (c.where && c.where.length) card.append(el("div", { style: "margin-top:6px" }, el("button", { class: "btn", onclick: () => showWhere(c.where) }, "show where")));
        p.append(card);
      }
    },
    Edit(p) {
      const b = S.b;
      p.append(el("h2", {}, "Edit"),
        el("p", {}, "Left click breaks, right click places, middle click picks. E opens the block picker, R rotates, Ctrl+Z / Ctrl+Y undo and redo."),
        el("p", {}, `New blocks go into step ${pad2(curStep() + 1)}: ${b.steps[curStep() - 1].title}. Move the step navigator to choose.`),
        el("div", { class: "row" }, el("button", { class: "btn on", onclick: () => togglePicker(true) }, "Block picker (E)"),
          el("button", { class: "btn", onclick: undo }, "Undo"), el("button", { class: "btn", onclick: redo }, "Redo")),
        el("h4", {}, "Saved edits"),
        el("div", { class: "card" }, `${S.edits.put.size} placed · ${S.edits.remove.size} removed`,
          el("div", { class: "meta" }, EMBED ? "Static page: edits stay in this page." : `Saved to edits/${b.name}.json and merged into the build, the checks and the pack.`)));
      if (EMBED) p.append(el("button", { class: "btn", onclick: downloadEdits }, "Download edits JSON"));
      else p.append(el("button", { class: "btn", onclick: clearEdits }, "Discard all edits"));
    },
  };
  function showWhere(list) {
    checkMarks.clear();
    for (const w of list) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(1.06, 1.06, 1.06), new THREE.MeshBasicMaterial({ color: 0xff4d4d, wireframe: true, depthTest: false }));
      m.position.set(w[0] + 0.5, w[1] + 0.5, w[2] + 0.5);
      m.renderOrder = 11;
      checkMarks.add(m);
    }
    if (list.length) { const w = list[0]; frame([w[0] - 4, w[1] - 2, w[2] - 4], [w[0] + 4, w[1] + 3, w[2] + 4], -Math.PI * 0.75, -0.5); }
    setTimeout(() => checkMarks.clear(), 15000);
  }
  async function clearEdits() {
    if (!confirm("Discard every hand edit for this build?")) return;
    S.edits = { put: new Map(), remove: new Set() };
    await api.saveEdits(S.b.name, { put: [], remove: [] });
    setStatus("edits cleared · rebuilding…");
  }
  function downloadEdits() {
    const data = { build: S.b.name, put: [...S.edits.put.values()], remove: [...S.edits.remove].map((k) => k.split(",").map(Number)) };
    el("a", { href: URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" })), download: `${S.b.name}.json` }).click();
  }
  function copy(t) {
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => toast("copied"), () => toast("copy failed"));
  }

  // ---------------------------------------------------------------- labels
  const labelsEl = $("#labels");
  const labelPool = [], labelOcc = [];
  let labelT = 0;
  function updateLabels() {
    const items = [];
    if (S.labels) {
      if ((S.mode === "world" || !S.b) && S.world) {
        for (const b of S.world.builds) {
          let top = S.world.terrain.grade + 2;
          for (let i = 1; i < b.cells.length; i += 4) top = Math.max(top, b.cells[i]);
          items.push({ text: b.title, cls: "label build", p: toWorld((b.rect[0] + b.rect[2] + 1) / 2, top + 2.5, (b.rect[1] + b.rect[3] + 1) / 2) });
        }
      } else if (S.b) {
        for (const a of S.b.areas) {
          if (a.ring || a.rest || a.label === false) continue;
          let top = 0;
          for (const k of S.cells.keys()) {
            const [x, y, z] = k.split(",").map(Number);
            if (x >= a.box[0] && x <= a.box[2] && z >= a.box[1] && z <= a.box[3] && y <= S.cut) top = Math.max(top, y);
          }
          items.push({ text: a.title, cls: "label", p: toWorld((a.box[0] + a.box[2] + 1) / 2, top + 1.6, (a.box[1] + a.box[3] + 1) / 2) });
        }
      }
    }
    const w = stage.clientWidth, h = stage.clientHeight;
    items.forEach((it, i) => {
      let e = labelPool[i];
      if (!e) { e = el("div", { class: "label" }); labelsEl.append(e); labelPool.push(e); }
      const v = it.p.clone().project(camera);
      const on = v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1;
      e.style.display = on ? "block" : "none";
      if (!on) return;
      if (vol && labelT % 4 === i % 4) {   // dim labels hidden behind blocks
        const d = it.p.clone().sub(camera.position), dist = d.length();
        const lr = localRay(camera.position, d.normalize());
        const hit = MC.raycast(vol, pal, lr.o, lr.d, dist);
        labelOcc[i] = !!(hit && hit.t < dist - 1.5);
      }
      e.style.opacity = labelOcc[i] ? 0.35 : 1;
      e.className = it.cls;
      e.textContent = it.text;
      e.style.left = ((v.x + 1) / 2) * w + "px";
      e.style.top = ((1 - v.y) / 2) * h + "px";
    });
    for (let i = items.length; i < labelPool.length; i++) labelPool[i].style.display = "none";
  }

  // ---------------------------------------------------------------- live reload
  function live() {
    if (EMBED || !window.EventSource) return;
    const es = new EventSource("/api/events");
    es.onopen = () => setStatus("live", true);
    es.onerror = () => setStatus("dev server offline (retrying)");
    es.onmessage = async (m) => {
      const ev = JSON.parse(m.data);
      if (ev.type === "status") return setStatus(ev.text, true);
      if (ev.type === "rebuilt") {
        setStatus(`rebuilt ${ev.names.join(", ")} ${ev.ok ? "✓" : "with errors"}`, true);
        try {
          if (S.mode === "world") { S.keepCamera = true; await openWorld(); }
          else if (S.b && ev.names.includes(S.b.name)) { S.keepCamera = true; await openBuild(S.b.name, S.mode); }
          refreshBuildList();
        } catch (e) { setStatus("reload failed: " + e.message); }
      }
    };
  }
  async function refreshBuildList() {
    const names = await api.builds();
    const sel = $("#build-select");
    sel.innerHTML = "";
    sel.append(el("option", { value: "" }, "open build…"));
    for (const n of names) sel.append(el("option", { value: n }, n));
    sel.value = S.b ? S.b.name : "";
  }

  // ---------------------------------------------------------------- loop
  let last = performance.now(), hoverT = 0;
  function loop(now) {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    moveCamera(dt);
    U.uTime.value = now / 1000;
    sky.position.copy(camera.position);
    disc.position.copy(sunDir(TIMES[S.time])).multiplyScalar(1200);
    disc.lookAt(0, 0, 0);
    if ((hoverT += dt) > 0.05) { hoverT = 0; updateHover(); }
    renderer.render(scene, camera);
    labelT++;
    updateLabels();
    requestAnimationFrame(loop);
  }

  // ---------------------------------------------------------------- automation API (screenshots, tests)
  Object.assign(window.studio, {
    setTime, viewPreset, setStep, setCut, focusArea, setFacing,
    toggle: (k, v) => { if (v == null || !!S[k] !== !!v) toggle(k); },
    open: (name, mode) => navigate(name, mode || "build"),
    world: () => navigate(null, "world"),
    ui: (on) => document.body.classList.toggle("noui", !on),
    frameNow: () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
    pickAt: (x, y) => pick(x, y),
    place: (h) => placeBlock(h), breakAt: (h) => breakBlock(h), undo, redo,
    editState: () => ({ put: [...S.edits.put.values()], remove: [...S.edits.remove] }),
    setSlot: (i, key) => { S.slot = i; if (key) S.hotbar[i] = key; renderHotbar(); },
    // look in the build's own frame (yaw 0 = toward north); pos is local
    look: (yaw, pitch, pos) => {
      S.yaw = yaw - ((S.turns || 0) * Math.PI) / 2; S.pitch = pitch;
      if (pos) S.pos.copy(toWorld(...pos));
    },
  });

  async function boot() {
    try {
      resize();
      const pj = await api.palette();
      pal = new MC.Palette(pj, atlas);
      const q = new URL(location.href).searchParams;
      setTime(q.get("time") || "day");
      if (q.get("ui") === "0") document.body.classList.add("noui");
      if (!EMBED) { S.world = await api.world().catch(() => null); await refreshBuildList(); }
      else $("#build-select").style.display = "none";
      await route();
      resize();
      live();
      if (EMBED) setStatus("static export · " + (EMBED.exported || ""));
      S.ready = window.studio.ready = true;
      requestAnimationFrame(loop);
    } catch (e) {
      setStatus("error: " + e.message);
      console.error(e);
      window.studio.error = String((e && e.stack) || e);
    }
  }
  boot();
})();
