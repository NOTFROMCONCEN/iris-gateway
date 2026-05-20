@echo off
echo Starting Iris AI Gateway...
cd /d "%~dp0"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
