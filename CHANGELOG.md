# Changelog

## Unreleased

* **A dropped key press still turns the knight; diagonal turns go diagonally at once** (D157; custom rules): some
  keyboards do not send a key's press while another key is held (seen with A while D was held), only its release; in a
  fight such a direction key's release now counts as a tap, so the knight turns. And a turn with up or down (a
  diagonal the other way) now moves diagonally at once instead of straight up or down for a moment.
* **A back tap turns the knight even when the forward key is let go late** (D156; custom rules): walking one way and
  tapping the other way while still holding the walking key turned the knight only if that key was let go at once.
  Now the tap turns the knight and it stays turned: a key held from before a turn the other way counts again only
  after it is let go and pressed again.
* **A back tap turns the knight also right after walking** (D155; custom rules): a short tap of the back key pressed
  before the forward key was let go did nothing, because the game drops left and right when both are held. Now the key
  pressed later counts: the tap turns the knight, and back held while forward is still held turns and walks it back
  (D156: let go of back, the knight then stands until forward is pressed again).
* **A tapped walk moves a little** (D154; custom rules, `walk_short_first_step = on`): the game's walk steps are 25, 3, 23
  and 4 pixels in turn, so tapping left or right made the knight jump 23-25 pixels every second tap. Now a walk from
  standing always starts with the short step: every tap moves the knight 3-4 pixels, and a held walk takes its big step
  second, also right after a turn. Diagonal taps too; up and down are unchanged. `walk_short_first_step = off` keeps the game's steps.
* **Fights and turns start quickly again; no automatic save at a practice fight** (D153): the automatic save before
  each fight and at each human turn's start had become slow since the smooth animation's attack poses (D146-D148),
  because DOSBox-X packs its save states and the poses' file packed very slowly. Setup now stores that file packed in a
  way that DOSBox-X packs quickly (rerun Setup.bat once; until then the poses are drawn in place). Practice fights from
  the menu no longer make an automatic save. `moonstone-dosbox-x.conf` now names `compresssaveparts = true`, with a
  comment on `false` (quicker saves, but about 41 MB a save file).
* **A short tap backwards turns the knight** (D152; custom rules, `input_chord`): in a fight a back key tapped too briefly
  for two key reads did nothing; now the knight turns when the short chord wait ends, unless fire or the forward key came
  in the wait. The attack chords (back + up or down + fire) and the joysticks are unchanged.
* **The riposte against the troll and the hammer trogg; one riposte for each blow** (D151; custom rules, timed defence):
  a riposte on the troll's or the hammer trogg's blow from above still does its damage, but no longer stops the blow:
  the monster does not flinch, its blow lands and it waits as after any blow (so riposting the hammer trogg all the time
  no longer keeps it from hitting). The axe trogg is unchanged. A riposte that lands in the same moment as another
  knight's blow from above now stops it, as one landing a moment earlier did. And a knight gets one riposte for each
  blow a foe starts: pressed again against the same blow, it is the ordinary lunge.
* **The dragon attacks in a co-op dragon practice** (D150; custom rules): in the D practice with 2-4 knights the dragon
  went for the knight nearest it but, while it breathed its far fire, drifted towards the first knight's depth, so its
  fire never hurt anyone and the fight went on for ever. It now keeps to its own knight during its fires too: a knight
  that stands in the fire is burnt, one that runs in time gets away, as with one knight. One knight, HOTSTUFF and
  `monster_target = first` are unchanged.
* **The Gem of Keyfinding shows only the nearest missing key** (D149; custom rules, `rare_gems = on`): instead of all
  four keys it now names the holder of the one key you lack that is nearest your knight on the map (by distance across
  and down; a tie goes to Forest, Wasteland, Swamp, Moors in that order), and only that key's lair glows until the turn
  ends. A key with no place to walk to (the dragon's, or nobody's) counts as the farthest. A knight with all four keys
  cannot use it: nothing happens and the gem stays. The IDROPPEDMYKEY code still shows all four.
* **Smooth animation: moves begun straight from a held block, dodge or throw** (D148; custom rules, with
  `smooth_animation` 2, 3 or 6): when the keys change while a knight holds the block, the dodge or the thrown pose,
  he now goes into the next move in poses in between too; from the dodge into the swing or the fast backward thrust
  the sword sweeps down in front, as from standing. Run Setup.bat once (`SAVEHOOK.INB` is now about 5.3 MB).
* **Smooth animation: the remaining blows, and a no-spin dagger throw** (D147; custom rules, with `smooth_animation`
  2, 3 or 6): the backward thrust (also the fast one), the upward thrust, the dagger throw, the block and the dodge are
  now shown in poses in between too, as the swing, the chop and the lunge are; the upward thrust keeps its sword on its
  line, and the fast backward thrust sweeps down in front as the backward thrust does. The dagger throw is now a
  no-spin throw: the knight holds the dagger by its hilt with the point away from him until he lets go (the game's own
  raised frame is turned, also in the original game). Run Setup.bat once (`SAVEHOOK.INB` is now about 3.9 MB).
* **Smooth animation: the swing, the overhead chop and the lunge** (D146; custom rules, with `smooth_animation` 2, 3
  or 6): these blows (with the quick swing after a block and the riposte) are now shown in poses in between, up to
  five a tick, as the walk is: the body turns and leans, the sword sweeps and its arc grows with it, and a blow that
  strikes straightens back to the ready pose. They are shown one tick late, like the walk, and the game itself (its
  logic, hits, timing windows and pace) is unchanged. Setup makes the pictures from your own game files into
  `SAVEHOOK.INB` (about 3 MB, a few seconds): run Setup.bat once. The other blows, the hit reactions and a knight
  under a Potion of Speed look as before.
* **The block stops a ratman's bite and claw** (D145; the fixed game, also without custom rules: run Setup.bat
  again). In the ratmen fight a knight blocking (back + down + hit) and facing the ratman takes no damage and no
  disease from its bite or claw; the ratman finishes its blow, as a trogg does. From behind, or with any other move,
  the blow lands as before. With timed defence on, the block has to come in time, as against the troggs.
