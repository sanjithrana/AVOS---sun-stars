#!/usr/bin/env bash
# Run from D:\star\apps in Git Bash AFTER extracting this zip there:  bash apply-explainer.sh
# Removes the old Facts screens (the new Explainer replaces them), then you restart the two services.
set -e
rm -rf desktop/app/facts desktop/app/project desktop/app/studio desktop/components/projects desktop/components/studio
rm -f desktop/tests/e2e/create-project.spec.ts desktop/tests/e2e/day15-checkpoint.spec.ts desktop/tests/e2e/final-video.spec.ts \
      desktop/tests/e2e/generation-monitor.spec.ts desktop/tests/e2e/qa-dashboard.spec.ts
echo "Old Facts screens removed."
echo "Now: docker compose restart animation-studio   (then refresh http://127.0.0.1:3000)"
