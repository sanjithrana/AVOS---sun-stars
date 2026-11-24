/* STAGE kit v1 (Claude 3D Styles, free from Anylancer.com)
   A small "film camera" for three.js: every frame is rendered many times with tiny changes
   (lens position, light position, time, sub-pixel offset) and averaged. That gives real depth of
   field, soft area-light shadows, motion blur and clean edges with core three.js only (no addons).

   Usage:  const S = await K.run(canvas, style, { format: "9:16", samples: 16 });
           S.seek(t)            // draws time t (seconds) with the full sample count
           S.seek(t, 2)         // quick preview with 2 samples
   A style is { name, duration, fonts, samples, grade, build(S) -> update(t), sound(k) }.
   update(t) must set the WHOLE scene for time t (it is called many times per frame). Use K.rng(seed), never Math.random. */
(function () {
  const K = (window.K = window.K || {});
  const FORMATS = { "9:16d": [540, 960], "16:9d": [960, 540], "1:1d": [720, 720], "9:16": [1080, 1920], "16:9": [1920, 1080], "1:1": [1080, 1080], "4:5": [1080, 1350] };

  /* ---------- maths ---------- */
  K.rng = (seed = 1) => { let s = (seed * 2654435761) >>> 0 || 1; return () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };
  K.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  K.lerp = (a, b, t) => a + (b - a) * t;
  K.prog = (t, a, b) => K.clamp((t - a) / (b - a));
  K.smooth = (x) => x * x * (3 - 2 * x);
  K.ease = {
    lin: (x) => x,
    in: (x) => x * x * x,
    out: (x) => 1 - Math.pow(1 - x, 3),
    inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    sine: (x) => 0.5 - 0.5 * Math.cos(Math.PI * x),
    expo: (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2),
    back: (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
    spring: (x) => (x >= 1 ? 1 : 1 - Math.exp(-6.5 * x) * Math.cos(11 * x)),
    bounce: (x) => { const n = 7.5625, d = 2.75; if (x < 1 / d) return n * x * x; if (x < 2 / d) return n * (x -= 1.5 / d) * x + 0.75; if (x < 2.5 / d) return n * (x -= 2.25 / d) * x + 0.9375; return n * (x -= 2.625 / d) * x + 0.984375; },
  };
  /** eased 0..1 between times a and b */
  K.tw = (t, a, b, e = K.ease.inOut) => e(K.prog(t, a, b));
  /** keyframes: K.keys(t, [[0,[x,y,z]],[2,[..]]], ease) -> number or array */
  K.keys = (t, list, e = K.ease.inOut) => {
    if (t <= list[0][0]) return list[0][1];
    for (let i = 0; i < list.length - 1; i++) {
      const [a, va] = list[i], [b, vb] = list[i + 1];
      if (t <= b) { const k = (list[i + 1][2] || e)(K.prog(t, a, b)); return Array.isArray(va) ? va.map((v, j) => v + (vb[j] - v) * k) : va + (vb - va) * k; }
    }
    return list[list.length - 1][1];
  };
  K.halton = (i, b) => { let f = 1, r = 0; while (i > 0) { f /= b; r += f * (i % b); i = Math.floor(i / b); } return r; };
  /** smooth value noise in 1D, deterministic */
  K.wobble = (t, seed = 1, freq = 1) => { const x = t * freq + seed * 17.13, i = Math.floor(x), f = x - i; const h = (n) => { const s = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453; return s - Math.floor(s); }; return K.lerp(h(i), h(i + 1), K.smooth(f)) * 2 - 1; };

  /* ---------- textures drawn in code ---------- */
  K.canvas = (w, h) => { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; };
  /** fBm value noise into a grey canvas (for bump / roughness / grain maps) */
  K.noiseCanvas = (size = 256, seed = 1, scale = 8, oct = 4, contrast = 1) => {
    const c = K.canvas(size, size), x = c.getContext("2d"), img = x.createImageData(size, size), r = K.rng(seed);
    const G = 64, grid = new Float32Array(G * G); for (let i = 0; i < G * G; i++) grid[i] = r();
    const vn = (u, v) => { const i = Math.floor(u), j = Math.floor(v), fu = K.smooth(u - i), fv = K.smooth(v - j); const g = (a, b) => grid[(((b % G) + G) % G) * G + (((a % G) + G) % G)]; return K.lerp(K.lerp(g(i, j), g(i + 1, j), fu), K.lerp(g(i, j + 1), g(i + 1, j + 1), fu), fv); };
    for (let py = 0; py < size; py++) for (let px = 0; px < size; px++) {
      let a = 0, amp = 0.5, f = scale / size, tot = 0;
      for (let o = 0; o < oct; o++) { a += amp * vn(px * f, py * f); tot += amp; amp *= 0.5; f *= 2; }
      const v = K.clamp(0.5 + (a / tot - 0.5) * contrast) * 255, k = (py * size + px) * 4;
      img.data[k] = img.data[k + 1] = img.data[k + 2] = v; img.data[k + 3] = 255;
    }
    x.putImageData(img, 0, 0); return c;
  };
  K.tex = (canvas, { srgb = true, repeat = [1, 1], aniso = 8 } = {}) => {
    const T = window.THREE, t = new T.CanvasTexture(canvas);
    if (srgb) t.colorSpace = T.SRGBColorSpace;
    t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); t.anisotropy = aniso; t.needsUpdate = true; return t;
  };

  /* ---------- geometry ---------- */
  /** rounded box: real rounded edges and corners, smooth normals */
  K.rbox = (w, h, d, r = 0.1, s = 5) => {
    const T = window.THREE; r = Math.max(1e-4, Math.min(r, w / 2 - 1e-4, h / 2 - 1e-4, d / 2 - 1e-4));
    const n = 2 * s + 1, g = new T.BoxGeometry(1, 1, 1, n, n, n), P = g.attributes.position, N = g.attributes.normal;
    const half = [w / 2, h / 2, d / 2];
    const map = (u, hw) => { const k = Math.round((u + 0.5) * n); return k <= s ? -hw + r * (k / s) : hw - r * ((n - k) / s); };
    const p = new T.Vector3(), q = new T.Vector3(), m = new T.Vector3();
    for (let i = 0; i < P.count; i++) {
      p.set(map(P.getX(i), half[0]), map(P.getY(i), half[1]), map(P.getZ(i), half[2]));
      q.set(K.clamp(p.x, -half[0] + r, half[0] - r), K.clamp(p.y, -half[1] + r, half[1] - r), K.clamp(p.z, -half[2] + r, half[2] - r));
      m.subVectors(p, q); if (m.lengthSq() > 1e-12) { m.normalize(); p.copy(q).addScaledVector(m, r); N.setXYZ(i, m.x, m.y, m.z); }
      P.setXYZ(i, p.x, p.y, p.z);
    }
    g.computeBoundingSphere(); return g;
  };
  /** rounded rectangle THREE.Shape (for extrusions, cards, tiles) */
  K.rrectShape = (w, h, r) => { const T = window.THREE, s = new T.Shape(), x = -w / 2, y = -h / 2; r = Math.min(r, w / 2, h / 2);
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r); s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r); s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y); return s; };
  /** seamless studio sweep (floor that curves up into a back wall), centred at origin, floor at y=0 */
  K.sweep = (w = 40, depth = 20, height = 20, radius = 6, seg = 48) => {
    const T = window.THREE, pts = [];
    pts.push([depth, 0]);
    for (let i = 0; i <= seg; i++) { const a = (i / seg) * Math.PI / 2; pts.push([-Math.sin(a) * radius, radius - Math.cos(a) * radius]); }
    pts.push([-radius, height]);
    const g = new T.BufferGeometry(), pos = [], uv = [], idx = [], cols = 2; let len = 0; const L = [0];
    for (let i = 1; i < pts.length; i++) { len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); L.push(len); }
    pts.forEach((p, i) => { for (let c = 0; c < cols; c++) { pos.push((c - 0.5) * w, p[1], p[0]); uv.push(c, L[i] / len); } });
    for (let i = 0; i < pts.length - 1; i++) { const a = i * 2, b = a + 1, c = a + 2, d = a + 3; idx.push(a, b, c, b, d, c); }
    g.setIndex(idx); g.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); g.setAttribute("uv", new T.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
  };

  /* ---------- the stage ---------- */
  const FULL_VS = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }";
  const ACC_FS = "uniform sampler2D tex; uniform float w; varying vec2 vUv; void main(){ gl_FragColor = vec4(texture2D(tex, vUv).rgb * w, 1.); }";
  const BRIGHT_FS = "uniform sampler2D tex; uniform float thr; varying vec2 vUv; void main(){ vec3 c = texture2D(tex, vUv).rgb; float l = max(c.r, max(c.g, c.b)); float k = max(l - thr, 0.) / max(l, 1e-4); gl_FragColor = vec4(c * k, 1.); }";
  const BLUR_FS = "uniform sampler2D tex; uniform vec2 dir; varying vec2 vUv; void main(){ vec3 c = texture2D(tex, vUv).rgb * .227; c += (texture2D(tex, vUv + dir * 1.385).rgb + texture2D(tex, vUv - dir * 1.385).rgb) * .316; c += (texture2D(tex, vUv + dir * 3.23).rgb + texture2D(tex, vUv - dir * 3.23).rgb) * .0703; gl_FragColor = vec4(c, 1.); }";
  const FINAL_FS = `
    uniform sampler2D tAcc, tBloom; uniform float exposure, bloom, sat, contrast, vig, grain, frame, tm, warm;
    uniform vec3 lift, gain; uniform vec2 res; varying vec2 vUv;
    vec3 aces(vec3 x){ return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14), 0., 1.); }
    vec3 neutral(vec3 c){ float x = min(c.r, min(c.g, c.b)); float off = x < .08 ? x - 6.25*x*x : .04; c -= off;
      float pk = max(c.r, max(c.g, c.b)); if (pk < .76) return c; float d = .24; float np = 1. - d*d/(pk + d - .76);
      c *= np / pk; float g = 1. - 1. / (.15 * (pk - np) + 1.); return mix(c, vec3(np), g); }
    vec3 toSRGB(vec3 c){ c = clamp(c, 0., 1.); return mix(c * 12.92, 1.055 * pow(c, vec3(1./2.4)) - .055, step(.0031308, c)); }
    float hash(vec2 p){ p = fract(p * vec2(443.897, 441.423)); p += dot(p, p.yx + 19.19); return fract((p.x + p.y) * p.x); }
    void main(){
      vec3 c = texture2D(tAcc, vUv).rgb + texture2D(tBloom, vUv).rgb * bloom;
      c *= exposure; c *= gain; c.r *= 1. + warm * .06; c.b *= 1. - warm * .06;
      c = tm < .5 ? aces(c) : (tm < 1.5 ? neutral(c) : clamp(c, 0., 1.));
      float l = dot(c, vec3(.2126, .7152, .0722)); c = mix(vec3(l), c, sat);
      c = toSRGB(c);
      c = (c - .5) * contrast + .5; c = c + lift * (1. - c);
      vec2 q = vUv - .5; q.x *= res.x / res.y; float v = smoothstep(.95, .25, length(q) * (1. + vig * .4)); c *= mix(1., v, vig);
      c += (hash(vUv * res + frame * 13.7) - .5) * grain;
      gl_FragColor = vec4(clamp(c, 0., 1.), 1.);
    }`;

  K.run = async (canvas, style, opts = {}) => {
    const T = window.THREE; if (!T) throw new Error("STAGE: window.THREE is not set");
    const fmt = opts.format || style.format || "16:9";
    const [W, H] = opts.size || FORMATS[fmt] || FORMATS["16:9"];
    canvas.width = W; canvas.height = H;
    if (style.fonts && style.fonts.length) await K.loadFonts(style.fonts);
    const renderer = new T.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(1); renderer.setSize(W, H, false); renderer.autoClear = false;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
    renderer.toneMapping = T.NoToneMapping; renderer.outputColorSpace = T.LinearSRGBColorSpace;
    const rtOpt = { type: T.HalfFloatType, format: T.RGBAFormat, depthBuffer: true, minFilter: T.LinearFilter, magFilter: T.LinearFilter };
    const rtS = new T.WebGLRenderTarget(W, H, rtOpt), rtA = new T.WebGLRenderTarget(W, H, { ...rtOpt, depthBuffer: false });
    const bw = Math.max(2, W >> 2), bh = Math.max(2, H >> 2);
    const rtB1 = new T.WebGLRenderTarget(bw, bh, { ...rtOpt, depthBuffer: false }), rtB2 = rtB1.clone();
    const quadScene = new T.Scene(), quadCam = new T.OrthographicCamera(-1, 1, 1, -1, 0, 1), quad = new T.Mesh(new T.PlaneGeometry(2, 2));
    quad.frustumCulled = false; quadScene.add(quad);
    const sm = (fs, u, extra = {}) => new T.ShaderMaterial({ vertexShader: FULL_VS, fragmentShader: fs, uniforms: u, depthTest: false, depthWrite: false, ...extra });
    const accMat = sm(ACC_FS, { tex: { value: rtS.texture }, w: { value: 1 } }, { blending: T.AdditiveBlending, transparent: true });
    const brightMat = sm(BRIGHT_FS, { tex: { value: rtA.texture }, thr: { value: 1 } });
    const blurMat = sm(BLUR_FS, { tex: { value: null }, dir: { value: new T.Vector2() } });
    const G = Object.assign({ exposure: 1, bloom: 0, bloomThreshold: 1, saturation: 1, contrast: 1, vignette: 0.25, grain: 0.012, tonemap: "aces", lift: [0, 0, 0], gain: [1, 1, 1], warm: 0 }, style.grade || {});
    const finalMat = sm(FINAL_FS, { tAcc: { value: rtA.texture }, tBloom: { value: rtB1.texture }, exposure: { value: 1 }, bloom: { value: 0 }, sat: { value: 1 }, contrast: { value: 1 }, vig: { value: 0 }, grain: { value: 0 }, frame: { value: 0 }, tm: { value: 0 }, warm: { value: 0 }, lift: { value: new T.Vector3() }, gain: { value: new T.Vector3(1, 1, 1) }, res: { value: new T.Vector2(W, H) } });
    const pass = (mat, target, clear = true) => { quad.material = mat; renderer.setRenderTarget(target); if (clear) renderer.clear(); renderer.render(quadScene, quadCam); };

    const scene = new T.Scene(), camera = new T.PerspectiveCamera(35, W / H, 0.05, 400);
    const S = { THREE: T, K, scene, camera, renderer, W, H, aspect: W / H, portrait: H > W, format: fmt, fps: opts.fps || style.fps || 30, grade: G, soft: [], time: 0 };
    const camState = { pos: new T.Vector3(0, 2, 10), target: new T.Vector3(), fov: 35, aperture: 0, focus: null, roll: 0, shift: [0, 0] };

    /** set the camera: S.cam([x,y,z], [tx,ty,tz], { fov, aperture (lens radius, world units), focus (distance; default = target distance), roll, shift:[x,y] (frame shift in NDC, keeps perspective) }) */
    S.cam = (pos, target, o = {}) => { camState.pos.set(...pos); camState.target.set(...target); camState.fov = o.fov ?? 35; camState.aperture = o.aperture ?? 0; camState.focus = o.focus ?? null; camState.roll = o.roll ?? 0; camState.shift = o.shift || [0, 0]; };
    /** pin an object to the screen at the focus distance (always sharp): sx, sy in -1..1 (frame centre = 0), wFrac = its width as a fraction of the frame width,
        baseW = its width at scale 1 (labels: mesh.userData.size[0]), pop = extra scale for pop-in animations. Call it after S.cam() in update(t). */
    const _pd = new T.Vector3(), _pr = new T.Vector3(), _pu = new T.Vector3(), _pm = new T.Matrix4();
    S.pin = (obj, sx, sy, wFrac, baseW, pop = 1) => {
      if (opts.nopins) { obj.visible = false; return obj; } // clean plates (no on-screen words)
      const D = camState.focus ?? camState.pos.distanceTo(camState.target), hh = D * Math.tan((camState.fov * Math.PI) / 360), ww = hh * S.aspect;
      _pd.subVectors(camState.target, camState.pos).normalize(); _pr.crossVectors(_pd, _pu.set(0, 1, 0)).normalize(); _pu.crossVectors(_pr, _pd);
      obj.position.copy(camState.pos).addScaledVector(_pd, D * 0.995).addScaledVector(_pr, sx * ww).addScaledVector(_pu, sy * hh);
      obj.quaternion.setFromRotationMatrix(_pm.makeBasis(_pr, _pu, _pd.clone().negate()));
      if (wFrac) obj.scale.setScalar(Math.max(0.0001, ((wFrac * 2 * ww) / (baseW || 1)) * pop));
      if (obj.material && !obj.userData.hud) { obj.material.depthTest = false; obj.renderOrder = 999; obj.userData.hud = 1; } // screen words always draw on top
      return obj;
    };
    /** distance at which a w x h region fills the frame for this aspect (use it to frame both 9:16 and 16:9) */
    S.fitDist = (w, h, fov = 35) => { const tv = Math.tan((fov * Math.PI) / 360); return Math.max(h / 2 / tv, w / 2 / (tv * S.aspect)); };
    S.rng = K.rng;
    S.add = (o, parent = scene) => { parent.add(o); return o; };
    S.mesh = (geo, mat, { pos, rot, scale, shadow = true, parent } = {}) => { const m = new T.Mesh(geo, mat); if (pos) m.position.set(...pos); if (rot) m.rotation.set(...rot); if (scale != null) Array.isArray(scale) ? m.scale.set(...scale) : m.scale.setScalar(scale); m.castShadow = m.receiveShadow = shadow; (parent || scene).add(m); return m; };
    S.group = (parent = scene, pos) => { const g = new T.Group(); if (pos) g.position.set(...pos); parent.add(g); return g; };
    S.color = (c) => new T.Color(c);

    /* materials */
    S.mat = {
      std: (color, o = {}) => new T.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0, ...o }),
      phys: (color, o = {}) => new T.MeshPhysicalMaterial({ color, roughness: 0.4, metalness: 0, ...o }),
      matte: (color, o = {}) => new T.MeshStandardMaterial({ color, roughness: 0.92, metalness: 0, ...o }),
      gloss: (color, o = {}) => new T.MeshPhysicalMaterial({ color, roughness: 0.18, clearcoat: 1, clearcoatRoughness: 0.08, ...o }),
      metal: (color, o = {}) => new T.MeshStandardMaterial({ color, roughness: 0.25, metalness: 1, ...o }),
      glass: (color = "#ffffff", o = {}) => new T.MeshPhysicalMaterial({ color, roughness: 0.03, metalness: 0, transmission: 1, thickness: 0.4, ior: 1.5, transparent: false, ...o }),
      glow: (color, power = 3) => { const m = new T.MeshBasicMaterial({ color }); m.color.multiplyScalar(power); return m; },
      basic: (color, o = {}) => new T.MeshBasicMaterial({ color, ...o }),
    };
    /** a soft bump map from noise, cached by key */
    const texCache = {};
    S.noiseTex = (key, size = 256, seed = 1, scale = 8, oct = 4, contrast = 1, repeat = [1, 1]) => (texCache[key] = texCache[key] || K.tex(K.noiseCanvas(size, seed, scale, oct, contrast), { srgb: false, repeat }));

    /* lights */
    /** directional key light with soft (area) shadows. pos is where the light sits; soft = jitter radius (world units at that distance) */
    S.sun = ({ pos = [6, 10, 6], target = [0, 0, 0], color = "#ffffff", intensity = 3, soft = 0.6, size = 8, map = 2048, bias = -0.0004, normalBias = 0.02, near = 0.5, far = 60 } = {}) => {
      const l = new T.DirectionalLight(color, intensity); l.position.set(...pos); l.target.position.set(...target);
      l.castShadow = true; const sc = l.shadow.camera; sc.left = sc.bottom = -size; sc.right = sc.top = size; sc.near = near; sc.far = far;
      l.shadow.mapSize.set(map, map); l.shadow.bias = bias; l.shadow.normalBias = normalBias; l.shadow.radius = 2;
      scene.add(l, l.target); if (soft > 0) S.soft.push({ light: l, r: soft }); return l;
    };
    S.spot = ({ pos = [0, 8, 4], target = [0, 0, 0], color = "#ffffff", intensity = 60, angle = 0.5, penumbra = 0.6, soft = 0.3, map = 2048, decay = 2, distance = 0, bias = -0.0003, shadow = true } = {}) => {
      const l = new T.SpotLight(color, intensity, distance, angle, penumbra, decay); l.position.set(...pos); l.target.position.set(...target);
      l.castShadow = shadow; l.shadow.mapSize.set(map, map); l.shadow.bias = bias; l.shadow.normalBias = 0.02; scene.add(l, l.target); if (soft > 0) S.soft.push({ light: l, r: soft }); return l;
    };
    S.point = ({ pos = [0, 2, 0], color = "#ffffff", intensity = 10, distance = 0, decay = 2, shadow = false, soft = 0 } = {}) => {
      const l = new T.PointLight(color, intensity, distance, decay); l.position.set(...pos); l.castShadow = shadow; if (shadow) { l.shadow.mapSize.set(1024, 1024); l.shadow.bias = -0.001; }
      scene.add(l); if (soft > 0) S.soft.push({ light: l, r: soft }); return l;
    };
    S.hemi = (sky = "#ffffff", ground = "#888888", intensity = 0.6) => { const l = new T.HemisphereLight(sky, ground, intensity); scene.add(l); return l; };
    /** image-based light from a small studio built in code: gradient dome + bright softboxes. Gives glossy and glass things real reflections. */
    S.env = ({ top = "#ffffff", bottom = "#9aa3ad", horizon = null, boxes = [{ pos: [0, 6, 4], size: [6, 3], color: "#ffffff", power: 6 }, { pos: [-7, 2, -2], size: [3, 6], color: "#ffffff", power: 3 }, { pos: [7, 3, 2], size: [3, 5], color: "#ffffff", power: 2.5 }], intensity = 1, background = false } = {}) => {
      const es = new T.Scene();
      const dome = new T.Mesh(new T.SphereGeometry(30, 32, 16), new T.ShaderMaterial({ side: T.BackSide, uniforms: { a: { value: new T.Color(top) }, b: { value: new T.Color(bottom) }, h: { value: new T.Color(horizon || top) } }, vertexShader: "varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }", fragmentShader: "uniform vec3 a,b,h; varying vec3 vP; void main(){ float y = normalize(vP).y; vec3 c = y > 0. ? mix(h, a, pow(y, .6)) : mix(h, b, pow(-y, .5)); gl_FragColor = vec4(c, 1.); }" }));
      es.add(dome);
      for (const bx of boxes) { const m = new T.Mesh(new T.PlaneGeometry(bx.size[0], bx.size[1]), new T.MeshBasicMaterial({ color: new T.Color(bx.color).multiplyScalar(bx.power), side: T.DoubleSide })); m.position.set(...bx.pos); m.lookAt(0, 0, 0); es.add(m); }
      const pm = new T.PMREMGenerator(renderer), rt = pm.fromScene(es, 0.03); pm.dispose();
      scene.environment = rt.texture; scene.environmentIntensity = intensity; S._envI = intensity; if (background) scene.background = rt.texture; return rt.texture;
    };
    /** big unlit backdrop sphere with a vertical gradient (screen-filling sky or studio wall) */
    S.gradientBg = (top, bottom, { mid = null, power = 1, radius = 150 } = {}) => {
      const m = new T.Mesh(new T.SphereGeometry(radius, 32, 24), new T.ShaderMaterial({ side: T.BackSide, depthWrite: false, fog: false, uniforms: { a: { value: new T.Color(top) }, b: { value: new T.Color(bottom) }, m: { value: new T.Color(mid || bottom) }, hasMid: { value: mid ? 1 : 0 }, p: { value: power } }, vertexShader: "varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }", fragmentShader: "uniform vec3 a,b,m; uniform float hasMid,p; varying vec3 vP; void main(){ float y = normalize(vP).y * .5 + .5; y = pow(clamp(y,0.,1.), p); vec3 c = hasMid > .5 ? (y > .5 ? mix(m, a, (y-.5)*2.) : mix(b, m, y*2.)) : mix(b, a, y); gl_FragColor = vec4(c, 1.); }" }));
      m.renderOrder = -10; m.frustumCulled = false; scene.add(m); return m;
    };
    /** invisible floor that only catches shadows */
    S.shadowFloor = (opacity = 0.25, size = 60, y = 0) => { const m = new T.Mesh(new T.PlaneGeometry(size, size), new T.ShadowMaterial({ opacity })); m.rotation.x = -Math.PI / 2; m.position.y = y; m.receiveShadow = true; scene.add(m); return m; };

    /* words: printed labels (canvas textures on planes) */
    /** S.label("Text", { h: world height, font: "800 120px Inter", color, bg, border, radius, pad, lit, stroke, strokeW, lineHeight, align, extraW, draw, castShadow, rough, pos, parent }) -> Mesh (plane faces +z; "
" for more lines) */
    S.label = (text, o = {}) => {
      const font = o.font || "800 120px Inter", px = parseFloat(font.match(/(\d+(\.\d+)?)px/)[1]), pad = o.pad ?? px * 0.35, lines = String(text).split("\n");
      const c0 = K.canvas(8, 8).getContext("2d"); c0.font = font; const tw = Math.max(...lines.map((l) => c0.measureText(l).width));
      const lh = px * (o.lineHeight || 1.12), cw = Math.ceil(tw + pad * 2 + (o.extraW || 0)), ch = Math.ceil(lh * lines.length + pad * 2 - (lh - px) + px * 0.18);
      const c = K.canvas(cw, ch), x = c.getContext("2d");
      if (o.bg) { x.fillStyle = o.bg; const r = o.radius ?? ch * 0.22; x.beginPath(); x.roundRect ? x.roundRect(0, 0, cw, ch, r) : x.rect(0, 0, cw, ch); x.fill(); if (o.border) { x.lineWidth = o.borderW || px * 0.06; x.strokeStyle = o.border; x.stroke(); } }
      x.font = font; x.textBaseline = "alphabetic"; x.textAlign = o.align || "center";
      const ax = o.align === "left" ? pad : o.align === "right" ? cw - pad : cw / 2;
      lines.forEach((l, i) => { const y = pad + px * 0.86 + i * lh; if (o.stroke) { x.lineJoin = "round"; x.lineWidth = o.strokeW || px * 0.12; x.strokeStyle = o.stroke; x.strokeText(l, ax, y); } x.fillStyle = o.color || "#111"; x.fillText(l, ax, y); });
      if (o.draw) o.draw(x, cw, ch);
      const tex = K.tex(c, { repeat: [1, 1] }); tex.wrapS = tex.wrapT = T.ClampToEdgeWrapping;
      const h = o.h || 0.5, w = (h * cw) / ch;
      const mat = o.lit === false ? new T.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: !o.noDepth, toneMapped: false }) : new T.MeshStandardMaterial({ map: tex, transparent: true, roughness: o.rough ?? 0.75, metalness: 0, alphaTest: 0.02 });
      if (o.lit === false && o.power) mat.color.setScalar(o.power);
      const m = new T.Mesh(new T.PlaneGeometry(w, h), mat); m.castShadow = !!o.castShadow; m.receiveShadow = o.lit !== false; m.userData.size = [w, h];
      if (o.pos) m.position.set(...o.pos); (o.parent || scene).add(m); return m;
    };
    /** any canvas drawing as a texture on a plane: S.picture(w, h, (ctx, cw, ch) => {...}, { ppu: pixels per unit (default 400), lit }) */
    S.picture = (w, h, draw, o = {}) => {
      const ppu = o.ppu || 400, c = K.canvas(Math.round(w * ppu), Math.round(h * ppu)); draw(c.getContext("2d"), c.width, c.height);
      const tex = K.tex(c); tex.wrapS = tex.wrapT = T.ClampToEdgeWrapping;
      const mat = o.lit === false ? new T.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false }) : new T.MeshStandardMaterial({ map: tex, transparent: !!o.transparent, roughness: o.rough ?? 0.8, alphaTest: o.transparent ? 0.02 : 0 });
      const m = new T.Mesh(new T.PlaneGeometry(w, h), mat); m.receiveShadow = o.lit !== false; m.castShadow = !!o.castShadow; if (o.pos) m.position.set(...o.pos); (o.parent || scene).add(m); return m;
    };

    /* build the style */
    const update = (await style.build(S)) || (() => {});
    S.update = update;
    // three r160 has no scene.environmentIntensity: apply it per material (only where the style left the default)
    if (S._envI != null && S._envI !== 1) scene.traverse((o) => { const ms = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : []; ms.forEach((m) => { if ("envMapIntensity" in m && m.envMapIntensity === 1 && !m.userData.envFixed) { m.envMapIntensity = S._envI; m.userData.envFixed = 1; } }); });

    /* render one frame */
    const tmIdx = { aces: 0, neutral: 1, none: 2 }[G.tonemap] ?? 0;
    const _right = new T.Vector3(), _up = new T.Vector3(), _fwd = new T.Vector3(), _base = [];
    let frameNo = 0;
    S.seek = (t, samples) => {
      const N = Math.max(1, Math.round(samples ?? opts.samples ?? style.samples ?? 16));
      const shutter = (style.shutter ?? 0.5) / S.fps;
      renderer.setRenderTarget(rtA); renderer.setClearColor(0x000000, 1); renderer.clear();
      for (let i = 0; i < N; i++) {
        const ts = N > 1 ? Math.max(0, t + shutter * ((i + 0.5) / N - 0.5)) : t; S.time = ts; // never sample before 0
        update(ts);
        // camera with lens (depth of field) + sub-pixel jitter
        camera.fov = camState.fov; camera.aspect = W / H; camera.position.copy(camState.pos); camera.up.set(0, 1, 0); camera.lookAt(camState.target);
        if (camState.roll) camera.rotateZ(camState.roll);
        camera.updateProjectionMatrix(); camera.updateMatrixWorld();
        const focus = camState.focus ?? camState.pos.distanceTo(camState.target);
        let lx = 0, ly = 0;
        if (N > 1 && camState.aperture > 0) { const a = K.halton(i + 1, 2) * Math.PI * 2, r = Math.sqrt(K.halton(i + 1, 3)) * camState.aperture; lx = Math.cos(a) * r; ly = Math.sin(a) * r; }
        _right.setFromMatrixColumn(camera.matrixWorld, 0); _up.setFromMatrixColumn(camera.matrixWorld, 1);
        camera.position.addScaledVector(_right, lx).addScaledVector(_up, ly); camera.updateMatrixWorld();
        const P = camera.projectionMatrix.elements, jx = N > 1 ? (K.halton(i + 1, 5) - 0.5) * 2 / W : 0, jy = N > 1 ? (K.halton(i + 1, 7) - 0.5) * 2 / H : 0;
        P[8] += -(P[0] * lx) / focus + jx + camState.shift[0]; P[9] += -(P[5] * ly) / focus + jy + camState.shift[1];
        camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
        // soft (area) lights
        _base.length = 0;
        S.soft.forEach((s, j) => { _base.push(s.light.position.clone()); if (N > 1) { const a = K.halton(i + 1 + j * 7, 2) * Math.PI * 2, r = Math.sqrt(K.halton(i + 1 + j * 7, 3)) * s.r; _fwd.subVectors(s.light.target ? s.light.target.position : new T.Vector3(), s.light.position).normalize(); _right.crossVectors(_fwd, new T.Vector3(0, 1, 0.0001)).normalize(); _up.crossVectors(_right, _fwd).normalize(); s.light.position.addScaledVector(_right, Math.cos(a) * r).addScaledVector(_up, Math.sin(a) * r); } });
        renderer.setRenderTarget(rtS); renderer.setClearColor(style.clear || 0x000000, 1); renderer.clear(); renderer.render(scene, camera);
        S.soft.forEach((s, j) => s.light.position.copy(_base[j]));
        accMat.uniforms.w.value = 1 / N; pass(accMat, rtA, false);
      }
      // bloom
      if (G.bloom > 0) {
        brightMat.uniforms.thr.value = G.bloomThreshold; pass(brightMat, rtB1);
        for (let k = 0; k < 3; k++) { const s = 1 + k; blurMat.uniforms.tex.value = rtB1.texture; blurMat.uniforms.dir.value.set(s / bw, 0); pass(blurMat, rtB2); blurMat.uniforms.tex.value = rtB2.texture; blurMat.uniforms.dir.value.set(0, s / bh); pass(blurMat, rtB1); }
      } else { renderer.setRenderTarget(rtB1); renderer.setClearColor(0, 1); renderer.clear(); }
      const u = finalMat.uniforms;
      u.exposure.value = G.exposure; u.bloom.value = G.bloom; u.sat.value = G.saturation; u.contrast.value = G.contrast; u.vig.value = G.vignette; u.grain.value = G.grain; u.tm.value = tmIdx; u.warm.value = G.warm;
      u.lift.value.set(...G.lift); u.gain.value.set(...G.gain); u.frame.value = Math.round(t * S.fps) + frameNo * 0;
      pass(finalMat, null);
    };
    return S;
  };

  /** load fonts: ["Inter:800", "Fraunces:700italic"]. Uses Google Fonts unless a matching @font-face already exists. */
  K.loadFonts = async (specs) => {
    const fam = specs.map((s) => { const [f, w = "400"] = s.split(":"); return { f, w: w.replace("italic", ""), it: /italic/.test(w) }; });
    const have = new Set([...document.fonts].map((f) => f.family.replace(/["']/g, "")));
    const need = fam.filter((x) => !have.has(x.f));
    if (need.length && !document.querySelector("link[data-stage-fonts]")) {
      const q = [...new Set(need.map((x) => x.f))].map((f) => { const ws = need.filter((x) => x.f === f); const hasIt = ws.some((x) => x.it); const list = [...new Set(ws.map((x) => (hasIt ? `${x.it ? 1 : 0},${x.w}` : x.w)))].sort(); return `family=${f.replace(/ /g, "+")}:${hasIt ? "ital," : ""}wght@${list.join(";")}`; }).join("&");
      const l = document.createElement("link"); l.rel = "stylesheet"; l.dataset.stageFonts = 1; l.href = `https://fonts.googleapis.com/css2?${q}&display=block`; document.head.appendChild(l);
      await new Promise((r) => { l.onload = r; l.onerror = r; setTimeout(r, 6000); });
    }
    await Promise.all(fam.map((x) => document.fonts.load(`${x.it ? "italic " : ""}${x.w} 64px "${x.f}"`).catch(() => {})));
  };
})();
