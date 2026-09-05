@echo off
cd /d "%~dp0"
if not exist skillswap.db (
  echo First run: creating SkillSwap database...
)
python app.py
pause
