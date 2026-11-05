@echo off
setlocal
rem AVOS Animations tab: starts the Animation Studio service (ReelMimic in Python) on http://127.0.0.1:8020
rem First run creates apps\animation_studio\.venv and installs what it needs (a few minutes). Keep this window open.
cd /d "%~dp0animation_studio"

if exist ".venv\Scripts\python.exe" goto run

set "PY="
for %%V in (3.12 3.11 3.10 3.13) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python 3.10 - 3.12 is needed. Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run this again.
  pause
  exit /b 1
)
echo Creating the Python environment with %PY% ...
%PY% -m venv .venv || (echo Could not create .venv & pause & exit /b 1)

:run
if not exist ".venv\installed.txt" (
  echo Installing the animation engine's packages ^(first run only^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo Package install failed - see the messages above. & pause & exit /b 1)
  echo optional: lyric timing ^(karaoke captions^)...
  ".venv\Scripts\python.exe" -m pip install -r requirements-lyrics.txt || echo Lyric timing not installed ^(optional^) - everything else works.
  echo ok> ".venv\installed.txt"
)

where ffmpeg >nul 2>&1 || (
  echo.
  echo FFmpeg was not found. Install it ^(winget install Gyan.FFmpeg^) and open a new window,
  echo or set FFMPEG_DIR to the folder that has ffmpeg.exe.
  echo.
)

".venv\Scripts\python.exe" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=2)" >nul 2>&1 || (
  echo Ollama is not running. The local AI crew needs it: install from https://ollama.com, then run:  ollama pull qwen2.5:7b
  echo ^(You can still use the built-in crew, or a free/paid crew from AI settings in the Animations tab.^)
  echo.
)

set STUDIO_HOST=127.0.0.1
echo Animation Studio: http://127.0.0.1:8020  ^(open AVOS at http://localhost:3000 -^> Animations^)
".venv\Scripts\python.exe" -m studio
pause
