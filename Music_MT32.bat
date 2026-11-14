@echo off
rem Switches the music to: Roland MT-32 (needs the MT-32 ROMs in mt32-roms). The Amiga sound effects cannot play with
rem it (both need the MIDI device): if they are on, the sound effects become the DOS game's (D82).
cd /d "%~dp0"
if not exist "mt32-roms\*CONTROL.ROM" (
  echo The music was not changed: it needs the MT-32 ROMs in mt32-roms.
  pause
  exit /b 1
)
call tools\set_sound.bat mt32 keep
if errorlevel 1 goto failed
if defined SOUND_NOTE echo %SOUND_NOTE%
echo %SOUND_SAID%.
pause
exit /b 0
:failed
echo %SOUND_NOTE%
pause
exit /b 1
