@echo off
rem ReelMimic - build the UI if needed and start the server on http://localhost:4318
cd /d "%~dp0app"
if not exist node_modules call npm install
if not exist dist call npm run build
start "" http://localhost:4318
node server\index.ts
