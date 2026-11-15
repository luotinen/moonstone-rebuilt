@echo off
rem Turns on the Amiga intro and ending music (set up first with Setup.bat or AmigaMusic_Setup.bat). It plays inside
rem DOSBox-X from the SoundFont of the Amiga sound effects, in step with the pictures (D87): with AdLib or General MIDI
rem music and with the DOS or the Amiga sound effects. MT-32 music keeps its own Roland intro and ending tunes.
cd /d "%~dp0"
if not exist "_music\amiga\font\ATUNE1.BIN" goto notset
if not exist "_music\amiga\amiga.tunes" goto notset
> AMIGA.FLG echo amiga
call tools\set_sound.bat keep keep
if errorlevel 1 goto failed
if defined SOUND_NOTE echo %SOUND_NOTE%
echo %SOUND_SAID%.
if not defined SOUND_AMIGA_TUNES echo The Amiga intro and ending music is on; it plays with AdLib or General MIDI music, not with MT-32 music or in original mode (Fixes_Off.bat).
pause
exit /b 0
:notset
echo Amiga music is not set up yet - run AmigaMusic_Setup.bat first.
pause
exit /b 1
:failed
echo %SOUND_NOTE%
pause
exit /b 1
