# Headless Blender (as the `bpy` Python module, Blender 5.0) for the AVOS
# render service. CPU rendering (Cycles) - no GPU needed. For fast GPU
# renders run server.py with your own Blender instead (see README.md).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libegl1 libglx-mesa0 libsm6 libice6 libx11-6 libxext6 libxfixes3 libxi6 \
        libxrender1 libxxf86vm1 libxkbcommon0 libvulkan1 libbsd0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir bpy==5.0.1

WORKDIR /app
COPY blender_service ./blender_service
ENV AVOS_ASSETS_DIR=/app/blender_assets \
    PYTHONUNBUFFERED=1
EXPOSE 8090
HEALTHCHECK --interval=15s --timeout=5s --retries=20 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health')"
CMD ["python", "/app/blender_service/server.py"]
