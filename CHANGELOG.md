# Changelog

## 0.6.0 – Team combat and new fatalities

* D17: fights with 2-4 knights are no longer slow: when a fight starts SAVEHOOK.COM raises DOSBox-X's cycles by
  `additional_cycles_per_knight` (1000) for every knight past the first, from `default_cycles` (4000): 1-4 knights
  4000-7000; after the fight the speed goes back (`custom_rules.ini`; 0 per knight turns it off). CTRL+F12 /
  CTRL+F11 now change the speed by 1000 cycles.
* K25: in co-op a monster's instant kill (troll, mudman, Balok, dragon...) kills the knight it hit. It killed the
  first knight standing instead, while the knight hit stood up again and the monster kept attacking it. A knight
  killed in co-op now stays down, and a troll no longer goes idle (often off the screen) once knight 1 is down. A knight down goes off the screen
  after its fall, so it can never be seen standing again. When a mudman pulls a knight under, the next mudman comes
  for the knights left. A knight down no longer leaves a blue body behind (its last frames were drawn into the
  background without its colour). A mudman that takes hold of one knight now pulls under, or lets go of, that same
  knight: it held one and killed another, and could leave knights frozen. Its hold now kills only the knight it
  holds (it could kill others too), and after a mudman has pulled a knight under from below the other mudmen fight
  on (they stood still for good).
* K28: the Balok's hold in co-op: it shook one knight and let go of another, so the knight it held could stay
  frozen and the fight stuck. It now lets go of the knight it holds, and that knight is shown in its own colours
  while it is shaken (it was always blue). Its bite and squeeze now kill the knight it holds: they killed the knight
  nearest it (blue, or green with red). A knight on a spear trogg's spear is shown in its own colours (it was
  always blue). The mudman's pull from below no longer kills two more knights, and a mudman coming in after it
  no longer stands still for good.
* D19: practice against Black Knights with 2-4 players: key 0 sets all the knights against as many Black Knights,
  each a copy of one of them, every one going for the nearest knight; key B does it with strong black ones
  (strength, constitution and endurance 5, the Sword of Sharpness, battle armour, daggers that never run out and
  do double damage), also with one player. Daggers are on their thrower's side: in a team practice they hurt only
  the other team, against monsters or Black Knights the knights' daggers never hurt knights, and the Black Knights'
  never hurt Black Knights. A Black Knight now always comes in with its full HP: it is made from a knight's record
  before the practice readies the knights, and a knight that fell in the last fight made a Black Knight already
  down (with 4 players only 2 came). An up or down thrust no longer throws the knight hit through the air: the
  practice borrows the trolls' set-up, which makes those blows' hit reactions the troll club's throw; they are the
  knights' own again (a small lift for the up thrust).
* D20: new deaths. A knight that has fallen to its knees (dead, before it lies down) and is hit again dies by the
  blow: an up strike splits it in two from top to bottom (one half falls towards you, the other away, both showing the blood-red inside), a down and forward thrust
  goes through the middle of the body (from the front or from behind), a back strike goes down through the helmet, an up and
  forward strike lifts it on the sword, and a dagger stays where it hit: in the helmet's face or the back of the head, or in the belly or the back. Knights, Black
  Knights, axe troggs and ratmen use them on the players' knights; the forward sweep still takes the head off.
  The new pieces are made by setup from the game's own knight pieces (KN3.OB). A knight on its knees waits about a second longer for the death blow, and in the 3-4 knight practice a knight down no longer stands up again.
