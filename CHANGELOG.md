# Changelog

## 0.9.0 (unreleased)

* The dagger throw ends with an empty outstretched hand, so the knight seems to fire a pistol as the dagger flies (D63). **Run Setup.bat again.**
* New cheat code GUNSHOT (one fight): every knight, the computer's too, fires a musket instead of throwing a dagger, at once and with a bang; the small black ball flies three times as fast as a dagger and a hit takes all of a knight's or monster's hit points (a dodge in time still avoids it). See CHEATS.md (D64). **Run Setup.bat again** (the ball is a new piece in KN3.OB).
* Sound effects, fixed from a comparison with the Amiga version's sound driver (no Amiga files needed; with a Sound Blaster). **Run Setup.bat again.**
  * About 50 sounds played the wrong sample (K35): mudmen no longer scream like rats, the troll and the beast have their own grunt and roar, the Guardian screams, a knight in the dragon's mouth is muffled, and the ratmen's and troggs' sounds are in their right places.
  * Each sound plays at the pitch the Amiga gives it (K36): footsteps, roars and grunts vary, the troll's grunt is deep and slow.
  * The dragon bites with one chomp and grunts one grunt at a time, not the whole sample (K37).
  * A blocked blow makes its sword clash, and a blow that lands makes the hit sound; before, a block was silent and a hit clashed (K38, K35).
* The Amiga version's sound effects in the DOS game (D65, optional): with the images of your own three Amiga disks in the `amiga` folder, Setup builds the Amiga's sounds, and `AmigaSound_On.bat` turns them on: every sound at its own pitch and loudness, up to four at once, and the sounds the DOS disks lack. The music is AdLib while they are on. See README, "Amiga sound effects". **Run Setup.bat again.**
* The Amiga version's sound effects for everyone (D66): without the Amiga disks Setup builds them from the DOS game's own samples, with 14 sounds of our own for the ones DOS lacks (nine synthesized, five from public-domain recordings; all CC0, see `sounds/SOURCES.md`). `AmigaSound_On.bat` turns them on. With the disk images every sound is the Amiga's own. Needs the Python package numpy (`AmigaSound_Setup.bat` installs it).
* Amiga intro music with AdLib music: the intro no longer freezes, with a tone left on, where the DOS tune ends (D8). The silent copies of the AdLib intro and ending tunes are made another way. **Run Setup.bat or AmigaMusic_Setup.bat again.**

## 0.8.1

* DAGGERFALL now hits knights and monsters where the falling blade crosses their sprite on screen, with the usual dagger damage and reactions. The rain covers the arena without repeating the same 21 drops in a stationary fight.

## 0.8.0 – Timed Defence, Horses & Co-op Lairs

* Knights at 10 HP or less all glow the same way: their colours pulse lighter and back at the blue knight's pace (orange and the knights of 3-4 player and co-op practices no longer flash white; green no longer pulses faster; red dims as in the original). Black, purple, grey and white knights and the computer's knights do not glow. A knight healed above 10 HP stops glowing.
* DAGGERFALL's daggers are the thrown dagger turned point down (a new piece in KN3.OB: **run Setup.bat again**).
* New cheat codes, each for one fight: DARTS (endless daggers), DAGGERFALL (first menu or map: daggers rain from the sky
  in the next fight) and LIGHTSABER (a white line along the blade, glowing in the knight's dark colour; a blow that lands kills: a chop
  splits in two, a normal attack beheads, a thrust runs through). See CHEATS.md.
* MINEFIELD: the mines lie across the whole width, from the screen's bottom up to as high as the knights' feet can go, and show for five seconds before they turn invisible
  (they still go off).
* Practice: when a practice fight is of a kind played before (the same choice and the same knights), the score shows
  at the top of the screen, e.g. "3 - 2" (monsters or computer knights - players; the dragon's number red, the
  Guardian's turquoise), or one number for each knight in its own colour, in the order the knights start from the
  left (green - orange - blue), in fights between players. It is counted and shown as soon as a fight's winner is
  known. A new campaign (the knight selection screen) clears all scores.
* Esc on the Select Knight screen goes back to the first menu (custom rules).
* New cheat code BEATEMUP (first menu: every practice fight until the game is started again; map: the next fight): hit point bars at the top of the screen, a yellow
  one for the monsters or computer knights together and one for each knight (or team) in its colour.
* First menu: D, J, G, B and P no longer start their practice when they come right after a code's letters (a code
  mistyped, as BEATEMPUP, or left unfinished).
