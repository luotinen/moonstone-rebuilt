"""Game rules from an INI file (Moonstone Rebuilt, D10; user request): starting values per knight, a death mode per
knight, the computer knights' extras and global rules.
Usage: python -I tools/rules.py [game folder]   applies custom_rules.ini (Custom_rules_on.bat).
Custom_rules_off.bat puts the fixed MAIN.EXE back and removes CUSTOM_RULES.FLG; Custom_rules_reset.bat copies
custom_rules-default.ini (the normal game's values) to custom_rules.ini.

How it works. Values that the game keeps as a constant in its code (prices of the rules, caps, tables) are byte patches
on top of the fixed MAIN.EXE (_fixes/fixed/MAIN.EXE). Things that need new code use int 63h, which SAVEHOOK.COM handles
(make_savehook.py, rules_handler); it finds the job by the return address and reads its settings from a table that
this tool writes into SAVEHOOK.COM. The int 63h sites are in HOOKS below. Without CUSTOM_RULES.FLG the game is the
normal fixed one: SAVEHOOK.COM always carries the rules code, but the normal MAIN.EXE never calls it.

The knights. Record +20h is the knight: 0-3 for a human player's knight (the order on the selection screen; it also
gives the start corner and home village, which home_village can change), 4 for a computer knight. The INI sections [Knight1_blue]-[Knight4_red] are 0-3 and
[Black] is every computer-controlled knight (they wear black)."""
import sys, os, struct, configparser, shutil, time, uuid, hashlib, contextlib, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from patches import PATCHES, image_offset

SECTIONS = ['Knight1_blue', 'Knight2_orange', 'Knight3_green', 'Knight4_red', 'Black']
WEAPONS = {'long_sword': 0x16, 'broadsword': 0x17, 'claymore': 0x18, 'sword_of_sharpness': 0x19}
ARMOUR_MOVE_DEFAULT = (0, -1, -2, -4)                  # D37: each armour's movement with horses on (a knight's movement: endurance * 2 + 4 + this)
ARMOUR_BONUS_DEFAULT = (0, 2, 0, 2)                    # D38: the same with horses off
# D38: horses: (name for the ini, shop text, price, movement, speed in forest and swamp, in mountains and at the edges, in eighths)
HORSES = (('brown', 'Brown horse', 20, 1, 4, 2), ('light', 'Light horse', 40, 2, 6, 4), ('armoured', 'Armoured horse', 60, 3, 7, 6),
          ('black', 'Black charger', 80, 3, 8, 8), ('dappled', 'Dappled horse', 80, 5, 7, 6))
HORSE_TEXT_SIZE, HORSE_CHANCE_DEFAULT = 30, 10
ARMOURS = {'padded': 0x1b, 'chain_mail': 0x1c, 'plate_mail': 0x1d, 'battle_armour': 0x1e}
MODES = {'permadeath': 0, 'reincarnation': 1, 'respawn': 2, 'invulnerable': 3}
VILLAGE = {'below_3': 0, 'below_max': 1, 'full': 2}
ITEMS = [('healing_potions', 0x00), ('gems_of_seeing', 0x02), ('rings_of_protection', 0x06),   # item table offsets
         ('talismans_of_the_wyrm', 0x08), ('scrolls_of_haste', 0x0a), ('scrolls_of_the_hawk', 0x0c),
         ('scrolls_of_acquisition', 0x0e), ('scrolls_of_the_wyrm', 0x10), ('scrolls_of_protection', 0x12)]
SHARPNESS_ITEM, KEYS, MOONSTONES = 0x04, 0x14, 0x16
# one setting per Moonstone, its bit in the item table's mask. There are four (the Guardian gives one of the four
# bits, 1000:1037), but the moon phase has one value for both half moons (2Eh, cycle DS:05A9), so Stonehenge (1053)
# and the damage bonus (2DAB) treat bits 4 and 8 alike, and they share the icon and (since K19) the name. Which of
# the two is the waxing one is not in the code; the names follow moonstonetavern.co.uk
MOONSTONE_BITS = [('moonstone_new_moon', 1), ('moonstone_full_moon', 2), ('moonstone_half_moon_waxing', 4),
                  ('moonstone_half_moon_waning', 8)]
# Home villages: the places 15h-18h (table DS:0498: id, x, y) belong to the knights +20h = 0-3 and are near their
# start corners. A knight starts (and respawns or reincarnates) at the start corner of its home village.
HOME_VILLAGES = {'north_west': 0, 'north_east': 1, 'south_west': 2, 'south_east': 3}
SPAWNS = [(10, 10), (300, 5), (26, 180), (300, 185)]     # start corners (x, y in pixels) set at 1000:0157
KNIGHT_NAMES = ['Sir Godber', 'Sir Richard', 'Sir Jeffrey', 'Sir Edward']   # +20h = 0-3 (checked in play)
# Saves. DOSBox-X takes the save states; SAVEHOOK.COM only triggers the automatic ones (see make_savehook.py), so
# manual saves cannot be stopped from inside DOS. Instead, in the modes that forbid them, SAVEHOOK keeps a token in
# memory and in a file (SAVEHOOK.CHK, which save states do not restore) and compares the two at every turn, fight and
# reward roll: a state loaded from a manual save has an older token, and the game stops there.
SAVE_MODES = {'autosave_and_manual': 0, 'autosave_only': 1, 'manual_only': 2, 'none': 3}
SAVE_CHECKED = (SAVE_MODES['autosave_only'], SAVE_MODES['none'])
# The dragon's hoard (K18): grows = cleared at a new game, +1 magic item and 0-9 gold for every knight the dragon
# beats (the fixed game); reset = cleared, no growth; keep = never cleared (the original, a speedrun habit)
HOARD_MODES = {'grows': 0, 'reset': 1, 'keep': 2}
# Practice keys (D14-D15): for the keys 1-9 and 0, the lair (1-24, the order of DS:0A6A) whose monsters and count
# the practice fight uses, or the Black Knight
PRACTICE_KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
PRACTICE_DEFAULTS = [1, 4, 10, 2, 22, 20, 8, 13, 18, 'black_knight']
TARGETS = {'nearest': 0, 'first': 1}
# practice flags (G_PRACTICE_FLAGS)
TEAM_KNIGHT_HITS, COOP_KNIGHT_HITS, COOP_DAGGER_HITS, TARGET_FIRST = 1, 2, 4, 8

# Colours. A knight is identified only by record +20h (0-3 human, 4 computer: home village, start corner, turn
# order); its colour is only drawing, chosen from +20h in four places: the fight palette (1000:481A, 3 Amiga RGB
# words), the item screen (1000:B68B, 4 words; no computer case), the status panel (1000:C185, 2 words) and the map
# icon (sprite number = +20h + an offset; 1000:08D4, A3CD, A417). The selection screen's portraits are pictures and
# keep their colours. COLOURS lists each colour's original words; the INI picks one per knight.
COLOURS = {'blue':   ((0x00a, 0x007, 0x004), (0x05d, 0x028, 0x016, 0x003), (0x03f, 0x028), 0),
           'orange': ((0xf80, 0xc50, 0xa30), (0xfa0, 0xb40, 0x930, 0x710), (0xfb0, 0xb60), 1),
           'green':  ((0x8c6, 0x593, 0x251), (0x0c5, 0x082, 0x061, 0x040), (0x4c3, 0x160), 2),
           'red':    ((0xf22, 0xb22, 0x700), (0xe00, 0x900, 0x600, 0x300), (0xf00, 0x800), 3),
           'black':  ((0x206, 0x103, 0x001), (0x206, 0x104, 0x103, 0x001), (0x027, 0x003), 4)}
DEFAULT_COLOURS = ['blue', 'orange', 'green', 'red', 'black']        # [Knight1_blue]..[Knight4_red], [Black]
# A custom colour '#RGB' (one hex digit per channel, as the game's words) is the brightest shade; the darker ones are
# scaled from it. The map icon is a picture per colour, so it takes the named colour nearest to the fight shade.
SHADES = ((1, 0.75, 0.5), (1, 0.7, 0.45, 0.2), (1, 0.55))     # fight, item screen, status panel

def colour_words(colour):
    """(fight words, item screen words, status panel words, map icon) for a colour name or an '#RGB' string."""
    if colour in COLOURS:
        return COLOURS[colour]
    rgb = [int(d, 16) for d in colour[1:]]
    shade = lambda f: sum(int(c * f + 0.5) << s for c, s in zip(rgb, (8, 4, 0)))
    def dist(name):
        w = COLOURS[name][0][0]
        return sum((c - (w >> s & 15)) ** 2 for c, s in zip(rgb, (8, 4, 0)))
    return (*(tuple(shade(f) for f in fs) for fs in SHADES), COLOURS[min(COLOURS, key=dist)][3])

def _colour(raw):
    raw = raw.lower()
    if raw in COLOURS:
        return raw
    if len(raw) == 4 and raw[0] == '#' and all(c in '0123456789abcdef' for c in raw[1:]):
        return raw
    raise ValueError(raw)
_colour.allowed = [*COLOURS, 'a colour #RGB (three hex digits 0-F, e.g. #80F)']
# Addresses of the colour words for knight +20h = 0-4: (fight, item screen, status panel). The item screen has no
# computer case, and the computer case of the other two is also the fall-through for any other value.
COLOUR_SITES = [((0x4822, 0x4827, 0x482c), (0xb699, 0xb69e, 0xb6a3, 0xb6a8), (0xc197, 0xc19c)),
                ((0x4838, 0x483d, 0x4842), (0xb6b4, 0xb6b9, 0xb6be, 0xb6c3), (0xc1ab, 0xc1b0)),
                ((0x4864, 0x4869, 0x486e), (0xb6ea, 0xb6ef, 0xb6f4, 0xb6f9), (0xc1d3, 0xc1d8)),
                ((0x484e, 0x4853, 0x4858), (0xb6cf, 0xb6d4, 0xb6d9, 0xb6de), (0xc1bf, 0xc1c4)),
                ((0x4878, 0x487d, 0x4882), (), (0xc1e1, 0xc1e6))]
# D61: the low-HP glow's target words for +20h = 0-4 (KnightGlowColours 1000:09A5; the game's glow steps each fight
# word to its target and back). The named colours keep the game's targets (red dims); black, the computer's slot 4,
# near-blacks (nearest named colour black), greys / white (R = G = B) and purples (B >= R > G) do not pulse: targets =
# words.
GLOW_SITES = [(0x09b0, 0x09b5, 0x09ba), (0x09c6, 0x09cb, 0x09d0), (0x09f2, 0x09f7, 0x09fc), (0x09dc, 0x09e1, 0x09e6),
              (0x0a02, 0x0a07, 0x0a0c)]
GLOW_WORDS = {'blue': (0x00c, 0x009, 0x006), 'orange': (0xfa0, 0xe70, 0xc50), 'green': (0xae8, 0x6b5, 0x473),
              'red': (0xd00, 0x900, 0x500)}
GLOW_SPEED_SITE = 0x0973                                # knight 2's first entry (mov cx,1): 2 as knight 1's (0915)

def glow_words(colour, slot):
    """The three low-HP glow target words of a knight's colour in colour slot +20h = slot."""
    fight, *_, icon = colour_words(colour)
    if slot == 4 or colour == 'black':
        return fight
    if colour in GLOW_WORDS:
        return GLOW_WORDS[colour]
    rgb = [int(d, 16) for d in colour[1:]]
    r, g, b = rgb
    if icon == COLOURS['black'][3] or r == g == b or b >= r > g:       # near-black, grey / white, purple
        return fight
    return tuple(sum(min((w >> s & 15) + 2, 15) << s for s in (8, 4, 0)) for w in fight)   # lighter, 15 at most

# Prices. Shop prices are 8-bit signed operands (cmp/sub word [si+32h],nn), so at most 127: (name, human shop
# compare, human shop subtract, computer knight's compare, computer knight's price word).
SHOP = [('broadsword', 0xcf95, 0xcfa1, 0xaf1b, 0xaf28), ('claymore', 0xcfb7, 0xcfc3, 0xaefc, 0xaf09),
        ('chain_mail', 0xcf2c, 0xcf32, 0xaedd, 0xaeea), ('plate_mail', 0xcf4f, 0xcf55, 0xaebe, 0xaecb),
        ('battle_armour', 0xcf72, 0xcf78, 0xae9f, 0xaeac), ('dagger', 0xcfd3, 0xcfdf, 0xafe6, 0xaff2)]
# High Temple: buy price words set at 1000:D457 (DS:EDAE, by item table offset); selling pays half.
TEMPLE = [('healing_potion', 0x00), ('gem_of_seeing', 0x02), ('sword_of_sharpness', 0x04),
          ('ring_of_protection', 0x06), ('talisman_of_the_wyrm', 0x08), ('scroll_of_haste', 0x0a),
          ('scroll_of_the_hawk', 0x0c), ('scroll_of_acquisition', 0x0e), ('scroll_of_the_wyrm', 0x10),
          ('scroll_of_protection', 0x12), ('key', 0x14), ('moonstone', 0x16)]
