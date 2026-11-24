/* The Clock That Saved Sailors: demo short for the Science Story Shorts kit (John Harrison and longitude).
   THE SIX BEATS: weird action (a carpenter wants to save the navy with a clock) → stakes (1707) → the laugh (experts) →
   they look right (pendulums stop at sea, decades of work) → the clue (it fits in his hand) → the payoff (5 seconds in 81 days)
   → the science (15° an hour) → arguable last line (GPS is just very good clocks).
   FACTS: Harrison (1693-1776), a carpenter and self-taught clockmaker from Lincolnshire, began his sea clocks around 1730.
   Scilly naval disaster, 22 Oct 1707: four ships lost, 1,300-2,000 men (often blamed on longitude). H1-H3 took ~1730-1759
   (H3 alone 19 years). H4 (1759) is a large pocket watch; on the 1761-62 trial to Jamaica (81 days) it lost about 5 seconds.
   Earth turns 360° in 24 h = 15° an hour. The Board of Longitude held back the prize; George III backed him and Parliament
   paid him in 1773. GPS receivers find position from the timing of signals sent by satellites that carry atomic clocks.
   Dramatized: "the experts laughed" (the astronomers on the Board doubted and opposed him).
   Sources: rmg.co.uk/Harrison · en.wikipedia.org/wiki/Scilly_naval_disaster_of_1707 · historicengland.org.uk (marine chronometer)

   SHOT PLAN (30 shots, a cut every ~2 s, a sound on every cut)
    1 "In"          street   MCU hero beside a tall clock on a cart, push in
    2 "told"        hall     wide: hero talks to four wigged experts behind a green table
    3 "the navy"    sea      a warship sails by, tracking
    4 "with"        street   insert: the clock face, ting
    5 "Back"        sea fog  one ship lost in fog, wide
    6 "had no"      deck     captain with a map, scratches head, "?" on "idea"
    7 "In 1707"     storm    title 1707, rain, lightning, ships heading for rocks
    8 "hit"         storm    the ship slams a rock: boom, shake, flash
    9 "Over"        storm    wide: the ship sinks, hats float, music drops
   10 "So when"     hall     hero walks in holding his clock
   11 "the experts" hall     experts burst out laughing (laugh)
   12 "A clock?"    hall     CU: monocle expert sneers, points
   13 "On a rolling" hall    CU: expert rocks side to side mocking a ship (laugh2)
   14 "Every"       deck     insert: pendulum swinging, ticks
   15 "One big"     deck     wave hits, camera rolls, splash
   16 "stopped"     deck     CU: pendulum stuck at an angle
   17 "So he built" shop     hero hammering at the bench
   18 "His first"   shop     pull back: H1, a huge brass machine, rocking arms
   19 "His third"   shop     old hero, title "19 YEARS"
   20 "Then he"     shop     CU: the watch appears in his hand, sparkle
   21 "Eighty-one"  sea gold the ship sails to a palm island
   22 "it lost"     deck     sailor holds up the watch, crowd "ooh", title "5 SECONDS"
   23 "Here's"      shop     chalkboard writes 360° ÷ 24
   24 "The Earth"   space    globe turns 15°, clock hand moves one hour
   25 "Know"        deck     captain: watch in one hand, points at the sun
   26 "and you know" deck    top shot: chart, a red X pops on "exactly"
   27 "The experts still" hall  experts cross arms, old hero sad
   28 "The king"    throne   king stands and points, fanfare
   29 "Today"       city     modern girl with a phone map
   30 "GPS"         space    a satellite with a clock on it, sting on "clocks" */
