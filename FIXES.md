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
| K4 | **Object slots can run out in fights.** Fight objects such as fire, hit effects and daggers need a game slot (20) and an animation slot (only 10). When the animation slots were full, the game slot stayed taken for the rest of the fight (1000:3E89); with all 20 gone, the next object was written past the table (DS:76B0) over the fight's own data. The dragon fight makes the most objects when it is fought from a distance (fire breath, daggers). Now a slot that gets no animation slot is freed at once (1000:3EA5, 10 bytes). In play the limit is hard to reach (a dragon fight with fire and three daggers in the air uses about 8–9 of the 10 animation slots), so this is probably **not** the cause of the dragon fight hang reported on GOG; that cause is still open. | tested: no side effects |
| K5 | **Game Over on the Q key.** On the map, pressing Q ended the game at once, without asking, during any knight's turn (1000:A594). Q is next to W and A, the second player's movement keys, so the game could end by accident: the likely cause of the "unexpected Game Over" reports on GOG. Game Over is now on Esc (one byte). | tested |
| K11 | **Math and Mythral read their stat tables wrongly.** Math's stat gift (1000:B9C2) stepped through its table at the wrong stride: endurance never rose, half of the gifts went to a value that is not a stat, and Math's line was read from a wrong address (in play: a black screen and a long list of the game's internal data). Mythral (1000:BBD5) showed the wrong message, or none, for the stat it changed. Now Math gives strength, endurance or constitution (5/16, 5/16, 6/16) with the matching line, and Mythral the right message. Losing to the Guardian now always costs a real stat point, as intended. | tested |
| K16 | **Duel looting.** When a knight took the loser's weapon and that weapon was the Sword of Sharpness, only the weapon moved, not the sword itself: the loser kept the sword and was armed with it again, so both knights had one (1000:CE91). The sword now moves with the weapon (the code is in `SAVEHOOK.COM`, which needs to be running, as for D6). Also: when a computer knight won and took better armour, the hit points that moved with it came from its own old armour (1000:0B8E); a computer knight's stat raise after a duel win had no limit of 5, unlike a player's (1000:04B0); and when the loser had no lives left, the sword was set as the dead loser's weapon (1000:0C4B, harmless). | from the code |
| K17 | **Ratmen disease removed.** A ratman's bite infected the knight, and every four days (each moon phase) a diseased knight lost a life point until healed, without any message in the game, so players took it for a bug. The bite no longer infects, and a knight infected in an older save no longer loses lives to it. | from the code |
| K18 | **The dragon's hoard grows with its victories, not from game to game.** Every new game (and every practice) added four magic items and gold to the hoard without clearing it, so after several games in one session it held far more than one game's worth. Now it is rolled anew at each new game, and every time the dragon beats a knight it gets one more magic item at a 50 % chance and 0-9 gold (1000:1DBE, 0D23; needs `SAVEHOOK.COM`). `custom_rules.ini`: `dragon_hoard = reset` (no growth) or `keep` (the original, for speedruns). | emulator-tested; not yet tried in play |
| K19 | **Moonstone names.** The item screen called the half-moon Moonstones "New moon Moonstone" and the new-moon one "Half Moonstone" (the names now follow the phase in which each doubles the damage; 1000:C709, C747, C766). | emulator-tested; not yet tried in play |
| K10 | **Sound effects at the wrong speed.** The DOS sound files are the Amiga version's samples byte for byte, but every DOS file says 16,129 Hz, while the Amiga plays them at 4,766–22,655 Hz. Most sounds played too fast and too high (the dragon's grunts 3.4 times). Each file now carries its real rate (one byte per file; the rates come from the Amiga version, no Amiga files needed). | tested |

## Improvements