TEMPLE_SITES = {0x00: 0xd459, 0x02: 0xd45e, 0x04: 0xd463, 0x06: 0xd468, 0x08: 0xd46d, 0x0a: 0xd472, 0x0c: 0xd477,
                0x0e: 0xd47c, 0x10: 0xd481, 0x12: 0xd486, 0x14: 0xd48b, 0x16: 0xd490}
# The price texts (DS offsets), stored end to end with no spare bytes: (price name, buy or sell).
PRICE_TEXTS = [(0xe9b4, 'broadsword', 'buy'), (0xe9ce, 'claymore', 'buy'), (0xe9eb, 'chain_mail', 'buy'),
               (0xea03, 'plate_mail', 'buy'), (0xea1e, 'battle_armour', 'buy'), (0xea3a, 'dagger', 'buy'),
               (0xea50, 'sword_of_sharpness', 'buy'), (0xea72, 'key', 'buy'), (0xea84, 'healing_potion', 'buy'),
               (0xeaa4, 'gem_of_seeing', 'buy'), (0xeac0, 'ring_of_protection', 'buy'),
               (0xeae1, 'talisman_of_the_wyrm', 'buy'), (0xeaf8, 'scroll_of_haste', 'buy'),
               (0xeb16, 'scroll_of_acquisition', 'buy'), (0xeb39, 'scroll_of_the_hawk', 'buy'),
               (0xeb5a, 'scroll_of_the_wyrm', 'buy'), (0xeb7b, 'scroll_of_protection', 'buy'),
               (0xeb9e, 'moonstone', 'buy'), (0xebb6, 'sword_of_sharpness', 'sell'), (0xebd8, 'key', 'sell'),
               (0xebea, 'healing_potion', 'sell'), (0xec0b, 'gem_of_seeing', 'sell'),
               (0xec28, 'ring_of_protection', 'sell'), (0xec3c, 'talisman_of_the_wyrm', 'sell'),
               (0xec54, 'scroll_of_haste', 'sell'), (0xec73, 'scroll_of_acquisition', 'sell'),
               (0xec97, 'scroll_of_the_hawk', 'sell'), (0xecb9, 'scroll_of_the_wyrm', 'sell'),
               (0xecdb, 'scroll_of_protection', 'sell'), (0xecff, 'moonstone', 'sell')]
# Base damage of each move (1000:17F0, words into DS:69D4); the overhead chop is doubled by the game.
MOVES = [('lunge', 0x1800), ('swing', 0x17f6), ('dagger_throw', 0x180a), ('backward_thrust', 0x17fb),
         ('upward_thrust', 0x180f), ('overhead_chop', 0x1805)]

# Treasure. A lair's contents are rolled at the start (1000:1EF7) against the limits DS:6952 (gold / two magic items /
# gold and two items; the fourth type is the same as the third). The gold (1000:B9F2) is 10 + 0-21 from 5 random bits
# with 22-31 folded onto 12-21; Math and the dragon's hoard use the same routine. A magic item (1000:BA5F) is rolled
# against the limits of DS:E365 (word pairs limit, item, in this order); the lairs, Math, the dragon's hoard and the
# High Temple's stock (1000:1DE3) use it. It rolls again for the same item twice in a row and for a second Sword of
# Sharpness, so at least two other items need a chance or it could roll forever.
TREASURE_ITEMS = ['healing_potion', 'gem_of_seeing', 'sword_of_sharpness', 'ring_of_protection', 'talisman_of_the_wyrm',
                  'scroll_of_haste', 'scroll_of_acquisition', 'scroll_of_the_hawk', 'scroll_of_the_wyrm',
                  'scroll_of_protection']
LAIR_TYPES = ['gold', 'magic_items', 'gold_and_magic_items']
GOLD_MIN, GOLD_MAX = 10, 31
# Math the Wizard (1000:B8D6): roll + irritation <= 30 magic item, <= 70 ability, <= 90 gold, else frog (cmp ax,imm16).
MATH = [('magic_item', 0xb8f7), ('ability', 0xb8fc), ('gold', 0xb901), ('frog', None)]
# Mythral the Mystic (1000:BC18): DS:E478 holds six (largest donation, modifier) word pairs; success when
# roll + modifier <= 50. The sixth limit (250) also ends the table: a larger donation reads past it and always fails.
MYTHRAL_BANDS = 6
# Monsters: (name, HP words, damage sites (address, size)). The HP words are the mov [di+38h] and [di+3Ch] of each
# monster's set-up (1000:2100-27B5). Damage is what a hit does to a knight: a sub [di+38h],imm8 in the handler for
# the attacker's type (table DS:7843, 1000:417E), or the words of a monster's own damage table set at 1000:1938-1B6E.
MONSTERS = [('war_beast', (0x2312, 0x2317), ((0x443f, 1),)),
            ('axe_trogg', (0x2140, 0x2145), tuple((a, 2) for a in (0x1940, 0x1945, 0x194a, 0x194f, 0x1954, 0x1959))),
            ('wasteland_trogg', (0x21cc, 0x21d1), tuple((a, 2) for a in (0x19f5, 0x19fa, 0x19ff, 0x1a04, 0x1a09, 0x1a0e))),
            ('spear_trogg', (0x225f, 0x2264), ((0x433d, 1),)),
            ('mudman', (0x2692, 0x2697), ((0x1b69, 2),)),     # DS:6AE2, through the knights' formula (1000:2D73)
            ('balok', (0x25fc, 0x2601), ((0x4294, 1),)),
            ('troll', (0x272a, 0x272f), ((0x4399, 1),))]
# Ratmen by moon phase (1000:23C4; with fix K2 strong at three-quarter moon, strongest at full moon): HP words,
# bite word (DS:6A8A, infects), claw word (DS:6A8C).
RATMEN = [('normal', (0x23e3, 0x23e8), 0x240a, 0x2405), ('three_quarter_moon', (0x2416, 0x241b), 0x2425, 0x2420),
          ('full_moon', (0x2431, 0x2436), 0x2440, 0x243b)]

# Settings table in SAVEHOOK.COM: one SECTION_SIZE block per INI section in SECTIONS order, then the globals.
# Block: +0 STR, +1 CON, +2 END, +3 lives, +4 gold (word), +6 daggers (= knight record +2Eh..+34h, copied as is),
# +7 death mode, +8 XP, +0Ah weapon, +0Ch armour, +0Eh HP bonus (words), +10h the 24-byte item table.
SECTION_SIZE = 0x28
G_ARMOUR_HP = len(SECTIONS) * SECTION_SIZE    # 4 words: max HP bonus of padded, chain, plate, battle
G_SWORD = G_ARMOUR_HP + 8                     # word: damage bonus of the long sword (the others are in MAIN.EXE)
G_REST, G_VILLAGE, G_MAX_LIVES = G_SWORD + 2, G_SWORD + 3, G_SWORD + 4    # bytes
G_RING = G_SWORD + 6                          # word: max HP per Ring of Protection
G_COLOURS = G_RING + 2                        # 5 bytes: map icon colour (0-4) for knight +20h = 0-4
G_HOMES = G_COLOURS + 5                       # 5 bytes: home village (0-3) for knight +20h = 0-4 (4: none, FFh)
G_VILLAGE_ANY = G_HOMES + 5                   # byte: 1 = the druids heal in every village
G_SAVE_MODE = G_VILLAGE_ANY + 1               # byte: SAVE_MODES
G_FATE = G_SAVE_MODE + 1                      # byte: 1 = prevent savescumming (fixed outcomes)
G_SELLING = G_FATE + 1                        # byte: 1 = the merchant buys back daggers, weapons and armour
G_MAX_GOLD = G_SELLING + 1                    # word: max_gold (the sale's gold is capped like the game's)
G_SELL = G_MAX_GOLD + 2                       # 6 words: what the merchant pays (SELL_ITEMS order)
G_HOARD = G_SELL + 12                         # byte: HOARD_MODES
G_PRACTICE = G_HOARD + 1                      # 10 bytes: the lair of each practice key (0-23), FFh = Black Knight
G_PRACTICE_FLAGS = G_PRACTICE + 10            # byte: the flags above
G_TARGET_MARGIN = G_PRACTICE_FLAGS + 1        # byte: a monster keeps its knight unless another is this much nearer
G_HIT_REST = G_TARGET_MARGIN + 1              # 2 bytes (K6): BIOS ticks after a hit on the dragon / the Guardian in
                                              # which further hits do not count (0 = as the game: every hit counts)
G_EXPLOIT_FIXES = G_HIT_REST + 2              # byte: fixes of exploits runs use, off in speedrun mode (bits below)
KEEP_DRAGON_TARGET = 1                        # K21: the dragon keeps its target when the map is drawn again
NO_EXTRA_TURN = 2                             # K22: after an action that used up the turn, no input before its end
POTION_LIFE = 4                               # K23: a potion gives no life to a knight without lives
EXPLOIT_FIXES = KEEP_DRAGON_TARGET | NO_EXTRA_TURN | POTION_LIFE
G_CYCLES = G_EXPLOIT_FIXES + 1                # 2 words: DOSBox-X cycles, more per knight in a fight (D17)
G_DEATHS = G_CYCLES + 4                       # byte: death_animations (D20), DEATHS
DEATHS = {'extended': 0, 'vanilla': 1, 'off': 2}   # all deaths / only the game's beheading / no blood (as gore off)
G_DRAGON_DEBUG = G_DEATHS + 1                 # byte: dragon_debug_mode (D21), 0 or 1
G_INPUT_BUFFER = G_DRAGON_DEBUG + 1           # byte: input_buffer (D24), 1 = on
G_REST_FIXED = G_INPUT_BUFFER + 1             # byte: rest_heal_fixed_percentage (0-100)
G_REST_ENDURANCE = G_REST_FIXED + 1           # byte: rest_heal_endurance_percentage (0-100)
G_CHEATS = G_REST_ENDURANCE + 1               # byte: cheat_codes, 1 = yes
G_ANTICHEESE = G_CHEATS + 1                   # byte: anticheese, 1 = true (as TOOEASY's anti-cheese rules)
G_CATCHUP = G_ANTICHEESE + 1                  # byte: catchup, 1 = yes (more loot for a knight behind, potions when low)
G_AGE = G_CATCHUP + 1                         # byte: [Parental] age_rating: 12 gore off, 16 no fatalities, 18 all
G_FIGHT_CYCLES = G_AGE + 1                    # 4 words: DOSBox-X cycles of a fight with 1-4 knights (D17)
G_HASTE_CURSE = G_FIGHT_CYCLES + 8            # signed byte: roll <= this: a Scroll of Haste is cursed (-1 never)
G_WYRM_CURSE = G_HASTE_CURSE + 1              # signed byte: the same for a Scroll of the Wyrm
G_INPUT_CHORD = G_WYRM_CURSE + 1              # byte: input_chord (D24): BIOS ticks a turn waits for its attack, 0 = off
G_INPUT_LOG = G_INPUT_CHORD + 1               # byte: input_log (D24), 1 = INPUT.LOG after every fight
G_COOP_LAIRS = G_INPUT_LOG + 1                # byte: coop_lairs (D33), COOP_MODES
G_COOP_EXTRA = G_COOP_LAIRS + 1               # byte: extra_loot_per_knight (D33), percent
G_ENCHANT = G_COOP_EXTRA + 1                  # byte: sword_enchantments (D35), 1 = on
G_ENCH_CHANCE = G_ENCHANT + 1                 # byte: sword_enchantment_chance (D35), percent
ENCH_CHANCE_DEFAULT = 10
G_ARMOUR_MOVE = G_ENCH_CHANCE + 1             # 4 signed bytes: movement of padded, chain, plate, battle (D37)
G_ARM_ENCH = G_ARMOUR_MOVE + 4                # byte: armour_enchantments (D37), 1 = on
G_ARM_CHANCE = G_ARM_ENCH + 1                 # byte: armour_enchantment_chance (D37), percent
G_DISEASE = G_ARM_CHANCE + 1                  # byte: 1 = the ratmen's disease is on (Venomproof has a use)
G_HORSES = G_DISEASE + 1                      # byte: horses (D38), 1 = on
G_HORSE_CHANCE = G_HORSES + 1                 # byte: rare_horse_chance, percent
G_HORSE_PRICE = G_HORSE_CHANCE + 1            # 5 words: each horse's price
G_HORSE_MOVE = G_HORSE_PRICE + 10             # 5 signed bytes: movement
G_HORSE_SOFT = G_HORSE_MOVE + 5               # 5 bytes: forest and swamp speed, eighths
G_HORSE_HARD = G_HORSE_SOFT + 5               # 5 bytes: mountains and edges speed, eighths
G_HORSE_TEXT = G_HORSE_HARD + 5               # 5 texts of HORSE_TEXT_SIZE bytes (the shop's hover)
G_INPUT_RECENT = G_HORSE_TEXT + 5 * HORSE_TEXT_SIZE   # byte: input_recent_direction (D39), BIOS ticks, 0 = off
G_TRADE_IN = G_INPUT_RECENT + 1               # byte: 1 = worse goods at the merchant are free in exchange (D40)
G_HORSE_SELL = G_TRADE_IN + 1                 # 5 texts of HORSE_TEXT_SIZE bytes (the knight's own horse, hover)
G_BUY = G_HORSE_SELL + 5 * HORSE_TEXT_SIZE    # 6 words: the merchant's full prices (SELL_ITEMS order), D42
G_COMPUTER = G_BUY + 12                       # byte: computer_knights (D44), 0 = none in the game
G_BK_AI = G_COMPUTER + 1                      # byte: black_knight_ai (D45), 1 = smart, 0 = classic
G_BK_HEAL = G_BK_AI + 1                       # byte: a full heal's price at the healer (D45: smart knights pay it)
G_TD = G_BK_HEAL + 1                          # byte: timed_defence (D46), 1 = on
G_TD_WINDOW = G_TD + 1                        # byte: defence_window, BIOS ticks
G_TD_FAST = G_TD_WINDOW + 1                   # byte: fast_swing_time, ticks
G_TD_STAGGER = G_TD_FAST + 1                  # byte: stagger_time, ticks
G_TD_PURPLE = G_TD_STAGGER + 1                # 2 bytes: a Purple Knight's percent: correct, mistimed
G_TD_BLACK = G_TD_PURPLE + 2                  # 2 bytes: a Black Knight's percent: correct, mistimed
G_TD_PAUSE = G_TD_BLACK + 2                   # byte: computer_defence_pause, attacks
TD_DEFAULTS = {'defence_window': 18, 'fast_swing_time': 30, 'stagger_time': 16, 'purple_knight_defence': 15,
               'purple_knight_mistimed': 10, 'black_knight_defence': 25, 'black_knight_mistimed': 15, 'computer_defence_pause': 2}
