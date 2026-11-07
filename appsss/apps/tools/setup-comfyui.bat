@echo off
rem AVOS: install ComfyUI (Windows portable; it also runs on a CPU-only PC) next to AVOS and point it at AVOS's models folder.
rem   Run from anywhere:  D:\star\apps\tools\setup-comfyui.bat
rem   ComfyUI goes to D:\star\ComfyUI_windows_portable (set COMFY_HOME to choose another folder).
rem   Models are read from D:\star\apps\models (set AVOS_MODELS to use another folder).
setlocal EnableExtensions
set "APPS=%~dp0.."
for %%I in ("%APPS%") do set "APPS=%%~fI"
if "%COMFY_HOME%"=="" for %%I in ("%APPS%\..") do set "COMFY_HOME=%%~fI"
if "%AVOS_MODELS%"=="" set "AVOS_MODELS=%APPS%\models"
set "PORTABLE=%COMFY_HOME%\ComfyUI_windows_portable"
set "URL=https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z"

echo.
echo  ComfyUI folder : %PORTABLE%
echo  AVOS models    : %AVOS_MODELS%
echo.

if exist "%PORTABLE%\run_nvidia_gpu.bat" (
  echo [1/3] ComfyUI is already installed: updating it
  if exist "%PORTABLE%\update\update_comfyui.bat" (
    pushd "%PORTABLE%\update" & call update_comfyui.bat < nul & popd
  )
  goto paths
)

echo [1/3] Downloading ComfyUI portable (about 2 GB) ...
curl.exe -L --fail -o "%COMFY_HOME%\ComfyUI_portable.7z" "%URL%"
if errorlevel 1 (
  echo Download failed. Get it by hand from https://github.com/comfyanonymous/ComfyUI/releases
  echo and extract it into %COMFY_HOME%, then run this script again.
  exit /b 1
)
echo       Extracting ...
tar -xf "%COMFY_HOME%\ComfyUI_portable.7z" -C "%COMFY_HOME%" 2> nul
if not exist "%PORTABLE%\run_nvidia_gpu.bat" (
  if exist "%ProgramFiles%\7-Zip\7z.exe" (
    "%ProgramFiles%\7-Zip\7z.exe" x -y -o"%COMFY_HOME%" "%COMFY_HOME%\ComfyUI_portable.7z" > nul
  )
)
if not exist "%PORTABLE%\run_nvidia_gpu.bat" (
  echo Couldn't extract the .7z. Install 7-Zip from https://www.7-zip.org and run this script again.
  exit /b 1
)
del "%COMFY_HOME%\ComfyUI_portable.7z"

:paths
echo [2/3] Pointing ComfyUI at the AVOS models folder
if not exist "%AVOS_MODELS%" mkdir "%AVOS_MODELS%"
set "BASE=%AVOS_MODELS:\=/%"
(
  echo # Written by AVOS apps\tools\setup-comfyui.bat: ComfyUI also reads the models AVOS downloads.
  echo avos:
  echo     base_path: %BASE%
  echo     checkpoints: checkpoints
  echo     diffusion_models: ^|
  echo         diffusion_models
  echo         unet
  echo     text_encoders: ^|
  echo         text_encoders
  echo         clip
  echo     clip_vision: clip_vision
  echo     vae: vae
  echo     loras: loras
  echo     latent_upscale_models: latent_upscale_models
  echo     upscale_models: upscale_models
  echo     audio_encoders: audio_encoders
  echo     model_patches: model_patches
  echo     hunyuanvideo_foley: hunyuanvideo_foley
) > "%PORTABLE%\ComfyUI\extra_model_paths.yaml"
for %%D in (checkpoints diffusion_models text_encoders vae loras latent_upscale_models upscale_models audio_encoders) do (
  if not exist "%AVOS_MODELS%\%%D" mkdir "%AVOS_MODELS%\%%D"
)

echo [3/3] Done.
echo.
echo  NVIDIA graphics card:  %APPS%\tools\start-gpu.bat   (ComfyUI + the AVOS GPU worker in Docker)
echo  No NVIDIA card (Intel / AMD CPU):  %APPS%\tools\start-cpu.bat   (ComfyUI --cpu + the worker; slow but free)
endlocal
