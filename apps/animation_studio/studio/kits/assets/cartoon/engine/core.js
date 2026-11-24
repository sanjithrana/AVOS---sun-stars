/* Cartoon Shorts engine: renderer, toon materials, lights, cards, camera, ink + lens + grade passes. Free from Anylancer.com. */
(function () {
const CS = window.CS = window.CS || {};
const { clamp, lerp, ease } = CS;
let W, H, renderer, scene, camera, sun, hemi, amb, sky, rtColor, rtNormal, post, postScene, postCam;
const cards = [], sprites = [], sets = {};
CS.cards = cards;

// ---------- start ----------
CS.start = function (opt) {
  W = opt.width; H = opt.height;
  renderer = new THREE.WebGLRenderer({ canvas: opt.canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(1); renderer.setSize(W, H, false);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.LinearSRGBColorSpace;   // the grade pass converts to sRGB itself
  renderer.toneMapping = THREE.NoToneMapping;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(40, W / H, 0.1, 1200);
  sun = new THREE.DirectionalLight(0xffffff, 2.6); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.03; sun.shadow.radius = 3;
  scene.add(sun, sun.target);
  hemi = new THREE.HemisphereLight(0xbfe3ff, 0x8a7a5a, 1.1); scene.add(hemi);
  amb = new THREE.AmbientLight(0xffffff, 0.25); scene.add(amb);
  scene.fog = new THREE.Fog(0xcfe6f5, 60, 420);
  // sky dome
  sky = new THREE.Mesh(new THREE.SphereGeometry(950, 32, 16), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { top: { value: new THREE.Color() }, hor: { value: new THREE.Color() }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, glow: { value: new THREE.Color() }, stars: { value: 0 } },
    vertexShader: "varying vec3 vD; void main(){ vD = normalize(position); vec4 p = projectionMatrix*modelViewMatrix*vec4(position,1.); gl_Position = p.xyww; }",
    fragmentShader: `uniform vec3 top, hor, glow, sunDir; uniform float stars; varying vec3 vD;
      float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,37.719)))*43758.5453); }
      void main(){ float y = clamp(vD.y, 0., 1.); vec3 c = mix(hor, top, pow(y, .55));
        float s = max(dot(normalize(vD), normalize(sunDir)), 0.); c += glow * (pow(s, 24.) * .9 + pow(s, 4.) * .25);
        if (stars > 0.) { vec3 q = floor(vD * 260.); float st = step(.9975, h(q)) * smoothstep(.05, .35, vD.y); c += st * stars; }
        gl_FragColor = vec4(c, 1.); }`
  }));
  sky.userData.ink = "none"; sky.renderOrder = -10; sky.frustumCulled = false; scene.add(sky);
  // render targets
  rtColor = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 });
  rtNormal = new THREE.WebGLRenderTarget(W, H, { type: THREE.UnsignedByteType });
  rtNormal.depthTexture = new THREE.DepthTexture(W, H); rtNormal.depthTexture.type = THREE.UnsignedIntType;
  post = new THREE.ShaderMaterial({
    uniforms: {
      tColor: { value: rtColor.texture }, tNormal: { value: rtNormal.texture }, tDepth: { value: rtNormal.depthTexture },
      res: { value: new THREE.Vector2(W, H) }, near: { value: .1 }, far: { value: 1200 },
      inkW: { value: 2.8 * W / 1080 }, inkA: { value: 1 }, inkCol: { value: new THREE.Color(0x1d1420) }, inkFar: { value: 340 },
      focus: { value: 6 }, dofK: { value: 0 }, maxBlur: { value: 14 * W / 1080 },
      sat: { value: 1.08 }, gain: { value: new THREE.Vector3(1, 1, 1) }, lift: { value: new THREE.Vector3(0, 0, 0) }, vig: { value: .22 },
      dbg: { value: 0 }, flash: { value: 0 }, flashCol: { value: new THREE.Color(1, 1, 1) }, grain: { value: .018 }, seed: { value: 0 },
    },
    vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }",
    fragmentShader: `precision highp float;
      uniform sampler2D tColor, tNormal, tDepth; uniform vec2 res; uniform float dbg, near, far, inkW, inkA, inkFar, focus, dofK, maxBlur, sat, vig, flash, grain, seed;
      uniform vec3 gain, lift, inkCol, flashCol; varying vec2 vUv;
      float lin(float d){ float z = d * 2. - 1.; return 2. * near * far / (far + near - z * (far - near)); }
      float D(vec2 uv){ return lin(texture2D(tDepth, uv).x); }
      vec3 N(vec2 uv){ return texture2D(tNormal, uv).xyz * 2. - 1.; }
      float coc(float d){ return clamp(abs(d - focus) / max(d, .001) * dofK, 0., maxBlur); }
      void main(){
        vec2 px = 1. / res; float dc = D(vUv); vec3 nc = N(vUv);
        vec3 col = texture2D(tColor, vUv).rgb; float cc = coc(dc);
        if (cc > .6) { vec3 acc = col; float ws = 1.;
          for (int i = 0; i < 40; i++) { float a = float(i) * 2.39996; float r = sqrt((float(i) + .5) / 40.) * cc;
            vec2 o = vec2(cos(a), sin(a)) * r * px; float ds = D(vUv + o);
            float w = ds >= dc - .05 ? 1. : smoothstep(r - 1., r + 1., coc(ds));
            acc += texture2D(tColor, vUv + o).rgb * w; ws += w; }
          col = acc / ws; }
        float ink = 0.;
        for (int i = 0; i < 8; i++) { float a = float(i) * .785398; vec2 o = vec2(cos(a), sin(a)) * inkW * px;
          float dn = D(vUv + o); vec3 nn = N(vUv + o); float dd = dn - dc;
          if (dd > max(.03 * dc, .025)) ink = 1.;
          else if (abs(dd) < .05 * dc + .04) ink = max(ink, smoothstep(.22, .42, 1. - dot(nc, nn)) * .8); }
        ink *= inkA * (1. - smoothstep(inkFar * .25, inkFar, dc)) * (1. - smoothstep(4., 14., cc) * .5);
        if (dbg > .5) { gl_FragColor = vec4(dbg > 1.5 ? N(vUv) * .5 + .5 : vec3(1. - ink), 1.); return; }
        col = mix(col, inkCol, ink);
        float l = dot(col, vec3(.2126, .7152, .0722)); col = mix(vec3(l), col, sat);
        col = col * gain + lift * (1. - col);
        vec2 q = vUv - .5; q.x *= res.x / res.y; col *= 1. - vig * smoothstep(.3, .9, length(q) * 1.25);
        col = mix(col, flashCol, flash); col = clamp(col, 0., 1.);
        col = mix(col * 12.92, 1.055 * pow(col, vec3(1. / 2.4)) - .055, step(.0031308, col));
        float hh = fract(sin(dot(vUv * res + seed, vec2(12.9898, 78.233))) * 43758.5453); col += (hh - .5) * grain;
        gl_FragColor = vec4(col, 1.); }`,
    depthTest: false, depthWrite: false,
  });
  postScene = new THREE.Scene(); postCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const tri = new THREE.BufferGeometry(); tri.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3)); tri.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
  const q = new THREE.Mesh(tri, post); q.frustumCulled = false; postScene.add(q);
  CS.scene = scene; CS.camera = camera; CS.renderer = renderer; CS.sun = sun; CS.post = post.uniforms; CS.W = W; CS.H = H;
};