G_CHOP_CHEESE = G_TD_PAUSE + 1                # byte: from anticheese (D46): 2 = chop rule for all, 1 = knights only, 0 = none
ANTICHEESE = {'yes': 2, 'true': 2, 'blackknights_only': 1, 'no': 0, 'false': 0}   # 2: all the rules; 1: knights keep out from under a chop; 0: none
TABLE_SIZE = G_CHOP_CHEESE + 1
COOP_MODES = {'off': 0, 'full': 1, 'shared': 2}
COOP_DEFAULT, COOP_EXTRA_DEFAULT = 1, 50
INPUT_CHORD_DEFAULT = 2
INPUT_RECENT_DEFAULT = 3
# age_rating: (rating, permanent lock). PARENTAL.LCK holds the highest rating allowed in this installation: the setup
# writes 18 once (a new installation, or the first setup of 0.7.0 over an older one: _fixes/PARENTAL.INIT), a
# permanent rating lowers it for good, and a missing file counts as 12 (deleting it locks the game to K12)
AGE_RATINGS = {'k12_permanent': (12, 12), 'k12': (12, 0), 'k16_permanent': (16, 16), 'k16': (16, 0), 'k18': (18, 0)}
AGE_LOCK, AGE_INIT = 'PARENTAL.LCK', os.path.join('_fixes', 'PARENTAL.INIT')
INSTALLING = 'INSTALLING.FLG'                          # swap_files: a change of the programs is under way or did not finish
UPDATE_LOCK = os.path.join('_fixes', 'UPDATE.LCK')    # install_lock: held (not merely present) while a change runs
BUILD_STAMP = 'BUILD.TXT'                             # write_stamp: what this installation is running, for playtest reports
SETUP_FLAG = 'SETUP.FLG'                               # Setup is under way or did not finish; only a finished Setup removes it
# on_E_rest_heal (G_REST): none = the game's daily healing (a quarter of the missing HP); full = also the E key
# restores full HP; fixed_and_endurance and fixed_only = the daily healing is fixed % of the missing HP (at least
# 1), plus endurance % times the share of the movement (endurance) the knight had left when its last turn ended
# (E pressed, a fight, a place)
REST_HEAL = {'none': 0, 'full': 1, 'fixed_and_endurance': 2, 'fixed_only': 3}
CYCLES_DEFAULT = (4000, 650)                  # the conf's cycles (map, menus), more for each knight past the first
CURSE_DEFAULT = 12.5                          # % for the Haste and Wyrm curses (as the Hawk's)
FIGHT_CYCLES_DEFAULT = (2600, 3250, 3500, 3750)   # fights with 1-4 knights (play tests: 2 knights 3250, 4 at 4550 too fast)
HIT_REST_DEFAULT = 8                          # K6: tenths of a second (0.8 s), until play tests set it
# Selling at the merchant (item screen mode 5): half the shop price, rounded down. The long sword and padded armour
# are what a knight gets back and are not bought; the Sword of Sharpness is a magic item and not sold here.
SELL_ITEMS = ['dagger', 'broadsword', 'claymore', 'chain_mail', 'plate_mail', 'battle_armour']

# int 63h sites: (address, original bytes, kind). The kind names the handler in make_savehook.py.
# The lives kinds keep the instruction's 8-bit operand after the int (cd 63 nn 90): the handler reads it
# and skips it. Code addresses (1000:xxxx) are also offsets in the MAIN.EXE image.
HOOKS = [
    (0x1fea, '8b7544b81800c60400464875f9', 'init'),     # knight set-up (1000:1FAE): clear the item table
    (0x02d3, '83c30a', 'max_hp'),                       # max HP formula (1000:028D): add bx,10
    (0x2d84, '8a4c2e03c1', 'damage'),                   # damage of a hit (1000:2D73): + strength (long sword bonus)
    (0xa66c, '807c3100', 'turn'),                       # turn change: is the knight dead?
    (0xa58e, 'a1accc', 'rest'),                         # E key: end the turn
    (0xa568, '8b3ee877', 'turn_moves'),                 # every pass of the map loop, before the E key and actions
    (0xa607, 'c706aacc0000', 'turn_end'),               # the end of a turn: the movement left noted
    (0x11bf, '8b5c3c2b5c387407d1ebd1eb83cb01', 'daily_heal'),   # the day's end: each record's healing
    (0xbfec, 'e89710', 'items_loop'),                   # cheat codes: every pass of the item screen's loop
    (0xa6d2, '833ea2cc00', 'turn_haste'),               # cheat codes: the turn's budget, KNIGHTRIDER's haste
    (0x3c24, 'e8be1a', 'dragon_move'),                  # HOTSTUFF: the dragon's moves (call 56E5)
    (0x3c27, '8b36e877', 'dragon_input'),               #   ... and player 1's input as its moves
    (0x3886, 'e85904', 'dragon_range'),                 #   no flights of its own (call 3CE2)
    (0x39e6, '83268677bf', 'dragon_attack'),            #   its attacks by the keys
    (0x3150, 'e8ac0b', 'rat_decide'),                   # DIRTYRAT: player 1's ratman decides by the keys
    (0x32c4, '8b36e877', 'rat_tree'),                   #   ... and in the tree
    (0x32f9, 'e8c450', 'rat_escape'),                   # co-op: a knight a ratman hangs breaks free by its own keys
    (0x335f, 'e85e50', 'rat_escape'),                   #   ... or one it rides
    (0x3576, 'c7063a780038', 'rat_ride'),               #   ... the knight it jumps on
    (0x3597, 'c7063a78d43b', 'rat_hang'),               #   ... the knight it hangs
    (0x5605, 'e8dd00', 'troll_decide'),                 # CLUBMEMBER: player 1's troll decides by the keys
    (0x35ec, '837d3800', 'balok_decide'),               # JUMPSCARE: player 1's Balok decides by the keys
    (0x2e19, 'e8c928', 'trogg_decide'),                 # TROGLIFE: player 1's trogg decides by the keys
    (0x4e97, '8b36e877', 'mon_walk'),                   # LUNAR: the monsters' walk (trolls, troggs) at half speed
    (0x3ab4, '8b4428', 'dragon_hit'),                   # D46 anticheese: a knight's blow on the dragon: a run of them may end in its bite
    (0x389c, '830e867710', 'dragon_long'), (0x39a6, '8bc7', 'dragon_depth'),   # D46 anticheese: the long fire's depth reach
    (0x05b6, 'c745080100', 'lair_loot'),                # catchup: a lair won the first time, before its chest
    (0x5363, 'e87f03', 'mud_decide'),                   # SWAMPTHING: player 1's mudman decides by the keys
    (0x54c7, 'e8cde7', 'mud_rise'),                     # SWAMPTHING: player 1's mudman grabs from below only after its dive
    (0x550a, 'e8b32e', 'mud_escape'),                   # co-op: a knight a mudman holds breaks free by its own keys
    (0xbcac, 'b90000', 'healer'),                       # the healer: partial donations are chances, the change is returned
    (0xcccf, 'c706a2ccffff', 'haste_curse'),            # Scroll of Haste: may be cursed
    (0xc03c, 'c7067af30000', 'wyrm_curse'),             # Scroll of the Wyrm: may be cursed
    (0x0d15, 'e82c17', 'dragon_scroll'),                # Scroll of Protection against the dragon
    (0xab7d, '83445c20', 'hawk_land'),                  # a cursed Hawk never lands in the Valley
    (0x0fd2, '807c140f', 'valley_keys'),                # SIRPICKSALOT: the Valley with any number of keys
    (0xa45f, 'b81400', 'lair_icon'),                    # IDROPPEDMYKEY: the lairs holding keys glow
    (0x3711, '8b36e877', 'balok_land'),                 #   ... and its hop lands on a knight
    (0xd08c, 'e831b3', 'pointer'),                      # D36: the item screen's pointer moves by the time held
    (0x43d1, 'c744281000', 'fireblock'),                # D35: the dragon's fire on a knight
    (0x2da4, '83fa107502d1e0', 'ench_hit'),             # D35: a knight's blow's damage (the chop's double, the banes)
    (0xc8e5, '837c0400', 'ench_icon'),                  # D35: a chest's or the hoard's enchantment, as the magic sword's
    (0xc51d, 'a3a4e4', 'ench_name'),                    # D35: the item screen's sword: its enchanted name
    (0xcd9f, '83fb047503', 'ench_take'),                # D35: an enchantment taken from the chest
    (0xa6c4, '8a453e', 'turn_move'),                    # D37: a turn's movement: the armour's value from the ini
    (0x0d59, 'e89d82', 'horse_town_w'), (0x0e14, 'e8cb81', 'horse_town_h'),   # D40: slot 4 is rolled as a town is entered
    (0xc3be, 'e8beb9', 'gold5'), (0xb32b, 'e851ca', 'gold5'), (0xbdcb, 'e8b1bf', 'gold5'), (0x0bbe, '014432', 'gold_add'),   # D41
    (0x0de4, 'e8f9a3', 'visit_tavern'), (0x0e93, 'e84aa3', 'visit_tavern'), (0x0df6, 'e8b3b1', 'visit_merchant'), (0x0ea5, 'e804b1', 'visit_merchant'), (0x0eb4, 'e8f5b0', 'visit_merchant'),   # D43: max_gold as these are left
    (0xb4c7, '014432', 'gold_add'),                     # D43: the dice's wins, up to 32767 until the tavern is left
    (0xb491, '8b4432', 'gold999'), (0xb4e3, '8b4432', 'gold999'),   # D41: the dice result's three-character field
    (0xc55c, '8b3690e4', 'horse_panel'),                # D40: the knight's own horse on its panel
    (0xca76, 'b90d00', 'horse_icons'), (0xcf0c, '8b3688ed', 'horse_buy'),   # D38: horses
    (0xa918, 'be2ac4', 'horse_terrain'),
    (0xc8d7, 'be266e', 'arm_icon'), (0xc54a, 'a3a4e4', 'arm_name'), (0xce5b, '8b6d42', 'arm_tkar'),   # D37: armour enchantments
    (0xa643, 'c744460000', 'arm_danu'), (0xa5f1, 'e83901', 'arm_dragon'), (0x4405, '8a4f08', 'arm_fire'),
    (0x42a7, 'c7063a78483a', 'arm_venom'), (0xcb04, 'bf7989', 'arm_target'),
    (0xadcc, '837c4600', 'arm_ai_wyrm'), (0xadf6, '837c4600', 'arm_ai_acq'), (0xcd2e, 'e832de', 'arm_hawk'),
    (0xcd71, 'c70630090100', 'arm_prot'),
    (0xce91, '8b6d40', 'ench_tkwp'),                    # D35: a sword taken from a knight takes its enchantment
    (0x37fc, '8b3e7809', 'balok_crush'),                #   ... and its crushing grab (the secondary button)
    (0x112e, '807c31037d0480443101', 'village'),        # home village druids
    (0x0add, '806c3101', 'lives_si'), (0x0aed, '806d3101', 'lives_di'),   # fight lost
    (0x0d03, '806c3101', 'lives_si'),                   # computer knight robbed by the dragon
    (0x0fff, '806c3102', 'lives_si'),                   # Guardian: two more
    (0x122f, '806c3101', 'lives_si'),                   # ratmen disease
    (0x40ca, '894528', 'td_move'),                      # D46: a knight's move starts: the block's or dodge's time, the fast swing
    (0x441f, '833efc7700', 'td_check'), (0x4d6c, '833efc7700', 'td_check'),   # D46: a knight struck by a knight (a human's, a computer's)
    (0x42d8, '833efc7700', 'td_monster'), (0x432a, '833efc7700', 'td_monster'),   # D46: a knight blocking a trogg, a spear trogg
    (0x4302, '294538', 'td_trogg'), (0x4da1, '294538', 'td_cdmg'),   # D46: damage
    (0x4b85, '8936e877', 'bk_down'),                    # D46: a computer knight whose extended death is over stays down
    (0x4c93, 'c744280800', 'td_bk_block'),              # D46: BKBlock's own block is replaced by the roll at the hit
    (0x08f8, '833e120400', 'glow_k1'), (0x0955, '833e180400', 'glow_k2'),   # D61: KnightGlowOn: the low-HP glow stops above 10 HP
    (0x15b5, 'f7c31000', 'choose_keys'),                # D53: Select Knight: Esc back to the first menu; D52: the practice scores cleared
    (0x4bcd, '0bc0', 'bk_track'),                       # D45: a Black Knight in a fight, after its MonsterTrack
    (0xa9b6, 'bed2cc', 'bk_lair'),                      # D45: a computer knight picks a lair from the sorted list
    (0xabd7, '837c4600', 'bk_target'),                  # D45: where a computer knight walks (four keys: Stonehenge)
    (0xae78, '8b36e877', 'bk_shop'),                    # D45: what a computer knight wants from town (weak: a heal)
    (0xafa3, '8b36e877', 'bk_town'),                    # D45: a computer knight in town
    (0x00df, 'e9cea3', 'no_computer'),                  # D44: a new campaign's last step (jmp A4B0), the knights are set
    (0xa410, '3bfe742a', 'map_others'),                 # D44: the map draws the other knights: none for removed ones
    (0x08d4, '8b4420', 'colour_si'), (0xa417, '8b4420', 'colour_si'),   # map icons: mov ax,[si+20h]
    (0xa3cd, '8b4520', 'colour_di'),                    # map icon of the knight whose turn it is: mov ax,[di+20h]
    (0x0732, '3d15007506837d200075c63d16007506837d200175bb3d17007506837d200275b03d18007506837d200375a5', 'place'),
    (0xcc0f, '268b5e12268b4e10', 'sell'),               # item screen click: mov bx,es:[bp+12h] / mov cx,es:[bp+10h]
    # D33 co-op lairs: the map's choices (the list's end, a line's text, the choice made)
    (0x08ca, '33c0', 'coop_list'), (0xb137, '837f0402', 'coop_text'), (0xb089, '3e8b4600', 'coop_pick'),
    # ... the lair's set-up (call 1F2C), its end (test word [0942h],1), its chest (call BFAC with ax = 2)
    (0x058b, 'e89e19', 'coop_setup'), (0x0597, 'f70642090100', 'coop_end'), (0x05c6, 'e8e3b9', 'coop_loot'),
    # ... a shared chest: a click on the gold (TKGP, call D6E1) and its loop (dec word [di], a gold piece out)
    (0xced3, 'e80b08', 'gold_click'), (0xcefa, 'ff0d', 'gold_step'),
]                                                       # map places: villages 15h-18h react only to their knight
# Reward rolls (only patched for prevent_savescumming or the checked save modes): call rel16 -> int 63h / nop. The
# handler sets the game's random state (DS:E22F) from a stream of its own, one per kind, that advances only at these
# rolls, then does the call. So after loading a state the same rolls give the same results however the time in between
# was spent. (address, original call, stream): tavern dice (each die), Math, Mythral (his random ability), curses.
FATE_HOOKS = [(0xb413, 'e84c0b', 0), (0xb8ec, 'e89306', 1), (0xbb74, 'e84bfe', 2), (0xcd1b, 'e864f2', 3),
              (0xcd67, 'e818f2', 3)]
