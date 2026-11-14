@echo off
rem Switches the music to: AdLib (original) (needs no extra files). The sound effects stay as they are (D82).
cd /d "%~dp0"
call tools\set_sound.bat adlib keep
if errorlevel 1 goto failed
if defined SOUND_NOTE echo %SOUND_NOTE%
echo %SOUND_SAID%.
pause
exit /b 0
:failed
echo %SOUND_NOTE%
pause
exit /b 1
