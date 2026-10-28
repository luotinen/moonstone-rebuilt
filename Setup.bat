@echo off
rem Moonstone Rebuilt setup: builds the game in this folder from your GOG copy of Moonstone (DOS).
rem Usage: Setup.bat                         finds the GOG installation itself
rem        Setup.bat "C:\GOG Games\Moonstone"  uses that folder
cd /d "%~dp0"
call tools\find_python.bat
if errorlevel 1 goto end_failed
rem unicorn (to unpack MAIN.EXE) goes into _python here, which setup.py uses; checked as setup.py runs (-I)
%PY% -I -c "import sys; sys.path.insert(0, sys.argv[1]); import unicorn" "%~dp0_python" >nul 2>nul
if errorlevel 1 (
  echo Installing the Python package unicorn into the _python folder, needed once to unpack MAIN.EXE ...
  %PY% -m pip install --disable-pip-version-check --target "%~dp0_python" unicorn
  if errorlevel 1 (
    echo Could not install unicorn. Check the internet connection and try again.
    goto end_failed
  )
)
%PY% -I "%~dp0setup\setup.py" %1
if errorlevel 1 (
  echo Setup failed.
  goto end_failed
)
pause
exit /b 0
:end_failed
pause
exit /b 1
