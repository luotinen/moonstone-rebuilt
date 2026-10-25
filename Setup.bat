@echo off
rem Moonstone Rebuilt setup: builds the game in this folder from your GOG copy of Moonstone (DOS).
rem Usage: Setup.bat                         finds the GOG installation itself
rem        Setup.bat "C:\GOG Games\Moonstone"  uses that folder
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 is needed: https://www.python.org/downloads/ - tick "Add python.exe to PATH" when installing.
  pause
  exit /b 1
)
%PY% -c "import unicorn" >nul 2>nul
if errorlevel 1 (
  echo Installing the Python package unicorn, needed once to unpack MAIN.EXE ...
  %PY% -m pip install --user unicorn
  if errorlevel 1 (
    echo Could not install unicorn. Check the internet connection and try again.
    pause
    exit /b 1
  )
)
%PY% -I "%~dp0setup\setup.py" %1
if errorlevel 1 (
  echo Setup failed.
  pause
  exit /b 1
)
pause
