---
name: avos-explainer-looks
description: The ten explainer, music-video and motion looks added to Film Style from six open-source skill repos, what was taken from each, and what was left out and why. Read before adding another outside skill.
---

# Explainer looks (Film Style entries): ten added

Run exactly like the other 66 looks: your writer plans the shots, your picture/video models draw and move them, ffmpeg joins them. No Claude, no Node, no Chrome. Cost follows the Cost setting (Free / Paid / Automatic).

| Look (Skills tab) | Source (licence) | What was taken |
|---|---|---|
| Editorial Collage Explainer | CK42BB/vox-explainer-skill (MIT) | 5-beat arc (cold open, zoom out, escalate, complication, reframe), paper-collage look, calm 2D motion |
| Watercolour Music Video | lintsinghua/paint-mv-skills (MIT) | lyrics-to-storyboard rules: small cast, one escalating idea, motivated transitions, a move on every shot |
| Hand-Drawn Stroke Story | hi-nikola/hand-drawn-explainer-video-nikola (Apache-2.0) | drawn-on-screen ink story, consistent characters, exact text kept out of pictures |
| Minimal Black Line | same repo (Apache-2.0) | sparse black line on white with one accent |

| Cutout Cartoon, Press Collage, Catalogue Grid, Vintage Engraving Explainers | bangtutorial/bang-motion (MIT) | its explainer surfaces and rules: camera never static, no slide fades, no repeated entry direction |
| Layered Motion Film | haidrrrry/claude-remotion-skill (MIT) | five layers, hero colour once per frame, spring entrances and stagger, hit-hold-build rhythm |
| Product Promo Showcase | Vincentwei1021/video-shotcraft (Apache-2.0) | one motion idea per shot, hero-card arc, riser-impact-sparkle sound, long holds |

Only style knowledge, written as short notes in our own words. No code or assets were copied.

## Not added, and why
- **anything2explainer**: PolyForm Noncommercial. Can't be used in anything you earn from.
- **The Remotion / GSAP / browser renderers** of claude-remotion-skill, video-shotcraft and bang-motion: they need Node and Chrome, which the studio container does not have. Their looks run through your picture and video models instead. video-shotcraft's real-screenshot capture is not included, so its promo look draws invented interface cards.
- **paint-mv-skills (renderer)**: needs p5 in headless Chrome and fetches upstream code that has no licence. Song-to-lyrics alignment (faster-whisper) is also not in the container.
- **vox-explainer (pipeline)**: calls Atlas Cloud (paid, about $3 to $8 per minute). AVOS's own pipeline already does script, voice, pictures, motion and assembly on the Cost setting you choose.

Keep the cost rule: say which of free to call / free to run / free to license applies to anything you add.
