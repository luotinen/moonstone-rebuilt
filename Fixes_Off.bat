@echo off
rem Switches the game to: original (unpacked but unchanged programs, original sound files).
cd /d "%~dp0"
for %%F in ("_fixes\original\MAIN.EXE" "_fixes\original\INTR.EXE" "_fixes\original\DISKA\CAMEL4") do if not exist %%F goto missing
if not exist "_fixes\original\SAMPLES\*" goto missing
copy /y "_fixes\original\MAIN.EXE" MAIN.EXE >nul || goto failed
copy /y "_fixes\original\INTR.EXE" INTR.EXE >nul || goto failed
copy /y "_fixes\original\SAMPLES\*" SAMPLES >nul || goto failed
copy /y "_fixes\original\DISKA\CAMEL4" DISKA >nul || goto failed
> ORIGINAL.FLG echo original
echo Game: original (unpacked but unchanged programs, original sound files)
pause
exit /b 0
:missing
echo The original programs are missing (_fixes\original). Run Setup.bat first. Nothing was changed.
pause
exit /b 1
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
