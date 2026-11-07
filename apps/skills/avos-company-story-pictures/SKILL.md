---
name: avos-company-story-pictures
description: How Company Story makes its pictures: the picture model draws only a people-free backdrop, and the chosen 2D character is placed on it in code in poses that follow the narration.
---

# Pictures for Company Story

The character is never drawn by the picture model. That is why he is always exactly the one you picked.

1. **One ready-made 2D character per video** (executive, director or young businessman). Each is cut out of your model sheet into transparent poses (`characters/<id>/<pose>.png`): front, three-quarter, welcoming, thinking, pointing/presenting, tablet or laptop, on the phone, cheering.
2. **The picture model draws only the backdrop**, with no people, using this prompt. The left third is kept almost empty and the upper right stays calm, for the character and the paper cards.
3. **The character is stood on the backdrop in code** (`compose.py`): about 78% of the frame tall, in the left third, with a soft ground shadow. The three gestures the script writes for the scene ("hand on chin, thinking", "pointing toward the right", "fists raised, cheering"…) choose three different poses; the first is the scene picture.
4. **Motion**: the free *paper puppet* mode keeps the character as a paper cut-out that rises into the frame, sways on his feet and flips like a card to the next pose, over a slowly pushing paper backdrop; AI video (Seedance) animates the scene picture with the prompt below.
5. **Cards** (title, counting numbers, caption, VS banner) are drawn by code on top and never cover the character.

## Backdrop prompt (sent to the picture model)
a handcrafted PAPER-CUT diorama: every object cut from layered cardstock and kraft paper with exposed edges, visible paper fibres, real paper thickness and deep shadows between the layers, like premium editorial stop-motion on a tabletop, built as a toy-town of paper buildings, factories and towers on a tabletop, every building, hill, cloud and river a separate cut-out sheet with its own drop shadow, simple bold shapes, NOT photographic, NOT 3D, NOT realistic, NOT a painting. SCENE: <the place, from the research>. In the scene: <objects and symbols in the backdrop>. Bright even daylight, warm cream or soft blue paper sky, every shape clearly lit. Never a dark, gloomy or empty frame, even in a crisis scene. COMPOSITION (16:9 landscape): the buildings and props sit in the CENTRE and right-centre of the frame. The LEFT third is kept almost empty (flat grass, road or floor, low detail), because a character is placed there afterwards. The top band and a strip along the bottom stay calm sky or ground (paper cards are placed there later). NO people at all. Flat paper colours, visible cut edges and real paper thickness, deep shadow separation between the layers, generous empty space. No text, no letters, no numbers, no signs, no logos, no watermark anywhere.

Negative prompt: people, person, character, face, crowd, silhouette, aerial view of a tiny map, text, letters, numbers, logo, watermark, caption, blurry, photo-realistic, photograph, realistic, 3D render, painting, oil painting, gradient mesh, lens flare, cartoon, clip art, children's book illustration, flat vector, digital painting, low-detail illustration, smooth plastic 3D render, CGI, photograph, photorealistic skin, text, letters, numbers, captions, logos, labels, watermark, cluttered frame, muddy shadows

## Backdrop prompt for the rivalry scene (adds the rival company's towers, still no people)
COMPOSITION (16:9 landscape): this company's buildings in the centre-left and the rival company's taller towers on the right, a river or road between them with a clear gap; the far LEFT third stays almost empty (flat ground, low detail) because a character is placed there afterwards; the top band stays calm. NO people at all.

## AI video prompt (Seedance, from the scene picture)
A 10-second paper-craft cartoon shot made from this exact picture (keep the cut-paper look, the white paper-sticker outline round the character and the paper texture). Keep the character standing in the left third of the frame with exactly the same face, hair, suit and proportions for the whole shot; he never leaves the frame and his face stays visible. He acts with clear, expressive cartoon animation: <gesture 1>, then <gesture 2>, then <gesture 3>; his mouth moves as if he is telling the story. <symbols>. Small cars move on the road and the river flows in the backdrop; the camera does a slow push in, very slowly and with no other camera move. Everything keeps the weight of real cardstock: tiny stop-motion jitter, natural paper friction, a slight settle after every movement, soft paper collisions and the layered paper depth and shadows visible throughout, never perfectly smooth CGI motion. Cut-paper parts slide, tilt and swap rather than bending, melting or morphing, and no element changes its size, colour or place in the frame. No text, no new characters, no style change, no cuts.

## Gestures the writer may use
arms open wide, welcoming · pointing toward the right · presenting with one hand out · hand on chin, thinking · holding a tablet or paper · on the phone · fists raised, cheering · standing proud, hands on hips

## Full model sheet as reference
For AI video, the model gets two reference images: the composed scene picture and the character's **full model sheet** (all angles, expressions and poses, `characters/<id>/sheet.jpg`). The prompt tells it to follow the sheet exactly for face, hair, glasses/mustache, suit, tie, shoes and proportions in every frame, including turns and expression changes.

## The paper look (added by code, whatever the picture model draws)
- The backdrop is cropped (the free picture models stamp a watermark along the bottom), smoothed and posterised into flat paper colours, then given paper fibre, a warm tint and a vignette (`compose.paper_bg`).
- The character is a **paper sticker**: white die-cut outline and a soft drop shadow (`compose.sticker`).
- Every frame has a cream **torn-paper border** with a shadow (`compose.torn_frame`); each scene **slides in like a new sheet**.
- Cards are **taped paper notes** that drop on and settle with a small wobble (`cards.py`).

## The look itself
The paper-cut craft rules (hero rule, one background per scene, palette, museum lighting, the motion prompt) live in `avos-paper-art/SKILL.md` and are shared with Explainer and Stickman.

## Shapes and lengths

The same scene is asked for in the shape it will be used in: `16:9 landscape` keeps one side third empty for the character, who changes
side every other scene; `9:16 vertical reel` builds the scene tall and keeps the BOTTOM third empty, with the character centred there.

| Video | Scenes | Each |
|---|---|---|
| 30s | 3 | 10s |
| 60s | 6 | 10s |
| 90s | 9 | 10s |
| 180s | 15 | 12s |
| 300s | 25 | 12s |
| 600s | 40 | 15s |

A video longer than ten scenes is written act by act: each pass is given the scenes already written and carries the story on from the last
one, walking the research's milestones forward in time.

## When a model will not draw

If no picture model answers, the backdrop is drawn here in code (a paper sky, hills, a cut-paper skyline and a ground band) so the run
always finishes. If the video model fails or the fal.ai credit runs out, the rest of the run uses the free paper-puppet motion.
