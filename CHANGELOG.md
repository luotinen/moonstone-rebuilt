# Changelog

## Unreleased

* D10: optional custom rules in `custom_rules.ini` (`Custom_rules_on.bat`, `Custom_rules_off.bat`, `Custom_rules_reset.bat`): starting values per knight, death modes (permadeath, reincarnation, respawn, invulnerable), the computer knights' extras, and global rules such as the ratmen disease, curses, gold and life caps, home village healing (optionally in any village) and a full heal with the E key. `SAVEHOOK.COM` has a fourth handler (int 63h). Every value is checked against its bounds (listed in the file)
  before anything is changed, and the maximum hit points stay at most 999.
* Custom rules: the rules handler now uses int 63h. It used int 61h, which the game itself takes over for its sound
  drivers (1000:5887), so the rules from the previous commit would have crashed once the sound was set up.
* Custom rules: prices (shops, healer, High Temple, with the texts on screen), move and dagger damage, the most
  daggers, ring hit points, Math the Wizard's frog days and irritation, and a colour per knight. Buying armour
  now heals by the armour's configured hit points. The High Temple's text for selling a Scroll of Haste said
  16 GP but paid 18; the text now shows the real price.
* Custom rules: lair treasure, the treasure gold, the magic item chances, what Math the Wizard gives, Mythral's
  chances, and the hit points and damage of every monster, the Guardian and the dragon. Tables that the game
  could roll on forever are refused. A ring from Math now adds the configured ring hit points.
* Custom rules: any colour per knight as `#RGB`; on the map it shows as the nearest of the five named colours.
* Custom rules: a home village per knight (start, respawn, healing); `save_mode` (automatic and manual saves, only
  automatic, only manual or none) and `prevent_savescumming`. The knight sections now come right after `[Rules]`.
  `Custom_rules_off.bat` also puts the normal `SAVEHOOK.COM` back.
* D11: Practice with 1 player chosen is now against a computer-played Black Knight (2 or more: two players, as
  before).
* Game controllers: `Controller_PlayStation.bat` and `Controller_Standard.bat` set up one pad per player with the
  D-pad on (PlayStation: the stick's up and down turned round); `Controller_Default.bat` goes back.
* D16: practice settings in `custom_rules.ini` (`[Practice]`): each key's lair (its monsters and their number) or the
  Black Knight; knights' and daggers' hits on knights; how monsters pick their knight. Against monsters, thrown daggers
  no longer hit knights, and with 2-4 knights their strength and hit points are added up for the monster count.
* D15: co-op practice: with 2-4 players the practice keys put all the knights on the same side against the
  monsters; every monster goes for its nearest knight.
* D14: 3-4 player practice: Enter = everyone against everyone, Space = teams (same colour per team). 1 player:
  the keys 1-9 start a practice against the monsters of a lair, 0 the Black Knight.
* K18: the dragon's hoard no longer grows with every new game or practice in the same session; instead it gets one
  magic item at a 50 % chance and 0-9 gold for every knight the dragon beats. Custom rules: `dragon_hoard` (grows, reset, keep).
* K19: the Moonstones' names on the item screen match their moon phases (half and new moon were swapped).
* D12 (prototype): Practice with 3 or 4 players and one or two game controllers is a team fight (keyboard player 1
  + controller 1 against keyboard player 2 + controller 2); without the controllers, the normal practice.
* D13: in that practice every knight has its own colour (the controller knights use new palette entries 32-37).
* Controllers: DOSBox-X keeps key and controller bindings in `moonstone.map` in the game folder; the README shows how
  to add the D-pad and turn round an inverted axis in the mapper.
* README: how to play with game controllers (two players with `joysticktype = 2axis`, the J calibration).
* Custom rules: `merchant_selling`: the merchant buys daggers, weapons and armour for half their price; the long
  sword and padded armour come back for free.
* A clean `custom_rules.ini` comes with the release, ready to edit; `custom_rules-default.ini` is the copy that
  `Custom_rules_reset.bat` restores from.
* K16: duel loot no longer duplicates the Sword of Sharpness. A computer winner moves the right armour hit points,
  and its stat raise after a duel stops at 5 like a player's. `SAVEHOOK.COM` has a third handler (int 62h).
* GUIDE.md: a new player's guide covering the manual's topics in new text, the rules the manual leaves out, and
  the places where the manual and the game disagree.

## 0.4.0 – No ratmen disease, better music defaults

* K17: the ratmen disease is removed (it silently took a life point every four days).
* General MIDI: reverb and chorus settings recommended for GeneralUser GS; tested with GeneralUser GS 2.0.3.
* MT-32: tested with ROM version 1.07 (README gives the control ROM's SHA-1); volume lowered to 50%.
* Setup picks the best music available on a new install: MT-32 (ROMs), General MIDI (SoundFont) or AdLib.
* Setup no longer puts the AdLib tunes back when run again after GM or MT-32 was chosen.

## 0.3.0 – Game Over on Esc, player 2 on W A S D

* K5: Game Over moved from the Q key (next to the second player's W and A) to Esc.
* `Fixes_Off.bat` works again: original mode used the packed programs with `LOADFIX`, which left too little memory
  (*Insufficient memory*); it now uses the original programs only unpacked.
* README: a knight can carry at most 150 gold; the rest is lost without a warning.
* D9: player 2 moves with W, A, S, D (down was X).
* FIXES: K5, K10, K11 and D9 confirmed in play.

## 0.2.0 – Math and Mythral fix

* K11: Math the Wizard's stat gift and Mythral's messages read their tables wrongly (endurance never rose from
  Math, and his line could be a long list of garbage). Fixed.
* Docs: K4 is a safeguard, not the cure for the dragon fight hang reported on GOG.

## 0.1.0 – first public release

* Setup from the GOG DOS version (`Setup.bat`), checked by checksum; no game files included.
* Bug fixes K1, K2, K4, K10; intro and ending skip (K9).
* DOSBox-X with save states and automatic saves before every fight and every human turn (D6, D7).
* MT-32, General MIDI or AdLib music; optional Amiga intro and ending music from your own disk 1 (D8).
* Community DOSBox settings (speed, joystick, output), 4:3 picture, mouse off.
* Released under the GNU General Public License v3.0.

See FIXES.md for details and test status.