* **Ducking a thrown dagger** (D144; custom rules, `[Combat] duck_dodge = on`, `duck_window = 6`): press down just
  before a dagger strikes your knight (down alone, as for a step down; held or let go) and the knight ducks: the
  dagger flies over it, at any depth. The knight must be standing or walking, not attacking, defending or staggered;
  down held from earlier (walking down) does not duck. Computer knights duck a dagger now and then (one in four). Not
  GUNSHOT's ball, DAGGERFALL's daggers or a knight played with a joystick. The game's own dodge (down + hit) is unchanged.
* **The ratmen fight: up + hit is the straight upward thrust, back + down + hit the block** (D142; the fixed game,
  also without custom rules: run Setup.bat again). The game gave back + down + hit the straight upward thrust in
  this fight; now up + hit is that thrust (in place of the slow overhead chop) and kills a ratman on the ground at
  once, and back + down + hit is the block, as in the other fights. Down + hit is still the downward stab. On the
  keyboard, back + down counts only when down is pressed together with the back key: walking with down held and
  then back + hit gives the quick backward thrust.
* **Smooth animation: the knight's walk** (D143; custom rules, with `smooth_animation` 2, 3 or 6): a walking knight is
  now shown in poses in between the game's four walk poses, up to five for each step, so the walk no longer jumps
  12 pixels with every pose. The in-between poses are made by Setup from your own game files (`SAVEHOOK.INB`; pixels
  are only moved, nothing is drawn or shipped) and shown one step late: the knight's picture is at most about 12
  pixels (a ninth of a second) behind where the game has it, and the game itself (its logic, hits and pace) is
  unchanged. Starting, stopping, turning round and blows look as before. Run Setup.bat once to make the file; without
  it, or without XMS memory, the walk looks as in D136.
* **Switching sides with down held turns the knight** (D141): a knight lunging or walking with down (or up) held
  that presses the other side's direction and hits now turns and lunges that way, as in the original game. Rebuilt's
  quick back + down / back + up reading (the block, the dagger) had kept the old facing, so in the ratmen fight the
  hit became the straight upward thrust. Back + down pressed together is still the block (in the ratmen fight the
  game's own straight upward thrust).
* **Special items in only some lairs** (D139, D140; custom rules, `special_items = lairs`, the new default, with
  `special_item_lairs = 8`): only that many of the 24 lairs hold enchantments or special potions, rings and gems,
  spread evenly over the map's four quarters (two in each), and each of them at least one (each kind rolled at its
  chance; when none comes, one is drawn, every kind once before any twice). Which lairs and kinds is fixed when the
  game starts. At the defaults a game has about 9 special items (about 12.5 before), and the number of lairs with one
  no longer swings from 6 to 14. The dragon's hoard is as before. `special_items = chance` is the old way, and an
  older custom_rules.ini without the key keeps it.
* **A lair stays on the map while a special item is left in it** (D140; custom rules): before, a lair whose gold and
  items were all taken left the map even with a special potion, ring or gem still in its chest (one a knight with no
  free place could not take), and the item was lost.
* **Rebirth and the Black Knights' four keys lead to the real Stonehenge** (D138; custom rules): a knight saved by
  Rebirth armour now wakes at Stonehenge, and a computer knight with all four keys walks to Stonehenge and waits there.
  Both used to go to Water Deep by mistake. A Stonehenge moved with the map tool is followed; with `custom_places =
  off` it is the game's own.
* **The special items' settings in one place** (D137; custom rules): the sword and armour enchantments, the special
  potions, rings and gems now have their keys together in a new section `[Special_items]`, right after `[Treasure]`,
  with a master switch `special_items = chance` (as before) or `off` (none of them at all). An older custom_rules.ini
  with the keys in `[Rules]` and `[Treasure]` is read as before. **Fix:** speedrun mode now has no enchantments or
  special items, as the docs said.
* **Smooth animation in fights** (D136; custom rules, `smooth_animation = 6`, the default, also for an older
  custom_rules.ini; `1` = the original): between two of the game's own pictures a fight now shows up to five more, in
  which what moves without changing its picture is drawn part of the way: thrown daggers, the dragon's body parts and
  figures pushed or thrown back move in small steps, up to 54.6 pictures a second instead of 9.1. A knight or monster
  whose pose changes (walking, blows) is drawn as before. The game itself is unchanged: its logic keeps its 9.1
  ticks a second, a key is read and a blow lands exactly when it did, and a pose still changes once a tick (in-between
  poses are a later stage). `2` and `3` show one or two extra pictures a tick. The extra pictures need a faster
  emulated CPU, so fights then run at `smooth_fight_cycles` (`auto`); a fight waits for the game's clock, so it does
  not get faster, but the heaviest fights (the dragon, many knights), which used to run slow, now keep the full pace.
  A picture the CPU has no time for is left out; the game is never slowed for one. Speedrun mode keeps one picture a
  tick. `[Debug] draw_FPS` and `draw_TPS` show the pictures and the ticks a second in a fight's corner.
* **Special gems** (D113; custom rules, `rare_gems = on`, `rare_gem_chance = 10`): a lair chest or the dragon's hoard
  may hold a special gem, shown after its Gems of Seeing in its own colours (the stand tells the group, the ball the
  gem). A knight carries three in its gem row's first places, its Gems of Seeing after them; take, swap, sell (the
  High Temple pays a Gem of Seeing's price) and offer them as the special rings, and the loot rules and the gold cross
  cover them. Click your own on the item screen to use it. First two: the **Gem of Fury** (your blows hit as with
  Strength 5 or more in your next fight) and the **Gem of Keyfinding** (IDROPPEDMYKEY's key screen and glowing lairs,
  no cheat codes needed). The Gem of Concealment can already be found (its effect: D115); the other gems follow.
