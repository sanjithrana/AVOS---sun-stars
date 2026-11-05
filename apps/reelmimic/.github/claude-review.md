# PR review format

Review only the changes in this pull request (the diff), not the whole repo. Don't run builds or tests. Keep it short.

Report real problems only: bugs, security issues, breaking changes, performance traps. No style or formatting nits (the code is deliberately dense).
Project rules: `app/server` runs TypeScript directly on Node type stripping, so no `enum`, `namespace` or parameter properties. `.claude/skills/` holds upstream skills; only review our own engines there (pixel-art, anime-cel, paper-cutout, whiteboard, video-clone, blender-product-film).

Reply in English with exactly the layout between the TEMPLATE lines. Don't output those two lines, and add no `---` separators of your own.

TEMPLATE START
## 🤖 Claude Review

**Verdict: ✅ Ready to merge**　(or ⚠️ Merge after fixes / ❌ Don't merge)
One sentence on why.

| Check | Result |
|---|---|
| Correctness | ✅ No issues, or 🔴 n issues |
| Security | ✅ No issues, or 🔴 n issues |
| Performance | ✅ No issues, or 🟡 n issues |
| Compatibility | ✅ No breaking changes, or 🟡 what breaks |
| Tests | ✅ Covered, or ➖ No new tests |

### Must fix
1. 🔴 **`file:line`**: the problem in one sentence.
   → How to fix it (a short code snippet if it helps)

Write "None" if there's nothing.

### Nice to have
- 🟡 One-line suggestion

Leave this section out if there's nothing.

<sub>Reviewed this PR's changes only · Automated review by Claude</sub>
TEMPLATE END

Verdict rules: any 🔴 → ⚠️ Merge after fixes (or ❌ Don't merge if it breaks the app or leaks secrets). Only 🟡 or nothing → ✅ Ready to merge.
