@echo off
rem Restores custom_rules.ini to the default state (a copy of custom_rules-default.ini).
cd /d "%~dp0"
copy /y custom_rules-default.ini custom_rules.ini >nul
echo custom_rules.ini has the default values again. Custom_rules_on.bat uses them.
pause
