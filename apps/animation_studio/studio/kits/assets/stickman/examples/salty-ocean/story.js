/* Shot plan: "Why is the ocean salty?"  (Stickman Shorts example)
   #1 "Why is the ocean"   beach · a kid sips sea water, YUCK face, tongue out · stink lines on "salty"
   #2 "Rain falls"         mountains · a grumpy rain cloud pours on the rocks · zoom circle: salt crystals pop off on "salt"
   #3 "Rivers carry"       the camera rides down a winding river · little salt crystals float along to the sea
   #4 "Then the sun"       the sea · a smiling sun lifts droplets up into a cloud · "but the salt stays" = crystals wave bye
   #5 "Do that for"        a big MILLIONS OF YEARS card over a fast day-night blink · salt piles up
   #6 "well"               pop cut · the kid sips again · BLEGH burst · laugh
*/
window.SHORT = {
  title: "Why Is the Ocean Salty?", slug: "salty-ocean",
  script: `Why is the ocean salty? Rain falls on rocks and washes out tiny bits of salt. Rivers carry it all to the sea. Then the sun lifts the water back into clouds, but the salt stays behind. Do that for *millions* of years, and, well.`,
  tail: 1.3,
  captions: { y: 1440, size: 108, hide: [] },
  shots(T) {
    const kid = { shirt: "#ffd23a", pattern: "stripes", stripe: "#3a7bff", hat: "cap", hatColor: "#ff4f6d", s: 1.15 };
    const salt = T.w("salt"), stays = T.w("salt stays"), well = T.w("well");
    const glassHand = (fill) => ({ R: (g, x, y) => CS.glass(g, x + 10, y + 60, .75, fill, "#3fb5ef") });
    const beach = (g, s) => {
      CS.sky(g, "#48b6ff", "#e2f6ff"); CS.sun(g, 860, 300, 85, s.t, { face: "happy" }); CS.clouds(g, s.t, [[200, 360, .8], [1100, 260, .6]]);
      CS.sea(g, 900, s.t); g.beginPath(); g.moveTo(-500, 1250); g.quadraticCurveTo(540, 1150, 1600, 1260); g.lineTo(1600, 3000); g.lineTo(-500, 3000); g.closePath(); CS.fs(g, "#ffe3a1", 8);
      for (let i = 0; i < 14; i++) CS.circle(g, CS.rand(i * 5) * 1080, 1320 + CS.rand(i * 5 + 1) * 500, 6, "#f5c978", 0);
    };
    const crystalBuddy = (g, x, y, s, t, face = "happy", i = 0) => { CS.crystal(g, x, y, s, Math.sin(t * 2 + i) * .15); CS.drawFace(g, x - 2 * s, y + 2 * s, 18 * s, { face, t }); };
    return [
      { at: 0, cam: { from: [540, 1060, 1.25], to: [540, 1030, 1.36] },
        draw(g, s) {
          beach(g, s); const yk = CS.seg(s.t, .0, .3);
          CS.stick(g, 520, 1560, Object.assign({}, kid, CS.alive(s.t, 1), { face: "yuck", green: .8, arms: ["shrug", [44, 150]], hold: glassHand(.45), headTilt: -8 * yk }));
          if (s.t > T.w("salty")) CS.stinkLines(g, 520, 820, s.t);
          CS.pop(g, 720, 760, "!", CS.seg(s.t, T.w("salty"), T.w("salty") + .9));
        } },
      { at: "rain falls", cam: { from: [540, 960, 1.05], to: [560, 1000, 1.12] },
        draw(g, s) {
          const t = s.t; CS.sky(g, "#7fa9d8", "#d9ebff");
          CS.mountain(g, 300, 1300, 900, 820, "#9b8ae0"); CS.mountain(g, 820, 1300, 800, 640, "#b6a6f0");
          CS.hills(g, 1300, "#76d45f", { amp: 30 }); CS.rainDrops(g, t, [120, 520, 960, 1180], { n: 46, speed: 1100, r: 10 });
          CS.cloud(g, 540, 430, 1.6, { color: "#e8eef7", shade: "rgba(90,110,150,.35)" }); CS.drawFace(g, 540, 440, 70, { face: "angry", t });
          CS.rock(g, 380, 1330, 1.3, "#a99d93", 3); CS.rock(g, 720, 1330, 1.0, "#bdb2a8", 7);
          const zk = CS.seg(t, T.w("washes") - .2, T.w("washes") + .3);
          s.screen(g => CS.zoom(g, 560, 700, 300, zk, (g, r) => {
            g.fillStyle = "#b9aea5"; g.fillRect(-r, -r, r * 2, r * 2);
            for (let i = 0; i < 9; i++) CS.ell(g, -r + CS.rand(i) * 2 * r, -r + CS.rand(i + 3) * 2 * r, 40, 26, i, "#a3978d", 0);
            CS.rainDrops(g, t, [-r, -r, r, r], { n: 10, speed: 700, r: 16 });
            for (let i = 0; i < 7; i++) { const t0 = salt - .2 + i * .1, k = CS.seg(t, t0, t0 + 1.4); const x = -180 + i * 60, y = 80 - 260 * CS.ease.out(k) + Math.sin(t * 6 + i) * 8; crystalBuddy(g, x, y, 1.6, t, k > 0 ? "joy" : "sleepy", i); }
          }, { from: s.toScreen(400, 1270) }));
        } },
      { at: "rivers carry", tr: "whip", cam: { from: [540, 700, 1.05], to: [540, 1250, 1.05], ease: "inOut" },
        draw(g, s) {
          const t = s.t; CS.sky(g, "#5cc4ff", "#d9f4ff", -400, -400, 1880, 800);
          CS.mountain(g, 300, 600, 700, 500, "#9b8ae0"); CS.mountain(g, 800, 600, 600, 380, "#b6a6f0");
          g.fillStyle = "#7ad35f"; g.fillRect(-500, 590, 2100, 1300); CS.seg2(g, -500, 592, 1600, 592, 7);
          CS.sea(g, 1580, t);
          // the river: an S curve from the mountain to the sea
          const P = k => [540 + Math.sin(k * 7.5) * 280 * (1 - k * .3), 600 + k * 1000];
          g.lineCap = "round"; g.lineJoin = "round";
          for (const [w, c] of [[150, CS.INK], [134, "#3fb5ef"], [60, "#7fd3ff"]]) { g.beginPath(); for (let k = 0; k <= 1; k += .01) { const [x, y] = P(k); k ? g.lineTo(x, y) : g.moveTo(x, y); } g.lineWidth = w * (c === CS.INK ? 1 : 1); g.strokeStyle = c; g.stroke(); }
          for (let i = 0; i < 9; i++) { const k = ((t - s.shot.start) * .32 + i / 9) % 1, [x, y] = P(k); crystalBuddy(g, x, y - 10, 1.1, t, i % 3 ? "joy" : "wow", i); }
          for (let i = 0; i < 12; i++) { const x = CS.rand(i * 3) * 1080, y = 700 + CS.rand(i * 3 + 1) * 800; if (Math.abs(x - P((y - 600) / 1000)[0]) > 140) { g.save(); g.translate(x, y); CS.circle(g, 0, -50, 50, "#3c9e4f", 6); CS.rrect(g, -9, -10, 18, 40, 4, "#7a4a2a", 5); g.restore(); } }
        } },
      { at: "then the sun", tr: "whip", cam: { from: [540, 960, 1.0], to: [540, 940, 1.08] },
        draw(g, s) {
          const t = s.t; CS.sky(g, "#48b6ff", "#e2f6ff"); CS.sun(g, 220, 330, 100, t, { face: "joy" }); CS.cloud(g, 760, 360, 1.2 + .3 * CS.seg(t, s.shot.start, stays));
          CS.sea(g, 1080, t);
          for (let i = 0; i < 14; i++) { const k = ((t - s.shot.start) * .45 + i / 14) % 1, x = 560 + (i - 7) * 46 + Math.sin(k * 8 + i) * 24, y = CS.lerp(1100, 420, k); g.globalAlpha = 1 - k * .7; CS.drop(g, x, y, 16, 5); g.globalAlpha = 1; }
          CS.arrow(g, 420, 1050, 420, 640, 1, { color: "rgba(255,255,255,.85)", lw: 14, dash: [22, 18] });
          const sk = CS.seg(t, stays - .3, stays + .2);
          for (let i = 0; i < 5; i++) { const x = 200 + i * 170, y = 1240 + Math.sin(t * 2.5 + i) * 14; crystalBuddy(g, x, y, 1.7, t, sk > 0 ? (i % 2 ? "smug" : "happy") : "curious", i); if (sk > 0) CS.seg2(g, x + 34, y - 10, x + 64 + Math.sin(t * 14 + i) * 16, y - 60, 8); }
          if (sk > 0) CS.label(g, "bye!", 820, 1140, { size: 70, color: "#ffd23a", scale: CS.ease.back(sk), rot: -.1 });
        } },
      { at: "do that for", tr: "pop", cam: { from: [540, 960, 1.0], to: [540, 960, 1.06] },
        draw(g, s) {
          const t = s.t, k = CS.seg(t, s.shot.start, well), dn = .5 + .5 * Math.sin(t * 7);
          CS.sky(g, CS.mix("#48b6ff", "#1b2350", dn), CS.mix("#e2f6ff", "#46508f", dn));
          CS.sea(g, 1080, t * 3, { color: CS.mix("#2fa8e8", "#bfe6f7", k * .6) });
          for (let i = 0; i < Math.round(6 + k * 40); i++) crystalBuddy(g, 60 + CS.rand(i * 3) * 960, 1180 + CS.rand(i * 3 + 1) * 360 - k * 40, 1.1, t, "happy", i);
          CS.label(g, "MILLIONS", 540, 640, { size: 150, color: "#ffd23a", scale: CS.ease.back(CS.seg(t, s.shot.start, s.shot.start + .4)), rot: -.05 });
          CS.label(g, "of years", 540, 800, { size: 84, color: "#fff", scale: CS.ease.back(CS.seg(t, s.shot.start + .2, s.shot.start + .6)), rot: -.05 });
        } },
      { at: "well", tr: "pop", lead: .25, cam: { from: [540, 1060, 1.42], to: [540, 1040, 1.5] }, shake: [[well + .25, .5, 28]],
        draw(g, s) {
          beach(g, s); const t = s.t, b = t > well + .2;
          CS.stick(g, 520, 1560, Object.assign({}, kid, CS.alive(t, 5), { face: b ? "yuck" : "curious", green: b ? 1 : 0, arms: ["shrug", [44, 150]], hold: glassHand(.4), lean: b ? -8 : 0 }));
          if (b) { CS.stinkLines(g, 520, 820, t); CS.burst(g, 700, 660, 190, CS.seg(t, well + .2, well + 1.6), { color: "#9be37d", text: "BLEGH!", size: 66 }); }
        } },
    ];
  },
  sound(A, T) {
    A.music({ style: "folk", bpm: 108, key: 60, sections: [{ at: 0, style: "folk" }, { at: T.w("do that for") - .1, style: "drone" }, { at: T.w("well") + .2, style: "stop" }], end: T.duration + 1.3 });
    CS.cutSounds(A, T, ["whoosh", "swish"], .4);
    A.sfx("waves", 0, .35, { dur: 2.4 }); A.sfx("splash", .05, .2); A.sfx("boing", T.w("salty"), .45);
    A.sfx("wind", T.w("rain falls"), .3, { dur: 3 }); A.sfx("bang", T.w("rain falls") + .1, .15);
    for (let i = 0; i < 6; i++) A.sfx("pop", T.w("salt") - .2 + i * .1, .35);
    A.sfx("splash", T.w("rivers"), .3); A.sfx("waves", T.w("rivers"), .25, { dur: 2 });
    A.sfx("magic", T.w("lifts"), .35); A.sfx("ting", T.w("salt stays"), .5);
    A.sfx("drumroll", T.w("do that for"), .35, { dur: 1.8 });
    A.sfx("splash", T.w("well") + .2, .45); A.sfx("boing", T.w("well") + .25, .55); A.sfx("laugh", T.w("well") + .6, .4, { dur: 1.2 });
  },
};