FATE_STREAMS = 4

def hook_bytes(where, old, kind):
    """The replacement for a hook site and the return address that the handler sees."""
    old = bytes.fromhex(old)
    if kind == 'init':                                  # mov si,[di+44h] / int 63h / jmp 1FF7
        new = old[:3] + b'\xcd\x63\xeb\x06'
        return new.ljust(len(old), b'\x90'), where + 5
    if kind == 'village':                               # int 63h / jmp 1138
        return b'\xcd\x63\xeb\x06'.ljust(len(old), b'\x90'), where + 2
    if kind == 'place':                                 # int 63h / jne 0703 (skip the place) / jmp 075E (it reacts)
        return b'\xcd\x63\x75\xcd\xeb\x26'.ljust(len(old), b'\x90'), where + 2
    if kind == 'sell':                                  # int 63h / jnz CC16 (go on) / jmp CFE3 (sound, redraw, ret)
        return b'\xcd\x63\x75\x03\xe9\xcd\x03\x90', where + 2
    if kind == 'fate':                                  # int 63h / nop: the handler does the call
        return b'\xcd\x63\x90', where + 2
    if kind.startswith('lives'):
        return b'\xcd\x63' + old[3:4] + b'\x90', where + 2    # handler reads the operand at the return address
    return b'\xcd\x63'.ljust(len(old), b'\x90'), where + 2

# --- reading the INI --------------------------------------------------------------------------------------------------
class RulesError(Exception):
    pass

class SetupUnfinished(RulesError):
    pass

class Busy(OSError):
    """Another Setup, rules change or mode switch holds this installation's lock."""

def _fight_cycles(cp, sec, per, bounds):
    """fight_cycles: 1-4 numbers, the cycles of a fight with 1, 2, 3, 4 knights; past the last one given, each
    knight adds additional_cycles_per_knight (one number: that and more per knight, as before)."""
    raw = cp.get(sec, 'fight_cycles').split(';')[0].strip()
    lo, hi = bounds
    try:
        vals = [int(v) for v in raw.split(',')]
    except ValueError:
        vals = []
    if not 1 <= len(vals) <= 4 or not all(lo <= v <= hi for v in vals):
        raise RulesError(f'[{sec}] fight_cycles = {raw}: must be 1-4 numbers {lo}-{hi}, separated by commas')
    while len(vals) < 4:
        vals.append(vals[-1] + per)
    if not all(lo <= v <= hi for v in vals):
        raise RulesError(f'[{sec}] fight_cycles = {raw}: all four expanded speeds must be {lo}-{hi} '
                         '(including additional_cycles_per_knight)')
    return tuple(vals)

def _bk_ai(raw):
    return {'classic': 0, 'smart': 1}[raw.lower()]
_bk_ai.allowed = ['classic', 'smart']


def _get(cp, sec, key, conv, lo=None, hi=None):
    if not cp.has_option(sec, key):
        raise RulesError(f'[{sec}] {key} is missing')
    raw = cp.get(sec, key).strip()
    try:
        val = conv(raw)
    except (ValueError, KeyError):
        allowed = getattr(conv, 'allowed', None)
        raise RulesError(f'[{sec}] {key} = {raw}: must be ' +
                         (' or '.join(allowed) if allowed else f'a number, {lo}-{hi}'))
    if lo is not None and not lo <= val <= hi:
        raise RulesError(f'[{sec}] {key} = {raw}: must be {lo}-{hi}')
    return val

def _choice(table):
    def conv(raw):
        return table[raw.lower()]
    conv.allowed = list(table)
    return conv

_onoff = _choice({'on': 1, 'off': 0, 'true': 1, 'false': 0})

# Settings of earlier versions: an older ini file may still have them, and they are ignored
REMOVED_SETTINGS = {'dynamic_difficulty'}

# Allowed values (all checked before anything is written). Values above the game's own limits are allowed (user
# decision); the bounds only keep each value inside what its storage and the screens can hold:
# * abilities, life points 1-99: signed bytes (above 127 they would count as negative, i.e. dead or weakened).
#   Life points are drawn as icons 19 pixels apart (1000:C428), so more than about 6 run past the panel's edge on
#   the item screen; that only looks wrong.
# * max HP: SAVEHOOK.COM caps it at MAX_HP during the game: the item screen writes "current/max" into a small text
#   buffer (DS:E4B4, 1000:C46B), and 999/999 is as long as the original's longest.
# * gold at most 20000: a word that the game compares as signed (limit 32767); a dice win adds at most 150 x 30.
# * experience per ability point at least 1: 0 would let the computer knights raise abilities without end.
# * item counts 0-9: how bigger counts show on the item screen has not been checked.
# * byte operands in MAIN.EXE are signed (at most 127): armour HP, moon days, the computer knights' XP, the shop
#   and healer prices, the most daggers, Math's irritation drop.
# * Math's irritation 0-150: it is added to a 0-100 roll in a byte (1000:B8F3), so the sum must stay below 256.
# * temple prices 0-999: the price texts are rewritten in the space of the original ones.
# * chances 0-100 in percent; each table's chances are relative. check_treasure() refuses tables that would let the
#   game's reroll loops run forever (magic items, Math).
# * treasure gold 0-1000, gold_max at least gold_min (the new code divides by gold_max - gold_min + 1).
# * monster HP 1-999 (words; monsters have no hit point display), monster damage 0-127 (most are byte operands).
MAX_HP = 999
KNIGHT_BOUNDS = {'strength': (1, 99), 'constitution': (1, 99), 'endurance': (1, 99), 'lives': (1, 99),
                 'hp_bonus': (0, 900), 'gold': (0, 20000), 'experience': (0, 20000), 'daggers': (0, 99),
                 'keys': (0, 4), **{name: (0, 1) for name, _ in MOONSTONE_BITS},
                 **{name: (0, 9) for name, _ in ITEMS}}
SPEEDRUN_GAME = ('healer', 'dragon_scroll', 'hawk_land', 'bk_track', 'bk_lair', 'bk_target', 'bk_shop', 'bk_town')   # speedrun mode keeps the game's own behaviour here
RULES_BOUNDS = {'hawk_curse_chance': (0, 100), 'protection_curse_chance': (0, 100), 'haste_curse_chance': (0, 100),
                'wyrm_curse_chance': (0, 100), 'max_gold': (0, 32767),
                'max_lives': (1, 99), 'moon_days': (1, 100), 'xp_per_stat': (1, 1000), 'weapon_damage': (0, 100),
                'armour_hp': (0, 100), 'xp_per_moon_phase': (0, 100), 'duel_win_xp': (0, 100),
                'ring_of_protection_hp': (0, 100), 'shop_price': (0, 127), 'temple_price': (0, 999),
                'healer_price': (0, 127), 'move_damage': (0, 100), 'max_daggers': (1, 99), 'frog_days': (0, 100),
                'irritation_after_visit': (0, 150), 'irritation_drop_per_day': (0, 127), 'chance': (0, 100),
                'treasure_gold': (0, 1000), 'donation': (1, 20000), 'monster_hp': (1, 999),
                'monster_damage': (0, 127), 'target_margin': (0, 200), 'hit_recovery': (0, 50),
                'default_cycles': (100, 65535), 'additional_cycles_per_knight': (0, 20000),
                'fight_cycles': (100, 65535)}

def ticks(tenths):
    """Tenths of a second -> BIOS ticks (18.2 a second), as SAVEHOOK.COM counts them."""
    return (tenths * 182 + 50) // 100

