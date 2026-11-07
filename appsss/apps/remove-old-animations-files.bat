@echo off
rem Removes files from the previous Animations version (the embedded ReelMimic web app), now replaced by the
rem native Animations tab + apps\animation_studio. Safe to run more than once.
cd /d "%~dp0"
if exist "desktop\components\animations" rmdir /s /q "desktop\components\animations" && echo removed desktop\components\animations
if exist "desktop\lib\api\reelmimic.ts" del /q "desktop\lib\api\reelmimic.ts" && echo removed desktop\lib\api\reelmimic.ts
if exist "start-reelmimic.bat" del /q "start-reelmimic.bat" && echo removed start-reelmimic.bat
if exist "start-reelmimic.sh" del /q "start-reelmimic.sh" && echo removed start-reelmimic.sh
echo Done.
pause
