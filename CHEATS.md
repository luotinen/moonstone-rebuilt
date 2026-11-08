# Cheat codes

With custom rules on, `cheat_codes = yes` and speedrun mode off in `custom_rules.ini` (`[Rules]`, the default), these codes can be
typed in the game. Type a code in one go (a pause of more than a second starts it over). From its second letter on, the keys
of a code do not reach the game (so the E of HEREBEDRAGONS does not end the turn); the first letter does, except
in the first menu: there D, J, G and B (the dragon's and the Guardian's practice, the joystick set-up, the Black Knights) wait
two thirds of a second for a code's
next letter and only then act. A code typed whole plays the sword clash sound.

## In the item screen (Space on the map, or any item screen)

They act on the knight whose turn it is.

| Code | Effect |
|---|---|
| IDKFA | One more of every magic item, the Sword of Sharpness, the four keys, the four Moonstones, battle armour and 99 daggers |
| ↑ ↑ ↓ ↓ ← → ← → B A | 99 lives |
| HESOYAM, ROSEBUD, KLAPAUCIUS, MOTHERLODE | +20 000 gold (at most 65 535) |
| POINTTAKEN | 99 daggers |
| TINMAN | The next better armour (again and again, up to battle armour) |
| SIRLOIN | The next better sword (up to the claymore; not the Sword of Sharpness) |
| HEADSROLL | The Sword of Sharpness |
| WYRMPROOF | +1 Talisman of the Wyrm |
| MINEALLMINE | +1 Scroll of Acquisition |
| KNIGHTRIDER | The Scroll of Haste's effect for good (from this turn on) |
| HASTALAVISTA | +1 Scroll of Haste |
| SPECIALDELIVERY | +1 Scroll of the Wyrm |
| NOTTODAY | +1 Scroll of Protection |
| FLYBYKNIGHT | +1 Scroll of the Hawk |
| KEYMASTER | The four keys |
| FULLMOONEY | The full-moon Moonstone |
| DARKSIDE | The new-moon Moonstone |
| COMINGSOON | The waxing half-moon Moonstone |
| GOINGGONE | The waning half-moon Moonstone |
| FLESHWOUND | +1 healing potion |
| PEEPINGTOM | +1 Gem of Seeing |
| LIVEANDLEARN | +10 experience |
| SIRLIFTSALOT | Strength 5 |
| BUILTTOLAST | Constitution 5 (max hit points follow) |
| AREWETHEREYET | Endurance 5 (movement follows) |
| DANUBLESS | Full hit points; at full hit points one life more (up to the life cap, `max_lives`, 5 as in the game); at full hit points and lives +1 healing potion |
| PUTARINGONIT | +1 Ring of Protection |
| MOONMAX | Strength, constitution and endurance 5 |

## In a fight (practice or the game)

Each stays on until typed again. They can also be typed beforehand: in the first menu for the next practice
fight only, or on the map for the next fight of the game only (if it applies there: IDDQD needs no human knights against each other).
Several can be typed that way; of codes that clash (THERECANBEONLYONE with JUSTFLESHWOUND or IDDQD, ABACABB with
FINISHHIM) the last one typed counts. A code typed beforehand that was on already stays as it was.

