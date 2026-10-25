@echo off
rem Switches the music to: Roland MT-32 (needs the MT-32 ROMs in mt32-roms).
cd /d "%~dp0"
copy /y "_music\mt32\DISKA\*.BIN" DISKA >nul
copy /y "_music\mt32\DISKB\*.BIN" DISKB >nul
copy /y "_music\profiles\mt32.conf" music.conf >nul
echo Music: Roland MT-32
pause
