@echo off
rem Switches the game to: fixed (unpacked EXEs, K1, K2, K4, K5, K9, K10, K11, K17, D6, D7, D9).
cd /d "%~dp0"
copy /y "_fixes\fixed\MAIN.EXE" MAIN.EXE >nul
copy /y "_fixes\fixed\INTR.EXE" INTR.EXE >nul
rem K10: the sound effects at their real sample rates
copy /y "_fixes\fixed\SAMPLES\*" SAMPLES >nul
copy /y "_fixes\fixed\DISKA\CAMEL4" DISKA >nul
if exist ORIGINAL.FLG del ORIGINAL.FLG
echo Game: fixed (unpacked EXEs, K1, K2, K4, K5, K9, K10, K11, K17, D6, D7, D9)
pause
