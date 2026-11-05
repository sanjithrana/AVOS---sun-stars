# Wan2GP settings templates

Put one Wan2GP settings file here for each AVOS model you want Wan2GP to run. Name it after the AVOS model id:

```
wan-2.2.json       ltx-2.3.json       wan-vace.json      infinitetalk.json
z-image.json       qwen-image.json    flux-schnell.json
```

The worker runs Wan2GP's headless batch mode with the file filled in:
`python wgp.py --process <file> --output-dir <tmp> --attention ... --quantize-transformer ...`

## Making a template

1. In Wan2GP's web UI, choose the model and the settings you want: resolution, steps, LoRAs, sliding windows and so
   on.
2. Save the settings to a JSON file, then copy it here under the AVOS model id.
3. Replace the values AVOS should control with placeholders:

| Placeholder | Becomes |
|---|---|
| `{{PROMPT}}`, `{{NEGATIVE_PROMPT}}` | The shot's prompt |
| `{{SEED}}`, `{{STEPS}}`, `{{FRAMES}}`, `{{FPS}}`, `{{WIDTH}}`, `{{HEIGHT}}` | Numbers. Use them as a field's whole value. |
| `{{RESOLUTION}}` | `"1280x720"` |
| `{{IMAGE}}`, `{{AUDIO}}`, `{{VIDEO}}` | Paths to the shot's picture, narration and driving video, written next to the settings file |

Leave everything else exactly as Wan2GP saved it, including the model type and Wan2GP's own option names. Field
names differ between Wan2GP versions, so always start from a file your own Wan2GP saved; don't write one by hand.