* **Gem of Spying and Gem of Duplication** (D114; with `rare_gems`): the **Gem of Spying** opens the Scroll of the
  Wyrm's view without the Wyrm: another knight's whole panel (its specials and enchantments too), the arrow button
  shows the next one, nothing can be taken, Exit goes back to the map. The **Gem of Duplication**: click it, then an
  item on your panel: one more of it (a dagger up to `max_daggers`; a Potion of Healing, a Gem of Seeing, a Ring of
  Protection, the Talisman or a scroll up to 9; a special potion, ring or gem into a free place, the gem's own place
  counting as free). An item that cannot be copied (gold, weapons, armour, the Sword of Sharpness, keys, Moonstones,
  the horse, another Gem of Duplication, a full kind) or Exit keeps the gem. Both can be found in chests now.
* **Fix:** switching your own horse off on an item screen with a second panel (loot, Scroll of Acquisition, Scroll of
  the Wyrm) switched the other knight's horse instead (D114).
* **Gem of Greed and Gem of Concealment** (D115; with `rare_gems`): the **Gem of Greed**, used on the item screen you
  open on the map, shows each lair's gold under it on the map for the rest of your turn (0 for a lair with only items);
  in a town or a village it is not used up, as the turn ends there. The **Gem of Concealment** works while you carry it:
  the other players do not see your knight on the map in their turns, and computer knights never go after you, never
  send a scroll or the dragon at you and never attack you; a human player can still walk onto you and fight, and the
  dragon still finds you. The **Gem of Spying** now shows only the knights still in the game (none that are dead), sees
  a Spellproof knight (a gem is not a scroll), and stays in your row when there is nobody to spy on. Both new gems can
  be found in chests now.
* **Fix:** in a campaign without computer knights the arrow button of the Scroll of the Wyrm and the Scroll of
  Acquisition also offered the computer knights left out of the game (with their starting kit): the Wyrm could be sent
  after a knight not on the map, and Acquisition could take items from one. They are passed over now (D115).
* **Gem of Banish Monsters and Gem of Frog** (D116; with `rare_gems`), the first aimed gems: used on the item screen
  you open on the map, they turn your knight into a crystal ball as the Gem of Seeing does. **Banish Monsters:** fire
  on a lair: you see its chest, and its monsters are gone for the rest of the game; anyone who enters it later (also
  with co-op partners) takes the chest without a fight and without the first win's experience. **Frog:** fire with the
  ball on another knight (within 8 pixels; not a dead or a hidden one): it is a frog for its next turn only. Fire on
  nothing does nothing; Space or E cancels and keeps the gem; after a hit your knight is back in place with the
  movement it had left and its Haste. Both can be found in chests now.
* **Gem of Change Places and Gem of Slow** (D117; with `rare_gems`, new `slow_gem_percent = 33`), the last two aimed gems:
  used on the item screen you open on the map, they turn your knight into the crystal ball; fire with the ball on another
  knight (not a dead or a hidden one; a frog or a computer's knight too). **Change Places:** the two knights swap places
  and your turn goes on with the movement and Haste you had left; a lair or town under your new place opens only if you
  press fire there, as after walking there. **Slow:** that knight's next turn it plays has `slow_gem_percent` (33) % of
  its movement (after Haste, the horse, Mithril and the Rings of Endurance; at least one movement point); a frog's
  skipped turn does not count, and a second Slow adds nothing. All ten special gems can now be found in chests.
* **Spellproof armour protects from the Gem of Frog** (D118; custom rules): the Gem of Frog cannot hit a player's
  knight in Spellproof armour, as scrolls cannot target it; fire on it does nothing and the gem is kept. The other
  gems are unchanged (Spying still shows that knight; Change Places and Slow still work on it).
* **Fix:** the pointer on the item screen was violet since the enchanted gear's look (D98): it has the game's own
  colours again on every item screen (your own, a chest, the dragon's hoard, another knight's, the merchant, the High
  Temple), also in a game saved before this fix (D119). The violet enchanted swords and armours and the special potions,
  rings and gems look as before.
* **Fix:** after the dragon had eaten a knight, the next dragon or Guardian fight (with no lair or knight fight
  between) made its knight vanish at once and never ended; this was in the original game too. Every fight now starts
  with no knight eaten. And the dragon that beats or robs a knight now flies off with what it took and comes back from
  the map's edge, instead of waiting where it caught the knight: a knight that was the only one left was attacked again
  at the start of its next turn, before it could move (D120; also without custom rules).
* **Fix:** the Rings of Strength, Constitution and Endurance now show their +1 on the item screen (the ability's
  number counts one higher for each ring carried, two of a kind +2), and it goes back down when the ring is lost by
  any route; before, the bonus worked in fights, hit points and movement but the number did not change. The bonus is
  on top of the base ability and never blocks raising it: a knight at 5 with a Ring of Strength shows 6 and can still
  raise its base by experience, Math, Mythral and the potions as any knight at 5. A ring now always adds its +1, also
  over 9 (D121; custom rules, `rare_rings = on`).
* **Math and Mythral never raise an ability that is 5 or more** (D123; the fixed game, also without custom rules; run
  Setup.bat again). Before, only an ability of exactly 5 was left alone, so one taken above 5 by the Potions of
  Strength, Endurance and Constitution (or a high start value in `custom_rules.ini`) could still be raised, also past 9.
  The stat rings do not count (base 4 with a Ring of Strength, shown 5, can still be raised). With every ability at 5
  or more nothing changes from the game: Math gives another gift, Mythral says you have nothing left to learn.
* **The computer knights' level-up never raises an ability that is 5 or more either** (D126; the fixed game, also
  without custom rules; run Setup.bat again), as Math and Mythral since D123. With every ability at 5 or more, losing
  to the Guardian and a Mythral donation that goes wrong no longer change a byte of the knight's record that is not an
  ability: the Guardian takes the lives as before but no ability, and Mythral says his powers are weak.
* **Losing to the Guardian may lower any ability, never below 1** (D130; the fixed game, also without custom rules;
  run Setup.bat again). Before, the ability that fell was never one of exactly 5, and with every ability at 5 or more
  none fell. Now one of the abilities above 1 falls by 1, each as likely; only a knight with all three at 1 loses none.
  The rings do not count (the base falls; base 1 with a ring is not lowered).