def read_ini(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=(';',))
    cp.optionxform = str.lower
    try:
        if not cp.read(path, encoding='utf-8'):
            raise RulesError(f'{path} not found')
    except configparser.Error as e:
        raise RulesError(f'the file cannot be read: {e}')
    rb = RULES_BOUNDS
    g = 'Rules'
    # [Parental] age_rating: kept also in speedrun mode
    age = (_get(cp, 'Parental', 'age_rating', _choice(AGE_RATINGS))
           if cp.has_option('Parental', 'age_rating') else AGE_RATINGS['k18'])
    # speedrun mode: everything else in the file is ignored; the default rules with the fixes, but the game's own
    # behaviour wherever runs use it (the dragon's and the Guardian's hits, the dragon's hoard)
    if cp.has_option(g, 'speedrun_mode') and _get(cp, g, 'speedrun_mode', _onoff):
        default = os.path.join(os.path.dirname(os.path.abspath(path)), 'custom_rules-default.ini')
        if os.path.abspath(path) == default:
            raise RulesError('custom_rules-default.ini must have speedrun_mode = off')
        r = read_ini(default)
        r['age'], r['age_lock'] = age
        r.update(cheats=0, catchup=0, anticheese=0)        # no cheat codes; the game's own loot and AI (its exploits)
        r.update(speedrun=1, hoard=HOARD_MODES['keep'], hit_rest=(0, 0), exploit_fixes=0,
                 hawk_curse=0, protection_curse=0, haste_curse=0, wyrm_curse=0,   # no curses: luck should not end a run
                 cycles=(CYCLES_DEFAULT[0], 0),         # D17 off: the game's own speed
                 fight_cycles=(CYCLES_DEFAULT[0],) * 4)
        return r
    r = {'knights': [], 'speedrun': 0, 'exploit_fixes': EXPLOIT_FIXES, 'age': age[0], 'age_lock': age[1]}
    r['ratmen_disease'] = _get(cp, g, 'ratmen_disease', _onoff)
    r['hawk_curse'] = _get(cp, g, 'hawk_curse_chance', float, *rb['hawk_curse_chance'])
    r['protection_curse'] = _get(cp, g, 'protection_curse_chance', float, *rb['protection_curse_chance'])
    for key, name in (('haste_curse', 'haste_curse_chance'), ('wyrm_curse', 'wyrm_curse_chance')):
        r[key] = _get(cp, g, name, float, *rb[name]) if cp.has_option(g, name) else CURSE_DEFAULT
    r['max_gold'] = _get(cp, g, 'max_gold', int, *rb['max_gold'])
    r['max_lives'] = _get(cp, g, 'max_lives', int, *rb['max_lives'])
    r['village_heal'] = _get(cp, g, 'village_heal', _choice(VILLAGE))
    r['village_any'] = _get(cp, g, 'village_heal_where', _choice({'home': 0, 'any': 1}))
    if cp.has_option(g, 'rest_heal'):
        raise RulesError(f'[{g}] rest_heal is now on_E_rest_heal (none, fixed_and_endurance, fixed_only or full)')
    r['rest_heal'] = _get(cp, g, 'on_e_rest_heal', _choice(REST_HEAL))
    r['rest_fixed'] = _get(cp, g, 'rest_heal_fixed_percentage', int, 0, 100)
    r['rest_endurance'] = _get(cp, g, 'rest_heal_endurance_percentage', int, 0, 100)
    r['cheats'] = _get(cp, g, 'cheat_codes', _choice({'no': 0, 'yes': 1})) if cp.has_option(g, 'cheat_codes') else 1
    r['anticheese'] = _get(cp, g, 'anticheese', _choice(ANTICHEESE)) if cp.has_option(g, 'anticheese') else 2
    r['catchup'] = (_get(cp, g, 'catchup', _choice({'off': 0, 'no': 0, 'yes': 1, 'on': 1}))
                    if cp.has_option(g, 'catchup') else 1)
    r['moon_days'] = _get(cp, g, 'moon_days', int, *rb['moon_days'])
    r['deaths'] = _get(cp, g, 'death_animations', _choice(DEATHS)) if cp.has_option(g, 'death_animations') else 0
    r['dragon_debug'] = _get(cp, g, 'dragon_debug_mode', int, 0, 1) if cp.has_option(g, 'dragon_debug_mode') else 0
    r['input_buffer'] = _get(cp, g, 'input_buffer', _onoff) if cp.has_option(g, 'input_buffer') else 1
    r['input_chord'] = (_get(cp, g, 'input_chord', int, 0, 6) if cp.has_option(g, 'input_chord')
                        else INPUT_CHORD_DEFAULT)
    r['input_recent'] = (_get(cp, g, 'input_recent_direction', int, 0, 6) if cp.has_option(g, 'input_recent_direction')
                         else INPUT_RECENT_DEFAULT)
    r['input_log'] = _get(cp, g, 'input_log', _onoff) if cp.has_option(g, 'input_log') else 0
    r['coop_lairs'] = (_get(cp, g, 'coop_lairs', _choice(dict(COOP_MODES, on=1))) if cp.has_option(g, 'coop_lairs')
                       else COOP_DEFAULT)
    r['coop_extra'] = (_get(cp, g, 'extra_loot_per_knight', int, 0, 100) if cp.has_option(g, 'extra_loot_per_knight')
                       else COOP_EXTRA_DEFAULT)
    r['computer_knights'] = _get(cp, g, 'computer_knights', _onoff) if cp.has_option(g, 'computer_knights') else 1
    r['black_knight_ai'] = _get(cp, g, 'black_knight_ai', _bk_ai) if cp.has_option(g, 'black_knight_ai') else 1
    r['timed_defence'] = _get(cp, g, 'timed_defence', _onoff) if cp.has_option(g, 'timed_defence') else 0
    for key, default in TD_DEFAULTS.items():
        r[key] = _get(cp, g, key, int, 0, 100) if cp.has_option(g, key) else default
    r['enchant'] = _get(cp, g, 'sword_enchantments', _onoff) if cp.has_option(g, 'sword_enchantments') else 1
    r['arm_enchant'] = _get(cp, g, 'armour_enchantments', _onoff) if cp.has_option(g, 'armour_enchantments') else 1
    r['arm_chance'] = _get(cp, g, 'armour_enchantment_chance', int, 0, 100) if cp.has_option(g, 'armour_enchantment_chance') else ENCH_CHANCE_DEFAULT
    r['ench_chance'] = (_get(cp, g, 'sword_enchantment_chance', int, 0, 100) if cp.has_option(g, 'sword_enchantment_chance')
                        else ENCH_CHANCE_DEFAULT)
    r['cycles'] = (_get(cp, g, 'default_cycles', int, *rb['default_cycles']),
                   _get(cp, g, 'additional_cycles_per_knight', int, *rb['additional_cycles_per_knight']))
    r['fight_cycles'] = (_fight_cycles(cp, g, r['cycles'][1], rb['fight_cycles'])
                         if cp.has_option(g, 'fight_cycles') else FIGHT_CYCLES_DEFAULT)
    r['save_mode'] = _get(cp, g, 'save_mode', _choice(SAVE_MODES))
    r['fate'] = _get(cp, g, 'prevent_savescumming', _onoff)
    r['selling'] = _get(cp, g, 'merchant_selling', _onoff)
    r['xp_per_stat'] = [_get(cp, g, f'xp_per_stat_{n}_player{"s" if n > 1 else ""}', int, *rb['xp_per_stat'])
                        for n in (1, 2, 3, 4)]
    w = 'Weapons'
    r['weapon_damage'] = [_get(cp, w, name, int, *rb['weapon_damage']) for name in WEAPONS]
    a = 'Armour'
    r['armour_hp'] = [_get(cp, a, f'{name}_hp', int, *rb['armour_hp']) for name in ARMOURS]
    def opt(sec, key, conv, default, *bounds):            # a setting older ini files do not have
        return _get(cp, sec, key, conv, *bounds) if cp.has_option(sec, key) else default
    r['horses'] = opt(g, 'horses', _onoff, 1)
    r['horse_chance'] = opt(g, 'rare_horse_chance', int, HORSE_CHANCE_DEFAULT, 0, 100)
    r['trade_in'] = opt(g, 'merchant_trade_in', _onoff, 1)
    r['horse_list'] = [(text, opt(g, f'{name}_horse_price', int, price, 0, 999), opt(g, f'{name}_horse_movement', int, move, -20, 20),
                        opt(g, f'{name}_horse_forest_swamp_speed', int, soft, 1, 8), opt(g, f'{name}_horse_mountains_edges_speed', int, hard, 1, 8))
                       for name, text, price, move, soft, hard in HORSES]
    r['armour_move'] = [opt(a, f'{name}_movement_penalty_with_horses', int, d, -20, 20) if r['horses'] else
                        opt(a, f'{name}_movement_bonus_without_horses', int, b, -20, 20)
                        for name, d, b in zip(ARMOURS, ARMOUR_MOVE_DEFAULT, ARMOUR_BONUS_DEFAULT)]
    r['ring_hp'] = _get(cp, a, 'ring_of_protection_hp', int, *rb['ring_of_protection_hp'])
    c = 'Combat'
    r['moves'] = {name: _get(cp, c, name, int, *rb['move_damage']) for name, _ in MOVES}
    r['max_daggers'] = _get(cp, c, 'max_daggers', int, *rb['max_daggers'])
    p = 'Prices'
    r['shop'] = {name: _get(cp, p, name, int, *rb['shop_price']) for name, *_ in SHOP}
    r['temple'] = {name: _get(cp, p, f'temple_{name}', int, *rb['temple_price']) for name, _ in TEMPLE}
    r['healer_heal'] = _get(cp, p, 'healer_full_heal', int, *rb['healer_price'])
    r['healer_life'] = _get(cp, p, 'healer_life_point', int, *rb['healer_price'])
    m = 'Math'
    r['frog_days'] = _get(cp, m, 'frog_days', int, *rb['frog_days'])
    r['irritation'] = _get(cp, m, 'irritation_after_visit', int, *rb['irritation_after_visit'])
    r['irritation_drop'] = _get(cp, m, 'irritation_drop_per_day', int, *rb['irritation_drop_per_day'])
    r['math'] = [_get(cp, m, f'{name}_chance', float, *rb['chance']) for name, _ in MATH]
    t = 'Treasure'
    r['lair'] = [_get(cp, t, f'lair_{name}', float, *rb['chance']) for name in LAIR_TYPES]
    r['gold_min'] = _get(cp, t, 'gold_min', int, *rb['treasure_gold'])
    r['gold_max'] = _get(cp, t, 'gold_max', int, *rb['treasure_gold'])
    if r['gold_max'] < r['gold_min']:
        raise RulesError(f'[{t}] gold_max = {r["gold_max"]}: must be at least gold_min ({r["gold_min"]})')
    r['items'] = [_get(cp, t, name, float, *rb['chance']) for name in TREASURE_ITEMS]
    r['hoard'] = _get(cp, t, 'dragon_hoard', _choice(HOARD_MODES))
    pr = 'Practice'
    def lair_or_knight(raw):
        if raw.lower() == 'black_knight':
            return 'black_knight'
        n = int(raw)
        if not 1 <= n <= 24:
            raise ValueError(raw)
        return n
    lair_or_knight.allowed = ['a lair 1-24', 'black_knight']
    r['practice'] = [_get(cp, pr, f'key{k}', lair_or_knight) for k in PRACTICE_KEYS]
    r['practice_flags'] = (TEAM_KNIGHT_HITS * _get(cp, pr, 'team_knight_hits', _onoff) +
                           COOP_KNIGHT_HITS * _get(cp, pr, 'coop_knight_hits', _onoff) +
                           COOP_DAGGER_HITS * _get(cp, pr, 'coop_dagger_hits', _onoff) +
                           TARGET_FIRST * _get(cp, pr, 'monster_target', _choice(TARGETS)))
    r['target_margin'] = _get(cp, pr, 'target_switch_margin', int, *rb['target_margin'])
    y = 'Mythral'
    r['mythral_up_to'] = [_get(cp, y, f'band{n}_up_to', int, *rb['donation']) for n in range(1, MYTHRAL_BANDS)]
    r['mythral'] = [_get(cp, y, f'band{n}_chance', float, *rb['chance']) for n in range(1, MYTHRAL_BANDS + 1)]
    mo = 'Monsters'
    monster_keys = set()
    def monster(key, bounds):
        monster_keys.add(key)
        return _get(cp, mo, key, int, *rb[bounds])
    r['monsters'] = {name: (monster(f'{name}_hp', 'monster_hp'), monster(f'{name}_damage', 'monster_damage'))
                     for name, *_ in MONSTERS}
    r['ratmen'] = {}
    for phase, *_ in RATMEN:
        pre = 'ratman' if phase == 'normal' else f'ratman_{phase}'
        r['ratmen'][phase] = tuple(monster(f'{pre}_{what}', 'monster_hp' if what == 'hp' else 'monster_damage')
                                   for what in ('hp', 'bite', 'claw'))
    r['guardian'] = (monster('guardian_hp', 'monster_hp'), monster('guardian_damage', 'monster_damage'),
                     monster('guardian_second_attack_damage', 'monster_damage'))
    r['dragon'] = (monster('dragon_hp', 'monster_hp'), monster('dragon_damage', 'monster_damage'),
                   monster('dragon_second_attack_damage', 'monster_damage'))
    r['dragon_parts'] = (monster('dragon_parts_hp', 'monster_hp'), monster('dragon_parts_damage', 'monster_damage'))
    r['talisman_min'] = monster('talisman_min_damage', 'monster_damage')
    r['hit_rest'] = tuple(ticks(monster(f'{who}_hit_recovery', 'hit_recovery')) for who in ('dragon', 'guardian'))
    check_treasure(r)
    for sec in SECTIONS:
        if not cp.has_section(sec):
            old = sec.split('_')[0]                          # [Knight1] became [Knight1_blue]
            raise RulesError(f'section [{sec}] is missing' + (f' ([{old}] is now [{sec}])' if cp.has_section(old) else ''))
        if cp.has_option(sec, 'moonstones'):                 # moonstones = 0-4 became one line per stone
            raise RulesError(f'[{sec}] moonstones: now one line per stone, 0 or 1: '
                             + ', '.join(name for name, _ in MOONSTONE_BITS))
        k = {key: _get(cp, sec, key, int, lo, hi) for key, (lo, hi) in KNIGHT_BOUNDS.items()}
        k['weapon'] = _get(cp, sec, 'weapon', _choice(WEAPONS))
        k['armour'] = _get(cp, sec, 'armour', _choice(ARMOURS))
        k['mode'] = _get(cp, sec, 'mode', _choice(MODES))
        k['colour'] = _get(cp, sec, 'colour', _colour)
        if sec != 'Black':
            k['home'] = _get(cp, sec, 'home_village', _choice(HOME_VILLAGES))
        r['knights'].append(k)
    b = 'Black'
    r['ai_xp_per_moon_phase'] = _get(cp, b, 'xp_per_moon_phase', int, *rb['xp_per_moon_phase'])
    r['ai_math_per_moon_phase'] = _get(cp, b, 'math_visit_per_moon_phase', _onoff)
    r['ai_duel_win_xp'] = _get(cp, b, 'duel_win_xp', int, *rb['duel_win_xp'])
    knight_keys = set(KNIGHT_BOUNDS) | {'weapon', 'armour', 'mode', 'colour'}
    known = {g: {'ratmen_disease', 'hawk_curse_chance', 'protection_curse_chance', 'haste_curse_chance', 'wyrm_curse_chance', 'max_gold', 'max_lives',
                 'speedrun_mode', 'default_cycles', 'fight_cycles', 'additional_cycles_per_knight', 'death_animations', 'dragon_debug_mode', 'input_buffer', 'input_recent_direction', 'input_chord', 'input_log', 'coop_lairs', 'extra_loot_per_knight', 'sword_enchantments', 'sword_enchantment_chance', 'armour_enchantments', 'armour_enchantment_chance', 'village_heal', 'village_heal_where', 'on_e_rest_heal', 'rest_heal_fixed_percentage', 'rest_heal_endurance_percentage', 'cheat_codes', 'anticheese', 'catchup', 'moon_days', 'save_mode', 'prevent_savescumming',
                 'merchant_selling', 'merchant_trade_in', 'horses', 'rare_horse_chance', 'computer_knights', 'black_knight_ai', 'timed_defence', *TD_DEFAULTS,
                 *(f'{name}_horse_{what}' for name, *_ in HORSES for what in ('price', 'movement', 'forest_swamp_speed', 'mountains_edges_speed')),
                 'xp_per_stat_1_player',
                 'xp_per_stat_2_players', 'xp_per_stat_3_players', 'xp_per_stat_4_players'},
             w: set(WEAPONS), a: {f'{name}_hp' for name in ARMOURS} | {f'{name}_movement_penalty_with_horses' for name in ARMOURS} | {f'{name}_movement_bonus_without_horses' for name in ARMOURS} | {'ring_of_protection_hp'},
             c: {name for name, _ in MOVES} | {'max_daggers'},
             p: {name for name, *_ in SHOP} | {f'temple_{name}' for name, _ in TEMPLE}
                | {'healer_full_heal', 'healer_life_point'},
             m: {'frog_days', 'irritation_after_visit', 'irritation_drop_per_day'} | {f'{n}_chance' for n, _ in MATH},
             t: {f'lair_{name}' for name in LAIR_TYPES} | {'gold_min', 'gold_max', 'dragon_hoard'} | set(TREASURE_ITEMS),
             y: {f'band{n}_up_to' for n in range(1, MYTHRAL_BANDS)}
                | {f'band{n}_chance' for n in range(1, MYTHRAL_BANDS + 1)},
             mo: monster_keys,
             'Parental': {'age_rating'},
             'Practice': {f'key{k}' for k in PRACTICE_KEYS} | {'team_knight_hits', 'coop_knight_hits', 'coop_dagger_hits', 'monster_target',
                            'target_switch_margin'},
             **{sec: knight_keys | {'home_village'} for sec in SECTIONS[:-1]},
             b: knight_keys | {'xp_per_moon_phase', 'math_visit_per_moon_phase', 'duel_win_xp'}}
    for sec in cp.sections():                            # a misspelt name would otherwise be ignored silently
        if sec not in known:
            raise RulesError(f'unknown section [{sec}]')
        for key in cp.options(sec):
            if key not in known[sec] and not (sec == g and key in REMOVED_SETTINGS):
                raise RulesError(f'[{sec}] {key}: unknown setting')
    return r

