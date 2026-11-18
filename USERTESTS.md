# Moonstone Rebuilt – tests for the player

One checklist of everything that needs a human to play it. Tick as you go:

- `[ ]` not tried yet
- `[x]` tried, works
- `[*]` tried, there is something to report (write a short note after the line: what you did, what you saw)

Each task has its own section, named by its task code (D = improvement or fix, K = co-op fix; the same codes as in
`FIXES.md`), newest first. A task that changes something you can see adds its section here.

## How to start a test

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

- [ ] Start the game: the DOSBox-X window shows no line "no XMS, or no SAVEHOOK.OVL of this build" before the game.
- [ ] On the map, type a map code (WEPL, HOMESICK, ONEMORETURN, now SIRNEVERTIRED): each does what CHEATS.md says, as before.
- [ ] On the map, IDROPPEDMYKEY: the screen of who holds each key, fire, the map again, the lairs with keys glow.
- [ ] In the item screen, an item code (IDKFA, PUTARINGONIT): the items come, max HP follows.
- [ ] Type a fight code on the map (IDDQD or another from CHEATS.md), then start a fight: the code is on in it.
- [ ] In the tavern, LOADEDDICE, then the dice game: every throw wins, until you leave.
- [ ] Type IDROPPEDMYKEY, end the turn, and on your next turn press F11+S (a save). Close DOSBox-X, start the game
      again, press F11+L: the game goes on where it was saved; type IDROPPEDMYKEY and WEPL again: both work.
- [ ] Move `SAVEHOOK.OVL` out of the game folder, start the game: the line "no XMS, or no SAVEHOOK.OVL of this
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
