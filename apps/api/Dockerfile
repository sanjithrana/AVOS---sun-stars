# Build context is the repo root (see docker-compose.yml) so the image
# contains every package the API imports - packages/, tool_gateway/ and
# agentic_core/ used to exist only as dev volume mounts, so the image
# could not run on its own.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# ffmpeg renders the final video (clips + narration + captions) and the
# free "motion" clips; DejaVu is the caption font.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY packages ./packages
COPY tool_gateway ./tool_gateway
COPY agentic_core ./agentic_core
COPY comfyui_workflows ./comfyui_workflows
COPY api/src ./src
COPY api/alembic ./alembic
COPY api/alembic.ini ./alembic.ini
COPY api/tests ./tests
COPY api/pytest.ini ./pytest.ini

RUN mkdir -p /data/assets

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
