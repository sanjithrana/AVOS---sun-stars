# AVOS GPU worker. Build on the GPU machine:  docker compose -f docker-compose.gpu.yml up -d --build
# Base: PyTorch with CUDA 12.8 (RTX 30/40/50, A100, H100, L40S). For the Diffusers backend pass
#   --build-arg WITH_DIFFUSERS=1   (ComfyUI and Wan2GP run outside this container and are reached over HTTP / CLI).
FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ARG WITH_DIFFUSERS=0
ENV PYTHONUNBUFFERED=1 WORKER_PORT=8700 WORKER_DATA=/data HF_HOME=/data/hf
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-diffusers.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$WITH_DIFFUSERS" = "1" ]; then pip install --no-cache-dir -r requirements-diffusers.txt; fi
COPY worker ./worker
COPY workflows ./workflows
COPY wan2gp_templates ./wan2gp_templates
EXPOSE 8700
CMD ["python", "-m", "worker"]