| Code | Effect |
|---|---|
| ROCKETMAN | The knights fly: hold the secondary button to rise, let go to fall; they walk and strike in the air |
| LUNAR | Moon physics: every blow sends the one hit flying a little away (a blow that flings: much farther), slowly as on the moon; the knights and the walking monsters move at half speed; the secondary button makes a knight jump (a long, floating moon jump). With ROCKETMAN on too: holding the secondary button flies, rising faster, and let go the knight floats down slowly |
| MINEFIELD | Ten barely visible mines (small black marks) at random places on the ground; none starts next to a knight. A knight whose feet touch one, the Black Knights too, is blown up, as by the troll's crush, in its own colours (the plain death with gore off, K12, K16 or `death_animations = off`). A monster or computer knight that walks on one simply dies; the dragon and the Guardian do not set them off, nor does anything in the air. A spent mine's mark stays. This fight only. |
| JUSTFLESHWOUND | The players' knights lose no hit points from hits (the instant kills of the monsters' special attacks still kill) |
| THERECANBEONLYONE | Every hit kills |
| FAIRFIGHT | The monsters still to come come at once (up to six on the screen) |
| YOUANDWHATARMY | Twice as many monsters in all |
| FORE | The knights' blows fling the knights they hit, as a troll's blow |
| ABACABB | Three times the blood at every hit (with blood on), and a knight dies at once by a death animation: by the blow (split, thrust, back strike, dagger), else the beheading |
| FINISHHIM | A knight that a blow kills dies at once by the death animation of that blow (else a knight's blow beheads it, a monster's leaves the game's fall) |

With one human knight in the fight:

| Code | Effect |
|---|---|
| IDDQD | Against monsters (and computer knights), every player's knight takes no damage from ordinary hits (special attacks that kill still kill), also in co-op; this fight only. With players' knights against each other it does nothing |

## On the map

| Code | Effect |
|---|---|
| WEPL | The four keys for the knight whose turn it is |
| MOONWALK | The moon goes on to its next phase |
| HOMESICK | The knight whose turn it is goes to its home village |
| ONEMORETURN | No movement is used up this turn; end it with E or by doing something |
| HEREBEDRAGONS | The dragon lives again (if it was killed) and goes for a random knight |
| DRAGONSLAYER | The dragon lives again (if it was killed) and goes for the knight whose turn it is |
| FROGPRINCE | The knight becomes a frog (three days), or a frog a knight again |
| BACKFORSECONDS | All the lairs as at a new game (monsters, treasure and keys) |
| BLACKDEATH | The computer's knights become Black Knights: strength, constitution and endurance 5, the Sword of Sharpness, battle armour, full hit points, and black in fights (until DOSBox-X is closed; their stats stay) |
| SIRWALKSALOT | Unlimited walking on the map for all human knights, on until typed again; end a turn with E or by doing something. Computer knights keep their own limit, or their turns might never end |
| IDROPPEDMYKEY (or IDROPPEDMYKEYS) | Shows who holds each of the four keys: a knight, the dragon, the High Temple or a lair. The lairs holding one glow on the map until the turn ends |
| SIRPICKSALOT | The Valley of the Gods opens with any number of keys, also none, on until typed again |

## In the first menu

| Code | Effect |
|---|---|
| HOTSTUFF | The dragon's fight: player 1 is the dragon. Arrows move it (left and right, nearer and farther); fire with forward (right) = the long, far fire; fire with forward and down = the short, near fire; fire alone (or with another direction) = claw and bite, which eats a knight it holds. It takes the keys when its last move is over, as it chose before by itself. A knight that comes close in front of it (also stepping up or down there) gets its paw at once, whatever the keys: a push away to the right, not the bite. |
| DIRTYRAT | The ratmen's fight (as key 1): player 1 is the ratman. A direction leaps that way (as the ratmen move, but quicker); fire = its swing; fire and down = its thrust; the secondary button = it leaps up into the tree. In the tree it stays as long as you like: the secondary button hangs the knight below it (that knight breaks free with fire and down, on its own keys), fire = it jumps down at its knight, a direction = a leap down that way. It takes the keys when its last move is over. |
| CLUBMEMBER | The trolls' fight (as key 9): player 1 is the troll; off the screen's edge it first walks back in by itself (fire still strikes). A direction steps that way (left and right also turn it); fire = its push (the club swing that flings); up and fire (also up, forward and fire) = its overhead blow. |
| JUMPSCARE | The Baloks' fight (as key 7): player 1 is the Balok. The Balok moves only by jumps: a direction hops that way (left and right also turn it; up and down farther and nearer). A hop up or down crushes a knight it comes down on at once, as the computer's Balok does (the dragon or the Guardian would take one blow instead); a hop only left or right crushes nobody. Fire = its swing, which flings; fire and down = its grab (then its bite or squeeze, as the game's); the secondary button = it grabs a knight in front of it (within its reach, level with it) and crushes it to death, or with none there it makes a big jump forward (with up or down also farther or nearer) that crushes a knight it comes down on. |
| TROGLIFE (or TROGGLIFE) | One of the troggs' fights at random (as key 3, 4 or 6): player 1 is the trogg. A direction steps that way (left and right also turn it); fire = its sideways blow; up and fire (also up, forward and fire) = its overhead blow; a spear trogg has its one thrust (fire, with or without down). |
| SWAMPTHING | The mudmen's fight (as key 8): player 1 is the mudman, once it has come up out of the mud. A direction steps that way; fire = its blow, and a knight it hits it holds for a moment (shorter than the computer's) and pulls under unless the knight breaks free (fire and down, on that knight's own keys); the secondary button (or fire and down) = it sinks into the mud and comes up beside the nearest knight (within 100, level with it), pulling it under; with no knight that near it just stands up again. Coming up out of the mud the first time it just stands up; only its own sinking grabs from below. When it has pulled a knight under it leaves, and player 1 is the next mudman. |
| TOOEASY | Harder fights, on until TOOHARD or JUSTRIGHT: a monster hit again within a third of a second does not flinch (no keeping it reeling with quick blows: it strikes back); in co-op the monsters go for a weaker knight before a stronger one; the dragon attacks without its pauses. Against the cheese: trolls, troggs, mudmen, the Guardian and the computer knights no longer walk up or down into a knight's blade (the trick of stepping off their level and striking as they come level): off its knight's level a monster keeps out of reach and comes in only once level, so it has to be fought face to face. A blow on the dragon during its long fire (or while it waits or moves) no longer makes it flinch: it answers at once with its near fire, so running in under its head gives one blow, not three or four; blows during its near fire or claw and bite still hurt it but do not stop them. Every fight, the game's and the practices. The anti-cheese part alone, without the rest of TOOEASY: `anticheese = true` in `custom_rules.ini`. Fights with Black Knights (the B key's practice, and once BLACKDEATH was typed, every fight with a computer knight) always use all of TOOEASY; after them the rules are again as before. |
| TOOHARD | Easier fights, on until TOOEASY or JUSTRIGHT: the players' knights lose half the hit points of an ordinary hit (rounded up; the instant kills of special attacks still kill), and in co-op the monsters go for a healthier knight before a weaker one. Fights with Black Knights use TOOEASY's rules anyway |
| JUSTRIGHT | The game's own fights again (TOOEASY and TOOHARD off) |

HOTSTUFF, DIRTYRAT, CLUBMEMBER, JUMPSCARE, TROGLIFE and SWAMPTHING start their practice fight at once. Player 1 (the arrows, Enter and
right Shift) is the fight's one monster once it has walked in (no other monster comes: when it falls, the knights have won); the number
of players chosen is the number of knights, each with an input of its own:

| Players chosen | Knights (their inputs) |
|---|---|
| 1 | knight 2 (W A S D, Tab, left Shift) |
| 2 | knights 2 and 3 (W A S D; joystick A) |
| 3 | knights 2-4 (W A S D; joystick A; joystick B) |
| 4 | knights 1-4 (knight 1 on the third key set: I J K L to move, B to attack, N the secondary button) |

So with 4 players five people play. Controllers past the second can be bound to the third key set (or to W A S D)
with a key mapper such as AntiMicroX or JoyToKey; DOSBox-X itself takes two controllers.

The *secondary button* is right Shift for player 1, left Shift for player 2, N on the third key set, or a
controller's second button (circle on a PlayStation pad, B on an Xbox pad); the first button is fire.
