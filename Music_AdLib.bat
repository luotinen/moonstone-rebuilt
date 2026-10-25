@echo off
rem Switches the music to: AdLib (original) (needs no extra files).
cd /d "%~dp0"
copy /y "_music\adlib\DISKA\*.BIN" DISKA >nul
copy /y "_music\adlib\DISKB\*.BIN" DISKB >nul
copy /y "_music\profiles\adlib.conf" music.conf >nul
echo Music: AdLib (original)
pause
