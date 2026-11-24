# Music library

The final render adds a background track (ducked under the voice, faded
in and out) and a whoosh on every cut, from this folder:

```
music/
  suspense/    tracks for the "Viral 3D facts" style
  uplifting/   tracks for the "Storybook explainer" style
  sfx/         one transition sound, ideally named whoosh.mp3
```

Any .mp3 / .wav / .m4a / .ogg works. Each video gets one track from its
style's folder (the same project always gets the same track). If a mood
folder is empty, any track in `music/` itself is used; with no tracks at
all the video just has the voice.

Free, YouTube-safe sources (check each track's licence):

- Pixabay Music - pixabay.com/music (search "suspense", "dark cinematic",
  "epic"; and pixabay.com/sound-effects, search "whoosh")
- YouTube Audio Library - studio.youtube.com -> Audio library

Settings in apps/.env: `MUSIC_VOLUME=0.22` (0-1, under the voice),
`SFX_VOLUME=0.5`, `MUSIC=off` or `SFX=off` to disable. The folder is
mounted live, so new tracks are used on the next render - no restart.