window.SHORT = {
  title: "The Clock That Saved Sailors", slug: "the-clock-that-saved-sailors",
  script: `In seventeen thirty, a country carpenter told London he could save the *navy*… with a *clock.*
Back then, ships at sea had *no idea* where they were.
In seventeen-oh-seven, four warships hit the *rocks.* Over a thousand sailors drowned.
So when this carpenter showed up… the experts *laughed.* A *clock?* On a rolling *ship?*
Every clock had a swinging *pendulum.* One big wave… and it *stopped.*
So he built clocks with *no* pendulum at all.
His first one was *huge.* His third took him nineteen years.
Then he built the fourth… and it fit in his *hand.*
Eighty-one days at sea, all the way to Jamaica… it lost five *seconds.*
Here's why that matters. The *Earth* turns fifteen degrees every hour.
Know the time back home and the time where you are… and you know *exactly* where you are.
The experts still wouldn't *pay* him. The *king* had to step in.
Today, your *phone* finds you the same way. GPS… is just very good *clocks.*`,
  tail: 1.2,
  captions: { subs: { "seventeen thirty": "1730", "seventeen-oh-seven": "1707", "a thousand": "1,000", "four": "4", "nineteen": "19", "eighty-one": "81", "five": "5", "fifteen": "15" } },

  init(T) {
    if (this._T === T) return; this._T = T; const S = this;
    const w = (q, a = 0) => T.w(q, a);
    S.W = { carpenter: w("carpenter"), clock1: w("clock"), idea: w("idea"), y1707: w("seventeen-oh-seven"), hit: w("hit"), rocks: w("rocks"), over: w("over"),
      so: w("so when"), laughed: w("laughed"), aclock: w("clock?"), rolling: w("rolling"), every: w("every"), wave: w("wave"), stopped: w("stopped"),
      built: w("so he built"), first: w("first"), huge: w("huge"), third: w("third"), nineteen: w("nineteen"), then: w("then he"), fit: w("fit"), hand: w("hand"),
      eighty: w("eighty-one"), jamaica: w("jamaica"), lost: w("lost"), five: w("five"), seconds: w("seconds"), heres: w("here's"), earth: w("earth"), fifteen: w("fifteen"),
      hour: w("hour"), know: w("know the"), home: w("home"), where2: w("where you are", 46), exactly: w("exactly"), still: w("still"), pay: w("pay"), king: w("king"), step: w("step"),
      today: w("today"), phone: w("phone"), gps: w("gps"), very: w("very"), clocks: w("clocks", 50) };
    const Wt = S.W; S.strikes = [Wt.y1707 + .35, Wt.hit + .1, Wt.over + .9];
    // ---------- shots ----------
    const v = (p, l, fov = 40, roll = 0) => ({ p, l, fov, roll });
    S.plan = CS.shots(T, [
      { at: 0, set: "street", light: "bright", from: v([.15, 1.85, 5.6], [.12, 1.55, 0]), to: v([.12, 1.8, 4.7], [.12, 1.6, 0]), blur: .18 },
      { at: "told", set: "hall", light: "hall", from: v([.2, 2.1, 8.6], [0, 1.4, -1]), to: v([0, 2.0, 7.6], [0, 1.4, -1]), blur: .1 },
      { at: "the navy", set: "sea", light: "bright", from: v([-4, 4, 38], [-2, 3.4, 0], 40), to: v([2, 4, 36], [2, 3.4, 0], 40), blur: .03, id: "navy" },
      { at: "with a", set: "street", light: "bright", from: v([.66, 2.9, 2.4], [.62, 2.85, -.5], 38), to: v([.64, 2.9, 1.8], [.62, 2.85, -.5], 38), blur: .3 },
      { at: "back then", set: "sea", light: "fog", from: v([20, 7, 46], [0, 3, 0], 36), to: v([14, 6, 40], [0, 3, 0], 36), blur: 0, id: "fog" },
      { at: "had no", set: "deck", light: ["fog", "bright", .4], from: v([0, 1.7, 3.6], [-.4, 1.45, 0]), to: v([-.2, 1.65, 3.0], [-.4, 1.5, 0]), blur: .22 },
      { at: "in seventeen-oh-seven", set: "sea", light: "storm", from: v([-10, 5, 34], [6, 2, -2], 40), to: v([-6, 4.5, 30], [8, 2, -2], 40), blur: 0, id: "storm1", flash: t => CS.flashAt(t, S.strikes) },
      { at: "hit", set: "sea", light: "storm", from: v([10, 4.5, 34], [6, 2.6, 0], 38), to: v([9, 4.2, 30], [6, 2.6, 0], 38), blur: .05, shake: .35, shakeAt: Wt.hit + .1, shakeDur: .5, id: "hit", flash: t => CS.flashAt(t, S.strikes) },
      { at: "over a", set: "sea", light: "storm", from: v([26, 9, 34], [12, 1, 0], 36), to: v([24, 8, 30], [12, 1, 0], 36), blur: 0, id: "sink", flash: t => CS.flashAt(t, S.strikes) },
      { at: "so when", set: "hall", light: "hall", from: v([0, 2.0, 8.6], [-.2, 1.4, -.5]), to: v([0, 1.95, 7.8], [-.2, 1.4, -.5]), blur: .1, id: "enter" },
      { at: "the experts", after: 16, set: "hall", light: "hall", from: v([0, 1.8, 4.6], [0, 1.5, -2]), to: v([0, 1.75, 3.9], [0, 1.5, -2]), blur: .15, id: "laugh" },
      { at: "a clock?", after: 19, set: "hall", light: "hall", from: v([-1.15, 1.6, 1.2], [-1.2, 1.55, -2]), to: v([-1.18, 1.6, .8], [-1.2, 1.55, -2]), blur: .3, id: "sneer" },
      { at: "on a", set: "hall", light: "hall", from: v([.4, 1.6, 1.0], [.4, 1.55, -2], 40, 4), to: v([.4, 1.6, .7], [.4, 1.55, -2], 40, -4), blur: .3, id: "roll" },
      { at: "every", set: "deck", light: "bright", from: v([.05, 1.15, 1.4], [0, 1.0, -1.6], 36), to: v([.05, 1.1, 1.0], [0, .95, -1.6], 36), blur: .3, id: "pend" },
      { at: "one big", set: "deck", light: "bright", from: v([0, 2.4, 6.5], [0, 1.4, -1], 42), to: v([0, 2.2, 6.0], [0, 1.4, -1], 42, -9), blur: .05, shake: .14, shakeAt: Wt.wave + .15, id: "wave" },
      { at: "and it", after: 24, set: "deck", light: "bright", from: v([.05, 1.1, 1.0], [0, .95, -1.6], 34, -9), to: v([.05, 1.08, .8], [0, .95, -1.6], 34, -9), blur: .32, id: "stopped" },
      { at: "so he built", set: "shop", light: "shop", from: v([-.3, 1.6, 3.6], [-.4, 1.3, -1]), to: v([-.3, 1.55, 3.0], [-.4, 1.35, -1]), blur: .2, id: "hammer" },
      { at: "his first", set: "shop", light: "shop", from: v([.9, 2.6, 2.4], [.9, 2.6, -2]), to: v([.2, 2.4, 7.2], [.2, 2.0, -1.4]), blur: .08, ease: "out", id: "h1" },
      { at: "his third", set: "shop", light: "shop", from: v([-.3, 1.55, 3.4], [-.4, 1.35, -1]), to: v([-.3, 1.55, 3.0], [-.4, 1.35, -1]), blur: .45, id: "old" },
      { at: "then he", set: "shop", light: "shop", from: v([.1, 1.5, 3.4], [.1, 1.4, 0]), to: v([.15, 1.45, 2.6], [.15, 1.42, 0]), blur: .3, id: "watch" },
      { at: "eighty-one", set: "sea", light: "voyage", from: v([-24, 6, 30], [10, 4, -10], 40), to: v([-6, 5, 28], [24, 4, -16], 40), blur: 0, id: "voyage" },
      { at: "it lost", set: "deck", light: "voyage", from: v([0, 1.8, 5.2], [0, 1.6, -.6]), to: v([0, 1.75, 4.4], [0, 1.6, -.6]), blur: .12, id: "lost" },
      { at: "here's", set: "shop", light: "shop", from: v([-1.9, 1.9, 2.6], [-1.9, 1.95, -3.3], 40), to: v([-1.9, 1.9, 2.0], [-1.9, 1.95, -3.3], 40), blur: .15, id: "board" },
      { at: "the earth", set: "space", light: "space", from: v([0, 1.2, 11], [.8, .4, 0], 40), to: v([0, .8, 9.5], [.8, .3, 0], 40), blur: 0, id: "globe" },
      { at: "know the", set: "deck", light: "bright", from: v([0, 1.9, 4.6], [0, 1.9, -1]), to: v([0, 2.0, 4.0], [0, 2.0, -1]), blur: .12, id: "sun" },
      { at: "and you know", set: "deck", light: "bright", from: v([0, 4.2, 3.4], [.1, .95, 1.6], 40), to: v([0, 3.6, 2.9], [.2, .95, 1.6], 40), blur: .1, id: "chart" },
      { at: "the experts", after: 49, set: "hall", light: "hall", from: v([0, 2.0, 8.4], [0, 1.4, -.8]), to: v([0, 1.95, 7.4], [0, 1.4, -.8]), blur: .1, id: "nopay" },
      { at: "the king", set: "throne", light: "hall", from: v([0, 2.0, 6.0], [0, 1.7, -2]), to: v([0, 1.9, 4.6], [0, 1.8, -2]), blur: .12, id: "king" },
      { at: "today", set: "city", light: "city", from: v([.2, 1.7, 3.6], [0, 1.5, 0]), to: v([.15, 1.6, 2.6], [0, 1.45, 0]), blur: .2, id: "phone" },
      { at: "gps", set: "space", light: "space", from: v([0, 3.6, 7.5], [0, 4.3, 0], 40), to: v([0, 4.3, 2.4], [0, 4.25, 0], 40), blur: .05, ease: "inOut", id: "sat" },
    ]);
  },

  setup(T) {
    const S = this, Wd = CS.world, R = CS.rand, P = (spec, parent, o) => CS.person(Object.assign({ style: "round" }, spec), Object.assign({ parent }, o || {}));
    S.init(T); const Wt = S.W;
    // ---------- looks ----------
    CS.LIGHTS.bright = Object.assign({}, CS.LIGHTS.day, { sat: 1.18, top: "#2f86e8", hor: "#cfeaff" });
    CS.LIGHTS.hall = Object.assign({}, CS.LIGHTS.indoor, { sun: "#fff6e8", card: "#ffffff", sat: 1.14, gain: [1.02, 1.01, 1.0], hemiI: 1.35 });
    CS.LIGHTS.shop = Object.assign({}, CS.LIGHTS.indoor, { sun: "#fff1dc", card: "#fffaf2", sat: 1.16, hemiI: 1.3 });
    CS.LIGHTS.fog = Object.assign({}, CS.LIGHTS.day, { top: "#8aa0b8", hor: "#c8d2dc", fog: [12, 90], sunI: 1.6, sat: .85, card: "#e6eaf0" });
    CS.LIGHTS.storm = Object.assign({}, CS.LIGHTS.night, { top: "#0b1430", hor: "#2c3e66", fog: [70, 300], sunI: 1.1, sat: .95, card: "#a6b4dc", stars: 0 });
    CS.LIGHTS.voyage = Object.assign({}, CS.LIGHTS.golden, { sat: 1.2, top: "#3a7ad8", hor: "#ffd2a0" });
    CS.LIGHTS.space = Object.assign({}, CS.LIGHTS.night, { top: "#05060f", hor: "#101a3a", stars: 1, fog: [200, 900], sunI: 2.6, sun: "#fff4e0", az: 60, el: 20, card: "#e8ecff", sat: 1.15, hemiI: .7 });
    CS.LIGHTS.city = Object.assign({}, CS.LIGHTS.dusk, { sat: 1.2, top: "#2a2f7a", hor: "#ff8a6a", card: "#ffe0d8" });
    // ---------- cast looks ----------
    const hero = { hair: { style: "short", color: "#5a3a26" }, top: { type: "coat", color: "#2f6fa8", vest: "#f08a2a", shirt: "#ffffff" }, pants: "#3a2e2a" };
    const heroOld = Object.assign({}, hero, { hair: { style: "tufts", color: "#d8d4cc" }, mustache: "thin", mustacheColor: "#d8d4cc" });
    const expert = (coat, o = {}) => Object.assign({ hair: { style: "wig", color: "#f2f0ea" }, top: { type: "coat", color: coat, vest: o.vest || "#e8d6a0" } }, o);
    const exSpecs = [expert("#6a3f8a", { monocle: true }), expert("#2a3a5a", { glasses: true }), expert("#8a2f3a", { mustache: "handlebar", mustacheColor: "#d8d4cc" }), expert("#3a5a3a", { hat: { type: "tricorn", color: "#1d1d24" } })];
    const captain = { hat: { type: "tricorn", color: "#1d1d2a", trim: "#e8c048" }, hair: { style: "wig", color: "#f2f0ea" }, top: { type: "uniform", color: "#24407a", trim: "#f4f0e6" }, mustache: "handlebar", mustacheColor: "#6a4a2a" };
    const sailor = (c, hat) => ({ hair: { style: "short", color: c }, hat, top: { type: "shirt", color: "#f4f6fa" }, pants: "#2a3a6a" });

    // ================= STREET =================
    let G = CS.set("street");
    Wd.ground([300, 300], Wd.painted("stone", "#b8b0a8"), G, { tile: 3 });
    const houseCols = ["#e6735a", "#f2c85a", "#6fb3d8", "#f4efe6", "#8fcf8a", "#e88aa8", "#f2c85a"];
    for (let i = -3; i <= 3; i++) Wd.house({ w: 4, d: 4, h: 5.2 + (i % 2 ? .8 : 0), wall: houseCols[i + 3], roof: i % 2 ? "#3f4f7a" : "#7a3a3a", windows: 2 }, [i * 4.3, 0, -9], G);
    Wd.lamp([-2.4, 0, -2.6], G); Wd.lamp([3.4, 0, -3.4], G);
    Wd.clouds(10, 160, 60, 2, G, { cz: -80, size: 34 });
    S.cart = new THREE.Group(); S.cart.position.set(.62, 0, -.5); G.add(S.cart);
    Wd.box(1.3, .35, .9, Wd.painted("planks", "#a8743f"), [0, .45, 0], S.cart);
    for (const s of [-1, 1]) Wd.cyl(.42, .42, .08, CS.mat("#6a4a2a"), [0, .42, s * .5], S.cart, { rot: [Math.PI / 2, 0, 0] });
    S.clock1 = Wd.tallClock({ color: "#8a4a2a" }, S.cart); S.clock1.position.y = .8; S.clock1.scale.setScalar(.95);
    S.h1 = P(hero, G).at(-.38, 0, .35);

    // ================= HALL (the experts) =================
    G = CS.set("hall");
    Wd.room({ w: 10, d: 8, h: 4.8, wall: "#2f8f8a", wallTex: "stripes", wain: "#6a3f2a", floor: "#f4ecd8", floor2: "#2f6f6a", windows: [-3.4, 3.4], sconces: [-1.8, 1.8], winH: 2.4 }, G);
    const shipPic = document.createElement("canvas"); shipPic.width = 400; shipPic.height = 260; { const g = shipPic.getContext("2d"); const gr = g.createLinearGradient(0, 0, 0, 260); gr.addColorStop(0, "#9fd0f0"); gr.addColorStop(1, "#f4e2b8"); g.fillStyle = gr; g.fillRect(0, 0, 400, 260); g.fillStyle = "#2f6fa8"; g.fillRect(0, 180, 400, 80); g.fillStyle = "#5a3a26"; g.beginPath(); g.moveTo(110, 170); g.lineTo(290, 170); g.lineTo(260, 205); g.lineTo(140, 205); g.fill(); g.fillStyle = "#fff"; for (const x of [150, 200, 250]) { g.beginPath(); g.moveTo(x, 70); g.lineTo(x + 30, 160); g.lineTo(x - 26, 160); g.fill(); } }
    const pic = Wd.frame(2.0, 1.3, shipPic, { color: "#c8962e" }, G); pic.position.set(0, 2.6, -3.95);
    Wd.box(3.8, .9, 1.3, CS.mat("#2f6a3a", { tex: "flat", texOpt: { color: "#2f6a3a" } }), [0, 0, -1.25], G);
    Wd.box(4.0, .08, 1.45, CS.mat("#e8c048"), [0, .86, -1.25], G);
    for (let i = 0; i < 4; i++) { Wd.box(.4, .02, .3, CS.mat("#fbf7ec"), [-1.2 + i * .8 + .12, .94, -1.0], G); Wd.cyl(.05, .05, .12, CS.mat("#2a2226"), [-1.2 + i * .8 - .2, .94, -1.05], G); }
    S.ex = exSpecs.map((sp, i) => P(sp, G).at(-1.2 + i * .8, 0, -2.0 - (i % 2) * .15));
    S.h2 = P(hero, G); S.h2old = P(heroOld, G);

    // ================= SEA (day, fog, storm, voyage) =================
    G = CS.set("sea");
    S.water = Wd.water(1200, 1200, "#2f7fc0", [0, 0, 0], G);
    S.ship = Wd.ship({ flag: "union", seed: 1 }, G);
    S.ships = [Wd.ship({ flag: "union", seed: 2 }, G), Wd.ship({ flag: "union", seed: 3 }, G)];
    S.ships[0].position.set(-14, 0, -26); S.ships[1].position.set(16, 0, -40);
    S.rocks = Wd.rocks(9, [8, -10, 22, 6], { color: "#5a5a66", size: 2.6 }, 5, G);
    S.island = new THREE.Group(); S.island.position.set(70, 0, -60); G.add(S.island);
    Wd.hill(14, "#f2d08a", [0, 0, 0], S.island, { squash: .35 }); Wd.hill(9, "#5cb04a", [-2, 1, -2], S.island, { squash: .45 });
    for (let i = 0; i < 6; i++) Wd.tree("palm", 6 + R(i) * 3, [-8 + i * 3.2, 2, -2 + R(i + 4) * 5], S.island, i);
    S.seaClouds = Wd.clouds(14, 320, 80, 9, G, { cz: -160, size: 60 });
    S.hats = [0, 1, 2].map(i => { const h = Wd.cyl(.5, .6, .25, CS.mat("#1d1d2a"), [13 + i * 1.6, .05, 2 + i], G); return h; });

    // ================= DECK =================
    G = CS.set("deck");
    Wd.box(14, .3, 9, Wd.painted("planks", "#c8955a", { n: 8 }), [0, -.3, -1], G, { tile: 2 });
    for (let i = -6; i <= 6; i += 1.5) Wd.box(.16, 1.0, .16, CS.mat("#7a4a2a"), [i, 0, -4.4], G);
    Wd.box(14, .14, .26, CS.mat("#7a4a2a"), [0, 1.0, -4.4], G);
    Wd.cyl(.24, .3, 14, CS.mat("#7a4a2a"), [2.8, 0, -3.2], G);
    { const sg = new THREE.PlaneGeometry(5, 4.5); const sail = new THREE.Mesh(sg, CS.mat("#f6f1e4", { side: THREE.DoubleSide })); sail.position.set(2.8, 7.2, -3.0); sail.rotation.y = .2; CS.add(sail, G); }
    S.dwater = Wd.water(800, 800, "#2f86c8", [0, -2.4, 0], G);
    Wd.clouds(10, 220, 50, 4, G, { cz: -140, size: 50 });
    S.sun = Wd.ball(6, CS.mat("#fff2a0", { emissive: "#ffe070", emissiveI: 2 }), [-40, 38, -150], G); S.sun.userData.ink = "none";
    S.clock2 = Wd.tallClock({ color: "#8a4a2a" }, G); S.clock2.position.set(0, 0, -1.6);
    S.cap = P(captain, G); S.sail = [P(sailor("#3a2a20", { type: "cap", color: "#2a3a6a" }), G), P(sailor("#a8642e"), G), P(sailor("#1d1d24", { type: "flat", color: "#5a6a7a" }), G)];
    S.chart = new THREE.Group(); G.add(S.chart); S.chart.position.set(0, 0, 1.6);
    Wd.box(2.4, .95, 1.5, Wd.painted("planks", "#8a5a33"), [0, 0, 0], S.chart);
    const chartTex = CS.paint.canvasTex(1024, 640, (g) => { g.fillStyle = "#f2e2b8"; g.fillRect(0, 0, 1024, 640); g.fillStyle = "#9fd0e8"; g.fillRect(40, 40, 944, 560);
      g.fillStyle = "#e8d49a"; for (const [x, y, rx, ry] of [[200, 200, 130, 90], [520, 430, 90, 60], [800, 180, 150, 70], [860, 470, 70, 50]]) { g.beginPath(); g.ellipse(x, y, rx, ry, .3, 0, 7); g.fill(); g.strokeStyle = "#8a6a3a"; g.lineWidth = 5; g.stroke(); }
      g.strokeStyle = "rgba(60,80,120,.45)"; g.lineWidth = 3; for (let i = 1; i < 8; i++) { g.beginPath(); g.moveTo(40 + i * 118, 40); g.lineTo(40 + i * 118, 600); g.stroke(); } for (let j = 1; j < 5; j++) { g.beginPath(); g.moveTo(40, 40 + j * 112); g.lineTo(984, 40 + j * 112); g.stroke(); }
      g.strokeStyle = "#5a3a26"; g.lineWidth = 12; g.strokeRect(40, 40, 944, 560); });
    S.chartTop = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 1.375), CS.mat("#ffffff", { tex: chartTex })); S.chartTop.rotation.x = -Math.PI / 2; S.chartTop.position.set(0, .97, 0); CS.add(S.chartTop, S.chart);
    S.xMark = new THREE.Group(); S.xMark.position.set(.25, 1.0, .1); S.chart.add(S.xMark);
    for (const r of [.7, -.7]) Wd.box(.36, .03, .07, CS.mat("#e5383b"), [0, 0, 0], S.xMark, { rot: [0, r, 0] });

    // ================= WORKSHOP =================
    G = CS.set("shop");
    Wd.room({ w: 9, d: 7, h: 4.3, wall: "#5c8fbf", wallTex: "planks", wallOpt: { n: 6 }, wain: "#6a4a3a", floor: "#c8955a", floorTex: "planks", floorOpt: { n: 6 }, windows: [3.0], winW: 1.4, winH: 2.1, sconces: [-.8] }, G);
    Wd.box(3.6, .95, 1.1, Wd.painted("planks", "#a8743f", { n: 3 }), [-.6, 0, -2.6], G);
    for (let i = 0; i < 5; i++) Wd.box(.12 + R(i) * .3, .08, .3, CS.mat(["#c8962e", "#6a6a72", "#8a5a33"][i % 3]), [-1.9 + i * .55, .95, -2.5 + R(i + 3) * .3], G);
    S.gears = [[-2.6, 2.9, .5], [-1.85, 2.5, .34], [-3.2, 2.2, .3], [.6, 3.0, .42]].map(([x, y, r], i) => { const gg = Wd.cyl(r, r, .08, CS.mat(i % 2 ? "#c8962e" : "#e8b93c"), [x, y, -3.4], G, { rot: [Math.PI / 2, 0, 0], seg: 12 }); return gg; });
    for (let i = 0; i < 3; i++) Wd.clock(.22, [1.5 + i * .6, 2.6, -3.4], G).set(2 + i * 3);
    Wd.box(2.2, .06, .3, CS.mat("#7a4a2a"), [2.1, 2.25, -3.35], G);
    S.board = Wd.board("EARTH = 360°\n÷ 24 hours\n= 15° an hour", { w: 2.1, h: 1.45, head: "#ffd23a" }, G); S.board.position.set(-1.9, 1.35, -3.35);
    // H1: a big brass sea clock with rocking balance arms
    S.H1 = new THREE.Group(); S.H1.position.set(.9, 0, -2.0); S.H1.scale.setScalar(1.75); G.add(S.H1);
    Wd.box(1.4, .7, 1.0, Wd.painted("planks", "#6a4a2a"), [0, 0, 0], S.H1);
    Wd.box(1.3, 1.1, .9, CS.mat("#e8b93c", { tex: "metal", texOpt: { color: "#e8b93c" } }), [0, .7, 0], S.H1);
    Wd.clock(.32, [0, 1.25, .47], S.H1).set(10.2);
    S.arms = [0, 1].map(i => { const a = new THREE.Group(); a.position.set(0, 2.0, i ? -.2 : .2); S.H1.add(a); Wd.box(1.9, .07, .07, CS.mat("#c8962e"), [0, -.035, 0], a); for (const s of [-1, 1]) Wd.ball(.2, CS.mat("#f2c230"), [s * .95, 0, 0], a); return a; });
    Wd.cyl(.05, .05, .9, CS.mat("#c8962e"), [0, 1.1, 0], S.H1);
    S.h3 = P(hero, G); S.h3old = P(heroOld, G);

    // ================= SPACE =================
    G = CS.set("space");
    S.globe = Wd.globe(3, { wedge: "#ffb02e" }, G);
    S.sunS = Wd.ball(8, CS.mat("#fff2a0", { emissive: "#ffe070", emissiveI: 2.2 }), [60, 20, -120], G); S.sunS.userData.ink = "none";
    S.sclock = Wd.clock(.6, [.9, 1.7, 4.0], G);
    S.sat = new THREE.Group(); S.sat.position.set(0, 4.6, 0); G.add(S.sat);
    const satBody = Wd.satellite({}, S.sat); satBody.scale.setScalar(.7);
    S.satClock = Wd.clock(.3, [0, -.36, .37], S.sat);

    // ================= THRONE ROOM =================
    G = CS.set("throne");
    Wd.room({ w: 10, d: 8, h: 5.2, wall: "#7a3a8a", wallTex: "stripes", wain: "#e8b93c", floor: "#f4ecd8", floor2: "#c8b8e8", windows: [-3.4, 3.4], sconces: [-1.6, 1.6], winH: 2.8 }, G);
    Wd.ground([2.4, 9], Wd.painted("carpet", "#c23a4a"), G, { tile: 2.4, y: .015, z: 0 });
    Wd.throne([0, 0, -3.1], {}, G);
    for (const s of [-1, 1]) Wd.flag("#c23a4a", [s * 2.6, 0, -3.3], G, { pole: 3.6, w: 1.0, h: 1.4 });
    S.king = P({ hat: { type: "crown" }, beard: true, beardColor: "#f2f0ea", hair: { style: "wig", color: "#f2f0ea" }, top: { type: "robe", color: "#c23a4a", trim: "#f4f0e6" }, size: 1.05 }, G);
    S.guards = [-1, 1].map(s => P({ hat: { type: "shako", color: "#1d1d24" }, top: { type: "uniform", color: "#c23a3a", trim: "#f4f0e6" }, pants: "#f4f0e6" }, G));

    // ================= CITY (today) =================
    G = CS.set("city");
    Wd.ground([300, 300], Wd.painted("stone", "#8a8a96"), G, { tile: 3 });
    const winTex = CS.paint.canvasTex(256, 512, (g) => { g.fillStyle = "#3a3f6a"; g.fillRect(0, 0, 256, 512); for (let i = 0; i < 4; i++) for (let j = 0; j < 10; j++) { g.fillStyle = R(i * 31 + j) > .45 ? "#ffd27a" : "#2a2f52"; g.fillRect(18 + i * 60, 16 + j * 50, 40, 32); } });
    for (let i = -4; i <= 4; i++) { const h = 12 + R(i + 9) * 16; Wd.box(5, h, 5, CS.mat(["#5a6aa8", "#7a5aa8", "#4a7aa8"][(i + 9) % 3], { tex: winTex, repeat: [1, Math.round(h / 8)] }), [i * 6, 0, -14 - R(i) * 6], G); }
    Wd.lamp([-2.2, 0, -2], G); Wd.lamp([2.8, 0, -3], G);
    S.girl = P({ hair: { style: "bun", color: "#2a1d1a" }, top: { type: "shirt", color: "#ff5f8a" }, pants: "#2f3f6a" }, G);

    // ---------- effects ----------
    S.fx = [];
    S.fx.push(CS.pop("?", [-.05, 2.3, .4], Wt.idea, Wt.idea + 1.2, { size: .7 }));
    S.fx.push(CS.pop("bang", [7.5, 4.6, 3], Wt.hit + .1, Wt.hit + .8, { size: 5.5 }));
    S.fx.push(CS.burst("spark", [.05, 1.1, .3], Wt.built + .4, { n: 10, size: .2, spread: .6, up: 1.2, gravity: 2, seed: 4, dur: .6 }));
    S.fx.push(CS.burst("spark", [.05, 1.1, .3], Wt.built + 1.2, { n: 10, size: .2, spread: .6, up: 1.2, gravity: 2, seed: 5, dur: .6 }));
    S.fx.push(CS.burst("star", [.45, 1.55, .3], Wt.fit, { n: 9, size: .16, spread: .5, up: .8, gravity: .4, seed: 8, dur: 1.2, colors: ["#ffe27a", "#fff6c0"] }));
    S.fx.push(CS.burst("confetti", [0, 2.4, 0], Wt.seconds, { n: 26, size: .18, spread: 2.2, up: 2.2, gravity: 2.4, seed: 9, dur: 1.6 }));
    S.fx.push(CS.burst("cloud", [1.5, .6, -2.6], Wt.wave + .15, { n: 12, size: 1.3, spread: 2.4, up: 2.6, gravity: 3, seed: 3, dur: 1.2, colors: ["#e8f4ff", "#bfe0ff"] }));
    S.fx.push(CS.burst("spark", [0, 4.3, .4], Wt.clocks, { n: 12, size: .2, spread: .8, up: .6, gravity: .3, seed: 11, dur: 1.2, colors: ["#fff6c0"] }));
    // overlay: title cards and the storm
    CS.title("1707", Wt.y1707 - .05, Wt.y1707 + 1.25, { size: 230 });
    CS.title("19 YEARS", Wt.nineteen - .05, Wt.then - .1, { size: 190, sub: "later…", dim: "#0b0712" });
    CS.title("ONLY 5 SECONDS", Wt.five - .05, Wt.heres - .12, { size: 130, sub: "in 81 days at sea" });
    CS.rain(Wt.y1707 - .2, Wt.so - .06, { n: 260 });
    S.strikes.forEach((s, i) => CS.bolt(s, [300, 760, 520][i], { seed: i + 2 }));

  },

  frame(t, T) {
    const S = this, Wt = S.W, sm = CS.ease.smooth, out = CS.ease.out, seg = CS.seg, b = (x, s) => CS.blinkAt(x, s);
    const sh = S.plan.apply(t), id = sh.shot.id, set = sh.shot.set, L = sh.local;
    const live = (c, s, o) => CS.alive(c, t, s, o);
    if (set === "street") {
      S.h1.pose({ face: t < Wt.carpenter ? "proud" : "happy", arms: ["hip", "point"], talk: t > 2.8 && t < 5.3 ? Math.round(t * 7) % 2 : 0, blink: b(t, 1), look: .6 }); live(S.h1, 1);
      S.clock1.swing(Math.sin(t * Math.PI) * .28); S.clock1.face.set(10 + t / 60);
    }
    if (set === "hall") {
      const laughing = (id === "laugh" && t > Wt.laughed - .05) || id === "sneer" || id === "roll";
      S.ex.forEach((c, i) => {
        let face = "stern", arms = ["hold", "hold"], o = {};
        if (id === "enter") face = t > Wt.so + .8 ? "smug" : "bored";
        if (laughing) { face = i === 0 ? "smug" : "laugh"; arms = i === 0 ? ["hip", "point"] : i === 3 ? ["cheek", "cheek"] : ["hip", "hip"]; o = { bob: 4, sway: 2 }; }
        if (id === "nopay") { face = i % 2 ? "stern" : "smug"; arms = ["shrug", "shrug"]; }
        if (id === "roll" && i === 2 && false) { c.pivot.rotation.z = Math.sin(L * 5) * .18; }
        c.at(-1.2 + i * .8, laughing ? Math.abs(Math.sin(t * 9 + i)) * .04 : 0, -2.0 - (i % 2) * .15).pose({ face, arms, look: i < 2 ? .5 : -.5, blink: b(t, 10 + i), talk: id === "sneer" && i === 0 ? Math.round(t * 7) % 2 : 0 });
        if (id === "roll" && i === 2) c.pivot.rotation.z = Math.sin(L * 5) * .2; else live(c, 10 + i, o);
      });
      const old = id === "nopay";
      S.h2.show(!old && id !== "laugh" && id !== "sneer" && id !== "roll"); S.h2old.show(old);
      if (id === "enter") { const k = sm(seg(t, Wt.so, Wt.so + 1.4)); S.h2.at(-2.6 + k * 2.0, 0, 1.9).pose({ face: "proud", arms: ["hang", "hold"], prop: { kind: "watch", hand: "R", r: 62 }, step: k * 3, stride: k < 1 ? .8 : 0, blink: b(t, 2) }); }
      else S.h2.at(-.55, 0, 2.0).pose({ face: "happy", arms: ["hip", "wave"], wave: t * 1.5, talk: Math.round(t * 7) % 2, blink: b(t, 2), look: .5 });
      S.h2old.at(-.55, 0, 2.0).pose({ face: "sad", arms: ["hang", "hang"], blink: b(t, 3), look: .6 }); live(S.h2, 2); live(S.h2old, 3);
    }
    if (set === "sea") {
      S.water.flow(t); S.ship.bob(t); S.ships.forEach(s => s.bob(t));
      S.island.visible = id === "voyage"; S.seaClouds.forEach(c => c.visible = !(id === "storm1" || id === "hit" || id === "sink")); S.rocks.visible = id === "storm1" || id === "hit" || id === "sink"; S.hats.forEach(h => h.visible = id === "sink");
      S.ships.forEach(s => s.visible = id === "storm1" || id === "navy");
      if (id === "navy") S.ship.position.set(-3 + L * 2.2, 0, 0);
      else if (id === "fog") S.ship.position.set(-2 + L * .6, 0, 0);
      else if (id === "storm1") { S.ship.position.set(-2 + L * 1.6, 0, 0); S.ship.rotation.z = Math.sin(t * 1.7) * .06; }
      else if (id === "hit") { const k = seg(t, Wt.hit - .5, Wt.hit + .1); S.ship.position.set(-4 + out(k) * 7.5, 0, 0); S.ship.rotation.z = t > Wt.hit + .1 ? -.12 - seg(t, Wt.hit + .1, Wt.over) * .2 : 0; }
      else if (id === "sink") { const k = seg(t, Wt.over, Wt.so); S.ship.position.set(3.5, -k * 3.2, 0); S.ship.rotation.set(0, 0, -.32 - k * .3); S.hats.forEach((h, i) => { h.position.y = .05 + Math.sin(t * 2 + i) * .06; }); }
      else if (id === "voyage") { S.ship.position.set(-2 + L * 3, 0, -4 - L * 1.4); S.ship.rotation.set(0, .35, 0); }
      if (id !== "sink" && id !== "hit" && id !== "storm1") S.ship.rotation.z = 0;
      if (id !== "voyage" && id !== "sink") S.ship.rotation.y = 0;
    }
    if (set === "deck") {
      S.dwater.flow(t); S.chart.visible = id === "chart"; S.clock2.visible = id === "pend" || id === "wave" || id === "stopped";
      const stopped = t > Wt.stopped - .05, wave = id === "wave" || id === "stopped";
      S.clock2.swing(id === "stopped" ? -.42 : wave ? Math.sin(L * 2.6) * .55 - .2 : Math.sin(t * Math.PI) * .28); S.clock2.face.set(stopped ? 3.2 : 3 + t / 60);
      S.clock2.rotation.z = wave ? -.08 : 0;
      const capOn = id === "had no" || sh.shot.at === "had no" || id === "sun" || id === "wave";
      S.cap.show(id !== "pend" && id !== "stopped" && id !== "chart" && id !== "lost");
      if (sh.shot.at === "had no") S.cap.at(-.4, 0, 0).pose({ face: t > Wt.idea ? "worried" : "neutral", arms: ["hold", "scratch"], prop: { kind: "scroll", hand: "L" }, blink: b(t, 4), look: -.4 });
      else if (id === "sun") S.cap.at(0, 0, 0).pose({ face: t > Wt.where2 ? "joy" : "determined", arms: [t > Wt.home - .1 ? "hold" : "hang", t > Wt.where2 - .2 ? "up" : "hang"], prop: { kind: "watch", hand: "L", r: 50 }, blink: b(t, 4), look: -.5, lookY: -1 });
      else if (id === "wave") S.cap.at(-2.0, 0, .4).pose({ face: "scared", arms: ["up", "up"], blink: 0 });
      live(S.cap, 4, wave ? { sway: 6 } : {});
      S.sail.forEach((c, i) => {
        const on = id === "lost" || id === "wave"; c.show(on);
        if (id === "lost") c.at([-1.5, 1.5, 0][i], 0, [-.6, -.8, -1.6][i]).pose({ face: t > Wt.seconds - .1 ? (i === 2 ? "awe" : "joy") : "neutral", arms: i === 0 ? ["hang", "up"] : t > Wt.seconds ? ["up", "up"] : ["hang", "hip"], prop: i === 0 ? { kind: "watch", hand: "R", r: 60 } : null, blink: b(t, 20 + i), jump: i && t > Wt.seconds ? Math.max(0, Math.sin((t - Wt.seconds) * 8)) * .6 : 0 });
        else c.at([2.0, -.6, 1.2][i], 0, [-.2, -1.0, .8][i]).pose({ face: "scared", arms: ["up", "up"], blink: 0 });
        live(c, 20 + i, id === "wave" ? { sway: 6 } : {});
      });
      S.xMark.scale.setScalar(CS.ease.back(seg(t, Wt.exactly - .05, Wt.exactly + .25)) + .001);
    }
    if (set === "shop") {
      S.gears.forEach((g, i) => g.rotation.y = t * (i % 2 ? -.8 : .6));
      S.arms[0].rotation.z = Math.sin(t * 2.4) * .35; S.arms[1].rotation.z = -Math.sin(t * 2.4) * .35;
      S.board.write("EARTH = 360°\n÷ 24 hours\n= 15° an hour", id === "board" ? seg(t, Wt.heres + .05, Wt.earth - .05) : 1);
      const old = id === "old" || id === "watch" || id === "board";
      S.h3.show(!old); S.h3old.show(old);
      if (id === "hammer") S.h3.at(-.4, 0, -1.6).pose({ face: "determined", arms: ["hang", Math.sin(t * 10) > 0 ? "up" : "point"], blink: b(t, 5), look: .3 });
      else if (id === "h1") S.h3.at(-.75, 0, -.2).pose({ face: t > Wt.huge ? "awe" : "proud", arms: ["hip", "point"], blink: b(t, 5), look: .8, lookY: -.6 });
      if (id === "old") S.h3old.at(-.4, 0, -1.6).pose({ face: t > Wt.nineteen ? "sleepy" : "bored", arms: ["cheek", "hang"], blink: b(t, 6) });
      else if (id === "watch") { const has = t > Wt.fit - .1; S.h3old.at(0, 0, 0).pose({ face: has ? "joy" : "determined", arms: ["hang", [120, 30]], prop: has ? { kind: "watch", hand: "R", r: 66, hours: 10.1 } : null, blink: b(t, 6) }); }
      else if (id === "board") S.h3old.at(-1.25, 0, -2.0).pose({ face: "determined", arms: ["hang", "point"], prop: { kind: "chalk", hand: "R" }, blink: b(t, 6), look: -.6 });
      live(S.h3, 5); live(S.h3old, 6);
    }
    if (set === "space") {
      S.globe.spin.rotation.y = id === "globe" ? -seg(t, Wt.earth, Wt.hour + .4) * Math.PI / 12 * 2.2 : t * .05;
      S.sclock.visible = id === "globe"; S.sclock.set(12 + seg(t, Wt.fifteen - .1, Wt.hour + .3));
      S.sat.visible = id === "sat"; S.sat.rotation.y = Math.sin(t * .6) * .25; S.satClock.set(10 + t * .5);
      S.globe.position.y = id === "sat" ? -3.5 : 0;
    }
    if (set === "throne") {
      const up = t > Wt.step - .3;
      S.king.at(0, 0, -2.1).pose({ face: t > Wt.king + .2 ? "determined" : "stern", arms: [up ? "hip" : "hold", up ? "point" : "hold"], blink: b(t, 8), talk: up ? Math.round(t * 7) % 2 : 0 }); live(S.king, 8);
      S.guards.forEach((c, i) => { c.at(i ? 1.9 : -1.9, 0, -1.4).pose({ face: "stern", arms: ["salute", "hang"], blink: b(t, 30 + i) }); live(c, 30 + i); });
    }
    if (set === "city") { S.girl.at(0, 0, 0).pose({ face: t > Wt.phone ? "happy" : "neutral", arms: ["hang", "hold"], prop: { kind: "phone", hand: "R" }, blink: b(t, 9), lookY: .6, look: .3 }); live(S.girl, 9); }
    for (const f of S.fx) f.update(t);
  },

  sound(A, T) {
    const S = this; S.init(T); const Wt = S.W;
    A.music({ bpm: 104, key: 57, sections: [{ at: 0, style: "whimsy" }, { at: Wt.y1707 - .2, style: "tense" }, { at: Wt.so - .1, style: "sneak" }, { at: Wt.every - .1, style: "whimsy" },
      { at: Wt.built - .1, style: "folk" }, { at: Wt.then - .1, style: "stop" }, { at: Wt.fit - .05, style: "whimsy" }, { at: Wt.heres - .1, style: "drone" },
      { at: Wt.still - .2, style: "sneak" }, { at: Wt.king - .1, style: "march" }, { at: Wt.today - .1, style: "drone" }, { at: Wt.gps - .1, style: "stop" }] });
    S.plan.cutSounds(A, ["whoosh", "swish"], .42);
    A.sfx("ting", Wt.clock1 + .05, .7); A.sfx("tick", Wt.clock1 + .4, .4, { n: 3, gap: .3 });
    A.sfx("waves", Wt.eighty - .2, .5, { dur: 3 }); A.sfx("wind", T.w("back then") - .1, .45, { dur: 3.2 });
    A.sfx("boing", Wt.idea + .02, .5);
    A.sfx("wind", Wt.y1707 - .2, .6, { dur: 5.6 }); A.sfx("waves", Wt.y1707, .6, { dur: 5.5 });
    S.strikes.forEach(s => A.sfx("boom", s, .5));
    A.sfx("crash", Wt.hit + .1, .9); A.sfx("creak", Wt.over + .2, .5); A.sfx("splash", Wt.over + 1.0, .6);
    A.sfx("step", Wt.so + .2, .4); A.sfx("step", Wt.so + .55, .4); A.sfx("step", Wt.so + .9, .4);
    A.sfx("laugh", Wt.laughed + .05, .55, { dur: 3.2 }); A.sfx("laugh2", Wt.rolling - .1, .45, { dur: 1.6 });
    A.sfx("tick", Wt.every, .45, { n: 7, gap: .32 }); A.sfx("splash", Wt.wave + .1, .8); A.sfx("creak", Wt.wave + .4, .5);
    A.sfx("thunk", Wt.stopped + .05, .7); A.sfx("slidedown", Wt.stopped + .25, .35);
    for (let i = 0; i < 6; i++) A.sfx("hit", Wt.built + .1 + i * .31, .25);
    A.sfx("boing", Wt.huge, .4); A.sfx("drumroll", Wt.then + .1, .4, { dur: 1.3 }); A.sfx("magic", Wt.fit - .05, .7); A.sfx("ting", Wt.hand, .5);
    A.sfx("ooh", Wt.seconds - .1, .6, { dur: 1.7 }); A.sfx("cheer", Wt.seconds + .5, .35, { dur: 1.2 });
    A.sfx("paper", Wt.heres + .1, .4); for (let i = 0; i < 8; i++) A.sfx("click", Wt.heres + .3 + i * .14, .25);
    A.sfx("slideup", Wt.earth, .3); A.sfx("tick", Wt.fifteen, .4, { n: 4, gap: .28 });
    A.sfx("pop", Wt.exactly, .7); A.sfx("ting", Wt.exactly + .05, .5);
    A.sfx("murmur", Wt.still - .1, .5, { dur: 2.2 }); A.sfx("slidedown", Wt.pay + .05, .45);
    A.sfx("horn", Wt.step - .05, .55); A.sfx("bell", Wt.step + .15, .25);
    A.sfx("click", Wt.phone, .5); A.sfx("pop", Wt.phone + .25, .4);
    A.sfx("tick", Wt.very, .45, { n: 3, gap: .3 }); A.sfx("sting", Wt.clocks, .7);
  },
};
