# AVOS Animation Studio: ReelMimic's workflow in Python (analysis, AI crew, 2D renderer, review gates).
# Build context is the apps/ folder (see docker-compose.yml).
FROM python:3.11-slim

ARG WITH_LYRICS=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg fonts-noto-cjk fonts-dejavu-core libfontconfig1 libgl1 libegl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/animation_studio
COPY animation_studio/requirements.txt animation_studio/requirements-lyrics.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$WITH_LYRICS" = "1" ]; then pip install --no-cache-dir -r requirements-lyrics.txt; fi
COPY animation_studio/ ./
# The shared model catalog (same list as the Facts tab; docker-compose also mounts the live file over it).
COPY agentic_core/models/catalog.json ./catalog.json
# The agents' SKILL.md files (docker-compose also mounts the live folder, so edits apply without a rebuild)
COPY skills/ /app/skills/

ENV STUDIO_HOST=0.0.0.0 \
    STUDIO_PORT=8020 \
    STUDIO_PROJECTS=/data/projects \
    STUDIO_SECRETS=/data/secrets.json \
    STUDIO_FONT_CACHE=/data/font-cache \
    COMFYUI_WORKFLOW_DIR=/app/comfyui_workflows \
    PYTHONUNBUFFERED=1
EXPOSE 8020
HEALTHCHECK --interval=15s --timeout=5s --retries=20 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8020/api/health')"
CMD ["python", "-m", "studio"]
