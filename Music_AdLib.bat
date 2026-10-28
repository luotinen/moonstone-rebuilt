@echo off
rem Switches the music to: AdLib (original) (needs no extra files).
cd /d "%~dp0"
for %%F in ("_music\adlib\DISKA\*.BIN" "_music\adlib\DISKB\*.BIN" "_music\profiles\adlib.conf") do if not exist %%F goto missing
copy /y "_music\adlib\DISKA\*.BIN" DISKA >nul || goto failed
copy /y "_music\adlib\DISKB\*.BIN" DISKB >nul || goto failed
copy /y "_music\profiles\adlib.conf" music.conf >nul || goto failed
echo Music: AdLib (original)
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