// ---------- materials ----------
let grad;
function gradient() {
  if (grad) return grad;
  const d = new Uint8Array([105, 105, 105, 255, 185, 185, 185, 255, 255, 255, 255, 255]);
  grad = new THREE.DataTexture(d, 3, 1, THREE.RGBAFormat); grad.minFilter = grad.magFilter = THREE.NearestFilter; grad.needsUpdate = true; return grad;
}
// mat("#c44") or mat("#fff", {tex:"planks", texOpt:{...}, repeat:[2,2], emissive, side, flat})
CS.mat = function (color, o = {}) {
  const m = new THREE.MeshToonMaterial({ color: new THREE.Color(color), gradientMap: gradient() });
  if (o.tex) { m.map = typeof o.tex === "string" ? CS.paint.tex(o.tex, o.texOpt || {}) : o.tex; if (o.repeat) { m.map = m.map.clone(); m.map.repeat.set(o.repeat[0], o.repeat[1]); m.map.needsUpdate = true; } }
  if (o.emissive) { m.emissive = new THREE.Color(o.emissive); m.emissiveIntensity = o.emissiveI ?? 1; }
  if (o.side) m.side = o.side;
  if (o.transparent) { m.transparent = true; m.opacity = o.opacity ?? 1; }
  return m;
};
CS.basic = (color, o = {}) => new THREE.MeshBasicMaterial(Object.assign({ color: new THREE.Color(color) }, o));

