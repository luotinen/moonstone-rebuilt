@echo off
rem Switches the game to: fixed (unpacked programs and the fixes in FIXES.md).
rem tools\mode.py makes the change as one (all files and flags, or none) under the installation's lock.
cd /d "%~dp0"
set "TOOLS=tools"
if not exist "tools\mode.py" set "TOOLS=..\tools"
call "%TOOLS%\find_python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)
%PY% -I "%TOOLS%\mode.py" fixed "%~dp0."
if errorlevel 1 (
  pause
  exit /b 1
)
pause
exit /b 0
