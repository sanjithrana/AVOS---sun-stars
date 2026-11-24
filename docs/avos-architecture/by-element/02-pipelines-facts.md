# Pipelines: Facts video pipeline
Status: planning, researching, awaiting_approval, generating_audio, planning_shots, generating_visuals, awaiting_review (optional), rendering_video, complete (or rejected/failed).

1. Research -> 2. Script -> 3. **Script gate (you approve)** -> 4. Audio (Edge TTS, word timings, beats become shots) -> 5. Shot specs vs world state (continuity) -> 6. Physics proxy (Blender or mock) -> 7. Visuals (3 picture candidates + clip per shot, parallel) -> 8. QA committee (6 dimensions) -> 9. Repair ladder MICRO (new seeds) -> MACRO (corrected prompt) -> HUMAN_REQUIRED -> 10. Optional review gate -> 11. Final render (captions, music; H.264 crf 18).

Agents: Director, Research, Narrative, Audio, Physics, Video, QA, Repair, Learning. The tool gateway checks tool exists, role scope, JSON schema, constitution + physics gate, writes an audit row per call; budget warning 80%, stop 100%.