// ---------- scene graph helpers ----------
// add(mesh, parent?, {ink:'world'|'card'|'none', shadow:true})
CS.add = function (obj, parent, o = {}) {
  (parent || scene).add(obj);
  obj.traverse(m => { if (m.isMesh) { if (m.userData.ink == null) m.userData.ink = o.ink || "world"; if (o.shadow !== false) { m.castShadow = m.userData.ink === "world"; m.receiveShadow = true; } } });
  return obj;
};
// sets: build each location in its own set and show one at a time
CS.set = function (name) { if (!sets[name]) { const g = new THREE.Group(); g.name = name; scene.add(g); sets[name] = g; } return sets[name]; };
CS.showSet = function (name) { for (const k in sets) sets[k].visible = (k === name) || (Array.isArray(name) && name.includes(k)); };
CS.sets = sets;

// ---------- lights ----------
CS.LIGHTS = {
  day:    { az: 35, el: 52, sun: "#fff4e0", sunI: 2.7, sky: "#bfe0ff", ground: "#9a8a62", hemiI: 1.15, top: "#3f8fe0", hor: "#cfe9fb", glow: "#fff2cc", fog: [70, 420], card: "#ffffff", sat: 1.1, gain: [1, 1, 1], lift: [0, 0, 0], vig: .2, stars: 0 },
  golden: { az: 75, el: 16, sun: "#ffc27a", sunI: 2.9, sky: "#ffd2a8", ground: "#8a5a3a", hemiI: 1.0, top: "#4a76c9", hor: "#ffc690", glow: "#ffb060", fog: [60, 380], card: "#ffe2c4", sat: 1.15, gain: [1.04, .98, .9], lift: [.02, .01, 0], vig: .3, stars: 0 },
  dusk:   { az: 95, el: 6, sun: "#ff9a6a", sunI: 2.2, sky: "#c9a0c8", ground: "#5a4060", hemiI: .95, top: "#2c3a7a", hor: "#ff9d7a", glow: "#ff7a4a", fog: [50, 340], card: "#f2c7c0", sat: 1.1, gain: [1, .93, .95], lift: [.03, .01, .04], vig: .34, stars: .2 },
  night:  { az: -40, el: 40, sun: "#9fb8ff", sunI: 1.3, sky: "#5f7fc8", ground: "#2a3050", hemiI: .95, top: "#0d1838", hor: "#3a5a9a", glow: "#a8c4ff", fog: [40, 300], card: "#a9b8e6", sat: 1.0, gain: [.92, .96, 1.08], lift: [0, .01, .05], vig: .4, stars: .9 },
  indoor: { az: 20, el: 60, sun: "#ffe6c0", sunI: 1.9, sky: "#fff0dc", ground: "#7a5a40", hemiI: 1.25, top: "#e8d8c0", hor: "#f2e6d4", glow: "#ffffff", fog: [40, 200], card: "#fff3e4", sat: 1.08, gain: [1.02, 1, .96], lift: [.01, .005, 0], vig: .28, stars: 0 },
  dawn:   { az: 100, el: 10, sun: "#ffd0a0", sunI: 2.3, sky: "#d8c8e8", ground: "#6a5a6a", hemiI: 1.0, top: "#5a7ac0", hor: "#ffd6b0", glow: "#ffc890", fog: [50, 360], card: "#f8dccc", sat: 1.05, gain: [1, .97, .96], lift: [.02, .015, .03], vig: .3, stars: 0 },
};
const C1 = new THREE.Color(), C2 = new THREE.Color();
function lerpLight(a, b, k) {
  if (!b || k <= 0) return a; if (k >= 1) return b;
  const o = {};
  for (const key in a) {
    const x = a[key], y = b[key];
    if (typeof x === "number") o[key] = lerp(x, y, k);
    else if (Array.isArray(x)) o[key] = x.map((v, i) => lerp(v, y[i], k));
    else { C1.set(x); C2.set(y); o[key] = "#" + C1.lerp(C2, k).getHexString(); }
  }
  return o;
}
let curLight = CS.LIGHTS.day, cardTint = new THREE.Color(1, 1, 1);
// light("day") or light("day", "golden", 0.4) to blend; extra = {sunI, ...} overrides
CS.light = function (a, b, k = 0, extra) {
  const A = typeof a === "string" ? CS.LIGHTS[a] : a, B = typeof b === "string" ? CS.LIGHTS[b] : b;
  const L = Object.assign({}, lerpLight(A, B, k), extra || {}); curLight = L;
  const az = L.az * Math.PI / 180, el = L.el * Math.PI / 180;
  const dir = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), Math.cos(az) * Math.cos(el));
  sun.color.set(L.sun); sun.intensity = L.sunI; sun.userData.dir = dir;
  hemi.color.set(L.sky); hemi.groundColor.set(L.ground); hemi.intensity = L.hemiI;
  sky.material.uniforms.top.value.set(L.top); sky.material.uniforms.hor.value.set(L.hor); sky.material.uniforms.glow.value.set(L.glow);
  sky.material.uniforms.sunDir.value.copy(dir); sky.material.uniforms.stars.value = L.stars;
  scene.fog.color.set(L.hor); scene.fog.near = L.fog[0]; scene.fog.far = L.fog[1];
  cardTint.set(L.card);
  post.uniforms.sat.value = L.sat; post.uniforms.gain.value.set(...L.gain); post.uniforms.lift.value.set(...L.lift); post.uniforms.vig.value = L.vig;
  return L;
};
// shadow box follows the action: shadowAt(x, z, size)
CS.shadowAt = function (x, z, size = 24, y = 0) {
  const d = sun.userData.dir || new THREE.Vector3(0, 1, 0);
  sun.target.position.set(x, y, z); sun.position.set(x + d.x * 80, y + d.y * 80, z + d.z * 80);
  const c = sun.shadow.camera; c.left = -size; c.right = size; c.top = size; c.bottom = -size; c.near = 1; c.far = 220; c.updateProjectionMatrix();
};

