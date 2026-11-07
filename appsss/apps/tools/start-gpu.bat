@echo off
rem AVOS: start ComfyUI (in its own window) and the AVOS GPU worker (Docker), on this PC's NVIDIA GPU.
rem   D:\star\apps\tools\start-gpu.bat
rem Then on the AVOS GPU page add the worker:  http://host.docker.internal:8700
rem Optional: set GPU_WORKER_TOKEN=... first (and the same value in AVOS Settings) to require a token.
setlocal EnableExtensions
set "APPS=%~dp0.."
for %%I in ("%APPS%") do set "APPS=%%~fI"
if "%COMFY_HOME%"=="" for %%I in ("%APPS%\..") do set "COMFY_HOME=%%~fI"
set "PORTABLE=%COMFY_HOME%\ComfyUI_windows_portable"

if not exist "%PORTABLE%\run_nvidia_gpu.bat" (
  echo ComfyUI isn't installed yet: run %APPS%\tools\setup-comfyui.bat first.
  exit /b 1
)

echo [1/2] Starting ComfyUI (a new window; keep it open) ...
rem --listen lets the worker container reach it; Windows may ask once: allow "Private networks" only.
start "ComfyUI" /D "%PORTABLE%" cmd /k ".\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 0.0.0.0 --port 8188"

echo [2/2] Starting the AVOS GPU worker (Docker) ...
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi -L > nul 2>&1
if errorlevel 1 (
  echo Docker can't see the GPU. Update the NVIDIA driver and use Docker Desktop's WSL 2 engine, then try again.
  exit /b 1
)
pushd "%APPS%\gpu_worker"
docker compose -f docker-compose.gpu.yml up -d --build
popd

echo.
echo  ComfyUI    : http://127.0.0.1:8188
echo  GPU worker : http://localhost:8700/health
echo  In AVOS, GPU page: add  http://host.docker.internal:8700
if not "%GPU_WORKER_TOKEN%"=="" echo  Token: %GPU_WORKER_TOKEN%  (the same value in AVOS Settings - API keys - GPU_WORKER_TOKEN)
endlocal
