@echo off
rem Sets up the Amiga intro and ending music from your own Amiga Moonstone disk 1 (amiga\Moonstone_Disk1.adf).
rem Needs Python 3 and VLC (VLC turns the Amiga modules into WAV files once; the game itself does not need it).
rem Setup.bat does this too when the disk image is there; use this after adding the image later.
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
> AMIGA.FLG echo amiga
echo Amiga intro and ending music: on (AmigaMusic_Off.bat turns it off)
pause
