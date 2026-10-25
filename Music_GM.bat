@echo off
rem Switches the music to: General MIDI (SoundFont) (needs a SoundFont at soundfonts\default.sf2).
cd /d "%~dp0"
copy /y "_music\gm\DISKA\*.BIN" DISKA >nul
copy /y "_music\gm\DISKB\*.BIN" DISKB >nul
copy /y "_music\profiles\gm.conf" music.conf >nul
echo Music: General MIDI (SoundFont)
pause
