@echo off
rem Switches the music to: Roland MT-32 (needs the MT-32 ROMs in mt32-roms).
cd /d "%~dp0"
if not exist "mt32-roms\*CONTROL.ROM" (
  echo The music was not changed: it needs the MT-32 ROMs in mt32-roms.
  pause
  exit /b 1
)
for %%F in ("_music\mt32\DISKA\*.BIN" "_music\mt32\DISKB\*.BIN" "_music\profiles\mt32.conf") do if not exist %%F goto missing
copy /y "_music\mt32\DISKA\*.BIN" DISKA >nul || goto failed
copy /y "_music\mt32\DISKB\*.BIN" DISKB >nul || goto failed
copy /y "_music\profiles\mt32.conf" music.conf >nul || goto failed
echo Music: Roland MT-32
pause
exit /b 0
:missing
echo The Roland MT-32 music files are missing (_music). Run Setup.bat first. Nothing was changed.
pause
exit /b 1
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
