// Voxel volume, Minecraft-style lighting (sky + block light, smooth lighting, AO)
// and mesh generation for every block shape in the palette.
(function () {
  const MC = (window.MC = window.MC || {});
  const DIRV = { north: [0, -1], east: [1, 0], south: [0, 1], west: [-1, 0] };
  const LEFT = { north: "west", west: "south", south: "east", east: "north" };
  const RIGHT = { west: "north", south: "west", east: "south", north: "east" };
  const OPP = { north: "south", south: "north", east: "west", west: "east" };
  // faces: 0 +x east, 1 -x west, 2 +y up, 3 -y down, 4 +z south, 5 -z north
  const FN = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
  const FACE_DIR = ["east", "west", "up", "down", "south", "north"];
  const UP = [0, 1, 0];
  MC.DIRV = DIRV; MC.LEFT = LEFT; MC.OPP = OPP; MC.FACE_DIR = FACE_DIR;

  // ---------------------------------------------------------------- palette / variants
  class Palette {
    constructor(json, atlas) {
      this.blocks = json.blocks;
      this.atlas = atlas;
      this.variants = [];
      this.index = new Map();
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
      v.cutout = v.tiles.some((t) => this.atlas.alpha[t]);
      v.color = def.color;
      this.variants.push(v);
      this.index.set(k, v.id);
      return v.id;
    }
    v(id) { return this.variants[id]; }
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
  class Vol {
    constructor(x0, y0, z0, sx, sy, sz) {
      Object.assign(this, { x0, y0, z0, sx, sy, sz });
      const n = sx * sy * sz;
      this.ids = new Int32Array(n);      // variant id + 1 (0 = air)
      this.step = new Uint8Array(n);     // 0 terrain, 1.. build steps
      this.group = new Int32Array(n);
    }
    inside(x, y, z) {
      return x >= this.x0 && y >= this.y0 && z >= this.z0 && x < this.x0 + this.sx && y < this.y0 + this.sy && z < this.z0 + this.sz;
    }
    idx(x, y, z) { return ((y - this.y0) * this.sz + (z - this.z0)) * this.sx + (x - this.x0); }
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
  function computeLight(vol, pal) {
    const n = vol.ids.length, sky = new Uint8Array(n), blk = new Uint8Array(n);
    const { sx, sy, sz } = vol;
    const opac = new Uint8Array(n);
    const q = new Int32Array(n * 2);
    for (let i = 0; i < n; i++) {
      const id = vol.ids[i] - 1;
      if (id >= 0) {
        const v = pal.v(id);
        opac[i] = v.opacity;
        if (v.light) blk[i] = v.light;
      }
    }
    // sky: straight down from the top, then spread sideways
    let qn = 0;
    for (let z = 0; z < sz; z++) for (let x = 0; x < sx; x++) {
      let l = 15;
      for (let y = sy - 1; y >= 0; y--) {
        const i = (y * sz + z) * sx + x;
        if (opac[i] >= 15) break;
        l -= opac[i];
        if (l <= 0) break;
        sky[i] = l;
        q[qn++] = i;
      }
    }
    spread(sky, q, qn, opac, sx, sy, sz);
    qn = 0;
    for (let i = 0; i < n; i++) if (blk[i]) q[qn++] = i;
    spread(blk, q, qn, opac, sx, sy, sz);
    return { sky, blk, opac };
  }
  function spread(L, q, qn, opac, sx, sy, sz) {
    let head = 0;
    const layer = sx * sz;
    while (head < qn) {
      const i = q[head++];
      const l = L[i];
      if (l <= 1) continue;
      const x = i % sx, z = ((i / sx) | 0) % sz, y = (i / layer) | 0;
      const nb = [x > 0 ? i - 1 : -1, x < sx - 1 ? i + 1 : -1, z > 0 ? i - sx : -1, z < sz - 1 ? i + sx : -1,
        y > 0 ? i - layer : -1, y < sy - 1 ? i + layer : -1];
      for (const j of nb) {
        if (j < 0 || opac[j] >= 15) continue;
        const nl = l - 1 - opac[j];
        if (nl > L[j]) {
          L[j] = nl;
          if (qn < q.length) q[qn++] = j;
        }
      }
    }
  }
  MC.computeLight = computeLight;

  // ---------------------------------------------------------------- geometry buffers
  class Buf {
    constructor() { this.pos = []; this.nrm = []; this.uv = []; this.light = []; this.hl = []; this.idx = []; this.n = 0; }
    quad(P, UV, LT, hl, flip, N) {
      const b = this.n;
      for (let k = 0; k < 4; k++) {
        this.pos.push(P[k][0], P[k][1], P[k][2]);
        this.nrm.push(N[0], N[1], N[2]);
        this.uv.push(UV[k][0], UV[k][1]);
        this.light.push(LT[k][0], LT[k][1], LT[k][2]);
        this.hl.push(hl);
      }
      if (flip) this.idx.push(b + 1, b + 2, b + 3, b + 1, b + 3, b);
      else this.idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
      this.n += 4;
    }
    geometry() {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(this.pos, 3));
      g.setAttribute("normal", new THREE.Float32BufferAttribute(this.nrm, 3));
      g.setAttribute("uv", new THREE.Float32BufferAttribute(this.uv, 2));
      g.setAttribute("light", new THREE.Float32BufferAttribute(this.light, 3));
      g.setAttribute("hl", new THREE.Float32BufferAttribute(this.hl, 1));
      g.setIndex(this.n > 65000 ? new THREE.Uint32BufferAttribute(this.idx, 1) : new THREE.Uint16BufferAttribute(this.idx, 1));
      g.computeBoundingSphere();
      return g;
    }
  }

  // face corner positions (unit box) and texture coordinates (px from top-left)
  function faceVerts(f, b) {
    const [x0, y0, z0, x1, y1, z1] = b;
    switch (f) {
      case 0: return [[x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1]];
      case 1: return [[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]];
      case 2: return [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0]];
      case 3: return [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]];
      case 4: return [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
      default: return [[x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0]];
    }
  }
  function faceST(f, v) {
    const [x, y, z] = v;
    switch (f) {
      case 0: return [1 - z, 1 - y];
      case 1: return [z, 1 - y];
      case 2: return [x, z];
      case 3: return [x, 1 - z];
      case 4: return [x, 1 - y];
      default: return [1 - x, 1 - y];
    }
  }

  // ---------------------------------------------------------------- mesher
  function Mesher(vol, pal, light, opts) {
    const atlas = pal.atlas;
    const solid = new Buf(), water = new Buf();
    const hlStep = opts.highlightStep || -1;
    const I = (x, y, z) => vol.idx(x, y, z);

    function cell(x, y, z) {
      if (!vol.inside(x, y, z)) return null;
      const id = vol.ids[I(x, y, z)] - 1;
      return id >= 0 ? pal.v(id) : null;
    }
    function L(x, y, z) {
      if (!vol.inside(x, y, z)) return [y >= vol.y0 + vol.sy ? 15 : 0, 0, false];
      const i = I(x, y, z);
      return [light.sky[i], light.blk[i], light.opac[i] >= 15 && !!(cell(x, y, z) || {}).opaque];
    }
    // light for a non-opaque shape that still blocks light (slabs, stairs): brightest neighbour
    function own(x, y, z) {
      const i = I(x, y, z);
      if (light.opac[i] < 15) return [light.sky[i], light.blk[i]];
      let s = 0, b = 0;
      for (const n of FN) {
        const l = L(x + n[0], y + n[1], z + n[2]);
        if (!l[2]) { s = Math.max(s, l[0] - 1); b = Math.max(b, l[1] - 1); }
      }
      return [Math.max(0, s), Math.max(0, b)];
    }

    function tileUV(tile, st, crop) {
      const [u0, v0, du, dv] = atlas.uv(tile);
      const e = 0.0005;
      return [u0 + e + st[0] * (du - 2 * e), v0 + e + st[1] * (dv - 2 * e)];
    }

    // full cube face with smooth light + AO
    function cubeFace(buf, x, y, z, f, tile, hl, b) {
      const n = FN[f];
      const nx = x + n[0], ny = y + n[1], nz = z + n[2];
      const verts = faceVerts(f, b || [0, 0, 0, 1, 1, 1]);
      const LT = [], aos = [];
      for (const v of verts) {
        const t = [];
        for (let a = 0; a < 3; a++) if (n[a] === 0) t.push(a);
        const s1 = [0, 0, 0], s2 = [0, 0, 0];
        s1[t[0]] = v[t[0]] > 0.5 ? 1 : -1;
        s2[t[1]] = v[t[1]] > 0.5 ? 1 : -1;
        const c0 = L(nx, ny, nz);
        const c1 = L(nx + s1[0], ny + s1[1], nz + s1[2]);
        const c2 = L(nx + s2[0], ny + s2[1], nz + s2[2]);
        const c3 = L(nx + s1[0] + s2[0], ny + s1[1] + s2[1], nz + s1[2] + s2[2]);
        const corner = c1[2] && c2[2] ? [0, 0, true] : c3;
        let ss = 0, bb = 0, cnt = 0;
        for (const c of [c0, c1, c2, corner]) if (!c[2]) { ss += c[0]; bb += c[1]; cnt++; }
        const ao = c1[2] && c2[2] ? 0 : 3 - ((c1[2] ? 1 : 0) + (c2[2] ? 1 : 0) + (corner[2] ? 1 : 0));
        aos.push(ao);
        LT.push([cnt ? ss / cnt / 15 : 0, cnt ? bb / cnt / 15 : 0, [0.42, 0.6, 0.8, 1][ao]]);
      }
      const UV = verts.map((v) => tileUV(tile, faceST(f, v)));
      buf.quad(verts.map((v) => [v[0] + x, v[1] + y, v[2] + z]), UV, LT, hl, aos[0] + aos[2] < aos[1] + aos[3], FN[f]);
    }

    // partial box (coords 0..16), flat light; faces on the cell edge cull against opaque neighbours
    function box(buf, x, y, z, bx, tiles, hl, ownL, skip) {
      const b = bx.map((c) => c / 16);
      for (let f = 0; f < 6; f++) {
        if (skip && skip[f]) continue;
        const n = FN[f];
        const onEdge = (f === 0 && b[3] >= 1) || (f === 1 && b[0] <= 0) || (f === 2 && b[4] >= 1) ||
          (f === 3 && b[1] <= 0) || (f === 4 && b[5] >= 1) || (f === 5 && b[2] <= 0);
        let l = ownL;
        if (onEdge) {
          const nb = cell(x + n[0], y + n[1], z + n[2]);
          if (nb && nb.opaque) continue;
          const nl = L(x + n[0], y + n[1], z + n[2]);
          l = [Math.max(nl[0], ownL[0]), Math.max(nl[1], ownL[1])];
        }
        const verts = faceVerts(f, b);
        const LT = [l[0] / 15, l[1] / 15, 1];
        const UV = verts.map((v) => tileUV(tiles[f], faceST(f, v)));
        buf.quad(verts.map((v) => [v[0] + x, v[1] + y, v[2] + z]), UV, [LT, LT, LT, LT], hl, false, FN[f]);
      }
    }
    function plane(buf, x, y, z, P, tile, l, hl) {   // double-sided quad, P in 0..16 coords, uv full tile
      const pts = P.map((p) => [x + p[0] / 16, y + p[1] / 16, z + p[2] / 16]);
      const st = [[0, 1], [1, 1], [1, 0], [0, 0]];
      const UV = st.map((s) => tileUV(tile, s));
      const LT = [l[0] / 15, l[1] / 15, 0.92];
      buf.quad(pts, UV, [LT, LT, LT, LT], hl, false, UP);
      buf.quad([pts[1], pts[0], pts[3], pts[2]], [UV[1], UV[0], UV[3], UV[2]], [LT, LT, LT, LT], hl, false, UP);
    }
    function rotBox(bx, facing) {   // rotate a box defined for facing north around the cell centre
      let [x0, y0, z0, x1, y1, z1] = bx;
      const r = { north: 0, east: 1, south: 2, west: 3 }[facing] || 0;
      for (let k = 0; k < r; k++) {     // clockwise: (x, z) -> (16 - z, x)
        [x0, z0, x1, z1] = [16 - z1, x0, 16 - z0, x1];
      }
      return [x0, y0, z0, x1, y1, z1];
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
      const at = (d) => {
        const n = cell(x + DIRV[d][0], y, z + DIRV[d][1]);
        return n && n.shape === "stair" && n.props.half === half ? n : null;
      };
      const axis = (d) => (d === "north" || d === "south" ? "z" : "x");
      const canTake = (d) => { const n = at(d); return !(n && n.props.facing === f); };
      const back = at(f);
      if (back && axis(back.props.facing) !== axis(f) && canTake(OPP[back.props.facing]))
        return back.props.facing === LEFT[f] ? "outer_left" : "outer_right";
      const front = at(OPP[f]);
      if (front && axis(front.props.facing) !== axis(f) && canTake(front.props.facing))
        return front.props.facing === LEFT[f] ? "inner_left" : "inner_right";
      return "none";
    }

    const { x0, y0, z0, sx, sy, sz } = vol;
    for (let y = y0; y < y0 + sy; y++) for (let z = z0; z < z0 + sz; z++) for (let x = x0; x < x0 + sx; x++) {
      const i = I(x, y, z);
      const id = vol.ids[i] - 1;
      if (id < 0) continue;
      const v = pal.v(id);
      const sh = v.shape;
      if (sh === "air") continue;
      const hl = vol.step[i] && vol.step[i] === hlStep ? 1 : 0;
      const T = v.tiles;
      if (sh === "path") {
        box(solid, x, y, z, [0, 0, 0, 16, 15, 16], T, hl, own(x, y, z));
        continue;
      }
      if (sh === "cube" || sh === "log" || sh === "glass" || sh === "leaves") {
        for (let f = 0; f < 6; f++) {
          const n = FN[f];
          const nb = cell(x + n[0], y + n[1], z + n[2]);
          // paths are 15/16 tall: keep the side face next to them so there is no gap
          if (nb && ((nb.opaque && (nb.shape !== "path" || f === 2 || f === 3)) || ((sh === "glass" || sh === "leaves") && nb.key === v.key))) continue;
          cubeFace(solid, x, y, z, f, T[f], hl);
        }
        continue;
      }
      const ol = own(x, y, z);
      const p = v.props;
      switch (sh) {
        case "slab":
          box(solid, x, y, z, p.half === "top" ? [0, 8, 0, 16, 16, 16] : [0, 0, 0, 16, 8, 16], T, hl, ol);
          break;
        case "stair": {
          const top = p.half === "top";
          box(solid, x, y, z, top ? [0, 8, 0, 16, 16, 16] : [0, 0, 0, 16, 8, 16], T, hl, ol);
          const corner = stairCorner(x, y, z, v);
          const ya = top ? 0 : 8, yb = top ? 8 : 16;
          // quadrants of the upper layer: which are filled
          const back = DIRV[p.facing], left = DIRV[LEFT[p.facing]];
          for (const qx of [0, 1]) for (const qz of [0, 1]) {
            const cx = qx ? 1 : -1, cz = qz ? 1 : -1;
            const isBack = cx * back[0] + cz * back[1] > 0;
            const isLeft = cx * left[0] + cz * left[1] > 0;
            let on = isBack;
            if (corner === "outer_left") on = isBack && isLeft;
            else if (corner === "outer_right") on = isBack && !isLeft;
            else if (corner === "inner_left") on = isBack || isLeft;
            else if (corner === "inner_right") on = isBack || !isLeft;
            if (on) box(solid, x, y, z, [qx * 8, ya, qz * 8, qx * 8 + 8, yb, qz * 8 + 8], T, hl, ol);
          }
          break;
        }
        case "fence": case "wall": case "pane": {
          const post = sh === "fence" ? [6, 0, 6, 10, 16, 10] : sh === "wall" ? [4, 0, 4, 12, 16, 12] : [7, 0, 7, 9, 16, 9];
          const conns = {};
          for (const d of ["north", "east", "south", "west"]) conns[d] = connects(v, cell(x + DIRV[d][0], y, z + DIRV[d][1]), d);
          const any = Object.values(conns).some(Boolean);
          const straight = (conns.north && conns.south && !conns.east && !conns.west) || (conns.east && conns.west && !conns.north && !conns.south);
          if (sh !== "wall" || !straight || cell(x, y + 1, z)) box(solid, x, y, z, post, T, hl, ol);
          if (sh === "pane" && !any) { box(solid, x, y, z, [0, 0, 7, 16, 16, 9], T, hl, ol); break; }
          for (const d in conns) {
            if (!conns[d]) continue;
            if (sh === "fence") {
              box(solid, x, y, z, rotBox([7, 12, 0, 9, 15, 6], d), T, hl, ol);
              box(solid, x, y, z, rotBox([7, 6, 0, 9, 9, 6], d), T, hl, ol);
            } else if (sh === "wall") box(solid, x, y, z, rotBox([5, 0, 0, 11, 14, 8], d), T, hl, ol);
            else box(solid, x, y, z, rotBox([7, 0, 0, 9, 16, 7], d), T, hl, ol);
          }
          break;
        }
        case "fence_gate": {
          const f = p.open ? (p.facing === "north" || p.facing === "south" ? "east" : "north") : p.facing;
          for (const bx of [[0, 5, 7, 2, 16, 9], [14, 5, 7, 16, 16, 9]]) box(solid, x, y, z, rotBox(bx, p.facing), T, hl, ol);
          if (!p.open) for (const bx of [[2, 6, 7, 14, 9, 9], [2, 12, 7, 14, 15, 9], [6, 9, 7, 10, 12, 9]]) box(solid, x, y, z, rotBox(bx, f), T, hl, ol);
          else for (const bx of [[0, 6, 9, 2, 15, 16], [14, 6, 9, 16, 15, 16]]) box(solid, x, y, z, rotBox(bx, p.facing), T, hl, ol);
          break;
        }
        case "door": {
          // closed: panel on the side you approach from; open: swung to the hinge side
          const side = p.open ? (p.hinge === "right" ? RIGHT[p.facing] : LEFT[p.facing]) : OPP[p.facing];
          box(solid, x, y, z, rotBox([0, 0, 0, 16, 16, 3], side), T, hl, ol);
          break;
        }
        case "trapdoor":
          if (p.open) box(solid, x, y, z, rotBox([0, 0, 0, 16, 16, 3], OPP[p.facing]), T, hl, ol);
          else box(solid, x, y, z, p.half === "top" ? [0, 13, 0, 16, 16, 16] : [0, 0, 0, 16, 3, 16], T, hl, ol);
          break;
        case "carpet":
          box(solid, x, y, z, [0, 0, 0, 16, 1, 16], T, hl, ol);
          break;
        case "bed":
          box(solid, x, y, z, [0, 0, 0, 16, 9, 16], T, hl, ol);
          break;
        case "chest":
          box(solid, x, y, z, [1, 0, 1, 15, 14, 15], T, hl, ol);
          break;
        case "campfire":
          box(solid, x, y, z, [0, 0, 0, 16, 7, 16], T, hl, ol);
          break;
        case "pot":
          box(solid, x, y, z, [5, 0, 5, 11, 6, 11], T, hl, ol);
          break;
        case "chain": {
          const a = p.axis || "y";
          box(solid, x, y, z, a === "y" ? [7, 0, 7, 9, 16, 9] : a === "x" ? [0, 7, 7, 16, 9, 9] : [7, 7, 0, 9, 9, 16], T, hl, ol);
          break;
        }
        case "ladder":
          box(solid, x, y, z, rotBox([0, 0, 15, 16, 16, 16], p.facing), T, hl, [Math.max(ol[0], 0), ol[1]]);
          break;
        case "lantern":
          if (p.hanging) {
            box(solid, x, y, z, [5, 1, 5, 11, 8, 11], T, hl, [ol[0], 15]);
            box(solid, x, y, z, [6, 8, 6, 10, 10, 10], T, hl, [ol[0], 15]);
            box(solid, x, y, z, [7.5, 10, 7.5, 8.5, 16, 8.5], T, hl, [ol[0], 15]);
          } else {
            box(solid, x, y, z, [5, 0, 5, 11, 7, 11], T, hl, [ol[0], 15]);
            box(solid, x, y, z, [6, 7, 6, 10, 9, 10], T, hl, [ol[0], 15]);
          }
          break;
        case "torch":
          if (p.facing === "up") box(solid, x, y, z, [7, 0, 7, 9, 10, 9], T, hl, [ol[0], 15]);
          else box(solid, x, y, z, rotBox([7, 3, 12, 9, 13, 14], p.facing), T, hl, [ol[0], 15]);
          break;
        case "plant": case "tall_plant":
          plane(solid, x, y, z, [[1, 0, 1], [15, 0, 15], [15, 16, 15], [1, 16, 1]], T[4], ol, hl);
          plane(solid, x, y, z, [[1, 0, 15], [15, 0, 1], [15, 16, 1], [1, 16, 15]], T[4], ol, hl);
          break;
        case "crop":
          for (const c of [4, 12]) {
            plane(solid, x, y, z, [[c, 0, 0], [c, 0, 16], [c, 16, 16], [c, 16, 0]], T[4], ol, hl);
            plane(solid, x, y, z, [[0, 0, c], [16, 0, c], [16, 16, c], [0, 16, c]], T[4], ol, hl);
          }
          break;
        case "flat": {
          const LT = [ol[0] / 15, ol[1] / 15, 1];
          const pts = [[x, y + 0.02, z + 1], [x + 1, y + 0.02, z + 1], [x + 1, y + 0.02, z], [x, y + 0.02, z]];
          const UV = [[0, 1], [1, 1], [1, 0], [0, 0]].map((s) => tileUV(T[2], s));
          solid.quad(pts, UV, [LT, LT, LT, LT], hl, false, UP);
          break;
        }
        case "water": {
          const up = cell(x, y + 1, z);
          const topH = up && up.shape === "water" ? 1 : 14 / 16;
          for (let f = 0; f < 6; f++) {
            const n = FN[f];
            const nb = cell(x + n[0], y + n[1], z + n[2]);
            if (nb && (nb.shape === "water" || nb.opaque)) continue;
            if (f === 2 && topH === 1) continue;
            const verts = faceVerts(f, [0, 0, 0, 1, topH, 1]);
            const l = L(x + n[0], y + n[1], z + n[2]);
            const ll = [Math.max(l[0], ol[0]) / 15, Math.max(l[1], ol[1]) / 15, 1];
            const UV = verts.map((vv) => tileUV(T[f], faceST(f, vv)));
            water.quad(verts.map((vv) => [vv[0] + x, vv[1] + y, vv[2] + z]), UV, [ll, ll, ll, ll], hl, false, FN[f]);
          }
          break;
        }
        default:
          box(solid, x, y, z, [0, 0, 0, 16, 16, 16], T, hl, ol);
      }
    }
    return { solid: solid.geometry(), water: water.geometry() };
  }
  MC.mesh = Mesher;

  // translucent "later steps" boxes, one colour per block
  MC.ghostMesh = function (cells, pal) {
    const set = new Set(cells.map((c) => c[0] + "," + c[1] + "," + c[2]));
    const pos = [], col = [], idx = [];
    let n = 0;
    for (const [x, y, z, vid] of cells) {
      const c = MC.hexToRgb(pal.v(vid).color).map((v) => v / 255);
      for (let f = 0; f < 6; f++) {
        const d = FN[f];
        if (set.has(x + d[0] + "," + (y + d[1]) + "," + (z + d[2]))) continue;
        for (const v of faceVerts(f, [0.02, 0.02, 0.02, 0.98, 0.98, 0.98])) { pos.push(v[0] + x, v[1] + y, v[2] + z); col.push(...c); }
        idx.push(n, n + 1, n + 2, n, n + 2, n + 3);
        n += 4;
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    g.setIndex(n > 65000 ? new THREE.Uint32BufferAttribute(idx, 1) : new THREE.Uint16BufferAttribute(idx, 1));
    return g;
  };

  // voxel ray cast (Amanatides & Woo). Returns {x,y,z, face normal [nx,ny,nz], t} or null.
  MC.raycast = function (vol, pal, origin, dir, maxDist, skipWater = true) {
    let x = Math.floor(origin.x), y = Math.floor(origin.y), z = Math.floor(origin.z);
    const sx = Math.sign(dir.x), sy = Math.sign(dir.y), sz = Math.sign(dir.z);
    const tdx = Math.abs(1 / dir.x), tdy = Math.abs(1 / dir.y), tdz = Math.abs(1 / dir.z);
    let tmx = (sx > 0 ? x + 1 - origin.x : origin.x - x) * tdx;
    let tmy = (sy > 0 ? y + 1 - origin.y : origin.y - y) * tdy;
    let tmz = (sz > 0 ? z + 1 - origin.z : origin.z - z) * tdz;
    let n = [0, 0, 0], t = 0;
    for (let i = 0; i < 2000 && t <= maxDist; i++) {
      const id = vol.get(x, y, z);
      if (id >= 0) {
        const v = pal.v(id);
        if (!(skipWater && v.shape === "water") && v.shape !== "air") return { x, y, z, n, t, id };
      }
      if (tmx < tmy && tmx < tmz) { x += sx; t = tmx; tmx += tdx; n = [-sx, 0, 0]; }
      else if (tmy < tmz) { y += sy; t = tmy; tmy += tdy; n = [0, -sy, 0]; }
      else { z += sz; t = tmz; tmz += tdz; n = [0, 0, -sz]; }
    }
    return null;
  };
})();
