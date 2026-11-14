@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
echo API docs will open at http://localhost:8000/docs  (Ctrl+C here to stop)
start "" http://localhost:8000/docs
uvicorn track1.api:app --reload --port 8000
pause