// ---------- cards: 2D drawings standing in the 3D world ----------
const texCache = new Map(); let texBytes = 0; const TEX_BUDGET = 700e6;
function cachedTex(key, cw, ch, scale, draw, state) {
  let e = texCache.get(key);
  if (e) { texCache.delete(key); texCache.set(key, e); return e.tex; }
  const c = document.createElement("canvas"); c.width = Math.round(cw * scale); c.height = Math.round(ch * scale);
  const g = c.getContext("2d"); g.setTransform(scale, 0, 0, scale, 0, 0); g.lineJoin = g.lineCap = "round";
  draw(g, state);
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  e = { tex, bytes: c.width * c.height * 4 }; texCache.set(key, e); texBytes += e.bytes;
  while (texBytes > TEX_BUDGET && texCache.size > 8) { const [k, old] = texCache.entries().next().value; old.tex.dispose(); texBytes -= old.bytes; texCache.delete(k); }
  return tex;
}
const qv = v => typeof v === "number" ? Math.round(v * 100) / 100 : v;
const cardNVS = "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }";
let blobTex;
function blobTexture() {
  if (blobTex) return blobTex;
  blobTex = CS.paint.canvasTex(128, 128, (g) => { const r = g.createRadialGradient(64, 64, 4, 64, 64, 62); r.addColorStop(0, "rgba(30,20,30,.55)"); r.addColorStop(1, "rgba(30,20,30,0)"); g.fillStyle = r; g.fillRect(0, 0, 128, 128); });
  return blobTex;
}
/* card({ draw(g, state), cw:600, ch:1000, h:2.0 (metres for the full canvas height), foot:0.975, scale:2, name, blob:true })
   -> { group, pivot, set(state), at(x,y,z), flip(bool), visible } ; draw in design units (cw x ch) */
