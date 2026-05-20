@echo off
echo Starting OpenCode connected to Iris Gateway...
cd /d "%~dp0"
set OPENCODE_CONFIG=%~dp0opencode.json
npx opencode
