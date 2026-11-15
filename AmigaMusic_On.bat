@echo off
rem Turns on the Amiga intro and ending music (set up first with AmigaMusic_Setup.bat).
cd /d "%~dp0"
if not exist "_music\amiga\intro.wav" if not exist "_music\amiga\font\ATUNE1.BIN" (
  echo Amiga music is not set up yet - run AmigaMusic_Setup.bat first.
  pause
  exit /b 1
)
> AMIGA.FLG echo amiga
echo Amiga intro and ending music: on
pause
