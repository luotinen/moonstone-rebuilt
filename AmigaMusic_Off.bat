@echo off
rem Turns off the Amiga intro and ending music and puts back the DOS intro and ending tunes of the music in use.
cd /d "%~dp0"
if exist AMIGA.FLG del AMIGA.FLG
call tools\set_sound.bat keep keep
if errorlevel 1 goto failed
copy /y "_music\%SOUND_TUNES%\DISKA\*.BIN" DISKA >nul || goto copyfailed
if exist AMIGATUN.FLG del AMIGATUN.FLG
echo Amiga intro and ending music: off. %SOUND_SAID%.
pause
exit /b 0
:failed
echo %SOUND_NOTE%
pause
exit /b 1
:copyfailed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
