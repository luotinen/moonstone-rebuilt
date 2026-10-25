@echo off
rem Switches the game to: original (packed EXEs, LOADFIX, original sound files).
cd /d "%~dp0"
copy /y "_fixes\original\MAIN.EXE" MAIN.EXE >nul
copy /y "_fixes\original\INTR.EXE" INTR.EXE >nul
copy /y "_fixes\original\SAMPLES\*" SAMPLES >nul
copy /y "_fixes\original\DISKA\CAMEL4" DISKA >nul
> ORIGINAL.FLG echo original
echo Game: original (packed EXEs, LOADFIX, original sound files)
pause
