@echo off
rem Game controllers: DOSBox-X's own bindings (no D-pad) and one controller for both players (joysticktype = auto).
rem An existing moonstone.map is kept as moonstone.map.bak.
cd /d "%~dp0"
if exist moonstone.map move /y moonstone.map moonstone.map.bak >nul
powershell -NoProfile -Command "(Get-Content moonstone-dosbox-x.conf) -replace '^joysticktype = .*', 'joysticktype = auto' | Set-Content moonstone-dosbox-x.conf"
echo Game controllers: DOSBox-X's own bindings
pause
