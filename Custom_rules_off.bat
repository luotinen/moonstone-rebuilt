@echo off
rem Uses the default rules: the normal game. custom_rules.ini is kept; Custom_rules_on.bat uses it again.
cd /d "%~dp0"
if not exist ORIGINAL.FLG copy /y "_fixes\fixed\MAIN.EXE" MAIN.EXE >nul
if exist CUSTOM_RULES.FLG del CUSTOM_RULES.FLG
echo Default rules (the normal game). Restart DOSBox-X for this to take effect.
pause
