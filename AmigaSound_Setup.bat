@echo off
rem Builds the Amiga version's sound effects (D65, D66). With the images of all three of your own Amiga Moonstone disks
rem in the amiga folder (any names ending in .adf) they are the Amiga's own sounds; without them they are built from
rem the DOS game's samples and the substitute sounds in the sounds folder. Needs Python 3; the package numpy is
rem installed into the _python folder here if Python does not have it. Setup.bat does the same; use this after adding
rem the disk images later. Then AmigaSound_On.bat turns the effects on.
cd /d "%~dp0"
call tools\find_python.bat
if errorlevel 1 (
  pause
  exit /b 1
)
%PY% -I -c "import sys; sys.path.insert(0, sys.argv[1]); import numpy" "%~dp0_python" >nul 2>nul
if errorlevel 1 (
  echo Installing the Python package numpy into the _python folder, needed once to build the sounds ...
  %PY% -m pip install --disable-pip-version-check --target "%~dp0_python" numpy
  if errorlevel 1 (
    echo Could not install numpy. Check the internet connection and try again.
    pause
    exit /b 1
  )
)
%PY% -I "%~dp0tools\make_amiga_audio.py" "%~dp0." "%~dp0_music\amiga\amiga.sf2" install
if errorlevel 1 (
  echo Setup failed.
  pause
  exit /b 1
)
echo The Amiga sound effects are built. AmigaSound_On.bat turns them on.
pause
