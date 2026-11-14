@echo off
cd /d "%~dp0"
if not exist notes mkdir notes
echo Pre-caching the 5 demo targets from NASA's archive.
echo This takes about 20-30 minutes. Keep the PC awake and online.
echo Progress is written to notes\precache_log.txt
call .venv\Scripts\activate.bat
python -u scripts\precache.py > notes\precache_log.txt 2>&1
type notes\precache_log.txt
echo.
echo Finished. You can close this window.
pause
