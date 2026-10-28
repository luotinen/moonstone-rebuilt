@echo off
rem Uses the default rules: the normal game. custom_rules.ini is kept; Custom_rules_on.bat uses it again.
cd /d "%~dp0"
if not exist "_fixes\fixed\MAIN.EXE" goto missing
if not exist "_fixes\fixed\SAVEHOOK.COM" goto missing
if not exist ORIGINAL.FLG copy /y "_fixes\fixed\MAIN.EXE" MAIN.EXE >nul || goto failed
rem The save mode lives in SAVEHOOK.COM: put the normal one back (Custom_rules_on.bat keeps a copy here)
copy /y "_fixes\fixed\SAVEHOOK.COM" SAVEHOOK.COM >nul || goto failed
if exist CUSTOM_RULES.FLG del CUSTOM_RULES.FLG
echo Default rules (the normal game). Restart DOSBox-X for this to take effect.
pause
exit /b 0
:missing
echo The fixed files are missing (_fixes\fixed). Run Setup.bat first. Nothing was changed.
pause
exit /b 1
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