| ID | Improvement | Status |
|---|---|---|
| K9 | **Skip the intro and the ending** with Enter, Space or Esc. The intro reads the keyboard through its own interrupt handler, and the skip checks that handler's key table. | tested |
| D1 | **DOSBox-X with save states:** 100 slots, F11+S and F11+L. | tested |
| D2 | **Better music:** Roland MT-32, General MIDI (SoundFont) or the original AdLib music. The General MIDI modules are the game's Roland modules with the instruments remapped. | MT-32 and GM need your own ROMs / SoundFont |
| D4 | **Settings confirmed by the GOG community:** speed 4,000 cycles (the GOG default 9,000 is about twice too fast), joystick drift fix (`timed = false`), OpenGL output against the black screen. | speed tested |
| D5 | **The intro works in DOSBox-X.** The packed original programs (EXEPACK) fail when DOSBox-X loads them into the lowest 64 KB, so the intro was skipped and the original MAIN.EXE stayed black. Rebuilt uses unpacked programs in both modes; in original mode (`Fixes_Off.bat`) they are only unpacked, otherwise unchanged. (An earlier version started the packed originals with `LOADFIX`, which left too little memory: *Insufficient memory*.) | tested |
| D6 | **Automatic save before every fight** (slots 96–100). DOSBox-X cannot be told to save from inside DOS, but it can save on a timer into separate slots per running program. When a fight starts (1000:0307), the helper `SAVEHOOK.COM` renames the game to `PREFIGHT` for about a second. | tested |
| D7 | **Automatic save at the start of every human turn** on the map (slots 91–95, `PRETURN`; 1000:A63F). Computer knights' turns are not saved. | tested |
| D9 | **Player 2 moves with W, A, S, D.** The original used W (up), A (left), D (right) and X (down); down is now S (1000:8403). Fire stays on Tab. | tested |
| D11 | **Practice against the computer.** With 1 player chosen in the menu, *Practice* now pits your knight against a computer-played Black Knight; with 2 or more it is two players, as before (1000:011D, 1000:2031; needs `SAVEHOOK.COM`). | emulator-tested; not yet tried in play |
| D12 | **Practice for 3 or 4 players, in two teams** (a prototype). With 3 players chosen and one game controller, or 4 and two, *Practice* adds a knight for each controller: team 1 is player 1 (arrows) with controller 1, team 2 is player 2 (W A S D) with controller 2. The keyboard and the controllers are then four separate inputs, teammates do not hurt each other, and the fight ends when one team has no knight left. Without the controllers it is the normal two-player practice. Needs `SAVEHOOK.COM`. | tested (3 and 4 players, two PS3 controllers) |
| D13 | **Four colours in that practice.** Every knight has its own colour: player 1 blue, player 2 green, controller 1 orange, controller 2 red; with custom rules, the colours of `[Knight1]`, `[Knight3]`, `[Knight2]` and `[Knight4]`. The game uses only 32 of the screen's 256 palette entries; the controller knights' armour is moved to entries 32-37 as they are drawn, and those entries follow the game's fades. No extra sprite files or memory. Needs `SAVEHOOK.COM`. | tested |
| D14 | **Practice choices.** 3-4 players: Enter on *Practice* = everyone against everyone (four colours, until one knight is left), Space = two teams in their keyboard players' colours. 1 player: the keys 1-9 start a practice against the monsters of one lair through the game's own lair fight (several at once, as in the lair), 0 the Black Knight (1000:1299, 0142; needs `SAVEHOOK.COM`). | emulator-tested (menu keys, set-up calls, end rules); play test pending |
| D15 | **Co-op practice against monsters.** With 2-4 players chosen, the practice keys put all the knights on the same side: they cannot hurt each other (thrown daggers neither), each has its own colour, every monster goes for the knight nearest to it, and the fight goes on while a knight stands and monsters are left (1000:2DF7, 2FC3; needs `SAVEHOOK.COM`). | emulator-tested (set-up, targeting, end rule, hits, colours); play test pending |
| D16 | **Practice settings.** In `custom_rules.ini`, `[Practice]`: each key 1-0 starts the monsters of a chosen lair (1-24; type and number as the lair has them) or the Black Knight; whether knights' blows and daggers hurt other knights; whether monsters go for the nearest knight or the first, and when they switch. With 2-4 knights against monsters, their strength and hit points are added up when the game counts the monsters (custom rules; needs `SAVEHOOK.COM`, no change in `MAIN.EXE`). | emulator-tested; play test pending |
| D8 | **Amiga intro and ending music** (optional, from your own Amiga disk 1). | intro tested, ending not yet |
| D10 | **Custom rules in `custom_rules.ini`** (optional; `Custom_rules_on.bat`): starting values per knight and for the computer knights, a death mode per knight (permadeath, reincarnation, respawn, invulnerable), the computer knights' extras, and global rules: ratmen disease, curse chances, gold and life caps, home village healing (also in any village), full hit points with the E key, days per moon phase, experience per ability point, weapon and move damage (including the dagger throw), armour and ring hit points, the most daggers, Math's frog days, irritation and what he gives, lair treasure and the magic item chances, the treasure gold, Mythral's chances, every monster's hit points and damage (also the Guardian and the dragon), all shop, healer and High Temple prices (the price texts follow), each knight's colour (also any `#RGB` colour) and home village, the save mode (automatic and manual saves, only automatic, only manual, none) an option against savescumming, and selling daggers, weapons and armour back to the merchant. Constants are byte patches; the rest is new code in `SAVEHOOK.COM` (int 63h). | from the code, emulator-tested; not yet tried in play |
| – | **No mouse.** The game does not use one; a mouse captured by a click disturbed the intro's keyboard handling. | tested |
| – | **Picture:** 4:3 aspect ratio and crisp pixels (`glshader = sharp`). | – |

## Kept as in the original

(The ratmen disease is not kept: see K17.)

The random number bias, plate armour giving no movement bonus, the lack of wandering monsters, the lack of hit
invulnerability, the computer knights' extra experience, and winning past the 150 gold limit in the dice game.

## Known bugs not fixed yet

| ID | Bug |
|---|---|
| – | Dragon fight hang about a second into the fight (reported on GOG many times). Not reproduced here; K4 is probably not its cause. |
| K3 | Crash after killing the Guardian or the dragon (reported). Not reproduced. |
| K6 | The dragon can be kept in a constant hit state with the upward thrust. |
| K7 | Crash when two trolls do an overhead chop at the same time (reported on the Amiga). |
| K8 | The end summary names *constitution* twice and leaves out endurance (reported). |
| – | After a lair fight, a dragon attack later in the same turn changes that lair's monster count. |
| – | Possibly: when all human knights are dead but a living computer knight plays between them, the game may not end (to be checked). |
