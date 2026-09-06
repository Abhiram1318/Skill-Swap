@echo off
setlocal
cd /d "%~dp0"
echo.
echo ============================================
echo       SkillSwap India - Local Server
echo ============================================
echo.
if not exist skillswap.db echo Database will be created automatically on first run.
python app.py
if errorlevel 1 (
  echo.
  echo SkillSwap could not start. Make sure Python is installed and dependencies are installed:
  echo   pip install -r requirements.txt
  echo.
)
pause
