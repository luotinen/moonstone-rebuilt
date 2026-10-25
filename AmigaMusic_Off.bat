@echo off
rem Turns off the Amiga intro and ending music and puts back the DOS intro and ending tunes.
cd /d "%~dp0"
if exist AMIGA.FLG del AMIGA.FLG
set "SET=adlib"
findstr /c:"= mt32" music.conf >nul && set "SET=mt32"
findstr /c:"= fluidsynth" music.conf >nul && set "SET=gm"
copy /y "_music\%SET%\DISKA\*.BIN" DISKA >nul
echo Amiga intro and ending music: off (DOS music: %SET%)
pause
