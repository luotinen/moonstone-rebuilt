@echo off
rem Uses the custom rules in custom_rules.ini (made from custom_rules-default.ini if missing). Restart DOSBox-X afterwards.
cd /d "%~dp0"
set "TOOLS=tools"
if not exist "tools\rules.py" set "TOOLS=..\tools"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 is needed: https://www.python.org/downloads/ - tick "Add python.exe to PATH" when installing.
  pause
  exit /b 1
)
%PY% -I "%TOOLS%\rules.py" "%~dp0."
pause
