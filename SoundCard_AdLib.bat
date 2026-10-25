@echo off
rem Sets the game's sound card to: AdLib (music and effects on AdLib).
cd /d "%~dp0"
> MOON.CFG echo SOUND=ADLIB
>> MOON.CFG echo YGUARD=11234
echo Sound card: AdLib (music and effects on AdLib)
pause
