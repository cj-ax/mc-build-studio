// Build Studio viewer: world mode, build mode (steps, cut-away, plan, inventory,
// commands, setup, areas, checks) and edit mode (place/break, undo, saved to edits/).
(function () {
  const MC = window.MC;
  const EMBED = window.STUDIO_EMBED || null;      // set by the static single-file export
  const $ = (s) => document.querySelector(s);
  const el = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (k === "html") e.innerHTML = v;
      else e.setAttribute(k, v);
    }
    for (const k of kids) if (k != null) e.append(k.nodeType ? k : document.createTextNode(k));
    return e;
  };
  const FACINGS = ["north", "east", "south", "west"];
  const rotXZ = (x, z, t) => { for (let i = 0; i < ((t % 4) + 4) % 4; i++) [x, z] = [-z, x]; return [x, z]; };
  const TIMES = {
    day: { sky: [1, 1, 1], level: 1, block: [1, 0.9, 0.72], top: 0x6c9fe8, bg: 0xb4d2f7, fog: 0xbcd7f7 },
    sunset: { sky: [1, 0.78, 0.6], level: 0.66, block: [1, 0.85, 0.6], top: 0x3f568f, bg: 0xf09a66, fog: 0xe9a57c },
    night: { sky: [0.42, 0.52, 0.95], level: 0.22, block: [1, 0.8, 0.52], top: 0x03050d, bg: 0x0c1430, fog: 0x0b1029 },
  };

  const S = {
    mode: "world", time: "day", step: 1, cut: 99, facing: "north",
    opts: { hl: true, ghost: true, terrain: true }, labels: true, panel: true, tab: null,
    cells: new Map(), edits: { put: new Map(), remove: new Set() }, undo: [], redo: [],
    hotbar: ["oak_planks", "cobblestone", "spruce_stairs", "spruce_slab", "glass_pane", "lantern", "oak_fence", "poppy", "torch"],
    slot: 0, rot: 0, measure: { on: false, a: null, b: null }, hover: null, keys: new Set(), speed: 12,
    yaw: -Math.PI * 0.75, pitch: -0.45, pos: new THREE.Vector3(0, 20, 0), ready: false, busy: 0,
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
  THREE.ColorManagement.enabled = false;     // Minecraft-style: colours and textures used as-is
  const canvas = $("#gl");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, 1, 0.1, 2000);
  camera.rotation.order = "YXZ";
  const atlas = new MC.Atlas();
  let pal = null;

  const VERT = `
    attribute vec3 light; attribute float hl;
    varying vec2 vUv; varying vec3 vLight; varying float vHl; varying float vDepth;
    void main() { vUv = uv; vLight = light; vHl = hl; vec4 mv = modelViewMatrix * vec4(position, 1.0);
      vDepth = -mv.z; gl_Position = projectionMatrix * mv; }`;
  const FRAG = `
    uniform sampler2D map; uniform vec3 skyColor; uniform float skyLevel; uniform vec3 blockColor;
    uniform vec3 fogColor; uniform float fogNear; uniform float fogFar; uniform float opacity; uniform float alphaTest; uniform float time;
    varying vec2 vUv; varying vec3 vLight; varying float vHl; varying float vDepth;
    float curve(float l) { return l / (4.0 - 3.0 * l); }
    void main() {
      vec4 t = texture2D(map, vUv);
      if (t.a < alphaTest) discard;
      float s = curve(clamp(vLight.x, 0.0, 1.0)) * skyLevel;
      float b = curve(clamp(vLight.y, 0.0, 1.0));
      vec3 lit = max(skyColor * s, blockColor * b) + vec3(0.04);
      vec3 c = t.rgb * min(lit, vec3(1.0)) * vLight.z;
      if (vHl > 0.5) c = mix(c, vec3(1.0, 0.86, 0.3), 0.22 + 0.12 * sin(time * 4.0)) + 0.05;
      float f = smoothstep(fogNear, fogFar, vDepth);
      gl_FragColor = vec4(mix(c, fogColor, f), t.a * opacity);
    }`;
  function mat(extra) {
    return new THREE.ShaderMaterial(Object.assign({
      vertexShader: VERT, fragmentShader: FRAG,
      uniforms: {
        map: { value: atlas.three() }, skyColor: { value: new THREE.Color(1, 1, 1) }, skyLevel: { value: 1 },
        blockColor: { value: new THREE.Color(1, 0.9, 0.7) }, fogColor: { value: new THREE.Color(0xbcd7f7) },
        fogNear: { value: 80 }, fogFar: { value: 260 }, opacity: { value: 1 }, alphaTest: { value: 0.5 }, time: { value: 0 },
      },
    }, extra));
  }
  const solidMat = mat({});
  const waterMat = mat({ transparent: true, depthWrite: false });
  waterMat.uniforms.opacity.value = 0.72;
  waterMat.uniforms.alphaTest.value = 0.0;
  const ghostMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.16, depthWrite: false });
  const meshes = { solid: null, water: null, ghost: null };
  const group = new THREE.Group();
  scene.add(group);

  // hover outline, measure line, area outline
  const outline = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.004, 1.004, 1.004)),
    new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.8 }));
  outline.visible = false;
  scene.add(outline);
  const measureLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: 0xffd23c, depthTest: false }));
  measureLine.visible = false;
  measureLine.renderOrder = 10;
  scene.add(measureLine);
  const areaBox = new THREE.Box3Helper(new THREE.Box3(), 0xffd23c);
  areaBox.visible = false;
  scene.add(areaBox);
  const markerMesh = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.06, 0.5), new THREE.MeshBasicMaterial({ color: 0xffcc00 }));
  scene.add(markerMesh);
  const checkMarks = new THREE.Group();
  scene.add(checkMarks);

  // sky: sun / moon and stars
  const sun = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.MeshBasicMaterial({ color: 0xfff2b0, fog: false }));
  const moon = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshBasicMaterial({ color: 0xdfe6ff, fog: false }));
  const starGeo = new THREE.BufferGeometry();
  {
    const p = [];
    let r = 12345;
    const rnd = () => ((r = (r * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    for (let i = 0; i < 900; i++) {
      const th = rnd() * Math.PI * 2, ph = Math.acos(rnd() * 0.95);
      p.push(Math.sin(ph) * Math.cos(th) * 900, Math.cos(ph) * 900, Math.sin(ph) * Math.sin(th) * 900);
    }
    starGeo.setAttribute("position", new THREE.Float32BufferAttribute(p, 3));
  }
  const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 2, sizeAttenuation: false }));
  const domeGeo = new THREE.SphereGeometry(950, 24, 16);
  domeGeo.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(domeGeo.attributes.position.count * 3), 3));
  const dome = new THREE.Mesh(domeGeo, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, depthWrite: false, fog: false }));
  dome.renderOrder = -10;
  function paintDome(top, horizon) {
    const a = new THREE.Color(top), b = new THREE.Color(horizon), c = new THREE.Color();
    const pos = domeGeo.attributes.position, col = domeGeo.attributes.color;
    for (let i = 0; i < pos.count; i++) {
      const t = Math.max(0, Math.min(1, pos.getY(i) / 950));
      c.copy(b).lerp(a, Math.pow(t, 0.6));
      col.setXYZ(i, c.r, c.g, c.b);
    }
    col.needsUpdate = true;
  }
  const sky = new THREE.Group();
  sky.add(dome, sun, moon, stars);
  scene.add(sky);

  function setTime(t) {
    S.time = t;
    const T = TIMES[t];
    scene.background = new THREE.Color(T.fog);
    paintDome(T.top, T.bg);
    for (const m of [solidMat, waterMat]) {
      m.uniforms.skyColor.value.setRGB(...T.sky);
      m.uniforms.skyLevel.value = T.level;
      m.uniforms.blockColor.value.setRGB(...T.block);
      m.uniforms.fogColor.value.set(T.fog);
    }
    const ang = { day: 1.1, sunset: 0.08, night: -0.9 }[t];
    sun.position.set(-Math.cos(ang) * 700, Math.sin(ang) * 700, -200);
    sun.lookAt(0, 0, 0);
    moon.position.set(Math.cos(ang) * 700, -Math.sin(ang) * 700 + (t === "night" ? 0 : -2000), 200);
    moon.lookAt(0, 0, 0);
    stars.visible = t === "night";
    sun.visible = t !== "night";
    document.querySelectorAll("#times button").forEach((b) => b.classList.toggle("on", b.dataset.time === t));
  }

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  // ---------------------------------------------------------------- volumes
  let vol = null;           // what is drawn (and picked)
  let fullVol = null;       // build mode: every cell regardless of step/cut
  function setMeshes(geo, ghostCells) {
    for (const k of Object.keys(meshes)) if (meshes[k]) { group.remove(meshes[k]); meshes[k].geometry.dispose(); meshes[k] = null; }
    meshes.solid = new THREE.Mesh(geo.solid, solidMat);
    meshes.water = new THREE.Mesh(geo.water, waterMat);
    meshes.water.renderOrder = 2;
    group.add(meshes.solid, meshes.water);
    if (ghostCells && ghostCells.length) {
      meshes.ghost = new THREE.Mesh(MC.ghostMesh(ghostCells, pal), ghostMat);
      meshes.ghost.renderOrder = 3;
      group.add(meshes.ghost);
    }
  }

  function terrainInto(v, x1, z1, x2, z2, grade, water, decorRects, decor) {
    const g = pal.variant("grass_block"), d = pal.variant("dirt"), w = pal.variant("water"), sand = pal.variant("sand");
    const deco = decor ? ["short_grass", "short_grass", "short_grass", "poppy", "dandelion", "short_grass", "fern"].map((k) => pal.variant(k)) : [];
    let seed = 99;
    const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
    for (let x = x1; x <= x2; x++) for (let z = z1; z <= z2; z++) {
      let wa = null;
      for (const a of water) if (x >= a.rect[0] && x <= a.rect[2] && z >= a.rect[1] && z <= a.rect[3]) wa = a;
      for (let y = grade - 4; y <= grade; y++) v.set(x, y, z, y === grade ? g : d);
      if (wa) {
        const surf = wa.surface, bottom = surf - wa.depth + 1;
        for (let y = bottom; y <= grade; y++) v.clear(x, y, z);
        for (let y = bottom; y <= surf; y++) v.set(x, y, z, w);
        v.set(x, bottom - 1, z, sand);
        continue;
      }
      const r = rnd();
      if (decor && r < decor && !decorRects.some((q) => x >= q[0] - 1 && x <= q[2] + 1 && z >= q[1] - 1 && z <= q[3] + 1))
        v.set(x, grade + 1, z, deco[(rnd() * deco.length) | 0]);
    }
  }

  // ---------------------------------------------------------------- world mode
  async function openWorld() {
    S.mode = "world";
    S.b = null;
    const w = (S.world = await api.world());
    const t = w.terrain;
    const [x1, z1, x2, z2] = t.bounds;
    let ymax = t.grade + 6, ymin = t.grade - 8;
    for (const b of w.builds) for (let i = 1; i < b.cells.length; i += 4) { ymax = Math.max(ymax, b.cells[i] + 3); ymin = Math.min(ymin, b.cells[i] - 2); }
    for (const a of t.water) ymin = Math.min(ymin, a.surface - a.depth - 2);
    vol = new MC.Vol(x1, ymin, z1, x2 - x1 + 1, ymax - ymin + 1, z2 - z1 + 1);
    terrainInto(vol, x1, z1, x2, z2, t.grade, t.water, w.builds.map((b) => b.rect), t.decor || 0);
    const vmap = w.variants.map(([k, p]) => pal.variant(k, p));
    const air = pal.variant("air");
    for (const b of w.builds) {
      for (let i = 0; i < b.cells.length; i += 4) {
        const vid = vmap[b.cells[i + 3]];
        if (vid === air) vol.clear(b.cells[i], b.cells[i + 1], b.cells[i + 2]);
        else vol.set(b.cells[i], b.cells[i + 1], b.cells[i + 2], vid, 1);
      }
    }
    const light = MC.computeLight(vol, pal);
    setMeshes(MC.mesh(vol, pal, light, {}));
    for (const m of [solidMat, waterMat]) { m.uniforms.fogNear.value = 90; m.uniforms.fogFar.value = 320; }
    markerMesh.visible = false;
    $("#title").innerHTML = "World <small>" + w.builds.length + " builds</small>";
    if (!S.keepCamera) frame([x1, t.grade - 2, z1], [x2, t.grade + 12, z2], -Math.PI * 0.75, -0.55, 0.75);
    S.keepCamera = false;
    syncUI();
  }

  // ---------------------------------------------------------------- build mode
  async function openBuild(name, mode = "build") {
    const b = await api.build(name);
    const first = !S.b || S.b.name !== name;
    S.b = b;
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
    $("#title").innerHTML = `${b.title} <small>${b.counts.total} blocks · target ${b.target} · pack v${b.pack_version}</small>`;
    remesh();
    if (first && !S.keepCamera) viewPreset("overview");
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

  function remesh() {
    const b = S.b, B = S.bounds, m = 5;
    const x0 = B.x1 - m, z0 = B.z1 - m, y0 = Math.min(B.y1, -4) - 2;
    vol = new MC.Vol(x0, y0, z0, B.x2 - B.x1 + 1 + 2 * m, B.y2 - y0 + 6, B.z2 - B.z1 + 1 + 2 * m);
    if (S.opts.terrain) {
      const water = b.keep_zones.filter((k) => k.what === "water").map((k) => ({ rect: k.box, surface: -1, depth: k.depth }));
      terrainInto(vol, x0, z0, x0 + vol.sx - 1, z0 + vol.sz - 1, -1, water, [], 0);
    }
    const ghost = [];
    const air = pal.variant("air");
    for (const [k, c] of S.cells) {
      const [x, y, z] = k.split(",").map(Number);
      if (y > S.cut) continue;
      if (c.step <= S.step) {
        if (c.v === air) vol.clear(x, y, z);
        else vol.set(x, y, z, c.v, c.step, c.group);
      } else if (S.opts.ghost && c.v !== air) ghost.push([x, y, z, c.v]);
    }
    if (S.cut < S.bounds.y2) for (let y = S.cut + 1; y < vol.y0 + vol.sy; y++)
      for (let z = vol.z0; z < vol.z0 + vol.sz; z++) for (let x = vol.x0; x < vol.x0 + vol.sx; x++) vol.clear(x, y, z);
    const light = MC.computeLight(vol, pal);
    setMeshes(MC.mesh(vol, pal, light, { highlightStep: S.opts.hl ? S.step : -1 }), ghost);
    for (const mm of [solidMat, waterMat]) { mm.uniforms.fogNear.value = 120; mm.uniforms.fogFar.value = 400; }
    markerMesh.visible = true;
    markerMesh.position.set(b.marker[0] + 0.5, b.marker[1] + 0.03, b.marker[2] + 0.5);
    updateStepUI();
  }

  // ---------------------------------------------------------------- camera
  function dirVec(yaw = S.yaw, pitch = S.pitch) {
    return new THREE.Vector3(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
  }
  function frame(min, max, yaw, pitch, tight = 1) {
    const c = new THREE.Vector3((min[0] + max[0] + 1) / 2, (min[1] + max[1] + 1) / 2, (min[2] + max[2] + 1) / 2);
    const r = Math.hypot(max[0] - min[0] + 1, max[1] - min[1] + 1, max[2] - min[2] + 1) / 2;
    const fov = (camera.fov * Math.PI) / 180;
    const dist = (r / Math.sin(fov / 2)) * 0.85 * tight / Math.min(1, camera.aspect);
    S.yaw = yaw; S.pitch = pitch;
    S.pos.copy(c).addScaledVector(dirVec(), -dist);
  }
  function viewPreset(name) {
    if (S.mode === "world" || !S.b) {
      const w = S.world;
      if (name.startsWith("build:")) {
        const bb = w.builds.find((b) => b.name === name.slice(6));
        if (bb) frame([bb.rect[0], w.terrain.grade, bb.rect[1]], [bb.rect[2], w.terrain.grade + 14, bb.rect[3]], -Math.PI * 0.75, -0.5);
        return;
      }
      const [x1, z1, x2, z2] = w.terrain.bounds;
      frame([x1, w.terrain.grade - 2, z1], [x2, w.terrain.grade + 12, z2], -Math.PI * 0.75, -0.55, 0.75);
      return;
    }
    const B = S.bounds;
    areaBox.visible = false;
    S.areaOn = null;
    const min = [B.x1, Math.max(B.y1, -1), B.z1], max = [B.x2, B.y2, B.z2];
    if (name === "overview") frame(min, max, -Math.PI * 0.75, -0.5);
    else if (name === "front") frame(min, max, Math.PI, -0.25);
    else if (name === "back") frame(min, max, 0, -0.25);
    else if (name === "left") frame(min, max, -Math.PI / 2, -0.25);
    else if (name === "right") frame(min, max, Math.PI / 2, -0.25);
    else if (name === "top") frame(min, max, 0, -1.5);
    else if (name === "rear") frame(min, max, Math.PI * 0.25, -0.45);
    else if (name.startsWith("area:")) focusArea(name.slice(5));
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
    let dx = fx - ax, dz = fz - az;
    let yaw = -Math.PI * 0.75, pitch = -0.6;
    if (!a.ring && Math.hypot(dx, dz) > 2) yaw = Math.atan2(-dx, -dz);
    else if (!a.ring) pitch = -0.75;
    frame([a.box[0], y1, a.box[1]], [a.box[2], y2, a.box[3]], yaw, pitch, a.ring ? 0.8 : 1.2);
    areaBox.box.set(new THREE.Vector3(a.box[0], y1, a.box[1]), new THREE.Vector3(a.box[2] + 1, y2 + 1, a.box[3] + 1));
    areaBox.visible = true;
    S.areaOn = key;
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
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      if (drag.moved) {
        S.yaw -= (e.movementX || 0) * 0.0045;
        S.pitch = Math.max(-1.55, Math.min(1.55, S.pitch - (e.movementY || 0) * 0.0045));
      }
    }
  });
  canvas.addEventListener("pointerup", (e) => {
    if (drag && !drag.moved) click(drag.button, e);
    drag = null;
  });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    S.speed = Math.max(2, Math.min(120, S.speed * (e.deltaY > 0 ? 0.85 : 1.18)));
    toast(`speed ${S.speed.toFixed(0)}`);
  }, { passive: false });
  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA") return;
    const k = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && k === "z") { e.preventDefault(); return e.shiftKey ? redo() : undo(); }
    if ((e.ctrlKey || e.metaKey) && k === "y") { e.preventDefault(); return redo(); }
    S.keys.add(e.code);
    if ($("#picker").classList.contains("open")) { if (k === "e" || k === "escape") { e.preventDefault(); togglePicker(false); } return; }
    if (k === "f") viewPreset("overview");
    else if (k === "l") { S.labels = !S.labels; syncUI(); }
    else if (k === "m") toggleMeasure();
    else if (k === "p") { S.panel = !S.panel; syncUI(); }
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
  function pick(mx, my) {
    if (!vol) return null;
    const r = canvas.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((mx - r.left) / r.width) * 2 - 1, -((my - r.top) / r.height) * 2 + 1), camera);
    return MC.raycast(vol, pal, ray.ray.origin, ray.ray.direction, 400);
  }
  function cellInfo(x, y, z) {
    const id = vol.get(x, y, z);
    return id >= 0 ? pal.v(id) : null;
  }
  function relCoords(x, y, z) {
    const b = S.b, m = b.marker;
    const dx = x - m[0], dy = y - m[1], dz = z - m[2];
    const t = FACINGS.indexOf(S.facing);
    const [rx, rz] = rotXZ(dx, dz, t);
    let abs = null;
    if (b.world) {
      const wt = FACINGS.indexOf(b.world.facing);
      const [wx, wz] = rotXZ(dx, dz, wt);
      const o = worldOrigin(b);
      abs = [o[0] + wx, o[1] + dy, o[2] + wz];
    }
    return { local: [dx, dy, dz], cmd: [rx, dy, rz], abs };
  }
  function worldOrigin(b) {
    const w = b.world;
    const grade = w.grade != null ? w.grade : S.world ? S.world.terrain.grade : 64;
    return [w.pos[0], w.y != null ? w.y : grade + 1, w.pos[1]];
  }
  function updateHover() {
    const ro = $("#readout");
    if (!S.mouse || drag && drag.moved) return;
    const h = pick(S.mouse.x, S.mouse.y);
    S.hover = h;
    if (!h) { outline.visible = false; ro.innerHTML = measureText(); return; }
    outline.visible = true;
    outline.position.set(h.x + 0.5, h.y + 0.5, h.z + 0.5);
    const v = cellInfo(h.x, h.y, h.z);
    if (S.mode === "world") {
      const bld = buildAt(h.x, h.z);
      ro.innerHTML = `<b>${v ? v.def.name : ""}</b> &nbsp; X ${h.x} Y ${h.y} Z ${h.z}` + (bld ? `<br>${bld.title} — click to open` : "");
      return;
    }
    const rc = relCoords(h.x, h.y, h.z);
    const props = v && Object.keys(v.props).length ? " " + Object.entries(v.props).map(([a, b]) => `${a}=${b}`).join(" ") : "";
    const c = S.cells.get(h.x + "," + h.y + "," + h.z);
    const step = c ? S.b.steps[c.step - 1].title : "ground";
    ro.innerHTML = `<b>${v ? v.def.name : "?"}</b><span style="color:var(--dim)">${props}</span><br>` +
      `from marker: <b>${rc.local.join(", ")}</b> &nbsp;(x east, y up, z south)<br>` +
      `command (${S.facing}): <code>~${rc.cmd[0]} ~${rc.cmd[1]} ~${rc.cmd[2]}</code>` +
      (rc.abs ? `<br>world: ${rc.abs.join(" ")}` : "") + `<br>step: ${step}` + measureText(true);
  }
  function buildAt(x, z) {
    return S.world && S.world.builds.find((b) => x >= b.rect[0] && x <= b.rect[2] && z >= b.rect[1] && z <= b.rect[3]);
  }

  // ---------------------------------------------------------------- measure
  function toggleMeasure() {
    S.measure = { on: !S.measure.on, a: null, b: null };
    measureLine.visible = false;
    syncUI();
    toast(S.measure.on ? "Measure: click two blocks" : "Measure off");
  }
  function measureText(br) {
    const M = S.measure;
    if (!M.on) return "";
    if (!M.a) return (br ? "<br>" : "") + "measure: click first block";
    if (!M.b) return (br ? "<br>" : "") + `measure: from ${M.a.join(",")} — click second block`;
    const d = M.b.map((v, i) => v - M.a[i]);
    const span = d.map((v) => Math.abs(v) + 1);
    return (br ? "<br>" : "") + `measure: Δ ${d.join(", ")} · span ${span.join(" × ")} blocks · ${Math.hypot(...d).toFixed(2)} m`;
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

  function snapshot() {
    return { put: new Map(S.edits.put), remove: new Set(S.edits.remove), cells: null };
  }
  function changeCells(changes, label) {
    // changes: [[key, newCell|null]]  (cells in the build's local frame)
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
    const after = { edits: snapshot(), cells: changes };
    S.undo.push({ before, after, label });
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
  function breakBlock(h) {
    const k = K3(h.x, h.y, h.z);
    if (S.cells.has(k)) changeCells(groupCells(k).map((kk) => [kk, null]), "break");
    else if (h.y < 0) changeCells([[k, { v: pal.variant("air"), step: curStep(), group: 0 }]], "dig");
  }
  function curStep() { return Math.max(1, Math.min(S.step, S.b.steps.length)); }
  function lookDir() {
    const d = dirVec(S.yaw, 0);
    let f = Math.abs(d.x) > Math.abs(d.z) ? (d.x > 0 ? "east" : "west") : (d.z > 0 ? "south" : "north");
    for (let i = 0; i < S.rot; i++) f = FACINGS[(FACINGS.indexOf(f) + 1) % 4];
    return f;
  }
  function placeBlock(h) {
    const key = S.hotbar[S.slot];
    const def = pal.def(key);
    if (!def) return;
    const n = h.n;
    const x = h.x + n[0], y = h.y + n[1], z = h.z + n[2];
    const free = (xx, yy, zz) => { const v = cellInfo(xx, yy, zz); return !v || v.flags.walk && v.shape !== "door" && v.shape !== "ladder"; };
    if (!free(x, y, z)) return toast("blocked");
    const props = {};
    const look = lookDir();
    const faceDir = n[0] > 0 ? "east" : n[0] < 0 ? "west" : n[2] > 0 ? "south" : n[2] < 0 ? "north" : n[1] > 0 ? "up" : "down";
    const hitY = (() => { // where on the face the cursor hit (for slabs/stairs)
      const r = ray.ray; const p = r.origin.clone().addScaledVector(r.direction, h.t); return p.y - Math.floor(p.y);
    })();
    const P = def.props;
    if ("facing" in P) {
      if (def.shape === "ladder" || def.shape === "torch") {
        if (faceDir === "down") return toast("can't attach there");
        props.facing = faceDir;
        if (def.shape === "ladder" && faceDir === "up") return toast("ladders go on walls");
      } else if (["chest", "cube", "campfire"].includes(def.shape) && key !== "barrel") props.facing = MC.OPP[look];
      else if (key === "barrel") props.facing = "up";
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
      const lo = Object.assign({}, props, { upper: false }), up = Object.assign({}, props, { upper: true });
      changes.push([K3(x, y, z), { v: pal.variant(key, lo), step, group: g }], [K3(x, y + 1, z), { v: pal.variant(key, up), step, group: g }]);
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
      const s = el("div", { class: "slot" + (i === S.slot ? " sel" : ""), title: v.def.name, onclick: () => { S.slot = i; renderHotbar(); } },
        atlas.swatch(v.tiles[4], 32), el("span", { class: "num" }, String(i + 1)));
      hb.append(s);
    });
  }
  let pkCat = "all";
  function togglePicker(open) {
    $("#picker").classList.toggle("open", open);
    if (open) { renderPicker(); $("#pk-search").focus(); }
    else canvas.focus();
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
      }, atlas.swatch(v.tiles[b.shape === "cube" || b.shape === "log" ? 4 : 4], 32)));
    }
  }
  $("#pk-search").addEventListener("input", renderPicker);
  $("#pk-search").addEventListener("keydown", (e) => { if (e.key === "Escape") togglePicker(false); });

  // ---------------------------------------------------------------- UI
  function setStatus(t, live) { const s = $("#status"); s.textContent = t; s.classList.toggle("live", !!live); }
  let toastT = null;
  function toast(t) {
    const e = $("#toast");
    e.textContent = t; e.style.display = "block";
    clearTimeout(toastT);
    toastT = setTimeout(() => (e.style.display = "none"), 1400);
  }
  function setStep(s) { if (!S.b) return; S.step = Math.max(1, Math.min(S.b.steps.length, s)); remesh(); syncPane(); }
  function setCut(c) { if (!S.b) return; S.cut = Math.max(S.bounds.y1, Math.min(S.bounds.y2, c)); remesh(); syncPane(); }
  function updateStepUI() {
    if (!S.b) return;
    const st = $("#step"), ct = $("#cut");
    st.min = 1; st.max = S.b.steps.length; st.value = S.step;
    const s = S.b.steps[S.step - 1];
    $("#step-label").textContent = `${S.step}/${S.b.steps.length} ${s.title} (+${S.b.counts.by_step[s.key] || 0})`;
    ct.min = S.bounds.y1; ct.max = S.bounds.y2; ct.value = S.cut;
    $("#cut-label").textContent = S.cut >= S.bounds.y2 ? "all layers" : `up to y=${S.cut}`;
  }
  $("#step").addEventListener("input", (e) => setStep(+e.target.value));
  $("#cut").addEventListener("input", (e) => setCut(+e.target.value));
  $("#opt-hl").addEventListener("change", (e) => { S.opts.hl = e.target.checked; S.b && remesh(); });
  $("#opt-ghost").addEventListener("change", (e) => { S.opts.ghost = e.target.checked; S.b && remesh(); });
  $("#opt-terrain").addEventListener("change", (e) => { S.opts.terrain = e.target.checked; S.b && remesh(); });
  document.querySelectorAll("#modes button").forEach((b) => b.addEventListener("click", () => {
    const m = b.dataset.mode;
    if (m === "world") navigate(null, "world");
    else if (S.b) { S.mode = m; navigate(S.b.name, m, true); }
    else { const n = $("#build-select").value; if (n) navigate(n, m); }
  }));
  document.querySelectorAll("#times button").forEach((b) => b.addEventListener("click", () => setTime(b.dataset.time)));
  $("#t-frame").addEventListener("click", () => viewPreset("overview"));
  $("#t-labels").addEventListener("click", () => { S.labels = !S.labels; syncUI(); });
  $("#t-measure").addEventListener("click", toggleMeasure);
  $("#t-panel").addEventListener("click", () => { S.panel = !S.panel; syncUI(); });
  $("#t-help").addEventListener("click", () => $("#help").classList.toggle("open"));
  $("#build-select").addEventListener("change", (e) => e.target.value && navigate(e.target.value, S.mode === "edit" ? "edit" : "build"));

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
    if (!name || mode === "world") { if (!EMBED) return openWorld(); }
    if (keep && S.b && S.b.name === name) { S.mode = mode; syncUI(); remesh(); return; }
    await openBuild(name, mode === "edit" ? "edit" : "build");
  }

  function syncUI() {
    document.querySelectorAll("#modes button").forEach((b) => {
      b.classList.toggle("on", b.dataset.mode === S.mode);
      if (EMBED && b.dataset.mode === "world") b.style.display = "none";
    });
    $("#t-labels").classList.toggle("on", S.labels);
    $("#t-measure").classList.toggle("on", S.measure.on);
    $("#t-panel").classList.toggle("on", S.panel);
    $("#side").classList.toggle("hidden", !S.panel);
    $("#bottom").style.display = S.mode === "world" ? "none" : "grid";
    $("#bottom").classList.toggle("wide", !S.panel);
    $("#hotbar").classList.toggle("on", S.mode === "edit");
    $("#crosshair").style.display = "none";
    if (S.mode === "edit") renderHotbar();
    if (S.b) $("#build-select").value = S.b.name;
    areaBox.visible = areaBox.visible && S.mode !== "world";
    renderTabs();
  }

  // ---------------------------------------------------------------- side panel
  const TABS = {
    world: ["Builds", "World"],
    build: ["Steps", "Plan", "Blocks", "Commands", "Setup", "Areas", "Checks"],
    edit: ["Edit", "Steps", "Plan", "Blocks", "Commands", "Setup", "Areas", "Checks"],
  };
  function renderTabs() {
    const tabs = TABS[S.mode];
    if (!tabs.includes(S.tab)) S.tab = tabs[0];
    const t = $("#tabs");
    t.innerHTML = "";
    for (const name of tabs) t.append(el("button", { class: name === S.tab ? "on" : "", onclick: () => { S.tab = name; renderTabs(); } }, name));
    syncPane();
  }
  function syncPane() {
    const p = $("#pane");
    const keepScroll = p.dataset.tab === S.tab ? p.scrollTop : 0;
    p.innerHTML = "";
    p.dataset.tab = S.tab;
    const fn = PANES[S.tab];
    if (fn) fn(p);
    p.scrollTop = keepScroll;
  }
  const swatchFor = (key) => {
    const v = pal.v(pal.variant(key));
    const c = atlas.swatch(v.tiles[4], 18);
    c.className = "sw";
    return c;
  };
  const PANES = {
    Builds(p) {
      p.append(el("h3", {}, "Builds in the world"));
      for (const b of S.world.builds) {
        p.append(el("div", { class: "card" },
          el("div", { class: "row space" }, el("b", {}, b.title), el("button", { onclick: () => navigate(b.name, "build") }, "Open")),
          el("div", { class: "meta" }, `${b.name} · facing ${b.facing} · marker at ${b.origin.join(" ")} · ${b.count} cells`),
          el("div", { class: "row", style: "margin-top:6px" }, el("button", { onclick: () => viewPreset("build:" + b.name) }, "Fly to"))));
      }
    },
    World(p) {
      const t = S.world.terrain;
      p.append(el("h3", {}, "Terrain"),
        el("div", { class: "card" }, `Grade (grass) Y ${t.grade} · sea level ${t.sea_level} · bounds ${t.bounds.join(", ")}`),
        el("h4", {}, "Water"), ...t.water.map((w) => el("div", { class: "card" }, `${w.name}: ${w.rect.join(", ")} · surface ${w.surface} · depth ${w.depth}`)),
        el("h4", {}, "Problems"), ...(S.world.problems.length ? S.world.problems.map((q) => el("div", { class: "card lvl-error" }, q.msg)) :
          [el("div", { class: "card lvl-ok" }, "No collisions between builds.")]),
        el("div", { class: "meta" }, "Edit world/world.json to move or turn builds; the view reloads."));
    },
    Steps(p) {
      const b = S.b;
      p.append(el("h3", {}, "Steps"));
      const tb = el("table", {}, el("tr", {}, el("th", {}, "#"), el("th", {}, "Step"), el("th", { class: "n" }, "Blocks")));
      b.steps.forEach((s, i) => {
        tb.append(el("tr", { class: "steprow" + (i + 1 === S.step ? " on" : ""), onclick: () => setStep(i + 1) },
          el("td", {}, String(i + 1)), el("td", {}, el("b", {}, s.title), el("div", { class: "meta" }, s.desc)),
          el("td", { class: "n" }, String(b.counts.by_step[s.key]))));
      });
      const tot = b.counts.total, pct = b.target ? ((100 * (tot - b.target)) / b.target).toFixed(0) : 0;
      tb.append(el("tr", {}, el("td"), el("td", {}, el("b", {}, "Total")), el("td", { class: "n" }, el("b", {}, String(tot)))));
      p.append(tb, el("div", { class: "meta", style: "margin-top:6px" },
        `Target ${b.target} (${pct >= 0 ? "+" : ""}${pct}%). Hidden below-grade fill not counted: ${b.counts.hidden}.`),
        el("div", { class: "meta" }, `Edits merged: ${b.edits.put || 0} placed, ${b.edits.remove || 0} removed. Built ${b.built}.`),
        el("h4", {}, "Views"),
        el("div", { class: "row", style: "flex-wrap:wrap" }, ...["overview", "front", "back", "left", "right", "top"].map((v) =>
          el("button", { onclick: () => viewPreset(v) }, v))));
      if (b.description) p.append(el("h4", {}, "About"), el("div", { class: "meta" }, b.description));
    },
    Plan(p) {
      const B = S.bounds;
      const y = Math.min(S.cut, B.y2);
      p.append(el("h3", {}, `Plan: layer y=${y}`),
        el("div", { class: "row" }, el("button", { onclick: () => setCut(S.cut - 1) }, "▼ down"), el("button", { onclick: () => setCut(S.cut + 1) }, "▲ up"),
          el("span", { class: "meta" }, "Uses the cut height. Faded = below this layer.")));
      const w = B.x2 - B.x1 + 3, d = B.z2 - B.z1 + 3;
      const s = Math.max(4, Math.floor(336 / Math.max(w, d)));
      const c = el("canvas", { id: "plan-canvas", width: w * s, height: d * s });
      const g = c.getContext("2d");
      g.fillStyle = "#3d5a2a"; g.fillRect(0, 0, c.width, c.height);
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
        const f = t.y === y ? 1 : Math.max(0.25, 0.6 - (y - t.y) * 0.06);
        g.fillStyle = `rgb(${col[0] * f | 0},${col[1] * f | 0},${col[2] * f | 0})`;
        g.fillRect(X(x), Z(z), s, s);
      }
      for (const k of S.b.keep_zones) { g.fillStyle = "rgba(60,110,220,0.45)"; g.fillRect(X(k.box[0]), Z(k.box[1]), (k.box[2] - k.box[0] + 1) * s, (k.box[3] - k.box[1] + 1) * s); }
      g.strokeStyle = "rgba(0,0,0,0.25)"; g.lineWidth = 1;
      const m = S.b.marker;
      for (let x = B.x1 - 1; x <= B.x2 + 2; x++) { g.strokeStyle = (x - m[0]) % 5 ? "rgba(0,0,0,0.2)" : "rgba(0,0,0,0.55)"; g.beginPath(); g.moveTo(X(x), 0); g.lineTo(X(x), c.height); g.stroke(); }
      for (let z = B.z1 - 1; z <= B.z2 + 2; z++) { g.strokeStyle = (z - m[2]) % 5 ? "rgba(0,0,0,0.2)" : "rgba(0,0,0,0.55)"; g.beginPath(); g.moveTo(0, Z(z)); g.lineTo(c.width, Z(z)); g.stroke(); }
      g.strokeStyle = "#fff"; g.lineWidth = 2;
      g.strokeRect(X(0), Z(0), S.b.footprint[0] * s, S.b.footprint[1] * s);
      g.fillStyle = "#ffcc00"; g.beginPath(); g.arc(X(m[0]) + s / 2, Z(m[2]) + s / 2, s / 2.5, 0, 7); g.fill();
      g.fillStyle = "#fff"; g.font = "11px sans-serif"; g.fillText("N ↑", 4, 12);
      const info = el("div", { class: "meta" }, "hover the plan for coordinates");
      c.addEventListener("mousemove", (e) => {
        const r = c.getBoundingClientRect();
        const x = Math.floor(((e.clientX - r.left) / r.width) * c.width / s) + B.x1 - 1;
        const z = Math.floor(((e.clientY - r.top) / r.height) * c.height / s) + B.z1 - 1;
        const cc = S.cells.get(x + "," + y + "," + z);
        const rc = relCoords(x, y, z);
        info.innerHTML = `from marker <b>${rc.local.join(", ")}</b> · command <code>~${rc.cmd.join(" ~")}</code> · ${cc ? pal.v(cc.v).def.name : "empty"}`;
      });
      p.append(c, info);
    },
    Blocks(p) {
      const b = S.b;
      const which = S.blocksView || "total";
      p.append(el("h3", {}, "Inventory"),
        el("div", { class: "row" }, ...["total", "this step"].map((w) => el("button", { class: w === which ? "on" : "", onclick: () => { S.blocksView = w; syncPane(); } }, w))));
      const s = b.steps[S.step - 1];
      const counts = which === "total" ? b.counts.by_block : b.counts.by_step_block[s.key];
      const tb = el("table", {}, el("tr", {}, el("th"), el("th", {}, which === "total" ? "Block (all steps)" : `Block (step ${S.step}: ${s.title})`),
        el("th", { class: "n" }, "Blocks"), el("th", { class: "n" }, "Items"), el("th", { class: "n" }, "Stacks")));
      let total = 0;
      for (const [k, n] of Object.entries(counts).sort((a, c) => c[1] - a[1])) {
        const items = Math.ceil(n / (pal.def(k).item_cells || 1));
        total += n;
        tb.append(el("tr", {}, el("td", {}, swatchFor(k)), el("td", {}, pal.def(k).name), el("td", { class: "n" }, String(n)),
          el("td", { class: "n" }, String(items)), el("td", { class: "n" }, items >= 64 ? `${(items / 64) | 0}+${items % 64}` : "")));
      }
      tb.append(el("tr", {}, el("td"), el("td", {}, el("b", {}, "Total")), el("td", { class: "n" }, el("b", {}, String(total))), el("td"), el("td")));
      p.append(tb, el("div", { class: "meta" }, "Doors, beds and tall flowers use two cells per item. Counts come from the last rebuild (edits included)."));
    },
    Commands(p) {
      const b = S.b;
      p.append(el("h3", {}, "Commands"), facingPicker());
      const c = b.commands[S.facing];
      p.append(el("div", { class: "meta" }, `${c.total} commands to build (prep + steps + entities). Functions live in ${b.name}/${S.facing}/.`));
      const order = ["setup", "test_blocks", ...c.run_order, "build", "cleanup"];
      for (const f of order) {
        const lines = c.files[f];
        if (!lines) continue;
        const pre = el("pre", { style: "display:none" }, lines.join("\n"));
        const call = `/function ${b.name}/${S.facing}/${f}`;
        p.append(el("div", { class: "card" },
          el("div", { class: "row space" }, el("code", {}, call),
            el("span", { class: "row" }, el("span", { class: "meta" }, `${lines.filter((l) => l && !l.startsWith("#")).length} cmds`),
              el("button", { onclick: () => (pre.style.display = pre.style.display === "none" ? "block" : "none") }, "show"),
              el("button", { onclick: () => copy(call) }, "copy"))), pre));
      }
    },
    Setup(p) {
      const b = S.b;
      const plat = b.config.platform === "pc" ? "PC" : `phone (${b.config.phone_os || "ios"})`;
      p.append(el("h3", {}, "Get it into your Realm"),
        el("div", { class: "meta" }, `Platform: ${plat} — set "platform" in config.json. Pack: ${b.mcpack} v${b.pack_version}.`));
      const ol = el("ol", {});
      for (const s of b.install) ol.append(el("li", {}, s));
      p.append(ol, el("h4", {}, "Build it in game"), facingPicker());
      const ns = `${b.name}/${S.facing}`;
      const steps = [
        ["Stand on the marker spot (the yellow square), or use the positioned command below.", null],
        ["Load the site, then wait about 5 seconds:", `/function ${ns}/setup`],
        ["Optional: check every block shows up correctly (a strip appears in front of you):", `/function ${ns}/test_blocks`],
        ["Build everything:", `/function ${ns}/build`],
        ["Or step by step:", [`/function ${ns}/prep`, ...b.commands[S.facing].run_order.slice(1).map((f) => `/function ${ns}/${f}`)].join("\n")],
        ["Tidy up (test strip, dropped items, ticking area):", `/function ${ns}/cleanup`],
      ];
      for (const [t, cmd] of steps) {
        p.append(el("div", { class: "card" }, t, cmd ? el("pre", {}, cmd) : null, cmd ? el("button", { onclick: () => copy(cmd) }, "copy") : null));
      }
      if (b.world) {
        const o = worldOrigin(b);
        const cmd = `/execute positioned ${o.join(" ")} run function ${b.name}/${b.world.facing}/setup\n/execute positioned ${o.join(" ")} run function ${b.name}/${b.world.facing}/build`;
        p.append(el("h4", {}, "At its world.json position"),
          el("div", { class: "card" }, `Marker at ${o.join(" ")}, facing ${b.world.facing} (matches the World view):`, el("pre", {}, cmd),
            el("button", { onclick: () => copy(cmd) }, "copy")));
      }
      p.append(el("div", { class: "meta" }, "Cheats must be on. The front of the build faces the chosen direction; the marker is where the player's feet are."));
    },
    Areas(p) {
      const b = S.b;
      p.append(el("h3", {}, "Areas"));
      for (const a of b.areas) {
        let n = 0;
        for (const [k, c] of S.cells) {
          const [x, , z] = k.split(",").map(Number);
          const inside = x >= a.box[0] && x <= a.box[2] && z >= a.box[1] && z <= a.box[3] &&
            (!a.ring || x === a.box[0] || x === a.box[2] || z === a.box[1] || z === a.box[3]);
          if (inside && pal.v(c.v).key !== "air") n++;
        }
        const w = a.box[2] - a.box[0] + 1, d = a.box[3] - a.box[1] + 1;
        p.append(el("div", { class: "card" + (S.areaOn === a.key ? " on" : "") },
          el("div", { class: "row space" }, el("b", {}, a.title), el("button", { onclick: () => { focusArea(a.key); syncPane(); } }, "Focus")),
          el("div", {}, a.desc),
          el("div", { class: "meta" }, `${w} × ${d}${a.ring ? " (edge)" : ""} · ${n} blocks · from marker ${a.box[0] - b.marker[0]},${a.box[1] - b.marker[2]} to ${a.box[2] - b.marker[0]},${a.box[3] - b.marker[2]}`)));
      }
      if (b.keep_zones.length) {
        p.append(el("h4", {}, "Keep-zones (never touched)"));
        for (const k of b.keep_zones) p.append(el("div", { class: "card" }, `${k.note || k.what}: ${k.box.join(", ")}`));
      }
    },
    Checks(p) {
      const b = S.b;
      const errs = b.checks.filter((c) => c.level === "error").length, warns = b.checks.filter((c) => c.level === "warn").length;
      p.append(el("h3", {}, "Checks"), el("div", { class: errs ? "lvl-error" : warns ? "lvl-warn" : "lvl-ok" },
        errs ? `${errs} errors, ${warns} warnings` : warns ? `${warns} warnings` : "All checks pass."));
      for (const c of b.checks) {
        const card = el("div", { class: "card" }, el("span", { class: "lvl-" + c.level }, c.level.toUpperCase()), " ", el("b", {}, c.check), " ", c.msg);
        if (c.where && c.where.length) card.append(el("div", {}, el("button", { onclick: () => showWhere(c.where) }, "show where")));
        p.append(card);
      }
    },
    Edit(p) {
      const b = S.b;
      p.append(el("h3", {}, "Edit mode"),
        el("div", {}, "Left click: break · Right click: place · Middle click: pick block · E: block picker · R: rotate · Ctrl+Z / Ctrl+Y"),
        el("div", { class: "meta", style: "margin:6px 0" }, `New blocks go into step ${curStep()}: ${b.steps[curStep() - 1].title} (move the step slider to choose).`),
        el("div", { class: "row" }, el("button", { onclick: () => togglePicker(true) }, "Open picker (E)"),
          el("button", { onclick: undo }, "Undo"), el("button", { onclick: redo }, "Redo")),
        el("h4", {}, "Saved edits"),
        el("div", { class: "card" }, `${S.edits.put.size} placed · ${S.edits.remove.size} removed`,
          el("div", { class: "meta" }, EMBED ? "Static page: edits stay in this page." : `Saved to edits/${b.name}.json and merged into the build, the checks and the pack.`)));
      if (EMBED) p.append(el("button", { onclick: downloadEdits }, "Download edits JSON"));
      else p.append(el("button", { onclick: clearEdits }, "Discard all edits"));
    },
  };
  function facingPicker() {
    return el("div", { class: "row", style: "margin:6px 0" }, el("span", { class: "meta" }, "Front faces:"),
      ...FACINGS.map((f) => el("button", { class: f === S.facing ? "on" : "", onclick: () => { S.facing = f; syncPane(); } },
        f + (S.b.world && S.b.world.facing === f ? " *" : ""))));
  }
  function showWhere(list) {
    checkMarks.clear();
    for (const w of list) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(1.06, 1.06, 1.06), new THREE.MeshBasicMaterial({ color: 0xff3030, wireframe: true, depthTest: false }));
      m.position.set(w[0] + 0.5, w[1] + 0.5, w[2] + 0.5);
      m.renderOrder = 11;
      checkMarks.add(m);
    }
    if (list.length) {
      const w = list[0];
      frame([w[0] - 4, w[1] - 2, w[2] - 4], [w[0] + 4, w[1] + 3, w[2] + 4], S.yaw, -0.5);
    }
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
    const a = el("a", { href: URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" })), download: `${S.b.name}.json` });
    a.click();
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
      if (S.mode === "world" && S.world) {
        for (const b of S.world.builds) {
          let top = S.world.terrain.grade + 2;
          for (let i = 1; i < b.cells.length; i += 4) top = Math.max(top, b.cells[i]);
          items.push({ text: b.title, cls: "label build", p: [(b.rect[0] + b.rect[2] + 1) / 2, top + 2.5, (b.rect[1] + b.rect[3] + 1) / 2] });
        }
      } else if (S.b) {
        for (const a of S.b.areas) {
          if (a.ring) continue;
          let top = 0;
          for (const k of S.cells.keys()) {
            const [x, y, z] = k.split(",").map(Number);
            if (x >= a.box[0] && x <= a.box[2] && z >= a.box[1] && z <= a.box[3] && y <= S.cut) top = Math.max(top, y);
          }
          items.push({ text: a.title, cls: "label", p: [(a.box[0] + a.box[2] + 1) / 2, top + 1.6, (a.box[1] + a.box[3] + 1) / 2] });
        }
      }
    }
    const w = window.innerWidth, h = window.innerHeight;
    items.forEach((it, i) => {
      let e = labelPool[i];
      if (!e) { e = el("div", { class: "label" }); labelsEl.append(e); labelPool.push(e); }
      const wp = new THREE.Vector3(...it.p);
      const v = wp.clone().project(camera);
      const on = v.z < 1 && Math.abs(v.x) < 1.1 && Math.abs(v.y) < 1.1;
      e.style.display = on ? "block" : "none";
      if (!on) return;
      if (vol && (it.occ == null || (labelT | 0) % 4 === i % 4)) {   // dim labels hidden behind blocks
        const d = wp.clone().sub(camera.position), dist = d.length();
        const h = MC.raycast(vol, pal, camera.position, d.normalize(), dist);
        it.occ = h && h.t < dist - 1.5;
        labelOcc[i] = it.occ;
      }
      e.style.opacity = (it.occ != null ? it.occ : labelOcc[i]) ? 0.35 : 1;
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
    const cur = sel.value;
    sel.innerHTML = "";
    sel.append(el("option", { value: "" }, "open build…"));
    for (const n of names) sel.append(el("option", { value: n }, n));
    sel.value = S.b ? S.b.name : cur;
  }

  // ---------------------------------------------------------------- loop
  let last = performance.now(), hoverT = 0;
  function loop(now) {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    moveCamera(dt);
    solidMat.uniforms.time.value = now / 1000;
    sky.position.copy(camera.position);
    if ((hoverT += dt) > 0.05) { hoverT = 0; updateHover(); }
    renderer.render(scene, camera);
    labelT++;
    updateLabels();
    requestAnimationFrame(loop);
  }

  // ---------------------------------------------------------------- screenshot / automation API
  Object.assign(window.studio, {
    setTime, viewPreset, setStep, setCut, focusArea,
    open: (name, mode) => navigate(name, mode || "build"),
    world: () => navigate(null, "world"),
    ui: (on) => document.body.classList.toggle("noui", !on),
    frameNow: () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
    pickAt: (x, y) => pick(x, y),
    place: (h) => placeBlock(h), breakAt: (h) => breakBlock(h), undo, redo,
    editState: () => ({ put: [...S.edits.put.values()], remove: [...S.edits.remove] }),
    setSlot: (i, key) => { S.slot = i; if (key) S.hotbar[i] = key; renderHotbar(); },
    look: (yaw, pitch, pos) => { S.yaw = yaw; S.pitch = pitch; if (pos) S.pos.set(...pos); },
  });

  async function boot() {
    try {
      resize();
      const pj = await api.palette();
      pal = new MC.Palette(pj, atlas);
      setTime(new URL(location.href).searchParams.get("time") || "day");
      if (new URL(location.href).searchParams.get("ui") === "0") document.body.classList.add("noui");
      if (!EMBED) { S.world = await api.world().catch(() => null); await refreshBuildList(); }
      else { $("#build-select").style.display = "none"; }
      await route();
      live();
      if (EMBED) setStatus("static export · " + (EMBED.exported || ""));
      S.ready = window.studio.ready = true;
      requestAnimationFrame(loop);
    } catch (e) {
      setStatus("error: " + e.message);
      console.error(e);
      window.studio.error = String(e);
    }
  }
  boot();
})();