* **The spear trogg attacks a little slower** (D124; custom rules, `[Monsters] spear_trogg_attack_pause = 130`): it
  waits 30 % longer between its thrusts (13 frames instead of 10 after a thrust that lands or is blocked, 26 instead of
  20 after a miss), so a knight standing in its reach is thrust at every 1.8 s instead of every 1.4 s. The thrust itself
  looks and hits as before. 100 gives the game's pace; older ini files get 130.
* **A riposte that lands at the same moment as the troll's blow from above now stops it** (D125; custom rules,
  `timed_defence = on`). Before, when the quick thrust and the troll's chop landed in the same frame, the troll
  ignored the thrust (no damage, no flinch) and its chop still hit; the axe and hammer troggs flinched but their blow
  still hurt. Now the knight's blow wins such a tie: the monster flinches and its blow does not land. A riposte that
  lands first worked already; a chop that is not interrupted still does its damage and the troll's crush.
* **The troll's blow from above lands where its club is drawn** (D131; the fixed game, also without custom rules; run
  Setup.bat again). The club had a thin line of collision points, so at many distances it passed through gaps in the
  knight's picture, and a knight standing where the troll stopped could be missed by every blow (from the left the
  troll stops about where the blow always missed). Setup now writes `DISKB\COLLFIX.HIT`, the game's collision file
  with 14 more points on the club, and the fixed game reads it. The blow's reach, damage, timing and the crush are as
  before; it now also strikes a knight holding the block in those spots (it never could be blocked).
* **Finer terrain zones, measured where the knight stands** (D133; custom rules, `[Map] terrain_cells = 4x4`, `terrain_probe = centre`): the map's movement zones (open ground, forest, swamp and water, rocks, mountains) are
  now cells of 4 x 4 pixels (80 x 50) instead of 8 x 8, so they can follow the map picture's forests and rivers, and
  the zone a knight is in is read under the middle of its icon instead of below its feet, so the slowing starts where
  the picture shows the zone under the icon. `tools/terrain_zones.csv` is 80 x 50 (an older 40 x 25 file still
  works: each cell becomes 2 x 2). `terrain_cells = 2x2` applies the zones in the original 8 x 8 blocks and
  `terrain_probe = feet` measures at the original point; speedrun mode is the original. Without XMS the zones work
  in 8 x 8 blocks.