* Custom rules: `death_animations = extended` (the default: the new deaths), `vanilla` (only the game's beheading)
  or `off` (no blood, as the game's gore setting off). The up and forward strike no longer has a death of its own;
  the spear trogg's blow on a knight on its knees is the thrust, the axe trogg's blow from above the split.
* A blow no longer throws a knight across the screen at the start of a session: the knockback table the game
  reads ([782Eh]) is set only when a monster strikes, and was empty before that.
* K26 now acts on the troll only: the mudman and the computer knight share the troll's step, and the mudman kept
  too far from its knight (it stayed stuck at the bottom of the screen).
* D14: a team practice shows each knight in its own colour for the first second, then in its team's colour.
* K26: the troll no longer stands swinging at the air a little off its knight's depth (as at the screen's edge with
  the troll off the screen): it steps until its swing can hit. It no longer swings from too close either (its stick
  passed the knight): it steps back first.
* K27: the dragon takes up its far fire for a knight 96 or more away (was 140), so it no longer breathes its near fire
  at a knight it cannot reach.
* Speedrun mode: scrolls are never cursed (Hawk, Protection), so bad luck cannot spoil a run.
* Custom rules: each knight's Moonstones are now one line per stone, 0 or 1 (`moonstone_new_moon`,
  `moonstone_full_moon`, `moonstone_half_moon_waxing`, `moonstone_half_moon_waning`) instead of `moonstones = 0-4`; a file with
  the old line is refused with a message that names the new ones.

## 0.5.0 – Dragon, Moonstone, team fight fixes

* K6: the dragon and the Guardian can no longer be stun-locked: after a hit, further hits do not count for a short
  time (`dragon_hit_recovery`, `guardian_hit_recovery` in `custom_rules.ini`).
* K19 corrected: the Moonstones' names follow the phase Stonehenge accepts them in. Only one half-moon stone was
  misnamed (as the new-moon stone); the 0.4.0 version of this fix followed the damage bonus instead and named two
  stones wrongly.
* K24: a Moonstone doubles the damage in its own phase (the new-moon stone and one half-moon stone did it in each
  other's phase).
* K20: the moon pictures on the map go full, three-quarters, half, crescent, new (half and three-quarters were
  swapped); the days do not change.
* K21: leaving the item screen no longer gives the dragon a new random target.
* K22: the extra-turn glitch (Enter as a fight or visit ends started another one the same day) is gone.
* K23: a knight with no lives left after losing to the Guardian no longer gets five lives from a healing potion.
* Speedrun mode (`speedrun_mode = on` in `custom_rules.ini`): ignores every other setting and keeps the game's own
  behaviour that runs rely on (no hit recovery, the dragon's target, the extra turn, the potion, the Moonstone damage
  bonus, the dragon's hoard kept from game to game); all other fixes stay on.
* Automatic saves take one slot each: turns go round slots 91-94 (`TURN1`-`TURN4`), fights round 96-100
  (`FIGHT1`-`FIGHT5`), one slot per name; before, one save often filled two slots of its range. `SAVEHOOK.SLT`
  keeps the next number, also when an older save is loaded.
* D14: Space starts the team practice from anywhere in the first menu; with 1-2 players it starts the normal
  practice.
* D15: in co-op a ratman takes the damage of the knight that hit it.
* Custom rules: the knight sections are now `[Knight1_blue]`, `[Knight2_orange]`, `[Knight3_green]` and
  `[Knight4_red]`; a file with the old names is refused with a message that names the new one.

## 0.4.0 – Custom rules and co-op practice

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
* Setup: Python is chosen by really starting it (the `py` launcher first, then `python`; 3.8 or newer), in
  `Setup.bat`, `Custom_rules_on.bat` and `AmigaMusic_Setup.bat` (`tools\find_python.bat`). `unicorn` is installed into
  `_python` here, which the setup sees (before, `pip install --user` put it where `python -I` does not look).
  A bad `custom_rules.ini` stops the setup before anything changes; if the rules cannot be applied later, they are
  turned off instead of leaving `CUSTOM_RULES.FLG` with the default programs.
* The switch scripts (`Fixes_On.bat`, `Fixes_Off.bat`, `Music_*.bat`, `Custom_rules_*.bat`, `AmigaMusic_Off.bat`,
  `Controller_*.bat`) check their files first and every copy, and change a flag or setting only after the copies
  worked. `Music_GM.bat` and `Music_MT32.bat` refuse without the SoundFont or the MT-32 ROMs.
* Amiga music: a damaged disk image or packed module gives an error instead of a hang (block bounds, loops in the
  directory and file chains, unpacked size and match limits).
* D15 fixes after the first play test: with 2 or 4 knights the monsters no longer stay frozen (each knight's
  walk-in toggled their pause); every monster now really goes for its nearest knight (the ratmen and others
  followed knight 1 only); a knight that fell no longer stands up again when the others win; Esc ends a practice
  fight.
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
