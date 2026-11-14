@echo off
cd /d "%~dp0"
if not exist notes mkdir notes
echo Building same-wavelength weekly time-lapses for R Draconis (all 6 detectors).
echo First run fetches ~2,500 image headers (46 KB each): about 10-20 minutes.
echo Progress: notes\timelapse_log.txt
call .venv\Scripts\activate.bat
python -u scripts\precache_timelapse.py %* > notes\timelapse_log.txt 2>&1
type notes\timelapse_log.txt
echo.
echo Finished. You can close this window.
pause