* **The map tool** (D133-D135; `Terrain_editor.bat`, needs Python 3 with Pillow): paints the terrain zones (brush,
  fill, 4 x 4 or 8 x 8 cells), moves the places, lairs and starts, imports your own 320 x 200 map picture (the
  colours become the nearest of the map's palette; six of its colours are free to set) and applies it all to the game
  in one step, keeping the original map as `MAP.CMP.orig`; *Restore original map* puts the game's own map, places and
  terrain back. `tools/map_palette.png` shows the map's 32 colours as squares to paint with. Projects are saved as one ZIP; the game's own map is never put in one. A map file up to 35,840 bytes
  is taken (the rules build tells the game a longer file's length).
* **Move the places and lairs** (D134; custom rules, `[Map] custom_places = on`): the map tool can move the home
  villages with the knights' starts, the two towns, Stonehenge, the Valley, Math's tower, the 24 lairs and the Black
  Knights' starts; the rules build puts them into the game, and the computer knights follow (they shop at the moved
  towns and walk to the moved lairs). A lair keeps its monsters and region by its number. Without the tool's files,
  or with `custom_places = off`, the game is exactly as before.
* **A way out of a stuck campaign fight** (D127, D132; custom rules, `[Combat] fight_idle_exit = 30`): when for 30
  seconds no player in the fight has pressed a key or a joystick control (a key held down counts as pressing) and no
  player's knight in it has lost or gained hit points, "ESC LEAVES THE FIGHT" shows at the top of the screen and one
  press of Esc leaves the fight. Any key, control or hit takes the hint away and starts the time again. Nobody wins: no
  loot, no experience, the lair keeps all its monsters, the knights keep their wounds, the turn is over; the dragon
  flies off. A knight already down still loses its life. A computer knight's own fight never offers it. Otherwise Esc
  does nothing in a fight, as before; practice keeps its own Esc. 0 turns it off; older ini files get 30 (D127's
  earlier `fight_safety_timer`, a fight-length timer, is gone; the line is ignored if an ini still has it).
* **The Players choice in the first menu goes round** (D129; also without the custom rules): right after *1* comes
  *1 + CPU* again, and left from *1 + CPU* goes to *1*: *1 + CPU*, *2 + CPU*, *3 + CPU*, *4*, *3*, *2*, *1*, *1 + CPU*, ...
  With `computer_knights = off` the ring is *4*, *3*, *2*, *1*. Before, the choice stopped at both ends.
* **The Gem of Change Places teleports when there is nobody to change places with** (D128; custom rules,
  `rare_gems = on`): when no other knight on the map could be hit by it (the others dead, out of the game, or hidden
  by Concealment or Invisibility), firing the ball anywhere puts your knight there, the gem used, and the turn goes on
  with the movement and Haste you had left, as after a swap. Not into the Valley of the Gods (the shot does nothing
  there and the gem stays), and not without moving the ball. While any knight could be hit, the gem works as before.
* **SKIPCOMBAT**, a new map code (D122; custom rules, `cheat_codes = yes`): typed on the map it skips fights until it
  is typed again. A human knight entering a lair goes straight to its chest as after a won fight (the lair won, its
  special items rolled at that first look, the catchup loot, the turn's movement used up) but gains no experience;
  co-op lairs share the chest as after a win. The dragon is beaten at once (its hoard, no experience). Knight duels,
  the Guardian, computer knights' own lair fights and the practice are fought as ever. Made for trying out the special
  items in lair chests quickly.

* The **Ring of Charisma**, the thirteenth and last special ring (D112; custom rules, `rare_rings = on`): each one takes
  `charisma_discount` (5) gp off what its knight pays at the merchant (weapons, armours, daggers, horses), the High
  Temple and the healer, never below 1 gp, and the shop's hover shows the knight's own prices; Mythral counts a donation
  as 5 gp more for each ring; each ring calms Math with `charisma_math` (50) % when he would turn the knight into a frog.
  Two rings stack. Whatever a knight sells now always pays less than the knight's own buying price, so there is no
  buy-and-sell loop.

* Special rings: the walk rings, Regeneration and Luck (D111; custom rules, `rare_rings = on`): the **Rings of Mountainwalk**
  (mountains, the map's edges and rocks), **Waterwalk** (swamp and water) and **Forestwalk** (forest) take away the
  slowing of their terrain, on foot or mounted; the **Ring of Plainswalking** makes a step on open ground cost two thirds,
  so a knight goes 50 % farther over it; the **Ring of Regeneration** heals to full HP at the end of each day; the **Ring
  of Luck** wins the first dice throw of each town visit and finds 0 to `luck_chest_gold` (9) more gold in chests and
  the dragon's hoard. Twelve special rings now.
* The map's terrain zones (D110; custom rules, `[Map] custom_terrain = on`): the terrain that slows a knight now comes
  from `tools/terrain_zones.csv`, painted with the terrain editor: open ground, forest, swamp and water, mountains and
  the map's edges, rocks (slowing as swamp). Off: the game's own map.
* Special rings, more of them (D109; custom rules, `rare_rings = on`): the **Ring of Undying** saves a knight from death once: when it would lose its last life (a fight, the Guardian, the disease) it wakes in its home village with 1 life and full HP and the ring is gone (a second ring saves once more; Rebirth armour acts first). The **Ring of Vampirism** gives 1 HP (two rings 2) for each sword blow or thrown dagger that hurts a knight or a monster, never above max HP. The **Ring of Absorb Soul** gives a life (up to `max_lives`) for each knight its bearer kills in a fight. They now turn up in chests too.
* Special rings (D108; custom rules, `rare_rings = on`): a lair chest or the dragon's hoard may hold one (`rare_ring_chance`, 10 %), each in its own colours (the band tells the group, the stone the ring), named on hover. A knight carries up to two in its ring row's first two places, its Rings of Protection after them; take them from chests and from other knights (with two already each click swaps). The High Temple buys one for a Ring of Protection's price, Stonehenge takes one as an offering, and a computer knight or the dragon may take them by the loot rules (they do nothing for a computer knight; win them back). Built so far: the Rings of Strength, Constitution and Endurance: the ability counts one higher while the ring is carried, also over 5 (two of a kind +2, at most 9); Math and Mythral still see the real value (D121: now shown on the item screen, with no cap). More rings follow.
* The loot rules and the dead knight's cross (D106; custom rules, `dead_knights_cross = on`): a computer knight or the dragon that beats a knight with lives left still takes one item, the first in the game's order, but that item can now be a special potion (the one in the first place, just before the Potion of Healing in the order) if the winner has room for it (a computer knight carries three, the dragon's hoard one). At the last life a computer knight takes everything that fits: all the gold up to `max_gold`, daggers up to 10, the better sword and the better armour with their enchantments (its own worse ones stay with the dead knight), every magic item, the keys and Moonstones and the special potions it has room for. The dragon takes half the gold as before and everything else into its hoard except the swords, armour and daggers (their enchantments and one special potion go into the hoard if its place is free). What is not taken stays at the dead knight's grave, as the original game already allowed: walk onto it with another knight and take everything you want on the loot screen; a computer knight may come and take it too. A computer knight's sword or armour enchantment taken this way has no effect for it, but shows on its panel and goes with the item to the knight who beats it. Reincarnation now also clears the knight's special potions, their effects, its enchantments and its horse (they were kept by mistake); respawn keeps the leftovers as before. Off in speedrun mode. **Run Setup.bat again.**
* The dead knight's cross on the map (D107; custom rules, `dead_knights_cross = on`): a dead knight's grave is drawn as a gold cross while it still holds something worth fetching: gold, daggers, a magic item, a key, a Moonstone, a special potion or the Sword of Sharpness. A sword, armour (also enchanted) and the horse alone do not count; when nothing else is left the game's grey grave is drawn. Standing on it shows the pink outline as before. Not with respawn or reincarnation (no cross), not in speedrun mode. The dragon that takes a knight's last life takes the Sword of Sharpness into its hoard again, as in the original game (D106 had left it at the grave), unless the hoard already has one. IDROPPEDMYKEY names a key at a grave as "<knight>'s grave".
* Special potions (D101-D105; custom rules, `rare_potions = on`): a lair chest or the dragon's hoard may hold one (`rare_potion_chance`, 10 %), each in its own colours. A knight carries up to three in the first places of its potion row, its Potions of Healing after them; click one on the knight's own item screen to drink it. All twelve: Danu (HP + the max HP, up to twice the max, and a life), Full Restoration (full HP and lives), Strength, Endurance and Constitution (+1 each for good, also above 5) and Life (+20 max HP for good, `life_potion_hp`, and as much HP at once). HP above the max after Danu stays until damage brings it down. Might and Fire Resistance (D102) work in the knight's next fight: Might makes its blows as strong as Strength 7 and pushes the one struck back a little (not the dragon or the Guardian), Fire Resistance lets the dragon's fire do only 1 damage, and Speed (D104) makes the knight walk half again as fast and its attacks about a fifth faster (not its blocks); a practice fight neither uses nor ends them, and a second of the same kind cannot be drunk while one waits. The map potions (D103): Recall takes the knight home to its village with full HP and lives as the village gives them, and its turn ends; Levitation, from the first forest, hill or other slowing ground the knight steps on, lets it walk at full speed to the end of that turn; Invisibility hides the knight's map icon from the others' turns until it enters a lair alone: then the lair's chest opens with no fight (as after the Hawk) and the invisibility ends. An invisible knight attacked by another knight or the dragon is not fought (and is visible again), and a knight holding Invisibility or Recall gets the attack prompt, as with the Scroll of Protection, to drink one and avoid the fight (Recall takes it home). Take one from another knight with three already and they cycle. The High Temple buys one for what a Potion of Healing sells for (it never sells them), and Stonehenge takes one as an offering, as a Potion of Healing (D105). They are lost with the knight's last life, unless a computer knight wins that fight: it takes up to three, never drinks them, and a human who beats it can take them back (D105); the dragon takes none. Without XMS memory they are off, as the cheat codes are.
* Enchanted swords and armours are violet (D98; custom rules): an enchantment in a lair's chest or the dragon's hoard shows as your own sword or armour in violet, and an enchanted sword or armour is violet on every knight's panel of the item screen, so you can see at once which gear is enchanted. Plain gear, fights and the map look as before.
* Armour enchantments now appear in lair chests (D97; custom rules, `armour_enchantments = on`): because of a bug they came only in the dragon's hoard. A lair already opened in a running game rolls for one the first time it is shown again.
* Mithril also gives movement (D99; custom rules): besides the armour never costing movement, the knight moves as if its Endurance were 2 higher (+4 a turn), on any armour, padded armour too, with or without a horse.
* Enchanted starting gear after a won fight (D100; custom rules): a loser's long sword or padded armour is still never taken, but if it is enchanted and the winner has the same starting item, the winner can click it on the loot screen and the two change places, each with its enchantment. Computer winners are as before.
* Cheat codes (D96): the map code ONEMORETURN is now SIRNEVERTIRED; IDKFA gives a full set of magic items (4 healing potions, 4 Gems of Seeing, 3 Rings of Protection, 4 Talismans of the Wyrm, 2 of every scroll); WEPL also works in the item screen. With 99 daggers or lives the potions and scrolls on the item screen could not be clicked; now they can (the daggers still run off the screen's edge). See CHEATS.md.
* The Amiga sound effects: the tavern's dice rattle and the thunder of the offering at Stonehenge (D95; with the optional Amiga sound effects): the DOS game played a thud for the dice and had lost the thunder. Both also play without the Amiga disk images: the thunder then is a sound of our own, cut from a public-domain (CC0) recording of a thunder blast (`sounds/thunder.wav`). The wind the Amiga's sound files hold is never played by the Amiga game either, so it stays out. **Run Setup.bat again.**
* The troll and the troggs give a fallen knight the finishing blow (D90): as the troggs did in the original game, but now every time, and the troll too (it went idle as soon as the knight fell): the troll crushes the knight with its club from above, the troggs behead it or split it, and the spear trogg runs its spear through it (the long thrust, also with vanilla deaths). Not with Gore Less or Off. In co-op, once no knight stands, the monsters go for each fallen knight still waiting for its blow; a fallen knight waits up to 5 seconds, then the monsters stand or walk off as before. **Run Setup.bat again.**
* Horses v2 (D92; custom rules, `horses = on`): click your own horse on the item screen to switch it off (it turns
  grey): the knight then moves as on foot, with the armour's movement penalty back, and the horse's other bonuses are
  off. Click it again to switch it on. At a merchant that buys horses the click still sells it. The merchant's horses
  are drawn as you enter the town, by the level of your own horse (no horse: brown 75 %, light 50 %; the better your
  horse, the better the stock; `horse_stock_*` in `custom_rules.ini`). Levels: brown 1, light 2, white 3 (the former
  "Armoured horse"), and level 4 the black charger, the dappled horse and the new **Armoured horse**, each as likely. The
  Armoured horse is fully armoured: the light horse's speed and +20 maximum HP while it is switched on (only the maximum:
  the knight heals up to it as usual, and loses HP above it when the horse is switched off or sold). `rare_horse_chance`
  is gone; an older ini's `armoured_horse_*` lines now set the white horse. **Run Setup.bat again.**
* Money shows up to five digits everywhere (D91): the gold sacks of the tavern, of Mythral the Mystic and of the healer are wider, so their boxes hold five digits, and the numbers sit in the middle of the box. With custom rules the dice result shows the whole gold (it stopped at 999), and the donation, a chest's gold, the dragon's hoard and Math's gift show five digits too (from 1000 they showed garbage). A large gold no longer upsets the dice or the donation behind the screen. **Run Setup.bat again.**
* The knight's sword is drawn as a sword when the troll pushes the knight over, the dragon's fireball knocks it down or the demon lets it go (D89): it was part of the body picture, so it had the armour's colour, and LIGHTSABER did not show there. Now it has the weapon's own colour and the lightsaber's look, as in every other move. **Run Setup.bat again.**
* The riposte works against the troll and the troggs (D88; custom rules, `timed_defence = on`): a lunge started while the troll, an axe trogg or a hammer trogg has its blow from above in the air comes out fast and strikes first, as against a knight's overhead chop.
* The Amiga intro and ending music plays inside DOSBox-X and in step with the pictures (D87; needs your own Amiga disk 1 and the Amiga music on, `AmigaMusic_On.bat`; with AdLib or General MIDI music and with the DOS or the Amiga sound effects). Setup plays the two Amiga modules with the Amiga game's own player routine and stores each tune as a left and a right sound in the effects' SoundFont, and a small tune module of our own starts them when the intro or the ending starts its music. Before, a helper played WAV files beside DOSBox-X from the moment the intro program started, 40 seconds before its music begins, so the music ran far ahead of the pictures. The intro now starts its music where the Amiga version does, early in the first scene (20 seconds sooner than the DOS tunes), and after the first lightning its pictures slow down to the Amiga's pace, so each lightning scene's first flash comes 0.3 seconds before its thunder (the intro lasts about 9 seconds longer than with the DOS tunes). The DOS tunes' intro is as it was. With the DOS sound effects DOSBox-X loads the SoundFont for the two tunes alone, and General MIDI music then plays from the SoundFont merged with the effects', as it does with the Amiga effects (6 dB quieter, FluidSynth's own reverb). MT-32 music and the original game (`Fixes_Off.bat`) keep the DOS intro and ending tunes. The older helper (`amiga_music.ps1`) and its WAV files are gone, and **VLC is no longer needed**; Setup removes what the helper left. Setup installs the Python package numpy when the `amiga` folder holds a disk image. The SoundFont grows by 36 MB. **Run Setup.bat again** (or `AmigaMusic_Setup.bat`).
* The intro skips with any key (not Ctrl, Alt, Shift or the lock keys) at any point, also while its music plays (K9); before, a short press of Enter or Space during the intro's scenes was often missed, and only Esc worked there. The ending still skips with Enter, Space or Esc, now also with a short press. **Run Setup.bat again.**
* The tavern's buttons react where they are drawn (D85): the bets and Exit were partly beside their pictures. **Run Setup.bat again.**
* Two secret spots in the tavern's picture (D86; custom rules with `cheat_codes = yes`): gold up to 999, and +10 gold. See CHEATS.md.
* SOUNDS.html, for modders: Setup now makes a page in the game folder where every sound effect can be heard, named as the game names it: the sound ids (the numbers the code asks for) with their sample, rate and part, the sample files, and Rebuilt's substitute sounds. It is made from your own copy of the game, so keep it to yourself; `tools/make_sound_page.py` makes it again. Every sound id has a plain name too (D93), such as "Troll grunts" or "Balok lands after a short jump", beside its code names, with what the name rests on; names that are only a guess are marked "inferred".
* The debug aids `dragon_debug_mode`, `input_log` and `pointer_coordinates` are now in a section of their own, `[Debug]`, at the end of the custom rules file. An older file with them in `[Rules]` still works.

## 0.9.1 – Amiga location music, GM music with Amiga effects and first-menu options

* Pointer coordinates (D84; custom rules, `pointer_coordinates = on`, off by default): a debug aid. On the screens with a mouse pointer (the towns, the tavern, the shops) the pointer's x and y are shown next to it, and the point where a click counts is marked with one pixel. For reporting a button that reacts in the wrong place.
* One press is one gold at the healer and at Mythral the Mystic (D83): a short press on an arrow of the donation screen could move two to four gold. Now a press moves one; held, the amount runs on after a short pause, faster after two seconds, and ten gold a step after four. The Enter that opened the screen no longer clicks anything. **Run Setup.bat again.**
* The troll no longer stands swinging at the air exactly at the edge of its reach; and outside co-op it no longer stands idle when knight 1 is dead (K43). **Run Setup.bat again.**
* General MIDI music with the Amiga sound effects (D82): the effects and the music now have switches of their own. `AmigaSound_On.bat` and `AmigaSound_Off.bat` keep the music that is chosen, and `Music_AdLib.bat` and `Music_GM.bat` keep the effects, so GM music can play together with the Amiga effects. MT-32 still cannot: `Music_MT32.bat` turns the Amiga effects off, and `AmigaSound_On.bat` with MT-32 music switches it to AdLib; both say so. With GM music the two play from one SoundFont, the GM SoundFont merged with the effects' (`_musicmigamiga_gm.sf2`, made on your machine and made again when either changes), and the music is 6 dB quieter there, so that both suit one mixer level. The GM tunes have a set of their own for it (`_music\gm_amiga`), whose player does not wait for the MIDI interface's answers that the effects would cut off; without the set the game froze when an effect played. With the Amiga disk images the places still play the Amiga's own music. **GeneralUser GS 2.0.3 now comes with the release** (`soundfonts\GeneralUser-GS.sf2`, by S. Christian Collins, under its own license): GM music needs no download, and a first setup without MT-32 ROMs now chooses GM music. A SoundFont of your own at `soundfonts\default.sf2` is still used instead. **Run Setup.bat again.**
* Computer knights are chosen in the first menu (D81): *Players* now goes *1 + CPU* (the start), *2 + CPU*, *3 + CPU*, *4*, *3*, *2*, *1*. With *+ CPU* the knights nobody plays are computer knights as before; *3*, *2* and *1* alone have none, so a campaign can be played by the players' knights only, also without the custom rules. The choice is remembered. With the custom rule `computer_knights = off` the menu offers only *4*, *3*, *2* and *1*. **Run Setup.bat again.**
* New cheat code LOADEDDICE (or LOADEDDIE; D80; custom rules with `cheat_codes = yes`): typed on the map or in the tavern, every throw of the tavern's dice wins until the knight leaves the tavern. Which win comes is still random, at the game's own odds. With D79 the winnings can be spent in town; above `max_gold` they come down as the knight leaves the town.
* A tavern win can be spent in town (D79; custom rules): the dice no longer cut a knight's gold to `max_gold` (150) at once, nor as the tavern is left. The knight can take a big win to the merchant, the healer or the High Temple in the same town, and only as the knight leaves the town for the map does gold above `max_gold` come down to it (only if the gold grew in town; gold the knight brought in stays). The same goes for Math's gold and the merchant's and the High Temple's sales. Without custom rules the game's cap of 150 is as before.
* Hardcore automatic saves (D78; `hardcore_autosave_mode`, on by default, also without custom rules): when a game ends in Game Over and no human player's knight has a life left, the automatic saves (slots 91-100) are deleted, so they serve only to go on with a game that was cut short. Giving up with Esc while a knight still has a life keeps them; your own saves in other slots are never touched. `hardcore_autosave_mode = off` in `custom_rules.ini` keeps them always. **Run Setup.bat again.**
* The secondary button throws a dagger (D77; custom rules): in a fight, right Shift (player 1), left Shift (player 2), N (player 3) or a controller's second button throws a dagger at once, the way the knight faces, with no back + up chord. `secondary_button` in `custom_rules.ini` chooses another move instead: `attack` (the swing), `chop`, `lunge`, `upward_thrust`, `backward_thrust`, `block`, `dodge` or `none`. While GUNSHOT or DARTS is on the button fires or throws whatever the choice; With `none` the button gives no move (GUNSHOT and DARTS too), but ROCKETMAN, LUNAR and the monster codes keep it for their own use whatever the choice. An older `custom_rules.ini` without the line gets the dagger. With three or four players on the keyboard (D70), player 3's secondary button is N or the first controller's second button.
* Gore has four values in the first menu (D76): **Off**, **Less**, **On** and **More**. Less keeps the blood of the hits but leaves out the fatalities and the special deaths (beheadings, knights split in two, the troll's crush, the spear trogg's impaling) and draws every death without blood: a knight that falls leaves no red patch, the Balok's bite and squeeze and the boar's toss are bloodless, as with gore off. `age_rating = K16` now does the same; More is what the cheat code ABACABB gives (three times the blood, every knight's death a death animation). Enter and right go to the next value, left to the one before. The game remembers the last choice and starts with it (at first On; with custom rules `gore` in `custom_rules.ini` sets that first value). The age rating limits the choice: K16 allows Off and Less, K12 only Off; a remembered choice above the limit shows as the highest allowed. `death_animations = off` now means Gore Less: no death animations, but the blood stays (it used to turn the blood off as well). ABACABB still works as before. A save made before this version has the old On/Off switch in it until you start the game anew. **Run Setup.bat again.**
* Movement bar on the map (D75; custom rules, `move_bar = on`): during a knight's turn a white line near the top of the map, centred, shows how far the knight can still go on open ground. It shrinks from both ends as the knight moves, faster through forest, swamp and mountains, and is gone when the turn's movement is spent. `move_bar = off` in `custom_rules.ini` hides it.
* Amiga music in the tavern, at the henge, the wizard's, Mythral's and the healer's (D73; only with `AmigaSound_On.bat` and the images of your own three Amiga disks): these places play the Amiga version's own music instead of the DOS tune. Setup builds it from the disk images into the effects' SoundFont; each of a piece's three or four parts loops by itself, as on the Amiga, and the music stops when you leave. Without the disk images nothing changes. **Run Setup.bat again** (or `AmigaSound_Setup.bat` after Setup).
* The Amiga's drums on the gods' message screen (D74; the same conditions as the music above): the screen shown before a fight or the wizard ("The Gods pause for a moment...") plays the Amiga version's music of that screen, which the DOS game did not have, until the fight starts. **Run Setup.bat again.**
* Amiga sound effects (D72; only with `AmigaSound_On.bat`): the sounds the Amiga plays in twos are there. The mudmen's voice has its second voice, the Guardian dies with one of three screams and its echo, the Guardian's yell is four sounds, a troll grunts twice, and the dragon lands with two thuds. **Run Setup.bat again.**
* Resume a game from the first menu (D71): when automatic saves exist, the first menu shows "RESUME GAME: F11+L" right of Select Knight, and F11+L there loads the newest of them (slots 91-100), without choosing a slot. Your own slot comes back for F11+S at the next turn or fight (in a save made before this version, choose it again under *Capture*; such a save also runs its old code, so after Esc the hint does not come back until you restart). The newest may be a Practice fight's automatic save. Not shown with `save_mode = none`. **Run Setup.bat again.**
* Three players on one keyboard (D70): with 3 or 4 players chosen, player 3 plays with I J K L (up, left, down, right), B (attack) and N (the secondary button), and every player keeps their own keys in every fight: player 1 the arrows and Enter, player 2 W A S D and Tab, player 3 I J K L and B, also when two knights fight each other (the game used to give the keys by position), on the map and on the item screen. **Run Setup.bat again.** A controller works as before for players 1 and 2, and player 3 can also use the first one; a fourth player keeps the game's (the arrows).
* One key press is one step in the first menu (D69): a short press of an arrow key or the joystick could move the cursor two or three lines, or take the number of players from 1 straight to 3, because the menu kept acting on a key for as long as it was held. A held direction still repeats, after about half a second. Enter changes Gore once a press. **Run Setup.bat again.**
* No more faint high whine when the game is quiet, most plainly in the first menu while the Amiga intro music is on (K39): the original game switches the PC speaker on at a pitch nobody hears on a real PC, and DOSBox-X made it audible. The PC speaker is now off in `moonstone-dosbox-x.conf`. The setting comes with the release's `moonstone-dosbox-x.conf`; if you keep your own copy of that file, add the lines `[speaker]` and `pcspeaker = false` to it.
* The Guardian no longer makes knights vanish in co-op (K40): its zap could hide one knight and then another, and a blow on the Guardian while it held a knight left that knight hidden, while the fight went on. The knight it takes now always comes back, also when the hold is cut short. **Run Setup.bat again.**
* Co-op deaths keep the knights' colours (K42): when the Guardian's zap killed a knight, all knights turned black; now only the knight killed is drawn burnt. The boar's toss and impaling show the knight struck in its own colours, not in those of the next knight the boar goes for. **Run Setup.bat again.**
* A Balok no longer makes a knight vanish (K41): when two Baloks grabbed the knight at once, or a Balok grabbed a dagger, the knight could stay hidden for the rest of the fight. **Run Setup.bat again.**
* GUNSHOT (D64): a ball still kills a knight, a ratman or a trogg at once, but any other monster (the trolls, the mudmen, the war beasts, the dragon and the rest) now takes 10 damage a shot, as much as a new knight's overhead chop, instead of dying at once. The number of shots is still the knight's number of daggers. A ball no longer flies over the ratmen: it hits at the height a thrown dagger does. A ball never hits a knight that is dodging (the special defence), whenever the dodge started.
* The dragon's fire can be dodged (D68; custom rules, `anticheese = yes`). In a corner, when the dragon breathed its long fire across the ground, a knight that ran was always caught, above all downwards from the top: the fire hurt as soon as it showed, and the dragon's body (with its fire) refused the knight's steps past it. Now the fire hurts only after a moment, the knight can step past the dragon while it breathes, and the fire follows a knight's depth only a limited, random distance that leaves the far edge clear when it begins near an edge. A knight that starts running within about a third of a second of the fire showing gets away; one that stands is still burnt.
* Amiga sound effects (D67; only with `AmigaSound_On.bat`): every effect stops when a fight ends, so a long sound no longer runs on into the map. The sounds that loop on the Amiga loop here too: the dragon's breath and fire sound for as long as the dragon breathes and the mudmen's mud (very quiet) for the whole fight. The lions' den after a Balok's roar loops as well, until other sounds take its voice (the roar comes again, lower, if nothing does). Without the Amiga disk images the den is a new sound: a quiet recording of a lion growling low, played in one piece. The old one was far too loud and clicked. The SoundFont grows from about 20 to 27 MB. **Run Setup.bat again.**

## 0.9.0 – Optional Amiga sound effects and DOS sound fixes

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
