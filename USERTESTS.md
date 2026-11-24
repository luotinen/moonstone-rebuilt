# Moonstone Rebuilt – tests for the player

One checklist of everything that needs a human to play it. Tick as you go:

- `[ ]` not tried yet
- `[x]` tried, works
- `[*]` tried, there is something to report (write a short note after the line: what you did, what you saw)

Each task has its own section, named by its task code (D = improvement or fix, K = co-op fix; the same codes as in
`FIXES.md`), newest first. A task that changes something you can see adds its section here.

## How to start a test

Testing items found in lair chests? With `cheat_codes = yes`, type SKIPCOMBAT on the map: every lair your knight enters
opens its chest at once, as after a won fight (D122). Type it again for real fights.

1. Use the dev install `R:\Claude\Moonstone\rebuilt` and start it with `Start.bat`.
2. Always start a **new game**. Never load an old save or a DOSBox-X state: they carry the old code and make a fixed
   thing look broken.
3. After you change `custom_rules.ini`, run `Custom_rules_on.bat` and restart DOSBox-X.
4. After a fix that says "run Setup.bat again", run `Setup.bat` on your install first.

Tests that need a setting say which one. Settings are in `custom_rules.ini` (comments there explain each).

---

## SR4 – SAVEHOOK's overlays: the cheat codes still work (run Setup.bat again)

The cheat codes' work, IDROPPEDMYKEY's screen and LOADEDDICE's throw now live in a new file, `SAVEHOOK.OVL`, which
SAVEHOOK copies into extended memory when DOSBox-X starts. Needs `cheat_codes = yes`.

- [x] Start the game: the DOSBox-X window shows no line "no XMS, or no SAVEHOOK.OVL of this build" before the game.
- [x] On the map, type a map code (WEPL, HOMESICK, ONEMORETURN, now SIRNEVERTIRED): each does what CHEATS.md says, as before.
- [x] On the map, IDROPPEDMYKEY: the screen of who holds each key, fire, the map again, the lairs with keys glow.
- [x] In the item screen, an item code (IDKFA, PUTARINGONIT): the items come, max HP follows.
- [x] Type a fight code on the map (IDDQD or another from CHEATS.md), then start a fight: the code is on in it.
- [x] In the tavern, LOADEDDICE, then the dice game: every throw wins, until you leave.
- [x] Type IDROPPEDMYKEY, end the turn, and on your next turn press F11+S (a save). Close DOSBox-X, start the game
      again, press F11+L: the game goes on where it was saved; type IDROPPEDMYKEY and WEPL again: both work.
- [x] Move `SAVEHOOK.OVL` out of the game folder, start the game: the line "no XMS, or no SAVEHOOK.OVL of this
      build: the cheat codes are off" shows, and the game plays normally without cheat codes (autosaves still work).
      Put the file back (or run `Custom_rules_on.bat`) and start again: no line, codes work.

## D95 – Amiga effects: the tavern's dice and the henge's thunder (run Setup.bat again)

Needs the Amiga sound effects on (`AmigaSound_On.bat`; the dev install has them on). Nobody but you can listen to these.

- [ ] Tavern, play the dice game: each roll rattles (a wooden dice rattle, a few quick ones in a row, not always
      at the same pitch) instead of the old thud. Also with General MIDI music (`Music_GM.bat`).
- [ ] Leave the tavern and walk on: the sounds after it (the menu click, a fight's sounds) play as before.
- [ ] Go to Stonehenge with a magic item (a potion or a scroll) and offer it: during "The druids prepare for the
      ritual" a thunder clap sounds once, at the lightning, over the music. (Only with the SoundFont made from your
      Amiga disk images, as in the dev install.)
- [ ] The thunder without the disk images (`sounds/thunder.wav`): with AdLib music, in `rebuilt\_music\amiga` rename
      `amiga.sf2`, `amiga.music` and `amiga.tunes` (for example to `amiga_disks.sf2`, `.music_off`, `.tunes_off`)
      and copy `amiga_dos.sf2` to `amiga.sf2`. Offer at Stonehenge: one thunder clap (a bright crack and a rough
      roll, about 1.5 s), about as loud as with the disks; the henge has no music then. Rename the three files back.
- [ ] With the DOS sound effects (`AmigaSound_Off.bat`): the dice thud and the silent henge are as they were.

## D94 – The game no longer hangs at the end of a fight (restart DOSBox-X)

Your saves 3 and 4 and every DOSBox-X state from today carry the old SAVEHOOK.COM in memory: loading one brings the
hang back. Start a new game.

- [ ] Win a lair fight: the chest screen comes, the game goes on to the map.
- [ ] Lose a fight (your knight dies): the knight's item screen comes, the game goes on.
- [ ] Play several fights in a row (and one with two or more knights): each ends normally, and the map does not run
      faster or slower after a fight than before it.
- [ ] After you have played a little, start DOSBox-X again: the first menu shows the Resume Game hint and F11+L
      loads the newest automatic save (one made since the restart, with the new code).

## D93 – Plain names on the sound page

Open `R:\Claude\Moonstone\rebuilt\SOUNDS.html` in a browser (made again on 15 Nov 2026; nothing to set).

- [ ] The first table, Sound ids, has a Sound column right after the play button: every row has a plain name
      ("Troll grunts (3 of 7)", "Dragon's fire roars (loop)"), some marked "inferred". Id, Sample and Amiga follow it.
- [ ] Type `troll` in the filter: the troll's rows stay, among them the grunts 136-142 and the club 135. Type `inferred`: only the
      guessed names stay.
- [ ] Play a few named sounds you know from the game (a trogg's roar 56, a ratman's scream 91, the Balok's landing
      45 or 47): the name fits what you hear. Write any name that is wrong after the line.
- [ ] In the Samples table, hold the pointer over an id number in "Played by the ids": its plain name shows.

## D92 – Horses v2: switching off, town stock, the Armoured horse (run Setup.bat again)

Custom rules on, `horses = on`, `merchant_selling = on`. Gold for horses: HESOYAM on the map (`cheat_codes = yes`).