# --- the SAVEHOOK.COM table -------------------------------------------------------------------------------------------
DEFAULT_KNIGHT = dict(strength=1, constitution=1, endurance=1, lives=5, gold=10, experience=0, daggers=10, hp_bonus=0,
                      weapon=0x16, armour=0x1b, keys=0, mode=0, colour=None,
                      **{name: 0 for name, _ in MOONSTONE_BITS}, **{name: 0 for name, _ in ITEMS})

def table(r=None):
    """Settings table for SAVEHOOK.COM (TABLE_SIZE bytes). Without rules: the normal game's values."""
    knights = r['knights'] if r else [DEFAULT_KNIGHT] * len(SECTIONS)
    t = bytearray(TABLE_SIZE)
    for i, k in enumerate(knights):
        o = i * SECTION_SIZE
        t[o:o + 4] = bytes([k['strength'], k['constitution'], k['endurance'], k['lives']])
        struct.pack_into('<HBBhHHh', t, o + 4, k['gold'], k['daggers'], k['mode'], k['experience'], k['weapon'],
                         k['armour'], k['hp_bonus'])
        items = bytearray(24)
        for name, off in ITEMS:
            struct.pack_into('<H', items, off, k[name])
        if k['weapon'] == WEAPONS['sword_of_sharpness']:
            struct.pack_into('<H', items, SHARPNESS_ITEM, 1)
        items[KEYS] = (1 << k['keys']) - 1                 # one bit per region
        items[MOONSTONES] = sum(bit for name, bit in MOONSTONE_BITS if k[name])
        t[o + 0x10:o + 0x28] = items
    hp = r['armour_hp'] if r else [0, 10, 20, 30]
    struct.pack_into('<4hh', t, G_ARMOUR_HP, *hp, r['weapon_damage'][0] if r else 0)
    t[G_REST] = r['rest_heal'] if r else 0
    t[G_REST_FIXED] = r['rest_fixed'] if r else 0
    t[G_REST_ENDURANCE] = r['rest_endurance'] if r else 0
    t[G_CHEATS] = r.get('cheats', 1) if r else 0
    t[G_ANTICHEESE] = 1 if r and r.get('anticheese', 0) == 2 else 0   # the older rules: only with yes
    t[G_CATCHUP] = r.get('catchup', 1) if r else 0
    t[G_AGE] = r.get('age', 18) if r else 18
    t[G_VILLAGE] = r['village_heal'] if r else 0
    t[G_MAX_LIVES] = r['max_lives'] if r else 5
    struct.pack_into('<h', t, G_RING, r['ring_hp'] if r else 20)
    for i, k in enumerate(knights):
        t[G_COLOURS + i] = colour_words(k['colour'] or DEFAULT_COLOURS[i])[3]
        t[G_HOMES + i] = 0xff if i == 4 else k['home'] if r else i
    t[G_VILLAGE_ANY] = r['village_any'] if r else 0
    t[G_SAVE_MODE] = r['save_mode'] if r else 0
    t[G_FATE] = r['fate'] if r else 0
    t[G_SELLING] = r['selling'] if r else 0
    struct.pack_into('<H', t, G_MAX_GOLD, r['max_gold'] if r else 150)
    prices = r['shop'] if r else {'dagger': 2, 'broadsword': 10, 'claymore': 25, 'chain_mail': 30, 'plate_mail': 50,
                                  'battle_armour': 75}
    struct.pack_into('<6H', t, G_SELL, *(prices[name] // 2 for name in SELL_ITEMS))
    struct.pack_into('<6H', t, G_BUY, *(prices[name] for name in SELL_ITEMS))
    t[G_HOARD] = r['hoard'] if r else HOARD_MODES['grows']
    for n, choice in enumerate(r['practice'] if r else PRACTICE_DEFAULTS):
        t[G_PRACTICE + n] = 0xff if choice == 'black_knight' else choice - 1
    t[G_PRACTICE_FLAGS] = r['practice_flags'] if r else 0
    t[G_TARGET_MARGIN] = r['target_margin'] if r else 20
    t[G_HIT_REST:G_HIT_REST + 2] = bytes(r['hit_rest'] if r else (ticks(HIT_REST_DEFAULT),) * 2)
    t[G_EXPLOIT_FIXES] = r['exploit_fixes'] if r else EXPLOIT_FIXES
    struct.pack_into('<HH', t, G_CYCLES, *(r['cycles'] if r else CYCLES_DEFAULT))
    struct.pack_into('<4H', t, G_FIGHT_CYCLES, *(r.get('fight_cycles', FIGHT_CYCLES_DEFAULT) if r else FIGHT_CYCLES_DEFAULT))
    t[G_DEATHS] = r.get('deaths', 0) if r else 0
    t[G_DRAGON_DEBUG] = r.get('dragon_debug', 0) if r else 0
    t[G_HASTE_CURSE] = roll_threshold(r.get('haste_curse', 0) if r else 0) & 0xff
    t[G_WYRM_CURSE] = roll_threshold(r.get('wyrm_curse', 0) if r else 0) & 0xff
    t[G_INPUT_BUFFER] = r.get('input_buffer', 1) if r else 1
    t[G_INPUT_CHORD] = r.get('input_chord', INPUT_CHORD_DEFAULT) if r else INPUT_CHORD_DEFAULT
    t[G_INPUT_RECENT] = r.get('input_recent', INPUT_RECENT_DEFAULT) if r else INPUT_RECENT_DEFAULT
    t[G_INPUT_LOG] = r.get('input_log', 0) if r else 0
    t[G_COOP_LAIRS] = r.get('coop_lairs', COOP_DEFAULT) if r else 0
    t[G_COOP_EXTRA] = r.get('coop_extra', COOP_EXTRA_DEFAULT) if r else 0
    t[G_COMPUTER] = r.get('computer_knights', 1) if r else 1
    t[G_BK_AI] = r.get('black_knight_ai', 1) if r else 0
    t[G_BK_HEAL] = r.get('healer_heal', 10) if r else 10
    t[G_CHOP_CHEESE] = r.get('anticheese', 0) if r else 0
    t[G_TD] = r.get('timed_defence', 0) if r else 0
    for at, key in ((G_TD_WINDOW, 'defence_window'), (G_TD_FAST, 'fast_swing_time'), (G_TD_STAGGER, 'stagger_time'), 
                    (G_TD_PURPLE, 'purple_knight_defence'), (G_TD_PURPLE + 1, 'purple_knight_mistimed'), (G_TD_BLACK, 'black_knight_defence'),
                    (G_TD_BLACK + 1, 'black_knight_mistimed'), (G_TD_PAUSE, 'computer_defence_pause')):
        t[at] = r.get(key, TD_DEFAULTS[key]) if r else TD_DEFAULTS[key]
    t[G_ENCHANT] = r.get('enchant', 1) if r else 0
    t[G_ENCH_CHANCE] = r.get('ench_chance', ENCH_CHANCE_DEFAULT) if r else 0
    struct.pack_into('<4b', t, G_ARMOUR_MOVE, *(r.get('armour_move', ARMOUR_MOVE_DEFAULT) if r else (0, 2, 0, 2)))
    t[G_ARM_ENCH] = r.get('arm_enchant', 1) if r else 0
    t[G_ARM_CHANCE] = r.get('arm_chance', ENCH_CHANCE_DEFAULT) if r else 0
    t[G_DISEASE] = 1 if r and r.get('ratmen_disease') else 0
    t[G_HORSES] = r.get('horses', 1) if r else 0          # D38
    t[G_HORSE_CHANCE] = r.get('horse_chance', HORSE_CHANCE_DEFAULT) if r else 0
    t[G_TRADE_IN] = r.get('trade_in', 1) if r else 0      # D40
    horses = r.get('horse_list') if r else None
    horses = horses or [(text, price, move, soft, hard) for _, text, price, move, soft, hard in HORSES]
    for i, (text, price, move, soft, hard) in enumerate(horses):
        struct.pack_into('<H', t, G_HORSE_PRICE + 2 * i, price)
        struct.pack_into('<b', t, G_HORSE_MOVE + i, move)
        t[G_HORSE_SOFT + i], t[G_HORSE_HARD + i] = soft, hard
        data = f'Buy {text} for {price} GP'.encode()
        t[G_HORSE_TEXT + i * HORSE_TEXT_SIZE:G_HORSE_TEXT + i * HORSE_TEXT_SIZE + len(data)] = data
        data = f'Sell {text} for {price // 2} GP'.encode()
        t[G_HORSE_SELL + i * HORSE_TEXT_SIZE:G_HORSE_SELL + i * HORSE_TEXT_SIZE + len(data)] = data
    return bytes(t)

# --- MAIN.EXE patches -------------------------------------------------------------------------------------------------
def roll_threshold(percent):
    """The game's 0-100 roll (1000:BF82: 7 random bits, 100-127 minus 27) is compared with 'roll <= limit'.
    Returns the limit whose chance is nearest to percent; -1 (never) for 0."""
    if percent <= 0:
        return -1
    rolls = [x - 27 if x >= 100 else x for x in range(128)]
    return min(range(101), key=lambda t: abs(sum(v <= t for v in rolls) / 1.28 - percent))

def chance_limits(chances):
    """Limits for a table that the game walks with 'roll <= limit' (first match wins), from the chance of each entry.
    The chances are relative (scaled to add up to 100); from the last entry with a chance on, the limit is 100."""
    total, cum, out = sum(chances), 0, []
    for c in chances:
        cum += c
        out.append(100 if cum >= total - 1e-9 else roll_threshold(cum * 100 / total))
    return out

def check_treasure(r):
    """The chance tables must leave the game something to pick, or its reroll loops could run forever."""
    for key, sec, what in (('lair', 'Treasure', 'lair_*'), ('items', 'Treasure', 'the magic item chances'),
                           ('math', 'Math', '*_chance')):
        if sum(r[key]) <= 0:
            raise RulesError(f'[{sec}] {what}: at least one must be above 0')
    prev, others = -1, 0
    for name, limit in zip(TREASURE_ITEMS, chance_limits(r['items'])):
        others += limit > prev and name != 'sword_of_sharpness'
        prev = max(prev, limit)
    if others < 2:
        raise RulesError('[Treasure] at least two magic items besides the Sword of Sharpness need a chance above 0: '
                         'the game never gives the same item twice in a row, so with fewer it could roll forever')
    item, ability, gold = chance_limits(r['math'])[:3]
    # Math adds his irritation to the roll in a byte (1000:B8F3); 255 = never visited, and then the frog is rolled
    # again. With all abilities at 5 the ability is rolled again (1000:B96D). Irritation drops by the daily amount and
    # becomes 0 when the byte goes negative (1000:11AB).
    irritations, i = set(), r['irritation']
    while i not in irritations:
        irritations.add(i)
        i = (i - r['irritation_drop']) & 255
        i = 0 if i & 0x80 else i
    for i in sorted(irritations | {255}):
        sums = [(x + i) & 255 for x in range(101)]
        if not any(s <= item or ability < s <= gold or (i != 255 and s > gold) for s in sums):
            raise RulesError('[Math] with these chances Math could roll forever (when all abilities are 5' +
                             (', on a first visit' if i == 255 else f', at irritation {i}') +
                             '): give magic_item_chance or gold_chance more')

def main_patches(r, img):
    """(image offset, old bytes, new bytes) for the rules, checked against the fixed MAIN.EXE image."""
    out = []
    def imm(where, size, value, signed=False):
        fmt = {1: 'b' if signed else 'B', 2: 'h' if signed else 'H'}[size]
        out.append((where, bytes(img[where:where + size]), struct.pack('<' + fmt, value)))
    for where, old, kind in HOOKS:
        if r['speedrun'] and kind in SPEEDRUN_GAME:
            continue
        new, _ = hook_bytes(where, old, kind)
        out.append((where, bytes.fromhex(old), new))
    for site in (0xb4cd, 0xb4d4, 0xba11, 0xba18, 0xcef6):   # gold cap 150: dice, Math, loot
        imm(site, 2, r['max_gold'])
    for site in (0xd060, 0xd068):                        # D43: the High Temple's sale only stops at 32767; max_gold as it is left
        imm(site, 2, 0x7fff)
    for site, old, new in ((0xb4cf, 0x7e, 0xeb), (0xba13, 0x7c, 0x72), (0xd062, 0x7e, 0x76)):   # D41: the cap's test unsigned, so a sum past 32767 is capped
        out.append((site, bytes([old]), bytes([new])))
    for site in (0xbdc6, 0xbdcf):                        # D41: the donation screen's gold in E4B4h, its own buffer has four bytes
        out.append((site, b'\x3f\xe2', b'\xb4\xe4'))
    if r['speedrun']:                                    # K24 undone: the damage bonus as the game
        out += [(where, new, old) for (_, where), old, new in PATCHES['K24']['bytes'] + PATCHES['K32']['bytes']]
    # the secondary button: a controller's button 2 (joystick A's, B's) no longer fires as button 1 does
    # (1000:834D, 82DA: shr al,1 / and dl,al joined the two buttons), it is the secondary button (SAVEHOOK sec_input)
    for site in (0x83b1, 0x833e):
        out.append((site, b'\xd0\xe8', b'\x8a\xc0'))      # shr al, 1 -> mov al, al
    m = r['max_lives']                                   # life cap 5: Stonehenge, healer, potion, computer potion use
    imm(0x10b1, 1, m); out.append((0x10b2, b'\x74', b'\x7d'))     # cmp 5 / je -> jge (a start above the cap)
    imm(0xbce4, 1, m); out.append((0xbce5, b'\x74', b'\x7d'))
    imm(0xada6, 1, m)                                    # (the potion's cap: SAVEHOOK, K23)
    if r['fate'] or r['save_mode'] in SAVE_CHECKED:     # reward rolls (village_any and homes: the place hook)
        for where, old, _ in FATE_HOOKS:
            new, _ = hook_bytes(where, old, 'fate')
            out.append((where, bytes.fromhex(old), new))
    imm(0x1164, 1, r['moon_days'] - 1, True)             # moon phase: cmp [898Bh],3 / jle (counter 1-4)
    imm(0xcd1f, 2, roll_threshold(r['hawk_curse']), True)          # Hawk: roll <= 15 -> cursed
    imm(0xcd6b, 2, roll_threshold(r['protection_curse']), True)    # Protection: roll <= 10 -> cursed
    for players, n in enumerate(r['xp_per_stat']):      # DS:04D4: XP per stat point for 1-4 players
        imm(image_offset(('DS', 0x4d4 + 2 * players)), 2, n)
    for value, site in zip(r['weapon_damage'][1:], (0x2d90, 0x2d99, 0x2da2)):   # add ax,2 / 3 / 5
        imm(site, 2, value, True)
    for value, site in zip(r['armour_hp'][1:], (0x02c0, 0x02c9, 0x02d2)):       # add bx,10 / 20 / 30
        imm(site, 1, value, True)
    imm(0x1217, 1, r['ai_xp_per_moon_phase'], True)      # computer knights: add word [si+36h],1 every moon phase
    if not r['ai_math_per_moon_phase']:
        out.append((0x121f, bytes(img[0x121f:0x1222]), b'\x90\x90\x90'))       # call 1000:B8D6 (Math)
    imm(0x04a2, 1, r['ai_duel_win_xp'], True)            # computer knight wins a duel: +1 XP
    for i, k in enumerate(r['knights']):                # colours: the chosen colour's words in this knight's slots
        fight, item, status = colour_words(k['colour'])[:3]
        for words, sites in zip((fight, item, status), COLOUR_SITES[i]):
            for value, site in zip(words, sites):
                imm(site, 2, value)
        for value, site in zip(glow_words(k['colour'], i), GLOW_SITES[i]):   # D61: the low-HP glow's targets
            imm(site, 2, value)
    imm(GLOW_SPEED_SITE, 2, 2)                           # D61: both knights' glows at the same speeds 2, 1, 1
    for name, cmp_h, sub_h, cmp_ai, price_ai in SHOP:   # shops: the human's check and payment, the computer's
        v = r['shop'][name]
        imm(cmp_h, 1, v, True); imm(sub_h, 1, v, True); imm(cmp_ai, 1, v, True)
        if name == 'dagger':
            imm(price_ai, 1, v, True)                    # computer knight: sub word [si+32h],2 per dagger
        else:
            imm(price_ai, 2, v)                          # computer knight: mov word [0C424h],price
    imm(0xaf41, 2, r['shop']['dagger'])                  # computer knight: the dagger's price word, as the others
    for name, off in TEMPLE:                             # High Temple buy prices (selling pays half)
        imm(TEMPLE_SITES[off], 2, r['temple'][name])
    prices = {**r['shop'], **r['temple']}
    for ds_off, name, kind in PRICE_TEXTS:              # the shown prices
        where = image_offset(('DS', ds_off))
        old = bytes(img[where:img.index(0, where) + 1])
        value = prices[name] if kind == 'buy' else prices[name] // 2
        out.append((where, old, price_text(old[:-1].decode('ascii'), value)))
    heal, life = r['healer_heal'], r['healer_life']      # healer: the donation must cover a full heal (1000:BCB6)
    imm(0xbcb7, 2, heal); imm(0xbcdb, 1, heal, True); imm(0xbcee, 1, life, True)
    imm(0xae86, 1, life, True); imm(0xae93, 2, life)     # computer knight buys a life point
    for name, site in MOVES:
        imm(site, 2, r['moves'][name])
    imm(0xcfd9, 1, r['max_daggers'], True)               # shop: cmp byte [si+34h],10 / jge
    imm(0xce19, 1, r['max_daggers'], True)               # loot: the same limit
    imm(0xce25, 1, r['max_daggers'], True)
    imm(0xafec, 1, r['max_daggers'], True)               # computer knight: cmp byte [si+34h],10 / je -> jge
    out.append((0xafed, b'\x74', b'\x7d'))
    for value, site in zip(r['armour_hp'][1:], (0xcf3b, 0xcf5e, 0xcf81)):   # buying armour adds its HP at once
        imm(site, 1, value, True)
    imm(0x02b2, 2, r['ring_hp'])                         # max HP formula: mov cx,20 per ring
    imm(0xd02b, 1, r['ring_hp'], True)                   # temple: buying a ring adds 20 HP at once
    imm(0xb90e, 1, r['frog_days'], True)                 # Math: mov byte [si+3Ah],3
    imm(0xb8cd, 1, r['irritation'])                      # Math: mov byte [si+3Bh],70 after a visit
    imm(0x11ae, 1, r['irritation_drop'], True)           # daily update: sub byte [si+3Bh],10
    imm(0xbad5, 1, r['ring_hp'], True)                   # Math gives a ring: add word [si+38h],20
    for (_, site), limit in zip(MATH, chance_limits(r['math'])):
        if site:
            imm(site, 2, limit, True)                    # cmp ax,30 / 70 / 90
    lair = chance_limits(r['lair'])                      # DS:6952: gold, two items, gold and items (twice)
    for n, limit in enumerate((lair[0], lair[1], max(lair[1], 90))):
        imm(image_offset(('DS', 0x6952 + 4 * n)), 2, limit, True)
    for n, limit in enumerate(chance_limits(r['items'])):   # DS:E365: (limit, item) pairs
        imm(image_offset(('DS', 0xe365 + 4 * n)), 2, limit, True)
    if (r['gold_min'], r['gold_max']) != (GOLD_MIN, GOLD_MAX):
        # 1000:B9F5 and ax,1Fh / cmp ax,15h / jle / sub ax,0Ah / add ax,0Ah -> an even spread:
        # push dx / xor dx,dx / mov bx,max-min+1 / div bx / xchg ax,dx / pop dx / add ax,min / nop
        # (bx is free: the Math branch sets it next, the lair branch returns to a loop that does not use it).
        new = (b'\x52\x33\xd2\xbb' + struct.pack('<H', r['gold_max'] - r['gold_min'] + 1) + b'\xf7\xf3\x92\x5a\x05' +
               struct.pack('<H', r['gold_min']) + b'\x90')
        out.append((0xb9f5, bytes.fromhex('251f003d15007e032d0a00050a00'), new))
    ups = r['mythral_up_to'] + [250 if r['max_gold'] <= 250 and r['mythral_up_to'][-1] < 250 else 0x7fff]
    for n, (up, chance) in enumerate(zip(ups, r['mythral'])):   # DS:E478: (largest donation, modifier) pairs
        imm(image_offset(('DS', 0xe478 + 4 * n)), 2, up)
        imm(image_offset(('DS', 0xe47a + 4 * n)), 2, 50 - roll_threshold(chance), True)
    for name, hp_sites, damage_sites in MONSTERS:
        hp, damage = r['monsters'][name]
        for site in hp_sites:
            imm(site, 2, hp)
        for site, size in damage_sites:
            imm(site, size, damage, True)
    for phase, hp_sites, bite, claw in RATMEN:
        hp, b, c = r['ratmen'][phase]
        for site in hp_sites:
            imm(site, 2, hp)
        imm(bite, 2, b); imm(claw, 2, c)
    hp, damage, second = r['guardian']                   # 1000:436C: chop and others 10, move 2: 8
    imm(0x278f, 2, hp); imm(0x4375, 1, damage, True); imm(0x4387, 1, damage, True); imm(0x4381, 1, second, True)
    hp, damage, second = r['dragon']                     # type 0Ah (1000:43B9): move 2: 20, others 30 (also type 14h)
    imm(0x2574, 2, hp); imm(0x43cf, 2, damage); imm(0x43ca, 2, second)
    hp, damage = r['dragon_parts']                       # the two type 16h objects (1000:24A8, 24E1; 43DF)
    for site in (0x24ba, 0x24bf, 0x24f3, 0x24f8):
        imm(site, 2, hp)
    imm(0x43e0, 2, damage)
    imm(0x440b, 2, r['talisman_min']); imm(0x4410, 2, r['talisman_min'])   # dragon damage >> talismans, at least 5
    if r['ratmen_disease']:                              # undo K17
        for where, old, new in PATCHES['K17']['bytes']:
            out.append((image_offset(where), new, old))
    return out

def price_text(text, value):
    """text ('Buy ... for 10 GP') with its price replaced by value, NUL-terminated and NUL-padded to the original
    length; shorter wording when the new number needs more room than the original text had."""
    verb, rest = text.split(' ', 1)
    name = rest.rsplit(' for ', 1)[0]
    for form in (f'{verb} {name} for {value} GP', f'{verb} {name} for {value}GP', f'{verb} {name} {value} GP',
                 f'{verb} {name} {value}GP'):
        if len(form) <= len(text):
            return form.encode('ascii').ljust(len(text) + 1, b'\0')
    raise RulesError(f'the price text "{text}" cannot hold {value}')

def apply(img, patches):
    img = bytearray(img)
    for where, old, new in patches:
        if len(new) != len(old):
            raise ValueError(f'1000:{where:04X}: the new bytes are not as long as the old ones')
        if img[where:where + len(old)] != old:
            raise RulesError(f'MAIN.EXE: expected {old.hex()} at 1000:{where:04X}, found '
                             f'{img[where:where + len(old)].hex()} (is _fixes/fixed/MAIN.EXE the fixed build?)')
        img[where:where + len(new)] = new
    return bytes(img)

def build(game, r):
    """Returns (MAIN.EXE, SAVEHOOK.COM) for the rules r."""
    from make_savehook import make_savehook
    exe = open(os.path.join(game, '_fixes', 'fixed', 'MAIN.EXE'), 'rb').read()
    header = struct.unpack('<H', exe[8:10])[0] * 16
    img = apply(exe[header:], main_patches(r, exe[header:]))
    return exe[:header] + img, make_savehook(table(r))

def install(game, setup=False):
    """install_lock around _install (below)."""
    with install_lock(game):
        return _install(game, setup)

def _install(game, setup=False):
    """Applies custom_rules.ini (made from custom_rules-default.ini if missing): _fixes/rules/MAIN.EXE, SAVEHOOK.COM,
    CUSTOM_RULES.FLG,
    and MAIN.EXE unless the game is in original mode. Raises RulesError (nothing written) for a bad value, and
    SetupUnfinished unless setup is true while a Setup has not finished: its game files cannot be vouched for here."""
    if not setup and os.path.exists(os.path.join(game, SETUP_FLAG)):
        raise SetupUnfinished('the setup did not finish')
    ini = os.path.join(game, 'custom_rules.ini')
    if not os.path.exists(ini):
        shutil.copyfile(os.path.join(game, 'custom_rules-default.ini'), ini)
    r = read_ini(ini)
    lock_path = os.path.join(game, AGE_LOCK)             # a permanent age rating: never above it again
    age_check(game, r)
    old_lock = age_limit(game)
    new_lock = min(old_lock, r['age_lock'] or 18)
    exe, hook = build(game, r)
    from make_savehook import make_savehook
    # The save mode is in SAVEHOOK.COM's table, so Custom_rules_off.bat puts the normal SAVEHOOK.COM back from here.
    # _fixes/rules holds the matching pair: Fixes_On.bat installs it and Start.bat compares against it
    writes = [(os.path.join('_fixes', 'fixed', 'SAVEHOOK.COM'), make_savehook()),
              (os.path.join('_fixes', 'rules', 'MAIN.EXE'), exe), (os.path.join('_fixes', 'rules', 'SAVEHOOK.COM'), hook),
              ('SAVEHOOK.COM', hook)]
    on = not os.path.exists(os.path.join(game, 'ORIGINAL.FLG'))
    if on:
        writes.append(('MAIN.EXE', exe))
    # a permanent age rating: Start.bat then starts the game only with the fixes and the custom rules in place, and
    # Custom_rules_off.bat, Custom_rules_reset.bat and Fixes_Off.bat refuse
    lock = f'{new_lock} the highest age rating allowed in this installation\n'.encode()
    swap_files(game, writes + [('CUSTOM_RULES.FLG', b'custom rules\r\n'), (AGE_LOCK, lock)])
    return on

_held = {}                                            # install_lock: the folders this process holds, with a depth

@contextlib.contextmanager
def install_lock(game, wait=10):
    """Holds this installation's lock (_fixes/UPDATE.LCK) for Setup, the custom rules and the mode switches, so that
    two of them never change the same folder at once. The operating system releases it if the process dies, so a
    leftover file blocks nothing; INSTALLING.FLG and SETUP.FLG stay the markers of an unfinished change. Reentrant
    within one process. Waits up to wait seconds, then raises Busy."""
    key = (os.path.normcase(os.path.abspath(game)), threading.get_ident())   # reentrant per thread, not shared
    if key in _held:
        _held[key] += 1
        try:
            yield
        finally:
            _held[key] -= 1
        return
    path = os.path.join(game, UPDATE_LOCK)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f = open(path, 'a+b')
    deadline = time.monotonic() + wait
    while True:
        try:
            if os.name == 'nt':
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if time.monotonic() >= deadline:
                f.close()
                raise Busy('another change of the game\'s files is under way in this folder (Setup.bat, '
                           'Custom_rules_on.bat or a Fixes/Custom_rules launcher); let it finish and try again')
            time.sleep(0.2)
    _held[key] = 1
    try:
        yield
    finally:
        del _held[key]
        try:
            if os.name == 'nt':
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        f.close()

def swap_files(game, files):
    """Puts (name, data) files in place as one change; data None removes the file. Runs under install_lock.
    Everything is first written next to its target under a name of this change's own, so a full disk or a read-only
    folder changes nothing. If a replacement or removal fails (a program holds the file open), the files already
    changed are put back. INSTALLING.FLG exists during the change and stays if the process dies or the undo fails:
    Start.bat and Fixes_On.bat then refuse until a new install. A marker that was already there stays after an undo too:
    the undo only brings back that unfinished state. A change that finishes removes it and writes BUILD.TXT.
    Raises OSError."""
    with install_lock(game):
        _swap(game, files)
    write_stamp(game)

def _swap(game, files):
    tag = f'.{os.getpid()}-{uuid.uuid4().hex[:8]}'
    pairs = [(os.path.join(game, name), data) for name, data in files]
    marker = os.path.join(game, INSTALLING)
    unfinished_before = os.path.exists(marker)
    def remove(path):
        try:
            os.remove(path)
        except OSError:
            pass
    def cleanup():
        for path, _ in pairs:
            remove(path + tag + '.new')
            remove(path + tag + '.old')
    try:
        for path, data in pairs:
            if data is not None:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path + tag + '.new', 'wb') as f:
                    f.write(data)
        with open(marker, 'wb') as f:
            f.write(b'a change of the programs has not finished\r\n')
    except OSError:
        cleanup()
        raise
    done = []
    try:
        for path, data in pairs:
            existed = os.path.exists(path)
            if data is None:
                if existed:
                    os.replace(path, path + tag + '.old')
            else:
                if existed:
                    shutil.copyfile(path, path + tag + '.old')
                os.replace(path + tag + '.new', path)
            done.append((path, existed, data))
    except OSError:
        for path, existed, data in reversed(done):    # an undo that fails leaves the marker: Start.bat refuses
            if existed:
                os.replace(path + tag + '.old', path)
            elif data is not None:
                os.remove(path)
        cleanup()
        if not unfinished_before:
            os.remove(marker)
        raise
    cleanup()
    os.remove(marker)

def _sha(path):
    try:
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]
    except OSError:
        return '-'

