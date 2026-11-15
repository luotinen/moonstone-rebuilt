@echo off
rem Sets up the Amiga intro and ending music from your own Amiga Moonstone disk 1 (amiga\Moonstone_Disk1.adf).
rem Needs Python 3. The two tunes play inside DOSBox-X from the SoundFont of the Amiga sound effects (D87), in step
rem with the pictures, with AdLib or General MIDI music and with the DOS or the Amiga effects (MT-32 music keeps its
rem Roland tunes); so this builds that SoundFont again, with the tunes, as AmigaSound_Setup.bat does (the package
rem numpy is installed into the _python folder if Python does not have it).
rem Setup.bat does all this too when the disk image is there; use this after adding the image later.
cd /d "%~dp0"
call tools\find_python.bat
if errorlevel 1 (
  pause
  exit /b 1
)
%PY% -I "%~dp0tools\make_amiga_music.py" "%~dp0amiga" "%~dp0."
if errorlevel 1 (
  echo Setup failed.
  pause
  exit /b 1
)
%PY% -I -c "import sys; sys.path.insert(0, sys.argv[1]); import numpy" "%~dp0_python" >nul 2>nul
if errorlevel 1 (
  echo Installing the Python package numpy into the _python folder, needed once to build the sounds ...
  %PY% -m pip install --disable-pip-version-check --target "%~dp0_python" numpy
)
%PY% -I "%~dp0tools\make_amiga_audio.py" "%~dp0." "%~dp0_music\amiga\amiga.sf2" install
if errorlevel 1 (
  echo The SoundFont could not be built, so the DOS intro and ending music plays. Check the internet connection
  echo ^(numpy^) and run this again.
  pause
  exit /b 1
)
> AMIGA.FLG echo amiga
call tools\set_sound.bat keep keep
if defined SOUND_NOTE echo %SOUND_NOTE%
echo Amiga intro and ending music: on (AmigaMusic_Off.bat turns it off). %SOUND_SAID%.
pause