- [ ] Buy a horse, then open the knight's item screen on the map and click the horse: it turns grey. Move on the
      map: the helmet shows (no horse), the knight goes as far as on foot, and rough ground is slow as on foot. With
      plate or battle armour the knight moves less than with the horse on (the armour's penalty is back).
- [ ] Click the grey horse: its colours come back, and on the map the horse shows and moves as before.
- [ ] At the merchant, click your own horse (on or grey): it is sold for half its price, as before. A horse bought
      after that is in colour (on).
- [ ] With `merchant_selling = off`, clicking your own horse at the merchant switches it off and on instead.
- [ ] Without a horse, enter the towns several times: the brown horse is for sale about 3 times in 4, the light one
      about every other time, never the white horse or a level-4 horse.
- [ ] With a brown horse: brown always, light usually, the white horse about every other time, a level-4 horse now
      and then. With a white horse: the first three always, a level-4 horse about one time in four. Each horse is
      always in its own place in the bottom row, with gaps where none is for sale.
- [ ] With a level-4 horse: all four slots are full; over several visits the fourth one is the black charger, the
      dappled horse and the armoured horse alike. Leaving the merchant and coming back in the same visit keeps the
      same horses.
- [ ] The armoured horse looks fully armoured (steel plates, a trim in your colour) on the goods panel, on your panel
      and on the map while moving; its hover says "Buy Armoured horse for 80 GP". The former armoured horse is now
      called "White horse".
- [ ] Buy the armoured horse with a full-HP knight: the item screen's maximum HP is 20 more, the current HP not yet;
      it heals up to the new maximum as usual. Switch the horse off: the maximum goes 20 down and HP above it come
      down to it. Switching off and on again does not heal.
- [ ] Sell the armoured horse at the merchant: the maximum goes 20 down at once on the panel.
- [ ] Your own `custom_rules.ini` (with the older `armoured_horse_*` lines): change `armoured_horse_price` to 55,
      run `Custom_rules_on.bat`: the White horse costs 55. Set it back afterwards.

## D91 – Five-digit money (run Setup.bat again)

For five digits: custom rules on with `cheat_codes = yes` (the default), type HESOYAM on the map: +20 000 gold. For
four digits: in the tavern, click the top-left spot of the picture (gold up to 999), then the second spot (x 189-229, y 50-69)
(+10 each click), see CHEATS.md.

- [ ] Tavern, before any cheat (for example 10 or 150 gold): the gold sack top right is wider than before and looks
      like a sack; the number sits in the middle of its dark box.
- [ ] Tavern with 20 000 or more gold: all five digits are inside the dark box, in its middle. Bet and roll: the
      dice result says "You now have" with the whole gold (not 999).
- [ ] Tavern with four digits (999 + 10 = 1009): the number fits and is in the middle; the dice still roll and pay
      as before.
- [ ] Mythral the Mystic with five-digit gold: both sacks at the bottom are wider; "Your Gold" (left) and
      "Donation" (right) show five digits inside their boxes, in the middle; the right sack is fully on the screen.
      Hold the right arrow until the donation has four and five digits: it counts on normally (no jumps back to a
      small number) and OK gives that donation.
- [ ] The healer with five-digit gold: the same two sacks (the healer's colours) with five digits, in the middle;
      a donation of four digits works.
- [ ] The knight's item screen (opened on the map) with five-digit gold: the gold shows all five digits.
- [ ] Set `gold_min = 1000` and `gold_max = 1000` in `custom_rules.ini` (run `Custom_rules_on.bat`), new game: a lair
      with gold shows "1000 gp." on the item screen (not garbage), and Math's gift says "1000 gold.". Set them back to
      10 and 31 afterwards.

## D90 – The finishing blow (run Setup.bat again)

- [ ] Gore On, troll fight (first menu key 9): let the troll beat you. As you sink down, the troll steps up and
      crushes you with its club from above (no push); your knight lies in a pool of blood, then the fight ends.
- [ ] Gore More (or ABACABB): the same as On, with the extra blood.
- [ ] Gore Less: troll fight, let the troll beat you: no finishing blow, the troll stands still (or walks off); the
      knight falls the plain way, the fight ends as before.
- [ ] Gore Off: the same as Less (no finishing blow, no blood).
- [ ] Gore On, wasteland troggs (key 3, the hammer trogg): let them beat you: a trogg comes and gives you its
      finishing blow (its death animation plays; note which one).
- [ ] Gore On, axe troggs (key 4): an axe trogg comes and takes your head off.
- [ ] Gore On, spear troggs (key 6): the spear trogg comes and spears you with its own forward thrust (not a
      swing), and the long thrust death plays: the spear goes through the middle of the body and out the other
      side; the knight never goes up on the spear. Try it with the trogg in front of you and behind you.
- [ ] Gore Less and Off with each trogg fight (keys 3, 4, 6): no finishing blow, the troggs stand.
- [ ] A troll or trogg far away when you fall (fall at the screen's edge): the knight stays sunk down while the
      monster walks over, up to about 5 seconds; if it does not get there in time the knight lies down and the fight
      ends as before.
- [ ] In every finishing death the knight keeps its own colours (blue, green, orange, purple) from the first frame
      to the last, with the knight's own armour look: check the troll crush, the trogg head-off, the split and the
      spear for each colour you can (co-op gives knights 2-4).
- [ ] Co-op, 2 players (Players 2, key 9 troll or key 4 axe troggs): let one knight fall while the other still
      fights: the fallen knight stays sunk down (waiting) and the monsters go on fighting the other knight; then let
      the second fall: the monsters finish both fallen knights one after the other, each in its own colours, and
      only then the fight ends.
- [ ] Co-op, both fall close together: both get their finishing blow, the fight does not end after the first.
- [ ] Co-op with Gore Less: no finishing blow; the fight ends when both knights are down, as before.
- [ ] `death_animations = vanilla` in custom rules, Gore On: the troll still crushes, the axe and hammer troggs
      behead, the spear trogg's thrust still gives the long thrust death, not the lift (in the knight's own colours
      in co-op).

## D89 – The knight's sword when pushed over (run Setup.bat again)

- [ ] Troll fight (first menu key 9) with a weapon other than the long sword (for example a broadsword or the Sword
      of Sharpness): let the troll push you (its low shove). In the three pictures of the knight thrown back and
      lying, the sword has the weapon's own colour (the same as when you swing it), not the armour's.
- [ ] The same push with the knight facing left and facing right: the sword lies exactly where it lay before (in the
      hand, no second sword or gap beside it).
- [ ] Type LIGHTSABER in the troll fight and let the troll push you: the sword in the push is the lightsaber (white
      line, dark glow), as in your swings.
- [ ] Dragon fight: let the dragon's fireball hit you without killing you: the knight's sword in the knock-down has
      the weapon's colour, and with LIGHTSABER the lightsaber's look.
- [ ] A push or fireball that kills: the knight falls and dies as before (no hang, the fight ends normally).
- [ ] Co-op or two knights (the other look): the second knight's sword in the push has its weapon's colour too.

## D88 – Riposte against the troll and the troggs (`timed_defence = on`)

- [ ] Troll fight (first menu key 9): when the troll raises its club for the blow from above, press fire + towards the
      troll (the lunge) at once: the lunge comes out fast, hits the troll first and the troll's blow never lands.
- [ ] The same against the troll's push (the low shove): the lunge is the ordinary, slower one (no riposte).
- [ ] Trogg fights (keys 3, 4, 6): the same riposte against an axe or hammer trogg's blow from above; the spear
      trogg (it only thrusts) gives no riposte.
- [ ] With `timed_defence = off` the lunge is the game's own against both.

## D87 – Amiga intro and ending music (needs Amiga disk 1 and `AmigaMusic_On.bat`)

- [ ] Start the game with `AmigaMusic_On.bat` set: the intro's tune starts with the first picture and the lightning
      flashes fall on the beats, not seconds before or after.
- [ ] Let the ending play (or skip to it): its tune plays in step with the pictures and stops when you skip.

Step 7, the host player retired (15 Nov 2026):
- [ ] `Music_AdLib.bat`, `AmigaSound_Off.bat` (it says "Intro and ending music: Amiga"), `Start.bat`: the intro plays
      the Amiga tune, in step and about as loud as with the Amiga effects; then the game's AdLib music and the DOS
      sound effects as before.
- [ ] `Music_GM.bat` with the DOS effects, `Start.bat`: the intro plays the Amiga tune; the GM music in the game sounds
      as it does with the Amiga effects (a little quieter and with another reverb than GM before), and the DOS
      effects are not drowned.
- [ ] `Music_MT32.bat` (needs the ROMs), `Start.bat`: the Roland intro tune plays, and no other music beside DOSBox-X.
- [ ] `AmigaMusic_Off.bat` with GM music and the DOS effects, `Start.bat`: the DOS GM intro tune, and GM music as it
      was before step 7.
- [ ] In no case does music play outside DOSBox-X (no second player, no music in the Windows volume mixer beside
      DOSBox-X).

## D86 – Two secret spots in the tavern (`cheat_codes = yes`)

- [ ] In the tavern click the spot in the picture at the left (x 9-37, y 32-56, between the buttons): your knight gets
      at least 999 gold.
- [ ] Click the other spot (x 189-229, y 50-69): +10 gold each click, never above 32767.

## D85 – Tavern buttons where they are drawn (run Setup.bat again)

- [ ] In the tavern click each of the five bet buttons: each reacts when the pointer is on its picture, not beside it.
- [ ] Click Exit on its picture: it leaves the tavern. The pointer can reach it at the bottom.

## D84 – Pointer coordinates (debug aid, `pointer_coordinates = on`)

- [ ] With the setting on, the pointer's x and y are shown next to it on the tavern screen. With it off nothing is shown.

## D83 – One press, one gold in the donation screen

- [ ] In the healer's donation screen tap left/right once: exactly one gold moves per short tap.
- [ ] Hold right/left: it waits, then repeats, then speeds up. Do the same at Mythral the Mystic. OK and Exit leave at
      the first press.

## D81 – Computer knights chosen in the first menu

- [ ] In the first menu step Players through *1 + CPU, 2 + CPU, 3 + CPU, 4, 3, 2, 1*; the text fits on screen.
- [ ] Start a campaign with "2 + CPU": two humans and computer knights. With "2" alone: only the two humans.
- [ ] Restart the game: the Players choice is remembered.
- [x] Resume Game hint (D71/D78), see below.

## D80 – LOADEDDICE (`cheat_codes = yes`)

- [ ] Type LOADEDDICE on the map, enter the tavern and roll: every roll is a win. The code also works typed in the
      tavern. After you leave the tavern it is off again.

## D79 – `max_gold` when leaving the town

- [ ] Set `max_gold = 150`. Win a lot with the dice (use LOADEDDICE): you can spend it in the town's shops.
- [ ] Leave the town: gold above `max_gold` is cut to `max_gold` (or to what you brought in, if that was more).

## D78 – Hardcore automatic saves

- [x] Autosave: a new `.sav` appears in `save` during play.
- [x] Game Over puts back the last automatic save (Resume Game works, also from the main menu).

## D77 – The secondary button's move (`secondary_button = dagger`)

- [x] In a fight the secondary button (right Shift for player 1) throws the dagger. Other moves can be chosen in the ini.

## D76 – Gore with four values

- [x] The first menu's Gore switch goes Off, Less, On, More, and the choice is remembered between starts.
- [ ] Less: knights die without death animations, beheading or crushing, blood stays.
- [ ] More: three times the blood and a death animation at once.

## D75 – Movement bar on the map (`move_bar = on`)

- [ ] On the map a white line in row 2 is as wide as the distance your knight can still go; it shrinks as you move.
- [ ] The bar stays visible through the whole turn (an earlier version hid it after the first frame).
- [ ] With a horse the bar is longer; in forest or swamp it shrinks slower per distance than on open ground; it is
      hidden while the Hawk flies.

## D71 – Resume Game hint

- [x] The first menu shows "RESUME GAME: F11+L" when an automatic save exists; F11+L loads the newest.

## D70 – Three players on one keyboard

- [x] With 3 players each has its own keys: arrows + Enter, W A S D + Tab, I J K L + B.

## D69 – One key press, one step in the first menu

- [x] A short press moves exactly one step in the first menu.

## D68 – The dragon's fire can be dodged (`anticheese = yes`)

- [x] In a corner, running away from the long fire lets you dodge it, also downwards from the top.

## D64 – GUNSHOT cheat code

- [x] Earlier version: balls hit ratmen and never hit a dodging knight.
- [ ] Latest version: a ball kills a knight, a ratman or a trogg at once; any other monster (troll, mudman, dragon…)
      takes 10 damage a shot.

## D63 – Dagger throw no longer looks like a pistol shot

- [x] After the throw the hand is empty and the knight does not hold a dagger.

## K43 – The troll swung at the air (run Setup.bat again)

- [ ] Stand still in a troll fight: the troll steps in and chops, never swings at the air at a distance. With knight 1
      dead the troll still attacks the knight that lives.

## K42 – Co-op colours of a knight's death (run Setup.bat again)

- [ ] In a co-op lair with the Guardian, let it burn one knight: the other knights keep their colours. A boar's toss
      shows the knight in its own colour.

---

Not listed: K39-K41 (whine, Guardian and Balok hiding a knight) were fixed earlier and have no open test.

## D96 – Cheat codes: SIRNEVERTIRED, a fuller IDKFA, WEPL in the item screen

Custom rules on, `cheat_codes = yes`.

- [ ] On the map, type SIRNEVERTIRED: no movement is used up this turn (as ONEMORETURN did); E ends the turn.
- [ ] On the map, type ONEMORETURN: nothing happens (the old name is gone).
- [ ] In the item screen (Space on the map), type IDKFA with an empty inventory: 4 healing potions, 4 Gems of Seeing, 3 Rings of Protection, 4 Talismans of the Wyrm and 2 of every scroll show, with the Sword of Sharpness, keys, Moonstones, battle armour and the daggers in one row running off the right edge.
- [ ] After IDKFA (and KONAMI's 99 lives), click a healing potion and a scroll in the same item screen: they can still be used (before, the daggers' icons could take every clickable slot).
- [ ] In the item screen, type WEPL: the four keys appear. WEPL on the map still gives them too.

## D97 – Armour enchantments in lair chests

Custom rules on, `armour_enchantments = on`, `armour_enchantment_chance = 100`.

- [ ] Open a lair's chest: an armour enchantment is there ("Enchantment of ..."), below the sword's place; before
      this fix they came only in the dragon's hoard.
- [ ] Click it: your armour (padded armour too) gets it; the chest's icon goes away.
- [ ] With `armour_enchantment_chance = 10` (the default): over several lairs about one chest in ten has one.

## D98 – Enchanted swords and armours look different (violet)

Custom rules on, `sword_enchantments = on`, `armour_enchantments = on`; for quick tests set both
`..._enchantment_chance = 100`.

- [ ] Open a lair's chest: the sword enchantment is your own sword's picture in violet, and the armour enchantment
      your own armour's picture in violet; the chest's other items look as before.
- [ ] Take both: on your item screen (Space) the sword and the armour are violet and named "<item> of <enchantment>".
- [ ] Start a new game and take an armour enchantment while still in padded armour: the brown padded armour turns
      violet and is named "Padded armour of ...".
- [ ] Buy a better sword or armour at the merchant: the new one is plain (grey or brown) again.
- [ ] Rebirth: lose a fight in enchanted Rebirth armour: after Stonehenge the armour is plain again.
- [ ] Look at another knight's items (both panels): its enchanted gear is violet, plain gear is not.
- [ ] The dragon's hoard: an enchantment there shows in violet as in a lair's chest.
- [ ] In a fight, swords and armours look as before (D31's colours); the map, the merchant's goods and the other
      item-screen pictures (potions, gems, rings, gold) keep their colours.

## D99 – Mithril also gives movement

Custom rules on, `armour_enchantments = on`, `armour_enchantment_chance = 100`.

- [ ] Note a knight's movement bar in padded armour, then take Mithril onto it: the next turn it moves clearly further
      (as with 2 more Endurance; the Endurance shown on the item screen does not change).
- [ ] In battle armour without Mithril the knight is slow; with Mithril it moves further than in plain padded armour.
- [ ] With a horse (`horses = on`): Mithril still adds the same extra; switch the horse off on the item screen: the
      extra is still there once, not twice.

## D100 – Enchanted starting gear changes places after a won fight

Custom rules on, two or more human knights, `sword_enchantments = on`, `armour_enchantments = on`.

- [ ] Knight A in padded armour of (say) Danu loses a fight to knight B, also in padded armour: on B's loot screen
      A's padded armour is violet; click it: B now has "Padded armour of Danu", A has B's padded armour (plain, or
      with B's own enchantment if it had one).
- [ ] The same with an enchanted long sword when the winner also has a long sword: they change places.
- [ ] Winner in chain mail (or better) and loser in enchanted padded armour: clicking the loser's armour does nothing,
      as before. The same for a winner with a broad sword, a claymore or the Sword of Sharpness.
- [ ] A loser with a plain padded armour or long sword: nothing to take, as before.
- [ ] A computer knight that wins against your enchanted padded knight takes no armour (as before) and your knight
      keeps its enchantment.

## D101 – Special potions (the base: Danu, Full Restoration, Strength, Endurance, Constitution, Life)

Custom rules on, `[Treasure] rare_potions = on` (an older `custom_rules.ini` without the key behaves as `on`). For the
chest tests set `rare_potion_chance = 100`. Might and Fire Resistance came in D102 (below); the other four special
potions came later: Recall, Invisibility and Levitation in D103, Speed in D104.

- [ ] Open lair chests (and the dragon's hoard): each shows a special potion first in its potion row, in its own
      colours, the chest's Potions of Healing after it; hovering over it shows "Potion of <name>".
- [ ] Each of the six looks different from the Potion of Healing and from each other: Danu light blue with lilac and
      a violet neck, Full Restoration deep blue-violet with a white neck, Strength red, Endurance blue-violet and
      Constitution dark green each with a gold streak and neck, Life green with a red streak and neck.
- [ ] Click the chest's special: it moves to your knight's panel, place 1 (the Potion of Healing moves one place
      right). Take three this way: they fill places 1-3 and the Potion of Healing is in place 4; a chest then shows
      no special potion (it keeps it) until one is drunk.
- [ ] With one special and four Potions of Healing: three healing icons show; drink one and the next takes its place.
- [ ] Two knights on the item screen (a loot screen where potions can be taken): take a special from the other knight
      into a free place: its other specials move up. With three already: each click puts the new one in place 1,
      moves your others one place on and gives your third to the other knight's panel.
- [ ] Drink Danu at low HP: HP rises by the max HP (the panel may show it above the max, at most twice the max), one
      more life (up to max_lives), the ratmen's disease gone. End the day and press E to rest: HP above the max stays
      until damage brings it down; a Potion of Healing, the healer, the home village and Stonehenge do not lower it
      (the healer takes no money then).
- [ ] Drink Full Restoration: full HP, lives up to max_lives, no disease.
- [ ] Drink Strength, Endurance and Constitution: each ability +1, shown as 6 when it was 5 (more than 5 is allowed,
      up to 9); Constitution raises the max HP, Endurance the movement.
- [ ] Drink Life: the max HP and the HP both rise by 20 (`life_potion_hp`), and the max stays higher for good.
- [ ] Specials cannot be drunk on a chest or loot screen, at the merchant, in the High Temple or at Stonehenge (a click
      there does nothing).
- [ ] (D105 retest) In the High Temple a click on a special now sells it and at Stonehenge offers it (see D105); on
      chest and loot screens and at the merchant a click still does not drink it.
- [ ] Lose a fight with lives left: the special potions stay. Lose the last life: they are gone.
- [ ] (D105 retest) Lose the last life to a monster or the dragon: they are gone; to a computer knight: it takes them
      (see D105).
- [ ] (D106 retest, replaces the two lines above) Lose a fight with lives left to a computer knight or the dragon: it
      may take your first special potion as its one item (see D106). Lose the last life: the winner takes what it has
      room for, the rest stays at your grave; to a monster, the Guardian or the disease: all of them stay at the grave.
- [ ] `rare_potions = off`: no special potions anywhere, the potion row as in the game.
- [ ] Without XMS memory (or with the SAVEHOOK.OVL missing): the start message says the cheat codes and special potions
      are off, and none appear.
- [ ] (D102 retest) Chests now also give Might (red, black streak and neck) and Fire Resistance (a flame, orange over
      red): all eight are found and each looks different; drinking one of the six above still works as before.
- [ ] (D104 retest) Chests now also give Speed (pale gold): all twelve are found, each looks different, and hovering
      over Speed shows "Potion of Speed".

## D102 – Special potions: Might and Fire Resistance (for the next fight)

Custom rules on, `rare_potions = on`, `rare_potion_chance = 100` to find them quickly. Both are drunk on the knight's
own item screen (the map's item key) and work in its next campaign fight only.

- [ ] Drink Might on the map, then fight in a lair: your blows hit harder (a weak knight clearly so) and push the
      monster back a little each time they land; the push never takes it past the screen's edge. The next fight is
      normal again.
- [ ] Might against the dragon and against the Guardian: harder blows, no push. A mudman in the mud or holding a
      knight is not pushed either.
- [ ] Might in a fight against another knight: the other knight is pushed back a little by each blow that lands.
- [ ] Drink Fire Resistance, then meet the dragon: its fire takes 1 HP (also with or without Talismans of the Wyrm or
      Fireproof armour); its bite and claws hurt as before. The next fight is normal.
- [ ] With Might waiting, click a second Might: nothing happens and it stays in its place; Fire Resistance can be
      drunk beside it. After the fight the second Might can be drunk.
- [ ] Drink Might, then avoid the fight (the Scroll of Protection when another knight attacks): Might still works in
      the next fight that happens.
- [ ] Lose (or leave) the fight Might was drunk for: Might is used up all the same.
- [ ] (D103 retest) Chests now also give Recall, Invisibility and Levitation: Might and Fire Resistance still work as
      above.
- [ ] (D104 retest) Might, Fire Resistance and Speed drunk together before one fight: all three work in it, and all
      three are used up by it.

## D103 – Special potions: Recall, Invisibility and Levitation (the map potions)

Custom rules on, `rare_potions = on`, `rare_potion_chance = 100` to find them quickly. Each is drunk on the knight's
own item screen (the map's item key), Recall and Invisibility also on the attack prompt's screen.

- [ ] The three look different from the others and from each other: Recall green, Invisibility black in the middle
      and white outside, Levitation white above and black below; hovering names them.
- [ ] Drink Recall far from home with low HP: the knight is at its home village with full HP (and lives as the home
      village gives them, `village_heal`), and its turn ends at once. Drunk at home it works the same.
- [ ] Drink Recall during the Hawk's flight (if the item key works then): the knight is at home and the flight ends.
- [ ] Attacked by another knight while holding Recall: the attack prompt opens (also without a Scroll of
      Protection); drink Recall there and leave the screen: no fight, the attacked knight is at home, and the turn of
      the knight whose turn it is ends.
- [ ] Drink Levitation on open ground: nothing changes yet. Walk into forest or mountains: no slowing there, to the
      end of that turn; the next turn is slowed as usual. On a horse it works the same.
- [ ] Drink Levitation while standing in forest: no slowing at once, to the end of the turn.
- [ ] With Levitation waiting (or working), click a second one: nothing happens, it stays in its place.
- [ ] Drink Invisibility: in the other knights' turns its map icon (and horse) is not drawn; in its own turn it is.
- [ ] While invisible, enter a lair alone: no fight, the chest opens at once (no XP), and after it the knight shows
      again on the map; the lair stays (its monsters too), and the next lair is fought as usual.
- [ ] While invisible, enter a lair together with other knights (co-op lairs): the fight happens as usual and the
      knight stays invisible.
- [ ] While invisible, another knight walks into it: no fight and no screen; the knight shows again. The same when the
      dragon attacks it: no fight, the dragon flies off, the turn ends.
- [ ] Holding Invisibility (not drunk), attacked by a knight or the dragon: the prompt opens; drink it there and leave
      the screen: no fight (the dragon flies off), and the knight is not invisible afterwards.
- [ ] With Invisibility waiting, click a second one: nothing happens, it stays.
- [ ] At the attack prompt Levitation cannot be drunk (the click does nothing); Danu and the others still can.
- [ ] Might or Fire Resistance waiting when a fight is avoided this way: they still work in the next fight.

## D104 – Special potions: Speed (for the next fight)

Custom rules on, `rare_potions = on`, `rare_potion_chance = 100` to find it quickly. Speed is drunk on the knight's own
item screen (the map's item key) or at the attack prompt, and works in its next campaign fight only. Only play can tell
whether it feels right: the Unicorn tests measure frames and pixels, not how it looks.

- [ ] Drink Speed, then fight in a lair: the knight walks clearly faster (its strides are half again as long) across
      and up and down the ground; it still stops at the screen's edges and at the ground's borders, and does not walk
      through monsters.
- [ ] With Speed, attack with each move (swing, overhead chop, lunge, upward and backward thrust, dagger throw): each is
      a little faster (about a fifth), and the blows still land and hurt as without Speed.
- [ ] With Speed, watch the attacks closely: no frame shows the knight missing or flickering; note any jerk you see.
- [ ] With Speed, block and use the special defence: they look and time as without Speed (timed defence's windows the
      same), and a timed block of your own still staggers an attacker.
- [ ] With Speed, get staggered by a timed block (timed defence on): the stagger lasts as long as without Speed.
- [ ] With Speed, lose the fight: the knight's fall and death look as without Speed, and the finishing blow can still
      be given to it.
- [ ] Speed against the dragon and against the Guardian, and in a fight against another knight: faster walking and
      attacks there too.
- [ ] The next fight after the one Speed was drunk for: normal speed again. A practice fight neither uses it nor ends
      it (it still works in the next campaign fight).
- [ ] With Speed waiting, click a second Speed: nothing happens and it stays in its place. Might and Fire Resistance
      can be drunk beside it.
- [ ] Drink Speed, then avoid the fight (the Scroll of Protection or Invisibility when attacked): Speed still works in
      the next fight that happens.

## D105 – Special potions: computer knights, the High Temple, Stonehenge

Custom rules on, `rare_potions = on`, `rare_potion_chance = 100` to find them quickly; for the computer knight tests a
game with computer knights (Players *1 + CPU* or the like) and a knight on its last life (`lives = 1` for it in
`custom_rules.ini` makes this quick).

- [ ] Holding special potions on the last life, lose a fight to a computer knight: it takes everything, the special
      potions too (up to three; with fewer free places it takes fewer).
- [ ] Later beat that computer knight with another knight: the loot screen shows its special potions first in its
      potion row, in their colours; take one into a free place, and with three already each click cycles (the swap
      rule), as from a human knight.
- [ ] The computer knight never drinks them (a Might or Speed it holds does nothing in its fights), and it still
      takes none from chests.
- [ ] Lose a fight to a computer knight with lives left: it takes one item as before, never a special potion; yours
      stay.
- [ ] (D106 retest, replaces the line above) Lose a fight to a computer knight with lives left: it takes one item, which
      can be your first special potion (see D106).
- [ ] Lose the last life to the dragon holding special potions: the dragon does not take them; they are gone.
- [ ] (D106 retest, replaces the line above) Lose the last life to the dragon holding special potions: it takes the
      first into its hoard (if its place is free); the others stay at your grave (see D106).
- [ ] High Temple: click a special potion on your knight's panel: it is gone and the gold rises by what a Potion of
      Healing sells for there (half the Temple's price, 10 gp by default); your Potions of Healing and the Temple's
      stock stay the same, and the Temple has no special potion for sale afterwards. With two or three, the one after
      it moves up.
- [ ] Stonehenge: offer a special potion: the offering is accepted as with a Potion of Healing (a life up to the
      maximum, full HP, the disease cured; HP above the max after Danu stays), and the potion is gone.
- [ ] With special potions on the panels: the horse switch (click your own horse), taking enchanted swords and
      armour, and the starting gear swap (D100) work as before, and clicking an empty special place does nothing.
- [ ] (D108 retest) The same with special rings on the panels as well: clicking an empty special ring place does
      nothing, the potions' clicks work as before.

## D106 – The loot rules and the dead knight's cross

Custom rules on, `dead_knights_cross = on` (the default), `rare_potions = on`, `rare_potion_chance = 100`; a game with
computer knights (Players *1 + CPU* or the like) and `mode = permadeath` for the human knight, `lives = 1` for it to reach
the last life quickly. The map still shows the game's grey grave (the gold look is D107).

- [ ] Hold two special potions and no item higher in the order than the Potion of Healing (no Moonstone, key, Sword of
      Sharpness, Ring of Protection, Talisman of the Wyrm, Scroll of Acquisition, Protection, the Hawk or the Wyrm); lose a fight with lives left to a
      computer knight: it takes only your first special potion (your Potions of Healing and the second special stay).
- [ ] The same while holding a Ring of Protection or a Talisman: it takes that item (the game's way), the potions stay.
- [ ] (D108 retest) The same while holding a special ring: it takes the special ring (it comes just before the Ring of
      Protection in the order), the potions stay (see D108).
- [ ] The same against the dragon: half the gold, then one item; with no higher item and its hoard's potion place free it
      is your first special potion (slay the dragon later to find it in the hoard).
- [ ] Lose the last life to a computer knight while holding gold, daggers, a better sword or armour (an enchanted one
      shows it), items, keys and three special potions: it takes all the gold (up to `max_gold`), daggers up to 10, the
      better sword and armour (its own worse ones are left to you), all items, keys and Moonstones, and the potions it
      has room for.
- [ ] Walk onto that grave with another human knight: the loot screen opens with no fight and no one-pick limit: take
      what was left (the computer knight's old sword or armour, gold over `max_gold`, extra daggers, potions), and leave
      the rest; come back later: it is still there.
- [ ] Beat that computer knight later: its panel shows the enchanted sword or armour it took by name, and you take
      the enchantment with the item.
- [ ] Lose the last life to the dragon: half the gold, all items, keys and Moonstones go to the hoard; your sword
      (also the Sword of Sharpness), armour and daggers stay at the grave (their enchantments go to the hoard if its
      place is free); one special potion to the hoard, the others at the grave.
- [ ] Die to monsters in a lair, the Guardian or the disease: everything is at the grave; take it all with another
      knight.
- [ ] (D109 retest) The same while holding a Ring of Undying: no grave; the knight is back in its home village with 1
      life and the ring is gone (see D109).
- [ ] A computer knight that walks onto a grave takes what is there by the same rule.
- [ ] `mode = reincarnation`: lose the last life holding special potions, an enchanted sword and a horse: the reborn
      knight has none of them (start values). `mode = respawn`: it comes back with what the winner left.
- [ ] `dead_knights_cross = off`: as before D106 (with lives left never a special; at the last life a computer knight
      takes no gold, daggers or armour, up to three special potions; the dragon no special). Speedrun mode: the same.
- [ ] (D107 retest, corrects the dragon line above) Lose the last life to the dragon while holding the Sword of
      Sharpness: it goes into the hoard (slay the dragon to find it there) and your grave keeps the long sword; if the
      hoard already holds one, yours stays at the grave.

## D107 – The dead knight's cross on the map

Custom rules on, `dead_knights_cross = on`, `mode = permadeath` and `lives = 1` for the knight that is to die, a game
with two human knights (one to die, one to fetch). The colour is to be judged in play: gold should stand out on grass,
forest and rocks and not look like the pink outline or a lair's glow.

- [ ] Die to monsters in a lair while holding gold and items: the grave on the map is a gold cross.
- [ ] Walk onto it with the other knight: the pink outline shows as before; take everything but the sword and armour:
      back on the map the grave is the game's grey one.
- [ ] A grave holding only a better or enchanted sword or armour (and a horse): grey.
- [ ] A grave holding only the Sword of Sharpness: gold (die holding it, take everything else).
- [ ] A grave holding only one of these is gold: a key, a Moonstone, a special potion, a Potion of Healing, a dagger,
      one gold piece.
- [ ] (D108 retest) A grave holding only a special ring is gold too.
- [ ] A computer knight that dies with something left: its grave is gold too; when a computer knight empties a grave,
      it turns grey.
- [ ] IDROPPEDMYKEY with a key at a dead knight's grave: the screen says "<name>'s grave" for it.
- [ ] `dead_knights_cross = off`, speedrun mode, `mode = respawn` or `reincarnation`: the grave is the game's grey one.

## D108 – Special rings: the base and the stat rings (Strength, Constitution, Endurance)

(D121 changes this section's stat-ring line: the item screen's number now shows the ring, with no cap of 9. Test the
shown value with the D121 section.)

Custom rules on, `rare_rings = on`, `rare_ring_chance = 100` to find them quickly (only the three stat rings exist so far);
for the loot tests a game with computer knights and `lives = 1` for the human knight, `mode = permadeath`.

- [ ] Lair chests and the dragon's hoard show a special ring after their Rings of Protection (in the first place when
      there is none), in its own colours: a silver band with a red (Strength), green (Constitution) or blue
      (Endurance) stone; hovering names it ("Ring of Strength" and so on).
- [ ] Take two special rings: they fill ring places 1-2 and one Ring of Protection shows in place 3 (all of them still
      count for max HP); a chest then shows that knight no special ring (another knight with a free place sees it).
- [ ] Two knights on the item screen (a loot screen, or walking onto another human's knight): take a special ring from
      the other knight: into your free place; with two already each click swaps (the new one first, your second goes
      to the other knight).
- [ ] Ring of Strength, Constitution, Endurance: the item screen shows that ability one higher (6 at 5; two of a kind
      +2; never above 9); with Constitution max HP is 10 higher; with Endurance a turn's movement is 2 higher and the
      knight lasts longer in fights; with Strength the blows are harder. Give, sell or offer the ring: all back as before.
- [ ] Mythral (or Math) still raises an ability to 5 when a stat ring shows it as 5 (its real value is 4), and never
      counts the ring.
- [ ] High Temple: click a special ring on your panel: it is gone and the gold rises by what a Ring of Protection
      sells for there; your Rings of Protection and the Temple's stock stay the same, and the Temple has no special ring
      for sale. Stonehenge: offer one: accepted as an offering, the ring is gone.
- [ ] Lose a fight with lives left to a computer knight or the dragon while holding a special ring and a Ring of
      Protection (no Moonstone, key or Sword of Sharpness): the special ring is the one item taken (the dragon's goes to
      its hoard).
- [ ] Lose the last life to a computer knight holding two special rings: it takes those it has room for, the rest stay
      at the grave, which is a gold cross even if only a ring is left; beat the computer knight later and take them back
      from its panel (they did nothing for it).
- [ ] `mode = reincarnation`: the reborn knight has no special rings; `mode = respawn`: it keeps what the winner left.
- [ ] `rare_rings = off`: no special rings anywhere and the ring row is the game's; a `custom_rules.ini` without the two
      keys behaves as `on` with 10 %.
- [ ] (D109 retest) Chests now also hold the Rings of Undying (iron band, gold stone), Vampirism (iron, red) and Absorb
      Soul (iron, lilac); hovering names them.

## D109 – Special rings: Undying, Vampirism, Absorb Soul

Custom rules on, `rare_rings = on`, `rare_ring_chance = 100` (six rings exist now, so a wanted one may take a few
chests); `mode = permadeath` and `lives = 1` for the knight that is to be saved, a game with computer knights for the
fights against knights.

- [ ] Ring of Undying, one life left: lose a fight (a lair's monsters, a computer knight, the dragon): the knight is in
      its home village (where it started) with 1 life and full HP, the ring is gone, and the turn ends as after any
      fight. No grave on the map.
- [ ] The same against a computer knight or the dragon: it takes one item as from a knight with lives left (it can be
      your other special ring, never the Undying ring that saved you); nothing else is lost.
- [ ] Two Rings of Undying: the first death takes one, the next death the other; then the knight dies as usual.
- [ ] With 2 or more lives the ring does nothing (a life is lost as usual, the ring stays).
- [ ] Lose to the Guardian with 1, 2 or 3 lives (it takes three in all): saved with 1 life, only one ring used.
- [ ] The ratmen's disease takes the last life: saved the same way (home, 1 life, full HP, the ring gone).
- [ ] Rebirth armour and a Ring of Undying, last life, a fight lost: Rebirth acts (at Stonehenge, no life lost, the armour
      plain) and the ring stays. `mode = invulnerable`: the ring is never used.
- [ ] `mode = respawn` and `mode = reincarnation`: the ring saves the same way (nothing lost, no respawn).
- [ ] Ring of Absorb Soul: kill another knight (a human's or a computer knight, its last life) in a fight: +1 life,
      never above `max_lives`; also when its grave becomes a gold cross, and in respawn and reincarnation modes.
- [ ] Absorb Soul gives nothing when the loser had lives left, was saved by Undying or Rebirth, or when you visit a grave;
      nor for monsters, the dragon or the Guardian; two rings give +1 only.
- [ ] Ring of Vampirism: each sword blow that hurts a knight, a monster, the dragon or the Guardian gives +1 HP (two
      rings +2), never above max HP; HP above max after Danu stays as it is. A blow that is blocked gives nothing.
- [ ] Ring of Vampirism and thrown daggers: a dagger that hurts a knight (also a computer knight), a trogg or the dragon
      gives +1 HP the same way; a dagger on a knight with Daggerward armour (no damage) gives nothing.
- [ ] Practice fights and computer knights: none of the three rings does anything (a computer knight with an Undying
      ring dies as usual and its ring can be taken).

## D110 – The terrain zones on the map

Custom rules on, `[Map] custom_terrain = on` (the default). The zones are the ones painted with the terrain editor
(`tools/terrain_zones.csv`); the movement bar (`move_bar = on`) shows how much a step costs. On foot, no special rings.

- [ ] The ruin in the big forest (lower left): its ground is open (full speed), the forest around it slows to half.
- [ ] The stone circle inside the red mountains (middle of the map): the mountains around it slow to a quarter, the
      circle itself is open ground.
- [ ] The tower on the brown plain (upper right): open, full speed; the golden rocky hills below it (right side, the
      rocks) slow to half, as swamp does.
- [ ] The lake on the left (below the castle) and the river and swamp at the lower right slow to half; the village with
      red roofs at the lower right edge is open ground.
- [ ] The strip west of the red mountains (upper middle, painted as forest) slows to half.
- [ ] On horseback: the golden rocky hills slow like forest and swamp (the horse's forest-and-swamp speed, e.g. a black
      horse not at all), the mountains by the horse's mountains speed.
- [ ] `custom_terrain = off`: the game's own map again: the lake on the left and the strip west of the mountains no
      longer slow (open ground).
- [ ] A save made before this version loads and plays as before (it carries its own map and program).

## D111 – Special rings: Mountainwalk, Waterwalk, Forestwalk, Plainswalking, Regeneration, Luck

Custom rules on, `rare_rings = on`, `rare_ring_chance = 100` (twelve rings exist now, so a wanted one may take several
chests); `move_bar = on` to see the movement. The places named are those of the D110 section.

- [ ] Ring of Mountainwalk (green band, grey-white stone): the red mountains and the golden rocky hills (right) do not
      slow; the forest and the swamp still do.
- [ ] Ring of Waterwalk (green band, ice-blue stone): the river and swamp at the lower right and the lake on the left do
      not slow; the rocky hills and the mountains still do.
- [ ] Ring of Forestwalk (all green): the big forest (lower left) does not slow; the swamp and the mountains still do.
- [ ] The three walk rings also on horseback: their terrain does not slow whatever the horse.
- [ ] A walk ring and a Potion of Levitation drunk: on the ring's terrain the potion keeps waiting; it starts on the first
      slowing terrain the ring does not free.
- [ ] Ring of Plainswalking (green band, pale yellow stone): on the brown
      plain (upper right) a turn takes the knight about half as far again as without it (the movement bar shrinks more
      slowly there); in the forest, swamp, rocks and mountains no change. The same on horseback.
- [ ] A second ring of the same walk kind adds nothing.
- [ ] Ring of Regeneration (violet band, green stone): end a day with low HP: full HP the next morning. HP above max
      after Danu stays. A knight with the ratmen's disease gets full HP but stays diseased.
- [ ] Ring of Luck (violet band, gold stone): enter a town, bet in the tavern: the first throw wins, the next ones are
      normal. Leave the tavern and come back in the same visit: no new winning throw. The next town visit (a later
      turn): the first throw wins again.
- [ ] Ring of Luck and a lair chest or the dragon's hoard: taking the gold gives 0-9 gold more than the chest showed
      (never past `max_gold`); `luck_chest_gold` changes the 9. Gold taken from a beaten knight or a cross: no extra.
- [ ] Computer knights and practice fights: none of these rings does anything.

## D112 – Special rings: the Ring of Charisma

Custom rules on, `rare_rings = on`, `rare_ring_chance = 100` (thirteen rings exist, so a Ring of Charisma may take several
chests; violet band, ice-blue stone); defaults `charisma_discount = 5`, `charisma_math = 50`.

- [ ] At the merchant with one Ring of Charisma: every weapon, armour, the daggers and every horse cost 5 gp less (the
      dagger 1 gp: never below 1); the hover text shows the lower price; the gold taken matches it.
- [ ] Two Rings of Charisma: 10 gp less (the broadsword 1 gp, the dagger 1 gp).
- [ ] A better sword, armour or horse for the knight's own one (`merchant_trade_in = on`): the new price is the lowered
      one less the old item's credit; a worse one in exchange is still free.
- [ ] With `merchant_selling = on`, sell each thing the merchant takes (dagger, broadsword, claymore, chain, plate,
      battle armour, the horse) with 0, 1 and 2 rings: it always pays less than buying it back costs this knight (with two
      rings the dagger and the broadsword sell for 0).
- [ ] At the High Temple with a ring: every item costs 5 gp less (10 with two), the hover shows it; selling anything
      (also a special potion or ring, sold as its plain item) pays less than buying it back costs.
- [ ] The healer with one ring: 5 gp heal a hurt knight, 10 gp buy a life (instead of 10 and 15); with two rings 1 gp
      heals and 5 gp buy a life.
- [ ] Mythral with a ring: a donation works as one 5 gp larger (10 with two rings); e.g. 5 gp give the chance of 10.
- [ ] Math with two rings: over many visits soon after an earlier one the frog comes clearly less often (about a quarter
      as often; with one ring about half); `charisma_math = 0` brings the frog back as before, 100 never with a ring.
- [ ] `charisma_discount = 0`: the ring changes no price; 50: everything at most 1 gp to buy with one ring, and selling
      still pays less than buying.
- [ ] The ring taken off or sold: the next item screen shows the full prices again. A computer knight with the ring pays
      full prices; in a practice fight it does nothing.

## D113 – Special gems: the base, Fury and Keyfinding

Custom rules on, `rare_gems = on`, `rare_gem_chance = 100` (three gems can be found so far: Fury with a green stand and a
red ball, Keyfinding with a gold stand and a white ball, Concealment with a green stand and a grey ball).

- [ ] Lair chests show a special gem after their Gems of Seeing, in its own colours (the Gem of Seeing stays grey and
      blue-grey); pointing at it names it ("Gem of Fury" and so on).
- [ ] Take three special gems: they fill the gem row's places 1-3 and a Gem of Seeing shows in place 4; a chest then shows
      no special gem (it keeps it for later).
- [ ] Two knights on a loot screen (or a beaten computer knight): take a special gem from a knight while you have three:
      each click cycles which three you keep; the other knight gets the one given away.
- [ ] Gem of Fury: click it on your item screen (it is gone), then fight a lair or a knight with Strength below 5: the
      blows hit as with Strength 5; the fight after that is normal again. Clicking a second Fury before the fight does
      nothing (it stays).
- [ ] Gem of Keyfinding: click it on the item screen opened on the map: the screen closes, a screen names who holds each
      key, and the lairs holding one glow until the turn ends. The same with `cheat_codes = no`.
      (Changed in D149: it shows only the nearest missing key; see D149 below.)
- [ ] Gem of Keyfinding used on the item screen at Math's (or right after a fight with a knight): the key screen shows
      before your turn ends, and never in the next player's turn.
- [ ] Gem of Concealment: clicking it does nothing (it stays; its effect comes later).
- [ ] High Temple: sell a special gem: 16 gp (the Gem of Seeing's selling price); the Temple never offers one for sale.
      Stonehenge: offer one (accepted as a Gem of Seeing).
- [ ] Lose to a computer knight or the dragon while holding special gems: taken or left as the special rings are (one
      item with lives left; at the last life what fits, the rest at the grave, which shows the gold cross); win them back
      from a computer knight's panel.
- [ ] `rare_gems = off`: no special gems anywhere, the gem row as in the game; an older ini without the two keys behaves
      as `on`.

## D114 – Special gems: Spying and Duplication

Custom rules on, `rare_gems = on`, `rare_gem_chance = 100` (five gems can be found now: Spying with a gold stand and a
green ball, Duplication with a green stand and a white ball, besides Fury, Keyfinding and Concealment).

- [ ] Gem of Spying: click it on your item screen: another knight's whole panel shows (gold, weapon, armour, daggers,
      items, keys, Moonstones, its enchanted gear, special potions, rings and gems); the gem is gone from your row.
- [ ] Spying: the arrow button shows the next knight, round all three others (never you); Exit goes back to the map.
- [ ] Spying in a game of two players without computer knights: report what the arrow button shows for the knights
      not in the game (the button is the Scroll of the Wyrm's own, which cycles all four records).
- [ ] Spying: click everything on the other knight's panel (gold, daggers, weapon, armour, a potion, a scroll, a special
      potion, ring and gem): nothing is taken or changes. Afterwards the dragon does not go after that knight.
- [ ] Gem of Duplication: click it: pointing at it reads "Gem of Duplication: pick an item" and it stays. Then click a
      dagger, a Potion of Healing, a scroll or the Talisman: one more of it, and the gem is gone.
- [ ] Duplication on a Ring of Protection: one more ring and its hit points at once (+20 with the default
      `ring_of_protection_hp`).
- [ ] Duplication on a special potion or ring with a free place of its kind: a second one of it appears; with that kind's
      places full: nothing copied, the gem stays.
- [ ] Duplication with three special gems (the Gem of Duplication one of them): click another special gem: it is copied
      into the place the Gem of Duplication leaves.
- [ ] Duplication on gold, the sword, the armour, the Sword of Sharpness, a key, a Moonstone, another Gem of Duplication,
      or with daggers at `max_daggers` or an item at 9: nothing copied, the gem stays and points as "Gem of Duplication"
      again; the click itself does nothing else (no potion drunk, no scroll used, no ability raised).
- [ ] Duplication armed, then Exit (or the screen closes another way): the gem stays; opened again, clicking an item uses
      it as usual (nothing is copied).
- [ ] With a horse (`horses = on`): on a loot screen or after the Scroll of the Wyrm, click your own horse's icon: your
      horse switches off and on, not the other knight's.

## D115 – Special gems: Greed and Concealment; Spying's knights

Custom rules on, `rare_gems = on`, `rare_gem_chance = 100` (six gems can be found now: Greed with a gold stand and a
gold ball, Concealment with a green stand and a smoke-grey ball, besides Spying, Duplication, Fury and Keyfinding).

- [ ] Gem of Greed: on the map press I and click it: the item screen closes and each lair on the map shows its gold
      under it in small gold digits with a black shadow (0 for a lair with only items); the gem is gone from your row.
- [ ] Greed: the numbers stay while you walk on that turn (and after a fight or another item screen in it); a lair you
      clear loses its number; the next player's map has no numbers.
- [ ] Greed near the map's edges: a lair at the left, right or bottom edge shows the part of its number that fits, with
      nothing drawn wrong elsewhere.
- [ ] Greed in a town, a village or another item screen that ends the turn: clicking it does nothing, the gem stays.
- [ ] Gem of Concealment: carry it (do not click it; a click does nothing). In the other players' turns your knight is not
      on the map; in your own turn it is.
- [ ] Concealment: put your knight next to a computer knight's path, or where one would come for you: computer knights
      never come after you or attack you, and none send the dragon (Scroll of the Wyrm) at you or take an item from you
      (Scroll of Acquisition).
- [ ] Concealment: another human player can still walk onto your hidden knight and fight it.
- [ ] Concealment: the dragon still finds and attacks your knight.
- [ ] Gem of Spying in a game of two players without computer knights: it shows the other player only (the arrow button
      stays on that knight); with that knight dead, clicking the gem does nothing and it stays.
- [ ] Spying with a dead knight in the game: the arrow button passes over the dead knight.
- [ ] Without computer knights: the Scroll of the Wyrm's and the Scroll of Acquisition's arrow buttons never show a knight
      that is not in the game (the Wyrm still shows a dead one, as the original).

## D116 – Special gems: the aim, Banish Monsters and Frog

Custom rules on, `rare_gems = on`, `rare_gem_chance = 100` (eight gems can be found now: Banish Monsters with a silver
stand and a gold ball, Frog with a silver stand and a green ball, besides the six of D113-D115).

- [ ] Gem of Banish Monsters: on the map press I and click it: the item screen closes and your knight is a crystal ball;
      walk it to a lair (the lair glows as with a Gem of Seeing) and fire: its chest shows (nothing can be taken); back on
      the map your knight stands where it was, with the movement it had left; the gem is gone.
- [ ] Banish: walk into that lair later, with the same knight or another player's: the chest opens without a fight (no
      experience for a first win); take everything: the lair goes from the map.
- [ ] Banish with co-op lairs on: enter the banished lair with another player's knight beside you ("Lair with"): no
      fight; the chest is shared as after a won fight.
- [ ] Banish: save, load the save: the lair is still banished. Start a new game: no lair is banished.
- [ ] Gem of Frog: use it, walk the ball onto another knight (a player's or a computer's) and fire: that knight is drawn
      as a frog; its next turn is skipped and the turn after it plays normally; your knight is back in place.
- [ ] Frog on a knight whose turn already came this day and on one whose turn is still to come: each misses exactly one
      turn. A knight Math made a frog for longer stays a frog for its own time.
- [ ] Frog: fire with the ball away from every knight: nothing happens, the ball stays; a knight hidden by a Gem of
      Concealment or a Potion of Invisibility, or a grave, cannot be hit.
- [ ] D118: Frog on another player's knight wearing Spellproof armour: fire with the ball on it: nothing happens, the
      ball stays and the gem is kept; Space or E puts your knight back. Change Places and Slow still work on that
      knight, and a Gem of Spying still shows it.
- [ ] Aimed gems: press Space or E while the ball is out: your knight is back in place, the gem stays, the item screen
      does not open and the turn does not end (press again for that).
- [ ] Use a Scroll of Haste, then an aimed gem, and hit or cancel: your knight still has its doubled movement.
- [ ] An aimed gem in a town, a village or on an item screen after a fight: clicking it does nothing and the gem stays.
- [ ] Two human players, one dead, the other made a frog: the game goes on (no Game Over) and the frog plays again.

## D117 – Special gems: Change Places and Slow

Custom rules on, `rare_gems = on`, `rare_gem_chance = 100`, `slow_gem_percent = 33` (all ten gems can be found now:
Change Places with a silver stand and a green and orange ball, Slow with a silver stand and a smoke grey ball, besides the
eight of D113-D116).

- [ ] Gem of Change Places: on the map press I and click it, walk the ball onto another knight (a player's or a
      computer's) and fire: the two knights have swapped places; your turn goes on from the new place with the movement
      you had left (the move bar shows the same length); the gem is gone.
- [ ] Change Places after a Scroll of Haste: you keep the doubled movement after the swap.
- [ ] Change Places on a knight standing on a lair or a town: after the swap nothing opens by itself; press fire there:
      the lair or town opens as if you had walked there. The other knight stands where you were and plays from there.
- [ ] Change Places on a frog: the frog is swapped and stays a frog for its turn; the dragon's attack on either knight
      still works afterwards (it follows the knights where they now stand).
- [ ] Gem of Slow: fire with the ball on another knight: on that knight's next turn its move bar is a third as long and
      it moves only a third as far; the turn after is normal. A computer's knight the same.
- [ ] Slow on a knight with a horse or a Scroll of Haste in that turn: still a third of what it would have had.
- [ ] Slow on a frog: the turn it misses does not count; its next turn it plays is the slow one.
- [ ] Two Slows on the same knight before its turn: still a third (not a ninth); one gem each.
- [ ] Slow: save and load before the slowed knight's turn: it is still slow. Start a new game: nobody is slow.
- [ ] Set `slow_gem_percent = 0`: the slowed knight can take only a step or two; 100: no cut.
- [ ] Change Places or Slow at a knight hidden by a Gem of Concealment or a Potion of Invisibility, or at a grave:
      cannot be hit (nothing happens).

## D119 – The item screen's pointer in its own colours

Custom rules on, `armour_enchantments = on`, `sword_enchantment_chance = 100`, `rare_potions = on`, `rare_rings = on`,
`rare_gems = on` (and their chances at 100), so enchanted and special items show up.

- [ ] Your own item screen (I on the map) with no enchanted or special items: the pointer (the gauntlet) has a black
      outline and its own light colours, as in the original game, not violet.
- [ ] The same with an enchanted sword or armour and special potions, rings and gems on the panel: the pointer is the
      same as above wherever it is (over a violet sword, beside it, over a plain item, over empty space, moving between
      them); the items keep their colours (the violet sword and armour, the potions', rings' and gems' own looks).
- [ ] A lair chest with an enchantment or a special item, the dragon's hoard, another knight's panel (loot, a grave),
      the merchant and the High Temple: the pointer as in the original game on each.
- [ ] Load a game saved during the first playtest (before this fix) and open an item screen: the pointer is already
      right.
- [ ] The item screen's fade in and out: the violet items fade with the rest of the screen (no item stays bright while
      the screen goes dark). The map's pointer and the fights look as before.

## D120 – The dragon's bite and the dragon after a won fight

Custom rules on or off (both fixes are in the fixed game). `[Debug] dragon_debug_mode = 1` makes it quick: on the map
the keys 1-4 make that knight the dragon's target, and Enter with the knight under the dragon starts its fight.

- [ ] Lose a fight to the dragon (any way but being eaten): back on the map the dragon is no longer where it caught
      you; it flies in again from the map's left edge. Your next turn does not start with a dragon fight.
- [ ] The playtest's case: a game where only one knight is still alive (the other knights dead, or a one-player game):
      lose to the dragon, and at your next turn you can walk away before the dragon reaches you.
- [ ] Let the dragon eat your knight (it takes the knight in its jaws). Then fight the dragon
      again at once (debug keys) without a lair or a knight fight between: your knight is there, can fight, and the
      fight ends as usual when one side loses.
- [ ] After being eaten, enter the Valley (all four keys) for the Guardian before any other fight: the Guardian fight
      is normal.
- [ ] Practice: the dragon practice, be eaten, then the dragon practice again: the second one is normal.
- [ ] With two or more knights alive: lose to the dragon with one knight; the next knight's turn is as before, and the
      dragon comes from the left edge. A computer's knight robbed by the dragon: the dragon flies off the same way.
- [ ] Optional, your slot 3 game: slot 3 itself stays the stuck fight (a save keeps the program it was made with).
      A repaired copy of its automatic save, `research/bugs/dragon-double-challenge-2026-11-18/100-repaired.sav` in the
      dev folder, can be copied into a free save slot and loaded: the second dragon fight starts again with the blue
      knight standing. That game still runs the build it was saved with (D118).

## D121 – Stat rings: the +1 is shown, and never blocks raising the base

Custom rules on, `rare_rings = on`, `rare_ring_chance = 100`. The item screen shows Strength, Constitution and Endurance
as numbers beside their icons; the number is the base + 1 for each ring of that ability the knight carries. Use a new
game (a save state keeps the build it was made with).

- [ ] Take a Ring of Strength from a chest: your Strength number goes up by 1 at once (3 -> 4). A second Ring of
      Strength: +2 in all (3 -> 5). The same for a Ring of Constitution (Constitution; max HP + 10 a ring) and a Ring of
      Endurance (Endurance).
- [ ] Lose a ring each way: sell it at the High Temple, offer it at Stonehenge, let another human knight take it (or
      swap it away when you hold two), lose a fight with lives left to a computer knight or the dragon that takes it,
      lose the last life. Each time the number goes back down by exactly 1 a ring, never below the base.
- [ ] Strength 5 (the usual top) with one Ring of Strength: the screen shows 6; with two: 7. Gain experience: the
      Strength icon is not offered for the XP click (the base is 5), the same as without the ring.
- [ ] Strength 4 with a Ring of Strength (shown 5): the XP click on Strength is still offered and raises the base to
      5, shown 6. Math's and Mythral's gifts can still raise Strength at base 4 although it shows 5.
- [ ] Drink a Potion of Strength at base 5 with a ring (shown 6): shown 7. Then give the ring away: shown 6 (base 6).
- [ ] Optional: base 9 (several Potions of Strength) with a ring shows 10, with two 11; the two digits are readable
      and touch nothing beside them (the gold icon to the right).
- [ ] Two knights on the item screen: the other knight's panel shows its own number with its rings; a computer's
      knight's panel shows its base (rings do nothing for computer knights).

## D122 – SKIPCOMBAT: fights skipped for testing (`cheat_codes = yes`)

Custom rules on, `cheat_codes = yes`. Start a new game. Type the code on the map, during a human knight's turn.

- [ ] Type SKIPCOMBAT: the cheat codes' sound (a sword clash). Walk into a lair: no fight, its chest opens at once with
      its gold and items. Take what you want and leave: the map comes back and the turn ends (as after a fight).
- [ ] With `rare_potions`, `rare_rings`, `rare_gems` and the enchantments on and their chances at 100: the chest of a lair
      you have not yet won holds a special item, as after a won fight.
- [ ] Your experience does not grow from a skipped fight (look at it on the item screen before and after).
- [ ] Empty a chest completely: the lair goes off the map, as after a real win. A lair you left items in stays; enter
      it again (a later turn): its chest opens again, no fight.
- [ ] Type SKIPCOMBAT again (the same sound): the next lair is a real fight. A lair you emptied of monsters with the
      code on has no monsters left when you come back with the code off (as after a real win).
- [ ] Co-op lairs (`coop_lairs` on, two knights next to a lair, "Lair with"): with the code on, no fight; each knight
      gets the chest as after a won co-op fight.
- [ ] The dragon catches your knight with the code on: no fight and no Scroll of Protection offer; its hoard opens
      at once, the dragon is dead (it flies again only with HEREBEDRAGONS), no experience gained.
- [ ] With the code on, a knight duel (attack another knight, or a computer's knight attacks you) is fought as ever,
      and so is the Guardian in the Valley. A computer's knight's own lair fights are as ever.
- [ ] A drunk "next fight" potion (Might, Fire Resistance, Speed) or the Gem of Fury is still working in your next
      real fight after skipped ones.
- [ ] `cheat_codes = no`: typing SKIPCOMBAT does nothing, lairs are fought.

## D123 – Math and Mythral never raise an ability at 5 or more

Run Setup.bat again first (the fixed game changed). Custom rules on or off. To get an ability above 5 quickly: custom
rules with a knight's start value (for example `strength = 6` in its `[Knight...]` section), or the Potions of
Strength, Endurance and Constitution (`rare_potions = on`).

- [ ] Strength 6 (or more), Constitution and Endurance below 5: visit Math and Mythral several times: when they raise
      an ability it is always Constitution or Endurance, never Strength.
- [ ] All three at 5 or more (for example 5, 6, 9): Math never raises one (he gives gold, an item or the frog instead);
      Mythral never raises one (when his roll would raise, he says you have already learnt what he can teach).
- [ ] Mythral's loss: with Strength 6 and the others below 5, a donation that goes wrong lowers Constitution or
      Endurance, never Strength (the game already spared an ability of exactly 5).
- [ ] With a Ring of Strength and base Strength 4 (shown 5): Math and Mythral can still raise Strength (to base 5,
      shown 6).
- [ ] The rest as before: experience still raises an ability only while it is below 5 (the item screen's click);
      Math and Mythral still raise abilities below 5 as they did.


## D124 – The spear trogg attacks a little slower

Custom rules on, `spear_trogg_attack_pause = 130` (the default; an older `custom_rules.ini` without the line gets 130 too). Practice key 6 (lair 20, spear troggs) is the quickest way in.

- [ ] Stand still in a spear trogg's reach: its thrusts come noticeably less often than before (about every 1.8 s instead of
      every 1.4 s), and between two thrusts there is time to step in and strike.
- [ ] The thrust itself looks as before (the same quick stab, the same reach and damage, 3).
- [ ] `spear_trogg_attack_pause = 100` (then Custom_rules_on or Setup as usual): the old pace again. 200: about twice as slow.
- [ ] Axe troggs, hammer troggs (Wastelands) and the war beasts attack at their old pace.

## D125 – A riposte at the same moment as the troll's blow from above stops it

Custom rules on, `timed_defence = on`. Practice key 9 (lair 18, trolls). The riposte: down + forward + fire (the lunge) while
the troll's club is going up for its blow from above.

- [ ] A late riposte, just before the club comes down: the quick thrust hits, the troll flinches and takes the damage, and its
      blow does not land (before, the troll ignored the thrust and its blow still hit).
- [ ] An early riposte: as before, the troll flinches and its blow never comes.
- [ ] Too late (after the club has come down): the troll's blow hits as before; a blow that kills still crushes the knight (Gore
      On or More).
- [ ] The troll's push (close in, its club sideways): as before, no riposte against it.
- [ ] Axe troggs (practice key 4) and hammer troggs (key 3): a riposte that lands as their blow from above lands: the trogg
      flinches and its blow does not hurt the knight (before, both hit).
- [ ] `timed_defence = off`: everything as the game (no riposte).

## D126 – Computer knights' level-up capped at 5; nothing wrong written with every ability at 5 or more

Run Setup.bat again first (the fixed game changed). Custom rules on or off; for abilities above 5 use start values in
`custom_rules.ini` (for example `strength = 6` in a knight's section, the computer knights' own section for them) or
the Potions of Strength, Endurance and Constitution (`rare_potions = on`).

- [ ] A computer knight with Strength 6 (or more) and Constitution and Endurance below 5: over a few weeks its
      level-ups raise Constitution or Endurance, never Strength (the knight's item screen, or the summary at the end).
- [ ] A computer knight with every ability at 5 or more: its abilities stay as they are, however much experience it
      gathers.
- [ ] A knight with every ability at 5 or more (for example 5, 6, 9) loses to the Guardian: it loses its lives as
      before and plays on normally (moves, fights, the item screen as before). Since D130 one of its abilities falls
      by 1 there.
- [ ] The same knight at Mythral: when the donation goes wrong he says his powers are weak and nothing changes; when it
      goes well he says there is nothing left to teach. Afterwards the knight plays on normally.
- [ ] The rest as before: Mythral's loss lowers only an ability below 5 (D123), and a human knight's experience raises
      an ability only while it is below 5. (The Guardian's own rule changed again in D130: see there.)

## D127 – Safety timer: Esc leaves a campaign fight after two minutes (replaced by D132)

Replaced by D132 before it was released: the exit no longer opens by the fight's length. Do not test these rows; D132's
section below tests the same leaving with the new rule.

Custom rules on (`[Combat] fight_safety_timer = 120`, the default; for quicker tests set it to 10 and run
Custom_rules_on.bat again). Start a new game. Watch a clock: the time counts from the fight's first frame.

- [ ] A lair fight: press Esc before the time is up: nothing happens, the fight goes on. Press it again after the time:
      the fight ends at once, the map comes back with no chest, and the turn is over. Your gold, items and experience
      are as before the fight; the knight's hit points are what they were when you left (wounds stay).
- [ ] Enter the same lair again (a later turn): it has all its monsters again (the ones you killed are back).
- [ ] Hold Esc down when leaving and keep holding it a second or two: the game does not end on the map (no Game Over);
      let go, then Esc on the map ends the game as before.
- [ ] A knight duel (attack another knight, or a computer's knight attacks you): Esc after the time leaves it; neither
      knight wins or takes anything, both keep their lives.
- [ ] The dragon: Esc after the time leaves the fight, no hoard, no life lost, and the dragon has flown off (it comes
      back later from the map's edge).
- [ ] The Guardian: Esc after the time leaves the fight; the keys stay with the knight and nothing else changes.
- [ ] Co-op lair ("Lair with", two knights): Esc after the time leaves the fight for both; no chest. A knight that was
      already down when you pressed Esc loses its life as after a normal fight; the standing one does not.
- [ ] A fight that is ending on its own (a knight just fell, or the last monster just died): Esc does not change it;
      the result is the game's.
- [ ] A computer's knight's own lair fight or duel that you watch: Esc after the time leaves it as well (its turn ends,
      nothing gained).
- [ ] Practice (from the first menu): Esc ends it at once, as before (the timer does not apply).
- [ ] `fight_safety_timer = 0`: Esc never leaves a campaign fight.

## D128 – Gem of Change Places: a teleport when there is nobody to change places with

Custom rules on, `rare_gems = on`, `rare_gem_chance = 100`. Get a Gem of Change Places (silver stand, green and orange
ball) from a lair chest. The teleport works only when no other knight on the map could be hit by the gem: play alone
(one player, no computer knights), or let the other knights die out of the game, or have them hidden (Gem of
Concealment, Potion of Invisibility).

- [ ] Alone on the map: press I, click the gem, move the ball somewhere and fire: your knight is there, the gem is gone,
      and your turn goes on with the movement you had left (the move bar as before the aim).
- [ ] After a Scroll of Haste: the doubled movement is kept after the teleport.
- [ ] Teleport onto a lair or a town: nothing opens by itself; press fire there and it opens as if you had walked there.
- [ ] Fire with the ball on the Valley of the Gods (anywhere your knight would touch its picture): nothing happens, the
      ball stays, the gem is kept. Just outside the Valley: the teleport works.
- [ ] Fire without moving the ball: nothing happens, the gem is kept.
- [ ] Space or E while aiming: your knight is back where it stood, the gem kept (as before).
- [ ] With another knight alive and visible anywhere on the map (a player's or a computer's, a frog too): fire away
      from it does nothing (the gem stays); fire on it swaps places as before (D117).
- [ ] Two players, the other one carrying a Gem of Concealment: the teleport works (a hidden knight cannot be a
      target); the hidden knight is not moved.
- [ ] Teleport next to the dragon: the dragon catches you as if you had walked there.

## D129 – The Players choice goes round

In the first menu, on the Players line, step with right and left (keyboard or controller).

- [ ] Right from *1 + CPU*: *2 + CPU*, *3 + CPU*, *4*, *3*, *2*, *1*, then *1 + CPU* again, and on round.
- [ ] Left from *1 + CPU*: *1*, *2*, *3*, *4*, *3 + CPU*, *2 + CPU*, *1 + CPU*, and on round.
- [ ] Hold right (or left): the choice keeps going round at the menu's repeat speed; one tap is one step.
- [ ] The menu looks as before (the same texts in the same place).
- [ ] Start a campaign with each of the seven: with *+ CPU* the knights nobody plays are computer knights; *4* has
      four players; *3*, *2* and *1* have only the players' knights on the map.
- [ ] Restart the game: the menu opens on the choice you left it on.
- [ ] Custom rules on, `computer_knights = off`: right goes *4*, *3*, *2*, *1*, *4*, ...; left the other way; no
      choice shows "+ CPU".

## D130 – The Guardian may lower any ability, never below 1

Run Setup.bat again first (the fixed game changed). Custom rules on or off. The Guardian fight needs all four keys; let the
Guardian win. Look at the abilities on the item screen before and
after; a save before the fight lets you try again.

- [ ] Abilities 5, 5, 5 (or above 5, for example 5, 6, 9): after a lost fight one of them is 1 lower (also one of
      exactly 5, which the game never lowered), and the lives go as before.
- [ ] Over several tries each of the three can be the one that falls.
- [ ] One ability at 1 (for example Strength 1, the others 4): that one never falls, one of the others does.
- [ ] All three at 1: nothing falls; the lives go as before, and the knight plays on normally.
- [ ] With a Ring of Strength (custom rules, `rare_rings = on`) and base Strength 1 (shown 2): Strength never falls.
- [ ] Math, Mythral and the computer knights' level-up as before (D123, D126).


## D131 – The troll's blow from above lands where its club is drawn

Run Setup.bat again first (the fixed game changed, and Setup writes `DISKB\COLLFIX.HIT`). Custom rules on or off. Practice
key 9 (lair 18, trolls), or the fight of your save slot 3.

- [ ] Let the troll come to you and stand still where it stops: its blows from above (the club coming down) hit you every
      time, from either side (before, from the left it could miss every blow at that spot).
- [ ] Step back and forth a little at the edge of its reach: the blow hits wherever the club comes down on the knight, and
      misses when the club comes down in front of the knight, as before (the reach is the same).
- [ ] Each blow does the troll's damage as before (7), and a blow that kills still crushes the knight (Gore On or More).
- [ ] Holding the block does not stop the blow from above (as before), and the knight is not missed while blocking.
- [ ] The troll's push (close in, its club sideways): as before.
- [ ] With `timed_defence = on`: a riposte as the club goes up still stops the blow (D125).
- [ ] Axe, hammer and spear troggs, ratmen and the other monsters hit as before.
- [ ] Fixes_Off.bat (the original game): the troll misses as in the original again; Fixes_On.bat: the fix is back.

## D132 – Stuck fight exit: Esc leaves a campaign fight when nobody has acted for 30 seconds

Custom rules on (`[Combat] fight_idle_exit = 30`, the default; an older custom_rules.ini without the line gets 30).
Start a new game. "Nothing happens" below means: no key pressed or held on the keyboard, no joystick moved or button
pressed, and your knight is not hit (its hit points do not change). Watch a clock.

- [ ] A lair fight: stand still and touch nothing. After 30 seconds "ESC LEAVES THE FIGHT" appears in small cream
      letters with a black shadow at the top centre of the screen. It does not flicker, and figures that pass under it
      do not leave marks.
- [ ] Before the hint is there, Esc does nothing (the fight goes on), and pressing Esc does not count as a key: the hint
      still comes 30 seconds after your last other key.
- [ ] With the hint showing, press any other key (or move the joystick): the hint disappears at once and cleanly (the
      sky or wall behind it is as before), and the 30 seconds start again.
- [ ] Hold a direction key down for more than 30 seconds without being hit: no hint (a held key counts as pressing).
- [ ] Stand still where a monster hits you now and then: no hint while you are hit more often than every 30 seconds.
- [ ] With the hint showing, press Esc: the fight ends at once, the map comes back with no chest, and the turn is over.
      Gold, items and experience are as before the fight; the knight keeps the hit points it had (wounds stay).
- [ ] Enter the same lair again (a later turn): it has all its monsters again.
- [ ] Hold Esc down when leaving and keep holding it a second or two: no Game Over on the map; let go, then Esc on the
      map ends the game as before.
- [ ] A knight duel against another player's knight: neither player touches anything for 30 seconds: the hint, Esc
      leaves it; neither knight wins or takes anything. If either player presses a key, the hint goes away.
- [ ] The dragon: the hint after 30 quiet seconds, Esc leaves the fight, no hoard, no life lost, and the dragon has
      flown off.
- [ ] The Guardian: the hint after 30 quiet seconds; Esc leaves; the keys stay with the knight.
- [ ] Co-op lair ("Lair with", two knights): the hint only when neither player has pressed anything and neither knight
      has been hit for 30 seconds. Esc leaves the fight for both; no chest. A knight that was already down loses its
      life as after a normal fight.
- [ ] A computer knight's own lair fight that you watch: no hint ever, Esc does nothing.
- [ ] A fight ending on its own while the hint shows (the last monster dies): the hint disappears, the result is the
      game's.
- [ ] Practice (from the first menu): no hint; Esc ends it at once, as before.
- [ ] `fight_idle_exit = 0` (run Custom_rules_on.bat again): no hint ever, Esc never leaves a campaign fight. With
      `fight_idle_exit = 5`: the hint after 5 quiet seconds.

## D133 – Terrain zones in 4 x 4 pixel cells, measured at the middle of the knight's icon

Custom rules on, `[Map] custom_terrain = on` (your zones; `tools/terrain_zones.csv` is now 80 x 50, made exactly from
your 40 x 25 drawing), `terrain_cells = 4x4` and `terrain_probe = centre` (the defaults; an older custom_rules.ini
without the lines gets them too). Start a new game (or load a state saved after this build).

- [ ] Walk a knight on foot into a forest, a swamp, rocks and mountains you drew: it slows where the middle of its
      helmet icon reaches the painted zone (not about one cell later going down, earlier going up, as before).
- [ ] Paint a narrow strip (one 4 x 4 cell wide) of mountains on open ground with the map tool (`Terrain_editor.bat`,
      Ctrl+S), run `Custom_rules_on.bat`, restart DOSBox-X: crossing it slows the knight for the few steps on it only.
- [ ] The same mounted: the horse's speeds in forest and swamp and in mountains are as before, now by the 4 x 4 cells.
- [ ] A Ring of Mountainwalk, Waterwalk or Forestwalk frees its zone; Plainswalking works on open ground (all by the
      new cells).
- [ ] Set `terrain_probe = feet`, run `Custom_rules_on.bat`: the zone is measured at the icon's bottom edge again (the
      original game's point): a border going down is reached a little later than with centre.
- [ ] Set `terrain_cells = 2x2`: the zones work in 8 x 8 blocks again (a narrow 4-pixel strip then takes its whole
      block or none of it, by what most of the block is).
- [ ] Speedrun mode: the game's own map and terrain, exactly as the original.
- [ ] A game state saved before this build still loads and plays (it keeps the terrain it was saved with until a
      restart).

## D134 – Places, starts and lairs where the map tool puts them

Custom rules on, `[Map] custom_places = on` (the default; an older custom_rules.ini gets it too). Open the map tool
(`Terrain_editor.bat`), choose *Move* (V) and drag some markers, Ctrl+S, run `Custom_rules_on.bat`, restart DOSBox-X,
start a new game.

- [ ] Without moving anything (or with `custom_places = off`): everything is where it always was.
- [ ] Move a lair marker (a violet ring with its number) to open ground: the lair's icon is drawn there, entering it
      starts its fight (the same monsters as before for that number), and the old spot is empty.
- [ ] Move a town (HW or WD) and paint its picture there (Map menu, your own picture; or just try with the old picture):
      the town is entered at the new place; computer knights walk to the moved town to shop.
- [ ] Move home village 1 (blue box "1"): its start S1 moves along; knight 1 starts at the new S1, and its druid's
      village works at the new place (only for its own knight, as before).
- [ ] Move a Black Knight's start (B1-B4): the Black Knight appears there at the start.
- [ ] Move the Valley (VY): with the keys the Valley is entered at its new place; a cursed Scroll of the Hawk never lands
      a knight on it there.
- [ ] Put a place on top of another in the tool: it is refused (red, with the reason) and jumps back.
- [ ] Speedrun mode: the game's own places.

## D135 – The map tool: your own map picture, Apply and Restore original

Python 3 with Pillow (`py -3 -m pip install pillow` once). Make a copy of your game folder first if you want to be
extra safe (the tool keeps the original map itself as `DISKB\MAP.CMP.orig` and `DISKC\MAP.CMP.orig`).

- [ ] `Terrain_editor.bat` opens the map tool with your game's map, your zones and the markers.
- [ ] Map > Export map picture: a 320 x 200 PNG of the map. Paint something on it in any paint program (keep the size),
      Map > Import map picture: it shows in the tool; the message says how many pixels took a nearest colour and the
      size as MAP.CMP.
- [ ] Map > Free colours of the palette: "Fit the free colours to the picture" changes only the six numbered colours;
      "The game's colours" puts them back.
- [ ] Map > Apply to the game: the list of what it will do, then Yes: "Done". Restart DOSBox-X: the map is your
      picture, the knights' icons, lairs and places look as before, and the zones and moved places work.
- [ ] Apply with a picture full of noise (many single pixels of random colours): refused before anything is written if
      it would be over 35,840 bytes.
- [ ] Map > Restore original map: Yes: the game's own map, places and terrain are back after a restart (your
      `custom_rules.ini` has `custom_places = off` and `custom_terrain = off`; set them on again to use your files).
- [ ] File > Save project as, then Load project: zones, places and your picture come back; a project made with the
      game's own map holds no map picture.
- [ ] Map > Export sprites and Export template: PNG files of the game's map sprites and a 4x template with the markers.
- [ ] `tools/map_palette.png`: open it in your paint program, paint a picture with colours picked from its squares
      with the colour dropper, import it: the message says every pixel has a colour of the map's palette.

## D136 – Smooth animation: in-between pictures in fights

Custom rules on (run Custom_rules_on.bat after Setup or after changing the ini). `[Rules] smooth_animation = 6` is the
default, also for an older custom_rules.ini without the line. The game's rules and pace do not change; only more
pictures are shown between the game's own. Look for motion, not for new poses: a pose still changes about nine times a
second (new in-between poses are a later stage).

Changed after the playtest of 19 Nov 2026 (walking floaty, the dragon's breath in chunks): only an object whose picture
stays the same now moves in the in-between pictures. A knight or monster whose pose changes is drawn exactly as in the
original. Daggers, swings and attacks were fine in that playtest; please look at them once more with this build.

- [ ] Practice, a knight against the trolls (first menu, key 9): walk left and right, up and down. The knight walks
      exactly as in the original: no gliding, no bobbing, no sliding feet. The same for the troll's walk.
- [ ] Throw daggers (yours, and in a knight duel the other knight's): a dagger flies in small steps, not 20 pixels at
      a time, and it still hits when it did: the struck figure reacts as the dagger arrives.
- [ ] The dragon fight: its body parts move smoothly. Its breath stays whole from mouth to tip in every picture: no
      gaps, no chunks, no piece out of place; the fire on a burning knight too. Nothing is left behind on the screen
      and no part flickers.
- [ ] Pushes and knock-backs (a blow that throws a knight back, the troll's push): a figure that keeps its pose
      while it is thrown slides back smoothly; it does not look floaty.
- [ ] Standing figures, blocks and blows look as before: no flicker, no doubled figure, no trail, no missing piece
      (shadows, blood, bodies on the ground, the score line and the HP bars at the top).
- [ ] A knight turning round, a knight walking on to the screen, a mudman rising far from where it sank: they appear
      in place, with no picture sliding across the screen.
- [ ] The pace of fights. In the playtest of 19 Nov 2026 it was a little faster than before: fights now keep the
      game's full 9.1 ticks a second, where at the old `fight_cycles` even a walking knight against the ratmen ran at
      about 8.65 (measured). `draw_TPS = yes` shows it. Tell me whether the full pace is right or the old, slightly
      slower feel should come back.
- [ ] Sound effects and music in fights are as before (no crackle, no slowdown).
- [ ] Your keys feel as before: blows start when you press, blocks work (timed defence too if you use it).
- [ ] A 2-player duel, a co-op lair and a 3-4 player practice: the same checks; every knight keeps its colours in
      every picture (no flash of a wrong colour).
- [ ] A Potion of Speed, LIGHTSABER, MINEFIELD and BEATEMUP's bars still look right in a fight.
- [ ] `[Debug] draw_FPS = yes` and `draw_TPS = yes`: two numbers in the top left corner in fights, pictures a second
      and ticks a second: about 54.6 and 9.1. Write down what they show in a troll fight, the dragon fight and a
      fight with 4 knights while everyone moves.
- [ ] `smooth_animation = 3`, then `2`: fewer in-between pictures (27.3 and 18.2 a second). `1`: exactly the old look.
- [ ] `smooth_fight_cycles = 3000` with `smooth_animation = 6` (too slow on purpose): the fight keeps its pace
      (draw_TPS 9.1), draw_FPS falls, the motion gets coarser; nothing hangs.
- [ ] A DOSBox-X save state made in the middle of a fight, then loaded: the fight goes on normally.
- [ ] After a fight the map and the towns run at their old speed.
- [ ] Speedrun mode: fights look as the original (one picture a tick).

## D137 – The special items in one ini section, with a master switch

Python only: no Setup.bat rerun. First reset your ini, so it has the new section: run `Custom_rules_reset.bat` (your
own custom_rules.ini values are lost; keep a copy if you want them), then `Custom_rules_on.bat`, and restart DOSBox-X.
After every ini change below run `Custom_rules_on.bat` again and start a **new** game.

- [ ] The reset custom_rules.ini has `[Special_items]` right after `[Treasure]`, starting with
      `special_items = lairs` (after D139; D137 alone wrote `chance`); `[Rules]` has no enchantment keys and `[Treasure]` no potion, ring or gem keys.
- [ ] `special_items = off`, a new game: win or SKIPCOMBAT several lairs and meet the dragon: no enchantment, special
      potion, ring or gem anywhere (chests and the hoard show only the game's own items).
- [ ] Back to `special_items = chance` (with the chances at 100 to see it quickly): enchantments and special items
      come again.
- [ ] `special_items = lairs`: since D139 the lairs way (the D139 tests below).
- [ ] `special_items = maybe`: `Custom_rules_on.bat` refuses with a message naming `special_items`.
- [ ] Speedrun mode (`speedrun_mode = on`): no enchantments or special items in any chest or the hoard.
- [ ] A save (DOSBox-X save state or RESUME GAME) made before the change with special items: loaded, it still has them.

## D138 – Rebirth and the four-key goal at the real Stonehenge

Run `Custom_rules_on.bat` (SAVEHOOK changed) and restart DOSBox-X; start a **new** game (a save keeps the old point).
Armour enchantments on (`armour_enchantments = on`, the chance at 100 helps), `black_knight_ai = smart`.

- [ ] A knight in Rebirth armour loses a fight: it wakes at Stonehenge (the stone circle in the lower left part of
      the map), not in Water Deep; no life lost; the armour is plain.
- [ ] On its next turn the Stonehenge icon is offered among the choices; nothing opens by itself. Click it: the
      offering screen as usual. Walk away: the knight moves normally.
- [ ] When a computer knight has all four keys (a long game; IDROPPEDMYKEY shows where the keys
      are): it walks to Stonehenge and stays there turn after turn.
- [ ] Walk your knight to it there: you are offered both Stonehenge and the attack; both work.
- [ ] With the map tool, move Stonehenge (Places menu, then Apply to the game): Rebirth and the four-key knight go
      to the new place. `custom_places = off` (then `Custom_rules_on.bat`): the game's own place again.
- [ ] Speedrun mode: no Rebirth armour, the Black Knights are classic (nothing of this changes).

## D139 – Special items in only some lairs (the lairs way)

Custom rules only: no Setup.bat rerun. Reset your ini once, so it has the new default (`special_items = lairs`,
`special_item_lairs = 8` since D140): run `Custom_rules_reset.bat` (your own custom_rules.ini values are lost; keep a copy if you
want them), then `Custom_rules_on.bat`, and restart DOSBox-X. After every ini change below run `Custom_rules_on.bat`
again, restart DOSBox-X and start a **new** game (a save keeps the rules it was started with). SKIPCOMBAT (cheat codes
on) is the quick way through the lairs; IDROPPEDMYKEY or a Gem of Greed are not needed.

- [ ] The reset file: `[Special_items]` starts with `special_items = lairs` and `special_item_lairs = 8`.
- [ ] Default (8 lairs, all five at 10 %), a new game: SKIPCOMBAT through all 24 lairs (or win them) with a knight
      that has free potion, ring and gem places: exactly eight chests hold a special item (an enchantment, a special
      potion, ring or gem), each at least one; the other 16 none. Now and then one of the eight holds two.
- [ ] `special_item_lairs = 3`, every chance 0 but one (for example `rare_ring_chance = 100`, the others 0): three
      lairs, each with a special ring only, no other special item anywhere in the lairs.
- [ ] Save (DOSBox-X save state, or quit and RESUME GAME) before entering a picked lair; load and enter it again:
      the same lair still holds the same kinds (the exact ring or potion may differ if it was not looked at yet).
- [ ] Co-op lairs `full`: two knights win a picked lair together: each special item is taken once, by the first who
      clicks it.
- [ ] The dragon's hoard still holds special items sometimes (about four games in ten at the defaults; set the chances
      to 100 to see it every time).
- [ ] `special_items = chance`: as before D139 (about 10 of the 24 lairs with something at 10 %); `special_items = off`:
      none anywhere.
- [ ] A save made before D139 (its game started in the chance way) still plays in the chance way after loading.
- [ ] Only if you test without XMS (`xms = false` in the DOSBox-X config of a test copy): only enchantments come,
      still in eight lairs.
- [ ] `special_item_lairs = 25`: `Custom_rules_on.bat` refuses with a message naming it.

## D140 – The lairs way: two picked lairs in each quarter; a lair stays while a special item is left

Custom rules only: no Setup.bat rerun. If you reset your ini for D139 before D140 was built, reset it once more (or set
`special_item_lairs = 8` by hand), then `Custom_rules_on.bat` and restart DOSBox-X. Start a **new** game for each test.
The quarters are the game's four key regions: lower left, upper right, lower right and upper left of the map (six
lairs each, one key in each).

- [ ] Default (`special_item_lairs = 8`): SKIPCOMBAT through all 24 lairs: the eight lairs with special items are two
      in each quarter.
- [ ] `special_item_lairs = 6`: one quarter-share each and two quarters with one more (1, 1, 2, 2); a few new games
      give the extra ones to different quarters. `= 4`: one in each quarter.
- [ ] A knight with all three potion places full wins a picked lair with a special potion, takes the gold and all
      the game's items, and leaves the potion: the lair stays on the map. Enter it again (a fight again, no
      experience this time): the chest still shows the potion; with a free place now, take it: then the lair leaves
      the map.
- [ ] The same with `special_items = chance` (set the potion chance to 100 to see it quickly): the lair stays while
      the potion is there.
- [ ] A lair with nothing left at all (gold, items and specials taken) leaves the map as before.
- [ ] Computer knights (`black_knight_ai = smart`) do not walk to a lair that holds only a special item.

## D141 – Switching sides with down held turns the knight (the ratmen fight's lunge)

SAVEHOOK.COM only: no Setup.bat rerun. Any fight mode; the ratmen fight shows it best. (D142 changed the ratmen fight:
up + hit is now the straight upward thrust, back + down + hit the block, down + hit the downward stab.)

- [ ] Ratmen fight: hold Down, lunge to the right a few times (Right + hit), then, still holding Down, press Left and
      hit: the knight turns and lunges to the left (not the straight upward thrust to the right).
- [ ] The same while mashing hit during the lunge: after the lunge the knight turns left, then lunges left.
- [ ] Standing, facing right, press Down and Left together, then hit: the block (D142; before it, in the ratmen
      fight, the straight upward thrust), and the knight still faces right.
- [ ] Standing, facing right, Up and Left together + hit: the dagger thrown to the right (as before).
- [ ] Walking up the screen (Up held), press Left, wait a moment and hit: the knight turns and does the upward thrust
      to the left (Left + hit at once: the backward thrust, D142).
- [ ] A knight facing right, Right + Down + hit: the lunge (as before).

## D142 – The ratmen fight: up + hit the straight thrust, back + down + hit the block

Run Setup.bat again first (the fixed game changed). Custom rules on or off. A ratmen fight (the Great Forest; practice
or your own save). Facing right ("back" is Left; facing left the other way round).

- [ ] Up + hit: the straight upward thrust (the sword straight up), not the overhead chop. It kills a ratman lying on
      the ground at once.
- [ ] Up + hit against a leaping ratman: it hurts it (often kills it); up + forward + hit still kills it at once.
- [ ] Press Down and Left together, then hit (or all three together): the block, and the knight still faces right
      (since D145 it also stops a ratman's bite and claw).
- [ ] Down + hit: the downward stab (as before); it kills a ratman on the ground at once.
- [ ] Walk down the screen (Down held), then press Left and hit at once: the quick backward thrust to the left, the
      knight still facing right (not the block).
- [ ] The same, but wait a moment after Left before hitting: the knight turns and lunges to the left (D141).
- [ ] Walking up the screen (Up held), Left + hit at once: the backward thrust (not the dagger).
- [ ] Hold Down, Right + hit: the lunge (as before).
- [ ] Other fights: back + down + hit is the block, up + hit the overhead chop, as before.

## D143 – Smooth animation: in-between poses for the knight's walk

Run Setup.bat first (it makes `SAVEHOOK.INB`, the in-between poses, from your own game files), then
Custom_rules_on.bat. `[Rules] smooth_animation = 6` as in D136. The dev install `rebuilt` already has the file.
What to judge is the look in the real game: the walk was approved from the sample page, not yet in play. The poses
are shown one step late (your decision of 19 Nov 2026): a walking knight's picture is at most about 12 pixels behind
where the game has it. Starting from standing, stopping and turning round have no in-between poses yet.

- [ ] Start the game: the DOSBox-X window shows no new error line before the game, and the cheat codes and special
      items still work (the file reader of `SAVEHOOK.OVL` was rewritten to serve both files).
- [ ] Practice, a knight against the trolls (first menu, key 9): walk left and right. The legs open and close
      smoothly between the game's poses, the standing foot stays on the ground, the head keeps its height; no
      gliding, no bobbing, no jump of 12 pixels with every pose.
- [ ] The same walking up, down and diagonally, and facing both ways: the body, its shadow and the sword stay together
      (the hilt may sit a pixel or two off the hands for one picture).
- [ ] The walk-in at a fight's start: the knights walk on to the screen smoothly and stop where they did.
- [ ] Start walking, stop, turn round: the first step, the stop and the turn appear at once, as before; nothing slides
      across the screen and no doubled or missing body shows for a moment.
- [ ] Walk, then strike or block without stopping: the blow starts when you press; the knight may move up to one step
      in that one picture (it catches up with the game's place), nothing worse.
- [ ] Does the one-step lag feel right while walking, for example when you walk up to a troll and strike, or step
      back from a blow? If your knight seems to be hit "from too far", say so: looking ahead is the alternative.
- [ ] A knight duel (two players or against a Black Knight): the second knight (the other look, the game's own second
      colours) walks as smoothly, in its own colours in every picture.
- [ ] A co-op lair and a 3-4 player practice: every knight walks smoothly in its own colours; computer knights too.
- [ ] Sword and armour enchantments, LIGHTSABER: a walking knight keeps its sword's and armour's colours in every
      picture.
- [ ] A hit while walking, a fall, a death, a thrown dagger while walking: as before; no leftover body on the screen.
- [ ] A Potion of Speed: the knight walks as in D136 (its poses skip one, so there is no in-between pose); nothing
      looks broken.
- [ ] `smooth_animation = 3`, then `2`: two, then one pose in between each step; `1`: exactly the original.
- [ ] `[Debug] draw_FPS = yes`, `draw_TPS = yes` while everyone walks (a troll fight, 4 knights): write down the two
      numbers (about 54.6 and 9.1).
- [ ] Move `SAVEHOOK.INB` out of the game folder and start the game: the walk looks as in D136 (in place), everything
      else works. Put it back.
- [ ] A DOSBox-X save state made while a knight walks, then loaded: the fight goes on normally.

## D144 – Ducking a thrown dagger

Custom rules on (`Custom_rules_on.bat`), `[Combat] duck_dodge = on`, `duck_window = 6` (the defaults). No Setup rerun.
A practice fight of two or three keyboard players (first menu: Players 2 or 3), or a duel against a computer knight.
"Down" is each player's own down key (player 1 the Down arrow, player 2 S, the third set K). The duck is the low
pose of the ratmen fight's downward stab without the sword, three frames (about a third of a second).

- [ ] The second player throws a dagger (back + up + hit) at the first, both at the same depth. Just before it
      reaches the first knight, tap Down: the knight ducks, the dagger flies over it and on off the screen, no hit
      points lost; the knight stands up and can act at once.
- [ ] The same with the thrower a little higher on the screen, and again a little lower (each up to about 10 pixels
      of depth apart, so the dagger would still hit a standing knight): the duck works in both.
- [ ] Press Down and keep it held just before the dagger arrives: the knight ducks, then walks on down after the duck.
- [ ] Tap Down too early (about half a second or more before the dagger arrives): the dagger hits as before.
- [ ] Walk down the screen with Down held from long before into the dagger's path: it hits (holding down from earlier
      is a walk, not a duck).
- [ ] Attack (any blow), block or dodge as the dagger comes, with Down pressed too: it hits as before.
- [ ] Does the timing feel right? Too hard or too easy to hit: `duck_window` (2-18 ticks, 18 a second) changes it.
- [ ] A computer knight (a duel or a Black Knight): throw many daggers at it while it stands or walks. Now and then
      (about one dagger in four) it ducks and the dagger flies over it.
- [ ] `duck_dodge = off`: tapping Down just before the dagger arrives does not duck; the dagger hits (or misses as the
      game's geometry decides, as before).
- [ ] The game's own dodge (down + hit) still shows the kneeling dodge, not the duck; the ratmen fight's down + hit is
      still the downward stab.
- [ ] With GUNSHOT on (a fight code), the ball cannot be ducked; DAGGERFALL's daggers from the sky cannot be ducked.
- [ ] With a joystick knight: no duck (keyboard players only).
- [ ] With `smooth_animation = 6` (the default): the duck shows cleanly, no slide or doubled knight.

## D145 – The block stops a ratman's bite and claw

Run Setup.bat again first (the fixed game changed). Custom rules on or off. A ratmen fight (the Great Forest).

- [ ] Face a ratman and block (back + down + hit) as it bites or claws: the knight loses no hit points, and the block
      goes on; the ratman just finishes its blow (it is not thrown back).
- [ ] A ratman that jumps over you and bites from behind: the block does not stop it.
- [ ] Without a block (standing, or with the downward stab or the straight thrust) the bite and claw hurt as before.
- [ ] Custom rules on with `timed_defence = on`: a block started just before the bite stops it; a block held for a
      while (started long before) does not, as against the troggs. With `timed_defence = off` a held block holds.

## D146 – Smooth animation: in-between poses for the swing, the overhead chop and the lunge

Run Setup.bat first (it makes `SAVEHOOK.INB` again, now with the attacks' in-between poses, about 3 MB, from your own
game files), then Custom_rules_on.bat. `[Rules] smooth_animation = 6` as in D136. The dev install `rebuilt` already
has the file. What to judge is the look in the real game: the attacks were approved from the sample page, not yet in
play. The poses are shown one tick late, as the walk's (your decision of 20 Nov 2026).

- [ ] Start the game: the DOSBox-X window shows no new error line, and the walk's in-between poses (D143) still show.
- [ ] Practice (first menu, key 9, the trolls): swing (forward + hit) facing left and facing right. The knight winds
      up, sweeps forward and raises the sword in one motion; the arc grows with the sword; no doubled or missing knight
      for a moment, the colours of the armour and the sword as in the game's own pictures.
- [ ] The overhead chop (up + hit) and the lunge (forward + down + hit), both facings: the chop raises the sword behind
      the head and brings it over the top and down; the lunge stretches out and comes back to its stance.
- [ ] Strike a troll (or another knight in a teams practice): the blow that lands goes back to the ready pose smoothly,
      and the struck figure's reaction is as before (it has no in-between poses).
- [ ] A two-player or teams practice, the second knight (the green, HE look) striking both ways: the same.
- [ ] Block in time (back + down + hit), then the quick swing; dodge (down + hit), then the riposte: they look like the swing
      and the lunge; the timing windows feel as before (in-between pictures are only drawn, never hit).
- [ ] Walk, then strike without stopping: the blow's first pose appears at once (no in-between from the walk into
      it), then the blow runs smoothly.
- [ ] The backward thrust, the upward thrust, the dagger throw, the block and the dodge themselves look as before (they
      are the next step).
- [ ] `smooth_animation = 2` and `3`: the same blows with one or two in-between pictures a tick.
- [ ] Optional: the fight's pace with several knights striking at once (`draw_TPS = yes`): about 9 ticks a second, as
      before.

The pictures changed after your review of every picture on 21 Nov 2026 (the fixes you approved from the side-by-side
page, "Fixed, with 5(a)"). Run Setup.bat again (the file is now about 2.8 MB); the dev install `rebuilt` has it.

- [ ] The swing and the fast swing: the motion trail only behind the sword (where it has been), never ahead of it,
      and no stray trail pieces; the sword the arm's straight extension.
- [ ] The overhead chop: the sword a straight extension of the arm in every picture, the trail only behind it.
- [ ] The lunge: the blade comes up from the stance and stays at or just below the line of the reach; no break at the
      waist, the hands with the sword.
- [ ] The riposte (dodge, then the riposte): a faster lunge, the blade turned level before the arm reaches out, then
      at the lunge's own height.
- [ ] The hit endings of the lunge (strike a troll with the lunge): still back to the ready pose smoothly.

## D147 – Smooth animation: in-between poses for the remaining attacks, and the no-spin dagger throw

Run Setup.bat first (it makes `SAVEHOOK.INB` again, now about 3.9 MB, and turns the held dagger in your `KN4.OB`),
then Custom_rules_on.bat. `[Rules] smooth_animation = 6` as in D136. The dev install `rebuilt` already has both. What
to judge is the look in the real game: the remaining attacks were approved from the review page (21 Nov 2026), not yet
in play. The poses are shown one tick late, as the walk's and D146's.

- [ ] The backward thrust (back + hit) facing left and facing right, as the KN (blue) and the HE (green) knight: the
      sword goes down in front and back in one motion; no doubled or missing knight for a moment.
- [ ] With timed defence on the backward thrust is always the fast one: the sword sweeps down in front and back
      (not over the knight's back), then comes up to the ready pose.
- [ ] The upward thrust (forward + up + hit): the knight leans into the thrust with the sword on its line, the sword
      the arm's straight extension in every picture.
- [ ] The dagger throw (back + up + hit): the knight holds the dagger by its hilt, the point up and back (also with
      `smooth_animation = 1`: this is the game's own frame, changed); through the throw the point stays away from the
      knight, the dagger in the forward fist until the release; then it flies as before.
- [ ] Hold the throw key: the throws follow one another smoothly (from the thrown pose straight back to the raised one).
- [ ] The dagger's and the sword's colours with an enchanted weapon (D31's tint) as in the game's own frames.
- [ ] The block and the dodge (back + down + hit, down + hit): in and out smoothly; the dodge's sword changes hands at
      mid-tick (the game's two frames hold it in different hands).
- [ ] Strike a troll with the backward thrust: back to the ready pose smoothly.
- [ ] The timing windows of the block and the dodge (timed defence) feel as before (in-between pictures are only
      drawn, never hit).
- [ ] A move begun straight from a held block, dodge or the thrown pose (a new key while holding) still changes its
      pose at once (no in-between poses there yet), and nothing flickers.
- [ ] Optional: `Fixes_Off.bat` (the original game) also shows the dagger held by its hilt (your choice: the frame
      is changed in place).
- [ ] Optional: the fight's pace with several knights striking at once (`draw_TPS = yes`): about 9 ticks a second, as
      before.

## D148 – Smooth animation: moves begun straight from a held block, dodge or thrown pose

Run Setup.bat first (it makes `SAVEHOOK.INB` again, now about 5.3 MB), then Custom_rules_on.bat.
`[Rules] smooth_animation = 6` as in D136. The dev install `rebuilt` already has it. What to judge is the look in the
real game: these moves were approved from the review page (21 Nov 2026), not yet in play. The poses are shown one
tick late, as D146's and D147's.

- [ ] Hold the block (back + down + hit) and, still holding, change the keys to another blow (the lunge, the chop,
      the dagger throw, the dodge): the knight goes from the block into the new move in poses in between, not at once.
- [ ] The same from a held dodge (down + hit): into the chop, the dagger throw and the fast backward thrust.
- [ ] From the dodge into the swing or the fast backward thrust: the sword goes over the head forward, down in
      front and back (not a jump), as the same blow from standing does.
- [ ] Throw a dagger and change the keys at once to the swing or the block: from the thrown pose the knight goes
      into the new move in poses in between; the sword appears with the new pose.
- [ ] As the KN (blue) and the HE (green) knight, facing left and facing right; no doubled or missing knight for a
      moment, and the sword's colours with an enchanted weapon as in the game's own frames.
- [ ] The timing windows of the block and the dodge (timed defence) feel as before.
- [ ] The game starts as before (SAVEHOOK reads the bigger file in a few seconds), and the fights' pace is as
      before (`draw_TPS = yes`: about 9 ticks a second).

## D149 – The Gem of Keyfinding shows only the nearest missing key

Custom rules on, `rare_gems = on`, `rare_gem_chance = 100` so that the gem turns up (or start with one from a chest).
The dev install `rebuilt` already has it (no Setup.bat needed; a new game). The rule: of the keys your knight does not
hold, the one whose holder is nearest the knight on the map is shown (the distance across plus the distance down, from
your knight to a lair, another knight or its grave, or the High Temple in High Wood). Two equally near: the first of
Forest, Wasteland, Swamp, Moors. A key nobody can walk to (the dragon's hoard, or nobody's) counts as the farthest.

- [ ] Use the gem on the item screen opened on the map (the item key): the screen closes, and the key screen names **one**
      key and its holder (for example "Swamp key: a glowing lair"), not four; its line is at the top and "Press fire to
      continue" follows. After the fire key only that lair glows on the map until your turn ends.
- [ ] The key shown is the missing key nearest your knight: stand near a lair you know holds a key (the Gem of Seeing or
      the IDROPPEDMYKEY cheat tells you which), use a fresh gem there: that key is the one shown. Move to another part
      of the map and use another: the key nearest there is shown.
- [ ] A key your knight already holds is never shown, even when its lair is next to you: take a key from a lair, then
      use another Keyfinding gem: it names a different key.
- [ ] A key held by another knight: it names the knight ("<name>'s grave" if that knight is dead) when that is the nearest;
      the High Temple when it is nearest and holds a key.
- [ ] With three keys in your hands the gem shows the fourth; with all four keys the gem does nothing when clicked (it
      stays in its place, no screen).
- [ ] The gem used at Math's or right after a fight with a knight still shows its screen before your turn ends, and
      never in the next player's turn (as in D113).
- [ ] The IDROPPEDMYKEY cheat code (`cheat_codes = yes`) is unchanged: all four keys named, every lair holding one
      glows.
- [ ] The gem works as above with `cheat_codes = no` too.

## D150 – The dragon attacks its own knight in a co-op dragon practice

Custom rules on, `anticheese = yes` and `monster_target = nearest` (the defaults). The dev install `rebuilt` already has
it (no Setup.bat needed). The practice menu with 2 or 3 players chosen, then the D key (the dragon with every knight on
one side). Your save slot 3 was this case: the dragon breathed fire again and again and nobody was ever hurt.

- [ ] 2 knights: walk the second knight (not player 1's) 100-200 pixels to the dragon's right, nearer the dragon than
      player 1's knight, and stand still. The dragon comes level with it and its far fire burns it (the knight loses HP).
      Then it goes for the other knight and burns it the same way.
- [ ] 3 knights: the same with the knight nearest the dragon being the second or the third: the fire burns that one
      first, then the next. The fight ends (no endless fire).
- [ ] A knight that runs up or down as soon as the dragon rears its head for the far fire still gets away (D68), with
      2-3 knights as with one.
- [ ] One knight (one player, the D key): the dragon fights as before.
- [ ] `monster_target = first`: the dragon goes for player 1's knight first, as before.
- [ ] HOTSTUFF (typed in the first menu, then the D practice with 2-3 players): player 1's dragon moves and breathes by
      the keys as before.

## D151 – The riposte against the troll and the hammer trogg; one riposte for each blow

Custom rules on, `timed_defence = on` (the default). The dev install `rebuilt` already has it (no Setup.bat needed).
The riposte is down + toward the foe + fire while its blow from above is in the air (the fast thrust).

- [ ] The troll (practice key 9): riposte its blow from above. The riposte does its damage (the troll's HP bar drops),
      but the troll does not flinch: its club comes down and hits the knight if it is in reach, and then the troll pauses
      as after any blow.
- [ ] The troll: a riposte just as the club comes down (late): the same, both blows land.
- [ ] The troll with little HP left: a riposte that takes its last HP kills it (its death as before).
- [ ] The troll: a riposte at close range (the troll just ahead of the knight): its push after the blow as before.
- [ ] The hammer trogg (practice key 3): riposte its blow from above. The riposte hurts it, but its hammer still comes
      down and hits; it then waits before its next blow. Riposting all the time no longer keeps it from ever hitting.
- [ ] The axe trogg (practice key 4): as before: a riposte stops its blow (it flinches).
- [ ] One riposte for each blow: riposte the troll's blow, and press the riposte again at once while the same blow is
      still under way: the second is the ordinary (slower) lunge. Against its next blow the riposte is fast again.
- [ ] Against another knight (two players): a riposte on its blow from above stops that blow, also when both land at
      the same moment; a second press against the same blow gives the ordinary lunge.

## D152 – A short tap backwards turns the knight

Custom rules on, `input_chord = 2` (the default). The dev install `rebuilt` already has it (no Setup.bat needed). Any
fight or practice, a knight on the keyboard (player 1's arrows, player 2's W A S D or the third key set).

- [ ] Standing, facing the foe: tap the back key as briefly as you can. The knight turns round (a moment after the tap),
      without a step.
- [ ] Tap it several times, short and a little longer: every tap turns the knight once (each tap turns it back again).
- [ ] Tap back and at once press forward: the knight walks forward and does not turn.
- [ ] Tap back and at once press fire: the attack as before (no turn after it).
- [ ] The chords as before: back + down + fire together is the block, back + up + fire the dagger throw, keeping the
      facing; walking down (down held), then back + fire is the backward thrust (the ratmen fight, D142).
- [ ] Holding the back key turns the knight as before.
- [ ] A joystick knight turns as before.

## D153 – Fights and turns start quickly again; no automatic save at a practice fight

Custom rules on or off, `save_mode = autosave_and_manual` (the default). The dev install `rebuilt` already has the new
SAVEHOOK.COM and SAVEHOOK.INB (no Setup.bat needed there); on another install rerun Setup.bat once (an old SAVEHOOK.INB
is refused: until Setup makes it again, the knights' in-between poses are drawn in place).

- [ ] A lair fight on the map: the knights and the monsters walk in about as soon after the map as before the attack
      poses came (D146): no longer a wait of several seconds.
- [ ] The same for a knight duel and the dragon.
- [ ] A human knight's turn on the map starts without the long pause.
- [ ] After a few fights and turns, `save` has new files in slots 91-94 (turns) and 96-100 (fights), each about 2 MB, and
      each loads (Capture menu or F11+L) and plays on.
- [ ] A practice fight from the menu (one knight, a co-op practice, a two-player practice, a practice lair): it starts at
      once, and no file in slots 96-100 changes.
- [ ] The smooth animation as before: the walk's in-between poses and every blow's (swing, lunge, chop, backward thrust,
      dagger throw, block, dodge) still drawn, both knight looks, both facings.
- [ ] An automatic save made before this build (a FIGHT or TURN slot from 22-23 Nov) still loads and plays on.
- [ ] Optional: `compresssaveparts = false` under `[dosbox]` in `moonstone-dosbox-x.conf`: saves are made a little faster,
      each file about 41 MB; a save made with `true` still loads, and the other way round.
