// Procedural 16x16 pixel textures, packed into one atlas (NearestFilter).
// A texture spec is [pattern, colour, colour...] straight from blocks/palette.json.
(function () {
  const MC = (window.MC = window.MC || {});
  const T = 16;

  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hash(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return h >>> 0;
  }
  function hex(c) {
    c = (c || "#888888").replace("#", "");
    return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)];
  }
  const clamp = (v) => (v < 0 ? 0 : v > 255 ? 255 : v | 0);
  const mul = (c, f) => [clamp(c[0] * f), clamp(c[1] * f), clamp(c[2] * f)];
  const mix = (a, b, t) => [clamp(a[0] + (b[0] - a[0]) * t), clamp(a[1] + (b[1] - a[1]) * t), clamp(a[2] + (b[2] - a[2]) * t)];

  // Each pattern paints a 16x16 buffer through put(x, y, rgb, alpha).
  const P = {
    noise(put, c, R, v = 0.12) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], 1 - v + R() * v * 2));
    },
    flat(put, c, R) { P.noise(put, c, R, 0.035); },
    smooth(put, c, R) {
      P.noise(put, c, R, 0.04);
      for (let i = 0; i < T; i++) { put(i, 0, mul(c[0], 1.08)); put(0, i, mul(c[0], 1.08)); put(i, 15, mul(c[0], 0.86)); put(15, i, mul(c[0], 0.86)); }
    },
    stone(put, c, R) {
      P.noise(put, c, R, 0.08);
      for (let k = 0; k < 7; k++) {
        const x = (R() * 14) | 0, y = (R() * 15) | 0, w = 1 + ((R() * 3) | 0);
        for (let i = 0; i < w; i++) put(x + i, y, mul(c[0], 0.8 + R() * 0.08));
      }
    },
    cobble(put, c, R, moss) {
      const pts = [];
      for (let i = 0; i < 9; i++) pts.push([R() * 16, R() * 16, 0.78 + R() * 0.35]);
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        let d1 = 1e9, d2 = 1e9, k = 0;
        for (const p of pts) for (const ox of [-16, 0, 16]) for (const oy of [-16, 0, 16]) {
          const d = (x - p[0] - ox) ** 2 + (y - p[1] - oy) ** 2;
          if (d < d1) { d2 = d1; d1 = d; k = p[2]; } else if (d < d2) d2 = d;
        }
        const edge = Math.sqrt(d2) - Math.sqrt(d1) < 1.1;
        let col = edge ? mul(c[0], 0.55) : mul(c[0], k + (R() - 0.5) * 0.08);
        if (moss && R() < 0.35 && (x + y * 3) % 5 < 3) col = mix(col, [86, 120, 48], 0.75);
        put(x, y, col);
      }
    },
    mossy_cobble(put, c, R) { P.cobble(put, c, R, true); },
    bricks_generic(put, c, R, rowH, bw, mortar, moss) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const row = (y / rowH) | 0, off = row % 2 ? bw / 2 : 0;
        const bx = Math.floor((x + off) / bw);
        const isM = y % rowH === rowH - 1 || (x + off) % bw === 0;
        let col = isM ? mortar : mul(c[0], 0.92 + ((hash("b" + row + "," + bx) % 100) / 100) * 0.16 + (R() - 0.5) * 0.06);
        if (moss && !isM && R() < 0.25) col = mix(col, [86, 120, 48], 0.7);
        put(x, y, col);
      }
    },
    stone_bricks(put, c, R) { P.bricks_generic(put, c, R, 8, 16, mul(c[0], 0.6)); },
    mossy_bricks(put, c, R) { P.bricks_generic(put, c, R, 8, 16, mul(c[0], 0.6), true); },
    bricks(put, c, R) { P.bricks_generic(put, c, R, 4, 8, [182, 172, 160]); },
    bricks_large(put, c, R) { P.bricks_generic(put, c, R, 4, 8, mul(c[0], 0.75)); },
    tiles(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const m = x % 8 === 7 || y % 8 === 7;
        put(x, y, m ? mul(c[0], 0.6) : mul(c[0], 0.95 + (R() - 0.5) * 0.12));
      }
    },
    sandstone(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const band = y < 3 ? 1.06 : y > 12 ? 0.9 : 1;
        put(x, y, mul(c[0], band * (0.96 + R() * 0.08)));
      }
    },
    planks(put, c, R) {
      for (let y = 0; y < T; y++) {
        const board = (y / 4) | 0;
        const seam = (hash("s" + board) % 12) + 2;
        const tone = 0.93 + ((hash("p" + board) % 100) / 100) * 0.13;
        for (let x = 0; x < T; x++) {
          let f = tone + (R() - 0.5) * 0.06;
          if (y % 4 === 3) f *= 0.72;
          else if (x === seam) f *= 0.8;
          else if ((x * 7 + y * 3 + board) % 9 === 0) f *= 0.92;
          put(x, y, mul(c[0], f));
        }
      }
    },
    bark(put, c, R) {
      const cols = [];
      for (let x = 0; x < T; x++) cols.push(0.82 + R() * 0.3);
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        let f = cols[x] * (0.94 + R() * 0.12);
        if ((x * 5 + ((y / 3) | 0)) % 7 === 0) f *= 0.78;
        put(x, y, mul(c[0], f));
      }
    },
    log_side_dark(put, c, R) { P.bark(put, c, R); },
    birch_bark(put, c, R) {
      P.noise(put, c, R, 0.05);
      for (let k = 0; k < 9; k++) {
        const x = (R() * 14) | 0, y = (R() * 16) | 0, w = 1 + ((R() * 3) | 0);
        for (let i = 0; i < w; i++) put(x + i, y, [44, 40, 36]);
      }
    },
    stripped(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        let f = 0.95 + R() * 0.08;
        if ((x * 3) % 7 === 0) f *= 0.9;
        put(x, y, mul(c[0], f));
      }
    },
    log_top(put, c, R) {
      const inner = c[0], bark = c[1] || mul(c[0], 0.6);
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        if (x === 0 || y === 0 || x === 15 || y === 15) { put(x, y, mul(bark, 0.9 + R() * 0.2)); continue; }
        const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5));
        put(x, y, mul(inner, (Math.floor(d) % 2 ? 0.86 : 1.0) * (0.96 + R() * 0.06)));
      }
    },
    leaves(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const r = R();
        if (r < 0.2) put(x, y, [0, 0, 0], 0);
        else put(x, y, mul(c[0], 0.7 + R() * 0.5));
      }
    },
    glass(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const edge = x === 0 || y === 0 || x === 15 || y === 15;
        const streak = (x - y === 3 || x - y === 4 || x - y === -6) && x > 2 && x < 12;
        if (edge) put(x, y, mul(c[0], 0.95), 255);
        else if (streak) put(x, y, [255, 255, 255], 150);
        else put(x, y, [0, 0, 0], 0);
      }
    },
    glass_tint(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const edge = x === 0 || y === 0 || x === 15 || y === 15;
        put(x, y, edge ? mul(c[0], 0.85) : c[0], edge ? 255 : 120);
      }
    },
    bars(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const bar = x % 5 === 2 || y === 1 || y === 14;
        put(x, y, mul(c[0], 0.9 + R() * 0.2), bar ? 255 : 0);
      }
    },
    grass_top(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], 0.82 + R() * 0.3));
    },
    grass_side(put, c, R) {
      const dirt = c[1] || [134, 96, 67];
      for (let x = 0; x < T; x++) {
        const h = 3 + ((R() * 2.2) | 0);
        for (let y = 0; y < T; y++) put(x, y, y < h ? mul(c[0], 0.82 + R() * 0.25) : mul(dirt, 0.85 + R() * 0.25));
      }
    },
    dirt(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const r = R();
        put(x, y, mul(c[0], r < 0.1 ? 0.72 : r > 0.92 ? 1.18 : 0.9 + R() * 0.15));
      }
    },
    gravel(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], [0.7, 0.85, 1.0, 1.15, 1.3][(R() * 5) | 0]));
    },
    path(put, c, R) { P.dirt(put, c, R); },
    farmland(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], (y % 4 === 0 ? 0.7 : 1) * (0.88 + R() * 0.22)));
    },
    water(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const w = Math.sin((x + y * 0.5) * 0.8) * 0.5 + Math.sin(y * 1.3 + x * 0.2) * 0.5;
        put(x, y, mul(c[0], 0.9 + w * 0.12 + R() * 0.04), 255);
      }
    },
    wool(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], ((x + y * 2) % 4 === 0 ? 0.9 : 1) * (0.94 + R() * 0.1)));
    },
    door(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const frame = x < 2 || x > 13 || y < 1 || y > 14;
        const board = (x - 2) % 4 === 3;
        let col = mul(c[0], (frame ? 0.78 : board ? 0.85 : 1) * (0.93 + R() * 0.1));
        if (y >= 3 && y <= 7 && x >= 4 && x <= 11 && !(x === 7 || x === 8)) col = [170, 200, 210];
        put(x, y, col);
      }
    },
    trapdoor(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const frame = x < 2 || x > 13 || y < 2 || y > 13 || x === 7 || x === 8 || y === 7 || y === 8;
        put(x, y, mul(c[0], 0.85 + R() * 0.15), frame ? 255 : 0);
      }
    },
    ladder(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const rail = x === 2 || x === 3 || x === 12 || x === 13;
        const rung = y % 4 === 1 && x > 3 && x < 12;
        put(x, y, mul(c[0], (rail ? 0.85 : 1) * (0.9 + R() * 0.15)), rail || rung ? 255 : 0);
      }
    },
    _clear(put) { for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, [0, 0, 0], 0); },
    _stem(put, c, R, top = 7) {
      for (let y = top; y < T; y++) put(7 + ((y % 5) === 0 ? 1 : 0), y, mul(c[0], 0.9 + R() * 0.2));
      put(6, 12, c[0]); put(5, 11, c[0]); put(9, 10, c[0]); put(10, 9, c[0]);
    },
    flower(put, c, R) {
      P._clear(put); P._stem(put, c, R);
      const pet = c[1], cen = c[2] || mul(c[1], 0.6);
      for (const [dx, dy] of [[-2, 0], [2, 0], [0, -2], [0, 2], [-1, -1], [1, -1], [-1, 1], [1, 1], [-1, 0], [1, 0], [0, -1], [0, 1]])
        put(7 + dx, 5 + dy, mul(pet, 0.9 + R() * 0.2));
      put(7, 5, cen);
    },
    flower_ball(put, c, R) {
      P._clear(put); P._stem(put, c, R, 8);
      for (let y = 1; y < 9; y++) for (let x = 3; x < 13; x++) if ((x - 7.5) ** 2 + (y - 4.5) ** 2 < 14 && R() < 0.85)
        put(x, y, R() < 0.3 ? c[2] || c[1] : mul(c[1], 0.85 + R() * 0.3));
    },
    tulip(put, c, R) {
      P._clear(put); P._stem(put, c, R, 8);
      for (let y = 3; y < 8; y++) for (let x = 6; x < 10; x++) put(x, y, mul(y < 4 && (x === 7 || x === 8) ? c[2] || c[1] : c[1], 0.9 + R() * 0.2));
    },
    sunflower(put, c, R) {
      P._clear(put); P._stem(put, c, R, 9);
      for (let y = 1; y < 10; y++) for (let x = 3; x < 13; x++) {
        const d = (x - 7.5) ** 2 + (y - 5) ** 2;
        if (d < 6) put(x, y, c[2]); else if (d < 17) put(x, y, mul(c[1], 0.9 + R() * 0.2));
      }
    },
    grass_plant(put, c, R) {
      P._clear(put);
      for (let k = 0; k < 9; k++) {
        const x = 1 + ((R() * 14) | 0), h = 5 + ((R() * 9) | 0);
        for (let y = T - 1; y > T - 1 - h; y--) put(x + (y < 6 && k % 2 ? 1 : 0), y, mul(c[0], 0.75 + (T - y) / 40 + R() * 0.1));
      }
    },
    fern(put, c, R) {
      P._clear(put);
      for (let y = 2; y < T; y++) {
        const w = Math.max(1, 6 - Math.abs(y - 9) / 1.5) | 0;
        for (let x = 8 - w; x <= 7 + w; x++) if ((x + y) % 2 || x === 7) put(x, y, mul(c[0], 0.8 + R() * 0.3));
      }
    },
    bush(put, c, R) {
      P._clear(put);
      for (let y = 3; y < T; y++) for (let x = 1; x < 15; x++) if ((x - 7.5) ** 2 / 50 + (y - 10) ** 2 / 45 < 1 && R() < 0.85)
        put(x, y, mul(c[0], 0.7 + R() * 0.45));
    },
    berry_bush(put, c, R) {
      P.bush(put, c, R);
      for (let k = 0; k < 7; k++) put(3 + ((R() * 10) | 0), 6 + ((R() * 8) | 0), c[1]);
    },
    cane(put, c, R) {
      P._clear(put);
      for (const x of [3, 4, 8, 9, 12, 13]) for (let y = 0; y < T; y++) put(x, y, mul(c[0], y % 6 === 0 ? 0.7 : 0.9 + R() * 0.2));
    },
    crop(put, c, R) {
      P._clear(put);
      for (const x of [2, 5, 8, 11, 14]) {
        const h = 9 + ((R() * 5) | 0);
        for (let y = T - 1; y > T - 1 - h; y--) put(x, y, y < T - h + 3 ? c[1] : mul(c[0], 0.85 + R() * 0.2));
      }
    },
    lily(put, c, R) {
      P._clear(put);
      for (let y = 1; y < 15; y++) for (let x = 1; x < 15; x++) {
        const d = (x - 7.5) ** 2 + (y - 7.5) ** 2;
        if (d < 42 && !(x > 7 && Math.abs(y - 7.5) < (x - 7) / 2)) put(x, y, mul(c[0], 0.8 + R() * 0.3));
      }
    },
    petals(put, c, R) {
      P._clear(put);
      for (let k = 0; k < 22; k++) put((R() * 16) | 0, (R() * 16) | 0, mul(c[0], 0.85 + R() * 0.25));
      for (let k = 0; k < 6; k++) put((R() * 16) | 0, (R() * 16) | 0, [90, 140, 50]);
    },
    lantern(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const frame = x < 2 || x > 13 || y < 2 || y > 13;
        put(x, y, frame ? mul(c[0], 0.9 + R() * 0.2) : mix(c[1], [255, 255, 230], R() * 0.4));
      }
    },
    torch(put, c, R) {
      P._clear(put);
      for (let y = 6; y < T; y++) { put(7, y, mul(c[0], 0.9)); put(8, y, mul(c[0], 1.1)); }
      put(7, 5, c[1]); put(8, 5, c[1]); put(7, 4, [255, 240, 180]); put(8, 4, [255, 250, 200]);
    },
    glow(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], 0.8 + R() * 0.45));
    },
    chest(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        let col = mul(c[0], 0.9 + R() * 0.12);
        if (x === 0 || x === 15 || y === 0 || y === 15) col = mul(c[0], 0.6);
        if (y === 5) col = mul(c[0], 0.55);
        if (y >= 4 && y <= 7 && x >= 7 && x <= 8) col = [200, 200, 200];
        put(x, y, col);
      }
    },
    barrel_top(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const edge = x < 2 || x > 13 || y < 2 || y > 13;
        put(x, y, mul(c[0], (edge ? 0.7 : (y % 4 === 3 ? 0.8 : 1)) * (0.92 + R() * 0.12)));
      }
    },
    barrel_side(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const hoop = y === 2 || y === 3 || y === 12 || y === 13;
        put(x, y, hoop ? [70, 70, 70] : mul(c[0], (x % 4 === 3 ? 0.8 : 1) * (0.92 + R() * 0.12)));
      }
    },
    crafting_top(put, c, R) {
      P.planks(put, c, R);
      for (let i = 2; i < 14; i++) { put(i, 2, [60, 40, 20]); put(i, 13, [60, 40, 20]); put(2, i, [60, 40, 20]); put(13, i, [60, 40, 20]); }
      for (let i = 4; i < 12; i++) { put(i, 7, [70, 50, 30]); put(7, i, [70, 50, 30]); }
    },
    crafting_side(put, c, R) {
      P.planks(put, c, R);
      for (let x = 3; x < 13; x++) { put(x, 3, [90, 90, 90]); if (x % 3 === 0) for (let y = 4; y < 9; y++) put(x, y, [120, 90, 60]); }
    },
    furnace_front(put, c, R) {
      P.smooth(put, c, R);
      for (let y = 8; y < 13; y++) for (let x = 4; x < 12; x++) put(x, y, y > 10 ? [255, 140, 40] : [30, 30, 30]);
      for (let x = 3; x < 13; x++) put(x, 4, mul(c[0], 0.6));
    },
    bookshelf(put, c, R) {
      const books = [[150, 40, 40], [40, 80, 140], [60, 120, 50], [170, 140, 50], [110, 50, 120], [200, 200, 190]];
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        if (y < 1 || y > 14 || y === 7 || y === 8) { put(x, y, mul(c[0], 0.9 + R() * 0.1)); continue; }
        const b = books[hash("bk" + ((x / 2) | 0) + (y > 7 ? "u" : "d")) % books.length];
        put(x, y, x % 2 === 1 ? mul(b, 0.75) : b);
      }
    },
    hay_side(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const band = y === 3 || y === 4 || y === 11 || y === 12;
        put(x, y, band ? [140, 40, 30] : mul(c[0], 0.85 + R() * 0.3));
      }
    },
    hay_top(put, c, R) { P.noise(put, [mul(c[0], 0.95)], R, 0.2); },
    pumpkin_side(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], (x % 4 === 0 ? 0.8 : 1) * (0.92 + R() * 0.12)));
    },
    pumpkin_top(put, c, R) {
      P.pumpkin_side(put, c, R);
      for (let y = 6; y < 10; y++) for (let x = 6; x < 10; x++) put(x, y, [90, 110, 40]);
    },
    melon(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) put(x, y, mul(c[0], (x % 5 === 0 ? 1.25 : 1) * (0.9 + R() * 0.15)));
    },
    campfire_top(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const log = y < 4 || y > 11 || x < 4 || x > 11;
        put(x, y, log ? mul(c[0], 0.8 + R() * 0.3) : mix(c[1], [255, 230, 120], R() * 0.6));
      }
    },
    chain(put, c, R) {
      P._clear(put);
      for (let y = 0; y < T; y++) { const o = y % 6 < 3 ? 0 : 1; put(7 + o, y, mul(c[0], 1.2)); put(8 - o, y, c[0]); }
    },
    metal(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const edge = x === 0 || y === 0 || x === 15 || y === 15;
        put(x, y, mul(c[0], edge ? 0.8 : 0.95 + R() * 0.08));
      }
    },
    bed(put, c, R) {
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        let col = mul(c[0], 0.9 + R() * 0.12);
        if (x === 0 || x === 15) col = mul(c[0], 0.7);
        put(x, y, col);
      }
    },
    pillow(put, c, R) {
      P.bed(put, c, R);
      for (let y = 1; y < 8; y++) for (let x = 2; x < 14; x++) put(x, y, mul(c[1], 0.92 + R() * 0.08));
    },
  };

  class Atlas {
    constructor(cols = 32, rows = 32) {
      this.cols = cols;
      this.rows = rows;
      this.canvas = document.createElement("canvas");
      this.canvas.width = cols * T;
      this.canvas.height = rows * T;
      this.ctx = this.canvas.getContext("2d");
      this.map = new Map();
      this.n = 0;
      this.alpha = [];      // tile index -> has transparent pixels
      this.avg = [];
      this.texture = null;
    }
    get(spec) {
      const key = JSON.stringify(spec);
      if (this.map.has(key)) return this.map.get(key);
      const idx = this.n++;
      const img = this.ctx.createImageData(T, T);
      const R = rng(hash(key));
      const cols = spec.slice(1).map(hex);
      let transparent = false, sr = 0, sg = 0, sb = 0, cnt = 0;
      const put = (x, y, rgb, a = 255) => {
        if (x < 0 || y < 0 || x >= T || y >= T) return;
        const o = (y * T + x) * 4;
        img.data[o] = rgb[0]; img.data[o + 1] = rgb[1]; img.data[o + 2] = rgb[2]; img.data[o + 3] = a;
      };
      (P[spec[0]] || P.noise)(put, cols, R);
      for (let i = 0; i < T * T; i++) {
        const a = img.data[i * 4 + 3];
        if (a < 250) transparent = true;
        if (a > 0) { sr += img.data[i * 4]; sg += img.data[i * 4 + 1]; sb += img.data[i * 4 + 2]; cnt++; }
      }
      this.ctx.putImageData(img, (idx % this.cols) * T, ((idx / this.cols) | 0) * T);
      this.alpha[idx] = transparent;
      this.avg[idx] = cnt ? [sr / cnt, sg / cnt, sb / cnt] : [0, 0, 0];
      this.map.set(key, idx);
      if (this.texture) this.texture.needsUpdate = true;
      return idx;
    }
    uv(idx) {
      const u = (idx % this.cols) / this.cols, v = ((idx / this.cols) | 0) / this.rows;
      return [u, v, 1 / this.cols, 1 / this.rows];
    }
    three() {
      if (!this.texture) {
        this.texture = new THREE.CanvasTexture(this.canvas);
        this.texture.magFilter = THREE.NearestFilter;
        this.texture.minFilter = THREE.NearestFilter;
        this.texture.generateMipmaps = false;
        this.texture.colorSpace = THREE.SRGBColorSpace;
        this.texture.flipY = false;
      }
      return this.texture;
    }
    // small swatch canvas for the picker / inventory
    swatch(idx, size = 32) {
      const c = document.createElement("canvas");
      c.width = c.height = size;
      const g = c.getContext("2d");
      g.imageSmoothingEnabled = false;
      g.drawImage(this.canvas, (idx % this.cols) * T, ((idx / this.cols) | 0) * T, T, T, 0, 0, size, size);
      return c;
    }
  }

  MC.Atlas = Atlas;
  MC.hexToRgb = hex;
})();
