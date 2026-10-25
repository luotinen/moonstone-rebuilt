@echo off
rem Sets the game's sound card to: Sound Blaster (music AdLib/MIDI, effects as samples).
cd /d "%~dp0"
> MOON.CFG echo SOUND=SOUNDBLASTER
>> MOON.CFG echo YGUARD=11234
echo Sound card: Sound Blaster (music AdLib/MIDI, effects as samples)
pause
