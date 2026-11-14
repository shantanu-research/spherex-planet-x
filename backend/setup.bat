@echo off
setlocal
cd /d "%~dp0"
rem Keep everything (virtual env + pip download cache) inside this folder.
set "PIP_CACHE_DIR=%~dp0.pipcache"
if not exist notes mkdir notes

set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo Python 3.10 or newer not found. Install it from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

echo === 1/4 Creating virtual environment in .venv ===
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
call .venv\Scripts\activate.bat

echo === 2/4 Installing packages (first time takes a few minutes) ===
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto fail

echo === 3/4 Running offline tests ===
python -m pytest -q
if errorlevel 1 goto fail

echo === 4/4 Checking the real NASA archive (IRSA) ===
python scripts\check_irsa.py > notes\check_irsa_output.txt 2>&1
type notes\check_irsa_output.txt

echo.
echo Setup finished. Double-click run_server.bat to start the API.
pause
exit /b 0

:fail
echo.
echo Something failed above. Take a screenshot of this window.
pause
exit /b 1
