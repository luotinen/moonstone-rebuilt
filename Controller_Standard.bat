@echo off
rem Game controllers: Xbox and most other pads (D-pad on)
rem Copies controllers\Standard.map to moonstone.map (DOSBox-X's key and controller bindings) and sets one controller per
rem player (joysticktype = 2axis). An existing moonstone.map is kept as moonstone.map.bak.
cd /d "%~dp0"
if not exist "controllers\Standard.map" (
  echo controllers\Standard.map is missing. Nothing was changed.
  pause
  exit /b 1
)
if exist moonstone.map copy /y moonstone.map moonstone.map.bak >nul || goto failed
copy /y "controllers\Standard.map" moonstone.map >nul || goto failed
powershell -NoProfile -Command "(Get-Content moonstone-dosbox-x.conf) -replace '^joysticktype = .*', 'joysticktype = 2axis' | Set-Content moonstone-dosbox-x.conf"
if errorlevel 1 goto failed
echo Game controllers: Xbox and most other pads (D-pad on)
echo Connect the controllers before Start.bat.
pause
exit /b 0
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
