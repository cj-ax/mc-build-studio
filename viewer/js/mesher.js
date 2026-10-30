// Voxel volume, Minecraft-style lighting (sky + block light, smooth lighting, AO)
// and chunked mesh generation for every block shape in the palette.
//
// Meshes are built once per build. Every vertex carries [step, cell y, atlas tile] so the
// viewer hides later steps, ghosts them and cuts the build away with shader uniforms instead
// of remeshing. A face is culled only against an opaque neighbour of the same or an earlier
// step, so each step looks solid on its own. Flat-lit cube faces are greedy-merged.
(function () {
  const MC = (window.MC = window.MC || {});
  const DIRV = { north: [0, -1], east: [1, 0], south: [0, 1], west: [-1, 0] };
  const LEFT = { north: "west", west: "south", south: "east", east: "north" };
  const RIGHT = { west: "north", south: "west", east: "south", north: "east" };
  const OPP = { north: "south", south: "north", east: "west", west: "east" };
  // faces: 0 +x east, 1 -x west, 2 +y up, 3 -y down, 4 +z south, 5 -z north
  const FN = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
  const FACE_DIR = ["east", "west", "up", "down", "south", "north"];
  const ROT = { north: 0, east: 1, south: 2, west: 3 };
  MC.DIRV = DIRV; MC.LEFT = LEFT; MC.OPP = OPP; MC.FACE_DIR = FACE_DIR;
  MC.CHUNK = 32;      // chunk columns
  MC.SECTION = 16;    // chunk layers per mesh section
  const AO = [0.42, 0.6, 0.8, 1];

  // ---------------------------------------------------------------- palette / variants
  class Palette {
    constructor(json, atlas) {
      this.blocks = json.blocks;
      this.atlas = atlas;
      this.variants = [];
      this.index = new Map();
      this._tab = null;
    }
    def(key) { return this.blocks[key]; }
    variant(key, props) {
      const def = this.blocks[key];
      if (!def) throw new Error("unknown block " + key);
      const full = Object.assign({}, def.props, props || {});
      const k = key + JSON.stringify(Object.keys(full).sort().map((p) => [p, full[p]]));
      if (this.index.has(k)) return this.index.get(k);
      const f = def.flags;
      const v = {
        id: this.variants.length, key, props: full, def, shape: def.shape, flags: f,
        light: def.light || 0,
        opaque: !!f.opaque,
        opacity: f.opaque || f.lightblock ? 15 : def.shape === "leaves" ? 1 : def.shape === "water" ? 2 : 0,
        tiles: [0, 1, 2, 3, 4, 5].map((face) => this.atlas.get(texSpec(def, face, full, key))),
      };
      v.cube = ["cube", "log", "glass", "leaves"].includes(def.shape);
      v.selfCull = def.shape === "glass" || def.shape === "leaves";
      v.cutout = v.tiles.some((t) => this.atlas.alpha[t]);
      v.color = def.color;
      this.variants.push(v);
      this.index.set(k, v.id);
      this._tab = null;
      return v.id;
    }
    v(id) { return this.variants[id]; }
    // lookup tables indexed by volume id (variant id + 1, 0 = air)
    table() {
      if (this._tab && this._tab.n === this.variants.length) return this._tab;
      const n = this.variants.length, t = { n, opq: new Uint8Array(n + 1), opacity: new Uint8Array(n + 1), light: new Uint8Array(n + 1),
        air: new Uint8Array(n + 1), water: new Uint8Array(n + 1), occ: new Uint8Array(n + 1), path: new Uint8Array(n + 1) };
      t.air[0] = 1;
      for (const v of this.variants) {
        t.opq[v.id + 1] = v.opaque ? 1 : 0;
        t.opacity[v.id + 1] = v.opacity;
        t.light[v.id + 1] = v.light;
        t.air[v.id + 1] = v.shape === "air" ? 1 : 0;
        t.water[v.id + 1] = v.shape === "water" ? 1 : 0;
        t.occ[v.id + 1] = v.shape === "slab" || v.shape === "stair" ? 1 : 0;
        t.path[v.id + 1] = v.shape === "path" ? 1 : 0;
      }
      return (this._tab = t);
    }
  }
  function texSpec(def, face, props, key) {
    const t = def.tex;
    if (def.shape === "log") {
      const axis = props.axis || "y";
      const end = axis === "y" ? face === 2 || face === 3 : axis === "x" ? face <= 1 : face >= 4;
      return end ? t.end || t.all || t.side : t.side || t.all;
    }
    if (def.shape === "bed" && face === 2 && props.head) return ["pillow"].concat(t.top.slice(1));
    if (face === 2) return t.top || t.all || t.side;
    if (face === 3) return t.bottom || t.all || t.side || t.top;
    if (t.front && props.facing === FACE_DIR[face]) return t.front;
    return t.side || t.all || t.top;
  }
  MC.Palette = Palette;

  // ---------------------------------------------------------------- volume
  // ids: variant id + 1 (0 = air); step: 0 terrain, 1.. build steps; group: multi-cell blocks
  class Vol {
    constructor(x0, y0, z0, sx, sy, sz) {
      Object.assign(this, { x0, y0, z0, sx, sy, sz });
      const n = (this.n = sx * sy * sz);
      this.ids = new Uint16Array(n);
      this.step = new Uint8Array(n);
      this.group = new Int32Array(n);
    }
    inside(x, y, z) {
      return x >= this.x0 && y >= this.y0 && z >= this.z0 && x < this.x0 + this.sx && y < this.y0 + this.sy && z < this.z0 + this.sz;
    }
    idx(x, y, z) { return ((y - this.y0) * this.sz + (z - this.z0)) * this.sx + (x - this.x0); }
    at(x, y, z) { return this.inside(x, y, z) ? this.idx(x, y, z) : -1; }
    get(x, y, z) { return this.inside(x, y, z) ? this.ids[this.idx(x, y, z)] - 1 : -1; }
    set(x, y, z, vid, step = 0, group = 0) {
      if (!this.inside(x, y, z)) return;
      const i = this.idx(x, y, z);
      this.ids[i] = vid + 1; this.step[i] = step; this.group[i] = group;
    }
    clear(x, y, z) { if (this.inside(x, y, z)) { const i = this.idx(x, y, z); this.ids[i] = 0; this.step[i] = 0; this.group[i] = 0; } }
  }
  MC.Vol = Vol;

  // ---------------------------------------------------------------- lighting
  // growable FIFO of volume indices, shared by every light pass
  let Q = new Int32Array(1 << 16), qh = 0, qt = 0;
  function qpush(i) {
    if (qt === Q.length) {
      if (qh > Q.length >> 1) { Q.copyWithin(0, qh, qt); qt -= qh; qh = 0; }
      else { const nq = new Int32Array(Q.length * 2); nq.set(Q); Q = nq; }
    }
    Q[qt++] = i;
  }
  // Whole volume (box omitted), or relight the columns x1..x2, z1..z2 (volume-relative) in place:
  // light outside the box is kept and flows back in from its edge.
  function computeLight(vol, pal, light, box) {
    const { sx, sy, sz, n, ids } = vol;
    const layer = sx * sz;
    if (!light) light = { sky: new Uint8Array(n), blk: new Uint8Array(n), opac: new Uint8Array(n) };
    const { sky, blk, opac } = light;
    const T = pal.table();
    let x1 = 0, z1 = 0, x2 = sx - 1, z2 = sz - 1;
    if (box) { x1 = Math.max(0, box[0]); z1 = Math.max(0, box[1]); x2 = Math.min(sx - 1, box[2]); z2 = Math.min(sz - 1, box[3]); }
    for (let y = 0; y < sy; y++) for (let z = z1; z <= z2; z++) {
      let i = y * layer + z * sx + x1;
      for (let x = x1; x <= x2; x++, i++) { const id = ids[i]; opac[i] = T.opacity[id]; sky[i] = 0; blk[i] = T.light[id]; }
    }
    // sky: straight down from the top
    for (let z = z1; z <= z2; z++) for (let x = x1; x <= x2; x++) {
      let l = 15;
      for (let y = sy - 1; y >= 0; y--) {
        const i = y * layer + z * sx + x;
        if (opac[i] >= 15) break;
        l -= opac[i];
        if (l <= 0) break;
        sky[i] = l;
      }
    }
    // then sideways: seed only lit cells next to something darker
    qh = qt = 0;
    for (let y = 0; y < sy; y++) for (let z = z1; z <= z2; z++) for (let x = x1; x <= x2; x++) {
      const i = y * layer + z * sx + x, l = sky[i];
      if (l <= 1) continue;
      if ((x > 0 && sky[i - 1] < l - 1 && opac[i - 1] < 15) || (x < sx - 1 && sky[i + 1] < l - 1 && opac[i + 1] < 15) ||
        (z > 0 && sky[i - sx] < l - 1 && opac[i - sx] < 15) || (z < sz - 1 && sky[i + sx] < l - 1 && opac[i + sx] < 15) ||
        (y > 0 && sky[i - layer] < l - 1 && opac[i - layer] < 15) || (y < sy - 1 && sky[i + layer] < l - 1 && opac[i + layer] < 15)) qpush(i);
    }
    if (box) edgeSeeds(sky, x1, z1, x2, z2, sx, sy, sz);
    spread(sky, opac, sx, sy, sz);
    qh = qt = 0;
    for (let y = 0; y < sy; y++) for (let z = z1; z <= z2; z++) for (let x = x1; x <= x2; x++) { const i = y * layer + z * sx + x; if (blk[i]) qpush(i); }
    if (box) edgeSeeds(blk, x1, z1, x2, z2, sx, sy, sz);
    spread(blk, opac, sx, sy, sz);
    return light;
  }
  function edgeSeeds(L, x1, z1, x2, z2, sx, sy, sz) {
    const layer = sx * sz;
    for (let y = 0; y < sy; y++) {
      for (let z = z1; z <= z2; z++) {
        if (x1 > 0) { const i = y * layer + z * sx + x1 - 1; if (L[i] > 1) qpush(i); }
        if (x2 < sx - 1) { const i = y * layer + z * sx + x2 + 1; if (L[i] > 1) qpush(i); }
      }
      for (let x = x1 - 1; x <= x2 + 1; x++) {
        if (x < 0 || x >= sx) continue;
        if (z1 > 0) { const i = y * layer + (z1 - 1) * sx + x; if (L[i] > 1) qpush(i); }
        if (z2 < sz - 1) { const i = y * layer + (z2 + 1) * sx + x; if (L[i] > 1) qpush(i); }
      }
    }
  }
  function spread(L, opac, sx, sy, sz) {
    const layer = sx * sz;
    const go = (j, l) => {
      if (opac[j] >= 15) return;
      const nl = l - 1 - opac[j];
      if (nl > L[j]) { L[j] = nl; qpush(j); }
    };
    while (qh < qt) {
      const i = Q[qh++];
      const l = L[i];
      if (l <= 1) continue;
      const x = i % sx, z = ((i / sx) | 0) % sz, y = (i / layer) | 0;
      if (x > 0) go(i - 1, l);
      if (x < sx - 1) go(i + 1, l);
      if (z > 0) go(i - sx, l);
      if (z < sz - 1) go(i + sx, l);
      if (y > 0) go(i - layer, l);
      if (y < sy - 1) go(i + layer, l);
    }
    qh = qt = 0;
  }
  MC.computeLight = computeLight;

  // ---------------------------------------------------------------- geometry buffers
  // position f32x3, normal i8x3, local uv f32x2 (repeats per cell), light u8x3 (sky, block, AO),
  // meta i16x3 (step, cell y, atlas tile). Grown by doubling, reused between chunks.
  class Buf {
    constructor() { this.alloc(4096); }
    alloc(cap) {
      const o = this.cap ? this : null;
      this.cap = cap;
      const pos = new Float32Array(cap * 3), nrm = new Int8Array(cap * 3), uv = new Float32Array(cap * 2),
        lt = new Uint8Array(cap * 3), meta = new Int16Array(cap * 3), idx = new Uint32Array(cap * 1.5);
      if (o) { pos.set(o.pos); nrm.set(o.nrm); uv.set(o.uv); lt.set(o.lt); meta.set(o.meta); idx.set(o.idx); }
      Object.assign(this, { pos, nrm, uv, lt, meta, idx });
      if (!o) this.n = 0;
    }
    reset() { this.n = 0; }
    // P: 12 coords, S: 8 uv, LT: 12 bytes, f: face for the normal (-1: up, used by plants)
    quad(P, S, LT, f, step, cy, tile, flip) {
      if (this.n + 4 > this.cap) this.alloc(this.cap * 2);
      const b = this.n, nx = f < 0 ? 0 : FN[f][0] * 127, ny = f < 0 ? 127 : FN[f][1] * 127, nz = f < 0 ? 0 : FN[f][2] * 127;
      const pos = this.pos, uv = this.uv, lt = this.lt, nrm = this.nrm, meta = this.meta;
      for (let k = 0; k < 12; k++) { pos[b * 3 + k] = P[k]; lt[b * 3 + k] = LT[k]; }
      for (let k = 0; k < 8; k++) uv[b * 2 + k] = S[k];
      for (let k = 0; k < 4; k++) {
        const v = (b + k) * 3;
        nrm[v] = nx; nrm[v + 1] = ny; nrm[v + 2] = nz;
        meta[v] = step; meta[v + 1] = cy; meta[v + 2] = tile;
      }
      const ii = (b / 4) * 6, I = this.idx;
      if (flip) { I[ii] = b + 1; I[ii + 1] = b + 2; I[ii + 2] = b + 3; I[ii + 3] = b + 1; I[ii + 4] = b + 3; I[ii + 5] = b; }
      else { I[ii] = b; I[ii + 1] = b + 1; I[ii + 2] = b + 2; I[ii + 3] = b; I[ii + 4] = b + 2; I[ii + 5] = b + 3; }
      this.n += 4;
    }
    geometry(bounds) {
      if (!this.n) return null;
      const n = this.n, g = new THREE.BufferGeometry();
      const A = (arr, size, norm) => {
        const a = new THREE.BufferAttribute(arr, size, norm);
        a.onUpload(dropArray);
        return a;
      };
      g.setAttribute("position", A(this.pos.slice(0, n * 3), 3, false));
      g.setAttribute("normal", A(this.nrm.slice(0, n * 3), 3, true));
      g.setAttribute("uv", A(this.uv.slice(0, n * 2), 2, false));
      g.setAttribute("light", A(this.lt.slice(0, n * 3), 3, true));
      g.setAttribute("meta", A(this.meta.slice(0, n * 3), 3, false));
      const ni = n * 1.5;
      let ix;
      if (n > 65535) ix = this.idx.slice(0, ni);
      else { ix = new Uint16Array(ni); ix.set(this.idx.subarray(0, ni)); }
      g.setIndex(A(ix, 1, false));
      g.boundingBox = new THREE.Box3(new THREE.Vector3(bounds[0], bounds[1], bounds[2]), new THREE.Vector3(bounds[3], bounds[4], bounds[5]));
      g.boundingSphere = g.boundingBox.getBoundingSphere(new THREE.Sphere());
      return g;
    }
  }
  function dropArray() { this.array = null; }   // GPU keeps it; frees the JS copy

  // face corner positions for box b (unit coords) into out[12] at offset (x, y, z)
  // corner order per face as (x, y, z) picks from (lo, hi): 0 = lo, 1 = hi
  const FV = [
    [1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 1, 1], [0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0], [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 0],
    [0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1], [0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1], [1, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0]];
  const C12 = new Float32Array(12);
  function faceVerts(out, f, x0, y0, z0, x1, y1, z1, ox, oy, oz) {
    const F = FV[f];
    for (let k = 0; k < 12; k += 3) {
      const cx = F[k] ? x1 : x0, cy = F[k + 1] ? y1 : y0, cz = F[k + 2] ? z1 : z0;
      C12[k] = cx; C12[k + 1] = cy; C12[k + 2] = cz;
      out[k] = cx + ox; out[k + 1] = cy + oy; out[k + 2] = cz + oz;
    }
    return C12;
  }
  // texture coordinates (in tiles, from the top-left) for the unit-box corners c
  function faceST(out, f, c) {
    for (let k = 0; k < 4; k++) {
      const x = c[k * 3], y = c[k * 3 + 1], z = c[k * 3 + 2];
      let s, t;
      switch (f) {
        case 0: s = 1 - z; t = 1 - y; break;
        case 1: s = z; t = 1 - y; break;
        case 2: s = x; t = z; break;
        case 3: s = x; t = 1 - z; break;
        case 4: s = x; t = 1 - y; break;
        default: s = 1 - x; t = 1 - y;
      }
      out[k * 2] = s; out[k * 2 + 1] = t;
    }
  }
  // per face, per corner: the two in-plane neighbour offsets used for smooth light and AO
  const CORNER = FN.map((n, f) => {
    const box = faceVertsRaw(f);
    const t = [0, 1, 2].filter((a) => n[a] === 0);
    return [0, 1, 2, 3].map((k) => {
      const v = box.slice(k * 3, k * 3 + 3);
      const s1 = [0, 0, 0], s2 = [0, 0, 0];
      s1[t[0]] = v[t[0]] > 0.5 ? 1 : -1;
      s2[t[1]] = v[t[1]] > 0.5 ? 1 : -1;
      return [s1, s2];
    });
  });
  function faceVertsRaw(f) { const o = new Array(12); return Array.from(faceVerts(o, f, 0, 0, 0, 1, 1, 1, 0, 0, 0)); }

  // ---------------------------------------------------------------- mesher
  // kinds: 0 build, 1 terrain, 2 under (build face only terrain hides: x-ray), 3 / 4 behind (build / terrain
  // face only a later step hides: drawn while a step or the cut exposes it)
  const bufs = { solid: new Buf(), terrain: new Buf(), under: new Buf(), behind: new Buf(), bterrain: new Buf(), water: new Buf(),
    capS: new Buf(), capT: new Buf(), capW: new Buf() };   // cut caps: up faces the cell above hides, shown only at the cut layer
  const KIND = ["solid", "terrain", "under", "behind", "bterrain", "capS", "capT"];
  // neighbour sub-cubes (bit qx + 2 qz + 4 qy) that face back toward a face in direction f
  const FACEBITS = [0x55, 0xAA, 0x0F, 0xF0, 0x33, 0xCC];
  const P = new Float32Array(12), ST = new Float32Array(8), LT = new Uint8Array(12);
  const CRN = new Int32Array(12);   // per corner: sky*12, block*12, ao
  const COFF = new Int32Array(72);
  let MASK = new Float64Array(0);

  // Mesh the columns x1..x2, z1..z2 (inclusive, build coords) of the volume, layers opts.y1..opts.y2 (default all).
  // opts.under: keep build faces that only terrain hides, in their own buffer (x-ray)
  // opts.caps: also emit cut caps (every up face that the cell above hides, drawn only at the cut layer)
  MC.meshChunk = function (vol, pal, light, x1, z1, x2, z2, opts = {}) {
    const T = pal.table(), V = pal.variants;
    const { sx, sy, sz, ids } = vol;
    const step = vol.step, layer = sx * sz;
    const { sky, blk } = light;
    const under = !!opts.under, caps = !!opts.caps;
    let cap = false;     // while true, shapes emit only their hidden up faces, into the cap buffers
    const out = (k) => (cap ? (k === 1 || k === 4 ? bufs.capT : bufs.capS) : bufs[KIND[k]]);
    // neighbour index offsets for the smooth-light samples (per face, per corner: j1, j2, j3 relative to j0)
    const OFF = [1, -1, layer, -layer, sx, -sx];
    for (let f = 0; f < 6; f++) for (let k = 0; k < 4; k++) {
      const s1 = CORNER[f][k][0], s2 = CORNER[f][k][1];
      const d1 = s1[0] + s1[1] * layer + s1[2] * sx, d2 = s2[0] + s2[1] * layer + s2[2] * sx;
      COFF[f * 12 + k * 3] = d1; COFF[f * 12 + k * 3 + 1] = d2; COFF[f * 12 + k * 3 + 2] = d1 + d2;
    }
    for (const k in bufs) bufs[k].reset();
    const W = x2 - x1 + 1, D = z2 - z1 + 1, WD = W * D;
    if (MASK.length < WD * 7) MASK = new Float64Array(WD * 7);   // six faces + the cut caps
    const M = MASK;
    let masked = 0, minStep = 255, maxStep = 0;
    const MF = new Int32Array(7);   // masked faces per slice

    const inside = (x, y, z) => x >= vol.x0 && y >= vol.y0 && z >= vol.z0 && x < vol.x0 + sx && y < vol.y0 + sy && z < vol.z0 + sz;
    const at = (x, y, z) => (inside(x, y, z) ? ((y - vol.y0) * sz + (z - vol.z0)) * sx + (x - vol.x0) : -1);
    const cellV = (j) => (j < 0 || !ids[j] ? null : V[ids[j] - 1]);
    const opq = (j) => j >= 0 && T.opq[ids[j]] === 1;
    const topY = vol.y0 + sy;
    // light of an opaque cell as if it were absent: brightest open neighbour, minus one
    function absentLight(j) {
      let s = 0, b = 0;
      const x = j % sx, z = ((j / sx) | 0) % sz, y = (j / layer) | 0;
      const nb = (k) => { if (!T.opq[ids[k]]) { if (sky[k] - 1 > s) s = sky[k] - 1; if (blk[k] - 1 > b) b = blk[k] - 1; } };
      if (x > 0) nb(j - 1); if (x < sx - 1) nb(j + 1);
      if (z > 0) nb(j - sx); if (z < sz - 1) nb(j + sx);
      if (y > 0) nb(j - layer); if (y < sy - 1) nb(j + layer); else s = 15;
      return s * 16 + b;
    }
    // light at cell (x,y,z) as [sky, block], for flat-lit shapes
    let ls = 0, lb = 0;
    function lightAt(x, y, z) {
      const j = at(x, y, z);
      if (j < 0) { ls = y >= topY ? 15 : 0; lb = 0; return; }
      if (T.opq[ids[j]]) { const a = absentLight(j); ls = a >> 4; lb = a & 15; return; }
      ls = sky[j]; lb = blk[j];
    }
    // own light of a cell; shapes that block light (slabs, stairs) take their brightest neighbour
    function own(x, y, z, i) {
      if (light.opac[i] < 15) { ls = sky[i]; lb = blk[i]; return; }
      const a = absentLight(i); ls = a >> 4; lb = a & 15;
    }
    // how a face of a cell (step ss) toward neighbour j is treated: 0 draw, 1 culled, 2 under (x-ray only)
    // how a face of a cell (step ss) toward neighbour j is treated:
    // 0 draw, 1 culled, 2 under (x-ray only), 3 behind (only a later step hides it)
    function faceClass(ss, v, j, f) {
      if (j < 0) return 0;
      const id = ids[j];
      if (!id) return 0;
      if (T.opq[id]) { if (T.path[id] && f !== 2 && f !== 3 && v.cube) return 0; }
      else if (T.occ[id]) {
        const m = occOf(V[id - 1], (j % sx) + vol.x0, ((j / layer) | 0) + vol.y0, (((j / sx) | 0) % sz) + vol.z0);
        if ((m & FACEBITS[f]) !== FACEBITS[f]) return 0;
      } else if (!(v.selfCull && V[id - 1].key === v.key)) return 0;
      const ns = step[j];
      if (ns > ss) return 3;
      return ss > 0 && ns === 0 ? (under ? 2 : 1) : 1;
    }
    // 2x2x2 occupancy of slabs and stairs (bit qx + 2 qz + 4 qy)
    function occOf(v, x, y, z) {
      const p = v.props, top = p.half === "top";
      if (v.shape === "slab") return top ? 0xF0 : 0x0F;
      let m = top ? 0xF0 : 0x0F;
      const qy = top ? 0 : 1;
      const corner = stairCorner(x, y, z, v);
      const back = DIRV[p.facing], left = DIRV[LEFT[p.facing]];
      for (let qx = 0; qx < 2; qx++) for (let qz = 0; qz < 2; qz++) {
        const cx = qx ? 1 : -1, cz = qz ? 1 : -1;
        const isBack = cx * back[0] + cz * back[1] > 0;
        const isLeft = cx * left[0] + cz * left[1] > 0;
        let on = isBack;
        if (corner === "outer_left") on = isBack && isLeft;
        else if (corner === "outer_right") on = isBack && !isLeft;
        else if (corner === "inner_left") on = isBack || isLeft;
        else if (corner === "inner_right") on = isBack || !isLeft;
        if (on) m |= 1 << (qx + 2 * qz + 4 * qy);
      }
      return m;
    }
    // slabs and stairs as sub-cubes: only faces between filled and empty sub-cubes are drawn,
    // and edge faces cull against opaque blocks and against the sub-cubes of neighbouring slabs/stairs
    const SUB = new Int8Array(4), DONE = new Uint8Array(4), lo = [0, 0, 0], hi = [0, 0, 0], q3 = [0, 0, 0];
    const UW = [[2, 1], [0, 2], [0, 1]];
    function occShape(kind, x, y, z, ss, v, m, Tl, ol, ob) {
      for (let f = 0; f < 6; f++) {
        if (cap && f !== 2) continue;
        const a = f >> 1, pos = (f & 1) === 0, n = FN[f], [ua, wa] = UW[a];
        const nx = x + n[0], ny = y + n[1], nz = z + n[2], j = at(nx, ny, nz);
        let cls = -1, nm = 0, nstep = 0, es = 0, eb = 0;
        for (let q = 0; q < 2; q++) {
          const edge = pos ? q === 1 : q === 0;
          if (cap && !edge) continue;
          let any = false;
          for (let w = 0; w < 2; w++) for (let u = 0; u < 2; u++) {
            q3[a] = q; q3[ua] = u; q3[wa] = w;
            let val = 0;
            if ((m >> (q3[0] + 2 * q3[2] + 4 * q3[1])) & 1) {
              if (!edge) {
                q3[a] = q + (pos ? 1 : -1);
                val = (m >> (q3[0] + 2 * q3[2] + 4 * q3[1])) & 1 ? 0 : kind + 1;
              } else {
                if (cls < 0) {
                  cls = faceClass(ss, v, j, f);
                  if (cls === 0 && j >= 0 && ids[j]) {
                    const nv = V[ids[j] - 1];
                    if (nv.shape === "slab" || nv.shape === "stair") { nm = occOf(nv, nx, ny, nz); nstep = step[j]; }
                  }
                  lightAt(nx, ny, nz);
                  es = Math.max(ls, ol); eb = Math.max(lb, ob);
                }
                let c = cls;
                if (c === 0 && nm) {
                  q3[a] = pos ? 0 : 1;
                  if ((nm >> (q3[0] + 2 * q3[2] + 4 * q3[1])) & 1) c = nstep <= ss ? 1 : 3;
                }
                if (cap) val = c === 1 || c === 2 ? 1 : 0;
                else val = c === 1 ? 0 : c === 2 ? 3 : c === 3 ? (kind === 1 ? 5 : 4) : kind + 1;
              }
            }
            SUB[u + 2 * w] = val; DONE[u + 2 * w] = 0;
            if (val) any = true;
          }
          if (!any) continue;
          const s = cap ? 15 : edge ? es : ol, b = cap ? 0 : edge ? eb : ob;
          for (let w = 0; w < 2; w++) for (let u = 0; u < 2; u++) {
            const k = u + 2 * w, val = SUB[k];
            if (!val || DONE[k]) continue;
            let u1 = u, w1 = w;
            if (u === 0 && SUB[k + 1] === val && !DONE[k + 1]) u1 = 1;
            if (w === 0 && SUB[u + 2] === val && !DONE[u + 2] && (u1 === u || (SUB[3] === val && !DONE[3]))) w1 = 1;
            for (let ww = w; ww <= w1; ww++) for (let uu = u; uu <= u1; uu++) DONE[uu + 2 * ww] = 1;
            lo[a] = q * 0.5; hi[a] = q * 0.5 + 0.5;
            lo[ua] = u * 0.5; hi[ua] = (u1 + 1) * 0.5; lo[wa] = w * 0.5; hi[wa] = (w1 + 1) * 0.5;
            const c = faceVerts(P, f, lo[0], lo[1], lo[2], hi[0], hi[1], hi[2], x, y, z);
            faceST(ST, f, c);
            for (let t = 0; t < 4; t++) { LT[t * 3] = s * 17; LT[t * 3 + 1] = b * 17; LT[t * 3 + 2] = 255; }
            out(cap ? kind : val - 1).quad(P, ST, LT, f, ss, y, Tl[f], false);
          }
        }
      }
    }
    // full cube face with smooth light + AO; flat-lit faces go to the merge mask
    function cubeFace(kind, x, y, z, f, tile, ss, i, fast) {
      const n = FN[f];
      const nx = x + n[0], ny = y + n[1], nz = z + n[2];
      const j0 = fast ? i + OFF[f] : at(nx, ny, nz);
      let s0, b0;
      if (j0 < 0) { s0 = ny >= topY ? 15 : 0; b0 = 0; }
      else if (T.opq[ids[j0]]) { const a = absentLight(j0); s0 = a >> 4; b0 = a & 15; }
      else { s0 = sky[j0]; b0 = blk[j0]; }
      const C = CORNER[f];
      if (fast) for (let k = 0; k < 4; k++) {
        const o = f * 12 + k * 3, j1 = j0 + COFF[o], j2 = j0 + COFF[o + 1];
        const o1 = T.opq[ids[j1]] === 1, o2 = T.opq[ids[j2]] === 1;
        let ss_ = s0, bb = b0, cnt = 1, o3 = true;
        if (!o1) { ss_ += sky[j1]; bb += blk[j1]; cnt++; }
        if (!o2) { ss_ += sky[j2]; bb += blk[j2]; cnt++; }
        if (!(o1 && o2)) {
          const j3 = j0 + COFF[o + 2];
          o3 = T.opq[ids[j3]] === 1;
          if (!o3) { ss_ += sky[j3]; bb += blk[j3]; cnt++; }
        }
        const ao = o1 && o2 ? 0 : 3 - ((o1 ? 1 : 0) + (o2 ? 1 : 0) + (o3 ? 1 : 0));
        CRN[k * 3] = (ss_ * 12) / cnt; CRN[k * 3 + 1] = (bb * 12) / cnt; CRN[k * 3 + 2] = ao;
      }
      else for (let k = 0; k < 4; k++) {
        const s1 = C[k][0], s2 = C[k][1];
        const j1 = at(nx + s1[0], ny + s1[1], nz + s1[2]), j2 = at(nx + s2[0], ny + s2[1], nz + s2[2]);
        const o1 = opq(j1), o2 = opq(j2);
        let ss_ = s0, bb = b0, cnt = 1, o3 = true;
        if (!o1) { ss_ += j1 < 0 ? (ny + s1[1] >= topY ? 15 : 0) : sky[j1]; bb += j1 < 0 ? 0 : blk[j1]; cnt++; }
        if (!o2) { ss_ += j2 < 0 ? (ny + s2[1] >= topY ? 15 : 0) : sky[j2]; bb += j2 < 0 ? 0 : blk[j2]; cnt++; }
        if (!(o1 && o2)) {
          const j3 = at(nx + s1[0] + s2[0], ny + s1[1] + s2[1], nz + s1[2] + s2[2]);
          o3 = opq(j3);
          if (!o3) { ss_ += j3 < 0 ? (ny + s1[1] + s2[1] >= topY ? 15 : 0) : sky[j3]; bb += j3 < 0 ? 0 : blk[j3]; cnt++; }
        }
        const ao = o1 && o2 ? 0 : 3 - ((o1 ? 1 : 0) + (o2 ? 1 : 0) + (o3 ? 1 : 0));
        CRN[k * 3] = (ss_ * 12) / cnt; CRN[k * 3 + 1] = (bb * 12) / cnt; CRN[k * 3 + 2] = ao;
      }
      // behind faces show only while the later step next to them is hidden: nothing there to occlude them
      if (kind === 3 || kind === 4) { CRN[2] = CRN[5] = CRN[8] = CRN[11] = 3; }
      const uniform = CRN[0] === CRN[3] && CRN[0] === CRN[6] && CRN[0] === CRN[9] && CRN[1] === CRN[4] && CRN[1] === CRN[7] &&
        CRN[1] === CRN[10] && CRN[2] === CRN[5] && CRN[2] === CRN[8] && CRN[2] === CRN[11];
      if (uniform) {
        // mask slot: up/down faces by (x, z); x faces by (x, z) merged along z; z faces merged along x
        const key = ((((tile * 256 + CRN[0]) * 256 + CRN[1]) * 4 + CRN[2]) * 256 + ss) * 8 + kind + 1;
        M[f * WD + (z - z1) * W + (x - x1)] = key;
        masked++; MF[f]++;
        return;
      }
      const c = faceVerts(P, f, 0, 0, 0, 1, 1, 1, x, y, z);
      faceST(ST, f, c);
      for (let k = 0; k < 4; k++) {
        LT[k * 3] = (CRN[k * 3] * 17) / 12; LT[k * 3 + 1] = (CRN[k * 3 + 1] * 17) / 12; LT[k * 3 + 2] = AO[CRN[k * 3 + 2]] * 255;
      }
      const flip = CRN[2] + CRN[8] < CRN[5] + CRN[11];
      out(kind).quad(P, ST, LT, f, ss, y, tile, flip);
    }
    // greedy-merge the masked faces of one layer
    function flush(y) {
      if (!masked) return;
      masked = 0;
      for (let ff = 0; ff < 7; ff++) {
        if (!MF[ff]) continue;
        MF[ff] = 0;
        const base = ff * WD, f = ff === 6 ? 2 : ff;
        for (let v = 0; v < D; v++) for (let u = 0; u < W; u++) {
          const key = M[base + v * W + u];
          if (!key) continue;
          let w = 1, h = 1;
          if (f > 1) while (u + w < W && M[base + v * W + u + w] === key) w++;
          if (f === 2 || f === 3 || f === 0 || f === 1) {
            outer: while (v + h < D) {
              for (let k = 0; k < w; k++) if (M[base + (v + h) * W + u + k] !== key) break outer;
              h++;
            }
          }
          for (let dv = 0; dv < h; dv++) M.fill(0, base + (v + dv) * W + u, base + (v + dv) * W + u + w);
          let r = key - 1;
          const kind = r % 8; r = (r - kind) / 8;
          const ss = r % 256; r = (r - ss) / 256;
          const ao = r % 4; r = (r - ao) / 4;
          const bl = r % 256; r = (r - bl) / 256;
          const sk = r % 256; const tile = (r - sk) / 256;
          const x = x1 + u, z = z1 + v;
          // f 0/1 merge along z only (u = x stays one cell)
          const c = faceVerts(P, f, 0, 0, 0, w, 1, h, x, y, z);
          faceST(ST, f, c);
          for (let k = 0; k < 4; k++) { LT[k * 3] = (sk * 17) / 12; LT[k * 3 + 1] = (bl * 17) / 12; LT[k * 3 + 2] = AO[ao] * 255; }
          out(kind).quad(P, ST, LT, f, ss, y, tile, false);
        }
      }
    }

    // partial box (coords 0..16), flat light; faces on the cell edge cull against opaque neighbours
    function box(kind, x, y, z, ss, v, bx0, by0, bz0, bx1, by1, bz1, tiles, ol, ob) {
      const b0 = bx0 / 16, b1 = by0 / 16, b2 = bz0 / 16, b3 = bx1 / 16, b4 = by1 / 16, b5 = bz1 / 16;
      for (let f = 0; f < 6; f++) {
        if (cap && f !== 2) continue;
        const n = FN[f];
        const onEdge = (f === 0 && b3 >= 1) || (f === 1 && b0 <= 0) || (f === 2 && b4 >= 1) ||
          (f === 3 && b1 <= 0) || (f === 4 && b5 >= 1) || (f === 5 && b2 <= 0);
        let s = ol, b = ob, k = kind;
        if (onEdge) {
          const cls = faceClass(ss, v, at(x + n[0], y + n[1], z + n[2]), f);
          if (cap) { if (cls === 0 || cls === 3) continue; s = 15; b = 0; }
          else {
            if (cls === 1) continue;
            if (cls === 2) k = 2;
            if (cls === 3) k = kind === 1 ? 4 : 3;
            lightAt(x + n[0], y + n[1], z + n[2]);
            s = Math.max(ls, ol); b = Math.max(lb, ob);
          }
        } else if (cap) continue;
        const c = faceVerts(P, f, b0, b1, b2, b3, b4, b5, x, y, z);
        faceST(ST, f, c);
        for (let q = 0; q < 4; q++) { LT[q * 3] = s * 17; LT[q * 3 + 1] = b * 17; LT[q * 3 + 2] = 255; }
        out(k).quad(P, ST, LT, f, ss, y, tiles[f], false);
      }
    }
    function rbox(kind, x, y, z, ss, v, bx, facing, tiles, ol, ob) {
      let [a0, a1, a2, a3, a4, a5] = bx;
      for (let k = 0, r = ROT[facing] || 0; k < r; k++) [a0, a2, a3, a5] = [16 - a5, a0, 16 - a2, a3];   // clockwise
      box(kind, x, y, z, ss, v, a0, a1, a2, a3, a4, a5, tiles, ol, ob);
    }
    // double-sided quad, corners in 0..16 coords, full tile
    function plane(kind, x, y, z, ss, q, tile, ol, ob) {
      if (cap) return;
      for (let k = 0; k < 4; k++) { P[k * 3] = x + q[k * 3] / 16; P[k * 3 + 1] = y + q[k * 3 + 1] / 16; P[k * 3 + 2] = z + q[k * 3 + 2] / 16; }
      ST.set([0, 1, 1, 1, 1, 0, 0, 0]);
      for (let k = 0; k < 4; k++) { LT[k * 3] = ol * 17; LT[k * 3 + 1] = ob * 17; LT[k * 3 + 2] = 0.92 * 255; }
      out(kind).quad(P, ST, LT, -1, ss, y, tile, false);
      // back side: corners 1 0 3 2
      const p = P.slice(), s = ST.slice();
      for (const [d, o] of [[0, 1], [1, 0], [2, 3], [3, 2]]) {
        P[d * 3] = p[o * 3]; P[d * 3 + 1] = p[o * 3 + 1]; P[d * 3 + 2] = p[o * 3 + 2];
        ST[d * 2] = s[o * 2]; ST[d * 2 + 1] = s[o * 2 + 1];
      }
      out(kind).quad(P, ST, LT, -1, ss, y, tile, false);
    }
    function connects(v, n, side) {
      if (!n) return false;
      if (n.shape === "fence_gate") {
        const ga = n.props.facing === "north" || n.props.facing === "south" ? "z" : "x";
        const sa = side === "north" || side === "south" ? "z" : "x";
        return (v.shape === "fence" || v.shape === "wall") && ga !== sa;
      }
      if (v.shape === "fence") return n.shape === "fence" || !!n.flags.sturdy;
      if (v.shape === "pane") return n.shape === "pane" || n.shape === "glass" || n.shape === "wall" || !!n.flags.sturdy;
      if (v.shape === "wall") return n.shape === "wall" || n.shape === "pane" || !!n.flags.sturdy;
      return false;
    }
    function stairCorner(x, y, z, v) {
      const f = v.props.facing, half = v.props.half;
      const sAt = (d) => {
        const n = cellV(at(x + DIRV[d][0], y, z + DIRV[d][1]));
        return n && n.shape === "stair" && n.props.half === half ? n : null;
      };
      const axis = (d) => (d === "north" || d === "south" ? "z" : "x");
      const canTake = (d) => { const n = sAt(d); return !(n && n.props.facing === f); };
      const back = sAt(f);
      if (back && axis(back.props.facing) !== axis(f) && canTake(OPP[back.props.facing]))
        return back.props.facing === LEFT[f] ? "outer_left" : "outer_right";
      const front = sAt(OPP[f]);
      if (front && axis(front.props.facing) !== axis(f) && canTake(front.props.facing))
        return front.props.facing === LEFT[f] ? "inner_left" : "inner_right";
      return "none";
    }

    // every non-cube shape; in cap mode only the hidden up faces come out
    function shape(v, kind, x, y, z, ss, Tl, ol, ob) {
      const sh = v.shape, p = v.props;
      switch (sh) {
        case "slab": case "stair":
          occShape(kind, x, y, z, ss, v, occOf(v, x, y, z), Tl, ol, ob);
          break;
        case "fence": case "wall": case "pane": {
          const post = sh === "fence" ? [6, 0, 6, 10, 16, 10] : sh === "wall" ? [4, 0, 4, 12, 16, 12] : [7, 0, 7, 9, 16, 9];
          const cn = {
            north: connects(v, cellV(at(x, y, z - 1)), "north"), east: connects(v, cellV(at(x + 1, y, z)), "east"),
            south: connects(v, cellV(at(x, y, z + 1)), "south"), west: connects(v, cellV(at(x - 1, y, z)), "west"),
          };
          const any = cn.north || cn.east || cn.south || cn.west;
          const straight = (cn.north && cn.south && !cn.east && !cn.west) || (cn.east && cn.west && !cn.north && !cn.south);
          if (sh !== "wall" || !straight || cellV(at(x, y + 1, z))) box(kind, x, y, z, ss, v, ...post, Tl, ol, ob);
          if (sh === "pane" && !any) { box(kind, x, y, z, ss, v, 0, 0, 7, 16, 16, 9, Tl, ol, ob); break; }
          for (const d in cn) {
            if (!cn[d]) continue;
            if (sh === "fence") {
              rbox(kind, x, y, z, ss, v, [7, 12, 0, 9, 15, 6], d, Tl, ol, ob);
              rbox(kind, x, y, z, ss, v, [7, 6, 0, 9, 9, 6], d, Tl, ol, ob);
            } else if (sh === "wall") rbox(kind, x, y, z, ss, v, [5, 0, 0, 11, 14, 8], d, Tl, ol, ob);
            else rbox(kind, x, y, z, ss, v, [7, 0, 0, 9, 16, 7], d, Tl, ol, ob);
          }
          break;
        }
        case "fence_gate": {
          const f = p.open ? (p.facing === "north" || p.facing === "south" ? "east" : "north") : p.facing;
          rbox(kind, x, y, z, ss, v, [0, 5, 7, 2, 16, 9], p.facing, Tl, ol, ob);
          rbox(kind, x, y, z, ss, v, [14, 5, 7, 16, 16, 9], p.facing, Tl, ol, ob);
          if (!p.open) for (const bx of [[2, 6, 7, 14, 9, 9], [2, 12, 7, 14, 15, 9], [6, 9, 7, 10, 12, 9]]) rbox(kind, x, y, z, ss, v, bx, f, Tl, ol, ob);
          else for (const bx of [[0, 6, 9, 2, 15, 16], [14, 6, 9, 16, 15, 16]]) rbox(kind, x, y, z, ss, v, bx, p.facing, Tl, ol, ob);
          break;
        }
        case "door": {
          // closed: panel on the side you approach from; open: swung to the hinge side
          const side = p.open ? (p.hinge === "right" ? RIGHT[p.facing] : LEFT[p.facing]) : OPP[p.facing];
          rbox(kind, x, y, z, ss, v, [0, 0, 0, 16, 16, 3], side, Tl, ol, ob);
          break;
        }
        case "trapdoor":
          if (p.open) rbox(kind, x, y, z, ss, v, [0, 0, 0, 16, 16, 3], OPP[p.facing], Tl, ol, ob);
          else if (p.half === "top") box(kind, x, y, z, ss, v, 0, 13, 0, 16, 16, 16, Tl, ol, ob);
          else box(kind, x, y, z, ss, v, 0, 0, 0, 16, 3, 16, Tl, ol, ob);
          break;
        case "carpet": box(kind, x, y, z, ss, v, 0, 0, 0, 16, 1, 16, Tl, ol, ob); break;
        case "bed": box(kind, x, y, z, ss, v, 0, 0, 0, 16, 9, 16, Tl, ol, ob); break;
        case "chest": box(kind, x, y, z, ss, v, 1, 0, 1, 15, 14, 15, Tl, ol, ob); break;
        case "campfire": box(kind, x, y, z, ss, v, 0, 0, 0, 16, 7, 16, Tl, ol, ob); break;
        case "pot": box(kind, x, y, z, ss, v, 5, 0, 5, 11, 6, 11, Tl, ol, ob); break;
        case "chain": {
          const a = p.axis || "y";
          if (a === "y") box(kind, x, y, z, ss, v, 7, 0, 7, 9, 16, 9, Tl, ol, ob);
          else if (a === "x") box(kind, x, y, z, ss, v, 0, 7, 7, 16, 9, 9, Tl, ol, ob);
          else box(kind, x, y, z, ss, v, 7, 7, 0, 9, 9, 16, Tl, ol, ob);
          break;
        }
        case "ladder": rbox(kind, x, y, z, ss, v, [0, 0, 15, 16, 16, 16], p.facing, Tl, ol, ob); break;
        case "lantern":
          if (p.hanging) {
            box(kind, x, y, z, ss, v, 5, 1, 5, 11, 8, 11, Tl, ol, 15);
            box(kind, x, y, z, ss, v, 6, 8, 6, 10, 10, 10, Tl, ol, 15);
            box(kind, x, y, z, ss, v, 7.5, 10, 7.5, 8.5, 16, 8.5, Tl, ol, 15);
          } else {
            box(kind, x, y, z, ss, v, 5, 0, 5, 11, 7, 11, Tl, ol, 15);
            box(kind, x, y, z, ss, v, 6, 7, 6, 10, 9, 10, Tl, ol, 15);
          }
          break;
        case "torch":
          if (p.facing === "up") box(kind, x, y, z, ss, v, 7, 0, 7, 9, 10, 9, Tl, ol, 15);
          else rbox(kind, x, y, z, ss, v, [7, 3, 12, 9, 13, 14], p.facing, Tl, ol, 15);
          break;
        case "plant": case "tall_plant":
          plane(kind, x, y, z, ss, [1, 0, 1, 15, 0, 15, 15, 16, 15, 1, 16, 1], Tl[4], ol, ob);
          plane(kind, x, y, z, ss, [1, 0, 15, 15, 0, 1, 15, 16, 1, 1, 16, 15], Tl[4], ol, ob);
          break;
        case "crop":
          for (const c of [4, 12]) {
            plane(kind, x, y, z, ss, [c, 0, 0, c, 0, 16, c, 16, 16, c, 16, 0], Tl[4], ol, ob);
            plane(kind, x, y, z, ss, [0, 0, c, 16, 0, c, 16, 16, c, 0, 16, c], Tl[4], ol, ob);
          }
          break;
        case "flat": {
          if (cap) break;
          P.set([x, y + 0.02, z + 1, x + 1, y + 0.02, z + 1, x + 1, y + 0.02, z, x, y + 0.02, z]);
          ST.set([0, 1, 1, 1, 1, 0, 0, 0]);
          for (let q = 0; q < 4; q++) { LT[q * 3] = ol * 17; LT[q * 3 + 1] = ob * 17; LT[q * 3 + 2] = 255; }
          out(kind).quad(P, ST, LT, 2, ss, y, Tl[2], false);
          break;
        }
        case "water": {
          const up = cellV(at(x, y + 1, z));
          const topH = up && up.shape === "water" ? 1 : 14 / 16;
          for (let f = 0; f < 6; f++) {
            if (cap && f !== 2) continue;
            const n = FN[f];
            const j = at(x + n[0], y + n[1], z + n[2]);
            const nb = cellV(j);
            const hidden = nb && (nb.shape === "water" || (nb.opaque && step[j] <= ss));
            if (cap) {
              if (!hidden) continue;
            } else {
              if (hidden) continue;
              if (f === 2 && topH === 1) continue;
            }
            const c = faceVerts(P, f, 0, 0, 0, 1, cap ? 14 / 16 : topH, 1, x, y, z);
            faceST(ST, f, c);
            lightAt(x + n[0], y + n[1], z + n[2]);
            const s = cap ? 15 : Math.max(ls, ol), b = cap ? 0 : Math.max(lb, ob);
            for (let q = 0; q < 4; q++) { LT[q * 3] = s * 17; LT[q * 3 + 1] = b * 17; LT[q * 3 + 2] = 255; }
            (cap ? bufs.capW : bufs.water).quad(P, ST, LT, f, ss, y, Tl[f], false);
          }
          break;
        }
        default:
          box(kind, x, y, z, ss, v, 0, 0, 0, 16, 16, 16, Tl, ol, ob);
    }
    }

    const ya = opts.y1 != null ? opts.y1 : vol.y0, yb = opts.y2 != null ? opts.y2 : vol.y0 + sy - 1;
    for (let y = ya; y <= yb; y++) {
      for (let z = z1; z <= z2; z++) {
        let i = at(x1, y, z);
        for (let x = x1; x <= x2; x++, i++) {
          const id = ids[i];
          if (!id) continue;
          const v = V[id - 1];
          const sh = v.shape;
          if (sh === "air") continue;
          const ss = step[i];
          const kind = ss === 0 ? 1 : 0;
          if (ss) { if (ss < minStep) minStep = ss; if (ss > maxStep) maxStep = ss; }
          const Tl = v.tiles;
          if (sh === "path") {
            own(x, y, z, i);
            box(kind, x, y, z, ss, v, 0, 0, 0, 16, 15, 16, Tl, ls, lb);
            continue;
          }
          if (v.cube) {
            const fast = x > vol.x0 + 1 && x < vol.x0 + sx - 2 && z > vol.z0 + 1 && z < vol.z0 + sz - 2 && y > vol.y0 + 1 && y < vol.y0 + sy - 2;
            for (let f = 0; f < 6; f++) {
              const n = FN[f];
              const cls = faceClass(ss, v, fast ? i + OFF[f] : at(x + n[0], y + n[1], z + n[2]), f);
              if (cls === 1 || cls === 2) {
                if (f === 2 && caps) {
                  // the cut opens this face to the sky: evenly lit, so it merges like any flat face
                  M[6 * WD + (z - z1) * W + (x - x1)] = ((((Tl[2] * 256 + 180) * 256) * 4 + 3) * 256 + ss) * 8 + (kind === 1 ? 6 : 5) + 1;
                  masked++; MF[6]++;
                }
                if (cls === 1) continue;
              }
              cubeFace(cls === 2 ? 2 : cls === 3 ? (kind === 1 ? 4 : 3) : kind, x, y, z, f, Tl[f], ss, i, fast);
            }
            continue;
          }
          own(x, y, z, i);
          shape(v, kind, x, y, z, ss, Tl, ls, lb);
          if (caps) {
            const ja = at(x, y + 1, z);
            if (ja >= 0 && ids[ja] && step[ja] <= ss) { own(x, y, z, i); cap = true; shape(v, kind, x, y, z, ss, Tl, ls, lb); cap = false; }
          }
        }
      }
      flush(y);
    }
    const bb = [x1, ya, z1, x2 + 1, yb + 1, z2 + 1], G = {};
    for (const k in bufs) G[k] = bufs[k].geometry(bb);
    G.minStep = minStep; G.maxStep = maxStep;
    return G;
  };

  // voxel ray cast (Amanatides & Woo). Returns {x,y,z, face normal [nx,ny,nz], t} or null.
  // visible(i): optional filter on the volume index (hidden steps, the cut)
  MC.raycast = function (vol, pal, origin, dir, maxDist, skipWater = true, visible = null) {
    let x = Math.floor(origin.x), y = Math.floor(origin.y), z = Math.floor(origin.z);
    const sx = Math.sign(dir.x), sy = Math.sign(dir.y), sz = Math.sign(dir.z);
    const tdx = Math.abs(1 / dir.x), tdy = Math.abs(1 / dir.y), tdz = Math.abs(1 / dir.z);
    let tmx = (sx > 0 ? x + 1 - origin.x : origin.x - x) * tdx;
    let tmy = (sy > 0 ? y + 1 - origin.y : origin.y - y) * tdy;
    let tmz = (sz > 0 ? z + 1 - origin.z : origin.z - z) * tdz;
    let n = [0, 0, 0], t = 0;
    const V = pal.variants;
    for (let i = 0; i < 2000 && t <= maxDist; i++) {
      if (vol.inside(x, y, z)) {
        const j = vol.idx(x, y, z), id = vol.ids[j] - 1;
        if (id >= 0) {
          const v = V[id];
          if (!(skipWater && v.shape === "water") && v.shape !== "air" && (!visible || visible(j, y))) return { x, y, z, n, t, id };
        }
      }
      if (tmx < tmy && tmx < tmz) { x += sx; t = tmx; tmx += tdx; n = [-sx, 0, 0]; }
      else if (tmy < tmz) { y += sy; t = tmy; tmy += tdy; n = [0, -sy, 0]; }
      else { z += sz; t = tmz; tmz += tdz; n = [0, 0, -sz]; }
    }
    return null;
  };
})();
