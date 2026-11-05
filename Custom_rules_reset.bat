@echo off
rem Restores custom_rules.ini to the default state (a copy of custom_rules-default.ini).
cd /d "%~dp0"
set "AGELOCK=1"
if exist PARENTAL.LCK findstr /b /c:"18 " PARENTAL.LCK >nul && set "AGELOCK="
if defined AGELOCK (
  echo This installation is locked to an age rating for good ^(PARENTAL.LCK, or no PARENTAL.LCK^): custom_rules.ini is not reset; edit it instead.
  echo Only a new installation of Moonstone Rebuilt removes the lock. Nothing was changed.
  pause
  exit /b 1
)
copy /y custom_rules-default.ini custom_rules.ini >nul || (
  echo Could not copy custom_rules-default.ini to custom_rules.ini. Nothing was changed.
  pause
  exit /b 1
)
echo custom_rules.ini has the default values again. Custom_rules_on.bat uses them.
pause