CS.card = function (o) {
  const cw = o.cw || 600, ch = o.ch || 1000, h = o.h || 2, w = h * cw / ch, foot = o.foot ?? .975, scale = o.scale ?? 2;
  const geo = new THREE.PlaneGeometry(w, h); geo.translate(0, h / 2 - h * (1 - foot), 0);
  const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, alphaTest: .5, side: THREE.DoubleSide, fog: true }); mat.alphaToCoverage = true;
  const mesh = new THREE.Mesh(geo, mat); mesh.userData.ink = "card"; mesh.castShadow = o.castShadow !== false; mesh.receiveShadow = false;
  mesh.customDepthMaterial = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, alphaTest: .5, side: THREE.DoubleSide });
  mesh.userData.nMat = new THREE.ShaderMaterial({ uniforms: { map: { value: null } }, vertexShader: cardNVS, side: THREE.DoubleSide,
    fragmentShader: "uniform sampler2D map; varying vec2 vUv; void main(){ if (texture2D(map, vUv).a < .5) discard; gl_FragColor = vec4(.5, .5, 1., 1.); }" });
  const group = new THREE.Group(), pivot = new THREE.Group(); group.add(pivot); pivot.add(mesh);
  (o.parent || scene).add(group);
  let blob = null;
  if (o.blob !== false) { blob = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: blobTexture(), transparent: true, depthWrite: false, fog: true })); blob.rotation.x = -Math.PI / 2; blob.userData.ink = "none"; blob.renderOrder = 1; (o.parent || scene).add(blob); }
  const c = { group, pivot, mesh, blob, cw, ch, h, w, name: o.name || "card", yawFixed: null, blobW: o.blobW || w * .55, ground: 0,
    set(state) {
      const s = {}; for (const k in state) s[k] = qv(state[k]);
      const key = (o.design || o.name || "card") + "|" + scale + "|" + JSON.stringify(s);
      if (key !== c.key) { c.key = key; const tex = cachedTex(key, cw, ch, scale, o.draw, s); mat.map = tex; mat.needsUpdate = true; mesh.customDepthMaterial.map = tex; mesh.customDepthMaterial.needsUpdate = true; mesh.userData.nMat.uniforms.map.value = tex; }
      return c;
    },
    at(x, y, z) { group.position.set(x, y, z); c.ground = y; return c; },
    flip(f) { pivot.scale.x = Math.abs(pivot.scale.x) * (f ? -1 : 1); return c; },
    show(v) { group.visible = v; if (blob) blob.visible = v; return c; },
  };
  cards.push(c); return c;
};
function updateCards() {
  const cp = camera.position;
  for (const c of cards) {
    let vis = c.group.visible, p = c.group.parent; while (vis && p) { vis = p.visible; p = p.parent; }
    c.mesh.material.color.copy(cardTint);
    if (c.yawFixed != null) c.group.rotation.y = c.yawFixed;
    else { const wp = c.group.getWorldPosition(new THREE.Vector3()); c.group.rotation.y = Math.atan2(cp.x - wp.x, cp.z - wp.z); }
    if (c.blob) { c.blob.visible = vis; const wp = c.group.position; c.blob.position.set(wp.x, c.ground + .02, wp.z); const lift = clamp((wp.y - c.ground) / 2, 0, .8); const s = c.blobW * (1 - lift * .5); c.blob.scale.set(s, s * .55, 1); c.blob.material.opacity = 1 - lift; }
  }
}

// ---------- sprites: small effects that always face the camera ----------
// sprite(texture, size) -> THREE.Sprite (tinted by the light; no ink)
CS.sprite = function (tex, size = .5, parent) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, alphaTest: .35, fog: true, depthWrite: true })); s.scale.set(size, size, 1);
  s.userData.ink = "none"; s.userData.tint = true; (parent || scene).add(s); sprites.push(s); return s;
};

// ---------- camera ----------
/* camPath([{t, p:[x,y,z], l:[x,y,z], fov, roll, e:'smooth'|'out'|'in'|'lin'|'back'|'cut'}...]) -> fn(t) -> {p, l, fov, roll}
   e = how we arrive at this key from the previous one; 'cut' = jump at t. */