def write_stamp(game):
    """BUILD.TXT: the release, the source revision (git, if this is a checkout), a hash of the tools, the mode and the
    hashes of the programs and generated files in use. Only a record: a failure to write it is ignored."""
    version = revision = '-'
    for root in (game, os.path.dirname(HERE)):         # the installation, else the tools' own folder (a dev install)
        try:
            version = next((line[3:].strip() for line in open(os.path.join(root, 'CHANGELOG.md'), encoding='utf-8')
                            if line.startswith('## ')), '-')
            break
        except OSError:
            pass
    for root in (game, os.path.dirname(HERE)):
        try:
            head = open(os.path.join(root, '.git', 'HEAD')).read().strip()
            if head.startswith('ref: '):
                ref = os.path.join(root, '.git', *head[5:].split('/'))
                head = open(ref).read().strip() if os.path.exists(ref) else head[5:]
            revision = head[:12]
            break
        except OSError:
            pass
    tools = hashlib.sha256()
    for name in sorted(n for n in os.listdir(HERE) if n.endswith('.py')):
        tools.update(name.encode() + open(os.path.join(HERE, name), 'rb').read())
    flag = lambda name: os.path.exists(os.path.join(game, name))
    mode = 'original' if flag('ORIGINAL.FLG') else 'fixed'
    if flag('CUSTOM_RULES.FLG'):
        mode += ' + custom rules' + (' (remembered for Fixes_On.bat)' if mode == 'original' else '')
    if flag(INSTALLING) or flag(SETUP_FLAG):
        mode += ' (a change did not finish)'
    lines = [f'Moonstone Rebuilt {version}', f'source revision: {revision}', f'tools: {tools.hexdigest()[:16]}',
             f'mode: {mode}', f'age limit: K{age_limit(game)}']
    for name in ('MAIN.EXE', 'INTR.EXE', 'SAVEHOOK.COM', os.path.join('DISKB', 'KN3.OB'), os.path.join('DISKB', 'HE3.OB'),
                 os.path.join('DISKB', 'KH.CEL'), os.path.join('DISKB', 'MH.C'), 'custom_rules.ini'):
        lines.append(f'{name.replace(os.sep, "/")}: {_sha(os.path.join(game, name))}')
    try:
        with open(os.path.join(game, BUILD_STAMP), 'w', newline='\r\n') as f:
            f.write('\n'.join(lines) + '\n')
    except OSError:
        pass

