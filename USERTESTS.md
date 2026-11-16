# Moonstone Rebuilt – tests for the player

One checklist of everything that needs a human to play it. Tick as you go:

- `[ ]` not tried yet
- `[x]` tried, works
- `[*]` tried, there is something to report (write a short note after the line: what you did, what you saw)

Each task has its own section, named by its task code (D = improvement or fix, K = co-op fix; the same codes as in
`FIXES.md`), newest first. A task that changes something you can see adds its section here.

## How to start a test

1. Use the dev install `F:\Claude\Moonstone\rebuilt` and start it with `Start.bat`.
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

Open `F:\Claude\Moonstone\rebuilt\SOUNDS.html` in a browser (made again on 15 Nov 2026; nothing to set).

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