CS.camPath = function (keys) {
  return function (t) {
    let i = 0; while (i < keys.length - 1 && keys[i + 1].t <= t) i++;
    const a = keys[i], b = keys[i + 1];
    let k = 0;
    if (b && b.e !== "cut") k = (ease[b.e || "smooth"] || ease.smooth)(CS.seg(t, a.t, b.t));
    const B = b && b.e !== "cut" ? b : a;
    return { p: a.p.map((v, j) => lerp(v, B.p[j], k)), l: a.l.map((v, j) => lerp(v, B.l[j], k)), fov: lerp(a.fov || 40, B.fov || 40, k), roll: lerp(a.roll || 0, B.roll || 0, k), key: i };
  };
};
// shake(t, t0, dur, amp) -> [dx, dy] decaying wobble after an impact
CS.shake = function (t, t0, dur = .25, amp = .06) { if (t < t0 || t > t0 + dur) return [0, 0]; const k = (t - t0) / dur, d = (1 - k) * amp; return [Math.sin(k * 60) * d, Math.cos(k * 47) * d * .7]; };
// cam({p, l, fov, roll}, t, {creep, shake:[dx,dy]}) places the camera; creep adds a slow living drift
CS.cam = function (c, t = 0, o = {}) {
  const cr = o.creep ?? .025, sh = o.shake || [0, 0];
  camera.position.set(c.p[0] + CS.noise1(t * .35, 3) * cr + sh[0], c.p[1] + CS.noise1(t * .3, 5) * cr + sh[1], c.p[2] + CS.noise1(t * .33, 7) * cr);
  camera.fov = c.fov || 40; camera.updateProjectionMatrix();
  camera.up.set(0, 1, 0); camera.lookAt(c.l[0], c.l[1], c.l[2]);
  if (c.roll) camera.rotateZ(c.roll * Math.PI / 180);
};
// lens({focus: metres from camera (or a THREE.Vector3/array point), blur: 0..1, ink, flash, flashColor})
CS.lens = function (o) {
  let f = o.focus ?? 6;
  if (Array.isArray(f)) f = camera.position.distanceTo(new THREE.Vector3(...f));
  else if (f && f.isVector3) f = camera.position.distanceTo(f);
  post.uniforms.focus.value = f;
  post.uniforms.dofK.value = (o.blur ?? 0) * 34 * W / 1080;
  if (o.ink != null) post.uniforms.inkA.value = o.ink;
  post.uniforms.flash.value = o.flash || 0;
  post.uniforms.flashCol.value.set(o.flashColor || "#ffffff");
};

// ---------- render ----------
const saved = new Map();
CS.renderFrame = function (frameNo = 0) {
  updateCards();
  for (const s of sprites) s.material.color.copy(cardTint);
  sky.position.copy(camera.position);
  post.uniforms.near.value = camera.near; post.uniforms.far.value = camera.far; post.uniforms.seed.value = frameNo % 97;
  // 1) colour
  renderer.shadowMap.autoUpdate = true; renderer.setRenderTarget(rtColor); renderer.setClearColor(0x000000, 1); renderer.clear(); renderer.render(scene, camera);
  // 2) normals + depth for ink and lens blur
  renderer.shadowMap.autoUpdate = false;
  const fog = scene.fog; scene.fog = null;
  scene.traverse(m => {
    if (!m.isMesh && !m.isSprite) return;
    const ink = m.userData.ink || "world";
    saved.set(m, [m.material, m.visible]);
    if (ink === "none" || m.isSprite) m.visible = false;
    else if (ink === "card") m.material = m.userData.nMat;
    else m.material = m.material.side === THREE.DoubleSide ? NMAT2 : NMAT;
  });
  renderer.setRenderTarget(rtNormal); renderer.setClearColor(new THREE.Color(.5, .5, 1), 1); renderer.clear(); renderer.render(scene, camera);
  for (const [m, [mat, v]] of saved) { m.material = mat; m.visible = v; } saved.clear(); scene.fog = fog;
  // 3) ink + lens + grade to the screen
  renderer.setRenderTarget(null); renderer.render(postScene, postCam);
};
const NMAT = new THREE.MeshNormalMaterial(), NMAT2 = new THREE.MeshNormalMaterial({ side: THREE.DoubleSide });
})();
