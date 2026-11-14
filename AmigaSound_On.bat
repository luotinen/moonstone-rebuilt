@echo off
rem Switches the sound effects to the Amiga version's (D65, D66). Setup.bat builds them (AmigaSound_Setup.bat does it
rem again): from the images of your three Amiga Moonstone disks in the amiga folder, or without them from the DOS
rem game's samples and the substitute sounds.
rem The music stays as it is (D82): AdLib, or General MIDI, which then plays with the effects from one SoundFont (made
rem here the first time, _music\amiga\amiga_gm.sf2; needs Python, as Setup.bat). MT-32 music cannot play with them
rem (both need the MIDI device): it becomes AdLib. AmigaSound_Off.bat switches the DOS effects back.
cd /d "%~dp0"
if not exist "_music\amiga\amiga.sf2" (
  echo The Amiga sound effects are not set up yet - run AmigaSound_Setup.bat first. Nothing was changed.
  pause
  exit /b 1
)
call tools\set_sound.bat keep amiga
if errorlevel 1 goto failed
if defined SOUND_NOTE echo %SOUND_NOTE%
echo %SOUND_SAID%.
pause
exit /b 0
:failed
echo %SOUND_NOTE%
pause
exit /b 1
