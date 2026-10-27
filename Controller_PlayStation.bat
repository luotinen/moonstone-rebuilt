@echo off
rem Game controllers: PlayStation pads (stick up and down turned round, D-pad on)
rem Copies controllers\PlayStation.map to moonstone.map (DOSBox-X's key and controller bindings) and sets one controller per
rem player (joysticktype = 2axis). An existing moonstone.map is kept as moonstone.map.bak.
cd /d "%~dp0"
if exist moonstone.map copy /y moonstone.map moonstone.map.bak >nul
copy /y controllers\PlayStation.map moonstone.map >nul
powershell -NoProfile -Command "(Get-Content moonstone-dosbox-x.conf) -replace '^joysticktype = .*', 'joysticktype = 2axis' | Set-Content moonstone-dosbox-x.conf"
echo Game controllers: PlayStation pads (stick up and down turned round, D-pad on)
echo Connect the controllers before Start.bat.
pause
