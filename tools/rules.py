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
gives the start corner and home village, which home_village can change), 4 for a computer knight. The INI sections [Knight1]-[Knight4] are 0-3 and
[Black] is every computer-controlled knight (they wear black)."""
import sys, os, struct, configparser, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from patches import PATCHES, image_offset

SECTIONS = ['Knight1', 'Knight2', 'Knight3', 'Knight4', 'Black']
WEAPONS = {'long_sword': 0x16, 'broadsword': 0x17, 'claymore': 0x18, 'sword_of_sharpness': 0x19}
ARMOURS = {'padded': 0x1b, 'chain_mail': 0x1c, 'plate_mail': 0x1d, 'battle_armour': 0x1e}
MODES = {'permadeath': 0, 'reincarnation': 1, 'respawn': 2, 'invulnerable': 3}
VILLAGE = {'below_3': 0, 'below_max': 1, 'full': 2}
ITEMS = [('healing_potions', 0x00), ('gems_of_seeing', 0x02), ('rings_of_protection', 0x06),   # item table offsets
         ('talismans_of_the_wyrm', 0x08), ('scrolls_of_haste', 0x0a), ('scrolls_of_the_hawk', 0x0c),
         ('scrolls_of_acquisition', 0x0e), ('scrolls_of_the_wyrm', 0x10), ('scrolls_of_protection', 0x12)]
SHARPNESS_ITEM, KEYS, MOONSTONES = 0x04, 0x14, 0x16
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
DEFAULT_COLOURS = ['blue', 'orange', 'green', 'red', 'black']        # [Knight1]..[Knight4], [Black]
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
TABLE_SIZE = G_TARGET_MARGIN + 1
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
    (0x112e, '807c31037d0480443101', 'village'),        # home village druids
    (0x0add, '806c3101', 'lives_si'), (0x0aed, '806d3101', 'lives_di'),   # fight lost
    (0x0d03, '806c3101', 'lives_si'),                   # computer knight robbed by the dragon
    (0x0fff, '806c3102', 'lives_si'),                   # Guardian: two more
    (0x122f, '806c3101', 'lives_si'),                   # ratmen disease
    (0x08d4, '8b4420', 'colour_si'), (0xa417, '8b4420', 'colour_si'),   # map icons: mov ax,[si+20h]
    (0xa3cd, '8b4520', 'colour_di'),                    # map icon of the knight whose turn it is: mov ax,[di+20h]
    (0x0732, '3d15007506837d200075c63d16007506837d200175bb3d17007506837d200275b03d18007506837d200375a5', 'place'),
    (0xcc0f, '268b5e12268b4e10', 'sell'),               # item screen click: mov bx,es:[bp+12h] / mov cx,es:[bp+10h]
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
                 'keys': (0, 4), 'moonstones': (0, 4), **{name: (0, 9) for name, _ in ITEMS}}
RULES_BOUNDS = {'hawk_curse_chance': (0, 100), 'protection_curse_chance': (0, 100), 'max_gold': (0, 20000),
                'max_lives': (1, 99), 'moon_days': (1, 100), 'xp_per_stat': (1, 1000), 'weapon_damage': (0, 100),
                'armour_hp': (0, 100), 'xp_per_moon_phase': (0, 100), 'duel_win_xp': (0, 100),
                'ring_of_protection_hp': (0, 100), 'shop_price': (0, 127), 'temple_price': (0, 999),
                'healer_price': (0, 127), 'move_damage': (0, 100), 'max_daggers': (1, 99), 'frog_days': (0, 100),
                'irritation_after_visit': (0, 150), 'irritation_drop_per_day': (0, 127), 'chance': (0, 100),
                'treasure_gold': (0, 1000), 'donation': (1, 20000), 'monster_hp': (1, 999),
                'monster_damage': (0, 127), 'target_margin': (0, 200)}

def read_ini(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=(';',))
    cp.optionxform = str.lower
    try:
        if not cp.read(path, encoding='utf-8'):
            raise RulesError(f'{path} not found')
    except configparser.Error as e:
        raise RulesError(f'the file cannot be read: {e}')
    rb = RULES_BOUNDS
    r = {'knights': []}
    g = 'Rules'
    r['ratmen_disease'] = _get(cp, g, 'ratmen_disease', _onoff)
    r['hawk_curse'] = _get(cp, g, 'hawk_curse_chance', float, *rb['hawk_curse_chance'])
    r['protection_curse'] = _get(cp, g, 'protection_curse_chance', float, *rb['protection_curse_chance'])
    r['max_gold'] = _get(cp, g, 'max_gold', int, *rb['max_gold'])
    r['max_lives'] = _get(cp, g, 'max_lives', int, *rb['max_lives'])
    r['village_heal'] = _get(cp, g, 'village_heal', _choice(VILLAGE))
    r['village_any'] = _get(cp, g, 'village_heal_where', _choice({'home': 0, 'any': 1}))
    r['rest_heal'] = _get(cp, g, 'rest_heal', _choice({'none': 0, 'full': 1}))
    r['moon_days'] = _get(cp, g, 'moon_days', int, *rb['moon_days'])
    r['save_mode'] = _get(cp, g, 'save_mode', _choice(SAVE_MODES))
    r['fate'] = _get(cp, g, 'prevent_savescumming', _onoff)
    r['selling'] = _get(cp, g, 'merchant_selling', _onoff)
    r['xp_per_stat'] = [_get(cp, g, f'xp_per_stat_{n}_player{"s" if n > 1 else ""}', int, *rb['xp_per_stat'])
                        for n in (1, 2, 3, 4)]
    w = 'Weapons'
    r['weapon_damage'] = [_get(cp, w, name, int, *rb['weapon_damage']) for name in WEAPONS]
    a = 'Armour'
    r['armour_hp'] = [_get(cp, a, f'{name}_hp', int, *rb['armour_hp']) for name in ARMOURS]
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
    check_treasure(r)
    for sec in SECTIONS:
        if not cp.has_section(sec):
            raise RulesError(f'section [{sec}] is missing')
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
    known = {g: {'ratmen_disease', 'hawk_curse_chance', 'protection_curse_chance', 'max_gold', 'max_lives',
                 'village_heal', 'village_heal_where', 'rest_heal', 'moon_days', 'save_mode', 'prevent_savescumming',
                 'merchant_selling',
                 'xp_per_stat_1_player',
                 'xp_per_stat_2_players', 'xp_per_stat_3_players', 'xp_per_stat_4_players'},
             w: set(WEAPONS), a: {f'{name}_hp' for name in ARMOURS} | {'ring_of_protection_hp'},
             c: {name for name, _ in MOVES} | {'max_daggers'},
             p: {name for name, *_ in SHOP} | {f'temple_{name}' for name, _ in TEMPLE}
                | {'healer_full_heal', 'healer_life_point'},
             m: {'frog_days', 'irritation_after_visit', 'irritation_drop_per_day'} | {f'{n}_chance' for n, _ in MATH},
             t: {f'lair_{name}' for name in LAIR_TYPES} | {'gold_min', 'gold_max', 'dragon_hoard'} | set(TREASURE_ITEMS),
             y: {f'band{n}_up_to' for n in range(1, MYTHRAL_BANDS)}
                | {f'band{n}_chance' for n in range(1, MYTHRAL_BANDS + 1)},
             mo: monster_keys,
             'Practice': {f'key{k}' for k in PRACTICE_KEYS} | {'team_knight_hits', 'coop_knight_hits', 'coop_dagger_hits', 'monster_target',
                            'target_switch_margin'},
             **{sec: knight_keys | {'home_village'} for sec in SECTIONS[:-1]},
             b: knight_keys | {'xp_per_moon_phase', 'math_visit_per_moon_phase', 'duel_win_xp'}}
    for sec in cp.sections():                            # a misspelt name would otherwise be ignored silently
        if sec not in known:
            raise RulesError(f'unknown section [{sec}]')
        for key in cp.options(sec):
            if key not in known[sec]:
                raise RulesError(f'[{sec}] {key}: unknown setting')
    return r

# --- the SAVEHOOK.COM table -------------------------------------------------------------------------------------------
DEFAULT_KNIGHT = dict(strength=1, constitution=1, endurance=1, lives=5, gold=10, experience=0, daggers=10, hp_bonus=0,
                      weapon=0x16, armour=0x1b, keys=0, moonstones=0, mode=0, colour=None,
                      **{name: 0 for name, _ in ITEMS})

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
        items[MOONSTONES] = (1 << k['moonstones']) - 1     # bits 1, 2, 4, 8: one per moon phase
        t[o + 0x10:o + 0x28] = items
    hp = r['armour_hp'] if r else [0, 10, 20, 30]
    struct.pack_into('<4hh', t, G_ARMOUR_HP, *hp, r['weapon_damage'][0] if r else 0)
    t[G_REST] = r['rest_heal'] if r else 0
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
    t[G_HOARD] = r['hoard'] if r else HOARD_MODES['grows']
    for n, choice in enumerate(r['practice'] if r else PRACTICE_DEFAULTS):
        t[G_PRACTICE + n] = 0xff if choice == 'black_knight' else choice - 1
    t[G_PRACTICE_FLAGS] = r['practice_flags'] if r else 0
    t[G_TARGET_MARGIN] = r['target_margin'] if r else 20
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
        new, _ = hook_bytes(where, old, kind)
        out.append((where, bytes.fromhex(old), new))
    for site in (0xb4cd, 0xb4d4, 0xba11, 0xba18, 0xcef6, 0xd060, 0xd068):   # gold cap 150: dice, Math, loot, sale
        imm(site, 2, r['max_gold'])
    m = r['max_lives']                                   # life cap 5: Stonehenge, healer, potion, computer potion use
    imm(0x10b1, 1, m); out.append((0x10b2, b'\x74', b'\x7d'))     # cmp 5 / je -> jge (a start above the cap)
    imm(0xbce4, 1, m); out.append((0xbce5, b'\x74', b'\x7d'))
    imm(0xccbc, 1, m + 1); imm(0xccc2, 1, m); imm(0xada6, 1, m)
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

def install(game):
    """Applies custom_rules.ini (made from custom_rules-default.ini if missing): _fixes/rules/MAIN.EXE, SAVEHOOK.COM,
    CUSTOM_RULES.FLG,
    and MAIN.EXE unless the game is in original mode. Raises RulesError (nothing written) for a bad value."""
    ini = os.path.join(game, 'custom_rules.ini')
    if not os.path.exists(ini):
        shutil.copyfile(os.path.join(game, 'custom_rules-default.ini'), ini)
    exe, hook = build(game, read_ini(ini))
    from make_savehook import make_savehook
    os.makedirs(os.path.join(game, '_fixes', 'rules'), exist_ok=True)
    # The save mode is in SAVEHOOK.COM's table, so Custom_rules_off.bat puts the normal SAVEHOOK.COM back from here
    for name, data in ((os.path.join('_fixes', 'rules', 'MAIN.EXE'), exe), ('SAVEHOOK.COM', hook),
                       (os.path.join('_fixes', 'fixed', 'SAVEHOOK.COM'), make_savehook()),
                       ('CUSTOM_RULES.FLG', b'custom rules\r\n')):
        open(os.path.join(game, name), 'wb').write(data)
    if os.path.exists(os.path.join(game, 'ORIGINAL.FLG')):
        return False
    open(os.path.join(game, 'MAIN.EXE'), 'wb').write(exe)
    return True

if __name__ == '__main__':
    try:
        on = install(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(HERE))
    except RulesError as e:
        raise SystemExit(f'custom_rules.ini: {e}\nNothing was changed.')
    print('Custom rules from custom_rules.ini are on. Restart the game (DOSBox-X) for them to take effect.' if on else
          'Custom rules from custom_rules.ini are set, but the game is in original mode: Fixes_On.bat turns them on.')