def age_limit(game):
    """The highest age rating PARENTAL.LCK allows (12, 16 or 18); a missing or unreadable file allows 12."""
    try:
        return min(18, max(12, int(open(os.path.join(game, AGE_LOCK)).read().split()[0])))
    except (OSError, ValueError, IndexError):
        return 12

def age_check(game, r, setup=False):
    """Raises RulesError if the rules r ask for more than PARENTAL.LCK allows. setup: before age_init, which would
    write 18 for an installation that has never had a lock."""
    never_set = not os.path.exists(os.path.join(game, AGE_INIT)) and not os.path.exists(os.path.join(game, AGE_LOCK))
    limit = 18 if setup and never_set else age_limit(game)
    if r['age'] > limit:
        raise RulesError(f'[Parental] age_rating: this installation allows at most K{limit} for good '
                         f'({AGE_LOCK}); only a new installation allows a higher rating')

def age_init(game):
    """The setup: a new installation (or the first of 0.7.0 over an older one) allows K18 (PARENTAL.LCK = 18)."""
    marker = os.path.join(game, AGE_INIT)
    if os.path.exists(marker):
        return
    if not os.path.exists(os.path.join(game, AGE_LOCK)):
        open(os.path.join(game, AGE_LOCK), 'w').write('18 the highest age rating allowed in this installation\n')
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    open(marker, 'w').write('PARENTAL.LCK set up\n')

if __name__ == '__main__':
    target = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(HERE)
    try:
        on = install(target)
    except SetupUnfinished:
        raise SystemExit('The setup did not finish. Run Setup.bat first. Nothing was changed.')
    except RulesError as e:
        raise SystemExit(f'custom_rules.ini: {e}\nNothing was changed.')
    except Busy as e:
        raise SystemExit(f'{e}. Nothing was changed.')
    except OSError as e:
        raise SystemExit(f'Could not write the game\'s files ({e}). Close DOSBox-X and run this again. ' +
                         ('The change did not finish, so Start.bat will not start the game until it does.'
                          if os.path.exists(os.path.join(target, INSTALLING)) else 'Nothing was changed.'))
    print('Custom rules from custom_rules.ini are on. Restart the game (DOSBox-X) for them to take effect.' if on else
          'Custom rules from custom_rules.ini are set, but the game is in original mode: Fixes_On.bat turns them on.')
