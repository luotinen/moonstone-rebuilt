@echo off
rem Switches the game to: fixed (unpacked programs and the fixes in FIXES.md).
cd /d "%~dp0"
if exist SETUP.FLG goto setupfail
if exist INSTALLING.FLG goto unfinished
for %%F in ("_fixes\fixed\MAIN.EXE" "_fixes\fixed\INTR.EXE" "_fixes\fixed\DISKA\CAMEL4") do if not exist %%F goto missing
if not exist "_fixes\fixed\SAMPLES\*" goto missing
set "SRC_MAIN=_fixes\fixed\MAIN.EXE"
rem D10: the custom rules from custom_rules.ini, if they are on (Custom_rules_on.bat): their MAIN.EXE and SAVEHOOK.COM
if not exist CUSTOM_RULES.FLG goto programs
if not exist "_fixes\rules\MAIN.EXE" goto norules
if not exist "_fixes\rules\SAVEHOOK.COM" goto norules
set "SRC_MAIN=_fixes\rules\MAIN.EXE"
copy /y "_fixes\rules\SAVEHOOK.COM" SAVEHOOK.COM >nul || goto failed
:programs
copy /y "%SRC_MAIN%" MAIN.EXE >nul || goto failed
copy /y "_fixes\fixed\INTR.EXE" INTR.EXE >nul || goto failed
rem K10: the sound effects at their real sample rates
copy /y "_fixes\fixed\SAMPLES\*" SAMPLES >nul || goto failed
copy /y "_fixes\fixed\DISKA\CAMEL4" DISKA >nul || goto failed
if exist ORIGINAL.FLG del ORIGINAL.FLG
if "%SRC_MAIN%"=="_fixes\rules\MAIN.EXE" echo Custom rules from custom_rules.ini: on
echo Game: fixed (unpacked programs and the fixes in FIXES.md)
pause
exit /b 0
:setupfail
echo The setup did not finish. Run Setup.bat. Nothing was changed.
pause
exit /b 1
:unfinished
echo A change of the game's programs did not finish. Close DOSBox-X and run Custom_rules_on.bat or Setup.bat. Nothing was changed.
pause
exit /b 1
:norules
echo The custom rules are on, but their programs are missing (_fixes\rules). Run Custom_rules_on.bat. Nothing was changed.
pause
exit /b 1
:missing
echo The fixed programs are missing (_fixes\fixed). Run Setup.bat first. Nothing was changed.
pause
exit /b 1
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
