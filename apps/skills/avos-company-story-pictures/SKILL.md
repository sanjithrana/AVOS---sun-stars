---
name: avos-company-story-pictures
description: How Company Story makes its pictures: the picture model draws only a people-free backdrop, and the chosen 2D character is placed on it in code in poses that follow the narration.
---

# Pictures for Company Story

The character is never drawn by the picture model. That is why he is always exactly the one you picked.

1. **One ready-made 2D character per video** (executive, director or young businessman). Each is cut out of your model sheet into transparent poses (`characters/<id>/<pose>.png`): front, three-quarter, welcoming, thinking, pointing/presenting, tablet or laptop, on the phone, cheering.
2. **The picture model draws only the backdrop**, with no people, using this prompt. The left third is kept almost empty and the upper right stays calm, for the character and the paper cards.
3. **The character is stood on the backdrop in code** (`compose.py`): about 78% of the frame tall, in the left third, with a soft ground shadow. The three gestures the script writes for the scene ("hand on chin, thinking", "pointing toward the right", "fists raised, cheering"…) choose three different poses; the first is the scene picture.
4. **Motion**: drawn poses cut and crossfade between the three poses with a slow push-in (free); AI video (Seedance) animates the scene picture with the prompt below.
5. **Cards** (title, counting numbers, caption, VS banner) are drawn by code on top and never cover the character.

## Backdrop prompt (sent to the picture model)
A wide 16:9 2D cartoon backdrop with NO people in it. SCENE: <the place, from the research>. Props and symbols that tell the moment: <objects and symbols in the backdrop>. STORY: <company>: <the story moment>. STYLE: hand-drawn 2D cartoon illustration in a satirical business-documentary style, an isometric toy-town of company buildings, factories and skyscrapers on rolling green land with winding roads and a blue river, distant blue mountains, a warm orange or soft blue sky with a pale sun, flat colours with soft shading and a light paper texture, clean dark outlines. COMPOSITION (16:9): the buildings and props of the scene sit in the CENTRE and right-centre. The LEFT third of the frame is kept almost empty (flat grass, road or floor, low detail), because a character is placed there afterwards. The upper-right corner and a band along the bottom stay calm sky or ground (paper cards are placed there later). NO people at all. No text, no letters, no numbers, no signs, no logos, no labels, no watermarks anywhere in the picture (text is added later).

Negative prompt: people, person, character, face, crowd, silhouette, aerial view of a tiny map, text, letters, numbers, logo, watermark, caption, blurry, photo-realistic, 3D render

## Backdrop prompt for the rivalry scene (adds the rival company's towers, still no people)
COMPOSITION (16:9): this company's buildings in the centre-left and the rival company's taller towers on the right, a river or road between them with a clear gap; the far LEFT third stays almost empty (flat ground, low detail) because a character is placed there afterwards; the top band stays calm. NO people at all.

## AI video prompt (Seedance, from the scene picture)
2D cartoon shot made from this exact picture. Keep the character standing in the left third of the frame with exactly the same face, hair, suit and proportions for the whole shot; he never leaves the frame and his face stays visible. He acts with clear, expressive cartoon animation: <gesture 1>, then <gesture 2>, then <gesture 3>; his mouth moves as if he is telling the story. <symbols>. Small cars move on the road and the river flows in the backdrop; the camera does a slow push in. No text, no new characters, no style change, no cuts.

## Gestures the writer may use
arms open wide, welcoming · pointing toward the right · presenting with one hand out · hand on chin, thinking · holding a tablet or paper · on the phone · fists raised, cheering · standing proud, hands on hips

## Full model sheet as reference
For AI video, the model gets two reference images: the composed scene picture and the character's **full model sheet** (all angles, expressions and poses, `characters/<id>/sheet.jpg`). The prompt tells it to follow the sheet exactly for face, hair, glasses/mustache, suit, tie, shoes and proportions in every frame, including turns and expression changes.
