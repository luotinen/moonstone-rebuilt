@echo off
rem Switches the sound effects back to the DOS game's (Sound Blaster). The music stays as it is (D82).
cd /d "%~dp0"
call tools\set_sound.bat keep dos
if errorlevel 1 goto failed
if defined SOUND_NOTE echo %SOUND_NOTE%
echo %SOUND_SAID%.
pause
exit /b 0
:failed
echo %SOUND_NOTE%
pause
exit /b 1
