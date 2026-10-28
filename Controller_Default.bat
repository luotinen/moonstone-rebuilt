@echo off
rem Game controllers: DOSBox-X's own bindings (no D-pad) and one controller for both players (joysticktype = auto).
rem An existing moonstone.map is kept as moonstone.map.bak.
cd /d "%~dp0"
if exist moonstone.map move /y moonstone.map moonstone.map.bak >nul || goto failed
powershell -NoProfile -Command "(Get-Content moonstone-dosbox-x.conf) -replace '^joysticktype = .*', 'joysticktype = auto' | Set-Content moonstone-dosbox-x.conf"
if errorlevel 1 goto failed
echo Game controllers: DOSBox-X's own bindings
pause
exit /b 0
:failed
echo Copying failed: the game may be half switched. Close DOSBox-X and run %~nx0 again.
pause
exit /b 1
