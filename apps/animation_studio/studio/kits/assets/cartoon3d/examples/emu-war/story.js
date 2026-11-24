/* The Great Emu War: demo short for the Cartoon Shorts skill.
   SHOT PLAN (seconds come from the words, so a new take re-times itself)
   1  0.0  "In 1932, Australia went to war… with birds."  MCU: the major salutes; an emu leans in on "birds" (rack focus).
   2  "Twenty"   Wide crane down: golden wheat, ~26 emus pecking, the farmer shakes his fist; stomps + dust on "trampling".
   3  "So"       The army truck rolls in; the major, two soldiers and two machine guns pop up word by word.
   4  "Easy"     Close-up: smug thumbs-up, sparkle.
   5  "The emus split up"  Over-the-gun wide: the emus scatter, puffs miss. "Ran" whip to one emu at full speed; "Dodged" it hops aside, smug.
   6  "The major said"  MCU: an emu in a tiny helmet, pings bounce off it.
   7  "After"    Flash, sunset: the truck drives home, everyone sad. Sad trombone on "home".
   8  "The emus" Golden: emus feasting; one wears the major's hat on an ammo crate; push in, music stops on "Australia".
   9  "to birds" Sting, roll, smug squawk on the last word. */
window.SHORT = {
  title: "The Great Emu War", slug: "the-great-emu-war",
  script: `In nineteen thirty-two, Australia went to war… with birds.
Twenty thousand emus were trampling wheat farms in the west.
So the army sent a major, two soldiers… and two machine guns.
Easy, right?
The emus split up. Ran at thirty miles an hour. Dodged everything.
The major said they could take bullets like tanks.
After a month, the army packed up… and went home.
The emus kept the wheat.
Australia lost a war… to birds.`,
  tail: .9,

  setup(T) {
    const S = this, Wd = CS.world, R = CS.rand;
    CS.LIGHTS.outback = Object.assign({}, CS.LIGHTS.day, { az: 30, el: 48, sun: "#fff0d2", sunI: 2.8, top: "#3a86d8", hor: "#f4e4c8", ground: "#b0703a", sky: "#cfe6ff", fog: [90, 480], sat: 1.12 });
    CS.LIGHTS.sunset = Object.assign({}, CS.LIGHTS.golden, { az: -78, el: 9, sunI: 2.6, hor: "#ffb47a", top: "#5470c0", glow: "#ffa050", card: "#ffd9b8", gain: [1.06, .97, .88] });
    // ---------- world ----------
    Wd.ground([900, 900], Wd.painted("sand", "#d9773f"), null, { tile: 7 });
    Wd.ground([80, 54], Wd.painted("wheat", "#e8b93c"), null, { tile: 5, y: .02, z: -23 });
    Wd.ground([200, 6], Wd.painted("dirt", "#c98a55"), null, { tile: 4, y: .03, z: 8 });
    Wd.tufts(2600, [-40, -50, 40, 3.4], { color: "#e4b23c", h: .95, r: .16 }, 11, (x, z) => Math.abs(x) < 2.2 && z > -5 && z < -1.5);
    Wd.tufts(500, [-90, 12, 90, 40], { color: "#b3a35a", h: .5, r: .2 }, 12);
    Wd.house({ w: 6, d: 4.5, h: 3, wall: "#f2e6cf", roof: "#a9434a", rot: .2, windows: 2 }, [-9, 0, -15]);
    Wd.box(6.5, .2, 2, CS.mat("#9a6a40"), [-8.5, 0, -12.4], null, { rot: [0, .2, 0] });
    Wd.fence([-18, -10], [-12, -8]);
    S.mill = Wd.windmill([15, 0, -22]);
    Wd.cyl(1.6, 1.6, 2, CS.mat("#8fa0a8", { tex: "metal", texOpt: { color: "#8fa0a8" } }), [17.5, 0, -22]);
    Wd.scatter(26, [-90, -110, 90, -56], 21, (i, x, z) => Wd.tree("gum", 7 + R(i) * 5, [x, 0, z], null, i));
    Wd.scatter(14, [-90, 16, 90, 50], 22, (i, x, z) => Wd.tree("gum", 6 + R(i * 3) * 4, [x, 0, z], null, i + 50));
    for (let i = 0; i < 7; i++) Wd.hill(60 + i * 9, i % 2 ? "#b98a4a" : "#a99c58", [-260 + i * 90, 0, -230 - (i % 3) * 30], null, { squash: .32 });
    for (const [x, z, r, h] of [[-160, -320, 34, 26], [120, -340, 46, 30], [260, -300, 30, 22]]) Wd.cyl(r * .8, r, h, CS.mat("#c0603a"), [x, 0, z], null, { seg: 9 });
    Wd.clouds(14, 280, 70, 5, null, { cz: -120, size: 46 });
    Wd.crate(.75, [0.2, 0, -3.1]); S.crateTop = .6;
    // the army truck + two machine guns
    S.truck = Wd.truck({ color: "#86935e" });
    S.guns = [Wd.gun(), Wd.gun()];
    S.guns.forEach((g, i) => { S.truck.add(g); g.position.set(i ? -2.25 : -.9, S.truck.bed, -.55); g.rotation.y = Math.PI / 2; });
    // ---------- cast ----------
    const khaki = "#8a8152", slouch = { type: "slouch", color: "#9a8558" };
    S.major = CS.person({ skin: "#f6c9a0", hair: { style: "short", color: "#6a4a2a" }, hat: slouch, top: { type: "uniform", color: khaki }, pants: "#6f6a44", mustache: "handlebar", medal: true });
    S.sold = [CS.person({ skin: "#f2c39a", hair: { style: "short", color: "#3a2a20" }, hat: slouch, top: { type: "uniform", color: khaki }, pants: "#6f6a44" }),
              CS.person({ skin: "#e7b58c", hair: { style: "short", color: "#a8642e" }, hat: slouch, top: { type: "uniform", color: khaki }, pants: "#6f6a44", nose: "big" })];
    S.farmer = CS.person({ skin: "#eab58e", hair: { style: "balding", color: "#7a5a3a" }, hat: { type: "straw", color: "#e8c878" }, top: { type: "overalls", color: "#d9634a", bib: "#3d6db0" }, beard: true, beardColor: "#8a6a4a" });
    S.emus = []; const used = [];
    for (let i = 0; i < 26; i++) {
      let x, z, k = 0; do { x = -12 + R(i * 7 + k) * 24; z = -15 + R(i * 7 + k + 100) * 13; k++; } while (used.some(p => Math.hypot(p[0] - x, p[1] - z) < 1.6) && k < 50);
      used.push([x, z]); S.emus.push({ c: CS.emu({ scale: .8 }), x, z, seed: i + 1, flip: R(i * 9) > .5 });
    }
    S.hook = CS.emu(); S.hero = CS.emu(); S.helm = CS.emu(); S.hat = CS.emu();
    S.feast = [0, 1, 2, 3, 4].map(i => ({ c: CS.emu(), x: [-2.2, 2.0, -1.0, 3.2, -3.4][i], z: [-5.2, -4.8, -7.5, -7.8, -7.0][i], seed: 40 + i }));
    // ---------- effects ----------
    S.fx = [];
    const fire1 = T.w("split"), runT = T.w("ran"), dodge = T.w("dodged");
    S.heroX = t => 1 + Math.max(0, t - runT + .05) * 8.4;   // the hero emu's run
    for (let i = 0; i < 10; i++) S.fx.push(CS.burst("dust", [-8 + R(i * 3) * 16, .3, -13 + R(i * 3 + 1) * 9], fire1 + .3 + i * .13, { n: 6, size: .9, spread: .8, up: .9, gravity: 1, seed: i * 11, grow: true, dur: .7 }));
    for (let i = 0; i < 5; i++) { const tt = runT + .25 + i * .32; S.fx.push(CS.burst("dust", [S.heroX(tt) - 1.4, .3, -1.6], tt, { n: 6, size: .8, spread: .7, up: .8, gravity: 1, seed: 90 + i, grow: true, dur: .65 })); }
    S.fx.push(CS.burst("dust", [S.heroX(dodge), .3, -1.5], dodge, { n: 8, size: 1, spread: .9, up: 1, gravity: 1, seed: 7, grow: true, dur: .8 }));
    for (let i = 0; i < 4; i++) S.fx.push(CS.burst("dust", [-6 + i * 4, .2, -8 + (i % 2) * 3], T.w("trampling") + i * .18, { n: 6, size: .9, spread: .9, up: .6, gravity: .6, seed: 200 + i, grow: true, dur: .8 }));
    const pingT = [T.w("bullets"), T.w("like"), T.w("tanks")];
    pingT.forEach((t0, i) => S.fx.push(CS.pop("spark", [30.0 + (i - 1) * .12, 2.08 + i * .03, -5.9], t0, t0 + .18, { size: .55 })));
    S.fx.push(CS.pop("star", [-1.0, 3.25, 8.4], T.w("right") - .05, T.w("right") + .5, { size: .35 }));
    S.fx.push(CS.burst("feather", [0.4, 2.4, -3.0], T.w("birds", 30), { n: 9, size: .32, spread: 1.1, up: 1.4, gravity: 1.5, seed: 5, dur: 1.2, colors: ["#7a5a40", "#5a4030"] }));
    S.flashSpr = CS.sprite(CS.fxTex("spark", { color: "#fff2a0" }), .9);
    S.speed = CS.sprite(CS.fxTex("speed"), 1.6);
    this.cam = CS.camPath(this.camKeys(T));
  },

  camKeys(T) {
    const w = (q, a) => T.w(q, a), tx = this.truckX.bind(this, T);
    const k = [];
    // 1 hook: MCU, slow push
    k.push({ t: 0, p: [0.3, 1.62, 11.6], l: [0.26, 1.52, 8], fov: 35 }, { t: w("twenty") - .02, p: [0.34, 1.62, 10.8], l: [0.32, 1.58, 8], fov: 35, e: "lin" });
    // 2 wide crane down
    k.push({ t: w("twenty"), p: [-5, 11, 25], l: [-1, 0, -8], fov: 42, e: "cut" }, { t: w("so") - .02, p: [-3.6, 5.2, 16.5], l: [-2.5, 1.2, -6], fov: 42, e: "smooth" });
    // 3 truck arrives (3/4 front, tracking)
    const t3 = w("so");
    for (let i = 0; i <= 6; i++) { const t = t3 + i * (w("easy") - .04 - t3) / 6, x = tx(t); k.push({ t, p: [x + 7.6 - i * .2, 3.3, 15.6 - i * .2], l: [x - .9, 1.7, 8], fov: 40, e: i ? "lin" : "cut" }); }
    // 4 close-up
    k.push({ t: w("easy") - .04, p: [-0.95, 2.62, 11.2], l: [-1.4, 2.5, 8.2], fov: 30, e: "cut" }, { t: w("the emus") - .02, p: [-1.1, 2.6, 10.6], l: [-1.4, 2.5, 8.2], fov: 30, e: "lin" });
    // 5a over the guns
    k.push({ t: w("the emus"), p: [2.5, 6.2, -25], l: [-.8, .9, 3], fov: 44, e: "cut" }, { t: w("ran") - .12, p: [2.2, 5.6, -23.5], l: [-.8, .9, 3], fov: 44, e: "lin" });
    // 5b whip + follow the hero emu
    const hx = this.heroX || (t => 1);
    const r0 = w("ran");
    for (let i = 0; i <= 8; i++) { const t = r0 + .1 + i * (w("major", 20) - .14 - r0) / 8, x = Math.min(hx(t), 19.4); k.push({ t, p: [x - 2.4, 1.55, 4.6], l: [x + .5, 1.25, -1.5], fov: 38, e: i ? "lin" : "out" }); }
    // 6 helmet emu
    k.push({ t: w("major", 20) - .02, p: [30.55, 1.95, -1.7], l: [30.05, 1.85, -6], fov: 30, e: "cut" }, { t: w("after") - .02, p: [30.4, 1.95, -2.3], l: [30.05, 1.9, -6], fov: 30, e: "lin" });
    // 7 sunset drive home
    k.push({ t: w("after"), p: [7.5, 2.1, 14.5], l: [-2, 1.4, 8], fov: 40, e: "cut" }, { t: w("the emus", 26) - .02, p: [5.5, 2.4, 13.5], l: [-12, 1.2, 8], fov: 40, e: "smooth" });
    // 8-9 feast, push in on the hat emu, roll on the sting
    const t8 = w("the emus", 26), tTo = w("to", 30);
    k.push({ t: t8, p: [1.1, 1.9, 4.2], l: [0, 1.35, -4], fov: 40, e: "cut" }, { t: tTo, p: [0.45, 2.15, -0.2], l: [0.25, 2.05, -3.1], fov: 34, e: "smooth" }, { t: tTo + 1.6, p: [0.36, 2.3, -1.1], l: [0.22, 2.3, -3.1], fov: 32, roll: 4, e: "out" });
    return k;
  },
  truckX(T, t) {
    const a = T.w("so"), b = T.w("after");
    if (t < a - .3) return -70;
    if (t < b + .3) return CS.lerp(-17, -1, CS.ease.out(CS.seg(t, a - .3, a + 1.2)));
    return CS.lerp(-1, -62, CS.ease.in(CS.seg(t, b + .3, b + 3.4)));
  },

  frame(t, T) {
    const S = this, E = CS.ease, sg = CS.seg, R = CS.rand, w = (q, a) => T.w(q, a);
    const q = (x, n) => Math.round(x * n) / n, cyc = (x) => q(((x % 1) + 1) % 1, 8) % 1;
    const tSo = w("so"), tEasy = w("easy"), tSplit = w("the emus"), tRan = w("ran"), tDodge = w("dodged"), tMaj = w("major", 20), tAfter = w("after"), tHome = w("home"), tKept = w("the emus", 26), tAus = w("australia", 27), tTo = w("to", 30), tBirds = w("birds", 30);
    const shot = t < w("twenty") ? 1 : t < tSo ? 2 : t < tEasy - .04 ? 3 : t < tSplit ? 4 : t < tRan ? 5 : t < tMaj - .02 ? 5.5 : t < tAfter ? 6 : t < tKept ? 7 : 8;
    // light
    if (t < tAfter) CS.light("outback"); else CS.light("sunset");
    // camera (+ shake while the guns fire)
    const c = S.cam(t); let sh = [0, 0];
    for (const t0 of [tSplit + .3, tRan + .2]) if (t > t0 && t < t0 + 1.2) sh = [Math.sin(t * 90) * .012, Math.cos(t * 77) * .01];
    CS.cam(c, t, { shake: sh });
    // lens: rack focus on the hook, soft backgrounds on close-ups
    if (shot === 1) CS.lens({ focus: CS.lerp(3.3, 4.6, E.smooth(sg(t, w("with") + .1, w("birds") + .4))), blur: .32 });
    else if (shot === 4) CS.lens({ focus: 2.9, blur: .4 });
    else if (shot === 5.5) CS.lens({ focus: 4.3, blur: .22 });
    else if (shot === 6) CS.lens({ focus: 4.3, blur: .38 });
    else if (shot === 8) CS.lens({ focus: Math.hypot(c.p[0] - .25, c.p[1] - 2, c.p[2] + 3.1), blur: .3 });
    else CS.lens({ focus: 12, blur: shot === 2 ? 0 : .08 });
    const fl = Math.max(1 - Math.abs(t - tAfter) * 7, 0) * .9;   // white flash for the time jump
    if (fl > 0) CS.post.flash.value = fl;
    CS.shadowAt(c.l[0], c.l[2], shot === 2 ? 30 : 16);
    // world motion
    S.mill.rotor.rotation.z = -t * 2.2;
    const tx = S.truckX(T, t); S.truck.position.set(tx, 0, 8); S.truck.spin(tx);
    S.truck.position.y = (t > tSo - .3 && t < tSo + 1.2) || (t > tAfter + .3) ? Math.abs(Math.sin(t * 22)) * .03 : 0;
    const gunUp = E.back(sg(t, w("machine") - .1, w("guns") + .15)) * (1 - E.inOut(sg(t, w("packed") - .1, w("up") + .3)));
    S.guns.forEach((g, i) => { g.visible = t > w("machine") - .15 && t < tKept; g.pivot.rotation.z = CS.lerp(-1.1, .12, gunUp) + (shot === 5 || shot === 5.5 ? Math.sin(t * 3 + i) * .08 : 0); });
    // muzzle flash flicker while firing
    let firing = false; for (const t0 of [tSplit + .3, tRan + .2, w("everything") - .2]) if (t > t0 && t < t0 + 1.1) firing = true;
    const mp = new THREE.Vector3(); S.guns[0].muzzle.getWorldPosition(mp); S.flashSpr.position.copy(mp);
    S.flashSpr.visible = firing && Math.floor(t * 30) % 3 === 0 && shot >= 5 && shot < 6; S.flashSpr.material.rotation = t * 9;
    // ---------- people ----------
    const inTruck = (c, lx, lz) => { c.at(tx + lx, S.truck.bed + S.truck.position.y, 8 + lz); };
    const vis = (c, v) => c.show(v);
    // major: on the road for the hook, in the truck from shot 3
    if (shot === 1) {
      const surprise = sg(t, w("birds") + .15, w("birds") + .35);
      S.major.at(.02, 0, 8); vis(S.major, true);
      S.major.pose({ face: surprise > .5 ? "worried" : "proud", arms: ["hang", "salute"], look: surprise * .9, blink: CS.blinkAt(t, 2) });
    } else if (t > tSo && t < tKept) {
      const up = E.back(sg(t, w("a major") + .02, w("major") + .2));
      inTruck(S.major, -.35, .25); S.major.group.position.y -= (1 - up) * 2.3; vis(S.major, up > 0);
      const sad = t > tAfter, smug = shot === 4;
      S.major.pose({ face: sad ? "sad" : smug ? "smug" : shot >= 5 ? (t > w("dodged") ? "shock" : "determined") : "proud", arms: sad ? ["hang", "hang"] : smug ? ["hip", "thumb"] : shot >= 5 ? ["hip", "point"] : ["hip", "salute"], look: shot >= 5 && !sad ? -.4 : 0, blink: CS.blinkAt(t, 2) });
    } else vis(S.major, false);
    CS.alive(S.major, t, 2, { tilt: shot === 4 ? Math.sin(t * 5) * .02 : 0 });
    S.sold.forEach((s, i) => {
      const up = E.back(sg(t, w("soldiers") - .25 + i * .2, w("soldiers") + .05 + i * .2));
      if (t > tSo && t < tKept) { inTruck(s, i ? -2.7 : -1.45, i ? .45 : .5); s.group.position.y -= (1 - up) * 2.3; vis(s, up > 0); } else vis(s, false);
      const sad = t > tAfter;
      s.pose({ face: sad ? "sad" : shot >= 5 ? (t > tRan ? "shock" : "determined") : "happy", arms: sad ? ["hang", "hang"] : shot >= 5 ? ["hold", "hold"] : ["hang", "salute"], blink: CS.blinkAt(t, 3 + i) });
      CS.alive(s, t, 3 + i, { tilt: sad ? -.05 : 0 });
    });
    // farmer
    vis(S.farmer, shot === 2 || shot === 3); S.farmer.at(-7.4, 0, -11.6);
    S.farmer.pose({ face: t > w("trampling") ? "furious" : "angry", arms: ["fist", t > w("trampling") ? "fist" : "hip"], wave: t * 2, blink: CS.blinkAt(t, 9) });
    CS.alive(S.farmer, t, 9, { tilt: t > w("trampling") ? Math.sin(t * 14) * .05 : 0 });
    // ---------- emus ----------
    const fieldOn = shot >= 2 && shot <= 6;
    S.emus.forEach((e, i) => {
      let x = e.x, z = e.z, pose = { face: "norm", blink: CS.blinkAt(t, e.seed) }, flip = e.flip, lift = 0;
      const tr = t > w("trampling") - .2 && t < w("farms") + .6 && i % 3 === 0;
      if (t < tSplit + .2 + R(i) * .3) {
        const cy = (t * .5 + R(i * 5)) % 1; pose.peck = q(cy < .4 ? Math.sin(cy / .4 * Math.PI) : 0, 4);
        if (tr) { pose.run = .5; pose.step = cyc(t * 3 + R(i)); pose.peck = 0; pose.face = "happy"; }
        x += CS.noise1(t * .3, e.seed) * .4;
      } else {
        const t0 = tSplit + .2 + R(i) * .3, dt = t - t0, dx = e.x - 0 + (R(i * 3) - .5) * 3, dz = e.z + 7 + (R(i * 4) - .5) * 3, L = Math.hypot(dx, dz) || 1;
        const d = dt < .4 ? dt * dt * 11 : 1.76 + (dt - .4) * 8.5;
        x = e.x + dx / L * d; z = e.z + dz / L * d; flip = dx < 0;
        pose = { face: "shock", run: 1, step: cyc(dt * 3.2 + R(i)), beak: q(Math.abs(Math.sin(dt * 8 + i)), 2) * .5, blink: 0 };
      }
      e.c.show(fieldOn && Math.abs(x) < 120 && z > -120); e.c.at(x, 0, z); e.c.flip(flip); e.c.pose(pose);
    });
    // hook emu (shot 1)
    { const k = E.back(sg(t, w("with") - .05, w("birds") + .25)); S.hook.show(shot === 1); S.hook.at(CS.lerp(1.55, .95, k), 0, CS.lerp(5.2, 7.25, k)); S.hook.flip(true);
      S.hook.pose({ face: k > .5 ? "smug" : "norm", neck: k * .5, look: -.2, blink: CS.blinkAt(t, 31), beak: t > w("birds") + .3 && t < w("birds") + .6 ? .6 : 0 }); CS.alive(S.hook, t, 31); }
    // hero runner (shot 5b)
    { const on = shot === 5.5, x = Math.min(S.heroX(t), 19.4), hop = sg(t, tDodge - .05, tDodge + .45), hy = Math.sin(hop * Math.PI) * .9, dz = E.out(hop) * 1.1, stop = sg(t, tDodge + .5, tDodge + 1.1);
      S.hero.show(on); S.hero.at(x, 0, -1.5 + dz); S.hero.group.position.y = hy;
      S.hero.pose({ face: t > tDodge + .3 ? "smug" : "angry", run: 1 - stop, step: cyc((t - tRan) * 3.4), neck: -.1, beak: 0, blink: CS.blinkAt(t, 33) });
      S.speed.visible = on && stop < .5; S.speed.position.set(x - 1.3, 1.3, -1.4); S.speed.material.opacity = 1; }
    // helmet emu (shot 6)
    { S.helm.show(shot === 6); S.helm.at(30, 0, -6); S.helm.flip(true); const ping = Math.max(...[w("bullets"), w("like"), w("tanks")].map(t0 => 1 - Math.min(1, Math.abs(t - t0 - .05) * 8)));
      S.helm.pose({ face: "smug", hat: "helmet", neck: -.05 - ping * .08, blink: CS.blinkAt(t, 35) }); CS.alive(S.helm, t, 35, { tilt: ping * .06 }); }
    // feast + hat emu (shots 8-9)
    S.feast.forEach((e, i) => { e.c.show(shot === 8); e.c.at(e.x, 0, e.z); e.c.flip(i % 2 === 0); const cy = (t * .6 + i * .3) % 1; e.c.pose({ face: "happy", peck: q(cy < .45 ? Math.sin(cy / .45 * Math.PI) : 0, 4), blink: CS.blinkAt(t, e.seed) }); CS.alive(e.c, t, e.seed); });
    { const on = shot === 8, smug = t > tTo - .05, sq = t > tBirds + .05 && t < tBirds + .5;
      S.hat.show(on); S.hat.at(.2, S.crateTop, -3.1); S.hat.flip(t < tAus);
      S.hat.pose({ face: smug ? "smug" : "happy", hat: "slouch", neck: smug ? -.15 : 0, beak: sq ? .8 : 0, look: smug ? -.3 : 0, blink: CS.blinkAt(t, 37) });
      CS.alive(S.hat, t, 37, { tilt: smug ? .05 : 0 }); }
    S.fx.forEach(f => f.update(t));
  },

  sound(A, T) {
    const w = (q, a) => T.w(q, a), s = A.sfx;
    A.music({ bpm: 116, key: 58, sections: [{ at: 0, style: "march" }, { at: w("after") - .05, style: "stop" }, { at: w("after") + .2, style: "tense" }, { at: w("the emus", 26) - .1, style: "march" }, { at: w("australia", 27) - .05, style: "stop" }], end: T.duration + .9 });
    s("drumroll", 0, .5, { dur: .7 }); s("thunk", .72, .6);
    s("pop", w("with") + .05, .7); s("squawk", w("birds") + .3, .8);
    s("whoosh", w("twenty") - .2, .6); s("squawk", w("emus") + .1, .4, { f: 280 });
    [0, .25, .5, .75].forEach(d => s("thunk", w("trampling") + d, .55)); s("boomdrum", w("farms"), .6);
    s("engine", w("so") - .4, .6, { dur: 2.6 }); s("horn", w("army") + .1, .5);
    s("pop", w("major") + .05, .7); s("pop", w("soldiers") - .15, .6); s("pop", w("soldiers") + .1, .6); s("thunk", w("machine"), .6); s("ting", w("guns") + .1, .5);
    s("swish", w("easy") - .05, .5); s("ting", w("right") - .05, .6);
    s("whoosh", w("the emus") - .15, .5); s("rattle", w("the emus") + .3, .55, { n: 10 }); s("squawk", w("split") + .1, .7, { f: 360 }); s("squawk", w("up") + .1, .5, { f: 300 });
    s("whoosh", w("ran") - .1, .7, { dur: .35 }); s("rattle", w("ran") + .2, .5, { n: 10 }); [0, .3, .6, .9, 1.2].forEach(d => s("step", w("ran") + .1 + d, .4));
    s("boing", w("dodged"), .7); s("squawk", w("everything") + .2, .5, { f: 420 });
    s("whoosh", w("major", 20) - .1, .4); [w("bullets"), w("like"), w("tanks")].forEach(t0 => s("ting", t0 + .02, .6)); s("squawk", w("tanks") + .4, .4, { f: 300 });
    s("whoosh", w("after") - .1, .6); s("engine", w("after") + .2, .5, { dur: 3.4 }); s("slidedown", w("home") - .05, .6);
    s("swish", w("the emus", 26) - .05, .4); s("squawk", w("kept") + .1, .5, { f: 340 }); s("pop", w("wheat") + .1, .4);
    s("sting", w("to", 30) - .02, .9); s("squawk", w("birds", 30) + .1, .8, { f: 300 }); s("flap", w("birds", 30) + .1, .5);
  },
};
