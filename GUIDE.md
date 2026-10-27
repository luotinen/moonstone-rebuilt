# Moonstone: A Hard Days Knight – player's guide

This guide covers what the original manual covers, written anew for Moonstone Rebuilt, plus the rules the manual
leaves out. Everything in it was checked against the DOS program (`MAIN.EXE`) where possible.

* **[In square brackets]:** the manual says something different from what the game does, or the manual's claim has
  not been checked in the program yet. *(manual p. N)* points to the page of the original manual (the GOG PDF).
* **Rebuilt:** something that Moonstone Rebuilt changes. With `Fixes_Off.bat` the original behaviour returns.

The GOG manual was written for the Amiga version (joystick, disk drive DF0:). The DOS version plays the same game with
the keyboard or a joystick.

## Contents

1. [The quest](#1-the-quest)
2. [Starting a game](#2-starting-a-game)
3. [Controls](#3-controls)
4. [Your knight](#4-your-knight)
5. [Days, turns and the moon](#5-days-turns-and-the-moon)
6. [The map](#6-the-map)
7. [Places](#7-places)
8. [Fighting](#8-fighting)
9. [Monsters](#9-monsters)
10. [Other knights, the dragon and the Guardian](#10-other-knights-the-dragon-and-the-guardian)
11. [Magic items](#11-magic-items)
12. [Prices](#12-prices)
13. [Tips](#13-tips)

## 1. The quest

Once in a thousand years the moon spirit Danu rewards the greatest warrior in the land. Up to four knights compete
for the reward. To win, a knight has to:

1. find the four **keys**, one hidden in a lair in each of the four regions;
2. enter the **Valley of the Gods** in the middle of the map and beat the **Guardian**, a demon, to win a **Moonstone**;
3. carry the Moonstone to **Stonehenge** while the moon is in the phase that matches that stone.

The first knight to do this wins. A knight who loses all five life points is out. *(manual pp. 3–4)*

The land has four regions:

| Region | Where | Lair monsters |
|---|---|---|
| Misty Moors | north-west | troggs (spear and axe), war beasts |
| Northern Wastelands | north-east | Baloks, troggs |
| Great Forest | south-west | ratmen, axe troggs |
| Wetlands | south-east | mudmen, trolls |

The dragon flies over all of them, and Black Knights roam the land hunting the questing knights.

## 2. Starting a game

The menu has these options *(manual p. 14)*:

* **Number of players:** 1 to 4 human players. Knights without a human player are played by the computer.
* **Gore:** turns the bloody deaths on or off.
* **Practice:** two players fight each other straight away, without the map.
* **Select knight:** pick a knight and type a name, then press Enter (or fire).

Every knight starts with *(manual p. 14; same in the code, `1000:1FAE`)*:

* strength, constitution and endurance 1;
* 5 life points and 20 hit points;
* padded armour and a long sword;
* 10 throwing daggers (also the most a knight can carry);
* 10 gold pieces.

Each knight starts in their own home village. Other knights cannot enter it.

[Moonstone Rebuilt: `custom_rules.ini` can change these starting values for each knight, and much else; see the README, *Custom rules*. This guide describes the normal game.]

## 3. Controls

The manual describes only a joystick. The DOS keys are:

| | Player 1 | Player 2 |
|---|---|---|
| Move | arrow keys | W A S D [original: W A X D; Rebuilt: S is down, D9] |
| Fire (enter a place, attack, choose) | Enter | Tab |

On the map *(manual p. 6)*:

* **Space:** shows the knight's inventory. Magic items and stat raises are used there.
* **E:** ends the turn at once. [The manual says this lets the knight rest and recover hit points. In the code
  hit points come back once a day whether the knight walked or not; E only gives up the rest of the turn.]
* **Esc:** ends the whole game with Game Over, without asking. [Original: Q, next to player 2's keys; Rebuilt: Esc, K5.]

A joystick works through DOSBox-X.

## 4. Your knight

### Abilities

Each ability goes from 1 to 5. Experience, Math the Wizard and Mythral the Mystic can raise it to 5 at most. The
manual does not give that limit. *(manual p. 5)*

| Ability | What it does in the game |
|---|---|
| **Strength** | Each point adds 1 to the damage of every attack. |
| **Constitution** | Each point adds 10 maximum hit points. Raising it also gives 10 hit points at once. |
| **Endurance** | Each point lets the knight walk further per turn. |

The exact formulas *(not in the manual; `1000:028D`, `1000:02E7`)*:

* **Maximum hit points** = 10 × constitution + 10 + 20 for each Ring of Protection + the armour bonus.
  * Armour bonus: padded 0, chain mail 10, plate mail 20, battle armour 30.
* **Movement per turn** = 16 × (2 × endurance + 4, + 2 for chain mail or battle armour).
  * [Plate mail gives no movement bonus, although chain mail and battle armour do. Probably an original slip; kept.]
* **Armour does not reduce damage.** It only raises the maximum hit points. The manual doesn't say this.

### Hit points and life points

Hit points are the knight's health in a fight. When they drop to 0, the fight is lost, and so is one **life point**.
A knight has at most 5 life points; at 0 the knight is dead and out of the game. *(manual pp. 5–6)*

The manual doesn't say that a knight who loses a fight gets all hit points back: losing costs the life point, not
the hit points. *(code `1000:0AC8`)*

Hit points come back:

* **Every day by themselves:** about a quarter of the missing hit points (at least 1). The manual only says that
  knights heal each day. *(code `1000:11BF`)*
* **At a healer:** 10 gp for a full heal *(see 7)*.
* **With a Potion of Healing** *(see 11)*.
* **With an offering at Stonehenge** *(see 7)*.

Life points come back at the healer, with a potion, at Stonehenge and in the home village; the details are in the
sections below.

### Experience

A knight earns experience points *(manual p. 5; same in the code)*:

| Event | Points |
|---|---|
| Clearing a lair (the first time only) | 1 |
| Killing the dragon | 2 |
| Beating the Guardian | 3 |

Experience buys ability points from the inventory screen (the "Increase …" entries). One point costs:

* 1 experience point with 3 or 4 players;
* 2 with 2 players;
* 3 with 1 player.

[The manual leaves out that **computer-controlled knights** gain extra experience: 1 point for every duel they win
against another knight, and 1 point plus a free visit to Math every moon phase (four days). They grow stronger even
without clearing lairs.]

### Limits the manual leaves out

| Thing | Limit |
|---|---|
| Gold | 150 gp (manual p. 14). Gold above that is lost without a message. |
| Throwing daggers | 10 |
| Life points | 5 |
| Abilities | 5 (magic items can raise them above that for a while) |

## 5. Days, turns and the moon

* Each knight gets one turn per day. During a turn the knight walks until the movement for the turn is used up, or
  the player ends it with E.
* The moon has eight steps that repeat: full → ¾ → half → ¼ → new → ¼ → half → ¾ → full. *(manual p. 6)*
* [The manual says the moon moves on after every knight has had **three** turns. In the code it moves on every
  **four** days (`1000:115B`, run once at the end of each day).]

The moon matters for two things:

* **Ratmen** change strength with the moon *(see 9)*.
* **Moonstones:** each of the four Moonstones belongs to one phase (full, new, waxing half or waning half). To win,
  the knight must reach Stonehenge while the moon is in that phase. During its phase the stone also helps in fights.
  [The manual says a Moonstone doubles the knight's hit points in its phase. In the code it doubles the damage of the
  knight's attacks (`1000:2D73`).]

## 6. The map

Move your knight around the map. When it touches a place or another figure, that figure lights up; press fire to
enter or fight. *(manual p. 6)*

Terrain slows the knight down *(code `1000:A901`)*:

| Terrain | Speed |
|---|---|
| Open ground | full |
| Forest, swamp, rocks | ½ |
| Mountains | ¼ |

[The manual says forest, mountains and swamp also make wandering monsters more likely. The DOS version has no
wandering monsters at all: fights happen only at lairs, against the dragon, Black Knights and other knights, and in
the Valley.]

## 7. Places

### Lairs

Each region has six lairs with a fixed type and number of monsters. Clear the lair to get its treasure.
*(manual p. 7)*

| Region | The six lairs (monster × number) |
|---|---|
| Great Forest | ratmen 10, axe troggs 10, axe troggs 14, ratmen 14, ratmen 14, axe troggs 13 |
| Northern Wastelands | Baloks 4, Baloks 3, Baloks 5, troggs 10, troggs 10, troggs 10 |
| Wetlands | mudmen 5, mudmen 5, mudmen 5, trolls 7, mudmen 6, trolls 6 |
| Misty Moors | spear troggs 4, spear troggs 5, spear troggs 6, war beasts 9, axe troggs 13, war beasts 8 |

What the manual leaves out about lair treasure *(code `1000:1E2D`)*:

* At the start of each game one lair per region is chosen at random to hold that region's key.
* The rest of the treasure is also rolled at the start of the game:
  * about 40 % of the lairs have only gold (10–31 gp);
  * about 15 % have two magic items;
  * about 45 % have gold and two magic items.
* There is only one **Sword of Sharpness** in the whole game.
* Experience comes only from the first clearing of a lair.

### Highwood (Misty Moors)

The druids' city. In the **High Temple** the druids buy and sell magic items. Point at an item to see its price.
*(manual p. 7)* The prices are listed in [section 12](#12-prices). [The manual gives no prices for the temple.]

### Waterdeep (Wetlands)

Home of **Mythral the Mystic**. Mythral takes a donation and then raises or lowers one random ability by 1.
*(manual p. 7)*

The manual only says that at least 10 gp improves your chances. The real odds of a rise *(code `1000:BB65`)*:

| Donation | Chance of a rise |
|---|---|
| 1–9 gp | 24 % |
| 10–19 gp | 32 % |
| 20–29 gp | 40 % |
| 30–39 gp | 48 % |
| 40–49 gp | 55 % |
| 50 gp or more | 70 % |

* An ability never drops below 1 or rises above 5. If all three are already 5, nothing happens.
* Below 30 gp you lose more often than you win.
* [Original: Mythral sometimes changed the wrong value and showed garbled messages. Rebuilt: fixed, K11.]

### Healers, taverns and merchants (both cities)

* **Healer** *(manual p. 7)*:
  * 10 gp heals all hit points;
  * 15 gp buys one life point (up to 5); the knight must be at full hit points first.
  * The healer also cures the ratmen disease *(see 9; code `1000:BCC9`)*.
* **Tavern:** the dice game. Bet 1–5 gp and roll three dice. The manual lists the winning combinations and their
  payouts, from 4:1 up to 30:1 for three dragons. *(manual pp. 7–8)*
  * The payouts in the code are the same as in the manual (table DS:D125). The order of the dice doesn't matter.
  * What the manual leaves out:
    * The bet is taken first, and a win pays bet × odds. So "4 to 1" turns a 1 gp bet into 4 gp: 3 gp profit.
    * The dice are fair: each of the six faces is equally likely. Three dragons come up once in 216 rolls.
    * Winnings stop at 150 gp like all gold. (On the Amiga they could go past it; the DOS code caps them,
      `1000:B4CA`.)
  * [The tavern's Exit button reacts only a little to the right of where it is drawn; not yet fixed.]
* **Merchant:** sells daggers, weapons and armour *(see 12)*.

### Home village

Only its own knight can enter. *(manual pp. 5, 8)*

[The manual says a knight with fewer than 3 life points is healed to full hit points and given a life point, at most
three times per game. In the DOS code (`1000:112A`) a knight with fewer than 3 life points gets one life point, every
time. No full heal and no three-visit limit were found.]

### Math's tower (Northern Wastelands)

**Math the Wizard** gives a visitor one of four things *(manual p. 8; odds from the code, `1000:B8D6`)*:

* a magic item;
* +1 to a random ability;
* 10–31 gold;
* or turns the knight into a frog.

The manual says that visiting often makes him more likely to be annoyed. In detail:

* On the first visit he never turns you into a frog.
* After a visit he is very annoyed. The annoyance wears off over seven days.
* Going straight back is a bad idea: the chance of becoming a frog is then 84 %. After seven or more days it is 15 %.

| Since the last visit | Item | Ability | Gold | Frog |
|---|---|---|---|---|
| first visit | 28 % | 36 % | 35 % | 0 % |
| 7 days or more | 24 % | 31 % | 30 % | 15 % |
| about 4 days | 1 % | 31 % | 16 % | 52 % |
| next day | 0 % | 1 % | 16 % | 84 % |

[The manual says the frog lasts "a number of turns". It lasts three days.]
[Original: Math never raised endurance and could show a garbled message. Rebuilt: fixed, K11.]

### Stonehenge

* A knight who brings the right Moonstone while the moon is in its phase wins the game.
* **Offering:** a knight can offer a magic item here. Danu then heals all hit points and gives one life point (up to
  5). The offering also cures the ratmen disease. *(manual p. 9; code `1000:10A7`)*
  * Danu takes any of the nine magic items: the potion, the Gem of Seeing, the Ring, the Talisman and the five
    scrolls. The Sword of Sharpness is refused (`1000:CC75`); daggers, keys and Moonstones cannot be offered.
    (On the Amiga, daggers were accepted by mistake.)

### The Valley of the Gods

Only a knight with all four keys can enter. Inside waits the Guardian; beat it to win a Moonstone. *(manual p. 9)*

* [The manual says other knights cannot touch you while you stay in the Valley. In the DOS version you don't stay:
  entering starts the Guardian fight at once, and afterwards you are back on the map (`1000:0FCB`).]
* What the manual leaves out:
  * Winning **uses up all four keys**. If you later lose the Moonstone, you have to find the keys again.
  * Which of the four Moonstones you get is random, each equally likely.
  * If you lose, you keep the keys.

## 8. Fighting

Hold fire and push a direction to attack; without fire the knight walks. The moves, for a knight facing right
*(manual p. 15; base damage from the code, `1000:177D`)*:

| Direction + fire | Move | Base damage | Use |
|---|---|---|---|
| up | Overhead chop | 4, doubled to 8 | hardest blow, but slow and easy to dodge |
| up + forward | Upward thrust | 3 | hits enemies jumping over you |
| forward | Swing | 4 | sweeps the area in front |
| down + forward | Lunge | 3 | longest reach of the sword moves |
| back | Backward thrust | 2 | hits behind you |
| up + back | Throw dagger | 3 | uses one dagger; long range |
| down + back | Block | – | stops swings |
| down | Special defence | – | the move against each monster's special attack |

When the knight turns round, forward and back swap.

**Damage** of a knight's attack *(not in the manual; `1000:2D73`)*:

* base damage + strength + weapon bonus;
* weapon bonus: long sword 0, broadsword 2, claymore 3, Sword of Sharpness 5;
* doubled for the overhead chop;
* doubled again with a Moonstone in its phase.

Other things to know:

* Monsters' damage is fixed per monster *(see 9)*. Armour does not reduce it.
* A knight that starts to flicker has 10 hit points or fewer left. *(manual p. 15)*
* Many monsters have a special attack that leaves the knight helpless; the special defence (down + fire) counters it.

## 9. Monsters

Hit points and damage to a knight per hit, from the code *(descriptions: manual pp. 10–11)*:

| Monster | Where | Hit points | Damage | Notes |
|---|---|---|---|---|
| Spear trogg | Moors | 15 | 3 | |
| Axe trogg | Moors, Forest | 20 | 3 | |
| Trogg | Wastelands | 20 | 2 | |
| War beast | Moors | 10 | 5 | the troggs' beasts |
| Ratman | Forest | 5–12 | bite 3–8, claw 1–5 | changes with the moon, see below |
| Mudman | Wetlands | 30 | 2 | rises out of the mud |
| Balok | Wastelands | 30 | 5 | |
| Troll | Wetlands | 40 | 7 | its overhead chop can kill outright |
| Dragon | everywhere | 50 | 10, fire 20–30 | |
| Guardian | Valley | 250 | 8–10 | |

* **Ratmen** *(manual p. 10)*. The manual says they grow stronger as the moon waxes.
  * [Original: strong at full moon and strongest at new moon. Rebuilt: strongest at full moon, strong at ¾, as in
    the manual (K2).]
* **The ratmen disease.** The manual warns that a bite carries a deadly disease that must be cured quickly.
  * [Original: the game never says when you catch it. A diseased knight lost one life point at every change of moon
    phase until a healer, a healing potion or an offering at Stonehenge cured it.]
  * [Rebuilt: removed (K17), because players took the silent life loss for a bug.]
* **Talisman of the Wyrm:** each Talisman halves the dragon's damage, down to at least 5. *(manual p. 12; code
  `1000:4400`)*
* **Black Knights:** they hunt the knights closest to winning. [The manual says they get stronger and more skilled
  during a fight. No such code was found: the only ability rise anywhere in the fight code is a computer knight's
  rise after winning a duel.]
* **Guardians:** the manual says they drain abilities and that losing to one costs three life points. The code
  agrees *(`1000:0FF5`)*:
  * losing costs the usual life point plus two more;
  * one random ability drops by 1, but not below 1.
  * [Original: the random ability was picked with the same broken table as Math's gift. Rebuilt: fixed, K11.]

## 10. Other knights, the dragon and the Guardian

**Duels.** Walk into another knight to challenge them. *(manual p. 9)*

* The manual says the winner takes either all the loser's gold or one item. A human winner gets one pick on the loot
  screen; taking the loser's weapon or armour keeps whichever is better for the winner, and the loser is left with a
  long sword or padded armour.
* A computer winner takes the first thing it finds, in this order:
  1. a Moonstone or a key;
  2. the Sword of Sharpness;
  3. the other items;
  4. better armour;
  5. otherwise half of the loser's gold.
* If the loser loses the last life point, the winner takes everything. *(code `1000:0AF7`)*
* [Original: taking the loser's weapon when it was the Sword of Sharpness left the sword with both knights. Rebuilt:
  the sword moves with the weapon (K16).]
* [Original: a computer knight's ability rise after winning a duel had no limit of 5. Rebuilt: limit 5 (K16).]

**Scroll of Protection.** If another knight attacks you and you have one, you may use it to avoid the fight.

**The dragon** picks a random living knight as its target and flies after it. *(manual p. 10)*

* [The manual says a dragon that beats a knight takes **all** the gold and one magic item. The code *(`1000:0CF3`,
  `0AF7`)* works like this:
  * The dragon takes **half** of the gold.
  * It also takes one thing, first match in this order: a Moonstone or a key, the Sword of Sharpness, another
    magic item, and finally better armour.
  * If the knight loses the last life point, the dragon takes everything, as the manual says.]
* What the manual leaves out:
  * A computer-controlled knight never fights the dragon: it just loses a life point and the loot.
  * A knight who is a frog, or has no life points left, is robbed without a fight.
* Whoever kills the dragon gets 2 experience points and opens the dragon's hoard. That screen has no one-pick limit,
  so you can take everything, as the manual says.
* Carry Talismans of the Wyrm before you fight it.

**The Guardian** *(manual p. 11)*:

* Beat it for a Moonstone and 3 experience points.
* Fight it with the best armour you can get and full hit points.

## 11. Magic items

Use a magic item from the inventory (Space), by pointing at it and pressing fire. *(manual pp. 12–13)*

* Potions, scrolls and the Gem of Seeing are used up when used.
* Other items last: the Sword of Sharpness, the rings, the Talismans, the keys and the Moonstones.

| Item | Effect |
|---|---|
| Potion of Healing | Heals all hit points; at full hit points it gives one life point instead (up to 5). Also cures the ratmen disease (`1000:CCA9`). |
| Gem of Seeing | Turns your figure into a crystal ball for a moment: fire on a lair to see its treasure. Useful for finding the keys. |
| Sword of Sharpness | The best weapon: +5 damage (claymore +3). Only one exists. |
| Ring of Protection | +20 maximum hit points for each ring. |
| Talisman of the Wyrm | Halves the dragon's damage; several Talismans halve it again (at least 5 damage). |
| Scroll of Haste | Doubles the movement of a turn. |
| Scroll of Acquisition | Take one item from another knight. Use the arrows in the middle of the screen to choose the knight. |
| Scroll of the Hawk | Fly to any place on the map except the Valley of the Gods. |
| Scroll of the Wyrm | Send the dragon after another knight. |
| Scroll of Protection | Avoid a fight when another knight attacks you. |
| Key | One per region; all four open the Valley of the Gods. |
| Moonstone | Wins the game at Stonehenge in its moon phase; doubles your damage in that phase. |

**Curses.** The manual says scrolls can be cursed, but not how a scroll gets cursed. In the code nothing curses a
scroll in advance: there is a random chance each time a scroll is read *(`1000:CD16`, `CD5C`)*.

| Scroll | According to the manual | In the code |
|---|---|---|
| Hawk | you land at a random place | yes: 1 read in 8 |
| Protection | your controls are reversed in the fight | yes: about 1 read in 12; the next fight only |
| Haste | half movement instead of double | [never: the code for it exists but is never reached] |
| Wyrm | the dragon attacks you | [never: no curse in the code] |

## 12. Prices

**Merchant** (both cities) *(manual p. 8; same in the program's texts)*:

| Item | Price |
|---|---|
| Throwing dagger | 2 gp |
| Broadsword | 10 gp |
| Claymore | 25 gp |
| Chain mail | 30 gp |
| Plate mail | 50 gp |
| Battle armour | 75 gp |

**High Temple in Highwood.** [Not in the manual. Prices from the program's texts; which items are on offer at a
time has not been checked.]

| Item | Buy | Sell |
|---|---|---|
| Sword of Sharpness | 100 gp | 50 gp |
| Ring of Protection | 50 gp | 25 gp |
| Talisman of the Wyrm | 52 gp | 26 gp |
| Scroll of Acquisition | 52 gp | 26 gp |
| Scroll of the Hawk | 52 gp | 26 gp |
| Scroll of the Wyrm | 40 gp | 20 gp |
| Scroll of Haste | 36 gp | 16 gp |
| Gem of Seeing | 32 gp | 16 gp |
| Scroll of Protection | 24 gp | 12 gp |
| Potion of Healing | 20 gp | 10 gp |
| Moonstone | 20 gp | 10 gp |
| Key | 12 gp | 6 gp |

**Healer:** a full heal costs 10 gp; a life point costs 15 gp.

## 13. Tips

* Spend experience as soon as you have it. Constitution keeps you alive, strength shortens fights, and endurance gets
  you around faster.
* Armour only adds hit points. Plate mail is +20 hit points but no faster than padded armour; battle armour is both.
* Keep at most 150 gold. Spend the rest before you pick up more, or it is lost.
* Visit Math at most once a week; give Mythral at least 30 gp, or don't go at all.
* Computer knights grow stronger every four days whatever happens. A long game favours them.
* Hit points come back by about a quarter of what is missing every day, so a hurt knight can wait a day or two
  near a lair instead of paying the healer.
* Fight the Guardian only with good armour, rings and full hit points.

---

The original manual and game are © 1991 Mindscape International and Rob Anderson. This guide is a new text written
for Moonstone Rebuilt and contains no text from the manual.
