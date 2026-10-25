# Moonstone Rebuilt – fixes and improvements

Addresses are in the unpacked programs: `1000:xxxx` is code in `MAIN.EXE`, `DS:xxxx` its data, `INTR` the intro
program. Every patch checks the original bytes first, so it is never applied to a different file.
*Tested* means confirmed in play; *from the code* means worked out from the program and checked in an emulator, but
not yet confirmed in play.

## Bug fixes in the original game

| ID | Fix | Status |
|---|---|---|
| K1 | **A sound that never played.** The sample name table lists `cheap2b` twice (DS:8721, entries 8 and 9); the list is alphabetical, so entry 8 is meant to be `cheap1b`, and CHEAP1B never played. | from the code |
| K2 | **Ratmen and the moon.** The manual says ratmen grow stronger as the moon waxes, but the game made them strong at full moon and strongest at new moon (1000:23FE). Now: strongest at full moon (12 hit points, bite 8, claw 5), strong at ¾ moon (7 / 6 / 3), normal otherwise. | from the code |
| K4 | **Object slots run out in fights** (the dragon fight hang reported on GOG). Fight objects such as fire, hit effects and daggers need a game slot (20) and an animation slot (only 10). When the animation slots were full, the game slot stayed taken for the rest of the fight (1000:3E89); with all 20 gone, the next object was written past the table (DS:76B0) over the fight's own data. The dragon fight makes the most objects when it is fought from a distance (fire breath, daggers). Now a slot that gets no animation slot is freed at once (1000:3EA5, 10 bytes). Probably also the cause of K3, the crash after killing the Guardian or the dragon. | from the code |
| K10 | **Sound effects at the wrong speed.** The DOS sound files are the Amiga version's samples byte for byte, but every DOS file says 16,129 Hz, while the Amiga plays them at 4,766–22,655 Hz. Most sounds played too fast and too high (the dragon's grunts 3.4 times). Each file now carries its real rate (one byte per file; the rates come from the Amiga version, no Amiga files needed). | from the code |

## Improvements

| ID | Improvement | Status |
|---|---|---|
| K9 | **Skip the intro and the ending** with Enter, Space or Esc. The intro reads the keyboard through its own interrupt handler, and the skip checks that handler's key table. | tested |
| D1 | **DOSBox-X with save states:** 100 slots, F11+S and F11+L. | tested |
| D2 | **Better music:** Roland MT-32, General MIDI (SoundFont) or the original AdLib music. The General MIDI modules are the game's Roland modules with the instruments remapped. | MT-32 and GM need your own ROMs / SoundFont |
| D4 | **Settings confirmed by the GOG community:** speed 4,000 cycles (the GOG default 9,000 is about twice too fast), joystick drift fix (`timed = false`), OpenGL output against the black screen. | speed tested |
| D5 | **The intro works in DOSBox-X.** The packed original programs (EXEPACK) fail when DOSBox-X loads them into the lowest 64 KB, so the intro was skipped and the original MAIN.EXE stayed black. Rebuilt uses unpacked programs; the original programs (`Fixes_Off.bat`) are started with `LOADFIX`. | tested |
| D6 | **Automatic save before every fight** (slots 96–100). DOSBox-X cannot be told to save from inside DOS, but it can save on a timer into separate slots per running program. When a fight starts (1000:0307), the helper `SAVEHOOK.COM` renames the game to `PREFIGHT` for about a second. | tested |
| D7 | **Automatic save at the start of every human turn** on the map (slots 91–95, `PRETURN`; 1000:A63F). Computer knights' turns are not saved. | tested |
| D8 | **Amiga intro and ending music** (optional, from your own Amiga disk 1). | intro tested, ending not yet |
| – | **No mouse.** The game does not use one; a mouse captured by a click disturbed the intro's keyboard handling. | tested |
| – | **Picture:** 4:3 aspect ratio and crisp pixels (`glshader = sharp`). | – |

## Kept as in the original

The random number bias, plate armour giving no movement bonus, the lack of wandering monsters, the lack of hit
invulnerability, the computer knights' extra experience, and winning past the 150 gold limit in the dice game.

## Known bugs not fixed yet

| ID | Bug |
|---|---|
| K3 | Crash after killing the Guardian or the dragon (reported). Probably the same cause as K4; to be confirmed. |
| K5 | Unexpected *Game Over* in mid-game (reported). |
| K6 | The dragon can be kept in a constant hit state with the upward thrust. |
| K7 | Crash when two trolls do an overhead chop at the same time (reported on the Amiga). |
| K8 | The end summary names *constitution* twice and leaves out endurance (reported). |
| – | After a lair fight, a dragon attack later in the same turn changes that lair's monster count. |
