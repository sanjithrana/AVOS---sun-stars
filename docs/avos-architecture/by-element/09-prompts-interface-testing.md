# Prompts, interface, testing
Prompts: versioned library explainer_prompts.json (director.cinema, director.story, picture.base, sheet.character...). After 6 uses, >30% bad -> fix (rules, then AI rewrite keeping placeholders); A/B; wins by 5 points. Full text: the prompt reference document.
Pages: /facts, /project/[id], /studio/[id], /animations, /animations/series, /explainer, /explainer/skills, /models, /gpu, /settings.
Tests: pytest agentic_core/tests, api/tests, animation_studio/tests, gpu_worker/tests; npx tsc --noEmit; npm run lint; npx playwright test. Mock providers; no GPU or keys needed.
