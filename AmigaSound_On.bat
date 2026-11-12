@echo off
rem Switches the sound effects to the Amiga version's (D65, D66). Setup.bat builds them (AmigaSound_Setup.bat does it
rem again): from the images of your three Amiga Moonstone disks in the amiga folder, or without them from the DOS
rem game's samples and the substitute sounds.
rem The music becomes AdLib (original): the effects use the MIDI device, so MT-32 and General MIDI music cannot
rem play at the same time. AmigaSound_Off.bat or any Music_*.bat switches the DOS effects back.
cd /d "%~dp0"
if not exist "_music\amiga\amiga.sf2" (
  echo The Amiga sound effects are not set up yet - run AmigaSound_Setup.bat first. Nothing was changed.
  pause
  exit /b 1
)
for %%F in ("_music\adlib\DISKA\*.BIN" "_music\adlib\DISKB\*.BIN" "_music\profiles\amiga.conf") do if not exist %%F goto missing
copy /y "_music\adlib\DISKA\*.BIN" DISKA >nul || goto failed
copy /y "_music\adlib\DISKB\*.BIN" DISKB >nul || goto failed
copy /y "_music\profiles\amiga.conf" music.conf >nul || goto failed
echo Sound effects: Amiga. Music: AdLib (original).
pause
exit /b 0
:missing
echo The AdLib (original) music files are missing (_music). Run Setup.bat first. Nothing was changed.
pause
exit /b 1
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
