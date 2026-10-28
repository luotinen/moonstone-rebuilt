@echo off
rem Switches the music to: General MIDI (SoundFont) (needs a SoundFont at soundfonts\default.sf2).
cd /d "%~dp0"
if not exist "soundfonts\default.sf2" (
  echo The music was not changed: it needs a SoundFont at soundfonts\default.sf2.
  pause
  exit /b 1
)
for %%F in ("_music\gm\DISKA\*.BIN" "_music\gm\DISKB\*.BIN" "_music\profiles\gm.conf") do if not exist %%F goto missing
copy /y "_music\gm\DISKA\*.BIN" DISKA >nul || goto failed
copy /y "_music\gm\DISKB\*.BIN" DISKB >nul || goto failed
copy /y "_music\profiles\gm.conf" music.conf >nul || goto failed
echo Music: General MIDI (SoundFont)
pause
exit /b 0
:missing
echo The General MIDI (SoundFont) music files are missing (_music). Run Setup.bat first. Nothing was changed.
pause
exit /b 1
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
