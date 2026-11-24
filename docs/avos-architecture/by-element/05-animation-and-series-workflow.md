# Animation workflow and Series
Reference animation (ReelMimic port): reference video + brief/song/lyrics -> AI crew analyses, plans storyboard, builds 2D animation with skia renderer, reviews, assembles MP4.
Stages: new, analyzing, styling, planning, plan_review, producing, critiquing, revising, needs_input, done, error.
Engines: hyperframes, painted-animation, crayon-storybook, pixel-art, paper-cutout, whiteboard, anime-cel. AI finish via Wan VACE / Wan 2.2 Animate / SCAIL-2 / LTX-2.3.
Series gates: Characters (sheet+voice; only approved can speak) -> Outline (parts 1 min, then 3) -> Part script -> Rendered part (redo shots).
Per part: voices (Chatterbox/IndicF5 clone), keyframes (Qwen-Image-Edit), lip-sync (InfiniteTalk) or action (Wan 2.2/LTX-2.3), foley (HunyuanVideo-Foley), music (your theme/ACE-Step), subtitles. Not yet tested on real GPUs.
