@echo off
rem Switches the music to: General MIDI (SoundFont). It uses soundfonts\default.sf2 if you put one there, else the
rem GeneralUser GS SoundFont that comes with Moonstone Rebuilt (soundfonts\GeneralUser-GS.sf2). The sound effects stay
rem as they are (D82): with the Amiga effects on, both play from one SoundFont, made here the first time
rem (_music\amiga\amiga_gm.sf2; needs Python, as Setup.bat).
cd /d "%~dp0"
if not exist "soundfonts\default.sf2" if not exist "soundfonts\GeneralUser-GS.sf2" (
  echo The music was not changed: it needs a SoundFont, soundfonts\default.sf2 or soundfonts\GeneralUser-GS.sf2.
  pause
  exit /b 1
)
call tools\set_sound.bat gm keep
if errorlevel 1 goto failed
if defined SOUND_NOTE echo %SOUND_NOTE%
echo %SOUND_SAID%.
pause
exit /b 0
:failed
echo %SOUND_NOTE%
pause
exit /b 1
