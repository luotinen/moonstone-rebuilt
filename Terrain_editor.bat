@echo off
rem The map tool: the terrain zones, the places and lairs, and the map picture (tools\terrain_editor.py). Needs
rem Python 3 with tkinter (part of the python.org installer) and Pillow. After a change: Custom_rules_on.bat.
cd /d "%~dp0"
set "TOOLS=tools"
if not exist "tools\terrain_editor.py" set "TOOLS=..\tools"
call "%TOOLS%\find_python.bat"
if errorlevel 1 (
  pause
  exit /b 1
)
%PY% -c "import tkinter, PIL" >nul 2>nul
if errorlevel 1 (
  echo The map tool needs Pillow. Install it once with:  %PY% -m pip install pillow
  pause
  exit /b 1
)
%PY% "%TOOLS%\terrain_editor.py"
if errorlevel 1 pause
