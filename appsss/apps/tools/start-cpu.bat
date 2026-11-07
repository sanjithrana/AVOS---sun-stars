@echo off
rem AVOS on a PC WITHOUT an NVIDIA graphics card (Intel / AMD CPU): ComfyUI in CPU mode + the AVOS worker.
rem   D:\star\apps\tools\start-cpu.bat
rem Runs Z-Image Turbo, LTX-2.3 and the other ComfyUI models on the processor. Slow (minutes per picture, much longer
rem per clip) but free and offline. Pictures and clips are drawn at most 512 px and 5 s; AVOS scales them up.
rem Models bigger than your RAM page from the SSD: make the Windows page file big first (tools\set-pagefile.ps1).
rem Then on the AVOS GPU page add the worker:  http://host.docker.internal:8700
setlocal EnableExtensions
set "APPS=%~dp0.."
for %%I in ("%APPS%") do set "APPS=%%~fI"
if "%COMFY_HOME%"=="" for %%I in ("%APPS%\..") do set "COMFY_HOME=%%~fI"
set "PORTABLE=%COMFY_HOME%\ComfyUI_windows_portable"
set "PY=%PORTABLE%\python_embeded\python.exe"
if "%WORKER_CPU_MAX_SIDE%"=="" set "WORKER_CPU_MAX_SIDE=512"
if "%WORKER_CPU_MAX_SECONDS%"=="" set "WORKER_CPU_MAX_SECONDS=5"

if not exist "%PY%" (
  echo ComfyUI isn't installed yet: run %APPS%\tools\setup-comfyui.bat first.
  exit /b 1
)

echo [1/3] Starting ComfyUI on the CPU (a new window; keep it open) ...
start "ComfyUI (CPU)" /D "%PORTABLE%" cmd /k ".\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --cpu --listen 127.0.0.1 --port 8188"

echo [2/3] Installing the AVOS worker into ComfyUI's Python (first time only) ...
"%PY%" -m pip install --disable-pip-version-check -q -r "%APPS%\gpu_worker\requirements.txt"
if errorlevel 1 (
  echo pip failed: check your internet connection and run this again.
  exit /b 1
)

echo [3/3] Starting the AVOS worker in CPU mode (a new window; keep it open) ...
set "WORKER_DEVICE=cpu"
set "WORKER_ADAPTERS=comfyui"
set "COMFYUI_URL=http://127.0.0.1:8188"
set "COMFYUI_WORKFLOW_DIR=%APPS%\comfyui_workflows"
set "WORKER_MODELS_DIR=%APPS%\models"
set "WORKER_DATA=%APPS%\gpu_worker\data"
start "AVOS worker (CPU)" /D "%APPS%\gpu_worker" cmd /k ""%PY%" -s "%APPS%\gpu_worker\run_worker.py""

echo.
echo  ComfyUI    : http://127.0.0.1:8188
echo  AVOS worker: http://localhost:8700/health
echo  In AVOS, GPU page: add  http://host.docker.internal:8700   (Windows may ask once: allow Private networks)
echo  Models: Z-Image Turbo (bf16 + the fp8 text encoder) and LTX-2.3 (fp8 + the fp4 Gemma text encoder) use the least memory.
endlocal
