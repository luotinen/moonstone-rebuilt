@echo off
rem Uses the custom rules in custom_rules.ini (made from custom_rules-default.ini if missing). Restart DOSBox-X afterwards.
cd /d "%~dp0"
set "TOOLS=tools"
if not exist "tools\rules.py" set "TOOLS=..\tools"
call "%TOOLS%\find_python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)
%PY% -I "%TOOLS%\rules.py" "%~dp0."
if errorlevel 1 (
  pause
  exit /b 1
)
pause
