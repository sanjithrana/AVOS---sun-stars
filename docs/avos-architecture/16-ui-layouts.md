# 16. UI layouts (what each screen looks like)

Wireframes of the desktop app (`apps/desktop`). Boxes are the real components. Look: dark violet, glass panels,
pill buttons, glow. Explainer layouts are drawn from the actual components; the other studios are drawn from their
page lists in [07](07-frontend.md).

## App shell (every page)
```
+-----------------------------------------------------------------------------+
| AVOS   Facts  Animations  Explainer  Stickman  Models  GPU  Settings   [theme]|
+-----------------------------------------------------------------------------+
|                                                                             |
|                         page content (below)                                |
|                                                                             |
+-----------------------------------------------------------------------------+
```

## Explainer: new video (INPUT)  `/explainer`  (Composer)
```
+--------------------- What should the video explain? ------------------------+
| One idea, or a full brief ...                                               |
| [ An idea | An article link ]   <- tabs                                     |
| +-------------------------------------------------------------------------+ |
| | textarea: idea or full brief (title, duration, scenes)      (explainer-brief)|
| +-------------------------------------------------------------------------+ |
|   article tab instead:  [ https://... url ] [Preview]  -> title/words/excerpt|
|                         ( Summarize )( Explain simply )( As a story )( Key points )|
| (example chips)                                                             |
|                                                                             |
| Length: (30s)(60s)(...)            Shape: (9:16)(16:9)(1:1)                 |
| Look:  [style cards: Auto, ...]                                             |
| Voice: [language] [voice list + preview]                                    |
| [x] Check the facts first  (Wikipedia, source links)                        |
| Autopilot: how should it run?   (pick one to start)                         |
|   ( ) Ask me at each step      ( ) Fully automatic                          |
| Models: [ Automatic | pinned model | Local only ]                             |
| Estimated cost: free / about $x-$y                                          |
|                                         [ Create video ]                    |
+-----------------------------------------------------------------------------+
| Your videos:  [card][card][card] ...                                        |
+-----------------------------------------------------------------------------+
```

## Explainer: project page (GENERATION box)  `/explainer/[id]`  (ProjectView)
```
<- All videos                      [Copy master prompt] [Delete]
Title                                                    (explainer-title)
+-- Progress -----------------------------------------------------------------+
| [Plan] [Design] [Board] [Shoot] [Finish]     live: "what the studio is doing"|
+-----------------------------------------------------------------------------+
| error/stopped box:  This step did not finish.        [ Continue ]           |
+-- Gate box (when waiting) --------------------------------------------------+
| [ Approve and draw the characters ]  [Save edits]                           |
| Change it: [ note.................. ] [ Redo plan ]                         |
+-----------------------------------------------------------------------------+
| Research panel: facts + source links                                        |
| Brief toggle | Palette swatches                                             |
+-- Characters and backgrounds (assets-panel) --------------------------------+
| +--------+ +--------+ +--------+ +--------+                                 |
| | poster | | char 1 | | char 2 | | props  |   each: picture, name, look,    |
| |  (key  | | sheet  | | sheet  | | / set  |   kind, [Redraw]                |
| | visual)| |        | |        | |        |                                 |
| +--------+ +--------+ +--------+ +--------+                                 |
+-- Storyboard -------- view tabs: [Scenes | Timeline | ...] -----------------+
| Production storyboard (contact sheet, download)                             |
| Shot cards (below)                                                          |
+-- Direct this ---------------------------------------------------------------+
| Tell the studio what to change. [ note ] [ Story ] ...                      |
+-----------------------------------------------------------------------------+
```

## Explainer: one shot card (ShotCard)
```
+-----------------------------------------------------------------+
| #3  [speaker chip]   [shot picture / clip]                      |
|-----------------------------------------------------------------|
| Voice says : [ text........................ ]                   |
| We see     : [ text........................ ]                   |
| Made with  : [ Automatic | AI video | Blender | Picture+move ]  |
| Angle and framing | Wants | Performance | Ends on | Keeps the same|
| Lighting | Mood | Audio                                         |
| Picture prompt : [ ........ ]   Motion prompt : [ ........ ]    |
| [Redraw picture] [Make clip again]  note [....]  (thumb up)(thumb down)|
+-----------------------------------------------------------------+
```

## Explainer: finished video (OUTPUT)
```
+-- Your video is ready ------------------------------------------------------+
| [ video player: final.mp4 ]                [Download] [final.srt]           |
| Rate: (thumb up)(thumb down)  -> teaches the prompt library                 |
| [Copy master prompt]  (paste into Seedance, Kling or Veo)                   |
+-----------------------------------------------------------------------------+
```

## Explainer: Skills page  `/explainer/skills`
```
Skills                       [ Improve now ]
+------------+ +------------+ +------------+
| Research   | | Script and | | Characters |  each card: name, stage,
| ready  [on]| | story  ... | | ...        |  what it does, readiness,
| 12 ok      | |            | |            |  success count, switch (optional ones)
+------------+ +------------+ +------------+   + prompt text editor per key
```

## Facts: new video and project  `/facts`, `/project/[id]`, `/studio/[id]`
```
/facts      [ topic | duration | aspect | style | text/picture/video model | Priority ]  [Create]
            project list (ProjectCard)
/project    [ PipelineSteps ]  [ Script approval ]  [ FinalVideoCard ]  [ jobs / warnings ]
/studio     +-- Storyboard (ShotCards) --+-- right panel w-96 ----------+
            | Timeline                   | ShotInfo / Edit shot          |
            | Generation monitor         | QA dashboard / Decision trace |
            +----------------------------+-------------------------------+
```

## Animations (reference), Series
```
/animations        [ upload reference video ] [ brief ] [ Create ]
/animations/[id]   Chat with director | Storyboard | Checks | Video | AI finish
/animations/series/[id]   Characters (sheet + voice, Approve/Redo) -> Outline -> Part script -> Rendered part, Models panel
```

## Stickman  `/stickman`, `/stickman/[id]`
```
New:     [ event or interest ] [ aspect ] [ tone ] [ auto ]  -> eight topic ideas, you pick one
Project: stages topics > brief > story > roster > clips > refs > scenes > animate > voice > finish
         reference sheets (Approve) | clip cards C01..C06 (scene, video, narration) | package.md | final.mp4
```

## GPU and Models and Settings
```
/gpu       totals | worker cards (VRAM bar, temp, loaded models, queue, Test/Send workflows/Turn off/Remove)
           add worker | generation limits | Ask the router | runs table | learned performance
/models    model cards: readiness, backend, licence, VRAM per precision, Download panel
/settings  API keys | GPU server (URL, Test, Run models on) | Your models | Workflow uploads
```
