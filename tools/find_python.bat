@echo off
rem Sets PY to a Python 3.8 or newer that really starts: the py launcher first, then python on the PATH.
rem errorlevel 1 (with a message) if there is none. Used by Setup.bat, Custom_rules_on.bat and AmigaMusic_Setup.bat.
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>nul && set "PY=python"
if defined PY exit /b 0
echo Python 3.8 or newer is needed: https://www.python.org/downloads/ - tick "Add python.exe to PATH" when installing.
exit /b 1
