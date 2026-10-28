@echo off
rem Turns off the Amiga intro and ending music and puts back the DOS intro and ending tunes.
cd /d "%~dp0"
set "SET=adlib"
findstr /c:"= mt32" music.conf >nul && set "SET=mt32"
findstr /c:"= fluidsynth" music.conf >nul && set "SET=gm"
if not exist "_music\%SET%\DISKA\*.BIN" (
  echo The DOS music files are missing ^(_music^). Run Setup.bat first. Nothing was changed.
  pause
  exit /b 1
)
copy /y "_music\%SET%\DISKA\*.BIN" DISKA >nul || goto failed
if exist AMIGA.FLG del AMIGA.FLG
echo Amiga intro and ending music: off (DOS music: %SET%)
pause
exit /b 0
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
