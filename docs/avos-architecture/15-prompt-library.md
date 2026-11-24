# 15. Prompt library and learning

All Explainer prompts live in a versioned library (`explainer_prompts.json`, `explainer/prompts.py`), editable on the
Skills page. Keys include `director.rules`, `director.cinema`, `director.story`, `sheet.character`, `poster.tail`,
`picture.base`, `picture.recipe.presenter`, `picture.recipe.demonstration`, `motion.keep`.

Outcomes recorded per use: ok, flag, failed, redo, thumbs down, thumbs up. Approvals count as the strongest signal.

| Rule | Value |
|---|---|
| Minimum uses before judging (`MIN_USES`) | 6 |
| Bad rate that triggers a fix (`BAD_RATE`) | 0.30 |
| Margin a candidate must win by (`MARGIN`) | 0.05 |
| A/B split | hash(key + project id) % 2 |

Fixes: heuristic rules first, then an AI improver whose answer must keep every placeholder. A candidate becomes active
only if it beats the old prompt by the margin; prompts edited by hand are never overwritten; defaults update only when
the active version's source is "default". API: `/api/explainer/prompts*` (see [13](13-explainer-studio.md)).

Stickman prompts are different: composed by code from structured data so wording is never paraphrased (see
[14](14-stickman-studio.md)). Facts shots use the ShotSpec prompt compiler with a constitution check
([02](02-facts-pipeline.md), [04](04-agents-and-tool-gateway.md)).