* D47: the Black Knights of a practice (keys 0 and B) keep a black or purple cloak with the game's own steel, as in the Amiga demo; those of the B key carry the claymore. In the campaign computer knights show the gear they have got, also a Sword of Sharpness, and BLACKDEATH gives the claymore unless the knight holds that sword.
* New custom rule `timed_defence` (on by default in the shipped ini): a block or dodge only counts if made after the attack's animation has begun. A block in time stops a swing, staggers the attacker and speeds your next swing; one made too early takes a fifth of the damage, with the usual hit. A dodge in time beats a thrust (the attacker staggers) or an overhead chop (it misses). Hitting a chopper first interrupts the chop; a lunge during an enemy's chop is a fast riposte (a backward thrust's damage); the faster swing after a good block does a lunge's damage. Daggers cannot be stopped. The backward thrust is the fastest blow. Works against axe and spear troggs. Smart computer knights defend by chance (`purple_knight_defence`, `black_knight_defence`, `computer_defence_pause`) and no longer walk under a chop; monsters neither (`anticheese` is now yes, blackknights_only or no, with yes the default and including the older anti-cheese rules). The P key in the first menu starts a practice against a white practice knight that defends perfectly and, if you do not attack, attacks you every few seconds. The dragon no longer skips its flinch (TOOEASY's old rule); instead, with anticheese = yes, its long fire follows you in depth only a random distance and a run of blows on it may end in its deadly bite. Settings: `defence_window`, `fast_swing_time`, `stagger_time`. `off` keeps the game's block.
* A dragon attack after a lair fight in the same turn no longer changes that lair's monster count (K34). **Run Setup.bat again.**
* K16 and K16_permanent replace the vanilla beheading with the plain fall, including cheat finishers,
  in every death animation mode. Gore off also suppresses the pending vanilla beheading.
* Start.bat refuses to launch with a missing PARENTAL.LCK until custom rules are rebuilt at K12,
  even if flags from a previously installed higher rating remain.
* CPU speed settings now reject values above the 16-bit storage limit (65535), including all four
  expanded fight speeds after additional_cycles_per_knight, with a configuration error before installation.
* Haste and Wyrm curse rolls use the deterministic curse stream with prevent_savescumming enabled,
  and the same save checkpoints as Hawk and Protection.
* Custom_rules_on.bat changes the programs as one step: everything is written next to its target first, and if a
  file cannot be replaced (DOSBox-X still running) the old ones are put back. If that cannot be done or the change
  stops half way, INSTALLING.FLG stays and Start.bat and Fixes_On.bat refuse until the change is made.
* Fixes_On.bat, Fixes_Off.bat and Custom_rules_off.bat make their change the same way (they now need Python, as
  Setup.bat does): a file held open no longer leaves the game half switched. Setup and all these switches take turns
  in one folder instead of mixing their files. Each finished change writes BUILD.TXT, which says what the installation
  runs: include it in playtest reports.
* A Setup.bat that stops half way, or whose custom rules step cannot undo a failed change, leaves SETUP.FLG. Start.bat,
  Fixes_On.bat and Custom_rules_on.bat then refuse until Setup.bat has finished.
* Setup.bat compares the age rating with PARENTAL.LCK before it changes anything: a rating above the lock leaves the
  working installation as it was (it used to replace MAIN.EXE and turn the custom rules off first).
* Start.bat refuses custom rules whose MAIN.EXE or SAVEHOOK.COM is not their own pair (`_fixes/rules`). Fixes_On.bat
  installs that pair, and stops if the custom rules are on but their programs are missing (it used the default
  MAIN.EXE and reported success).
* Start.bat stops if its AdLib fallback or the Amiga music set cannot be copied; it used to say AdLib and start the
  game with the old music settings.
* `save_mode = autosave_only` and `none`: only a SAVEHOOK.CHK that is not there starts a new token. Any other failure
  to open, read, write or close it, or a short file, stops the game like a loaded save (a read-only folder used to let
  every save through).
* `prevent_savescumming = on`: the dice, Math, Mythral and curse streams start when the game's knights are set up, so
  a save made before a stream's first roll fixes that roll too, and a stream no longer restarts after a zero.
* The automatic saves (slots 91-94 and 96-100) work again: none had been made since D20 (0.6.0). SAVEHOOK.COM ran
  itself as a child program to make DOSBox-X see the save's name, and DOSBox-X starts a program only with its file
  size free; D20's 9 KB for the knights' pieces left too little beside the game. The child is now SAVEHOOK.RUN, five
  bytes that SAVEHOOK.COM writes when it starts.
* The Black Knights (purple and black) and the other computer knights throw a dagger only from the screen, with
  none of their own in the air, and at one decision in four; they threw at every decision when over 100 away, even
  from off the screen as they came in, and the Black Knights never run out.
* IDDQD works for every player's knight against monsters, co-op included; with players' knights against each
  other it does nothing (it used to need a lone knight, and also worked knight against knight).
* TOOHARD (the first menu): easier fights, the players' knights lose half the hit points of an ordinary hit and in
  co-op the monsters go for a healthier knight first; JUSTRIGHT: the game's fights again. TOOEASY now stays on
  when typed again (JUSTRIGHT turns it off).
* The map's choices (with custom rules on) are in a fixed order: the place or the lair first, then "Battle with"
  a knight, then "Lair with" a knight.
* D33 (in progress; `coop_lairs = full`, `shared` or `off`, full by default): co-op lairs on the map. When a player's knight stops at a
  lair with other players' knights next to it, the choices add "Lair with" that knight, or with 2-3 of them "Lair
  together (N knights)": all fight the lair's monsters together (the co-op practice's rules: the monsters go for
  the nearest knight, the fight goes on while one stands), friendly fire on. Knights 3 and 4 take the joysticks
  that answer, then the third key set (I J K L, B); without a joystick at most 3 knights. With several knights to
  fight and no room (or 2-3 partners) they become one "Battle with ..." that lists them. A fallen knight loses a
  life as in a lone fight; the lair is won while one stands, and each knight standing gets the lair's chest in
  turn (in a drawn order), the gold and items put back for each, the keys and Moonstones to the first. With
  `shared`, one chest a little fuller (`extra_loot_per_knight`, 50 % for each knight past the first), opened first
  by the knight whose turn it was and then in a drawn order: a click on the gold takes the gold divided by the
  knights (the last one all that is left), an item one at a time, the rest to the next. Every knight wears its own
  player colour in the fight (its colour slot, not the practice's record colours; knight 1 has entries 44-46).
  Played: two knights fought a lair together, one fell and the fight went on; the chest first opened twice for the
  same knight (the item screen's knight is [8979h]), fixed. After the chests the visit's knight is the active one
  again (it was always knight 1).
* Catch-up gives at most +50 % of a lair's own gold, at most one more Potion of Healing in a chest and only to a
  knight that has none (catch-up's magic item that would be a potion is another item then), and a Scroll of
  Acquisition only to a knight that has none.
* The dynamic difficulty tried during this version (D34) was removed before release. An older `custom_rules.ini` that still
  has `dynamic_difficulty` is accepted and the setting ignored.
* D35: sword enchantments (`sword_enchantments = on`, on by default). One lair chest in ten, and the dragon's hoard
* D44: `computer_knights = off` (custom rules; on by default): a new campaign has only the players' 1-4 knights, without the
  Black Knights on the map.
* D45: `black_knight_ai = smart` (custom rules, the default; `classic` keeps the original AI): Black Knights line up from afar, wait at the
  edge of reach instead of walking into a blow, punish a swing and sometimes block; on the map they prefer lairs with something left, heal
  when weak and head for Stonehenge with four keys.
* D43: `max_gold` is checked as the tavern, the merchant and the High Temple are left, and only if the gold grew there, so a sale can pay for a purchase on the same visit.
* D42: buying a better sword, armour or horse at the merchant credits half of the old one's price (`merchant_trade_in`).
* D41: a knight's gold is shown with up to five digits on the item, tavern and donation screens; `max_gold` goes up to 32767,
  and gold can no longer wrap past it.
* D40: trading at the merchant. Your own sword, armour or horse, clicked on your side, sells for half its price
  (`merchant_selling`, now on in the supplied ini files); a worse one clicked on the merchant's side is free in exchange
  (`merchant_trade_in`; not for the Sword of Sharpness, which the High Temple buys). A sold horse is gone, and the armour's
  weight is back. The knight's horse is shown on its panel. The fourth horse slot is rolled once as a town is entered,
  so leaving the shop no longer changes it.
* D38: horses. With custom rules (`horses = on`) the merchant sells horses in the goods panel's bottom row: brown, light
  and armoured always, and on 10 % of town visits (`rare_horse_chance`) a black charger or a dappled horse. A horse adds
  movement, lets its knight through forest, swamp, mountains and the map's edges faster, and takes away the armour's
  movement penalty. It is shown on the map while its knight moves, and it is never lost. Prices, movement and speeds
  are in the ini. **Run Setup.bat again**: the horses' pictures are made at install time.
* D39: attacks read more accurately. Walking up or down and then attacking no longer turns a plain attack into the
  upward strike or the thrust. New setting `input_recent_direction` (ticks, 3 by default, 0 = off).
* D37: armour movement and enchantments. With custom rules, each armour's movement is set in the ini
  (`<armour>_movement_penalty_with_horses` 0, -1, -2, -4; `<armour>_movement_bonus_without_horses` 0, 2, 0, 2). Armour
  enchantments (`armour_enchantments = on`, `armour_enchantment_chance = 10`) are found in lair chests and the dragon's
  hoard, like the sword enchantments: of Mithril, Adamantium, Danu, Wyrm, Fireproof, Venomproof, Spellproof, Rebirth
  and Daggerward.
  one time in ten, holds an enchantment (shown as the knight's own sword, "Enchantment of ..."); never where the Sword of
  Sharpness is. Clicking it puts it on the knight's own sword, replacing one it had, and the sword's text on the
  item screen becomes "<sword> of <enchantment>"; the Sword of Sharpness and the computer's knights take none. It
  is lost with that sword (a better one bought, or the sword lost to a knight that wins), and a knight that takes
  the sword takes it too. Smite: the overhead chop three times the damage (the game's: twice). Dragonbane: twice
  against the dragon. Fireblock: no burns from the dragon's fire while the knight blocks. Gore (only with gore on;
  its effects stop while gore is off): three times the blood at every hit, and a knight it kills dies at once by
  the blow's death animation (as FINISHHIM). Troggbane: kills troggs at one blow. Desertbane: twice against Baloks
  and hammer troggs. Swampbane: twice against mudmen, kills trolls at one blow. Ratbane: kills ratmen and axe
  troggs at one blow.
* The item screen's pointer moves by the time a direction is held, not by the screen's loop: a press moves it one
  step (2) at once, then after 4 ticks 3 a tick, after 12 ticks 6 a tick (short moves used to be hard to aim).
* The dagger throw's turn undo (back + up + fire just after a turn) now needs up or down held as the knight turns:
  a turn made with the back direction alone stays, so back, then up + the new forward + fire is the upward thrust
  the new way (against ratmen it threw a dagger the old way).
* D31: every sword shows in a tint of its own (a request of Rob Anderson's, the game's author): the long sword
  blackened steel with a black iron grip (red looked like blood), the broadsword bronze, the claymore the game's bright steel and the Sword of
  Sharpness a glowing blue-white blade with a gold hilt. The sword is always drawn from KN4.OB, so only its four
  colours move, to palette entries 48-59 (the game uses 0-31); they follow the fades. No new graphics or memory.
  The armour the same way, in the knight's greys (helmet, collar, arms, legs; entries 60-71): padded armour the
  game's bright steel, chain mail brass, plate mail a cool blue-grey iron, battle armour blackened steel with a
  gold trim.
* Controls (D24): a back direction pressed without fire waits `input_chord` ticks (2, about 0.1 s) before it turns
  the knight, so back + up + fire and back + down + fire keep the facing whatever key comes first; a direction let
  go up to 3 ticks before the fire key still counts with it (unless one of the same axis is held). `input_log = on`
  writes every fight's key presses, the input read for each move and the attacks picked to INPUT.LOG, and
  `tools/input_log.py` shows them with the time from fire to attack.
* The dagger throw (back + up + fire) works: pressing back first turned the knight (D25), so the attack was read
  as forward + up, the upward thrust the other way. An attack with up or down and left or right within a quarter
  of a second of a turn is now read with the facing from before the turn, and the turn is undone. Up + forward +
  fire, facing that way, is the upward thrust as before.
* MINEFIELD: the Black Knights are blown up by a mine as the players' knights are (they took a deadly blow).
* MINEFIELD: a knight sets a mine off only with its feet on the mark, whichever way it faces (it went off with the
  knight's body over the mark). The second and fourth knights' blast now shows their own colours, not the first knight's.
* `tools/adf.py` refuses to extract a file whose name on the disk image could lead outside the output folder.
* The build's checks of its own output (jump ranges, duplicate labels, hook addresses, script sizes) also work under
  `python -O`.
* The 3-4 knight practice: a knight that falls stays in sight on the ground for the rest of the fight (D60). Its body
  disappeared after a while as the others fought on.

## 0.7.0 – Parental controls, Gore Off mode, Responsive controls

* Cheat codes (`cheat_codes = yes` in `custom_rules.ini`, the default): typed in the item screen, in a fight or on
  the map, and in the first menu TOOEASY (harder fights) and the monster codes, which start a practice fight with player 1 as one of its monsters: HOTSTUFF (the dragon), DIRTYRAT (a ratman), CLUBMEMBER (a troll), JUMPSCARE (a Balok), TROGLIFE or TROGGLIFE (a trogg) and SWAMPTHING (a mudman), with as many knights as players chosen (with 4, five people play: a third key set I J K L, B, N); D, J, G and B wait two thirds of a second in the first menu for a code's next letter (a code's keys may be 1.3 s apart); the monster is player 1's once it has walked in (or come up out of the mud) and it is the fight's only monster, and knight 1 leaves the screen unseen; the troll and the troggs: up and fire = the overhead blow, else the push or sideways blow; HOTSTUFF's dragon pushes a close knight away with its paw at once; DIRTYRAT's ratman leaps quickly, and from the tree (the secondary button) it hangs the knight below it; JUMPSCARE's Balok crushes a knight it hops onto up or down (not left or right), and the secondary button grabs and crushes the knight in front of it, or with none in reach makes a big jump that crushes; SWAMPTHING's mudman holds a knight for a shorter time, and after its own sinking (the secondary button) it comes up beside the nearest knight and pulls it under; a knight a ratman or a mudman holds breaks free on its own keys; CLUBMEMBER's troll no longer attacks by itself from the screen's edge, and it walks back onto the screen; a code typed whole plays the sword clash sound; the list is in CHEATS.md.
* Item screen codes DANUBLESS (full HP, else a life, else a healing potion), PUTARINGONIT (a Ring of Protection)
  and MOONMAX (strength, constitution and endurance 5).
* ROCKETMAN flies on the secondary button (the knight walks and strikes in the air); new fight code LUNAR: moon
  physics (blows push the one hit away, flings go farther, half-speed walking, moon jumps on the secondary button; with ROCKETMAN too: faster flight up, a slow moon fall).
* The fight codes can also be typed in the first menu (for the next practice fight) or on the map (for the next
  fight of the game), several at once; of codes that clash the last one typed counts. Speedrun mode turns the cheat
  codes, catch-up and anti-cheese off (the game's own exploits stay).
* Age rating for parents (`[Parental]` `age_rating` at the top of `custom_rules.ini`): K18 (the default, as the
  game), K16 (blood as chosen, no fatalities: the deaths of gore off), K12 (gore off whatever the game's options
  say), and K16_permanent / K12_permanent, kept in PARENTAL.LCK: the installation never goes above that rating
  again (only a new installation lifts it; the setup writes 18 for a new installation, and without the file the
  game is locked to K12); Start.bat then starts the game only with the custom rules on, and
  Custom_rules_off.bat, Custom_rules_reset.bat and Fixes_Off.bat refuse. README: a note for parents on the
  game's violence (Mindscape: 12+; ours: 18 with the normal settings, about 12 with gore off).
* Catch-up (`catchup = yes`, the default, or `off`; custom rules, the game only): a human knight behind the leading
  human knight (Moonstones, keys, lives, abilities, experience, HP) finds more in a lair's chest the first time it
  wins it: per 30 points behind (up to 4 levels) 10 gold and one magic item more, and from level 3 a Scroll of
  Acquisition. A human knight on its last life or at a quarter of its HP has a 10 % chance of a healing potion in
  the chest (both: 25 %).
* `anticheese = false / true` in `custom_rules.ini` (`[Rules]`): the anti-cheese rules below without TOOEASY. Black
  Knights' fights (the B key's practice; after BLACKDEATH, fights with computer knights) always use TOOEASY and the
  anti-cheese rules, for that fight only.
* TOOEASY against the cheese (Moonstone Tavern's tactics): the monsters that walk (trolls, troggs, mudmen, the
  Guardian, computer knights) keep out of a knight's reach until they are level with it, so the step-up-and-strike
  trick no longer works; the dragon answers a blow with its near fire at once instead of flinching (one blow per
  run in under its head), and its near fire and claw and bite are not stopped by blows.
* The secondary button (custom rules): right Shift for player 1, left Shift for player 2, a controller's second
  button (which no longer attacks as the first does). It does nothing in the game itself; JUMPSCARE uses it.
* Co-op: a knight a mudman holds breaks free (fire and down) by its own keys or controller; before, only player 1's
  keys counted, whichever knight was held.
* D25: knights turn in place: turning round no longer makes the knight hop sideways (its feet change places and it
  stays where it is), and the turn takes no step. Knights also walk right up to each other (and to monsters) until
  their pictures touch, instead of stopping up to a whole stride (25 pixels) apart. In depth they now stop 14 apart
  (it was 20, and up to a step more).
* Custom rules: `rest_heal` is now `on_E_rest_heal`, with a new default. When the day changes, each knight heals
  `rest_heal_fixed_percentage` (20) % of its missing hit points (at least 1) plus `rest_heal_endurance_percentage`
  (10) % times the share of its endurance (movement) left when its last turn ended: E pressed at once 30 %, all
  walked 20 % (the original heals a quarter); endurance left after a fight or a visit counts too
  (`fixed_and_endurance`). Also `fixed_only`, `full` (the original, and E restores full hit points, as
  `rest_heal = full` did) and `none` (the original). An old `rest_heal` line gives an error naming the new setting.
* K30: in co-op, the knight shown in a monster's special attack (a ratman's, the boar tossing a knight, a mudman's
  hold and pull, the Guardian's) was always drawn in the first knight's colours (blue). It now has the colours of
  the knight the monster goes for, as the Balok, the spear trogg and the dragon already had.
* D24: more responsive controls. A key tapped quickly (shorter than one frame, about 0.1 s) was sometimes missed:
  every key press now counts. An attack pressed while the knight is still finishing its last move is made as soon
  as that move ends, instead of being lost (`input_buffer` in `custom_rules.ini`, on by default).
* D15: a co-op practice against the dragon (D) did not end when the dragon was beaten: the fight went on with no
  enemy. The dragon is not one of the counted monsters, so the co-op check kept the fight running after the
  dragon's death had ended it. Now the fight is won when the dragon is dead.
* K25: when the dragon ate a knight in a co-op fight, the blue knight died instead (the eating animation's kill went
  to the dragon's nearest knight, and the "eaten" flag stopped the next knight's animation). Now the knight eaten
  dies, and it is shown in its own colours in the dragon's jaws (it was always blue).
* K29: a knight could stand behind the dragon at the left edge of the screen, where the dragon (which always faces
  right) never attacks it while the knight's blows still hurt it. The dragon's body is now a wall: the knights stay
  in front of it, where it attacks them. Also in the one-knight game.
* D22: gore off (the game's blood option, or `death_animations = off`) now means no blood at all. Blood that is a
  piece of its own (sprays, drops, pools) is not drawn, and blood on the knights, the Balok and the boar is painted
  over with the colour beside it. The troll's blow from above and the Balok's leap no longer crush a knight into a
  pool of blood: it falls to its knees and lies down. The new deaths (D20) are off. Every hit shows a hit marker
  instead: a short white X where the blow lands.
* More room for new knight pieces: SAVEHOOK.COM is loaded into upper memory (`lh savehook` in
  `moonstone-dosbox-x.conf`), which leaves the game about 9 KB more conventional memory, and the knights' bank area
  grows by 4 KB more (D20: 1BC0h paragraphs; the EMS cache places after KN3.OB and HE3.OB move on by 1600h). The hit
  marker's frames are no longer added to HE3.OB, which never draws them.
* Less CPU time in fights: SAVEHOOK.COM finds the hooks that run for every piece drawn, every object and every hit
  test first (they were 31st to 70th of 73 in the table it searches), and with gore off it stops looking for blood
  in a frame as soon as the answer is known.
* D23: faster drawing. The game turned every sprite piece, every frame, from its bit planes into pixels bit by bit;
  SAVEHOOK.COM now does it with a table and 32-bit registers, with exactly the same result. With the knights'
  recolouring made faster too, a fight takes about a third fewer instructions (measured on fight saves: 370 000 ->
  238 000 a frame with four knights). Two knight pieces drawn with fewer colour planes (KN3.OB 31, KN4.OB 25) now
  take each knight's own colours; they always showed in the first knight's.
* D6, D7: shorter pause before every turn and fight. The automatic save waited a fixed 1.1 s, and DOSBox-X often
  wrote the save twice in that time; the wait now ends as soon as the save has been written.
* D7: every turn on the map (the computer's too) starts with the game's menu sound, so a turn change can be heard.
* D12: practice with 3 or 4 players chosen started a two-player practice unless every extra player had a game
  controller. Players 3 and 4 now take the controllers that are connected, and one of them the third key set
  (I J K L to move, B to attack, N the secondary button); 4 players chosen with no controller give three knights.
* D20: the Black Knights now get the new deaths too, both the purple one of a one-player practice and the black
  ones of the B key and BLACKDEATH: a dagger, a thrust or an up strike on a Black Knight on its knees gave the
  game's beheading.
* D17: fights ran too fast after D23. A new custom rule `fight_cycles` sets a fight's speed with 1, 2, 3 and 4
  knights: 2600, 3250, 3500, 3750 cycles (were 4000-7000; play tests: 3250 right for two knights, 4550 too fast
  for four). Given one number, each knight past the first adds `additional_cycles_per_knight` (650). The map and
  menus keep `default_cycles` (4000).
* D19: in a practice with 3-4 players the Black Knights (key 0 and the B key) were drawn in the colours of the
  knight each went for, which changed as they changed knights; they wear their own purple or black again. Two of
  them came in at the same place and, overlapping, blocked each other for good (they never attacked); Black
  Knights now walk through each other (`1000:A008`).
* New cheat codes: MINEFIELD (a fight code: ten hidden mines that blow up knights and kill monsters), and on the map
  SIRWALKSALOT (unlimited walking for humans), IDROPPEDMYKEY or IDROPPEDMYKEYS (where the four keys are) and
  SIRPICKSALOT (the Valley with any number of keys).
* The manual's rules (custom rules, not in speedrun mode): the healer takes 10 gp for the heal and 15 gp per life up
  to `max_lives`, what is left is a chance at the next one (4 gp: 40 %; 27 gp: heal, life, 2/15 for another), and
  money nothing can use is returned; the home village always restores full hit points; new cursed Scrolls of Haste
  (half movement) and the Wyrm (the dragon goes for the reader), `haste_curse_chance` and `wyrm_curse_chance`, 12.5 %;
  the Scroll of the Hawk cannot enter the Valley of the Gods; the Scroll of Protection also works against the dragon.
* D28: in practices with 3-4 knights all knights flicker at 10 hit points or less.
* K32: the computer knights kept to a few lairs: their lair sort lost most of the 24 lairs. They now choose among the
  nearest ones as intended.
* K33: limits and checks: no false Game Over with a dead knight and a frog, and no endless game when two dead knights
  have a computer knight between them; hit points stay above 0 when armour is taken, and automatic loot moves the
  right armour's hit points; a monster with no free flight slot lands where it is; Mythral with a large donation
  (`max_gold` above 250) no longer always fails; loot follows the dagger limit `max_daggers`.
* D26: on the map a new turn waits until the keys are let go: a direction still held from the turn before no
  longer moves the next knight; it moves on the next press.
* K31: a dagger thrown to the left never left the fight (the game ended it only between x -10 and 0, and it flies
  20 a frame); the daggers filled the fight's object slots, and then no new dagger appeared when thrown.
* D15: a monster between two knights at other depths (a mudman among four knights) switched knights at every step
  and stood still: blocked in depth by the knights, it backed off from one towards the other. A monster now keeps a
  new knight for a moment before it may switch again.
* K25: the knight a mudman holds and pulls under is drawn in its own colours (the frames showed the knight the
  mudman would go for now: holding blue, red's death was shown); the same for a ratman's hold.
* D21: dragon debug mode for testing (`dragon_debug_mode = 1` in `custom_rules.ini`, off by default): on the map
  the keys 1-4 make knight 1-4 the dragon's target, and Enter starts the dragon fight when the knight whose turn it
  is stands under the dragon.

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
