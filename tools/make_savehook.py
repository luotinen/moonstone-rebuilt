"""Build SAVEHOOK.COM, the resident helper for D6 and D7 (DOSBox-X save state right before every fight and at the
start of every human player's turn on the map) and for K16 (code that does not fit in MAIN.EXE).

DOSBox-X has no way for a DOS program to ask for a save state, but its autosave can use a slot (or a slot range) per
running program, for up to 9 programs ("autosave = 1 -1 TURN1:91 ... TURN4:94 FIGHT1:96 ... FIGHT5:100": check every
second, never save for other programs, save into slot 96 while the program is FIGHT1). DOSBox-X takes the program
name from the memory block of the current PSP, and only re-reads it when a program starts or ends. SAVEHOOK numbers
the names in turn itself (number_name, the counters in SAVEHOOK.SLT): with one range per name (PREFIGHT:96-100, as
before) a wait that spanned two checks filled two slots of the range.

SAVEHOOK.COM installs four interrupt handlers and stays resident. The patches in patches.py replace an instruction in
MAIN.EXE with an interrupt:
* D6, int 66h: the first instruction of the fight routine (1000:0307, mov word [7841h],0); every fight starts there.
* D7, int 65h: the instruction after the turn set-up (1000:a63f, mov si,[77e8h], the record of the knight whose turn
  begins); only for knights not controlled by the computer (record +20h <> 4), so computer turns do not pause.
The handler:
1. does the replaced instruction,
2. renames MAIN's memory block to the next of FIGHT1-FIGHT5 or TURN1-TURN4 and runs a child program, so DOSBox-X
   re-reads the name: SAVEHOOK.RUN, five bytes that exit at once (the installer writes it). It used to be SAVEHOOK.COM
   itself, but DOSBox-X starts a .COM only with its file size free (dos_execute.cpp), and once SAVEHOOK.COM outgrew
   the free memory left beside MAIN.EXE (D20's knight pieces took 9 KB, 1 November) the child did not start, the
   name never reached DOSBox-X and no automatic save was made,
3. waits until DOSBox-X's once-a-second autosave check has saved the state: the save's file (C:\SAVE\91.SAV for
   TURN1 ... C:\SAVE\100.SAV for FIGHT5, as the conf's slots; C: is the game folder) gets a new date and time,
   read once a BIOS tick, or at most WAIT_TICKS ticks (about 1.1 s; also where the file cannot be seen). Emulation
   stops while DOSBox-X writes a save, so the game cannot see the pause (its clocks, the CMOS clock included, follow
   emulated time); ending at the save keeps a second check from saving again into the same slot,
4. restores the old name and runs the child again, so the name is MAIN again.
K16, int 62h: the weapon pick on the duel loot screen (1000:ce99) moved only the weapon number. Taking the Sword of
Sharpness (weapon 19h) left the sword item with the loser, so both knights had the sword. The handler also moves the
item (item table +4) when the weapon is 19h, then does the replaced compare and store (the better weapon is kept).
D11, int 63h (the rules handler): practice against the computer with one player chosen; see rules_code.
Rules, int 63h: the custom game rules from custom_rules.ini (rules.py; only when they are on, CUSTOM_RULES.FLG).
rules.py writes the settings table into SAVEHOOK.COM and patches MAIN.EXE; see rules_code below. Without custom
rules the table holds the normal game's values and the normal MAIN.EXE never calls int 63h.
Save modes (custom rules): the table's save mode turns the automatic saves off (manual_only, none). In autosave_only
and none, a manual save cannot be stopped (DOSBox-X takes it), but loading one is caught: every turn, fight and reward
roll (checkpoint) compares a token in memory with the one in SAVEHOOK.CHK and writes a new one to both. A loaded
manual save has an older token in memory, so the game stops there under the name LOADAUTO or NOSAVES (DOSBox-X shows
it in the title bar). A loaded automatic save resumes in the wait below and writes its own token to the file first.

MAIN.EXE may use all free memory, so SAVEHOOK keeps a small block of its own (RESERVE_PARAS) and frees it for the
child and the speed change's shell.
Usage: python -I tools/make_savehook.py <output SAVEHOOK.COM>   (the normal game; rules.py builds it with rules)"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import (G_CHOP_CHEESE, G_TD, G_TD_WINDOW, G_TD_FAST, G_TD_STAGGER, G_TD_PURPLE, G_TD_BLACK, G_TD_PAUSE, G_COMPUTER, G_BK_AI, G_BK_HEAL, G_TRADE_IN, G_HORSE_SELL, G_BUY, HOOKS, FATE_HOOKS, FATE_STREAMS, GLOW_SITES, SECTIONS, SECTION_SIZE, MODES, VILLAGE, SAVE_MODES, SPAWNS,
                   G_ARMOUR_HP, G_SWORD, G_REST, G_VILLAGE, G_MAX_LIVES, G_RING, G_COLOURS, G_HOMES, G_VILLAGE_ANY,
                   G_SAVE_MODE, G_FATE, G_SELLING, G_MAX_GOLD, G_SELL, G_HOARD, HOARD_MODES, MAX_HP, hook_bytes,
                   G_PRACTICE, G_PRACTICE_FLAGS, G_TARGET_MARGIN, COOP_KNIGHT_HITS, TEAM_KNIGHT_HITS,
                   COOP_DAGGER_HITS, TARGET_FIRST, G_HIT_REST, G_EXPLOIT_FIXES, KEEP_DRAGON_TARGET,
                   NO_EXTRA_TURN, POTION_LIFE, G_CYCLES, G_DEATHS, DEATHS, G_DRAGON_DEBUG, G_INPUT_BUFFER,
                   G_REST_FIXED, G_REST_ENDURANCE, REST_HEAL, G_CHEATS, G_ANTICHEESE, G_CATCHUP, G_AGE, G_FIGHT_CYCLES,
                   G_HASTE_CURSE, G_WYRM_CURSE, G_INPUT_CHORD, G_INPUT_LOG, G_INPUT_RECENT, G_COOP_LAIRS, G_COOP_EXTRA, COOP_MODES,
                   G_ENCHANT, G_ENCH_CHANCE, G_ARMOUR_MOVE, G_ARM_ENCH, G_ARM_CHANCE, G_DISEASE,
                   G_HORSES, G_HORSE_CHANCE, G_HORSE_PRICE, G_HORSE_MOVE, G_HORSE_SOFT, G_HORSE_HARD, G_HORSE_TEXT, HORSE_TEXT_SIZE,
                   table as rules_default_table)
from patches import (SOUND_RATES, SOUND_LAST_ID, SOUND_SLICES, SOUND_RATE_SITE, OWN_SOUND_IDS, SOUND_PLAY_SITE,
                     AMIGA_FIRST_KEY, AMIGA_PER_PRESET, amiga_program)

FIGHT_INT, TURN_INT, LOOT_INT, RULES_INT = 0x66, 0x65, 0x62, 0x63   # MAIN.EXE uses none of these
KEY_INT = 0x64                                        # D24: from the game's keyboard interrupt (nor this)
SHARPNESS = 0x19                         # weapon number of the Sword of Sharpness
FIGHT_NAME, FIGHT_SLOTS = b'FIGHT', 5     # program names FIGHT1-FIGHT5 and TURN1-TURN4, one autosave slot each
TURN_NAME, TURN_SLOTS = b'TURN', 4       # (moonstone-dosbox-x.conf: FIGHT1:96 ... FIGHT5:100, TURN1:91 ... TURN4:94)
MODE_REINCARNATION, MODE_RESPAWN, MODE_INVULNERABLE = MODES['reincarnation'], MODES['respawn'], MODES['invulnerable']
VILLAGE_FULL = VILLAGE['full']
COMPUTER = 4                             # knight record +20h: control type 4 = computer
AUTO_ONLY, MANUAL_ONLY, NO_SAVES = SAVE_MODES['autosave_only'], SAVE_MODES['manual_only'], SAVE_MODES['none']
CHK_PATH = b'C:\\SAVEHOOK.CHK\0'        # the save check's token file (save states do not restore files)
SLOT_PATH = b'C:\\SAVEHOOK.SLT\0'       # the next autosave number of each kind (a file, so loading a state keeps it)
AMIGA_PATH = b'C:\\AMIGASND.FLG\0'      # D65: Start.bat makes it when music.conf is the Amiga sound profile
AUTO_NAME, NONE_NAME = b'LOADAUTO', b'NOSAVES'   # program names shown when a forbidden manual save was loaded
RANDOM_STATE = 0xe22f                    # DS:E22F, the game's random number state (1000:BF62)
CHOSEN_PLAYERS = 0x0940                  # DS:0940: the number of players chosen, kept during practice (1000:00EB)
# D11 (patches.py, in the fixed MAIN.EXE, also without custom rules): practice set-up sites, (return address, job)
PRACTICE_HOOKS = [(0x011f, 'practice_si'), (0x2033, 'practice_di'),
                  # D12: 3-4 knights in practice
                  (0x203d, 'practice_add'), (0x0371, 'practice_frame'), (0x4275, 'practice_hit'), (0x83f0, 'joy_a'),
                  (0x8422, 'joy_b'), (0x0a91, 'input_pick'), (0x014d, 'practice_end'),
                  # D13: four colours
                  (0x9afd, 'draw'), (0x9b09, 'draw'), (0x5edf, 'recolour'), (0x5b40, 'dac_write'),
                  (0x5baf, 'fade_in'), (0x5c23, 'fade_out'),
                  # K18: the dragon's hoard is cleared at a new game
                  (0x1dc0, 'hoard_clear'), (0x0d25, 'hoard_win'),
                  # K36, K37: the pitch of each sound id, and the ids that are one part of a sample
                  (SOUND_RATE_SITE + 2, 'sound_rate'),
                  # D65: the Amiga version's effects from a SoundFont
                  (SOUND_PLAY_SITE + 2, 'sound_play'),
                  # D14: the menu's keys and the practice set-up
                  (0x129b, 'menu_keys'), (0x0144, 'practice_init'),
                  # D15: every monster's opponent
                  (0x025e, 'pause'), (0x98ff, 'update'),
                  # K6: hit recovery of the dragon and the Guardian; K20: the moon pictures
                  (0x3863, 'dragon_rest'), (0x4f6c, 'guardian_rest'), (0x9055, 'moon_picture'),
                  # K21: the dragon keeps its target
                  (0xa80f, 'dragon_target'),
                  # K22: no extra action at the end of a turn
                  (0xa5ba, 'action_done'),
                  # D21: dragon debug mode (custom rules): the keys 1-4 pick the dragon's target, Enter starts its fight
                  (0xa5bd, 'dragon_debug'),
                  # D22: gore off: the troll's and the Balok's crush become the plain death
                  (0x43b2, 'crush_troll'), (0x372b, 'crush_balok'),
                  # D23: faster drawing: the sprite converter
                  (0x5edc, 'convert'),
                  # D24: responsive controls: the key test, a knight's input
                  (0x828d, 'key_check'), (0x3f18, 'input'),
                  # D25: knights turn in place and walk up close
                  (0x3f85, 'face_right'), (0x3f94, 'face_left'), (0x3fae, 'walk_block'), (0x40ae, 'fire_facing'),
                  # K23: the healing potion's life
                  (0xccb8, 'potion_life'),
                  # D17: the fight's end, where the map's CPU speed comes back
                  (0x0ac0, 'fight_end'),
                  # K25: the instant kill's knight
                  (0x0ab5, 'instant_kill'), (0x3af5, 'dragon_eat'), (0x3afb, 'dragon_ate'),
                  # K25: a knight down in co-op stays down; the troll's knight
                  (0x3ed2, 'knight_down'), (0x55fb, 'troll_target'),
                  # K26: the troll's depth, where its swing hits
                  (0x5710, 'troll_depth'), (0x573d, 'troll_back'),
                  # K25: the mudman's knight while it holds one
                  (0x5300, 'mud_target'), (0x559e, 'mud_grab'), (0x54dd, 'mud_pull'),
                  # K28: the Balok's knight while it shakes one
                  (0x35b1, 'balok_target'), (0x37a9, 'balok_grab'),
                  # K28: the trogg that spears a fallen knight
                  (0x2f92, 'trogg_impale'),
                  # D20: a knight hit again while it falls
                  (0x2d60, 'death'), (0x3e5b, 'dagger_near'), (0x415b, 'strike_on'), (0x4359, 'spear_on'),
                  # D19: the Black Knights of a practice with 2-4 knights (or the B key)
                  (0x2826, 'spawn_init'), (0x0245, 'top_up'), (0xa14e, 'hit_pair'),
                  # D19: who threw a dagger
                  (0x3e3d, 'dagger_thrower'), (0x3e42, 'dagger_owner'), (0x44c4, 'dagger_damage'),
                  # D19: Black Knights do not block each other's way
                  (0xa00a, 'bk_collide'),
                  # D19: when a computer knight throws a dagger
                  (0x4d47, 'ck_throw'),
                  # D26: a new turn on the map waits for the keys to be let go
                  (0xa538, 'map_keys'),
                  # K33: limits and checks
                  (0xa67d, 'game_over'), (0xce77, 'loot_hp'), (0x0baf, 'auto_loot_hp'), (0x2cfd, 'path_none'),
                  (0xbc30, 'mythral_table')]
# D19: Black Knights against 2-4 knights: the fight is a lair fight (its set-up, counts and end) whose monsters are
# computer knights (+35h = 8, handler 1000:4B85) in the monster slots, as many as the knights, each a copy of one
# the fight borrows the trolls' own set-up (1000:2277; not a lair: the lair records change with every game) and its
# spawns (22DE -> 27FA), which the Black Knights replace
BK_CHOICE, B_SCAN, BK_SET_UP = 13, 0x30, 0x2277
DD_TOP, DD_BOTTOM, DD_NEAR, DD_GAP = 21, 146, 40, 20   # D46: a knight's depth range (CheckBorder), near an edge, the long fire's gap
TD_OWN_ATTACK = 30                                   # D46: ticks after its own attack's start a computer knight cannot defend
P_CHOICE, P_SCAN = 14, 0x19                          # D46: the practice Purple Knight, who only defends
KNOCKBACK = 0x7818                  # the blows' knockback table (1000:43ED, 56A6); [782Eh] = 0 in a new session
COMPUTER_TYPE, KNIGHT_BANK, STANDING = 8, 0x8933, 0x15e4
BK_ITEMS = 0x7666                   # their item table: monster slot 19 + 20h (the fight's set-up clears the slots)
BK_X, BK_FACE = (-40, 360, -40, 360), (1, 3, 1, 3)   # walk in from both sides (the registration, 2998, picks the depth)
BLACK_SITES = (0x4878, 0x487d, 0x4882)               # fight palette words of +20h = 4 (computer), for entries 41-43
DUMMY_WHITE = (0x0fff, 0x0ddd, 0x0aaa)               # D46: the practice knight (P key): a white highlight, light greys
STRONG_BLACK = (0x0222, 0x0111, 0x0000)              # the B key's knights: 8/4/0 of 63 (40/20/0 looked grey)
B_DAGGERS = 10                                       # the B key's knights' daggers (each throw gives one back)
# D19: a computer knight (1000:4D45) throws only from within x 10-300, with none of its own daggers in the air, and
# then at one of THROW_CHANCE + 1 decisions (the rest it walks on to its knight)
THROW_X_MIN, THROW_X_MAX, THROW_CHANCE = 10, 300, 3
BK_HP = 30                                           # a Black Knight's HP when its knight's record has no max HP
# the knights' hit reactions by the striker's attack (+28h), one table for all knights (1000:17C1): the trolls'
# set-up (2280) makes the up and down thrusts' (+0Eh, +10h) the club's throw through the air (31D0)
REACTIONS = 0x69c2
REACTION_DEFAULTS = ((0x0e, 0x0c90), (0x10, 0x1202))
BALOK_TYPE = 0x18                                    # K28: the Balok (+35h; handler 1000:35A5)
SPEAR_TROGG = 0x10                                   # K28: the trogg with the spear (+35h; handler 1000:2DEB)
# D20: new deaths for a knight hit again while it falls; their scripts (death_frames.py) are in MAIN.EXE's data
# segment from D20_BASE, one per D20_SLOT bytes: the bottom of the stack segment (SS = DS + F46h, SP 1000h), which
# no save state has ever touched
D20_BASE, D20_SLOT = 0xf480, 0x110
D20_NAMES = ('split', 'dagger_front', 'dagger_back', 'thrust_front', 'thrust_back', 'back',
             'dagger_waist_front', 'dagger_waist_back',   # dagger_front/back: at the head's height
             'up_forward')   # reserved, empty: a death for the up and forward strike (a kick?), TODO
D20_SIZE = {name: 0x150 if name == 'split' else D20_SLOT for name in D20_NAMES}   # the split is the longest
D20 = {name: D20_BASE + sum(D20_SIZE[n] for n in D20_NAMES[:k]) for k, name in enumerate(D20_NAMES)}
D20_END = D20_BASE + sum(D20_SIZE.values())          # FE50h
# D38: horses. The descriptors and hover texts of the four shop slots go in D20's reserved empty slot
HORSE_AREA, HORSE_WINDOW = D20['up_forward'], 19      # each slot's descriptor (19 bytes for its alignment, as D37), then the texts
HORSE_FIELD, HORSE_ICON_Y, HORSE_X = 0x36, 181, (30, 60, 91, 121)   # BuyGoods' field value; slots' y, x on the goods panel
HORSE_PANEL_WINDOW = HORSE_AREA + 4 * HORSE_WINDOW + 4 * HORSE_TEXT_SIZE   # D40: the knight's own horse: descriptor, text
HORSE_PANEL_TEXT = HORSE_PANEL_WINDOW + HORSE_WINDOW
HORSE_PANEL_X, HORSE_PANEL_Y = 130, 92               # right of the sword (longest ends at x 128; daggers end at y 90, keys start at y 111)
HORSE_IDLE = 18                                       # BIOS ticks (about a second) standing before the knight shows on foot again
HORSE_FRAME_SHOP, HORSE_MAP_BASE = 50, 42             # first new frame in KH.CEL; ax for horse 1, colour 0 at A3CD (MH.C frame 47 on)
# D22 (gore off): the hit marker's script (death_frames.py writes it), its object type (the game's hit effect, whose
# handler 1000:3EB9 runs the script until its 9Eh), BIOS ticks between two markers; the crush (1000:16E2) becomes
# the slump (1000:130E without its mirror toggle) and the lying knight
MARKER_SCRIPT, MARKER_SIZE, MARKER_TYPE, MARKER_GAP = 0xfe60, 0x40, 0x14, 3
TURN_MOVES_SITE = 0xa568                             # cheat codes: the map loop's hook (turn_moves), to come back to
# the hooks that run most often (every piece drawn: draw, recolour; every object: update; every hit test: hit_pair;
# every palette write: dac_write): first in the table that rules_handler searches
HOT = ('draw', 'convert', 'recolour', 'update', 'hit_pair', 'key_check', 'dac_write', 'bk_collide')
# D24: a key release this soon after its press (BIOS ticks; a frame is 2) waits, so every press is seen once; a fire
# press this recent when a knight's move ends is its next attack (input_buffer); the players' keys as 1000:83C0
# reads them (fire, then up 8, down 4, left 2, right 1): player 1 Enter and the arrows, player 2 Tab and W S A D (D9)
KEY_HOLD, BUF_TICKS = 3, 8
# D33 co-op lairs: the map's list of choices (1000:06B5: 5 entries of 8 bytes, [+0] the object, [+4] its type),
# the type of "Lair with" a knight, the free one after the list's last, and the text before the knight's name
CHOICES, CHOICE_SIZE, CHOICE_COUNT, COOP_TYPE, COMPUTER_TURN = 0x043c, 8, 5, 0x40, 0xcca0
COOP_TEXT = b'Lair with '
BATTLE_TYPE = 0x41                                   # "Battle with ...": the knights to fight in a list of their own
BATTLE_TEXT = b'Battle with ...'
TOGETHER_TEXT = b'Lair together (2 knights)'          # 3-4 knights; the digit at TOGETHER_DIGIT set as the list is made
TOGETHER_DIGIT = TOGETHER_TEXT.index(b'2')
DISPLAY_STACK = 0xb000                               # DisplayStack: the list of choices drawn and one taken
COOP_PARTNERS = 3                                    # a lair with up to 3 other players' knights
LAIR_XS = (220, 280, 190)                            # where the partners stand as the fight begins (facing left)
COOP_SAVE = (0x02, 0x04, 0x06, 0x08, 0x18)           # a partner's words kept over the fight: x, height, depth,
                                                     # facing and input (+8, +9), bank (its daggers are spent)
LAIR_ITEMS, KEYS_ITEM, MOONSTONES_ITEM = 24, 0x14, 0x16   # a lair's items (as an item table); the unique ones
ORDER_OPT_RET = 0xb171                                # OrderOpt's ret: a line's text is done
DIR_CHORD_MAX, DIR_AFTER_FIRE = 5, 2                 # D39: ticks: a direction held longer is walking; a direction pressed this soon after fire joins it
ILOG_MAX = 512                                       # D24: input_log entries a fight keeps (6 bytes each)
ILOG_PATH = b'C:\\INPUT.LOG\0'
ILOG_KEY_DOWN, ILOG_KEY_UP, ILOG_READ, ILOG_MOVE = 1, 2, 3, 4   # entry kinds; tools/input_log.py reads them
ILOG_DEFENCE, ILOG_STAGGER, ILOG_ATTACK = 5, 6, 7    # D46: a knight struck by a knight (defended or not), a stagger, an attack's start

# cheat codes (custom rules cheat_codes = yes): typed in the item screen, a fight or on the map; each is
# (name, context, id, scan codes). The ids: item codes 1-39, fight codes 40-59, map codes 60-79
CHEAT_LETTERS = {'A': 30, 'B': 48, 'C': 46, 'D': 32, 'E': 18, 'F': 33, 'G': 34, 'H': 35, 'I': 23, 'J': 36, 'K': 37, 'L': 38, 'M': 50, 'N': 49, 'O': 24, 'P': 25, 'Q': 16, 'R': 19, 'S': 31, 'T': 20, 'U': 22, 'V': 47, 'W': 17, 'X': 45, 'Y': 21, 'Z': 44}
CHEAT_ITEMS, CHEAT_FIGHT, CHEAT_MAP = 1, 2, 4
def _scans(name):
    if name == 'KONAMI':                                 # up up down down left right left right B A
        return [0x48, 0x48, 0x50, 0x50, 0x4b, 0x4d, 0x4b, 0x4d, 0x30, 0x1e]
    return [CHEAT_LETTERS[c] for c in name]
CHEAT_ITEM_CODES = ['IDKFA', 'KONAMI', 'HESOYAM', 'ROSEBUD', 'KLAPAUCIUS', 'MOTHERLODE', 'POINTTAKEN', 'TINMAN', 'SIRLOIN', 'HEADSROLL', 'WYRMPROOF', 'MINEALLMINE', 'KNIGHTRIDER', 'HASTALAVISTA', 'SPECIALDELIVERY', 'NOTTODAY', 'FLYBYKNIGHT', 'KEYMASTER', 'FULLMOONEY', 'DARKSIDE', 'COMINGSOON', 'GOINGGONE', 'FLESHWOUND', 'PEEPINGTOM', 'LIVEANDLEARN', 'SIRLIFTSALOT', 'BUILTTOLAST', 'AREWETHEREYET', 'DANUBLESS', 'PUTARINGONIT', 'MOONMAX']
CHEAT_FIGHT_CODES = ['ROCKETMAN', 'JUSTFLESHWOUND', 'THERECANBEONLYONE', 'FAIRFIGHT', 'YOUANDWHATARMY', 'FORE', 'IDDQD', 'ABACABB', 'FINISHHIM', 'LUNAR', 'MINEFIELD', 'DARTS', 'DAGGERFALL', 'LIGHTSABER', 'BEATEMUP', 'GUNSHOT']
CHEAT_MAP_CODES = ['WEPL', 'MOONWALK', 'HOMESICK', 'ONEMORETURN', 'HEREBEDRAGONS', 'DRAGONSLAYER', 'FROGPRINCE', 'BACKFORSECONDS', 'BLACKDEATH', 'SIRWALKSALOT', 'IDROPPEDMYKEY', 'SIRPICKSALOT']
FIGHT_ALIASES = {}                                    # D56: other spellings accepted, as the fight code they name
FIGHT_NOT_IN_FIGHT = ('DAGGERFALL', 'BEATEMUP')               # fight codes typed only in the first menu or on the map
# monster codes (typed in the first menu): that fight, player 1 one of its monsters: (type, lair of the practice)
MONSTER_CODES = ['DIRTYRAT', 'CLUBMEMBER', 'JUMPSCARE', 'TROGLIFE', 'SWAMPTHING']
TROGG_ANY = 0xfe                                      # mon_ctl: any trogg (types 0Ch, 0Eh, 10h)
MONSTER_ALIASES = {'TROGGLIFE': 'TROGLIFE'}           # also accepted, as the code they name
MONSTER_TYPES = {'DIRTYRAT': 0x12, 'CLUBMEMBER': 0x20, 'JUMPSCARE': 0x18, 'TROGLIFE': TROGG_ANY, 'SWAMPTHING': 0x02}
MONSTER_LAIRS = {'DIRTYRAT': 0, 'CLUBMEMBER': 17, 'JUMPSCARE': 7, 'SWAMPTHING': 12}   # as practice keys 1, 9, 7, 8
TROGG_LAIRS = (9, 1, 19)                              # TROGLIFE, one at random: keys 3, 4, 6 (wasteland, axe, spear)
LAIR_CHOICE = 0x40                                    # practice choice 40h + n: lair n itself (the monster codes)
BALOK_HOP_X, BALOK_HOP_Z = 40, 20                    # JUMPSCARE: a hop's length in x and depth
BALOK_REACH_X, BALOK_REACH_Z = 20, 14                # ... and how near a knight it comes down on is crushed
BALOK_JUMP_X, BALOK_JUMP_Z = 100, 30                 # ... its big jump (the secondary button, no knight to grab)
BALOK_GRAB_X, BALOK_GRAB_Z = 120, 12                 # ... a knight in front this near is grabbed (the AI's 80-120)
GUARDIAN_TYPE, KEY_TABLE = 0x04, 0x81e3                # the Guardian (+35h); MAIN's key table (cs:81E3h + scan)
CHEATS = ([(n, CHEAT_ITEMS, 1 + i, _scans(n)) for i, n in enumerate(CHEAT_ITEM_CODES)] +
          [(n, (CHEAT_MAP | 8) if n in FIGHT_NOT_IN_FIGHT else (CHEAT_FIGHT | CHEAT_MAP | 8), 40 + i, _scans(n))
           for i, n in enumerate(CHEAT_FIGHT_CODES)] +
          [(a_, CHEAT_MAP | 8, 40 + CHEAT_FIGHT_CODES.index(n), _scans(a_)) for a_, n in FIGHT_ALIASES.items()] +
          [(n, CHEAT_MAP, 60 + i, _scans(n)) for i, n in enumerate(CHEAT_MAP_CODES)] +
          [('HOTSTUFF', 8, 80, _scans('HOTSTUFF')), ('TOOEASY', 8, 81, _scans('TOOEASY')),
           ('TOOHARD', 8, 82, _scans('TOOHARD')), ('JUSTRIGHT', 8, 83, _scans('JUSTRIGHT'))] +
          [(n, 8, 90 + i, _scans(n)) for i, n in enumerate(MONSTER_CODES + list(MONSTER_ALIASES))])
CHEAT_ID = {n: i for n, _, i, _ in CHEATS}
CHEAT_TIMEOUT = 24                                   # BIOS ticks (1.3 s) between two keys of a code
# fight flags (cheat_flags)
CF_ROCKET, CF_FLESH, CF_ONLYONE, CF_FORE, CF_IDDQD, CF_ABACABB, CF_FINISH, CF_LUNAR = 1, 2, 4, 8, 16, 32, 64, 128
# D48: the new fight codes' flags (cheat_flags2); each lasts one fight
F2_DARTS, F2_SABER, F2_GUNSHOT = 1, 2, 4
# D64 GUNSHOT: every knight's dagger throw (move 6) is a musket shot. The shot's script (GUN_SHOT) skips the throw's
# 0.44 s wind-up: the bang (sound GUN_BANG, the whip's crack) and then the throw's last frame (DS:0E4A: the spawn, the
# arm forward, D63's empty hand) without the grunt. The ball (KN3.OB frame BALL_PIC, the last piece death_frames.py
# appends: BALL_W x 4, the ball at its right end, the rest clear) flies BALL_STEP a tick (the dagger 20). Its hit
# points (BALL_POINTS) run back along the whole frame, so the hit test covers the path since the last frame and a
# fast ball cannot pass through a target. Its first frame (where it leaves the hand) is not a weapon, so the points
# behind it never reach the shooter. A hit takes all of the target's HP. The scripts and points are written into a
# free part of MAIN's data at each shot (GUN_AREA: KEY_TEXT's, used only on the map and the item screen, after the
# hit marker's script)
GUN_BANG, GUN_JUMP, GUN_NO_DAGGER = 172, 0x0e4a, 0x0c74   # the bang; the throw's last frame; its no-dagger branch
BALL_BANK, BALL_PIC, BALL_W, BALL_STEP = 0x08, 92, 64, 60
BALL_FIRST, BALL_FIRST_DX, BALL_DX, BALL_DY = 5, 20, 15, 7   # as the dagger's first frame (move 5), the ball's dx
BALL_POINTS = tuple((x, 1 + (x // 4) % 2) for x in range(0, BALL_W, 4)) + ((BALL_W - 1, 1),)
# D52: the practice score. A practice fight's kind (score_sig): the practice's choice (these SAVEHOOK bytes) and for
# each knight record in the fight 10h + its colour slot (a human's), 20h + it (the computer's), FFh (not in it). Up to
# SCORE_KINDS kinds keep their wins (a computer side: [monsters, players]; else one a knight record); when a
# practice fight is of the previous one's kind its score shows at the top centre (in the background page, after
# the knights' colours are seen in their drawing or SCORE_WAIT ticks), in the knights' own colours (their pixel 7
# as drawn: the KN look's 7, the HE look's 10, or moved). Select Knight (a new campaign) clears them all
SCORE_SIG_LABELS = ('monster', 'teams', 'multi', 'coop', 'bk', 'dummy', 'dragon_ctl', 'mon_ctl')
SCORE_COMPUTER = (0, 3, 4, 5, 6, 7)                  # sig bytes that make a computer side: monster, coop, bk, dummy, dragon, mon_ctl
SCORE_KINDS, SCORE_SIG, SCORE_ENTRY = 8, 12, 16      # an entry: the sig, then four counts
SCORE_Y, SCORE_WAIT, SCORE_SHADOW, SCORE_WHITE, SCORE_MAX = 2, 54, 5, 1, 99
SCORE_FONT = ((7, 5, 5, 5, 7), (2, 6, 2, 2, 7), (7, 1, 7, 4, 7), (7, 1, 7, 1, 7), (5, 5, 7, 1, 1), (7, 4, 7, 1, 7),
              (7, 4, 7, 5, 7), (7, 1, 1, 1, 1), (7, 5, 7, 5, 7), (7, 5, 7, 1, 7), (0, 0, 7, 0, 0))   # 3 x 5: 0-9, the dash (10)
SCORE_SPACE = 11                                     # a gap of 4 pixels
# D54 BEATEMUP (first menu or map, the next fight): HP bars at the top, below the score's line when the score shows
# (BARS_Y_SCORE, else BARS_Y), BARS_H high, side by side over BARS_X..+BARS_SPAN with BARS_GAP between, drawn into
# the background page when one changes: the computer's side (every monster and computer knight, the dragon, and
# those still to come at the largest HP seen) in BARS_YELLOW, then each human's knight (HP of max HP, +3Ch) in its
# colour as drawn (D52), or with teams (D12) the two teams' sums in their first knights' colours. Empty: black
BARS_Y, BARS_Y_SCORE, BARS_H, BARS_X, BARS_SPAN, BARS_GAP, BARS_MAX = 15, 15, 4, 10, 300, 6, 5   # D56: always below the score's line
# D56: the score's box (the background under it, kept at its first drawing so it can be drawn again when a fight's
# winner is known); the dragon's wins in the fight palette's reddest entry, the Guardian's in its most turquoise
SCORE_BOX_X, SCORE_BOX_W, SCORE_BOX_H = 104, 112, 11
GUARDIAN_CHOICE, FIGHT_PALETTE, GAME_ENDING = 11, 0x7a80, 0x897d   # the G key's practice; DS:7A80 32 words 0RGB; 0: the fight ends
BARS_YELLOW, BARS_EMPTY = 58, 5                      # D31's Sword of Sharpness hilt (63, 50, 0); the knights' black
BARS_COMP = (0x00, 0x02, 0x0c, 0x0e, 0x10, 0x12, 0x18, 0x20, 0x04, 0x08)   # the computer's side in the monster slots: SABER_MONSTERS, the Guardian, computer knights
BARS_COMP_SIDE, BARS_TEAM = 0xfe, 0x10               # bars_who: the computer's side, team 0/1; else a knight record 0-3
# D51 LIGHTSABER: a knight's sword pieces (KN4.OB) white (entry 1, the knights' highlight), with a 1-pixel glow in the
# knight's own darkest colour (what its pixel 8 shows in this frame) on the empty pixels around it, within the
# frame. A blow that lands kills: a knight by a swing (move 4: beheading), a chop (10h: split in two) or a thrust
# (2, 0Ah, 0Ch: run through), not after a block (a mistimed one neither); a monster by any (not the dragon or the
# Guardian). Gore off, below K18 or death_animations = off: the plain death; vanilla: the beheading
SABER_WHITE = 1
# D57: the lightsaber's look (approved from a picture): in each KN4.OB sword frame the blade's straight centre line, one
# pixel wide (its pixels 1-2's main axis, worked out from the game's frames), white; its other pixels 1-2 (and a swing's
# trail, frames 11-23) the knight's darkest colour; the hilt, and the daggers (frames 9, 10), as they are
# (D59: each list's first and middle points lie on the blade's pixels 1-2: they find the frame, mirrored or not)
SABER_LINES = {
    0: ((3, 31), (3, 32), (3, 30), (3, 29), (3, 28), (3, 27), (3, 26), (3, 25), (3, 24), (3, 23), (3, 22), (3, 21), (3, 20), (3, 19), (3, 18), (3, 17), (3, 0), (3, 16), (3, 15), (3, 14), (3, 13), (3, 12), (3, 11), (3, 10), (3, 9), (3, 8), (3, 7), (3, 6), (3, 5), (3, 4), (3, 3), (3, 2), (3, 1)),
    1: ((2, 27), (3, 26), (3, 25), (4, 24), (4, 23), (5, 22), (6, 21), (6, 20), (7, 19), (7, 18), (8, 17), (9, 16), (9, 15), (10, 14), (18, 0), (10, 13), (11, 12), (12, 11), (12, 10), (13, 9), (13, 8), (14, 7), (15, 6), (15, 5), (16, 4), (16, 3), (17, 2), (17, 1)),
    2: ((3, 2), (3, 1), (4, 3), (4, 4), (4, 5), (5, 6), (5, 7), (6, 8), (6, 9), (6, 10), (7, 11), (7, 12), (8, 13), (8, 14), (14, 29), (8, 15), (9, 16), (9, 17), (9, 18), (10, 19), (10, 20), (11, 21), (11, 22), (11, 23), (12, 24), (12, 25), (13, 26), (13, 27), (13, 28)),
    3: ((0, 14), (1, 13), (2, 12), (3, 11), (4, 10), (5, 9), (6, 8), (12, 0), (7, 7), (8, 6), (9, 5), (10, 4), (10, 3), (11, 1)),
    4: ((2, 0), (3, 1), (4, 2), (5, 3), (6, 4), (7, 5), (8, 6), (9, 7), (16, 15), (10, 8), (10, 9), (11, 10), (12, 11), (13, 12), (14, 13), (15, 14)),
    5: ((0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2), (11, 2), (12, 2), (13, 2), (14, 2), (15, 2), (16, 2), (17, 2), (36, 2), (18, 2), (19, 2), (20, 2), (21, 2), (22, 2), (23, 2), (24, 2), (25, 2), (26, 2), (27, 2), (28, 2), (29, 2), (30, 2), (31, 2), (32, 2), (33, 2), (34, 2), (35, 2)),
    6: ((1, 0), (2, 1), (2, 2), (3, 3), (3, 4), (4, 5), (4, 6), (5, 7), (6, 8), (6, 9), (7, 10), (7, 11), (8, 12), (9, 13), (17, 27), (9, 14), (10, 15), (10, 16), (11, 17), (12, 18), (12, 19), (13, 20), (13, 21), (14, 22), (15, 23), (15, 24), (16, 25), (16, 26)),
    7: ((0, 0), (1, 1), (2, 1), (3, 1), (4, 2), (5, 2), (6, 2), (7, 3), (8, 3), (9, 4), (10, 4), (11, 4), (12, 5), (13, 5), (14, 5), (29, 11), (15, 6), (16, 6), (17, 7), (18, 7), (19, 7), (20, 8), (21, 8), (22, 8), (23, 9), (24, 9), (25, 10), (26, 10), (27, 10), (28, 11), (30, 12)),
    8: ((1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4), (8, 4), (9, 5), (10, 5), (11, 6), (12, 6), (23, 11), (13, 7), (14, 7), (15, 8), (16, 8), (17, 8), (18, 9), (19, 9), (20, 10), (21, 10), (22, 11), (24, 12)),
    24: ((0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2), (11, 2), (12, 2), (13, 2), (14, 2), (15, 2), (16, 2), (17, 2), (36, 2), (18, 2), (19, 2), (20, 2), (21, 2), (22, 2), (23, 2), (24, 2), (25, 2), (26, 2), (27, 2), (28, 2), (29, 2), (30, 2), (31, 2), (32, 2), (33, 2), (34, 2), (35, 2)),
    25: ((3, 2), (3, 1), (4, 3), (4, 4), (5, 5), (5, 6), (5, 7), (6, 8), (6, 9), (10, 19), (6, 10), (7, 11), (7, 12), (7, 13), (8, 14), (8, 15), (9, 16), (9, 17), (9, 18)),
}
SABER_FRAMES_TAB = 26                                 # KN4.OB's frames
SABER_KINDS = ((0x04, 1), (0x10, 2), (0x02, 3), (0x0a, 3), (0x0c, 3))   # move -> 1 beheading, 2 split, 3 run through
SABER_MONSTERS = (0x00, 0x02, 0x0c, 0x0e, 0x10, 0x12, 0x18, 0x20)       # the monsters it kills at once (MINE_TYPES' monsters)
# D49 DAGGERFALL: a dagger (the game's object, type 1Ah, its own script at DF_SCRIPT: KN4.OB frame 9, point down)
# Every DF_EVERY ticks, a dagger starts above the screen at a random x and depth (DD_TOP-DD_BOTTOM).
# It falls DF_FALL pixels each frame. The game draws it at depth + height (+4) + the piece's dy (1000:9A4C).
DF_SCRIPT, DF_EVERY, DF_FALL, DF_START = 0xfe50, 7, 8, 20
# D58: its picture: the thrown dagger (KN4.OB frame 10) turned a quarter, hilt up, blade down (4 x 18), the last of
# the pieces death_frames.install appends to KN3.OB (bank 8 of the knights' table)
DF_BANK, DF_PIC = 0x08, 91
DF_HIT_POINTS = ((2, 17), (2, 14), (2, 11), (2, 8))   # pixel coordinates on the blade, tip first
DF_RNG_MULT, DF_RNG_ADD = 25173, 13849               # full-period 16-bit LCG, private to DAGGERFALL
DF_BOTTOM = 200                                      # D59: it falls on till its top is past the screen's bottom (y)
DF_X0, DF_SPAN_X, DF_DAMAGE = 10, 300, 0x772a   # (the thrown dagger's damage table, 1000:3E40)
LUNAR_JUMP, KB_X, KB_Y, KB_FLING_X, KB_FLING_Y, ROCKET_MOON_RISE = 5, 2, 3, 4, 6, 8   # LUNAR: a jump's speed up; a blow's push (a fling's)
# fight codes typed in the first menu (the next practice fight) or on the map (the next fight of the game): queued;
# a code queued drops the queued ones it does not go with (the last one typed counts)
FIGHT_CLASH = {'THERECANBEONLYONE': ('JUSTFLESHWOUND', 'IDDQD'), 'JUSTFLESHWOUND': ('THERECANBEONLYONE',),
               'IDDQD': ('THERECANBEONLYONE',), 'ABACABB': ('FINISHHIM',), 'FINISHHIM': ('ABACABB',),
               }
FIGHT_FLAGS = {'ROCKETMAN': CF_ROCKET, 'JUSTFLESHWOUND': CF_FLESH, 'THERECANBEONLYONE': CF_ONLYONE, 'FORE': CF_FORE,
               'IDDQD': CF_IDDQD, 'ABACABB': CF_ABACABB, 'FINISHHIM': CF_FINISH, 'LUNAR': CF_LUNAR}
MON_LEAP_X, MON_LEAP_Z, RAT_LEAP_STEPS = 50, 25, 8  # DIRTYRAT: a leap's length and steps (the AI's: 2 a step)
RAT_HANG_X, RAT_HANG_Z = 30, 25                      # DIRTYRAT: how near the knight it hangs from the tree
VALLEY_X, VALLEY_Y = (145, 164), (88, 106)            # a knight at these touches the Valley's icon (measured, 1000:0653)
# D61: the low-HP pulse of the knights in the new entries: groups of three words 32, 35, 38, 41, 44 (colour slots
# 1, 3, 2, 4, 0, as colour_sites); a slot's group; the speeds (fight frames a step) of a group's words, the game's
GLOW_GROUP_SLOTS = (1, 3, 2, 4, 0)
SLOT_GROUP = tuple(GLOW_GROUP_SLOTS.index(slot) for slot in range(5))
GLOW_SPEEDS = (2, 1, 1)
NO_GLOW_GROUP = SLOT_GROUP[4]                         # 41-43, the Black Knights' (and the white practice knight's)
MINE_COUNT, MINE_X0, MINE_SPAN_X = 10, 4, 312          # MINEFIELD: x 4-315 (D58: the whole width; the mark is x-4..x+4)
MINE_REACH_X, MINE_REACH_Z, MINE_CLEAR_X, MINE_CLEAR_Z, MINE_SOUND = 14, 6, 36, 12, 171   # set off; not at the start near a knight; bonfire2 (OWN_SOUND_IDS, K35)
MINE_BANK, MINE_FRAME, MINE_DRAW_X, MINE_DRAW_Y = 0x893d, 39, -4, 22   # KN3.OB's small black shadow; its place from x, depth
# A knight's feet (the standing script 0C74's legs, KN1.OB 1) are 33 wide at x-13..x+19 (mirrored x-20..x+12), their
# lowest rows depth+49..51, and the mark's three rows are mine depth+22..24: they meet at a knight's depth = the mine's
# - MINE_FOOT_Z, within MINE_FOOT_REACH (a step of 3-4 in depth cannot pass over those 5 values)
MINE_FOOT_Z, MINE_FOOT_REACH, MINE_FOOT_WIDTH, MINE_FOOT_RIGHT, MINE_FOOT_MIRRORED = 27, 2, 32, 19, 12
# D50: the mines only where the knights' feet go: a knight's depth DD_TOP-DD_BOTTOM (CheckBorder) + MINE_FOOT_Z
MINE_Z0, MINE_SPAN_Z = 21 + MINE_FOOT_Z, 175 - 21 - MINE_FOOT_Z + 1   # D58: down to the screen's bottom (the mark's last row y 199)
# D50: shown MINE_SHOW ticks (5 s), then hidden: the background's pixels under each mark (MINE_W x MINE_H at x-4,
# depth+22; the fight's pages are unchained, 80 bytes a line) were kept before it was drawn, and go back where the
# mark's colour (MINE_COLOUR) still is; they still go off
MINE_SHOW, MINE_W, MINE_H, MINE_COLOUR, MINE_BG_PAGE = 91, 9, 3, 5, 0xac00
MINE_TYPES = (0x00, 0x02, 0x06, 0x08, 0x0c, 0x0e, 0x10, 0x12, 0x18, 0x20)   # who sets one off: no dragon, Guardian, objects
# free part of MAIN's data (zero in the image, above the stack's use): the text, its list, the mines' dummy knight
KEY_TEXT, KEY_LIST, MINE_HITTER = 0xfe80, 0xff70, 0xff00
# D35 sword enchantments: found in a lair's chest or the dragon's hoard (sword_enchantment_chance % each, decided the first time
# it is opened; not where the Sword of Sharpness is), taken onto the knight's own sword (not the Sword of
# Sharpness), lost with that sword; Gore only with gore on. The chest shows one as the magic sword's icon
# (ENCH_ICON), item ENCH_ITEM in the click's code; its texts in a free part of MAIN's data (KEY_TEXT, not used on
# the item screen: one part for each panel)
ENCH_NAMES = ('Smite', 'Dragonbane', 'Fireblock', 'Gore', 'Troggbane', 'Desertbane', 'Swampbane', 'Ratbane')
E_SMITE, E_DRAGON, E_FIRE, E_GORE, E_TROGG, E_DESERT, E_SWAMP, E_RAT = range(1, 9)
ENCH_ITEM, ENCH_ICON, ENCH_X, ENCH_Y = 0x05, 0x17, 0x2b, 0x5f     # (the chance: sword_enchantment_chance)
ENCH_KILL = 0x2000                                   # a blow's damage that kills at once
ENCH_TEXT = b'Enchantment of '
WEAPON_NAMES = ((0x16, b'Long sword'), (0x17, b'Broad sword'), (0x18, b'Claymore sword'))
SHARPNESS, KNIGHT_BLOCK, CHOP = 0x19, 0x08, 0x10     # the Sword of Sharpness (+40h); a knight's block, its chop (+28h)
LAIR_FIRST, LAIR_SIZE, LAIR_COUNT = 0x0002, 0x12, 24
# D36: the item screen's pointer (1000:D086 moved it 2 a pass of the screen's loop): by the BIOS tick instead; a
# press moves it one step at once, then after PTR_DELAY ticks PTR_SLOW a tick, after PTR_FAST_AFTER PTR_FAST
PTR_STEP, PTR_DELAY, PTR_SLOW, PTR_FAST_AFTER, PTR_FAST = 2, 4, 3, 12, 6
MUD_TYPE, HAMMER_TROGG = 0x02, 0x0e
ARM_NAMES = ('Mithril', 'Adamantium', 'Danu', 'Wyrm', 'Fireproof', 'Venomproof', 'Spellproof', 'Rebirth', 'Daggerward')
A_MITHRIL, A_ADAMANT, A_DANU, A_WYRM, A_FIRE, A_VENOM, A_SPELL, A_REBIRTH, A_DAGGER = range(1, 10)
ARM_ITEM, ARM_X, ARM_Y = 0x07, 0x1d, 0x70            # D37: an armour enchantment's item number and place on the chest's panel
ARMOUR_NAMES = ((0x1b, b'Padded armour'), (0x1c, b'Chain mail'), (0x1d, b'Plate armour'), (0x1e, b'Battle armour'))
ARM_WINDOWS, ARM_TEXTS = (0xffa2, 0xffb5), (0xffc8, 0xffe4)   # D37: free in MAIN's data: each panel's descriptor (19 bytes for its alignment), text (28)
STONEHENGE_X, STONEHENGE_Y = 277, 143                # the map's place of Stonehenge (location 1Ah in DS:0498h's list)
ENCH_AREA = 0xfe80                                   # = KEY_TEXT: 40h for each panel
KEY_REGIONS = ((8, 'Forest key: '), (4, 'Wasteland key: '), (2, 'Swamp key: '), (1, 'Moors key: '))   # the lair set-up's order (1E2D)
TEMPLE_ITEMS, MAP_WALK, MAP_ANY_KEYS = 0xed96, 1, 2
TARGET_HOLD = 24                                     # D15: a monster's updates it keeps a new knight (pick_target)
MON_X_MIN, MON_X_MAX, MON_Z_MIN, MON_Z_MAX = 10, 300, 90, 200
CU_STEP, CU_MAX, CU_SCROLL = 30, 4, 3                 # catchup: a level per 30 points behind, at most 4; from 3 a Scroll of Acquisition
CU_LOW, CU_BOTH = 10, 25                             # catchup: a potion's chance in % (last life or low HP; both)
LOOT_GOLD_MAX = 50                                   # catchup: at most +50 % gold
ACQUISITION, COMPUTER_CONTROL = 0x0e, 4              # the Scroll of Acquisition's item; knight +9 of a computer knight
CU_ITEMS = (0x00, 0x02, 0x06, 0x08, 0x0a, 0x0c, 0x10, 0x12)   # catchup's items: potion, gem, ring, talisman, haste, hawk, wyrm, protection
HARD_KEEP = 20                                       # TOOEASY: off its knight's level a monster keeps this beyond its range
HARD, EASY = 1, 2                                    # hard_ai: TOOEASY's harder fights, TOOHARD's easier ones (0: the game's)
HARD_REST = 6                                        # TOOEASY: a monster hit again within 6 BIOS ticks (1/3 s) does not flinch
DRAGON_Z_MIN, DRAGON_Z_MAX = 90, 200                 # HOTSTUFF: the dragon's depth kept within the knights'
CHEAT_MENU, PLAYER_INPUT = 8, 0x83c0                 # the first menu's codes (HOTSTUFF); 1000:83C0: bx = player 1's bits
BEHEADING, BLOOD_SCRIPT, BLOOD_BANK = 0x1386, 0x6820, 0x895f   # the game's beheading; its hit effect (blood), BLO.CEL
FLING = 0x1202                                       # the knights' fling reaction (a troll's blow, 69C2h + type)
KNIGHT_STRIKES = (0x02, 0x04, 0x0a, 0x0c, 0x10)
RECALC = 0x0279                                      # 1000:0279: max HP and movement of the four knights
ITEMS_REDRAW, ITEMS_CALL, ITEMS_SITE = 0xed86, 0xd086, 0xbfec
MOON_DRAW, LAIRS_SETUP = 0x9034, 0x1e2d
FAIR_MAX = 6                                         # FAIRFIGHT: monsters at once at most (10 animations in all)
ROCKET_UP1, ROCKET_UP2, ROCKET_RISE, ROCKET_FALL, ROCKET_TOP = 0x48, 0x11, 5, 8, 110   # ROCKETMAN
DEPTH_GAP = 14                                       # D25: knights keep this far apart in depth (the game: 20; hits reach 10)
TURN_SHIFT = 10                                      # D25: the standing knight spans x-13..x+23 (script 0C74): -13+23
TURN_GRACE = 5                                       # D25: an attack with up or down this soon (BIOS ticks) after a turn
                                                     # is read with the facing from before the turn
PLAYER_KEYS = ((0x1c, ((0x48, 8), (0x50, 4), (0x4b, 2), (0x4d, 1))), (0x0f, ((0x11, 8), (0x1f, 4), (0x1e, 2), (0x20, 1))),
               (0x30, ((0x17, 8), (0x25, 4), (0x24, 2), (0x26, 1))))   # players 1, 2 and the third key set (I K J L, B)
KEYS3_CONTROL, KEYS3_SECONDARY = 7, 0x31              # knight +9 for the third key set; its secondary button N
TURN_SITE, TURN_SOUND = 0xa63f, 0x0f                 # D7's int 65h; the game's menu sound (1000:D6E1)
SOUND, CHEAT_SOUND = 0x5970, 17                       # 1000:5970 plays a sound id; 17 = SWORDCL (a sword clash)
HOLD_WAIT = 12                                        # first menu: these keys wait 12 ticks (2/3 s) for a code's next letter
HOLD_KEYS = (0x20, 0x24, 0x22, 0x30, 0x19)                  # D (the dragon), J (joystick set-up), G (the Guardian), B (Black Knights), P (the practice Purple Knight, D46)
PAW_X, PAW_Z, PAW_TYPE = 70, 20, 6                    # HOTSTUFF: a knight this close gets the dragon's paw (attack type 6: a fling)
# D23: the converter's call (1000:5EDA), the frame's plane mask and the game's converters by it (MAIN's code
# segment), the count of bytes a plane (counted down), where the call returns; the masks the game has a converter for
# (the others' entries are 63D1h, a ret), which ours handle
CONVERT_MASK, CONVERT_TABLE, CONVERT_COUNT, CONVERT_RET = 0x638e, 0x638f, 0x637d, 0x5edd
CONVERT_MASKS = (1, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 23, 27, 28, 30, 31)
HANDLERS, EFFECT_HANDLER, CRUSH, PLAIN_DEATH, GORE = 0x6964, 0x3eb9, 0x16e2, 0x1310, 0x0700
ANIM_SLOTS, ANIM_SIZE, ANIM_COUNT = 0x947e, 0x24, 10   # the animations (1000:981F)
# the fall's slumped pose (script 1000:130E; its frame repeats 20 times, the script then goes on to the lying 1328,
# whose first frame ends at 134Ch)
SLUMP, SLUMP_END = 0x130e, 0x134c
SLUMP_FRAMES = 0x1d                                  # the slump's repeat (DS:1313; the game's 20), about 1 s longer
# a dagger hits a slumped knight up to 14 above it, and from 8 behind it to 16 nearer the player in depth
DAGGER_REACH, DAGGER_BEHIND, DAGGER_NEARER = 14, 8, 16
HE_BANK = 0x8949                                     # a duel's second knight is drawn from it (HE*.OB, 1000:202C)
HEAD_ZONE = 12                                       # a dagger whose top is less than this below the knight's is at its head
# attackers (+35h): the trogg with the axe (the one whose blow takes a fallen knight's head off, 1000:4308), the
# ratman; a trogg's swing is +28h 4, its blow from above 10h (1000:2EFD, 2F17)
DAGGER_TYPE, AXE_TROGG, RATMAN = 0x1a, 0x0c, 0x12
UP, DOWN_FORWARD, BACK = 0x10, 0x02, 0x0a            # a knight's strike (+28h; tables DS:0C32, 0C48)
DRAGON_ATE = 0x3eed                                  # K25: the eaten knight's kill (1000:3EEA) returns here
DRAGON_FRONT = 20                                    # K29: knights stay this far right of the dragon's x (its +54h)
MUDMAN, MUD_PULLING = 0x02, 0x18                     # the mudman (+35h); +48h bits of one rising under a knight (54C7)
MUD_HOLD, MUD_REACH_X, MUD_REACH_Z, MUD_GRAB_X = 12, 100, 40, 40   # SWAMPTHING: its hold; its rise beside a knight
MUD_LET_GO = 0x554e                                  # K25: the mudman's hold ends in a kill (call 1000:0AB2 at 554B)
DAGGER_OWNER = 0x5c                                  # D19: a dagger's thrower (an object field daggers do not use)
BLACK_SHIFT = 35                                     # KN*.OB pixels 6-8 -> 41-43
STRONG = 5                                           # the B key's knights: strength, constitution, endurance
STRONG_HP = 10 * STRONG + 30 + 10                    # 1000:028D: battle armour, no rings
STRONG_MOVE = 2 * STRONG + 4 + 2                     # 1000:02E7: battle armour
SWORD_OF_SHARPNESS, CLAYMORE, BATTLE_ARMOUR = 0x19, 0x18, 0x1e
TEAM_SHOW = 18                      # D14: ticks (18.2 a second) a team practice shows the knights' own colours first
TROLL_TYPE = 0x20                   # K26: the troll's +35h
TROLL_BACK = 104                    # K26: the troll steps back from its knight within this (the game: 90)
CMD_PATH = b'Z:\\COMMAND.COM\0'       # D17: DOSBox-X's shell runs its CONFIG command (in Z:\\SYSTEM, on the PATH)
def cycles_tail(cycles):
    """D17: the command line that sets DOSBox-X's cycles (length byte, text, CR); empty for 0 (no change)."""
    text = f' /C CONFIG -set cycles={cycles} >NUL'.encode() if cycles else b''
    return bytes([len(text)]) + text + b'\r'
MAP_LOOP, AFTER_ACTION = 0xa4b0, 0xa5bb             # K22: the map loop's start; its dragon and end-of-turn checks
MAP_REDRAW_RET, TARGET_KEPT = 0xa72c, 0xa831       # K21: the map set-up's call of 1000:A78C returns here; A78C's ret
MOON_HALF, MOON_THREE_QUARTER = 0x2e, 0x2f          # K20: phase values (= KI.CEL frames) whose pictures swap
WALK_IN_RET, PAUSE_RET = 0x9dca, 0x0278              # D15: script command 1000:9DB3's call returns here; 025C's ret
STRENGTH, MAX_HP_FIELD = 0x2e, 0x3c                  # D15: the knight stats 1000:2830 uses for the monster numbers
DAGGER = 0x1a                                        # D15: a thrown dagger's object type (+35h, 1000:3E4A)
KEY_TABLE = 0x81e3                                   # D14: MAIN's key states (code segment), FFh = released (1000:8288)
SPACE, ESC = 0x39, 0x01                              # scan codes
MENU_OPTION, PRACTICE_OPTION, PLAYERS = 0x0704, 2, 0x091e
# D14: practice keys with 1 player: (scan code, choice). Choices 1-9 are lairs (PRACTICE_LAIRS, numbered as the
# table DS:0A6A, 0 = the first forest lair), 0 the Black Knight, and two more fights by their own set-up (SET_UPS)
PRACTICE_KEYS = [(0x02, 1), (0x03, 2), (0x04, 3), (0x05, 4), (0x06, 5), (0x07, 6), (0x08, 7), (0x09, 8), (0x0a, 9),
                 (0x0b, 12), (0x20, 10), (0x22, 11), (B_SCAN, BK_CHOICE), (P_SCAN, P_CHOICE)]
KEY_0_CHOICE = 12                                    # the 0 key: the tenth practice entry (custom rules can set it)
# key 1 ratmen x10, 2 ratmen x14, 3 wasteland troggs x10, 4 axe troggs x10, 5 war beasts x9, 6 spear troggs x5,
# 7 Baloks x3, 8 mudmen x5, 9 trolls x6
PRACTICE_LAIRS = [0, 3, 9, 1, 21, 19, 7, 12, 17]
SET_UPS = {10: 0x2444, 11: 0x2749}                   # as 1000:0D15 and 0FE7
DRAGON_CHOICE = 10                                   # the D key: the dragon's fight (SET_UPS)
LAIR_RECORDS, LAIR_SIZE = 0x0002, 0x12               # lair records built at 1000:1E95
# D15 co-op: the knights after the first: (record, control, colour slot +20h, x); all face left like the first
COOP_KNIGHTS = [(0x6d00, 1, 2, 220), (0x6d62, 5, 1, 280), (0x6dc4, 6, 3, 190)]   # controls as D12's
KNIGHTS = (0x6c9e, 0x6d00, 0x6d62, 0x6dc4)
ADD_STATE = 10                                       # practice_init states from here: adding the co-op knights
TARGET_KEEP = 20                                     # a monster keeps its knight unless another is this much nearer
MONSTER_SLOTS, SLOT_SIZE, MONSTER_COUNT, DRAGON_RECORD = 0x6f08, 0x62, 20, 0x6e26   # fight objects (1000:2A1E), dragon
DF_HIT_DATA = MINE_HITTER + SLOT_SIZE                # collision data between the mine record and KEY_LIST
# D64 GUNSHOT: its scripts and hit points (gun_src), written at GUN_AREA: the shot, the ball's first frame, its flight
GUN_AREA = MARKER_SCRIPT + MARKER_SIZE
def _gun_data():
    shot = (bytes((0xa4, 0x01, 0x34, 0x00)) + struct.pack('<H', GUN_NO_DAGGER) +   # no dagger: the game's own branch
            bytes((0x92, GUN_BANG, 0x82, 0x03)) + struct.pack('<H', GUN_JUMP))       # the bang, the throw's last frame
    def frame(step, dx, flag):
        return (struct.pack('<BBhhh', 0x90, 0x01, step, 0, 0) +
                struct.pack('<BBbBh', BALL_BANK, BALL_PIC, BALL_DY, flag, dx) + b'\xff\xff')
    first, fly = frame(BALL_FIRST, BALL_FIRST_DX, 0x00), frame(BALL_STEP, BALL_DX, 0x02)   # 2: a weapon's piece
    xs, ys = zip(*BALL_POINTS)        # as COLLIDE.HIT (887F): count, a spare byte, max x and y, then the points
    points = bytes((len(xs), 0, max(xs), max(ys))) + bytes(n for p_ in BALL_POINTS for n in p_)
    parts = (shot, first, fly, points)
    offs = [GUN_AREA + sum(len(q) for q in parts[:k]) for k in range(4)]
    return b''.join(parts), offs
GUN_SRC, (GUN_SHOT, GUN_BALL, GUN_FLY, GUN_POINTS) = _gun_data()
if GUN_AREA + len(GUN_SRC) > MINE_HITTER or GUN_AREA < 0xfe80:
    raise ValueError("D64: GUNSHOT's scripts do not fit between the hit marker's script and the mines' record")
DRAGON_HOARD, DRAGON_GOLD = 0x6ee8, 0x6e26 + 0x32   # K18: the dragon's 24-byte item table and its gold
# D13: the knights drawn in the new colours: (record, its first knight-colour pixel, the game's fight palette words
# for +20h = 1 and 3, which custom rules recolour); their pixels move up by 26: 6-8 -> 32-34, 9-11 -> 35-37
RECOLOUR = [(0x6d62, 6, (0x4838, 0x483d, 0x4842)), (0x6dc4, 9, (0x484e, 0x4853, 0x4858))]
RECOLOUR_SHIFT, NEW_ENTRIES = 26, 32
# D15: in a lair fight bank 8949h holds the monsters, so every co-op knight is drawn from KN*.OB (6-8): knight 2
# moves to 38-40 (+32, the words of +20h = 2), 3 to 32-34 (+26), 4 to 35-37 (+29)
COOP_RECOLOUR = [(0x6d00, 6, 32), (0x6d62, 6, 26), (0x6dc4, 6, 29)]
SLOT_SHIFTS = (38, 26, 32, 29, 35)                   # D33: a knight's colour slot (+20h 0-4) -> its entries 44, 32, 38, 35, 41
PRACTICE_RECOLOUR = [(rec, first, RECOLOUR_SHIFT) for rec, first, _ in RECOLOUR]
GREEN_SITES = (0x4864, 0x4869, 0x486e)               # fight palette words of +20h = 2, for entries 38-40
NEW_WORDS = 15                                       # entries 32-46 (D19: 41-43 the Black Knights, D33: 44-46 knight 1)
BLUE_SITES = (0x4822, 0x4827, 0x482c)                # fight palette words of +20h = 0 (1000:481A), for entries 44-46
# D31: every sword its own tint. The sword is always drawn from KN4.OB (blade 1-2, hilt 3-4); for a knight with
# the weapon (record +40h) those four pixel values move to its entries. The claymore keeps the game's bright steel.
# 6-bit DAC values (0-63): blade light, blade dark, hilt, hilt dark
SWORD_FIRST, SWORD_KN4 = 48, 0x8941                  # its entries 48-59; KN4.OB's far pointer in the bank table
SWORD_TINTS = [(0x16, ((40, 40, 44), (20, 20, 24), (14, 14, 16), (6, 6, 8))),     # long sword: blackened, black iron grip
               (0x17, ((60, 50, 30), (44, 30, 12), (32, 18, 6), (18, 10, 2))),    # broadsword: bronze
               (0x19, ((52, 63, 63), (12, 46, 63), (63, 50, 0), (44, 30, 0)))]    # Sword of Sharpness: glow, gold
# D31: the armour (record +42h) the same way, in the knight's other pieces (its greys 1-4: helmet, collar, arms,
# legs); highlight, light, mid, dark. Padded armour keeps the game's bright steel
ARMOUR_FIRST = SWORD_FIRST + 4 * len(SWORD_TINTS)    # entries 60-71
ARMOUR_TINTS = [(0x1c, ((63, 54, 26), (46, 36, 12), (34, 25, 8), (18, 12, 3))),    # chain mail: brass
                (0x1d, ((42, 48, 58), (24, 30, 40), (17, 22, 31), (8, 11, 17))),   # plate mail: cool blue-grey iron
                (0x1e, ((63, 50, 12), (22, 22, 26), (15, 15, 18), (7, 7, 9)))]     # battle armour: blackened, gold trim
GEAR_ENTRIES = 4 * (len(SWORD_TINTS) + len(ARMOUR_TINTS))
BODY_SEGMENTS = (0x8937, 0x893b, 0x893f, 0x8947, 0x894d, 0x8951, 0x8955)   # KN1-3, KN5, HE1-3: their segments' words
BLITTER, BLIT_COUNT = 0x5dd4, 0x637b          # the blitter, and its converter's output count (a word in MAIN's code)
TEAM1, TEAM2 = (0x6c9e, 0x6d62), (0x6d00, 0x6dc4)   # D12: player 1 + joystick A, player 2 + joystick B
JOY_A_CONTROL, JOY_B_CONTROL = 5, 6                  # D12: knight +9 for the two joysticks (4 is the computer)
JOY_PORT_LIMIT = 0x2000                              # no joystick: its port bits never fall within this many reads
CHILD_PATH = b'C:\\SAVEHOOK.RUN\0'      # the game folder is drive C: in moonstone-dosbox-x.conf
CHILD_CODE = b'\xb8\x00\x4c\xcd\x21'     # the child: mov ax, 4C00h / int 21h
WAIT_TICKS = 20                          # 20 / 18.2 Hz = 1.1 s; the autosave check runs about every 1.0 s
SAVE_SLOTS = (91, 92, 93, 94, 96, 97, 98, 99, 100)   # the conf's autosave slots: TURN1-4, FIGHT1-5 (save_wait)
WAIT_LIMIT_HI = 50                       # gives up after 50 * 65536 loop rounds (several seconds) if ticks stop
RESERVE_PARAS = 0x100                    # 4 KB kept free for the child program
SIGNATURE = b'SV'                        # just before the fight handler: tells the child that the hook is installed

class Asm:
    """Minimal assembler: raw bytes plus labels, 16-bit absolute label words and short or near jumps."""
    def __init__(self, org):
        self.org, self.code, self.labels, self.fixups = org, bytearray(), {}, []
    def b(self, *data):
        for x in data:
            self.code += x if isinstance(x, (bytes, bytearray)) else bytes([x])
    def label(self, name):
        if name in self.labels:
            raise ValueError(f'label {name} defined twice')
        self.labels[name] = self.org + len(self.code)
    def word(self, label, add=0):                # 16-bit address of a label (+ add)
        self.fixups.append(('abs', len(self.code), label, add)); self.code += b'\0\0'
    def short(self, opcode, label):             # jcc / jmp short / loop
        self.code.append(opcode); self.fixups.append(('rel8', len(self.code), label, 0)); self.code.append(0)
    def near(self, opcode, label):              # call / jmp near
        self.code.append(opcode); self.fixups.append(('rel16', len(self.code), label, 0)); self.code += b'\0\0'
    def here(self):
        return self.org + len(self.code)
    def build(self):
        for kind, pos, label, add in self.fixups:
            target = self.labels[label] + add
            if kind == 'abs':
                struct.pack_into('<H', self.code, pos, target)
            elif kind == 'rel8':
                rel = target - (self.org + pos + 1)
                if not -128 <= rel < 128:
                    raise ValueError(f'short jump to {label} is out of range ({rel})')
                self.code[pos] = rel & 0xff
            else:
                struct.pack_into('<H', self.code, pos, (target - (self.org + pos + 2)) & 0xffff)   # wraps in the 64 KB segment
        return bytes(self.code)

def rules_code(a):
    """int 63h: the custom game rules from custom_rules.ini (rules.py). The MAIN.EXE sites are in rules.HOOKS; the
    handler finds the job by the return address. All jobs run with bp = frame ([bp+2] return IP, [bp+4] CS,
    [bp+6] flags) and bx saved at [bp-2]; they end at rules_done, or at rules_flags to return the arithmetic flags of
    their last instruction (the game code after the site may test them)."""
    a.label('rules_handler')
    a.b(0x55, 0x8b, 0xec, 0x53)                              # push bp / mov bp, sp / push bx
    a.b(0xbb); a.word('hooks')                               # mov bx, hooks
    a.label('rules_find')
    a.b(0x2e, 0x83, 0x3f, 0x00)                              # cmp word cs:[bx], 0     end of the table
    a.short(0x74, 'rules_done')                              # je rules_done
    a.b(0x50, 0x8b, 0x46, 0x02, 0x2e, 0x3b, 0x07, 0x58)      # push ax / mov ax, [bp+2] / cmp ax, cs:[bx] / pop ax
    a.short(0x74, 'rules_found')                             # je rules_found
    a.b(0x83, 0xc3, 0x04)                                    # add bx, 4
    a.short(0xeb, 'rules_find')                              # jmp rules_find
    a.label('rules_found')
    a.b(0x2e, 0xff, 0x67, 0x02)                              # jmp word cs:[bx+2]
    a.label('rules_flags')                                   # keep the caller's IF/TF, return OF SF ZF AF PF CF
    a.b(0x9c, 0x5b)                                          # pushf / pop bx
    a.b(0x81, 0xe3, 0xd5, 0x08)                              # and bx, 08D5h
    a.b(0x81, 0x66, 0x06, 0x2a, 0xf7)                        # and word [bp+6], 0F72Ah
    a.b(0x09, 0x5e, 0x06)                                    # or [bp+6], bx
    a.label('rules_done')
    a.b(0x5b, 0x5d, 0xcf)                                    # pop bx / pop bp / iret

    # section: si = record -> bx = its settings block, CF = 0, and [rec4] = record number * 4;
    # CF = 1 if si is not one of the four knight records (a monster, the dragon)
    a.label('section')
    a.b(0x50, 0x33, 0xc0)                                    # push ax / xor ax, ax
    for n, rec in enumerate((0x6c9e, 0x6d00, 0x6d62, 0x6dc4)):
        if n:
            a.b(0xb0, 4 * n)                                 # mov al, 4 * n
        a.b(0x81, 0xfe, rec & 0xff, rec >> 8)                # cmp si, record
        a.short(0x74, 'section_ok')                          # je section_ok
    a.b(0x58, 0xf9, 0xc3)                                    # pop ax / stc / ret
    a.label('section_ok')
    a.b(0x2e, 0xa3); a.word('rec4')                          # mov cs:[rec4], ax
    a.b(0x8b, 0x5c, 0x20)                                    # mov bx, [si+20h]    0-3 human knight, 4 computer
    a.b(0x83, 0xfb, 0x04)                                    # cmp bx, 4
    a.short(0x76, 'section_ptr')                             # jbe section_ptr
    a.b(0xbb, 0x04, 0x00)                                    # mov bx, 4
    a.label('section_ptr')
    a.b(0xd1, 0xe3)                                          # shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('section_ptrs')            # mov bx, cs:[bx+section_ptrs]
    a.b(0x58, 0xf8, 0xc3)                                    # pop ax / clc / ret

    # calc_hp: si = record, bx = block -> ax = max HP, as 1000:028D plus the HP bonus (1-999)
    a.label('calc_hp')
    a.b(0x51, 0x52)                                          # push cx / push dx
    a.b(0x8a, 0x44, 0x2f, 0x32, 0xe4)                        # mov al, [si+2Fh] / xor ah, ah     constitution
    a.b(0xb9, 0x0a, 0x00, 0xf7, 0xe1, 0x8b, 0xc8)            # mov cx, 10 / mul cx / mov cx, ax
    a.b(0x57, 0x8b, 0x7c, 0x44, 0x8b, 0x45, 0x06, 0x5f)      # push di / mov di, [si+44h] / mov ax, [di+6] / pop di
    a.b(0x2e, 0x8b, 0x16); a.word('rules_table', G_RING)     # mov dx, cs:[ring_hp]
    a.b(0xf7, 0xe2, 0x03, 0xc8)                              # mul dx / add cx, ax                 rings
    a.b(0x8b, 0x44, 0x42, 0x2d, 0x1b, 0x00)                  # mov ax, [si+42h] / sub ax, 1Bh    armour 0-3
    a.b(0x3d, 0x03, 0x00)                                    # cmp ax, 3
    a.short(0x77, 'calc_base')                               # ja calc_base
    a.b(0x53, 0x8b, 0xd8, 0xd1, 0xe3)                        # push bx / mov bx, ax / shl bx, 1
    a.b(0x2e, 0x03, 0x8f); a.word('rules_table', G_ARMOUR_HP)   # add cx, cs:[bx+armour_hp]
    a.b(0x5b)                                                # pop bx
    a.label('calc_base')
    a.b(0x83, 0xc1, 0x0a)                                    # add cx, 10
    a.b(0x2e, 0x03, 0x4f, 0x0e)                              # add cx, cs:[bx+0Eh]                HP bonus
    a.b(0x8b, 0xc1, 0x83, 0xf8, 0x01)                        # mov ax, cx / cmp ax, 1
    a.short(0x7d, 'calc_end')                                # jge calc_end
    a.b(0xb8, 0x01, 0x00)                                    # mov ax, 1
    a.label('calc_end')
    a.b(0x3d, MAX_HP & 0xff, MAX_HP >> 8)                    # cmp ax, 999
    a.short(0x7e, 'calc_ok')                                 # jle calc_ok
    a.b(0xb8, MAX_HP & 0xff, MAX_HP >> 8)                    # mov ax, 999
    a.label('calc_ok')
    a.b(0x5a, 0x59, 0xc3)                                    # pop dx / pop cx / ret

    # start_knight: si = record, di = its item table, bx = block: the starting values (clobbers ax, cx)
    a.label('start_knight')
    a.b(0x56, 0x57, 0x53)                                    # push si / push di / push bx
    a.b(0xb9, 0x18, 0x00)                                    # mov cx, 24
    a.label('start_items')
    a.b(0x2e, 0x8a, 0x47, 0x10, 0x88, 0x05, 0x43, 0x47)      # mov al, cs:[bx+10h] / mov [di], al / inc bx / inc di
    a.short(0xe2, 'start_items')                             # loop start_items
    a.b(0x5b, 0x53)                                          # pop bx / push bx
    a.b(0xb9, 0x07, 0x00)                                    # mov cx, 7    STR CON END lives gold daggers
    a.label('start_stats')
    a.b(0x2e, 0x8a, 0x07, 0x88, 0x44, 0x2e, 0x43, 0x46)      # mov al, cs:[bx] / mov [si+2Eh], al / inc bx / inc si
    a.short(0xe2, 'start_stats')                             # loop start_stats
    a.b(0x5b, 0x5f, 0x5e, 0x57)                              # pop bx / pop di / pop si / push di
    for src, dst in ((0x08, 0x36), (0x0a, 0x40), (0x0c, 0x42)):   # XP, weapon, armour
        a.b(0x2e, 0x8b, 0x47, src, 0x89, 0x44, dst)          # mov ax, cs:[bx+src] / mov [si+dst], ax
    a.b(0xc6, 0x44, 0x3a, 0x00)                              # mov byte [si+3Ah], 0     not a frog
    a.b(0xc6, 0x44, 0x3b, 0xff)                              # mov byte [si+3Bh], 0FFh  Math: first visit
    a.b(0xc6, 0x44, 0x60, 0x00)                              # mov byte [si+60h], 0     no disease
    a.b(0xc7, 0x44, 0x46, 0x00, 0x00)                        # mov word [si+46h], 0     (as 1000:1FE5)
    a.near(0xe8, 'calc_hp')                                  # call calc_hp
    a.b(0x89, 0x44, 0x3c, 0x89, 0x44, 0x38)                  # mov [si+3Ch], ax / mov [si+38h], ax   full HP
    a.b(0x8a, 0x44, 0x30, 0x32, 0xe4, 0xd1, 0xe0)            # mov al, [si+30h] / xor ah, ah / shl ax, 1
    a.b(0x05, 0x04, 0x00)                                    # add ax, 4      movement as 1000:02E7
    a.b(0x83, 0x7c, 0x42, 0x1c)                              # cmp word [si+42h], 1Ch
    a.short(0x74, 'start_fast')                              # je start_fast
    a.b(0x83, 0x7c, 0x42, 0x1e)                              # cmp word [si+42h], 1Eh
    a.short(0x75, 'start_move')                              # jne start_move
    a.label('start_fast')
    a.b(0x05, 0x02, 0x00)                                    # add ax, 2
    a.label('start_move')
    a.b(0x89, 0x44, 0x3e)                                    # mov [si+3Eh], ax
    a.b(0x5f, 0xc3)                                          # pop di / ret

    # init (1000:1FEF): knight set-up, di = record, si = item table. A human knight starts at the start corner of
    # its home village (1000:0157 placed it at its own)
    a.label('rules_init')
    a.near(0xe8, 'fate_init')                                # call fate_init
    a.b(0x50, 0x51, 0x56, 0x57, 0x87, 0xf7)                  # push ax cx si di / xchg si, di
    a.near(0xe8, 'section')                                  # call section
    a.near(0xe8, 'start_knight')                             # call start_knight
    a.near(0xe8, 'knight_reset')                             # its enchantments and horse cleared
    a.b(0x8b, 0x5c, 0x20, 0x83, 0xfb, 0x03)                  # mov bx, [si+20h] / cmp bx, 3
    a.short(0x77, 'init_pos')                                # ja init_pos       a computer knight: as set
    a.b(0x2e, 0x8a, 0x9f); a.word('rules_table', G_HOMES)    # mov bl, cs:[bx+homes]
    a.b(0x80, 0xfb, 0x03)                                    # cmp bl, 3
    a.short(0x77, 'init_pos')                                # ja init_pos
    a.b(0x32, 0xff, 0xd1, 0xe3, 0xd1, 0xe3)                  # xor bh, bh / shl bx, 1 / shl bx, 1
    a.b(0x2e, 0x8b, 0x87); a.word('spawns')                  # mov ax, cs:[bx+spawns]      the home's start corner
    a.b(0x89, 0x44, 0x5c)                                    # mov [si+5Ch], ax
    a.b(0x2e, 0x8b, 0x87); a.word('spawns', 2)               # mov ax, cs:[bx+spawns+2]
    a.b(0x89, 0x44, 0x5e)                                    # mov [si+5Eh], ax
    a.label('init_pos')
    a.b(0x2e, 0x8b, 0x1e); a.word('rec4')                    # mov bx, cs:[rec4]     remember the start position
    a.b(0x8b, 0x44, 0x5c, 0x2e, 0x89, 0x87); a.word('start_pos')      # mov ax, [si+5Ch] / mov cs:[bx+start_pos], ax
    a.b(0x8b, 0x44, 0x5e, 0x2e, 0x89, 0x87); a.word('start_pos', 2)   # mov ax, [si+5Eh] / mov cs:[bx+start_pos+2], ax
    a.b(0x5f, 0x5e, 0x59, 0x58)                              # pop di si cx ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # max_hp (1000:02D5): replaces add bx,10 of the max HP formula, si = record. The result is capped at 999: the
    # item screen prints "current/max" into a small buffer (rules.MAX_HP), and abilities and rings can keep growing
    # during a game
    a.label('rules_max_hp')
    a.b(0x50, 0xb8, 0x0a, 0x00)                              # push ax / mov ax, 10
    a.b(0x83, 0x7c, 0x42, 0x1b)                              # cmp word [si+42h], 1Bh
    a.short(0x75, 'max_hp_bonus')                            # jne max_hp_bonus
    a.b(0x2e, 0x03, 0x06); a.word('rules_table', G_ARMOUR_HP)   # add ax, cs:[armour_hp]   padded (others in MAIN)
    a.label('max_hp_bonus')
    a.near(0xe8, 'section')                                  # call section
    a.short(0x72, 'max_hp_add')                              # jc max_hp_add
    a.b(0x2e, 0x03, 0x47, 0x0e)                              # add ax, cs:[bx+0Eh]
    a.label('max_hp_add')
    a.b(0x50); a.near(0xe8, 'arm_of'); a.b(0x3c, A_ADAMANT, 0x58); a.short(0x75, 'max_hp_plain'); a.b(0x05, 0x0a, 0x00)   # D37: Adamantium
    a.label('max_hp_plain')
    a.b(0x01, 0x46, 0xfe, 0x58)                              # add [bp-2], ax (the saved bx) / pop ax
    a.b(0x81, 0x7e, 0xfe, MAX_HP & 0xff, MAX_HP >> 8)        # cmp word [bp-2], 999
    a.short(0x7e, 'max_hp_done')                             # jle max_hp_done
    a.b(0xc7, 0x46, 0xfe, MAX_HP & 0xff, MAX_HP >> 8)        # mov word [bp-2], 999
    a.label('max_hp_done')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # damage (1000:2D86): replaces mov cl,[si+2Eh] / add ax,cx; si = attacker, ax = base damage
    a.label('rules_damage')
    a.near(0xe8, 'td_fast_dmg')                              # D46: the fast swing and the riposte: a weaker blow's base damage
    a.b(0x8a, 0x4c, 0x2e, 0x03, 0xc1)                        # mov cl, [si+2Eh] / add ax, cx
    a.near(0xe8, 'section')                                  # call section
    a.short(0x72, 'damage_end')                              # jc damage_end    not a knight
    a.b(0x83, 0x7c, 0x40, 0x16)                              # cmp word [si+40h], 16h
    a.short(0x75, 'damage_end')                              # jne damage_end
    a.b(0x2e, 0x03, 0x06); a.word('rules_table', G_SWORD)    # add ax, cs:[long sword bonus]
    a.label('damage_end')
    a.b(0x85, 0xc0)                                          # test ax, ax
    a.short(0x7d, 'damage_done')                             # jge damage_done
    a.b(0x33, 0xc0)                                          # xor ax, ax
    a.label('damage_done')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # lives: sub byte [si+31h],nn / sub byte [di+31h],nn; an invulnerable knight keeps at least one
    a.label('rules_lives_di')
    a.b(0x56, 0x8b, 0xf7)                                    # push si / mov si, di
    a.short(0xeb, 'lives')                                   # jmp lives
    a.label('rules_lives_si')
    a.b(0x56)                                                # push si
    a.label('lives')
    a.b(0x50, 0x1e)                                          # push ax / push ds
    a.b(0x8b, 0x5e, 0x02, 0x8e, 0x5e, 0x04, 0x8a, 0x07, 0x1f)   # mov bx, [bp+2] / mov ds, [bp+4] / mov al, [bx] / pop ds
    a.b(0x83, 0x46, 0x02, 0x02)                              # add word [bp+2], 2
    a.b(0x81, 0x7e, 0x02, 0xe1, 0x0a); a.short(0x74, 'lives_fight')   # D37: a fight lost (0ADD, 0AED) with Rebirth?
    a.b(0x81, 0x7e, 0x02, 0xf1, 0x0a); a.short(0x75, 'lives_sub')
    a.label('lives_fight')
    a.b(0x50); a.near(0xe8, 'arm_of'); a.b(0x3c, A_REBIRTH, 0x58); a.short(0x75, 'lives_sub')
    a.near(0xe9, 'arm_reborn')
    a.label('lives_sub')
    a.b(0x28, 0x44, 0x31)                                    # sub [si+31h], al
    a.near(0xe8, 'section')                                  # call section
    a.short(0x72, 'lives_end')                               # jc lives_end
    a.b(0x2e, 0x80, 0x7f, 0x07, MODE_INVULNERABLE)           # cmp byte cs:[bx+7], 3
    a.short(0x75, 'lives_end')                               # jne lives_end
    a.b(0x80, 0x7c, 0x31, 0x01)                              # cmp byte [si+31h], 1
    a.short(0x7d, 'lives_end')                               # jge lives_end
    a.b(0xc6, 0x44, 0x31, 0x01)                              # mov byte [si+31h], 1
    a.label('lives_end')
    a.b(0x58, 0x5e)                                          # pop ax / pop si
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # turn (1000:A66E): replaces cmp byte [si+31h],0 (is the knight whose turn it is dead?); si = record.
    # Reincarnation: starting values again; respawn: max lives and full HP, the rest kept; both at the start position
    a.label('rules_turn')
    a.near(0xe8, 'section')                                  # call section
    a.short(0x72, 'turn_cmp')                                # jc turn_cmp
    a.b(0x80, 0x7c, 0x31, 0x00)                              # cmp byte [si+31h], 0
    a.short(0x7f, 'turn_cmp')                                # jg turn_cmp       alive
    a.b(0x50, 0x2e, 0x8a, 0x47, 0x07)                        # push ax / mov al, cs:[bx+7]
    a.b(0x3c, MODE_REINCARNATION)                            # cmp al, 1
    a.short(0x74, 'turn_reborn')                             # je turn_reborn
    a.b(0x3c, MODE_RESPAWN)                                  # cmp al, 2
    a.short(0x75, 'turn_pop')                                # jne turn_pop      permadeath
    a.b(0x2e, 0xa0); a.word('rules_table', G_MAX_LIVES)      # mov al, cs:[max_lives]
    a.b(0x88, 0x44, 0x31)                                    # mov [si+31h], al
    a.b(0x8b, 0x44, 0x3c, 0x89, 0x44, 0x38)                  # mov ax, [si+3Ch] / mov [si+38h], ax
    a.b(0xc6, 0x44, 0x60, 0x00)                              # mov byte [si+60h], 0
    a.short(0xeb, 'turn_place')                              # jmp turn_place
    a.label('turn_reborn')
    a.b(0x51, 0x57, 0x8b, 0x7c, 0x44)                        # push cx / push di / mov di, [si+44h]
    a.near(0xe8, 'start_knight')                             # call start_knight
    a.b(0x5f, 0x59)                                          # pop di / pop cx
    a.label('turn_place')
    a.b(0x53, 0x2e, 0x8b, 0x1e); a.word('rec4')              # push bx / mov bx, cs:[rec4]
    for pos, cell, add in ((0x5c, 0x2a, 0), (0x5e, 0x2c, 2)):    # x, y in pixels and in 8-pixel cells
        a.b(0x2e, 0x8b, 0x87); a.word('start_pos', add)      # mov ax, cs:[bx+start_pos]
        a.b(0x89, 0x44, pos, 0xd1, 0xe8, 0xd1, 0xe8, 0xd1, 0xe8, 0x89, 0x44, cell)   # mov [si+pos], ax / shr ax,1 x3
    a.b(0x5b)                                                # pop bx
    a.label('turn_pop')
    a.b(0x58)                                                # pop ax
    a.label('turn_cmp')
    a.b(0x80, 0x7c, 0x31, 0x00)                              # cmp byte [si+31h], 0  (replaced instruction)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # rest (1000:A590): the E key ends the turn; replaces mov ax,[0CCACh]. on_E_rest_heal = full: full HP at once
    # (fixed_and_endurance and fixed_only heal at the day's end, daily_heal)
    a.label('rules_rest')
    a.b(0xa1, 0xac, 0xcc)                                    # mov ax, [0CCACh]
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_REST); a.b(REST_HEAL['full'])   # cmp byte cs:[rest_heal], 1
    a.short(0x75, 'rest_end')                                # jne rest_end
    a.b(0x8b, 0x1e, 0xe8, 0x77, 0x50)                        # mov bx, [77E8h] / push ax
    a.b(0x8b, 0x47, 0x3c, 0x89, 0x47, 0x38, 0x58)            # mov ax, [bx+3Ch] / mov [bx+38h], ax / pop ax
    a.label('rest_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # turn_moves (1000:A568, replaces mov di,[77E8h], every pass of the map loop before the E key (A586) and a
    # place's action (A5B1)): the movement left now, before E or an action uses up the turn
    a.label('rules_turn_moves')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_wait'); a.b(0x00); a.short(0x74, 'sxtm_nw')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x00, 0x2e, 0xa1); a.word('snd_ax')   # back from the sound: ax again
    a.short(0xeb, 'sxtm_go')
    a.label('sxtm_nw')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_req'); a.b(0x00); a.short(0x74, 'sxtm_go')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_req'); a.b(0x00, 0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x01)
    a.b(0x2e, 0xa3); a.word('snd_ax'); a.b(0x8b, 0x46, 0x02, 0x2d, 0x02, 0x00)   # mov cs:[snd_ax], ax / mov ax, [bp+2] / sub ax, 2
    a.b(0x2e, 0xa3); a.word('call_ret')                      # this site's int 63h again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(SOUND & 0xff, SOUND >> 8)
    a.b(0xb8, CHEAT_SOUND, 0x00); a.near(0xe9, 'call_game')  # mov ax, sound id / 1000:5970
    a.label('sxtm_go')
    a.b(0x2e, 0x80, 0x3e); a.word('key_show'); a.b(0x00); a.short(0x74, 'tm_no_keys')
    a.near(0xe9, 'key_stage')                                # IDROPPEDMYKEY's screen
    a.label('tm_no_keys')
    a.near(0xe8, 'gore_lock')
    a.near(0xe8, 'cheat_map')                                # call cheat_map   CF = 1: call_target, then here again
    a.short(0x73, 'tm_go')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(TURN_MOVES_SITE & 0xff, TURN_MOVES_SITE >> 8)
    a.near(0xe9, 'call_game')
    a.label('tm_go')
    a.near(0xe8, 'hawk_guard')                               # call hawk_guard    the Hawk stays out of the Valley
    a.b(0x2e, 0xf6, 0x06); a.word('map_flags'); a.b(MAP_WALK); a.short(0x74, 'tm_walk')   # SIRWALKSALOT: a human's walk costs nothing
    a.b(0x56, 0x8b, 0x36, 0xe8, 0x77, 0x83, 0x7c, 0x20, COMPUTER, 0x5e); a.short(0x74, 'tm_walk')
    a.b(0xc7, 0x06, 0x98, 0xcc, 0x00, 0x00)                  # mov word [0CC98h], 0
    a.label('tm_walk')
    a.b(0x50, 0xa1, 0xac, 0xcc, 0x2b, 0x06, 0x98, 0xcc)      # push ax / mov ax, [0CCACh] / sub ax, [0CC98h]
    a.short(0x7d, 'tm_set'); a.b(0x33, 0xc0)                 # jge tm_set / xor ax, ax
    a.label('tm_set')
    a.b(0x2e, 0xa3); a.word('moves_left'); a.b(0x58)         # mov cs:[moves_left], ax / pop ax
    a.b(0x8b, 0x3e, 0xe8, 0x77)                              # mov di, [77E8h]   (replaced)
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # turn_end (1000:A607, replaces mov word [0CCAAh],0 where a turn ends, [77E8h] the knight): its movement left
    # (turn_moves) and the turn's budget ([0CCACh]), for its healing at the day's end (daily_heal)
    a.label('rules_turn_end')
    a.b(0xc7, 0x06, 0xaa, 0xcc, 0x00, 0x00)                  # mov word [0CCAAh], 0   (replaced)
    a.b(0x2e, 0xc6, 0x06); a.word('keys_shown'); a.b(0x00)   # IDROPPEDMYKEY: until the turn's end
    a.b(0x50, 0x53, 0x52)                                    # push ax bx dx
    a.b(0xa1, 0xe8, 0x77, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # mov ax, [77E8h] / sub ax, 6C9Eh
    a.short(0x72, 'te_pop')                                  # jb te_pop
    a.b(0x33, 0xd2, 0xbb, SLOT_SIZE, 0x00, 0xf7, 0xf3)       # xor dx, dx / mov bx, 62h / div bx   the knight 0-3
    a.b(0x3d, 0x04, 0x00); a.short(0x73, 'te_pop')           # cmp ax, 4 / jae te_pop
    a.b(0xd1, 0xe0, 0x8b, 0xd8)                              # shl ax, 1 / mov bx, ax
    a.b(0x2e, 0xa1); a.word('moves_left')                    # mov ax, cs:[moves_left]
    a.b(0x2e, 0x89, 0x87); a.word('day_left')                # mov cs:[bx+day_left], ax
    a.b(0xa1, 0xac, 0xcc)                                    # mov ax, [0CCACh]
    a.b(0x2e, 0x89, 0x87); a.word('day_budget')              # mov cs:[bx+day_budget], ax
    a.label('te_pop')
    a.b(0x5a, 0x5b, 0x58)                                    # pop dx bx ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # daily_heal (1000:11BF, the day's end, for each record si: bx = ((max - HP) >> 2) | 1, then add [si+38h],bx
    # at 11CE; the site is int 63h and nops up to it, the game's bx is set in the frame): the game's quarter of the
    # missing HP; with on_E_rest_heal fixed_and_endurance or fixed_only the missing HP times fixed % plus
    # endurance % times the share of its last turn's movement left (turn_end), at least 1:
    # missing * (fixed * budget + endurance * left) / (100 * budget)
    a.label('rules_daily_heal')
    a.b(0x50, 0x51, 0x52, 0x56)                              # push ax cx dx si
    a.b(0x8b, 0x4c, 0x3c, 0x2b, 0x4c, 0x38)                  # mov cx, [si+3Ch] / sub cx, [si+38h]   missing
    a.short(0x7f, 'dh_missing'); a.b(0x33, 0xc9)             # jg dh_missing / xor cx, cx
    a.near(0xe9, 'dh_set')
    a.label('dh_missing')
    a.b(0x2e, 0xa0); a.word('rules_table', G_REST)           # mov al, cs:[rest_heal]
    a.b(0x3c, REST_HEAL['fixed_and_endurance']); a.short(0x74, 'dh_ours')
    a.b(0x3c, REST_HEAL['fixed_only']); a.short(0x74, 'dh_ours')
    a.label('dh_game')
    a.b(0xd1, 0xe9, 0xd1, 0xe9, 0x83, 0xc9, 0x01)            # shr cx, 1 / shr cx, 1 / or cx, 1   (the game's)
    a.near(0xe9, 'dh_set')
    a.label('dh_ours')
    a.b(0x8a, 0xd0)                                          # mov dl, al       the mode
    a.b(0x8b, 0xc6, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # mov ax, si / sub ax, 6C9Eh
    a.short(0x72, 'dh_game')                                 # jb dh_game
    a.b(0x52, 0x33, 0xd2, 0xbe, SLOT_SIZE, 0x00, 0xf7, 0xf6, 0x5a)   # push dx / xor dx,dx / mov si, 62h / div si / pop dx
    a.b(0x3d, 0x04, 0x00); a.short(0x73, 'dh_game')          # cmp ax, 4 / jae dh_game   (the fifth record)
    a.b(0xd1, 0xe0, 0x8b, 0xf0)                              # shl ax, 1 / mov si, ax
    a.b(0x53, 0x2e, 0x8b, 0x9c); a.word('day_budget')        # push bx / mov bx, cs:[si+day_budget]
    a.b(0x0b, 0xdb); a.short(0x75, 'dh_budget'); a.b(0x43)   # or bx, bx / jnz / inc bx   (none: 1)
    a.label('dh_budget')
    a.b(0x51, 0x52)                                          # push cx dx       missing, mode
    a.b(0x2e, 0xa0); a.word('rules_table', G_REST_FIXED); a.b(0x32, 0xe4)   # mov al, cs:[fixed] / xor ah, ah
    a.b(0xf7, 0xe3, 0x8b, 0xc8)                              # mul bx / mov cx, ax   fixed * budget
    a.b(0x5a, 0x80, 0xfa, REST_HEAL['fixed_only'])           # pop dx / cmp dl, 3
    a.short(0x74, 'dh_sum')                                  # je dh_sum
    a.b(0x2e, 0x8b, 0x84); a.word('day_left')                # mov ax, cs:[si+day_left]
    a.b(0x3b, 0xc3); a.short(0x76, 'dh_left'); a.b(0x8b, 0xc3)   # cmp ax, bx / jbe / mov ax, bx
    a.label('dh_left')
    a.b(0x53, 0x32, 0xff, 0x2e, 0x8a, 0x1e); a.word('rules_table', G_REST_ENDURANCE)   # push bx / xor bh,bh / mov bl, cs:[endurance]
    a.b(0xf7, 0xe3, 0x5b, 0x03, 0xc8)                        # mul bx / pop bx / add cx, ax
    a.label('dh_sum')
    a.b(0xb8, 100, 0x00, 0xf7, 0xe3, 0x8b, 0xd8)             # mov ax, 100 / mul bx / mov bx, ax   100 * budget
    a.b(0x8b, 0xc1, 0x59)                                    # mov ax, cx / pop cx   the share, missing
    a.b(0xf7, 0xe1, 0xf7, 0xf3)                              # mul cx / div bx   missing * share / (100 * budget)
    a.b(0x5b)                                                # pop bx
    a.b(0x0b, 0xc0); a.short(0x75, 'dh_amount'); a.b(0x40)   # or ax, ax / jnz / inc ax   at least 1
    a.label('dh_amount')
    a.b(0x8b, 0xc8)                                          # mov cx, ax
    a.label('dh_set')
    a.b(0x89, 0x4e, 0xfe)                                    # mov [bp-2], cx   the game's bx: the HP added at 11CE
    a.b(0x5e, 0x5a, 0x59, 0x58)                              # pop si dx cx ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # colour (1000:08D6, A419, A3CF): replaces mov ax,[si+20h] / mov ax,[di+20h] where the map icon is chosen:
    # ax = the colour picked for that knight (the icon sprite number is ax + an offset)
    a.label('rules_colour_di')
    a.b(0x83, 0x3e, 0xa0, 0xcc, 0x00); a.short(0x75, 'x38_ci_base')   # D38: on foot's frames only when neither flag is set
    a.b(0x83, 0x3e, 0x9e, 0xcc, 0x00); a.short(0x75, 'x38_ci_base')
    a.near(0xe8, 'horse_of'); a.b(0x0a, 0xc0); a.short(0x74, 'x38_ci_base')
    a.near(0xe8, 'horse_riding'); a.short(0x73, 'x38_ci_base')   # the helmet until it moves, and when it has stood a while
    a.b(0x8b, 0x5d, 0x20, 0x83, 0xfb, 0x04); a.short(0x77, 'x38_ci_base')
    a.b(0xfe, 0xc8, 0xb2, 0x05, 0xf6, 0xe2, 0x05, HORSE_MAP_BASE, 0x00)   # dec al / mov dl, 5 / mul dl / add ax, base
    a.b(0x2e, 0x02, 0x87); a.word('rules_table', G_COLOURS); a.near(0xe9, 'rules_done')   # add al, cs:[bx+colours]
    a.label('x38_ci_base')
    a.b(0x8b, 0x5d, 0x20)                                    # mov bx, [di+20h]
    a.short(0xeb, 'colour')                                  # jmp colour
    a.label('rules_colour_si')
    a.b(0x8b, 0x5c, 0x20)                                    # mov bx, [si+20h]
    a.label('colour')
    a.b(0x83, 0xfb, 0x04)                                    # cmp bx, 4
    a.short(0x77, 'colour_end')                              # ja colour_end     not a knight: unchanged
    a.b(0x2e, 0x8a, 0x87); a.word('rules_table', G_COLOURS)  # mov al, cs:[bx+colours]
    a.b(0x32, 0xe4)                                          # xor ah, ah
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('colour_end')
    a.b(0x8b, 0xc3)                                          # mov ax, bx
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # place (1000:0734): replaces the check that villages 15h-18h react only to their own knight; ax = place id,
    # di = record. ZF = 1: the place reacts (any other place, every village with village_heal_where = any, or the
    # knight's home village); ZF = 0: skip it
    a.label('rules_place')
    a.b(0x3d, 0x15, 0x00)                                    # cmp ax, 15h
    a.short(0x72, 'place_yes')                               # jb place_yes
    a.b(0x3d, 0x18, 0x00)                                    # cmp ax, 18h
    a.short(0x77, 'place_yes')                               # ja place_yes
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_VILLAGE_ANY); a.b(0x00)   # cmp byte cs:[village_any], 0
    a.short(0x75, 'place_yes')                               # jne place_yes
    a.b(0x8b, 0x5d, 0x20, 0x83, 0xfb, 0x04)                  # mov bx, [di+20h] / cmp bx, 4
    a.short(0x77, 'place_no')                                # ja place_no
    a.b(0x2e, 0x8a, 0x9f); a.word('rules_table', G_HOMES)    # mov bl, cs:[bx+homes]     FFh for a computer knight
    a.b(0x32, 0xff, 0x83, 0xc3, 0x15)                        # xor bh, bh / add bx, 15h
    a.b(0x3b, 0xc3)                                          # cmp ax, bx
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags
    a.label('place_yes')
    a.b(0x3b, 0xc0)                                          # cmp ax, ax
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags
    a.label('place_no')
    a.b(0x0b, 0xe4)                                          # or sp, sp     ZF = 0
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # fate (rules.FATE_HOOKS): replaces a call to a random routine. Checkpoint first (save modes); with
    # prevent_savescumming the game's random state is set from this kind's stream, which advances only here; then
    # the call is done by turning the interrupt frame into a call frame (return to the site + 3)
    a.label('rules_fate')
    a.b(0x50, 0x51, 0x52, 0x56)                              # push ax cx dx si
    a.b(0xbe); a.word('fate_sites')                          # mov si, fate_sites
    a.label('fate_find')
    a.b(0x2e, 0x8b, 0x04, 0x3b, 0x46, 0x02)                  # mov ax, cs:[si] / cmp ax, [bp+2]
    a.short(0x74, 'fate_found')                              # je fate_found
    a.b(0x83, 0xc6, 0x06)                                    # add si, 6
    a.short(0xeb, 'fate_find')                               # jmp fate_find
    a.label('fate_found')
    a.b(0x2e, 0x8b, 0x44, 0x02)                              # mov ax, cs:[si+2]       the routine
    a.b(0x2e, 0xa3); a.word('fate_target')                   # mov cs:[fate_target], ax
    a.b(0x2e, 0x8b, 0x5c, 0x04)                              # mov bx, cs:[si+4]       stream * 2
    a.near(0xe8, 'fate_prepare')                             # checkpoint and seed this stream
    a.b(0x5e, 0x5a, 0x59, 0x58, 0x5b, 0x5d)                  # pop si dx cx ax / pop bx / pop bp
    a.b(0x50, 0x55, 0x8b, 0xec, 0x50)                        # push ax (room) / push bp / mov bp, sp / push ax
    a.b(0x8b, 0x46, 0x04, 0x40)                              # mov ax, [bp+4] / inc ax          site + 3
    a.b(0x87, 0x46, 0x08, 0x87, 0x46, 0x06)                  # xchg ax, [bp+8] / xchg ax, [bp+6]   flags, CS up
    a.b(0x89, 0x46, 0x04)                                    # mov [bp+4], ax
    a.b(0x2e, 0xa1); a.word('fate_target')                   # mov ax, cs:[fate_target]
    a.b(0x89, 0x46, 0x02)                                    # mov [bp+2], ax
    a.b(0x58, 0x5d, 0xcf)                                    # pop ax / pop bp / iret   -> the routine

    # fate_prepare: bx = stream * 2, DS = game data; clobbers ax, cx, dx. Also used by the new curse rolls.
    a.label('fate_prepare')
    a.near(0xe8, 'checkpoint')                               # call checkpoint
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_FATE); a.b(0x00)   # cmp byte cs:[fate], 0
    a.short(0x74, 'fate_call')                               # je fate_call
    a.b(0x2e, 0x8b, 0x87); a.word('fate_state')              # mov ax, cs:[bx+fate_state]
    a.b(0xb9, 0x55, 0x62, 0xf7, 0xe1)                        # mov cx, 25173 / mul cx
    a.b(0x05, 0x19, 0x36)                                    # add ax, 13849
    a.short(0x75, 'fate_seed')                               # jnz fate_seed
    a.b(0x40)                                                # inc ax                  never 0 (the LFSR stays 0)
    a.label('fate_seed')
    a.b(0x2e, 0x89, 0x87); a.word('fate_state')              # mov cs:[bx+fate_state], ax
    a.b(0xa3, RANDOM_STATE & 0xff, RANDOM_STATE >> 8)        # mov [0E22Fh], ax
    a.label('fate_call')
    a.b(0xc3)                                                # ret

    # fate_init (from init, a game's or practice's knight set-up, before any save of it): streams not yet in use start
    # from the game's random state, so that a save made before a stream's first roll fixes that roll too. DS = game data
    a.label('fate_init')
    a.b(0x50, 0x53, 0x51, 0x52)                              # push ax bx cx dx
    a.b(0xa1, RANDOM_STATE & 0xff, RANDOM_STATE >> 8)        # mov ax, [0E22Fh]
    a.b(0x33, 0xdb)                                          # xor bx, bx
    a.label('fate_i_stream')
    a.b(0x2e, 0x83, 0xbf); a.word('fate_state'); a.b(0x00)   # cmp word cs:[bx+fate_state], 0
    a.short(0x75, 'fate_i_next')                                 # jne fate_i_next
    a.b(0xb9, 0x55, 0x62, 0xf7, 0xe1)                        # mov cx, 25173 / mul cx
    a.b(0x05, 0x19, 0x36)                                    # add ax, 13849
    a.short(0x75, 'fate_i_store')                                # jnz fate_i_store
    a.b(0x40)                                                # inc ax
    a.label('fate_i_store')
    a.b(0x2e, 0x89, 0x87); a.word('fate_state')              # mov cs:[bx+fate_state], ax
    a.label('fate_i_next')
    a.b(0x83, 0xc3, 0x02, 0x83, 0xfb, 2 * FATE_STREAMS)      # add bx, 2 / cmp bx, streams * 2
    a.short(0x72, 'fate_i_stream')                               # jb fate_i_stream
    a.b(0x5a, 0x59, 0x5b, 0x58, 0xc3)                        # pop dx cx bx ax / ret

    # checkpoint: in autosave_only and none, the token in memory must match SAVEHOOK.CHK (else a manual save was
    # loaded: refuse); then a new token into both. Any DS; keeps all registers
    a.label('checkpoint')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_SAVE_MODE); a.b(AUTO_ONLY)   # cmp byte cs:[save_mode], 1
    a.short(0x74, 'chk')                                     # je chk
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_SAVE_MODE); a.b(NO_SAVES)    # cmp byte cs:[save_mode], 3
    a.short(0x74, 'chk')                                     # je chk
    a.b(0xc3)                                                # ret
    a.label('chk')
    a.b(0x50, 0x53, 0x51, 0x52, 0x1e, 0x06, 0x0e, 0x1f)      # push ax bx cx dx ds es / push cs / pop ds
    a.b(0xb8, 0x00, 0x3d, 0xba); a.word('chk_path')          # mov ax, 3D00h / mov dx, chk_path
    a.b(0xcd, 0x21)                                          # int 21h     open
    a.short(0x73, 'chk_read')                                # jnc chk_read
    a.b(0x3d, 0x02, 0x00)                                    # cmp ax, 2   only a file that is not there: a new token
    a.short(0x74, 'chk_new')                                 # je chk_new
    a.near(0xe9, 'refuse')                                   # jmp refuse  any other failure could hide a loaded save
    a.label('chk_read')
    a.b(0x8b, 0xd8, 0xb4, 0x3f, 0xb9, 0x04, 0x00, 0xba); a.word('file_token')   # mov bx, ax / mov ah, 3Fh / mov cx, 4 / mov dx, file_token
    a.b(0xcd, 0x21)                                          # int 21h     read
    a.b(0x9c, 0x50, 0xb4, 0x3e, 0xcd, 0x21)                  # pushf / push ax / mov ah, 3Eh / int 21h (close)
    a.short(0x72, 'chk_refuse')                              # jc chk_refuse   refuse never returns: the stack can stay
    a.b(0x58, 0x9d)                                          # pop ax / popf     the read's result
    a.short(0x72, 'chk_refuse')                              # jc chk_refuse
    a.b(0x3d, 0x04, 0x00)                                    # cmp ax, 4   a short file is no token
    a.short(0x75, 'chk_refuse')                              # jne chk_refuse
    for add in (0, 2):
        a.b(0xa1); a.word('file_token', add); a.b(0x3b, 0x06); a.word('token', add)   # mov ax, [file_token] / cmp ax, [token]
        a.short(0x75, 'chk_refuse')                          # jne chk_refuse
    a.label('chk_new')
    a.near(0xe8, 'new_token')                                # call new_token
    a.near(0xe8, 'write_token')                              # call write_token
    a.short(0x72, 'chk_refuse')                              # jc chk_refuse
    a.b(0x07, 0x1f, 0x5a, 0x59, 0x5b, 0x58, 0xc3)            # pop es ds dx cx bx ax / ret
    a.label('chk_refuse')
    a.near(0xe9, 'refuse')                                   # jmp refuse

    a.label('new_token')                                     # DS = CS: token = BIOS ticks, counter + 1
    a.b(0x06, 0xb8, 0x40, 0x00, 0x8e, 0xc0, 0x26, 0xa1, 0x6c, 0x00, 0x07)   # push es / mov ax, 40h / mov es, ax / mov ax, es:[6Ch] / pop es
    a.b(0xa3); a.word('token')                               # mov [token], ax
    a.b(0xff, 0x06); a.word('token', 2)                      # inc word [token+2]
    a.b(0xc3)                                                # ret

    a.label('write_token')                                   # DS = CS: SAVEHOOK.CHK = token, CF = 1 if it failed (clobbers ax bx cx dx)
    a.b(0xb4, 0x3c, 0x33, 0xc9, 0xba); a.word('chk_path')    # mov ah, 3Ch / xor cx, cx / mov dx, chk_path
    a.b(0xcd, 0x21)                                          # int 21h     create
    a.short(0x72, 'write_end')                               # jc write_end
    a.b(0x8b, 0xd8, 0xb4, 0x40, 0xb9, 0x04, 0x00, 0xba); a.word('token')   # mov bx, ax / mov ah, 40h / mov cx, 4 / mov dx, token
    a.b(0xcd, 0x21)                                          # int 21h     write
    a.b(0x9c, 0x50, 0xb4, 0x3e, 0xcd, 0x21)                  # pushf / push ax / mov ah, 3Eh / int 21h (close)
    a.short(0x72, 'write_shut')                              # jc write_shut
    a.b(0x58, 0x9d)                                          # pop ax / popf     the write's result
    a.short(0x72, 'write_end')                               # jc write_end
    a.b(0x3d, 0x04, 0x00)                                    # cmp ax, 4         fewer: CF = 1
    a.label('write_end')
    a.b(0xc3)                                                # ret
    a.label('write_shut')
    a.b(0x58, 0x9d, 0xf9, 0xc3)                              # pop ax / popf / stc / ret

    a.label('accept')                                        # DS = CS, after an automatic save's wait: its token
    a.b(0x80, 0x3e); a.word('rules_table', G_SAVE_MODE); a.b(AUTO_ONLY)   # cmp byte [save_mode], 1
    a.short(0x75, 'accept_end')                              # jne accept_end
    a.near(0xe8, 'write_token')                              # call write_token
    a.short(0x73, 'accept_end')                              # jnc accept_end
    a.near(0xe9, 'refuse')                                   # jmp refuse
    a.label('accept_end')
    a.b(0xc3)                                                # ret

    a.label('refuse')                                        # a forbidden save was loaded: show a name, stop
    a.b(0x0e, 0x1f)                                          # push cs / pop ds
    a.near(0xe8, 'mcb')                                      # call mcb
    a.b(0xbe); a.word('auto_name')                           # mov si, auto_name
    a.b(0x80, 0x3e); a.word('rules_table', G_SAVE_MODE); a.b(AUTO_ONLY)   # cmp byte [save_mode], 1
    a.short(0x74, 'refuse_name')                             # je refuse_name
    a.b(0xbe); a.word('none_name')                           # mov si, none_name
    a.label('refuse_name')
    a.near(0xe8, 'set_name')                                 # call set_name
    a.near(0xe8, 'refresh')                                  # call refresh
    a.b(0xfb)                                                # sti
    a.label('refuse_halt')
    a.b(0xf4)                                                # hlt
    a.short(0xeb, 'refuse_halt')                             # jmp refuse_halt

    # sell (1000:CC11): item screen click; replaces mov bx,es:[bp+12h] / mov cx,es:[bp+10h] (the hotspot's field and
    # type; the game's bp is at [bp]). At the merchant (mode 5, [0ED92h]) with merchant_selling on, a click on the
    # knight's own daggers (type 3, field 34h), weapon or armour (type 2, fields 40h, 42h) sells one for half the
    # shop price: the weapon goes back to the long sword, the armour to padded (minus its hit points, at least 1).
    # ZF = 1: sold, the site jumps to 1000:CFE3 (sound, redraw: the redraw recalculates max HP and movement,
    # 1000:C29B); ZF = 0: the game goes on as before
    a.label('rules_sell')
    a.b(0x56, 0x8b, 0x76, 0x00)                              # push si / mov si, [bp]     the game's bp
    a.b(0x26, 0x8b, 0x5c, 0x12, 0x26, 0x8b, 0x4c, 0x10)      # mov bx, es:[si+12h] / mov cx, es:[si+10h]
    a.b(0x5e, 0x89, 0x5e, 0xfe)                              # pop si / mov [bp-2], bx   (returned as bx)
    a.b(0x50, 0x56)                                          # push ax / push si
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_SELLING); a.b(0x00)   # cmp byte cs:[selling], 0
    a.short(0x74, 'sell_no')                                 # je sell_no
    a.b(0x83, 0x3e, 0x92, 0xed, 0x05)                        # cmp word [0ED92h], 5     the merchant
    a.short(0x75, 'sell_no')                                 # jne sell_no
    a.b(0x8b, 0x36, 0x88, 0xed)                              # mov si, [0ED88h]          the knight
    a.b(0x8a, 0xc1, 0x24, 0x0f)                              # mov al, cl / and al, 0Fh  hotspot type
    a.b(0x83, 0xfb, 0x34)                                    # cmp bx, 34h
    a.short(0x75, 'sell_kit')                                # jne sell_kit
    a.b(0x3c, 0x03)                                          # cmp al, 3
    a.short(0x75, 'sell_no')                                 # jne sell_no
    a.b(0x80, 0x7c, 0x34, 0x00)                              # cmp byte [si+34h], 0
    a.short(0x7e, 'sell_no')                                 # jle sell_no
    a.b(0xfe, 0x4c, 0x34)                                    # dec byte [si+34h]
    a.b(0x2e, 0xa1); a.word('rules_table', G_SELL)           # mov ax, cs:[dagger price]
    a.short(0xeb, 'sell_gold')                               # jmp sell_gold
    a.label('sell_no')
    a.b(0x5e, 0x58, 0x0b, 0xe4)                              # pop si / pop ax / or sp, sp     ZF = 0
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags
    a.label('sell_kit')
    a.b(0x3c, 0x02)                                          # cmp al, 2
    a.short(0x75, 'sell_no')                                 # jne sell_no
    a.b(0x83, 0xfb, 0x40)                                    # cmp bx, 40h
    a.short(0x74, 'sell_weapon')                             # je sell_weapon
    a.b(0x83, 0xfb, 0x42)                                    # cmp bx, 42h
    a.short(0x74, 'sell_arm')                                # je sell_arm
    a.b(0x83, 0xfb, HORSE_FIELD)                             # cmp bx, 36h     D40: the knight's own horse
    a.short(0x75, 'sell_no')                                 # jne sell_no
    a.near(0xe9, 'sell_horse')
    a.label('sell_arm')
    a.b(0x8b, 0x5c, 0x42, 0x83, 0xeb, 0x1c)                  # mov bx, [si+42h] / sub bx, 1Ch   chain, plate, battle
    a.b(0x83, 0xfb, 0x02)                                    # cmp bx, 2
    a.short(0x77, 'sell_no')                                 # ja sell_no              padded: nothing to sell
    a.b(0xd1, 0xe3)                                          # shl bx, 1
    a.b(0x2e, 0x8b, 0x87); a.word('rules_table', G_ARMOUR_HP + 2)   # mov ax, cs:[bx+armour_hp+2]
    a.b(0x29, 0x44, 0x38)                                    # sub [si+38h], ax
    a.b(0x83, 0x7c, 0x38, 0x01)                              # cmp word [si+38h], 1
    a.short(0x7d, 'sell_armour')                             # jge sell_armour
    a.b(0xc7, 0x44, 0x38, 0x01, 0x00)                        # mov word [si+38h], 1
    a.label('sell_armour')
    a.b(0xc7, 0x44, 0x42, 0x1b, 0x00)                        # mov word [si+42h], 1Bh   padded
    a.b(0x2e, 0x8b, 0x87); a.word('rules_table', G_SELL + 6)   # mov ax, cs:[bx+armour prices]
    a.short(0xeb, 'sell_gold')                               # jmp sell_gold
    a.label('sell_weapon')
    a.b(0x8b, 0x5c, 0x40, 0x83, 0xeb, 0x17)                  # mov bx, [si+40h] / sub bx, 17h   broadsword, claymore
    a.b(0x83, 0xfb, 0x01)                                    # cmp bx, 1
    a.short(0x77, 'sell_no')                                 # ja sell_no     long sword, Sword of Sharpness: no
    a.b(0xd1, 0xe3)                                          # shl bx, 1
    a.b(0xc7, 0x44, 0x40, 0x16, 0x00)                        # mov word [si+40h], 16h   long sword
    a.b(0x2e, 0x8b, 0x87); a.word('rules_table', G_SELL + 2)   # mov ax, cs:[bx+weapon prices]
    a.label('sell_gold')
    a.b(0x01, 0x44, 0x32)                                    # add [si+32h], ax
    a.short(0x71, 'sell_yes')                                # jno sell_yes     D43: max_gold is checked as the merchant is left
    a.b(0xc7, 0x44, 0x32, 0xff, 0x7f)                        # mov word [si+32h], 7FFFh
    a.label('sell_yes')
    a.b(0x5e, 0x58, 0x3b, 0xe4)                              # pop si / pop ax / cmp sp, sp    ZF = 1
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags
    a.label('sell_horse')                                    # D40: half the price, no horse any more
    a.b(0x57, 0x8b, 0xfe); a.near(0xe8, 'horse_of'); a.b(0x0a, 0xc0); a.short(0x75, 'sell_h_on')
    a.b(0x5f); a.near(0xe9, 'sell_no')
    a.label('sell_h_on')
    a.near(0xe8, 'knight_no'); a.b(0x2e, 0xc6, 0x87); a.word('horse_k'); a.b(0x00, 0x5f)
    a.b(0x32, 0xe4, 0x8b, 0xd8, 0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('rules_table', G_HORSE_PRICE - 2); a.b(0xd1, 0xe8)
    a.near(0xe9, 'sell_gold')

    # practice (D11): 1000:011F replaces the set-up of the second knight (si = 6D00h: type 6, controller 1, +20h = 2),
    # 1000:2033 InitPractice's controller (di = 6D00h, 1). With one player chosen it is a computer knight instead
    # (type 8, controller 4, +20h = 4, as 1000:1C75 makes them)
    a.label('rules_practice_si')
    a.near(0xe8, 'practice_mode')                            # call practice_mode     D12: 3-4 knights?
    a.b(0x83, 0x3e, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8, 0x01)   # cmp word [0940h], 1
    a.short(0x74, 'practice_ai')                             # je practice_ai
    a.b(0xc6, 0x44, 0x35, 0x06, 0xc6, 0x44, 0x09, 0x01)      # mov byte [si+35h], 6 / mov byte [si+9], 1
    a.b(0xc7, 0x44, 0x20, 0x02, 0x00)                        # mov word [si+20h], 2
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('practice_ai')
    a.b(0xc6, 0x44, 0x35, 0x08, 0xc6, 0x44, 0x09, 0x04)      # mov byte [si+35h], 8 / mov byte [si+9], 4
    a.b(0xc7, 0x44, 0x20, 0x04, 0x00)                        # mov word [si+20h], 4
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('rules_practice_di')
    a.b(0xc6, 0x45, 0x09, 0x01)                              # mov byte [di+9], 1
    a.b(0x83, 0x3e, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8, 0x01)   # cmp word [0940h], 1
    a.short(0x75, 'practice_end')                            # jne practice_end
    a.b(0xc6, 0x45, 0x09, 0x04)                              # mov byte [di+9], 4
    a.label('practice_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # sound_rate (K36, K37; 1000:9537, replaces mov bx,6 before the call to CT-VOICE.DRV): ES:DI = the VOC data block
    # of the sample in the page copied for this sound, DS = the game's, [SOUND_LAST_ID] = the id asked for. The id's
    # time constant (0 = the file's own) goes to the block's header. An id in the slice list (id, start, length; ends
    # with 0) plays one part of the sample: a new block header (type 1, length + 2, time constant, 0) is written just
    # before the part, an end mark after it, and DI moves there. The page is copied afresh for every sound
    a.label('rules_sound_rate')
    a.b(0x50, 0x51, 0x56, 0xfc)                              # push ax / push cx / push si / cld
    a.b(0x8a, 0x1e, SOUND_LAST_ID & 0xff, SOUND_LAST_ID >> 8)   # mov bl, [SOUND_LAST_ID]
    a.b(0x32, 0xff)                                          # xor bh, bh
    a.b(0x8a, 0x8f, SOUND_RATES & 0xff, SOUND_RATES >> 8)    # mov cl, [bx + SOUND_RATES]
    a.b(0x80, 0xfb, 180)                                     # cmp bl, 180            the table has ids 0-179
    a.short(0x73, 'sound_own')                               # jae sound_own
    a.b(0x0a, 0xc9)                                          # or cl, cl
    a.short(0x75, 'sound_slices')                            # jnz sound_slices
    a.label('sound_own')
    a.b(0x26, 0x8a, 0x4d, 0x04)                              # mov cl, es:[di+4]      the file's own rate
    a.label('sound_slices')
    a.b(0xbe, SOUND_SLICES & 0xff, SOUND_SLICES >> 8)        # mov si, SOUND_SLICES
    a.label('sound_next')
    a.b(0xac, 0x0a, 0xc0)                                    # lodsb / or al, al
    a.short(0x74, 'sound_set')                               # jz sound_set            not in the list: the whole sample
    a.b(0x3a, 0xc3)                                          # cmp al, bl
    a.short(0x74, 'sound_part')                              # je sound_part
    a.b(0x83, 0xc6, 0x04)                                    # add si, 4
    a.short(0xeb, 'sound_next')                              # jmp sound_next
    a.label('sound_part')
    a.b(0xad, 0x03, 0xf8)                                    # lodsw / add di, ax      the new header: 6 bytes before the part
    a.b(0xad, 0x8b, 0xd8)                                    # lodsw / mov bx, ax      bx = length
    a.b(0x26, 0xc6, 0x41, 0x06, 0x00)                        # mov byte es:[bx+di+6], 0    end mark after the part
    a.b(0x05, 0x02, 0x00)                                    # add ax, 2               block length: time constant, pack, data
    a.b(0x26, 0xc6, 0x05, 0x01)                              # mov byte es:[di], 1     block type 1: sound data
    a.b(0x26, 0x89, 0x45, 0x01)                              # mov es:[di+1], ax       length, low 16 bits
    a.b(0x26, 0xc6, 0x45, 0x03, 0x00)                        # mov byte es:[di+3], 0   length, high byte
    a.b(0x26, 0xc6, 0x45, 0x05, 0x00)                        # mov byte es:[di+5], 0   8-bit samples
    a.label('sound_set')
    a.b(0x26, 0x88, 0x4d, 0x04)                              # mov es:[di+4], cl       the time constant
    a.b(0x5e, 0x59, 0x58)                                    # pop si / pop cx / pop ax
    a.b(0xc7, 0x46, 0xfe, 0x06, 0x00)                        # mov word [bp-2], 6      the game's bx: the driver's function
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # sound_play (D65; 1000:5979, replaces cmp word [8645h],3 at the start of the sound routine, after it has saved
    # every register): al = the sound id. With Amiga sound on (amiga_on, from AMIGASND.FLG) and a program for the id
    # in the SoundFont (amiga_prog), the sound goes to DOSBox-X's synth device as MIDI: UART mode (ignored when already
    # in it), "program change (preset), note on (key, 127)" on the next of four channels, and the routine's own end
    # (59A0). A new note on a channel stops the sound that channel was playing (the SoundFont's exclusive class), so
    # at most four sounds play, as on the Amiga. The program change goes with every note: after a state is loaded the
    # synth has forgotten it. Interrupts are off here (int 63h), so the game's music driver cannot cut in.
    # Otherwise: the compare, with its flags
    a.label('rules_sound_play')
    a.b(0x2e, 0x80, 0x3e); a.word('amiga_on'); a.b(0x00)     # cmp byte cs:[amiga_on], 0
    a.short(0x74, 'sp_normal')                               # je sp_normal
    a.b(0x3c, 180)                                           # cmp al, 180
    a.short(0x73, 'sp_normal')                               # jae sp_normal
    a.b(0x8a, 0xd8, 0x32, 0xff)                              # mov bl, al / xor bh, bh
    a.b(0x2e, 0x8a, 0x9f); a.word('amiga_prog')              # mov bl, cs:[bx + amiga_prog]   the program, 0 = none
    a.b(0x0a, 0xdb)                                          # or bl, bl
    a.short(0x74, 'sp_normal')                               # jz sp_normal
    a.b(0x2e, 0x8a, 0x26); a.word('amiga_slot')              # mov ah, cs:[amiga_slot]
    a.b(0xfe, 0xc4, 0x80, 0xe4, 0x03)                        # inc ah / and ah, 3            the next channel
    a.b(0x2e, 0x88, 0x26); a.word('amiga_slot')              # mov cs:[amiga_slot], ah
    a.b(0xb1, 0x00, 0x8a, 0xeb)                              # mov cl, 0 / mov ch, bl        preset 0
    a.b(0x80, 0xc5, AMIGA_FIRST_KEY - 1)                     # add ch, 19                    key = program + 19
    a.b(0x80, 0xfb, AMIGA_PER_PRESET)                        # cmp bl, 100
    a.short(0x76, 'sp_send')                                 # jbe sp_send
    a.b(0xb1, 0x01, 0x80, 0xed, AMIGA_PER_PRESET)            # mov cl, 1 / sub ch, 100       preset 1, key = program - 81
    a.label('sp_send')
    a.b(0xba, 0x31, 0x03, 0xb0, 0x3f, 0xee)                  # mov dx, 331h / mov al, 3Fh / out dx, al   UART mode
    a.b(0x4a, 0xec)                                          # dec dx / in al, dx            its answer, if there is one
    a.b(0xb0, 0xc0, 0x0a, 0xc4, 0xee)                        # mov al, C0h / or al, ah / out dx, al   program change
    a.b(0x8a, 0xc1, 0xee)                                    # mov al, cl / out dx, al
    a.b(0xb0, 0x90, 0x0a, 0xc4, 0xee)                        # mov al, 90h / or al, ah / out dx, al   note on
    a.b(0x8a, 0xc5, 0xee)                                    # mov al, ch / out dx, al
    a.b(0xb0, 0x7f, 0xee)                                    # mov al, 7Fh / out dx, al
    a.b(0xc7, 0x46, 0x02, 0xa0, 0x59)                        # mov word [bp+2], 59A0h        the routine's end
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('sp_normal')
    a.b(0x83, 0x3e, 0x45, 0x86, 0x03)                        # cmp word [8645h], 3
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # amiga_check (D65): DS = CS: amiga_on = 1 if AMIGASND.FLG is there, else 0. Called when SAVEHOOK starts and at
    # every automatic save's numbering, so a loaded state follows the installation as it is now
    a.label('amiga_check')
    a.b(0x50, 0x53, 0x52)                                    # push ax / push bx / push dx
    a.b(0xb8, 0x00, 0x3d, 0xba); a.word('amiga_path')        # mov ax, 3D00h / mov dx, amiga_path
    a.b(0xcd, 0x21)                                          # int 21h     open
    a.b(0xc6, 0x06); a.word('amiga_on'); a.b(0x00)           # mov byte [amiga_on], 0   (flags stay)
    a.short(0x72, 'ac_end')                                  # jc ac_end
    a.b(0xc6, 0x06); a.word('amiga_on'); a.b(0x01)           # mov byte [amiga_on], 1
    a.b(0x8b, 0xd8, 0xb4, 0x3e, 0xcd, 0x21)                  # mov bx, ax / mov ah, 3Eh / int 21h   close
    a.label('ac_end')
    a.b(0x5a, 0x5b, 0x58, 0xc3)                              # pop dx / pop bx / pop ax / ret

    # hoard_clear (K18, 1000:1DC0; replaces mov dx,0 before the new game's hoard rolls): clear the dragon's item
    # table and gold, which would otherwise keep what earlier games in this session put there
    a.label('rules_hoard_clear')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_HOARD); a.b(HOARD_MODES['keep'])   # cmp byte cs:[hoard], keep
    a.short(0x74, 'hoard_dx')                                # je hoard_dx           the original: no reset
    a.b(0x50, 0x51, 0x57, 0x06, 0x1e, 0x07)                  # push ax cx di es / push ds / pop es
    a.b(0xbf, DRAGON_HOARD & 0xff, DRAGON_HOARD >> 8)        # mov di, 6EE8h
    a.b(0x33, 0xc0, 0xb9, 0x0c, 0x00, 0xfc, 0xf3, 0xab)      # xor ax, ax / mov cx, 12 / cld / rep stosw
    a.b(0xa3, DRAGON_GOLD & 0xff, DRAGON_GOLD >> 8)          # mov [6E58h], ax
    a.b(0x07, 0x5f, 0x59, 0x58)                              # pop es di cx ax
    a.label('hoard_dx')
    a.b(0xba, 0x00, 0x00)                                    # mov dx, 0     (replaced instruction)
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # hoard_win (K18, 1000:0D25; replaces mov si,6E26h before the dragon loots the knight it beat): with
    # dragon_hoard = grows, at a 50 % chance one more magic item (rolled against DS:E365 as 1000:BA5F does; a second
    # Sword of Sharpness is rolled again) and always 0-9 gold into the hoard
    a.label('rules_hoard_win')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_HOARD); a.b(HOARD_MODES['grows'])  # cmp byte cs:[hoard], grows
    a.short(0x75, 'win_si')                                  # jne win_si
    a.b(0x50, 0x51, 0x52, 0x56)                              # push ax cx dx si
    a.near(0xe8, 'game_random')                              # call game_random
    a.b(0xa8, 0x01)                                          # test al, 1         an item at 50 %
    a.short(0x74, 'win_gold')                                # jz win_gold
    a.b(0xb2, 0x08)                                          # mov dl, 8          tries
    a.label('win_roll')
    a.near(0xe8, 'game_random')                              # call game_random
    a.b(0x25, 0x7f, 0x00, 0x3d, 0x64, 0x00)                  # and ax, 7Fh / cmp ax, 100
    a.short(0x7c, 'win_table')                               # jl win_table
    a.b(0x2d, 0x1b, 0x00)                                    # sub ax, 27          the game's 0-100 roll
    a.label('win_table')
    a.b(0xbe, 0x65, 0xe3, 0xb9, 0x0a, 0x00)                  # mov si, 0E365h / mov cx, 10
    a.label('win_find')
    a.b(0x3b, 0x04)                                          # cmp ax, [si]
    a.short(0x7e, 'win_item')                                # jle win_item
    a.b(0x83, 0xc6, 0x04)                                    # add si, 4
    a.short(0xe2, 'win_find')                                # loop win_find
    a.b(0xb8, 0x00, 0x00)                                    # mov ax, 0           (no limit matched: a potion)
    a.short(0xeb, 'win_add')                                 # jmp win_add
    a.label('win_item')
    a.b(0x8b, 0x44, 0x02)                                    # mov ax, [si+2]      the item
    a.b(0x3d, 0x04, 0x00)                                    # cmp ax, 4           the Sword of Sharpness?
    a.short(0x75, 'win_add')                                 # jne win_add
    a.b(0x83, 0x3e, 0x06, 0x6f, 0x00)                        # cmp word [6F06h], 0  already in the game?
    a.short(0x74, 'win_sword')                               # je win_sword
    a.b(0xfe, 0xca)                                          # dec dl
    a.short(0x75, 'win_roll')                                # jnz win_roll
    a.b(0x33, 0xc0)                                          # xor ax, ax          enough tries: a potion
    a.short(0xeb, 'win_add')                                 # jmp win_add
    a.label('win_sword')
    a.b(0xc7, 0x06, 0x06, 0x6f, 0x01, 0x00)                  # mov word [6F06h], 1
    a.label('win_add')
    a.b(0x8b, 0xf0)                                          # mov si, ax
    a.b(0xfe, 0x84, DRAGON_HOARD & 0xff, DRAGON_HOARD >> 8)  # inc byte [si+6EE8h]
    a.label('win_gold')
    a.near(0xe8, 'game_random')                              # call game_random
    a.b(0x33, 0xd2, 0xb9, 0x0a, 0x00, 0xf7, 0xf1)            # xor dx, dx / mov cx, 10 / div cx   dx = 0-9
    a.b(0x01, 0x16, DRAGON_GOLD & 0xff, DRAGON_GOLD >> 8)    # add [6E58h], dx
    a.b(0x5e, 0x5a, 0x59, 0x58)                              # pop si dx cx ax
    a.label('win_si')
    a.b(0xbe, 0x26, 0x6e)                                    # mov si, 6E26h       (replaced instruction)
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    # game_random: ax = the game's next random word, as 1000:BF62 (state DS:E22F); keeps bx, cx
    a.label('game_random')
    a.b(0x53, 0x51, 0xa1, 0x2f, 0xe2, 0xb9, 0x08, 0x00)      # push bx cx / mov ax, [0E22Fh] / mov cx, 8
    a.label('gr_loop')
    a.b(0x8b, 0xd8, 0xd1, 0xcb, 0xd1, 0xcb, 0xd1, 0xcb)      # mov bx, ax / ror bx, 1 (x3)
    a.b(0x33, 0xd8, 0xd1, 0xdb, 0xd1, 0xdb, 0xd1, 0xd8)      # xor bx, ax / rcr bx, 1 / rcr bx, 1 / rcr ax, 1
    a.short(0xe2, 'gr_loop')                                 # loop gr_loop
    a.b(0xa3, 0x2f, 0xe2, 0x59, 0x5b, 0xc3)                  # mov [0E22Fh], ax / pop cx bx / ret

    # --- D12: practice with 3 or 4 knights, two teams ---
    # practice_mode: cs:[multi] = 3 or 4 when that many players were chosen, else 0. Knights 3 and 4 take the
    # joysticks that answer (A, then B), then the third key set (cs:[p3_ctl], cs:[p4_ctl]); with 4 chosen and no
    # joystick, 3 knights
    a.label('practice_mode')
    a.b(0x50, 0x53, 0x51, 0x52, 0x57)                        # push ax bx cx dx di
    a.b(0x2e, 0xc6, 0x06); a.word('multi'); a.b(0x00)        # mov byte cs:[multi], 0
    a.b(0x2e, 0xc6, 0x06); a.word('add_state'); a.b(0x00)    # mov byte cs:[add_state], 0
    a.b(0x8b, 0x1e, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8)   # mov bx, [0940h]
    a.b(0x83, 0xfb, 0x03)                                    # cmp bx, 3
    a.short(0x72, 'pm_end')                                  # jb pm_end
    a.b(0xbf); a.word('p3_ctl')                              # mov di, p3_ctl
    a.b(0xb4, 0x01)                                          # mov ah, 1         joystick A, x axis
    a.near(0xe8, 'joy_present'); a.short(0x72, 'pm_no_a')    # call joy_present / jc
    a.b(0x2e, 0xc6, 0x05, JOY_A_CONTROL, 0x47)               # mov byte cs:[di], 5 / inc di
    a.label('pm_no_a')
    a.b(0x83, 0xfb, 0x04); a.short(0x72, 'pm_no_b')          # cmp bx, 4 / jb   (3 chosen: no joystick B)
    a.b(0xb4, 0x04)                                          # mov ah, 4         joystick B, x axis
    a.near(0xe8, 'joy_present'); a.short(0x72, 'pm_no_b')
    a.b(0x2e, 0xc6, 0x05, JOY_B_CONTROL, 0x47)               # mov byte cs:[di], 6 / inc di
    a.label('pm_no_b')
    a.b(0x2e, 0xc6, 0x05, KEYS3_CONTROL, 0x47)               # mov byte cs:[di], 7 / inc di   (p4_ctl + 1: spare)
    a.b(0x8b, 0xc7, 0x2d); a.word('p3_ctl')                  # mov ax, di / sub ax, p3_ctl   the inputs found
    a.b(0x8b, 0xcb, 0x83, 0xe9, 0x02)                        # mov cx, bx / sub cx, 2        the knights wanted
    a.b(0x3b, 0xc1); a.short(0x76, 'pm_n'); a.b(0x8b, 0xc1)  # cmp ax, cx / jbe / mov ax, cx
    a.label('pm_n')
    a.b(0x04, 0x02, 0x2e, 0xa2); a.word('multi')             # add al, 2 / mov cs:[multi], al
    a.label('pm_end')
    a.b(0x5f, 0x5a, 0x59, 0x5b, 0x58, 0xc3)                  # pop di dx cx bx ax / ret

    # joy_present: ah = the port bit of an axis; CF = 0 if it answers (its bit falls), as 1000:82AA reads it
    a.label('joy_present')
    a.b(0xfa, 0xba, 0x01, 0x02, 0xee, 0x33, 0xc9)            # cli / mov dx, 201h / out dx, al / xor cx, cx
    a.label('jp_loop')
    a.b(0xec, 0x84, 0xc4)                                    # in al, dx / test al, ah
    a.short(0x74, 'jp_yes')                                  # jz jp_yes
    a.b(0x41, 0x81, 0xf9, JOY_PORT_LIMIT & 0xff, JOY_PORT_LIMIT >> 8)   # inc cx / cmp cx, limit
    a.short(0x72, 'jp_loop')                                 # jb jp_loop
    a.b(0xfb, 0xf9, 0xc3)                                    # sti / stc / ret
    a.label('jp_yes')
    a.b(0xfb, 0xf8, 0xc3)                                    # sti / clc / ret

    # practice_add (1000:203D, after InitPractice registered the second knight; replaces mov word [91Ch],6). Adds
    # the joystick knights one game call at a time: each call returns to the int 63h at 203B, which comes back here
    a.label('rules_practice_add')
    a.b(0x2e, 0xc7, 0x06); a.word('team_t0'); a.b(0x00, 0x00)   # mov word cs:[team_t0], 0   a new fight
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x74, 'pa_done')                                 # je pa_done
    a.b(0x2e, 0xa0); a.word('add_state')                     # mov al, cs:[add_state]
    a.b(0x2e, 0xfe, 0x06); a.word('add_state')               # inc byte cs:[add_state]
    a.b(0x3c, 0x00); a.short(0x74, 'pa_p3')                  # cmp al, 0 / je pa_p3
    a.b(0x3c, 0x01); a.short(0x74, 'pa_p3_run')              # cmp al, 1 / je pa_p3_run
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x04)        # cmp byte cs:[multi], 4
    a.short(0x75, 'pa_done')                                 # jne pa_done
    a.b(0x3c, 0x02); a.short(0x74, 'pa_p4')                  # cmp al, 2 / je pa_p4
    a.b(0x3c, 0x03); a.short(0x75, 'pa_done')                # cmp al, 3 / jne pa_done
    a.near(0xe9, 'pa_p4_run')                                # jmp pa_p4_run
    a.label('pa_done')
    a.b(0x2e, 0xc6, 0x06); a.word('add_state'); a.b(0x00)    # mov byte cs:[add_state], 0
    a.b(0xc7, 0x06, 0x1c, 0x09, 0x06, 0x00)                  # mov word [91Ch], 6     (replaced instruction)
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    for knight, colour, x, facing, bank in (('p3', 1, 0xfa, 3, 0x8933), ('p4', 3, 0x1e, 1, 0x8949)):
        rec = TEAM1[1] if knight == 'p3' else TEAM2[1]
        a.label('pa_' + knight)                              # as InitPractice's knights (1000:296E, 200F)
        a.b(0xbf, rec & 0xff, rec >> 8)                      # mov di, record
        a.b(0xc6, 0x45, 0x35, 0x06, 0x2e, 0xa0); a.word(knight + '_ctl')   # mov byte [di+35h], 6 / mov al, cs:[ctl]
        a.b(0x88, 0x45, 0x09)                                # mov [di+9], al   its input (practice_mode)
        a.b(0xc7, 0x45, 0x20, colour, 0x00)                  # mov word [di+20h], colour of its team
        a.b(0xc7, 0x45, 0x02, x & 0xff, x >> 8)              # mov word [di+2], x
        a.b(0xc7, 0x45, 0x04, 0x00, 0x00)                    # mov word [di+4], 0
        a.b(0xc7, 0x45, 0x06, 0x64, 0x00)                    # mov word [di+6], 100   (2998 picks the depth)
        a.b(0xc6, 0x45, 0x08, facing)                        # mov byte [di+8], facing
        a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x76, 0x1f)   # mov word cs:[call_target], 1F76h
        a.near(0xe9, 'pa_call')                              # jmp pa_call
        a.label('pa_' + knight + '_run')
        a.b(0xbf, rec & 0xff, rec >> 8)                      # mov di, record
        a.b(0xc7, 0x45, 0x18, bank & 0xff, bank >> 8)        # mov word [di+18h], its team's colour bank
        a.b(0xbe, 0xe4, 0x15)                                # mov si, 15E4h          standing script
        a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x98, 0x29)   # mov word cs:[call_target], 2998h
        a.near(0xe9, 'pa_call')                              # jmp pa_call
    a.label('pa_call')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x3b, 0x20)   # mov word cs:[call_ret], 203Bh (the int 63h)
    a.label('call_game')                                     # exit: call cs:[call_target], returning to cs:[call_ret]
    a.b(0x5b, 0x5d)                                          # pop bx / pop bp
    a.b(0x50, 0x55, 0x8b, 0xec, 0x50)                        # push ax (room) / push bp / mov bp, sp / push ax
    a.b(0x2e, 0xa1); a.word('call_ret')                      # mov ax, cs:[call_ret]
    a.b(0x87, 0x46, 0x08, 0x87, 0x46, 0x06)                  # xchg ax, [bp+8] / xchg ax, [bp+6]   flags, CS up
    a.b(0x89, 0x46, 0x04)                                    # mov [bp+4], ax
    a.b(0x2e, 0xa1); a.word('call_target')                   # mov ax, cs:[call_target]
    a.b(0x89, 0x46, 0x02)                                    # mov [bp+2], ax
    a.b(0x58, 0x5d, 0xcf)                                    # pop ax / pop bp / iret

    # --- D13: four colours ---
    # draw (1000:9AFD, 9B09; replaces call 5DD4): di = the animation slot, its object at +16h. Notes which colour
    # range of this frame moves (0 = none), then makes the call
    a.label('rules_draw')
    a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(0x00)     # mov byte cs:[recolour], 0
    a.b(0x2e, 0xc6, 0x06); a.word('sw_shift'); a.b(0x00)     # mov byte cs:[sw_shift], 0   D31
    a.b(0x2e, 0xc6, 0x06); a.word('saber_piece'); a.b(0x00)  # D51
    a.b(0x8b, 0x5d, 0x16)                                    # mov bx, [di+16h]   the object
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00); a.short(0x74, 'draw_no_hold')   # D60: cmp byte cs:[multi], 0 / je
    a.near(0xe8, 'hold_refresh')                             # call hold_refresh   a body held stays held
    a.label('draw_no_hold')
    # K25: frames flagged 10h are also drawn into the background (1000:9AEC, [80B9h] = 0AC00h), as the last frames
    # of a death: the body stays there. In co-op a knight down goes off the screen, and its body was left behind in
    # the knights' first colours (blue): a knight down is not drawn into the background
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'draw_bg')                                 # jne draw_bg
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # D46: the 3-4 knight practice too: knights 3 and 4 lay blue
    a.short(0x74, 'draw_kept')                               # je draw_kept
    a.label('draw_bg')
    a.b(0x81, 0x7e, 0x02, 0xfd, 0x9a)                        # cmp word [bp+2], 9AFDh   the background's draw
    a.short(0x75, 'draw_kept')                               # jne draw_kept
    a.b(0x81, 0xfb, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)      # cmp bx, 6C9Eh
    a.short(0x72, 'draw_kept')                               # jb draw_kept
    a.b(0x81, 0xfb, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8)      # cmp bx, 6DC4h
    a.short(0x76, 'draw_down')                               # jbe draw_down
    a.near(0xe8, 'black_knight')                             # call black_knight   D19: or a Black Knight
    a.short(0x75, 'draw_kept')                               # jnz draw_kept
    a.label('draw_down')
    a.b(0x83, 0x7f, 0x38, 0x00)                              # cmp word [bx+38h], 0
    a.short(0x7f, 'draw_kept')                               # jg draw_kept       standing
    a.near(0xe9, 'rules_done')                               # jmp rules_done     not drawn
    a.label('draw_kept')
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'draw_coop')                               # jne draw_coop
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x75, 'draw_multi')                              # jne draw_multi
    a.near(0xe9, 'draw_call')                                # jmp draw_call
    a.label('draw_multi')
    a.b(0x2e, 0x80, 0x3e); a.word('teams'); a.b(0x00)        # cmp byte cs:[teams], 0
    a.short(0x74, 'draw_own')                                # je draw_own
    # teams wear their team's colour, after their own for TEAM_SHOW ticks of the fight (so each player sees at
    # once which knight is theirs); cs:[team_t0] = the fight's first tick, 0 before it
    a.b(0x50, 0x1e, 0x33, 0xc0, 0x8e, 0xd8)                  # push ax / push ds / xor ax, ax / mov ds, ax
    a.b(0xa1, 0x6c, 0x04, 0x1f)                              # mov ax, [046Ch] / pop ds    the BIOS tick
    a.b(0x2e, 0x83, 0x3e); a.word('team_t0'); a.b(0x00)      # cmp word cs:[team_t0], 0
    a.short(0x74, 'draw_team_own')                           # je draw_team_own   not started
    a.b(0x2e, 0x2b, 0x06); a.word('team_t0')                 # sub ax, cs:[team_t0]
    a.b(0x3d, TEAM_SHOW, 0x00)                               # cmp ax, TEAM_SHOW
    a.short(0x72, 'draw_team_own')                           # jb draw_team_own
    a.b(0x58)                                                # pop ax
    a.near(0xe9, 'draw_call')                                # jmp draw_call     the team's colour
    a.label('draw_team_own')
    a.b(0x58)                                                # pop ax
    a.label('draw_own')
    for table, name in ((PRACTICE_RECOLOUR, 'p'), (COOP_RECOLOUR, 'c')):
        if name == 'c':
            a.near(0xe9, 'draw_call')                        # jmp draw_call
            a.label('draw_coop')
            # D19: a Black Knight (a computer knight in a monster slot) wears its own colours, not those of the
            # knight it goes for (K30 below)
            a.near(0xe8, 'black_knight')                     # call black_knight
            a.short(0x75, 'draw_not_bk')                     # jnz draw_not_bk
            a.near(0xe9, 'draw_black')                       # jmp draw_black
            a.label('draw_not_bk')
            # K28: the Balok's frames of its hold show the knight (pixels 6-8, which its own frames do not use):
            # in that knight's colours
            a.b(0x80, 0x7f, 0x35, BALOK_TYPE)                # cmp byte [bx+35h], 18h
            a.short(0x75, 'draw_not_balok')                  # jne draw_not_balok
            a.b(0x2e, 0x8b, 0x1e); a.word('balok_victim')    # mov bx, cs:[balok_victim]
            a.label('draw_not_balok')
            # K25: the dragon's frames of a knight eaten (DRAGON2.CEL 17-19, DRAGON5.CEL 32, 35: the only ones with
            # pixels 6-8) show the knight eaten: in its colours
            a.b(0x81, 0xfb, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)   # cmp bx, 6E26h
            a.short(0x75, 'draw_not_dragon')                 # jne draw_not_dragon
            a.b(0x2e, 0x83, 0x3e); a.word('dragon_victim'); a.b(0x00)   # cmp word cs:[dragon_victim], 0
            a.short(0x74, 'draw_not_dragon')                 # je draw_not_dragon
            a.b(0x2e, 0x8b, 0x1e); a.word('dragon_victim')   # mov bx, cs:[dragon_victim]
            a.label('draw_not_dragon')
            a.b(0x80, 0x7f, 0x35, SPEAR_TROGG)               # cmp byte [bx+35h], 10h   the trogg's spear
            a.short(0x75, 'draw_not_trogg')                  # jne draw_not_trogg
            a.b(0x57, 0x8b, 0xfb); a.near(0xe8, 'slot_index')   # push di / mov di, bx / call slot_index
            a.b(0x5f); a.short(0x72, 'draw_not_trogg')       # pop di / jc draw_not_trogg
            a.b(0x2e, 0x8b, 0x9f); a.word('impaled')         # mov bx, cs:[bx+impaled]
            a.label('draw_not_trogg')
            # K30: the other monsters' frames that show a knight (pixels 6-8: the ratmen's RATMEN2.CEL 42-62, the
            # boar's toss BE1.C 34-61, the mudmen's hold and pull MUDMEN1/2.CEL, the Guardian's DEMON2/3.CEL; their
            # own pixels do not use 6-8): in the colours of the knight the monster goes for (D15's last_target)
            a.b(0x81, 0xfb, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)   # cmp bx, 6F08h
            a.short(0x72, 'draw_not_monster')                # jb draw_not_monster   a knight, the dragon, none
            # a mudman holding or pulling a knight (K25: [7B8Ch] 1, 2, 4, 40h; mud_victim): that knight, not the
            # one it would go for now
            a.b(0x80, 0x7f, 0x35, MUDMAN); a.short(0x75, 'draw_not_mud')   # cmp byte [bx+35h], 2 / jne
            a.b(0xf7, 0x06, 0x8c, 0x7b, 0x47, 0x00); a.short(0x74, 'draw_not_mud')   # test word [7B8Ch], 47h / jz
            a.b(0x2e, 0x83, 0x3e); a.word('mud_victim'); a.b(0x00); a.short(0x74, 'draw_not_mud')
            a.b(0x2e, 0x8b, 0x1e); a.word('mud_victim')      # mov bx, cs:[mud_victim]
            a.short(0xeb, 'draw_not_monster')
            a.label('draw_not_mud')
            # a ratman hanging a knight or on its back ([779Ch] 8, 20h; rat_victim): that knight
            a.b(0x80, 0x7f, 0x35, 0x12); a.short(0x75, 'draw_not_rat')   # cmp byte [bx+35h], 12h / jne
            a.b(0xf7, 0x06, 0x9c, 0x77, 0x28, 0x00); a.short(0x74, 'draw_not_rat')   # test word [779Ch], 28h / jz
            a.b(0x2e, 0x83, 0x3e); a.word('rat_victim'); a.b(0x00); a.short(0x74, 'draw_not_rat')
            a.b(0x2e, 0x8b, 0x1e); a.word('rat_victim')      # mov bx, cs:[rat_victim]
            a.short(0xeb, 'draw_not_monster')
            a.label('draw_not_rat')
            a.b(0x50, 0x57, 0x8b, 0xc3, 0x8b, 0xfb)          # push ax di / mov ax, bx / mov di, bx
            a.near(0xe8, 'slot_index')                       # call slot_index      bx = slot * 2
            a.b(0x5f); a.short(0x72, 'draw_monster_back')    # pop di / jc draw_monster_back
            a.b(0x2e, 0x8b, 0x9f); a.word('last_target')     # mov bx, cs:[bx+last_target]
            a.b(0x0b, 0xdb); a.short(0x75, 'draw_monster_pop')   # or bx, bx / jnz draw_monster_pop
            a.label('draw_monster_back')
            a.b(0x8b, 0xd8)                                  # mov bx, ax          the monster itself
            a.label('draw_monster_pop')
            a.b(0x58)                                        # pop ax
            a.label('draw_not_monster')
            # D33: in a co-op lair every knight wears its own colour slot's entries (the records' colours are the
            # players', not the practice's)
            a.b(0x2e, 0x83, 0x3e); a.word('coop_partner'); a.b(0x00); a.short(0x74, 'draw_slots_no')
            a.b(0x81, 0xfb, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'draw_slots_no')
            a.b(0x81, 0xfb, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8); a.short(0x77, 'draw_slots_no')
            a.b(0x53, 0x8b, 0x5f, 0x20, 0x83, 0xfb, len(SLOT_SHIFTS) - 1); a.short(0x77, 'draw_slots_pop')   # push bx / mov bx, [bx+20h] / cmp bx, 4 / ja
            a.b(0x50, 0x2e, 0x8a, 0x87); a.word('slot_shifts'); a.b(0x2e, 0xa2); a.word('rc_shift'); a.b(0x58)   # its shift
            a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(0x06, 0x5b)   # mov byte cs:[recolour], 6 / pop bx
            a.near(0xe9, 'draw_call')
            a.label('draw_slots_pop')
            a.b(0x5b)
            a.label('draw_slots_no')
        for rec, first, shift in table:
            a.b(0x81, 0xfb, rec & 0xff, rec >> 8)            # cmp bx, record
            a.short(0x75, f'draw_{name}{rec:x}')             # jne next
            a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(first)    # mov byte cs:[recolour], first pixel value
            a.b(0x2e, 0xc6, 0x06); a.word('rc_shift'); a.b(shift)    # mov byte cs:[rc_shift], shift
            a.label(f'draw_{name}{rec:x}')
    a.near(0xe8, 'black_knight')                             # call black_knight   D19
    a.short(0x74, 'draw_black')                              # jz draw_black
    a.near(0xe9, 'draw_call')                                # jmp draw_call
    a.label('draw_black')
    a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(6)        # mov byte cs:[recolour], 6
    a.b(0x2e, 0xc6, 0x06); a.word('rc_shift'); a.b(BLACK_SHIFT)   # mov byte cs:[rc_shift], 35
    a.label('draw_call')
    a.near(0xe8, 'score_colour')                             # D52: a knight's colour, as drawn
    a.near(0xe8, 'he_shared')                                # call he_shared
    a.near(0xe8, 'sword_tint')                               # call sword_tint   D31
    a.near(0xe8, 'set_gore_pass')                            # call set_gore_pass   D22
    a.b(0x50, 0x8b, 0x46, 0x02, 0x40)                        # push ax / mov ax, [bp+2] / inc ax   site + 3
    a.b(0x2e, 0xa3); a.word('call_ret')                      # mov cs:[call_ret], ax
    a.b(0x58)                                                # pop ax
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(BLITTER & 0xff, BLITTER >> 8)   # mov word cs:[call_target], 5DD4h
    a.near(0xe9, 'call_game')                                # jmp call_game

    # sword_tint (D31, from draw; di = the animation, es:si = the bank): a piece of a knight (a human's or a
    # computer's) gets the entries of its gear in sw_shift, which the recolour adds to pixels 1-4: a piece of KN4.OB
    # (the sword) those of its weapon, any other piece those of its armour
    a.label('sword_tint')
    a.b(0x50, 0x53)                                          # push ax bx
    a.b(0x8b, 0x5d, 0x16)                                    # mov bx, [di+16h]   its object
    a.b(0x80, 0x7f, 0x35, 0x06); a.short(0x74, 'swt_knight')   # cmp byte [bx+35h], 6 / je
    a.b(0x80, 0x7f, 0x35, COMPUTER_TYPE); a.short(0x74, 'swt_knight'); a.near(0xe9, 'swt_pop')   # or a computer's knight
    a.label('swt_knight')
    # D51 LIGHTSABER: a sword piece is drawn white with its glow (saber_glow), not tinted
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_SABER); a.short(0x74, 'swt_d47')
    a.b(0x2e, 0xa2); a.word('saber_frame')                   # D57: mov cs:[saber_frame], al   (the frame drawn)
    a.b(0x3b, 0x36, SWORD_KN4 & 0xff, SWORD_KN4 >> 8); a.short(0x75, 'swt_d47')   # cmp si, [8941h] / jne
    a.b(0x8c, 0xc0, 0x3b, 0x06, (SWORD_KN4 + 2) & 0xff, (SWORD_KN4 + 2) >> 8); a.short(0x75, 'swt_d47')   # mov ax, es / cmp ax, [8943h] / jne
    a.b(0x2e, 0xc6, 0x06); a.word('saber_piece'); a.b(0x01)
    a.near(0xe9, 'swt_pop')
    a.label('swt_d47')
    # D47: the Black Knights of a practice (keys 0 and B) keep the game's steel; in the campaign the gear shows
    a.b(0x83, 0x7f, 0x20, 0x04); a.short(0x75, 'swt_go')     # cmp word [bx+20h], 4 / jne
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00); a.short(0x74, 'swt_go')
    a.near(0xe9, 'swt_pop')
    a.label('swt_go')
    a.b(0x3b, 0x36, SWORD_KN4 & 0xff, SWORD_KN4 >> 8); a.short(0x75, 'swt_armour')   # cmp si, [8941h] / jne
    a.b(0x8c, 0xc0, 0x3b, 0x06, (SWORD_KN4 + 2) & 0xff, (SWORD_KN4 + 2) >> 8)   # mov ax, es / cmp ax, [8943h]
    a.short(0x75, 'swt_armour')
    a.b(0x8b, 0x47, 0x40)                                    # mov ax, [bx+40h]   its weapon
    for k, (weapon, _) in enumerate(SWORD_TINTS):
        a.b(0x3d, weapon, 0x00); a.short(0x75, f'swt_n{k}')  # cmp ax, weapon / jne
        a.b(0x2e, 0xc6, 0x06); a.word('sw_shift'); a.b(SWORD_FIRST + 4 * k - 1)   # pixel 1 -> its first entry
        a.near(0xe9, 'swt_pop')
        a.label(f'swt_n{k}')
    a.near(0xe9, 'swt_pop')
    a.label('swt_armour')
    a.b(0x8c, 0xc0)                                          # mov ax, es   only the knights' body files (KN1-3, KN5, HE1-3)
    for seg in BODY_SEGMENTS:
        a.b(0x3b, 0x06, seg & 0xff, seg >> 8); a.short(0x74, 'swt_body')   # cmp ax, [its segment] / je
    a.near(0xe9, 'swt_pop')
    a.label('swt_body')
    a.b(0x8b, 0x47, 0x42)                                    # mov ax, [bx+42h]   its armour
    for k, (armour, _) in enumerate(ARMOUR_TINTS):
        a.b(0x3d, armour, 0x00); a.short(0x75, f'swt_a{k}')  # cmp ax, armour / jne
        a.b(0x2e, 0xc6, 0x06); a.word('sw_shift'); a.b(ARMOUR_FIRST + 4 * k - 1)
        a.near(0xe9, 'swt_pop')
        a.label(f'swt_a{k}')
    a.label('swt_pop')
    a.b(0x5b, 0x58)                                          # pop bx ax
    a.b(0xc3)
    # sword_entries (D31): the gear's entries 48-71 at the fade level cs:[level] (0-16)
    a.label('sword_entries')
    a.b(0x50, 0x51, 0x52, 0x56)                              # push ax cx dx si
    a.b(0xba, 0xc8, 0x03, 0xb0, SWORD_FIRST, 0xee, 0x42)     # mov dx, 3C8h / mov al, 48 / out dx, al / inc dx
    a.b(0xbe); a.word('sword_rgb'); a.b(0xb9, 3 * GEAR_ENTRIES, 0x00)   # mov si, sword_rgb / mov cx, 72
    a.label('se_loop')
    a.b(0x2e, 0x8a, 0x04, 0x2e, 0xf6, 0x26); a.word('level')   # mov al, cs:[si] / mul byte cs:[level]
    a.b(0xd1, 0xe8, 0xd1, 0xe8, 0xd1, 0xe8, 0xd1, 0xe8, 0xee, 0x46)   # shr ax, 1 (x4) / out dx, al / inc si
    a.short(0xe2, 'se_loop')
    a.b(0x5e, 0x5a, 0x59, 0x58, 0xc3)                        # pop si dx cx ax / ret

    # he_shared (from draw; di = the animation, es:si = the bank): a knight drawn from the HE banks wears 9-11, but its
    # bank table's last two entries are KN4.OB and KN5.OB (1000:8BF0), in the 6-8 of the KN look; KN5.OB has the crush
    # that a mine sets off. Their 6-8 move to where the knight's own 9-11 go: 9-11, or further with its own recolour
    a.label('he_shared')
    a.b(0x81, 0x7d, 0x18, HE_BANK & 0xff, HE_BANK >> 8); a.short(0x75, 'hes_end')   # cmp word [di+18h], HE_BANK / jne
    for bank in (0x8941, 0x8945):
        a.b(0x3b, 0x36, bank & 0xff, bank >> 8); a.short(0x75, f'hes_n{bank:x}')   # cmp si, [bank]
        a.b(0x50, 0x8c, 0xc0, 0x3b, 0x06, (bank + 2) & 0xff, (bank + 2) >> 8, 0x58)   # push ax / mov ax, es / cmp ax, [bank+2] / pop ax
        a.short(0x74, 'hes_hit')
        a.label(f'hes_n{bank:x}')
    a.label('hes_end')
    a.b(0xc3)
    a.label('hes_hit')
    a.b(0x50, 0x2e, 0xa0); a.word('recolour')                # push ax / mov al, cs:[recolour]
    a.b(0x3c, 0x06); a.short(0x74, 'hes_pop')                # cmp al, 6 / je   these colours are moved already
    a.b(0xb4, 0x03, 0x0a, 0xc0); a.short(0x74, 'hes_set')    # mov ah, 3 / or al, al / jz
    a.b(0x2e, 0x02, 0x26); a.word('rc_shift')                # add ah, cs:[rc_shift]
    a.label('hes_set')
    a.b(0x2e, 0x88, 0x26); a.word('rc_shift')                # mov cs:[rc_shift], ah
    a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(0x06)     # mov byte cs:[recolour], 6
    a.label('hes_pop')
    a.b(0x58, 0xc3)                                          # pop ax / ret

    # recolour (1000:5EDF; replaces pop di / pop si / pop ds, the frame now converted into es:0): moves this
    # frame's knight colours up, then does the three pops
    a.label('rules_recolour')
    a.b(0x2e, 0x80, 0x3e); a.word('gore_pass'); a.b(0x00)    # cmp byte cs:[gore_pass], 0   D22: no blood
    a.short(0x74, 'rc_colours')                              # je rc_colours
    a.near(0xe8, 'gore_clean')                               # call gore_clean
    a.b(0x2e, 0xc6, 0x06); a.word('gore_pass'); a.b(0x00)    # mov byte cs:[gore_pass], 0
    a.label('rc_colours')
    a.b(0x2e, 0x8a, 0x1e); a.word('recolour')                # mov bl, cs:[recolour]
    a.b(0x2e, 0x0a, 0x1e); a.word('sw_shift')                # or bl, cs:[sw_shift]   D31
    a.b(0x2e, 0x0a, 0x1e); a.word('saber_piece')             # or bl, cs:[saber_piece]   D51
    a.short(0x75, 'rc_go'); a.near(0xe9, 'rc_pop')           # jz rc_pop
    a.label('rc_go')
    a.b(0x2e, 0x8a, 0x1e); a.word('recolour')                # mov bl, cs:[recolour]
    a.b(0x2e, 0x8a, 0x3e); a.word('rc_shift')                # mov bh, cs:[rc_shift]
    a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(0x00)     # mov byte cs:[recolour], 0
    # D23: through a table, the identity but for the three colours (moved up by the shift while this frame is done)
    a.b(0x50, 0x51, 0x57, 0x56, 0x1e)                        # push ax cx di si ds
    a.b(0x8a, 0xc7, 0x32, 0xff)                              # mov al, bh / xor bh, bh   al = shift, bx = first
    a.b(0x0a, 0xdb); a.short(0x74, 'rc_no3')                 # or bl, bl / jz   no knight colours to move
    for k in range(3):
        a.b(0x2e, 0x00, 0x87); a.word('rc_xlat', k)          # add cs:[bx+rc_xlat+k], al
    a.label('rc_no3')
    a.b(0x2e, 0x8a, 0x26); a.word('sw_shift')                # mov ah, cs:[sw_shift]   D31: the sword's 1-4
    for k in range(1, 5):
        a.b(0x2e, 0x00, 0x26); a.word('rc_xlat', k)          # add cs:[rc_xlat+k], ah
    a.b(0x53, 0x50)                                          # push bx ax
    a.b(0x8e, 0x5e, 0x04)                                    # mov ds, [bp+4]     MAIN's code segment
    a.b(0x8b, 0x0e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)      # mov cx, [637Bh]    bytes the converter wrote
    a.b(0x06, 0x1f, 0x33, 0xf6, 0x33, 0xff, 0xfc)            # push es / pop ds / xor si, si / xor di, di / cld
    a.b(0xbb); a.word('rc_xlat')                             # mov bx, rc_xlat
    a.short(0xe3, 'rc_end')                                  # jcxz rc_end
    a.label('rc_loop')
    a.b(0xac, 0x2e, 0xd7, 0xaa)                              # lodsb / xlat cs: / stosb
    a.short(0xe2, 'rc_loop')                                 # loop rc_loop
    a.label('rc_end')
    a.b(0x2e, 0x80, 0x3e); a.word('saber_piece'); a.b(0x00); a.short(0x74, 'rc_no_saber')   # D51: a lightsaber's piece
    a.near(0xe8, 'saber_glow'); a.b(0x2e, 0xc6, 0x06); a.word('saber_piece'); a.b(0x00)
    a.label('rc_no_saber')
    a.b(0x58, 0x5b)                                          # pop ax bx
    a.b(0x0a, 0xdb); a.short(0x74, 'rc_no3b')                # or bl, bl / jz
    for k in range(3):
        a.b(0x2e, 0x28, 0x87); a.word('rc_xlat', k)          # sub cs:[bx+rc_xlat+k], al   the identity again
    a.label('rc_no3b')
    for k in range(1, 5):
        a.b(0x2e, 0x28, 0x26); a.word('rc_xlat', k)          # sub cs:[rc_xlat+k], ah
    a.b(0x2e, 0xc6, 0x06); a.word('sw_shift'); a.b(0x00)     # mov byte cs:[sw_shift], 0
    a.b(0x1f, 0x5e, 0x5f, 0x59, 0x58)                        # pop ds si di cx ax
    a.label('rc_pop')
    a.b(0x8b, 0x7e, 0x08, 0x8b, 0x76, 0x0a, 0x8e, 0x5e, 0x0c)   # mov di, [bp+8] / mov si, [bp+10] / mov ds, [bp+12]
    a.b(0x5b, 0x5d, 0x50, 0x55, 0x8b, 0xec)                  # pop bx / pop bp / push ax / push bp / mov bp, sp
    for src, dst in ((8, 14), (6, 12), (4, 10)):             # the frame up over the three popped words
        a.b(0x8b, 0x46, src, 0x89, 0x46, dst)                # mov ax, [bp+src] / mov [bp+dst], ax
    a.b(0x5d, 0x58, 0x83, 0xc4, 0x06, 0xcf)                  # pop bp / pop ax / add sp, 6 / iret

    # new_entries: write DAC entries 32-37 (the index is already there) at cl/16 of their colours; ds = MAIN's code
    a.label('new_entries')
    a.b(0x50, 0x53, 0x52, 0x56, 0x57)                        # push ax bx dx si di
    a.b(0xba, 0xc9, 0x03)                                    # mov dx, 3C9h
    a.b(0xbe); a.word('colour_sites')                        # mov si, colour_sites
    a.b(0xbf); a.word('glow_cur')                            # mov di, glow_cur   D61: a pulsing word, else FFFFh
    a.label('ne_word')
    a.b(0x2e, 0x8b, 0x1d, 0x83, 0xc7, 0x02)                  # mov bx, cs:[di] / add di, 2
    a.b(0x83, 0xfb, 0xff); a.short(0x75, 'ne_glow')          # cmp bx, -1 / jne ne_glow
    a.b(0x2e, 0x8b, 0x1c, 0x8b, 0x1f)                        # mov bx, cs:[si] / mov bx, [bx]   the word 0RGB
    a.label('ne_glow')
    for shift in (8, 4, 0):                                  # R, G, B
        a.b(0x8b, 0xc3)                                      # mov ax, bx
        for _ in range(shift):
            a.b(0xd1, 0xe8)                                  # shr ax, 1
        a.b(0x25, 0x0f, 0x00)                                # and ax, 0Fh       the nibble
        a.b(0xd1, 0xe0, 0xd1, 0xe0)                          # shl ax, 1 / shl ax, 1   x4: the game's 6-bit value
        a.b(0x2e, 0xf6, 0x26); a.word('level')               # mul byte cs:[level]
        for _ in range(4):
            a.b(0xd1, 0xe8)                                  # shr ax, 1          / 16
        a.b(0xee)                                            # out dx, al
    a.b(0x83, 0xc6, 0x02)                                    # add si, 2
    a.b(0x2e, 0xfe, 0x0e); a.word('words_left')              # dec byte cs:[words_left]
    a.short(0x74, 'ne_done'); a.near(0xe9, 'ne_word')        # jz ne_done / jmp ne_word
    a.label('ne_done')
    a.b(0x2e, 0xc6, 0x06); a.word('words_left'); a.b(NEW_WORDS)   # mov byte cs:[words_left], 15
    a.b(0x5f, 0x5e, 0x5a, 0x5b, 0x58, 0xc3)                  # pop di si dx bx ax / ret

    # dac_write (1000:5B40; replaces mov dx,3C8h of the palette write 5B3E): writes the 32 entries from ds:si as the
    # game does, then 32-37, and returns to its ret (5B4E)
    a.label('rules_dac_write')
    a.b(0xba, 0xc8, 0x03, 0x32, 0xc0, 0xee, 0x42)            # mov dx, 3C8h / xor al, al / out dx, al / inc dx
    a.b(0xb9, 0x60, 0x00)                                    # mov cx, 60h
    a.label('dw_loop')
    a.b(0xac, 0xee)                                          # lodsb / out dx, al
    a.short(0xe2, 'dw_loop')                                 # loop dw_loop
    a.b(0x2e, 0xc6, 0x06); a.word('level'); a.b(0x10)        # mov byte cs:[level], 16
    a.near(0xe8, 'colours_active')                           # call colours_active
    a.short(0x74, 'dw_ret')                                  # jz dw_ret
    a.near(0xe8, 'dac_new')                                  # call dac_new
    a.label('dw_ret')
    a.near(0xe8, 'sword_entries')                            # call sword_entries   D31 (after 32-43: its own index)
    a.b(0xc7, 0x46, 0x02, 0x4e, 0x5b)                        # mov word [bp+2], 5B4Eh   the routine's ret
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('colours_active')                                # ZF = 0 in a 3-4 player or co-op practice
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x75, 'ca_ret')                                  # jne ca_ret
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.label('ca_ret')
    a.b(0xc3)                                                # ret
    a.label('dac_new')                                       # new_entries with ds = MAIN's code segment
    a.b(0x1e, 0x8e, 0x5e, 0x04)                              # push ds / mov ds, [bp+4]
    a.near(0xe8, 'new_entries')                              # call new_entries
    a.b(0x1f, 0xc3)                                          # pop ds / ret

    # fade_in (1000:5BAF) and fade_out (1000:5C23); replace add bp,0C0h after a step's 32 entries. The step count
    # is the pushed cx (16..1): in, step 17 - cx of 16; out, (cx - 1) of 16
    for name, fade_in in (('fade_in', True), ('fade_out', False)):
        a.label('rules_' + name)
        a.b(0x50, 0x8b, 0x46, 0x08)                          # push ax / mov ax, [bp+8]   the pushed cx
        if fade_in:
            a.b(0xf7, 0xd8, 0x05, 0x11, 0x00)                # neg ax / add ax, 17
        else:
            a.b(0x48)                                        # dec ax
        a.b(0x2e, 0xa2); a.word('level')                     # mov cs:[level], al
        a.b(0x58)                                            # pop ax
        a.near(0xe8, 'colours_active')                       # call colours_active
        a.short(0x74, name + '_sw')                          # jz
        a.near(0xe8, 'dac_new')                              # call dac_new
        a.label(name + '_sw')
        a.near(0xe8, 'sword_entries')                        # call sword_entries   D31
        a.label(name + '_bp')
        a.b(0x81, 0x46, 0x00, 0xc0, 0x00)                    # add word [bp], 0C0h    (the game's bp, replaced)
        a.near(0xe9, 'rules_done')                           # jmp rules_done

    # menu_keys (D14, 1000:129B; replaces mov [77E2h],bx, the first menu's input): anywhere in the first menu Space
    # starts the practice in teams (with 1-2 players the normal practice: the Black Knight, or knight against knight)
    # and the keys of PRACTICE_KEYS a practice against that fight (0: the Black Knight); Enter (fire) clears both
    # choices. The key states are MAIN's table in its code segment
    a.label('rules_menu_keys')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_wait'); a.b(0x00); a.short(0x74, 'sxmk_nw')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x00, 0x2e, 0xa1); a.word('snd_ax')   # back from the sound: ax again
    a.short(0xeb, 'sxmk_go')
    a.label('sxmk_nw')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_req'); a.b(0x00); a.short(0x74, 'sxmk_go')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_req'); a.b(0x00, 0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x01)
    a.b(0x2e, 0xa3); a.word('snd_ax'); a.b(0x8b, 0x46, 0x02, 0x2d, 0x02, 0x00)   # mov cs:[snd_ax], ax / mov ax, [bp+2] / sub ax, 2
    a.b(0x2e, 0xa3); a.word('call_ret')                      # this site's int 63h again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(SOUND & 0xff, SOUND >> 8)
    a.b(0xb8, CHEAT_SOUND, 0x00); a.near(0xe9, 'call_game')  # mov ax, sound id / 1000:5970
    a.label('sxmk_go')
    a.near(0xe8, 'gore_lock')
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_ctx'); a.b(CHEAT_MENU)   # mov byte cs:[cheat_ctx], 8
    # a key held back for a code (D, J) goes to the game once no next letter came in HOLD_WAIT ticks
    a.b(0x2e, 0x80, 0x3e); a.word('held_scan'); a.b(0x00); a.short(0x74, 'mk_no_held')
    a.b(0x50, 0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f)   # push ax / push ds / xor ax,ax / mov ds,ax / mov ax,[046Ch] / pop ds
    a.b(0x2e, 0x2b, 0x06); a.word('cheat_last'); a.b(0x3d, HOLD_WAIT, 0x00, 0x58)   # sub ax, cs:[cheat_last] / cmp ax, wait / pop ax
    a.short(0x72, 'mk_no_held')
    a.b(0x1e, 0x8e, 0x5e, 0x04); a.near(0xe8, 'held_replay'); a.b(0x1f)   # push ds / mov ds, [bp+4] / call / pop ds
    a.label('mk_no_held')
    # TOOEASY: the harder fights, TOOHARD: the easier ones, JUSTRIGHT: the game's (hard_ai 1, 2, 0); they stay
    for code, level in (('TOOEASY', HARD), ('TOOHARD', EASY), ('JUSTRIGHT', 0)):
        a.b(0x2e, 0x80, 0x3e); a.word('cheat_pending'); a.b(CHEAT_ID[code]); a.short(0x75, f'mk_no_{code}')
        a.b(0x2e, 0xc6, 0x06); a.word('cheat_pending'); a.b(0x00)
        a.b(0x2e, 0xc6, 0x06); a.word('hard_ai'); a.b(level)  # mov byte cs:[hard_ai], level
        a.label(f'mk_no_{code}')
    a.b(0x50, 0x56, 0x06)                                    # push ax si es
    a.b(0x8e, 0x46, 0x04)                                    # mov es, [bp+4]    MAIN's code segment
    a.b(0x8b, 0x5e, 0xfe)                                    # mov bx, [bp-2]    the input bits
    # the monster codes and HOTSTUFF: that practice at once, player 1 its monster (mon_req; practice_init)
    a.b(0x2e, 0xa0); a.word('cheat_pending')                 # mov al, cs:[cheat_pending]
    a.b(0x3c, CHEAT_ID['HOTSTUFF']); a.short(0x75, 'mk_n_hot')
    a.b(0x2e, 0xc6, 0x06); a.word('hotstuff'); a.b(0x01, 0xb4, DRAGON_CHOICE)   # mov ah, 10   the dragon's practice
    a.near(0xe9, 'mk_code')
    a.label('mk_n_hot')
    for alias, name in MONSTER_ALIASES.items():             # TROGGLIFE: as TROGLIFE
        a.b(0x3c, CHEAT_ID[alias]); a.short(0x75, f'mk_a_{alias}'); a.b(0xb0, CHEAT_ID[name])
        a.label(f'mk_a_{alias}')
    for name in MONSTER_CODES:
        a.b(0x3c, CHEAT_ID[name]); a.short(0x75, f'mk_n_{name}')
        if name == 'TROGLIFE':
            a.b(0x2e, 0xc6, 0x06); a.word('mon_req'); a.b(TROGG_ANY)
            a.b(0x1e, 0x52, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x32, 0xe4)   # push ds dx / ds = 0 / mov ax, [046Ch] / xor ah, ah
            a.b(0xb2, 0x03, 0xf6, 0xf2, 0x5a, 0x1f, 0x8a, 0xc4)  # mov dl, 3 / div dl / pop dx ds / mov al, ah   0-2
            a.b(0xb4, LAIR_CHOICE + TROGG_LAIRS[0], 0x3c, 0x01); a.short(0x72, 'mk_trogg')
            a.b(0xb4, LAIR_CHOICE + TROGG_LAIRS[1]); a.short(0x74, 'mk_trogg')
            a.b(0xb4, LAIR_CHOICE + TROGG_LAIRS[2])
            a.label('mk_trogg')
        else:
            a.b(0x2e, 0xc6, 0x06); a.word('mon_req'); a.b(MONSTER_TYPES[name], 0xb4, LAIR_CHOICE + MONSTER_LAIRS[name])
        a.near(0xe9, 'mk_code')
        a.label(f'mk_n_{name}')
    a.b(0x3c, 40); a.short(0x72, 'mk_n_fight'); a.b(0x3c, 60); a.short(0x73, 'mk_n_fight')
    a.b(0xb4, 0x01); a.near(0xe8, 'queue_code')              # a fight code: for the next practice fight
    a.label('mk_n_fight')
    a.near(0xe9, 'mk_keys')
    a.label('mk_code')
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_pending'); a.b(0x00)
    a.b(0x2e, 0x88, 0x26); a.word('monster')                 # mov cs:[monster], ah
    a.b(0x2e, 0xc6, 0x06); a.word('teams'); a.b(0x00)
    a.near(0xe9, 'mk_practice')
    a.label('mk_keys')
    a.b(0x26, 0x80, 0x3e); a.b(struct.pack('<H', KEY_TABLE + SPACE)); a.b(0xff)   # cmp byte es:[Space], 0FFh
    a.short(0x73, 'mk_digits')                               # jae mk_digits     not held
    a.b(0x2e, 0xc6, 0x06); a.word('teams'); a.b(0x01)        # mov byte cs:[teams], 1
    a.b(0x2e, 0xc6, 0x06); a.word('monster'); a.b(0x00)      # mov byte cs:[monster], 0
    a.short(0xeb, 'mk_practice')                             # jmp mk_practice
    a.label('mk_digits')
    a.b(0xbe); a.word('practice_keys')                       # mov si, practice_keys
    a.label('mk_scan')
    a.b(0x2e, 0x8b, 0x1c)                                    # mov bx, cs:[si]   bl = scan code, bh = choice
    a.b(0x0a, 0xdb)                                          # or bl, bl
    a.short(0x74, 'mk_none')                                 # jz mk_none        end of the table
    a.b(0x53, 0x32, 0xff)                                    # push bx / xor bh, bh
    a.b(0x26, 0x80, 0xbf); a.b(struct.pack('<H', KEY_TABLE)); a.b(0xff)   # cmp byte es:[bx+81E3h], 0FFh
    a.b(0x5b)                                                # pop bx
    a.short(0x72, 'mk_digit')                                # jb mk_digit       held
    a.b(0x83, 0xc6, 0x02)                                    # add si, 2
    a.short(0xeb, 'mk_scan')                                 # jmp mk_scan
    a.label('mk_none')
    a.b(0x8b, 0x5e, 0xfe)                                    # mov bx, [bp-2]    the input bits again
    a.short(0xeb, 'mk_enter')                                # jmp mk_enter
    a.label('mk_digit')
    a.b(0x2e, 0x88, 0x3e); a.word('monster')                 # mov cs:[monster], bh
    a.b(0x2e, 0xc6, 0x06); a.word('teams'); a.b(0x00)        # mov byte cs:[teams], 0
    a.label('mk_practice')
    a.b(0x8b, 0x5e, 0xfe)                                    # mov bx, [bp-2]
    a.b(0xc7, 0x06, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION, 0x00)   # mov word [0704h], 2
    a.b(0x83, 0xcb, 0x10)                                    # or bx, 10h        as fire
    a.short(0xeb, 'mk_store')                                # jmp mk_store
    a.label('mk_enter')
    a.b(0xf6, 0xc3, 0x10)                                    # test bl, 10h      fire (Enter)
    a.short(0x74, 'mk_store')                                # jz mk_store
    a.b(0x2e, 0xc6, 0x06); a.word('teams'); a.b(0x00)        # mov byte cs:[teams], 0
    a.b(0x2e, 0xc6, 0x06); a.word('monster'); a.b(0x00)      # mov byte cs:[monster], 0
    a.label('mk_store')
    a.b(0x89, 0x1e, 0xe2, 0x77, 0x89, 0x5e, 0xfe)            # mov [77E2h], bx / mov [bp-2], bx   (replaced)
    a.b(0x07, 0x5e, 0x58)                                    # pop es si ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # practice_init (D14, 1000:0144; replaces call 1FFA, InitPractice): a lair practice instead calls the lair
    # fight's set-up as a lair visit does (1000:0588: 055E, then 1F2C with [6962h] = that lair's record); the other
    # choices call their fight's own set-up (SET_UPS); each call returns to the int 63h at 0142 or goes on at 0145
    a.label('rules_practice_init')
    a.b(0x2e, 0x80, 0x3e); a.word('init_state'); a.b(ADD_STATE)   # cmp byte cs:[init_state], 10
    a.short(0x72, 'pi_choice')                               # jb pi_choice
    a.near(0xe9, 'pi_add')                                   # jmp pi_add          adding the co-op knights
    a.label('pi_choice')
    a.b(0x2e, 0x8a, 0x1e); a.word('monster')                 # mov bl, cs:[monster]
    a.b(0x32, 0xff, 0x0a, 0xdb)                              # xor bh, bh / or bl, bl
    a.short(0x75, 'pi_monster')                              # jnz pi_monster
    a.label('pi_knight')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xfa, 0x1f)   # mov word cs:[call_target], 1FFAh
    a.label('pi_go_on')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x45, 0x01)      # mov word cs:[call_ret], 0145h
    a.near(0xe9, 'call_game')                                # jmp call_game
    a.label('pi_monster')
    a.b(0xc7, 0x06, 0xe8, 0x77, 0x9e, 0x6c)                  # mov word [77E8h], 6C9Eh   the knight
    # co-op: 2 knights with 2 players (or 3-4 without their controllers), 3-4 as D12's mode found them
    a.b(0x50, 0x2e, 0xc6, 0x06); a.word('coop'); a.b(0x00)   # push ax / mov byte cs:[coop], 0
    a.b(0x83, 0x3e, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8, 0x02)   # cmp word [0940h], 2
    a.short(0x72, 'pi_solo')                                 # jb pi_solo
    a.b(0x2e, 0xa0); a.word('multi')                         # mov al, cs:[multi]
    a.b(0x0a, 0xc0)                                          # or al, al
    a.short(0x75, 'pi_coop')                                 # jnz pi_coop
    a.b(0xb0, 0x02)                                          # mov al, 2
    a.label('pi_coop')
    a.b(0x2e, 0xa2); a.word('coop')                          # mov cs:[coop], al
    a.label('pi_solo')
    a.b(0x58)                                                # pop ax
    # a monster code's fight: as many knights as players chosen (each its own input: W A S D, joystick A,
    # joystick B, the third key set), player 1 (the arrows) the monster. With 1-3, knights 2-4 fight and knight 1
    # is out (k1_out); with 4, knight 1 too, on the third key set
    a.b(0x2e, 0x80, 0x3e); a.word('mon_req'); a.b(0x00); a.short(0x75, 'pi_mon_mode')
    a.b(0x2e, 0x80, 0x3e); a.word('hotstuff'); a.b(0x00); a.short(0x74, 'pi_not_mon')
    a.label('pi_mon_mode')
    a.b(0x50, 0xa1, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8)   # push ax / mov ax, [0940h]
    a.b(0x2e, 0xc6, 0x06); a.word('k1_out'); a.b(0x01)
    a.b(0x3d, 0x04, 0x00); a.short(0x73, 'pi_mon_4'); a.b(0x40); a.short(0xeb, 'pi_mon_n')   # cmp ax, 4 / jae / inc ax
    a.label('pi_mon_4')
    a.b(0xb0, 0x04); a.b(0x2e, 0xc6, 0x06); a.word('k1_out'); a.b(0x00)   # 4 knights: knight 1 in
    a.label('pi_mon_n')
    a.b(0x2e, 0xa2); a.word('coop')                          # mov cs:[coop], al
    a.b(0x2e, 0xc6, 0x06); a.word('multi'); a.b(0x00, 0x2e, 0xc6, 0x06); a.word('mon_mode'); a.b(0x01)
    a.b(0x2e, 0xa0); a.word('mon_req'); a.b(0x2e, 0xa2); a.word('mon_ctl')   # mon_ctl = mon_req
    a.b(0x58)
    a.label('pi_not_mon')
    a.b(0x2e, 0x80, 0x3e); a.word('hotstuff'); a.b(0x00); a.short(0x74, 'pi_no_hot')   # HOTSTUFF's fight?
    a.b(0x2e, 0xc6, 0x06); a.word('hotstuff'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('dragon_ctl'); a.b(0x01)
    a.label('pi_no_hot')
    a.b(0x2e, 0xc6, 0x06); a.word('bk'); a.b(0x00)           # mov byte cs:[bk], 0
    a.b(0x2e, 0xc6, 0x06); a.word('dummy'); a.b(0x00)        # D46
    a.b(0x2e, 0x80, 0x3e); a.word('init_state'); a.b(0x00)   # cmp byte cs:[init_state], 0
    a.short(0x75, 'pi_kept')                                 # jne pi_kept        (the second call of a lair)
    a.b(0x51, 0x57, 0x06, 0x0e, 0x07)                        # push cx di es / push cs / pop es
    a.b(0xbf); a.word('last_target')                         # mov di, last_target
    a.b(0x33, 0xc0, 0xb9, 0x2a, 0x00, 0xfc, 0xf3, 0xab)      # xor ax, ax / mov cx, 42 / cld / rep stosw   and target_hold
    a.b(0x07, 0x5f, 0x59)                                    # pop es di cx
    a.b(0x2e, 0xc6, 0x06); a.word('bk_count'); a.b(0x00)     # mov byte cs:[bk_count], 0   D19
    a.b(0x2e, 0xc7, 0x06); a.word('dragon_victim'); a.b(0x00, 0x00)   # mov word cs:[dragon_victim], 0   K25
    a.b(0x2e, 0xc7, 0x06); a.word('rat_victim'); a.b(0x00, 0x00)      # mov word cs:[rat_victim], 0
    a.label('pi_kept')
    # D19: the B key: Black Knights in black, strong, as many as the knights (one with one player: co-op of one)
    a.b(0x80, 0xfb, P_CHOICE); a.short(0x75, 'pi_not_p')     # cmp bl, 14 / jne   D46: the practice Purple Knight
    a.b(0x2e, 0xc6, 0x06); a.word('dummy'); a.b(0x01, 0x2e, 0xc6, 0x06); a.word('bk'); a.b(0x01)   # dummy = 1 / bk = 1
    a.b(0x50, 0x51, 0x57, 0x06, 0x0e, 0x07, 0xbf); a.word('dm_seen'); a.b(0x33, 0xc0, 0xb9, 72, 0x00, 0xfc, 0xf3, 0xab, 0x07, 0x5f, 0x59, 0x58)   # dm_seen, dm_next, dm_seq = 0
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00); a.short(0x75, 'pi_p_c')   # cmp byte cs:[coop], 0 / jne
    a.b(0x2e, 0xc6, 0x06); a.word('coop'); a.b(0x01)
    a.label('pi_p_c')
    a.near(0xe9, 'pi_bk_fight')
    a.label('pi_not_p')
    a.b(0x80, 0xfb, BK_CHOICE)                               # cmp bl, 13
    a.short(0x75, 'pi_not_bk')                               # jne pi_not_bk
    a.b(0x2e, 0xc6, 0x06); a.word('bk'); a.b(0x02)           # mov byte cs:[bk], 2
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'pi_bk_lair')                              # jne pi_bk_lair
    a.b(0x2e, 0xc6, 0x06); a.word('coop'); a.b(0x01)         # mov byte cs:[coop], 1
    a.label('pi_bk_lair')
    a.label('pi_bk_fight')
    a.b(0xc7, 0x06, 0x78, 0x09, 0x9e, 0x6c)                  # mov word [0978h], 6C9Eh   (as a set-up of its own)
    a.b(0x2e, 0xc6, 0x06); a.word('vs_monsters'); a.b(0x01)  # mov byte cs:[vs_monsters], 1
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(BK_SET_UP & 0xff, BK_SET_UP >> 8)   # the trolls' set-up
    a.near(0xe9, 'pi_after')                                 # jmp pi_after
    a.label('pi_not_bk')
    for choice, target in SET_UPS.items():                   # fights with their own set-up
        a.b(0x80, 0xfb, choice)                              # cmp bl, choice
        a.short(0x75, f'pi_not_{choice}')                    # jne next
        a.b(0xc7, 0x06, 0x78, 0x09, 0x9e, 0x6c)              # mov word [0978h], 6C9Eh   (as 1000:0CF6)
        a.b(0x2e, 0xc6, 0x06); a.word('vs_monsters'); a.b(0x01)   # mov byte cs:[vs_monsters], 1
        a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(target & 0xff, target >> 8)   # cs:[call_target] = set-up
        a.near(0xe9, 'pi_after')                             # jmp pi_after
        a.label(f'pi_not_{choice}')
    # a monster code's choice (40h + n): lair n
    a.b(0x8a, 0xc3, 0x3c, LAIR_CHOICE); a.short(0x72, 'pk_key')   # mov al, bl / cmp al, 40h / jb
    a.b(0x2c, LAIR_CHOICE); a.near(0xe9, 'pk_lair')          # sub al, 40h
    a.label('pk_key')
    # the key's entry (G_PRACTICE): its lair, or FFh the Black Knight
    a.b(0x8a, 0xc3, 0x3c, KEY_0_CHOICE)                      # mov al, bl / cmp al, 12   the 0 key?
    a.short(0x75, 'pk_entry')                                # jne pk_entry
    a.b(0xb0, 0x0a)                                          # mov al, 10
    a.label('pk_entry')
    a.b(0xfe, 0xc8, 0x32, 0xe4, 0x8b, 0xf0)                  # dec al / xor ah, ah / mov si, ax
    a.b(0x2e, 0x8a, 0x84); a.word('rules_table', G_PRACTICE) # mov al, cs:[si+entry]
    a.b(0x3c, 0xff)                                          # cmp al, 0FFh             the Black Knight
    a.short(0x75, 'pk_lair')                                 # jne pk_lair
    # D19: with 2-4 knights, Black Knights against them all; with one, knight against knight as before
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'pk_duel')                                 # je pk_duel
    a.b(0x2e, 0xc6, 0x06); a.word('bk'); a.b(0x01)           # mov byte cs:[bk], 1
    a.near(0xe9, 'pi_bk_fight')                              # jmp pi_bk_fight
    a.label('pk_duel')
    a.b(0x2e, 0xc6, 0x06); a.word('coop'); a.b(0x00)         # mov byte cs:[coop], 0    knight against knight
    a.near(0xe9, 'pi_knight')                                # jmp pi_knight
    a.label('pk_lair')
    a.b(0x2e, 0xc6, 0x06); a.word('vs_monsters'); a.b(0x01)  # mov byte cs:[vs_monsters], 1
    a.b(0x2e, 0x80, 0x3e); a.word('init_state'); a.b(0x00)   # cmp byte cs:[init_state], 0
    a.short(0x74, 'pk_setup')                                # je pk_setup
    a.near(0xe9, 'pi_fight')                                 # jmp pi_fight
    a.label('pk_setup')
    a.b(0xb4, LAIR_SIZE, 0xf6, 0xe4)                         # mov ah, 12h / mul ah
    a.b(0x05, LAIR_RECORDS & 0xff, LAIR_RECORDS >> 8, 0x8b, 0xf8)   # add ax, 2 / mov di, ax   the lair's record
    a.b(0x89, 0x3e, 0x62, 0x69)                              # mov [6962h], di   (its monsters and count)
    a.b(0x2e, 0xc6, 0x06); a.word('init_state'); a.b(0x01)   # mov byte cs:[init_state], 1
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x5e, 0x05)   # mov word cs:[call_target], 055Eh
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x42, 0x01)      # mov word cs:[call_ret], 0142h (the int again)
    a.near(0xe9, 'call_game')                                # jmp call_game
    a.label('pi_fight')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x2c, 0x1f)   # mov word cs:[call_target], 1F2Ch
    a.label('pi_after')                                      # the fight's set-up: alone, or then add the knights
    a.b(0x2e, 0xc6, 0x06); a.word('init_state'); a.b(0x00)   # mov byte cs:[init_state], 0
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'pi_then_add')                             # jne pi_then_add
    a.near(0xe9, 'pi_go_on')                                 # jmp pi_go_on
    a.label('pi_then_add')
    a.near(0xe8, 'combine')                                  # call combine       knight 1 = all knights' sum
    a.b(0x2e, 0xc6, 0x06); a.word('init_state'); a.b(ADD_STATE)   # mov byte cs:[init_state], 10
    a.label('pi_again')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x42, 0x01)      # mov word cs:[call_ret], 0142h (the int again)
    a.near(0xe9, 'call_game')                                # jmp call_game
    # pi_add: knight k = (state - 10) / 2 + 1; an even state sets it up as InitPractice does (1000:200F: fields,
    # 1F76), an odd one gives it the knights' colour bank and registers it (2998). After the last, on at 0145
    a.label('pi_add')
    a.b(0x2e, 0x80, 0x3e); a.word('init_state'); a.b(ADD_STATE)   # cmp byte cs:[init_state], 10
    a.short(0x75, 'pa_state')                                # jne pa_state
    a.near(0xe8, 'uncombine')                                # call uncombine     the set-up is done: knight 1 back
    a.label('pa_state')
    a.b(0x2e, 0xa0); a.word('init_state')                    # mov al, cs:[init_state]
    a.b(0x2c, ADD_STATE, 0x8a, 0xe0, 0xd0, 0xe8)             # sub al, 10 / mov ah, al / shr al, 1   al = k - 1
    a.b(0xfe, 0xc0)                                          # inc al                   k
    a.b(0x2e, 0x3a, 0x06); a.word('coop')                    # cmp al, cs:[coop]
    a.short(0x72, 'pa_knight')                               # jb pa_knight
    a.b(0x2e, 0xc6, 0x06); a.word('init_state'); a.b(0x00)   # mov byte cs:[init_state], 0
    a.b(0xc7, 0x46, 0x02, 0x45, 0x01)                        # mov word [bp+2], 0145h   on with the fight
    a.b(0x2e, 0x80, 0x3e); a.word('mon_mode'); a.b(0x00); a.short(0x74, 'pa_k1_kept')
    a.b(0x2e, 0x80, 0x3e); a.word('k1_out'); a.b(0x00); a.short(0x75, 'pa_k1_kept')
    a.b(0xa0, (KNIGHTS[0] + 9) & 0xff, (KNIGHTS[0] + 9) >> 8, 0x2e, 0xa2); a.word('k1_ctl')   # keep its +9
    a.b(0xc6, 0x06, (KNIGHTS[0] + 9) & 0xff, (KNIGHTS[0] + 9) >> 8, KEYS3_CONTROL)          # the third key set
    a.label('pa_k1_kept')
    a.near(0xe8, 'k1_away')                                  # at once, before the fight is drawn
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('pa_knight')
    a.b(0xfe, 0xc8, 0xb3, 0x06, 0xf6, 0xe3)                  # dec al / mov bl, 6 / mul bl   (k - 1) * 6
    a.b(0x8b, 0xd8)                                          # mov bx, ax               the knight's entry
    a.b(0x2e, 0x8b, 0xbf); a.word('coop_knights')            # mov di, cs:[bx+coop_knights]   the record
    a.b(0x2e, 0xfe, 0x06); a.word('init_state')              # inc byte cs:[init_state]
    a.b(0x2e, 0xf6, 0x06); a.word('init_state'); a.b(0x01)   # test byte cs:[init_state], 1
    a.short(0x74, 'pa_register')                             # jz pa_register   (now even: it was the odd step)
    a.b(0xc6, 0x45, 0x35, 0x06)                              # mov byte [di+35h], 6
    a.b(0x2e, 0x8a, 0x87); a.word('coop_knights', 2)         # mov al, cs:[bx+coop_knights+2]   control
    a.b(0x88, 0x45, 0x09)                                    # mov [di+9], al
    a.b(0x2e, 0x8a, 0x87); a.word('coop_knights', 3)         # mov al, cs:[bx+coop_knights+3]   colour slot
    a.b(0x32, 0xe4, 0x89, 0x45, 0x20)                        # xor ah, ah / mov [di+20h], ax
    a.b(0x2e, 0x8b, 0x87); a.word('coop_knights', 4)         # mov ax, cs:[bx+coop_knights+4]   x
    a.b(0x89, 0x45, 0x02)                                    # mov [di+2], ax
    a.b(0xc7, 0x45, 0x04, 0x00, 0x00)                        # mov word [di+4], 0
    a.b(0xc7, 0x45, 0x06, 0x64, 0x00)                        # mov word [di+6], 100
    a.b(0xc6, 0x45, 0x08, 0x03)                              # mov byte [di+8], 3       facing left
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x76, 0x1f)   # mov word cs:[call_target], 1F76h
    a.near(0xe9, 'pi_again')                                 # jmp pi_again
    a.label('pa_register')
    a.b(0xc7, 0x45, 0x18, 0x33, 0x89)                        # mov word [di+18h], 8933h  the knights' bank
    a.b(0xbe, 0xe4, 0x15)                                    # mov si, 15E4h            standing script
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x98, 0x29)   # mov word cs:[call_target], 2998h
    a.near(0xe9, 'pi_again')                                 # jmp pi_again

    # combine (D15): for the fight's set-up knight 1 has the sum of the co-op knights' strength (at most 127, a
    # signed byte) and maximum hit points (at most 999), the stats 1000:2830 counts the monsters by; uncombine puts
    # knight 1's own back
    a.label('combine')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56)                        # push ax bx cx dx si
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   the fight's own knight (practice: 1)
    a.b(0x2e, 0x89, 0x36); a.word('combined')                # mov cs:[combined], si
    a.b(0x8a, 0x44, STRENGTH, 0x2e, 0xa2); a.word('own_strength')   # mov al, [si+2Eh] / mov cs:[own_strength], al
    a.b(0x8b, 0x44, MAX_HP_FIELD, 0x2e, 0xa3); a.word('own_max_hp')  # mov ax, [si+3Ch] / mov cs:[own_max_hp], ax
    a.b(0x33, 0xd2, 0x33, 0xc0, 0x33, 0xc9)                  # xor dx, dx (strength) / xor ax, ax (HP) / xor cx, cx
    a.b(0x2e, 0x8a, 0x0e); a.word('k1_out')                  # mov cl, cs:[k1_out]   knight 1 out: not counted
    a.label('cb_loop')
    a.b(0x8b, 0xd9, 0xd1, 0xe3)                              # mov bx, cx / shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('knight_list')             # mov bx, cs:[bx+knight_list]
    a.b(0x02, 0x57, STRENGTH, 0x80, 0xd6, 0x00)              # add dl, [bx+2Eh] / adc dh, 0
    a.b(0x03, 0x47, MAX_HP_FIELD)                            # add ax, [bx+3Ch]
    a.b(0x41)                                                # inc cx
    a.b(0x2e, 0x3a, 0x0e); a.word('coop')                    # cmp cl, cs:[coop]
    a.short(0x72, 'cb_loop')                                 # jb cb_loop
    a.b(0x81, 0xfa, 0x7f, 0x00)                              # cmp dx, 127
    a.short(0x76, 'cb_str')                                  # jbe cb_str
    a.b(0xb2, 0x7f)                                          # mov dl, 127
    a.label('cb_str')
    a.b(0x88, 0x54, STRENGTH)                                # mov [si+2Eh], dl
    a.b(0x3d, MAX_HP & 0xff, MAX_HP >> 8)                    # cmp ax, 999
    a.short(0x76, 'cb_hp')                                   # jbe cb_hp
    a.b(0xb8, MAX_HP & 0xff, MAX_HP >> 8)                    # mov ax, 999
    a.label('cb_hp')
    a.b(0x89, 0x44, MAX_HP_FIELD)                            # mov [si+3Ch], ax
    a.b(0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)                  # pop si dx cx bx ax / ret
    a.label('uncombine')
    a.b(0x50, 0x56, 0x2e, 0x8b, 0x36); a.word('combined')    # push ax si / mov si, cs:[combined]
    a.b(0x2e, 0xa0); a.word('own_strength'); a.b(0x88, 0x44, STRENGTH)   # mov al, cs:[own_strength] / mov [si+2Eh], al
    a.b(0x2e, 0xa1); a.word('own_max_hp'); a.b(0x89, 0x44, MAX_HP_FIELD)  # mov ax, cs:[own_max_hp] / mov [si+3Ch], ax
    a.b(0x5e, 0x58, 0xc3)                                    # pop si ax / ret

    # update (D15, 1000:98FD, replaces mov bx,[di+1Ah] before the fight's update pass calls an object's handler,
    # si = the object): the monsters' moves read the knight they fight from [0978h] all over (1000:30EE, 310D, 32CE,
    # ...), so in co-op [0978h] is set for each object: a monster gets the knight it goes for (pick_target), anything
    # else the first knight standing (knight 1 while it stands)
    a.label('rules_update')
    a.b(0x8b, 0x5d, 0x1a, 0x89, 0x5e, 0xfe)                  # mov bx, [di+1Ah] / mov [bp-2], bx   as the game
    a.near(0xe8, 'cheat_object')                             # call cheat_object   cheat codes
    a.near(0xe8, 'hard_rest')                                # call hard_rest      TOOEASY
    a.b(0x81, 0xfe, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)   # cmp si, 6E26h   the dragon's turn
    a.short(0x75, 'up_not_dragon')                           # jne up_not_dragon
    a.near(0xe8, 'dragon_front')                             # call dragon_front
    a.label('up_not_dragon')
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'up_coop'); a.near(0xe9, 'up_done')        # jne up_coop / jmp up_done
    a.label('up_coop')
    a.b(0x50)                                                # push ax
    a.near(0xe8, 'first_standing')                           # call first_standing   ax
    a.b(0x81, 0xfe, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)   # cmp si, 6E26h
    a.short(0x74, 'up_monster')                              # je up_monster
    a.b(0x81, 0xfe, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)   # cmp si, 6F08h
    a.short(0x72, 'up_set')                                  # jb up_set            a knight
    end_slots = MONSTER_SLOTS + MONSTER_COUNT * SLOT_SIZE
    a.b(0x81, 0xfe, end_slots & 0xff, end_slots >> 8)        # cmp si, 76B0h
    a.short(0x73, 'up_set')                                  # jae up_set           not a fighter
    a.label('up_monster')
    a.b(0x2e, 0xf6, 0x06); a.word('rules_table', G_PRACTICE_FLAGS); a.b(TARGET_FIRST)   # test flags, first
    a.short(0x75, 'up_set')                                  # jnz up_set           all go for the first knight
    a.b(0x57, 0x8b, 0xfe)                                    # push di / mov di, si
    a.near(0xe8, 'pick_target')                              # call pick_target
    a.b(0x5f)                                                # pop di
    a.label('up_set')
    a.b(0xa3, 0x78, 0x09, 0x58)                              # mov [0978h], ax / pop ax
    a.label('up_done')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # first_standing: ax = the first knight in knight_list standing; knight 1 if none is
    a.label('first_standing')
    a.b(0x53, 0x51, 0x33, 0xc9)                              # push bx cx / xor cx, cx
    a.label('fs_loop')
    a.b(0x8b, 0xd9, 0xd1, 0xe3)                              # mov bx, cx / shl bx, 1
    a.b(0x2e, 0x8b, 0x87); a.word('knight_list')             # mov ax, cs:[bx+knight_list]
    a.b(0x8b, 0xd8, 0x83, 0x7f, 0x38, 0x00)                  # mov bx, ax / cmp word [bx+38h], 0
    a.short(0x7f, 'fs_found')                                # jg fs_found
    a.b(0x41)                                                # inc cx
    a.b(0x2e, 0x3a, 0x0e); a.word('coop')                    # cmp cl, cs:[coop]
    a.short(0x72, 'fs_loop')                                 # jb fs_loop
    a.b(0x2e, 0xa1); a.word('knight_list')                   # mov ax, cs:[knight_list]
    a.label('fs_found')
    a.b(0x59, 0x5b, 0xc3)                                    # pop cx bx / ret

    # pick_target: di = a monster -> ax = the nearest knight standing (by x and depth), kept unless another is more
    # than the target margin nearer; ax unchanged when no knight stands. A new knight is kept for TARGET_HOLD of
    # the monster's updates whatever the distances: a monster between two knights at other depths (blocked in
    # depth by the knights, sent back in x by hard_step) switched between them at every update and never moved on
    a.label('pick_target')
    a.b(0x53, 0x51, 0x52, 0x56)                              # push bx cx dx si
    a.b(0xbb, 0xff, 0xff, 0x33, 0xc9)                        # mov bx, 0FFFFh (best distance) / xor cx, cx (best)
    a.b(0x33, 0xd2)                                          # xor dx, dx          knight number
    a.label('tg_loop')
    a.b(0x8b, 0xf2, 0xd1, 0xe6)                              # mov si, dx / shl si, 1
    a.b(0x2e, 0x8b, 0xb4); a.word('knight_list')             # mov si, cs:[si+knight_list]
    a.b(0x83, 0x7c, 0x38, 0x00)                              # cmp word [si+38h], 0
    a.short(0x7e, 'tg_next')                                 # jle tg_next          down
    a.b(0x50)                                                # push ax
    a.near(0xe8, 'distance')                                 # call distance        ax
    a.b(0x3b, 0xc3)                                          # cmp ax, bx
    a.short(0x73, 'tg_far')                                  # jae tg_far
    a.b(0x8b, 0xd8, 0x8b, 0xce)                              # mov bx, ax / mov cx, si
    a.label('tg_far')
    a.b(0x58)                                                # pop ax
    a.label('tg_next')
    a.b(0x42)                                                # inc dx
    a.b(0x2e, 0x3a, 0x16); a.word('coop')                    # cmp dl, cs:[coop]
    a.short(0x72, 'tg_loop')                                 # jb tg_loop
    a.short(0xe3, 'tg_none')                                 # jcxz tg_none         nobody standing
    # keep the last knight unless the best is clearly nearer
    a.b(0x8b, 0xc7, 0x3d, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)   # mov ax, di / cmp ax, 6E26h
    a.short(0x75, 'tg_slot')                                 # jne tg_slot
    a.b(0xb8, MONSTER_COUNT, 0x00)                           # mov ax, 20          the dragon's place
    a.short(0xeb, 'tg_index')                                # jmp tg_index
    a.label('tg_slot')
    a.b(0x2d, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)      # sub ax, 6F08h
    a.short(0x72, 'tg_pick')                                 # jb tg_pick           not a slot: no memory
    a.b(0x52, 0x33, 0xd2, 0xbe, SLOT_SIZE, 0x00, 0xf7, 0xf6, 0x5a)   # push dx / xor dx, dx / mov si, 62h / div si / pop dx
    a.b(0x3d, MONSTER_COUNT, 0x00)                           # cmp ax, 20
    a.short(0x73, 'tg_pick')                                 # jae tg_pick
    a.label('tg_index')
    a.b(0xd1, 0xe0, 0x8b, 0xd0, 0x8b, 0xf2)                  # shl ax, 1 / mov dx, ax / mov si, dx   dx = its index
    a.b(0x2e, 0x8b, 0x84); a.word('last_target')             # mov ax, cs:[si+last_target]
    a.b(0x2e, 0x89, 0x8c); a.word('last_target')             # mov cs:[si+last_target], cx   (the best, for now)
    a.b(0x0b, 0xc0)                                          # or ax, ax
    a.short(0x74, 'tg_new')                                  # jz tg_new
    a.b(0x3b, 0xc1)                                          # cmp ax, cx
    a.short(0x74, 'tg_pick')                                 # je tg_pick
    a.b(0x8b, 0xf0)                                          # mov si, ax   the last knight
    a.b(0x83, 0x7c, 0x38, 0x00)                              # cmp word [si+38h], 0
    a.short(0x7e, 'tg_new')                                  # jle tg_new          down: the best
    a.b(0x87, 0xf2)                                          # xchg si, dx   si = the index, dx = the last knight
    a.b(0x2e, 0x83, 0xbc); a.word('target_hold'); a.b(0x00)  # cmp word cs:[si+target_hold], 0
    a.short(0x74, 'tg_cmp')                                  # je tg_cmp
    a.b(0x2e, 0xff, 0x8c); a.word('target_hold')             # dec word cs:[si+target_hold]   still held: keep it
    a.short(0xeb, 'tg_keep')                                 # jmp tg_keep
    a.label('tg_cmp')
    a.b(0x87, 0xf2)                                          # xchg si, dx   si = the last knight
    a.near(0xe8, 'distance')                                 # call distance
    a.b(0x52, 0x2e, 0x8a, 0x16); a.word('rules_table', G_TARGET_MARGIN)   # push dx / mov dl, cs:[margin]
    a.b(0x32, 0xf6, 0x03, 0xda, 0x5a)                        # xor dh, dh / add bx, dx / pop dx
    a.b(0x3b, 0xc3)                                          # cmp ax, bx
    a.short(0x77, 'tg_new')                                  # ja tg_new           clearly farther: switch
    a.b(0x87, 0xf2)                                          # xchg si, dx   si = the index, dx = the last knight
    a.label('tg_keep')
    a.b(0x8b, 0xca)                                          # mov cx, dx
    a.b(0x2e, 0x89, 0x8c); a.word('last_target')             # mov cs:[si+last_target], cx   keep it
    a.short(0xeb, 'tg_pick')                                 # jmp tg_pick
    a.label('tg_new')                                        # a new knight (cx): held a while
    a.b(0x8b, 0xf2)                                          # mov si, dx
    a.b(0x2e, 0xc7, 0x84); a.word('target_hold'); a.b(TARGET_HOLD, 0x00)   # mov word cs:[si+target_hold], n
    a.label('tg_pick')
    a.b(0x8b, 0xc1)                                          # mov ax, cx
    a.label('tg_none')
    a.b(0x5e, 0x5a, 0x59, 0x5b, 0xc3)                        # pop si dx cx bx / ret
    a.label('distance')                                      # ax = |x(si) - x(di)| + |depth(si) - depth(di)|
    a.b(0x52, 0x8b, 0x44, 0x02, 0x2b, 0x45, 0x02)            # push dx / mov ax, [si+2] / sub ax, [di+2]
    a.short(0x79, 'ds_x'); a.b(0xf7, 0xd8)                   # jns / neg ax
    a.label('ds_x')
    a.b(0x8b, 0xd0, 0x8b, 0x44, 0x06, 0x2b, 0x45, 0x06)      # mov dx, ax / mov ax, [si+6] / sub ax, [di+6]
    a.short(0x79, 'ds_z'); a.b(0xf7, 0xd8)                   # jns / neg ax
    a.label('ds_z')
    a.b(0x03, 0xc2)                                          # add ax, dx
    # TOOEASY: the knight's hit points count as distance: the monsters go for a weak knight before a strong one
    a.b(0x2e, 0x80, 0x3e); a.word('hard_eff'); a.b(0x00); a.short(0x74, 'dist_end')
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'dist_end'); a.b(0x03, 0x44, 0x38)   # cmp word [si+38h], 0 / jle / add ax, [si+38h]
    a.label('dist_end')
    # TOOHARD: the hit points a knight has lost count as distance: the monsters go for a healthier knight first
    a.b(0x2e, 0x80, 0x3e); a.word('easy_eff'); a.b(0x00); a.short(0x74, 'dist_ret')
    a.b(0x8b, 0x54, MAX_HP_FIELD, 0x2b, 0x54, 0x38); a.short(0x7e, 'dist_ret'); a.b(0x03, 0xc2)   # mov dx, [si+3Ch] / sub dx, [si+38h] / jle / add ax, dx
    a.label('dist_ret')
    a.b(0x5a, 0xc3)                                          # pop dx / ret

    # dragon_rest, guardian_rest (K6; 1000:3861 and 4F6A, replace cmp word [di/si+0Eh],0, the check whether the
    # dragon or the Guardian was hit, which comes before anything else in its update): a hit restarts its hit
    # reaction at once, so quick blows (the upward thrust under the dragon) kept it from ever fighting back. A hit
    # within the table's ticks of the last counted one is dropped (as practice_hit drops one: the attacker's +0Ch
    # too); the handler is not called every frame, so the time is BIOS ticks. Returns the flags of the compare
    a.label('rules_dragon_rest')
    a.b(0x8b, 0xdf, 0xb0, 0x00)                              # mov bx, di / mov al, 0
    a.short(0xeb, 'hr_start')                                # jmp hr_start
    a.label('rules_guardian_rest')
    a.b(0x8b, 0xde, 0xb0, 0x01)                              # mov bx, si / mov al, 1
    a.label('hr_start')
    a.b(0x50, 0x51, 0x52, 0x56, 0x06)                        # push ax cx dx si es
    a.b(0x83, 0x7f, 0x0e, 0x00)                              # cmp word [bx+0Eh], 0
    a.short(0x74, 'hr_end')                                  # je hr_end            not hit
    a.b(0x32, 0xe4, 0x8b, 0xf0)                              # xor ah, ah / mov si, ax
    a.b(0x2e, 0x8a, 0x8c); a.word('rules_table', G_HIT_REST) # mov cl, cs:[si+hit_rest]
    a.b(0x32, 0xed, 0xe3); a.b(0x00); hr_off = len(a.code) - 1   # xor ch, ch / jcxz hr_end   0: every hit
    a.b(0x33, 0xd2, 0x8e, 0xc2, 0x26, 0x8b, 0x16, 0x6c, 0x04)   # xor dx, dx / mov es, dx / mov dx, es:[046Ch]
    a.b(0xd1, 0xe6)                                          # shl si, 1
    a.b(0x2e, 0x8b, 0x84); a.word('last_hit')                # mov ax, cs:[si+last_hit]
    a.b(0x0b, 0xc0); a.short(0x74, 'hr_count')               # or ax, ax / jz hr_count   none yet
    a.b(0xf7, 0xd8, 0x03, 0xc2)                              # neg ax / add ax, dx       ticks since
    a.b(0x3b, 0xc1); a.short(0x72, 'hr_drop')                # cmp ax, cx / jb hr_drop
    a.label('hr_count')
    a.b(0x0b, 0xd2, 0x75, 0x01, 0x42)                        # or dx, dx / jnz +1 / inc dx   (0 = none)
    a.b(0x2e, 0x89, 0x94); a.word('last_hit')                # mov cs:[si+last_hit], dx
    a.short(0xeb, 'hr_end')                                  # jmp hr_end
    a.label('hr_drop')
    a.b(0x8b, 0x77, 0x0e, 0xc7, 0x47, 0x0e, 0x00, 0x00)      # mov si, [bx+0Eh] / mov word [bx+0Eh], 0
    a.b(0x39, 0x5c, 0x0c); a.short(0x75, 'hr_end')           # cmp [si+0Ch], bx / jne hr_end
    a.b(0xc7, 0x44, 0x0c, 0x00, 0x00)                        # mov word [si+0Ch], 0
    a.label('hr_end')
    a.code[hr_off] = (a.labels['hr_end'] - (a.org + hr_off + 1)) & 0xff
    a.b(0x07, 0x5e, 0x5a, 0x59, 0x58)                        # pop es si dx cx ax
    a.b(0x83, 0x7f, 0x0e, 0x00)                              # cmp word [bx+0Eh], 0   (replaced)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # dragon_target (K21; 1000:A80D, replaces sub cx,cx before the dragon's random target roll): the map set-up
    # (1000:A6E1, called again whenever the map is drawn anew, e.g. after the item screen) runs the dragon's set-up
    # 1000:A78C, which rolls a new target each time, so leaving the item screen rerolled it. Called from there
    # (not by the Scroll of the Wyrm, 1000:ADEE), the dragon keeps a target that still has lives
    a.label('rules_dragon_target')
    a.b(0x33, 0xc9)                                          # xor cx, cx            (replaced)
    a.b(0x2e, 0xf6, 0x06); a.word('rules_table', G_EXPLOIT_FIXES); a.b(KEEP_DRAGON_TARGET)   # test flags, keep
    a.short(0x74, 'dt_end')                                  # jz dt_end             speedrun mode: as the game
    a.b(0x81, 0x7e, 0x08, MAP_REDRAW_RET & 0xff, MAP_REDRAW_RET >> 8)   # cmp word [bp+8], A72Ch
    a.short(0x75, 'dt_end')                                  # jne dt_end            the Wyrm: a new target
    a.b(0x56, 0x8b, 0x36, (DRAGON_RECORD + 0x46) & 0xff, (DRAGON_RECORD + 0x46) >> 8)   # push si / mov si, [6E6Ch]
    for rec in KNIGHTS:
        a.b(0x81, 0xfe, rec & 0xff, rec >> 8)                # cmp si, record
        a.short(0x74, 'dt_knight')                           # je dt_knight
    a.short(0xeb, 'dt_pop')                                  # jmp dt_pop            no target yet
    a.label('dt_knight')
    a.b(0x80, 0x7c, 0x31, 0x00)                              # cmp byte [si+31h], 0  lives
    a.short(0x7e, 'dt_pop')                                  # jle dt_pop
    a.b(0xc7, 0x46, 0x02, TARGET_KEPT & 0xff, TARGET_KEPT >> 8)   # mov word [bp+2], A831h   ret: target kept
    a.label('dt_pop')
    a.b(0x5e)                                                # pop si
    a.label('dt_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # dragon_debug (D21; 1000:A5BB, replaces mov di,6E26h before the map loop's dragon check, run on every pass):
    # with dragon_debug_mode = 1 and the dragon on the map ([CCB0h] = 1), the keys 1-4 (scan codes 2-5, MAIN's key
    # table) make knight 1-4 (6C9Eh + n * 62h, with lives) the dragon's target (+46h); Enter (fire, [CC9Ah] bit 10h)
    # by a human knight that stands under the dragon (the list DS:0490 the map drawing fills, 1000:0816) makes it
    # the target, so the game's own check right after (A5BE) starts the fight
    a.label('rules_dragon_debug')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_DRAGON_DEBUG); a.b(0x00)   # cmp byte cs:[dragon_debug_mode], 0
    a.short(0x74, 'dd_end')                                  # je dd_end
    a.b(0x83, 0x3e, 0xb0, 0xcc, 0x00)                        # cmp word [0CCB0h], 0   the dragon on the map
    a.short(0x74, 'dd_end')                                  # je dd_end
    a.b(0x50, 0x53, 0x51, 0x56, 0x06)                        # push ax bx cx si es
    a.b(0x8e, 0x46, 0x04)                                    # mov es, [bp+4]    MAIN's code segment
    a.b(0x33, 0xc9)                                          # xor cx, cx
    a.label('dd_scan')
    a.b(0x8b, 0xd9)                                          # mov bx, cx
    a.b(0x26, 0x80, 0xbf); a.b(struct.pack('<H', KEY_TABLE + 2)); a.b(0xff)   # cmp byte es:[bx+81E5h], 0FFh
    a.short(0x73, 'dd_next')                                 # jae dd_next       not held
    a.b(0xb0, 0x62, 0xf6, 0xe1)                              # mov al, 62h / mul cl
    a.b(0x05, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8, 0x8b, 0xf0)   # add ax, 6C9Eh / mov si, ax
    a.b(0x80, 0x7c, 0x31, 0x00)                              # cmp byte [si+31h], 0   lives
    a.short(0x7e, 'dd_next')                                 # jle dd_next
    a.b(0x89, 0x36, (DRAGON_RECORD + 0x46) & 0xff, (DRAGON_RECORD + 0x46) >> 8)   # mov [6E6Ch], si
    a.label('dd_next')
    a.b(0x41, 0x83, 0xf9, 0x04)                              # inc cx / cmp cx, 4
    a.short(0x72, 'dd_scan')                                 # jb dd_scan
    a.b(0xf6, 0x06, 0x9a, 0xcc, 0x10)                        # test byte [0CC9Ah], 10h   fire
    a.short(0x74, 'dd_pop')                                  # jz dd_pop
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   the knight whose turn it is
    a.b(0x83, 0x7c, 0x20, 0x04)                              # cmp word [si+20h], 4
    a.short(0x74, 'dd_pop')                                  # je dd_pop         a computer knight
    a.b(0xbb, 0x90, 0x04, 0xb9, 0x04, 0x00)                  # mov bx, 0490h / mov cx, 4
    a.label('dd_list')
    a.b(0x3b, 0x37)                                          # cmp si, [bx]
    a.short(0x74, 'dd_fight')                                # je dd_fight
    a.b(0x83, 0xc3, 0x02)                                    # add bx, 2
    a.short(0xe2, 'dd_list')                                 # loop dd_list
    a.short(0xeb, 'dd_pop')                                  # jmp dd_pop        not under the dragon
    a.label('dd_fight')
    a.b(0x89, 0x36, (DRAGON_RECORD + 0x46) & 0xff, (DRAGON_RECORD + 0x46) >> 8)   # mov [6E6Ch], si
    a.label('dd_pop')
    a.b(0x07, 0x5e, 0x59, 0x5b, 0x58)                        # pop es si cx bx ax
    a.label('dd_end')
    a.b(0xbf, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)      # mov di, 6E26h     (replaced)
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # --- D22: gore off (the game's [0700h] set, or death_animations = off) ---
    # d20_state: ZF = 1 when the new deaths (D20) are on: death_animations = extended and gore on
    a.label('d20_state')
    a.b(0x50, 0x2e, 0xa0); a.word('rules_table', G_DEATHS)   # push ax / mov al, cs:[death_animations]
    a.b(0x0a, 0xc0); a.short(0x75, 'ds_end')                 # or al, al / jnz ds_end   ZF = 0
    a.near(0xe8, 'deaths_gore')                              # call deaths_gore
    a.label('ds_end')
    a.b(0x58, 0xc3)                                          # pop ax / ret
    # deaths_gore: ZF = 1 when the deaths may be gory: gore on and age_rating K18 (at K16 the deaths keep to gore
    # off's rules, blood or not: no fatalities)
    a.label('deaths_gore')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_AGE); a.b(18); a.short(0x75, 'dg_ret')   # below K18: ZF = 0
    a.b(0x83, 0x3e, GORE & 0xff, GORE >> 8, 0x00)            # cmp word [0700h], 0
    a.label('dg_ret')
    a.b(0xc3)

    # crush_troll (1000:43B0, mov word [783Ah],16E2h: the troll's blow from above on a knight down), crush_balok
    # (1000:3729, mov si,16E2h: the Balok lands on a knight): the knight crushed into a pool of blood; with gore off
    # the plain death (slump, then lying) instead
    for name, troll in (('crush_troll', True), ('crush_balok', False)):
        a.label('rules_' + name)
        a.b(0x50, 0xb8, CRUSH & 0xff, CRUSH >> 8)            # push ax / mov ax, 16E2h
        a.near(0xe8, 'deaths_gore')                          # gore on, K18?
        a.short(0x74, name + '_set')                         # je set
        a.b(0xb8, PLAIN_DEATH & 0xff, PLAIN_DEATH >> 8)      # mov ax, 1310h
        a.label(name + '_set')
        if troll:
            a.b(0xa3, 0x3a, 0x78)                            # mov [783Ah], ax
        else:
            a.b(0x8b, 0xf0)                                  # mov si, ax
        a.b(0x58); a.near(0xe9, 'rules_done')                # pop ax / jmp rules_done

    # set_gore_pass (from draw, di = the animation slot): what gore_clean does to the frame: 0 nothing (gore on,
    # not a fight's object, the dragon and its fire, whose own colours use 15), 1 a frame of blood only (all its
    # pixels 15) not drawn, 2 also the blood in a frame: the knights (their banks use 15 for blood only), the
    # Balok, the boar
    a.label('set_gore_pass')
    a.b(0x50, 0x53)                                          # push ax bx
    a.b(0x2e, 0xc6, 0x06); a.word('gore_pass'); a.b(0x00)    # mov byte cs:[gore_pass], 0
    a.b(0x83, 0x3e, GORE & 0xff, GORE >> 8, 0x00)            # cmp word [0700h], 0
    a.short(0x74, 'sg_end')                                  # je sg_end
    a.b(0x8b, 0x5d, 0x16)                                    # mov bx, [di+16h]
    a.b(0x81, 0xfb, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)      # cmp bx, 6C9Eh
    a.short(0x72, 'sg_end')                                  # jb sg_end
    end_slots = MONSTER_SLOTS + MONSTER_COUNT * SLOT_SIZE
    a.b(0x81, 0xfb, end_slots & 0xff, end_slots >> 8)        # cmp bx, 76B0h
    a.short(0x73, 'sg_end')                                  # jae sg_end
    a.b(0xb0, 0x02)                                          # mov al, 2
    a.b(0x81, 0xfb, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)   # cmp bx, 6E26h
    a.short(0x72, 'sg_set')                                  # jb sg_set          a knight's record
    a.short(0x74, 'sg_end')                                  # je sg_end          the dragon
    a.b(0x8a, 0x67, 0x35)                                    # mov ah, [bx+35h]   the type
    for t in (0x0a, 0x16):                                   # the dragon's fire
        a.b(0x80, 0xfc, t); a.short(0x74, 'sg_end')
    for t in (0x06, COMPUTER_TYPE, BALOK_TYPE, 0x00):        # knights, the Balok, the boar
        a.b(0x80, 0xfc, t); a.short(0x74, 'sg_set')
    a.b(0xb0, 0x01)                                          # mov al, 1
    a.label('sg_set')
    a.b(0x2e, 0xa2); a.word('gore_pass')                     # mov cs:[gore_pass], al
    a.label('sg_end')
    a.b(0x5b, 0x58, 0xc3)                                    # pop bx ax / ret

    # gore_clean (from recolour; es:0 = the frame as the converter wrote it, a byte a pixel, 0 = not drawn): a
    # frame of blood only (15) is cleared; with gore_pass 2 a blood pixel takes the colour of the pixel before it
    # (or after it) in its row, so the blood on a body looks like the body, and else is cleared. The first look
    # stops as soon as the answer is known: with gore_pass 1 at the first pixel that is not blood (most frames,
    # nothing to do), with 2 once it has seen both blood and another colour
    a.label('gore_clean')
    a.b(0x50, 0x53, 0x51, 0x52, 0x57, 0x1e)                  # push ax bx cx dx di ds
    a.b(0x2e, 0x8a, 0x16); a.word('gore_pass')               # mov dl, cs:[gore_pass]
    a.b(0x8e, 0x5e, 0x04)                                    # mov ds, [bp+4]     MAIN's code segment
    a.b(0xfc, 0x8b, 0x0e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)   # cld / mov cx, [637Bh]
    a.short(0xe3, 'gc_out')                                  # jcxz gc_out
    a.b(0x33, 0xff, 0x33, 0xdb)                              # xor di, di / xor bx, bx
    a.label('gc_scan')
    a.b(0x26, 0x8a, 0x05, 0x0a, 0xc0)                        # mov al, es:[di] / or al, al
    a.short(0x74, 'gc_next')                                 # jz gc_next
    a.b(0x3c, 0x0f); a.short(0x75, 'gc_other')               # cmp al, 15 / jne gc_other
    a.b(0xb3, 0x01, 0x0a, 0xff)                              # mov bl, 1 / or bh, bh
    a.short(0x75, 'gc_blood'); a.short(0xeb, 'gc_next')      # jnz gc_blood (both seen) / jmp gc_next
    a.label('gc_other')
    a.b(0x80, 0xfa, 0x02); a.short(0x75, 'gc_out')           # cmp dl, 2 / jne gc_out   pass 1: not blood only
    a.b(0xb7, 0x01, 0x0a, 0xdb)                              # mov bh, 1 / or bl, bl
    a.short(0x75, 'gc_blood')                                # jnz gc_blood       both seen
    a.label('gc_next')
    a.b(0x47); a.short(0xe2, 'gc_scan')                      # inc di / loop gc_scan
    a.b(0x0a, 0xdb); a.short(0x75, 'gc_blood')               # or bl, bl / jnz gc_blood
    a.label('gc_out')
    a.near(0xe9, 'gc_end')                                   # jmp gc_end          no blood
    a.label('gc_blood')
    a.b(0x8b, 0x0e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)      # mov cx, [637Bh]
    a.b(0x0a, 0xff); a.short(0x75, 'gc_mixed')               # or bh, bh / jnz gc_mixed
    a.b(0x33, 0xff, 0x32, 0xc0, 0xf3, 0xaa)                  # xor di, di / xor al, al / rep stosb   blood only
    a.short(0xeb, 'gc_out')                                  # jmp gc_out
    a.label('gc_mixed')
    a.b(0x2e, 0x80, 0x3e); a.word('gore_pass'); a.b(0x02)    # cmp byte cs:[gore_pass], 2
    a.short(0x75, 'gc_out')                                  # jne gc_out
    a.b(0x49); a.short(0x74, 'gc_rest')                      # dec cx / jz gc_rest   one pixel
    a.b(0xbf, 0x01, 0x00)                                    # mov di, 1
    a.label('gc_fwd')
    a.b(0x26, 0x80, 0x3d, 0x0f); a.short(0x75, 'gc_fn')      # cmp byte es:[di], 15 / jne gc_fn
    a.b(0x26, 0x8a, 0x45, 0xff)                              # mov al, es:[di-1]
    a.b(0x0a, 0xc0); a.short(0x74, 'gc_fn')                  # or al, al / jz gc_fn
    a.b(0x3c, 0x0f); a.short(0x74, 'gc_fn')                  # cmp al, 15 / je gc_fn
    a.b(0x26, 0x88, 0x05)                                    # mov es:[di], al
    a.label('gc_fn')
    a.b(0x47); a.short(0xe2, 'gc_fwd')                       # inc di / loop gc_fwd
    a.b(0x8b, 0x0e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)      # mov cx, [637Bh]
    a.b(0x49, 0x8b, 0xf9, 0x4f)                              # dec cx / mov di, cx / dec di   n-2 down to 0
    a.label('gc_bwd')
    a.b(0x26, 0x80, 0x3d, 0x0f); a.short(0x75, 'gc_bn')      # cmp byte es:[di], 15 / jne gc_bn
    a.b(0x26, 0x8a, 0x45, 0x01)                              # mov al, es:[di+1]
    a.b(0x0a, 0xc0); a.short(0x74, 'gc_bn')                  # or al, al / jz gc_bn
    a.b(0x3c, 0x0f); a.short(0x74, 'gc_bn')                  # cmp al, 15 / je gc_bn
    a.b(0x26, 0x88, 0x05)                                    # mov es:[di], al
    a.label('gc_bn')
    a.b(0x4f); a.short(0xe2, 'gc_bwd')                       # dec di / loop gc_bwd
    a.label('gc_rest')
    a.b(0x8b, 0x0e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)      # mov cx, [637Bh]
    a.b(0x33, 0xff)                                          # xor di, di
    a.label('gc_zero')
    a.b(0x26, 0x80, 0x3d, 0x0f); a.short(0x75, 'gc_zn')      # cmp byte es:[di], 15 / jne gc_zn
    a.b(0x26, 0xc6, 0x05, 0x00)                              # mov byte es:[di], 0
    a.label('gc_zn')
    a.b(0x47); a.short(0xe2, 'gc_zero')                      # inc di / loop gc_zero
    a.label('gc_end')
    a.b(0x1f, 0x5f, 0x5a, 0x59, 0x5b, 0x58, 0xc3)            # pop ds di dx cx bx ax / ret

    # spawn_marker (from hit_pair, a hit with gore off; [bp+0] = the weapon's animation slot, [bp-2] the body's):
    # the hit marker as an object of its own (as 1000:3E89 and 981F make the game's hit effect), in the middle of
    # where the two animations' boxes meet, just in front of the body; not within MARKER_GAP ticks of the last one,
    # nor without a free object and animation slot
    a.label('spawn_marker')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57)                  # push ax bx cx dx si di
    a.b(0x83, 0x3e, GORE & 0xff, GORE >> 8, 0x00)            # cmp word [0700h], 0
    a.short(0x75, 'sm_gore_off')                             # jne sm_gore_off
    a.near(0xe9, 'sm_end')
    a.label('sm_gore_off')
    a.b(0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f)   # push ds / xor ax, ax / mov ds, ax / mov ax, [046Ch] / pop ds
    a.b(0x8b, 0xd0)                                          # mov dx, ax
    a.b(0x2e, 0x2b, 0x06); a.word('marker_tick')             # sub ax, cs:[marker_tick]
    a.b(0x3d, MARKER_GAP, 0x00)                              # cmp ax, MARKER_GAP
    a.short(0x73, 'sm_free')                                 # jae sm_free
    a.near(0xe9, 'sm_end')
    a.label('sm_free')
    a.b(0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00)   # mov di, 6F08h / mov cx, 20
    a.label('sm_obj')
    a.b(0x83, 0x3d, 0x00); a.short(0x74, 'sm_anim')          # cmp word [di], 0 / je sm_anim
    a.b(0x83, 0xc7, SLOT_SIZE); a.short(0xe2, 'sm_obj')      # add di, 62h / loop sm_obj
    a.near(0xe9, 'sm_end')
    a.label('sm_anim')
    a.b(0xbe, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # mov si, 947Eh / mov cx, 10
    a.label('sm_a')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'sm_go')            # cmp byte [si], 0 / je sm_go
    a.b(0x83, 0xc6, ANIM_SIZE); a.short(0xe2, 'sm_a')        # add si, 24h / loop sm_a
    a.near(0xe9, 'sm_end')
    a.label('sm_go')
    a.b(0x2e, 0x89, 0x16); a.word('marker_tick')             # mov cs:[marker_tick], dx
    a.b(0x2e, 0xc7, 0x06); a.word('eff_script'); a.b(MARKER_SCRIPT & 0xff, MARKER_SCRIPT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('eff_bank'); a.b(KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8)
    a.label('sm_make')
    a.b(0x56)                                                # push si            the animation slot
    a.b(0x8b, 0x76, 0x00, 0x8b, 0x5e, 0xfe)                  # mov si, [bp+0] / mov bx, [bp-2]
    for lo, size, name in ((0x0a, 0x0e, 'x'), (0x0c, 0x10, 'y')):
        a.b(0x8b, 0x44, lo, 0x8b, 0x4f, lo)                  # mov ax, [si+lo] / mov cx, [bx+lo]
        a.b(0x3b, 0xc1); a.short(0x7d, f'sm_{name}1'); a.b(0x8b, 0xc1)   # cmp ax, cx / jge / mov ax, cx   the later start
        a.label(f'sm_{name}1')
        a.b(0x8b, 0x4c, lo, 0x03, 0x4c, size)                # mov cx, [si+lo] / add cx, [si+size]
        a.b(0x8b, 0x57, lo, 0x03, 0x57, size)                # mov dx, [bx+lo] / add dx, [bx+size]
        a.b(0x3b, 0xca); a.short(0x7e, f'sm_{name}2'); a.b(0x8b, 0xca)   # cmp cx, dx / jle / mov cx, dx   the earlier end
        a.label(f'sm_{name}2')
        a.b(0x03, 0xc1, 0xd1, 0xf8)                          # add ax, cx / sar ax, 1   the middle
        if name == 'x':
            a.b(0x50)                                        # push ax
    a.b(0x8b, 0x4f, 0x08, 0x41)                              # mov cx, [bx+8] / inc cx   the body's depth, nearer
    a.b(0x2b, 0xc1)                                          # sub ax, cx         height: screen y = y + z
    a.b(0x89, 0x45, 0x04, 0x58, 0x89, 0x45, 0x02)            # mov [di+4], ax / pop ax / mov [di+2], ax
    a.b(0x89, 0x4d, 0x06)                                    # mov [di+6], cx
    a.b(0xc7, 0x05, 0x01, 0x00, 0xc6, 0x45, 0x08, 0x00)      # mov word [di], 1 / mov byte [di+8], 0
    a.b(0x2e, 0xa1); a.word('eff_bank'); a.b(0x89, 0x45, 0x18)   # mov ax, cs:[eff_bank] / mov [di+18h], ax
    a.b(0xc7, 0x45, 0x0c, 0x00, 0x00, 0xc7, 0x45, 0x0e, 0x00, 0x00)   # mov word [di+0Ch], 0 / mov word [di+0Eh], 0
    a.b(0xc6, 0x45, 0x35, MARKER_TYPE)                       # mov byte [di+35h], 14h
    a.b(0xc7, 0x06, (HANDLERS + MARKER_TYPE) & 0xff, (HANDLERS + MARKER_TYPE) >> 8,
        EFFECT_HANDLER & 0xff, EFFECT_HANDLER >> 8)          # mov word [6978h], 3EB9h   (as 1000:57B5)
    a.b(0x5b)                                                # pop bx             the animation slot
    a.b(0x2e, 0xa1); a.word('eff_script')                    # mov ax, cs:[eff_script]
    a.near(0xe8, 'set_script')                               # call set_script    counters cleared, [bx+1] = 1
    a.b(0x89, 0x7f, 0x16)                                    # mov [bx+16h], di
    a.b(0x2e, 0xa1); a.word('eff_bank'); a.b(0x89, 0x47, 0x18)   # mov ax, cs:[eff_bank] / mov [bx+18h], ax
    for o_obj, o_anim in ((2, 4), (4, 6), (6, 8)):
        a.b(0x8b, 0x45, o_obj, 0x89, 0x47, o_anim)           # mov ax, [di+o] / mov [bx+o'], ax
    a.b(0xc6, 0x47, 0x14, 0x00)                              # mov byte [bx+14h], 0   not mirrored
    a.b(0xc7, 0x47, 0x1a, MARKER_TYPE, 0x00)                 # mov word [bx+1Ah], 14h
    a.b(0xc6, 0x07, 0x01)                                    # mov byte [bx], 1   in use
    a.label('sm_end')
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)            # pop di si dx cx bx ax / ret
    # spawn_blood (ABACABB, gore on): two more of the game's blood bursts (6820h, BLO.CEL) where the blow landed,
    # to the game's own: three times the blood
    a.label('spawn_blood')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_ABACABB); a.short(0x75, 'sb_on')
    a.near(0xe8, 'gore_hitter'); a.short(0x74, 'sb_on'); a.b(0xc3)   # D35: a Gore sword's blow
    a.label('sb_on')
    a.b(0x83, 0x3e, GORE & 0xff, GORE >> 8, 0x00); a.short(0x74, 'sb_go'); a.b(0xc3)   # gore off: none
    a.label('sb_go')
    a.b(0x2e, 0xc7, 0x06); a.word('eff_script'); a.b(BLOOD_SCRIPT & 0xff, BLOOD_SCRIPT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('eff_bank'); a.b(BLOOD_BANK & 0xff, BLOOD_BANK >> 8)
    a.near(0xe8, 'spawn_effect'); a.near(0xe8, 'spawn_effect'); a.b(0xc3)
    # spawn_effect: an effect object (eff_script, eff_bank) as spawn_marker makes it, if a slot is free
    a.label('spawn_effect')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57)                  # push ax bx cx dx si di
    a.b(0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00)
    a.label('se_obj')
    a.b(0x83, 0x3d, 0x00); a.short(0x74, 'se_anim')
    a.b(0x83, 0xc7, SLOT_SIZE); a.short(0xe2, 'se_obj')
    a.near(0xe9, 'sm_end')
    a.label('se_anim')
    a.b(0xbe, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)
    a.label('se_a')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'se_go')
    a.b(0x83, 0xc6, ANIM_SIZE); a.short(0xe2, 'se_a')
    a.near(0xe9, 'sm_end')
    a.label('se_go')
    a.near(0xe9, 'sm_make')

    # --- D23: faster drawing ---
    # convert (1000:5EDA, replaces call word cs:[bx], the call of the converter for this frame's planes, cs:[638Fh +
    # mask * 2], which turns the frame's planes into a byte a pixel at es:0, 8 pixels a byte of each plane, bit by
    # bit with rol / rcl): the same with a table (conv_t: a byte's 8 bits as 8 bytes of 0 or 1) and 386 registers,
    # one routine a mask (conv_routines), about four times fewer instructions. In: ds:si the first plane, the
    # others after it every cs:[637Dh] bytes (as the game's si, di, dx, bp and cs:[637Fh]), es:0 the output.
    # A mask the game has no converter for, or none of ours, goes to the game's own
    a.label('rules_convert')
    a.b(0x50, 0x0f, 0xa0)                                    # push ax / push fs
    a.b(0x8e, 0x66, 0x04)                                    # mov fs, [bp+4]     MAIN's code segment
    a.b(0x33, 0xc0, 0x64, 0xa0, CONVERT_MASK & 0xff, CONVERT_MASK >> 8)   # xor ax, ax / mov al, fs:[638Eh]
    a.b(0xd1, 0xe0, 0x8b, 0xd8)                              # shl ax, 1 / mov bx, ax
    a.b(0x64, 0x8b, 0x87, CONVERT_TABLE & 0xff, CONVERT_TABLE >> 8)   # mov ax, fs:[bx+638Fh]   the game's converter
    a.b(0x2e, 0xa3); a.word('call_target')                   # mov cs:[call_target], ax
    a.b(0x83, 0xfb, 0x40); a.short(0x73, 'cv_game')          # cmp bx, 64 / jae cv_game
    a.b(0x2e, 0x8b, 0x9f); a.word('conv_routines')           # mov bx, cs:[bx+conv_routines]
    a.b(0x0b, 0xdb); a.short(0x74, 'cv_game')                # or bx, bx / jz cv_game
    a.b(0x64, 0x83, 0x3e, CONVERT_COUNT & 0xff, CONVERT_COUNT >> 8, 0x00)   # cmp word fs:[637Dh], 0
    a.short(0x74, 'cv_game')                                 # je cv_game
    a.b(0x2e, 0x89, 0x1e); a.word('conv_jump')               # mov cs:[conv_jump], bx
    for r in (0x50, 0x51, 0x52, 0x53, 0x55, 0x56, 0x57):     # push eax ecx edx ebx ebp esi edi
        a.b(0x66, r)
    a.b(0x66, 0x0f, 0xb7, 0xf6)                              # movzx esi, si      the first plane
    a.b(0x64, 0x66, 0x0f, 0xb7, 0x1e, CONVERT_COUNT & 0xff, CONVERT_COUNT >> 8)   # movzx ebx, word fs:[637Dh]   a plane's bytes
    a.b(0x66, 0x67, 0x8d, 0x0c, 0x5e, 0x66, 0x01, 0xd9)      # lea ecx, [esi+ebx*2] / add ecx, ebx   the fourth plane
    a.b(0x33, 0xff, 0xfc)                                    # xor di, di / cld
    a.b(0x2e, 0xff, 0x16); a.word('conv_jump')               # call word cs:[conv_jump]
    # the bytes written, as the game's converters for 4 and 5 planes leave them; those for 1-3 planes (masks below
    # 8) left cs:[637Bh] at 0, so the knights' recolour never reached those frames (KN3.OB 31, KN4.OB 25 stayed in
    # the first knight's colours): now it does. Only the converters and the recolour read it (5EC0 sets it to 0)
    a.b(0x64, 0x89, 0x3e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)   # mov fs:[637Bh], di
    for r in (0x5f, 0x5e, 0x5d, 0x5b, 0x5a, 0x59, 0x58):     # pop edi esi ebp ebx edx ecx eax
        a.b(0x66, r)
    a.b(0x0f, 0xa1, 0x58)                                    # pop fs / pop ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('cv_game')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(CONVERT_RET & 0xff, CONVERT_RET >> 8)   # mov word cs:[call_ret], 5EDDh
    a.b(0x0f, 0xa1, 0x58)                                    # pop fs / pop ax
    a.near(0xe9, 'call_game')                                # jmp call_game      the game's converter
    # the routines: per 8 pixels, the planes from the highest down: the pixels so far shifted up to the next plane's
    # bit, its table bytes ORed in; ds:esi plane 0, then +ebx, +ebx*2, ecx (+3 * ebx), ecx+ebx
    SLOT_RM = ((0x2e,), (0x2c, 0x1e), (0x2c, 0x5e), (0x29,), (0x2c, 0x19))   # movzx ebp, byte [...] modrm (SIB)
    conv_names = {}
    for mask in CONVERT_MASKS:
        planes = [p for p in range(5) if mask >> p & 1]
        name = f'conv_{mask:02x}'; conv_names[mask] = name
        a.label(name)
        top = len(a.code)
        prev = None
        for slot, plane in reversed(list(enumerate(planes))):
            if prev is not None:
                a.b(0x66, 0xc1, 0xe0, prev - plane, 0x66, 0xc1, 0xe2, prev - plane)   # shl eax, d / shl edx, d
            a.b(0x66, 0x67, 0x0f, 0xb6, *SLOT_RM[slot])      # movzx ebp, byte [plane]
            op = 0x8b if prev is None else 0x0b              # mov / or
            a.b(0x2e, 0x66, 0x67, op, 0x04, 0xed); a.word('conv_t'); a.b(0, 0)      # eax, cs:[ebp*8+conv_t]
            a.b(0x2e, 0x66, 0x67, op, 0x14, 0xed); a.word('conv_t', 4); a.b(0, 0)   # edx, cs:[ebp*8+conv_t+4]
            prev = plane
        if prev:
            a.b(0x66, 0xc1, 0xe0, prev, 0x66, 0xc1, 0xe2, prev)   # shl eax, lowest / shl edx, lowest
        a.b(0x26, 0x66, 0x89, 0x05, 0x26, 0x66, 0x89, 0x55, 0x04, 0x83, 0xc7, 0x08)   # mov es:[di], eax / es:[di+4], edx / add di, 8
        a.b(0x46, 0x41)                                      # inc si / inc cx
        a.b(0x64, 0xff, 0x0e, CONVERT_COUNT & 0xff, CONVERT_COUNT >> 8)   # dec word fs:[637Dh]
        rel = top - (len(a.code) + 4)
        a.b(0x0f, 0x85, rel & 0xff, (rel >> 8) & 0xff)       # jnz (near, 386)
        a.b(0xc3)                                            # ret

    # --- D24: responsive controls ---
    # key_handler (int 64h from the game's keyboard interrupt, 1000:8271, which stored the key's state, al = 0
    # pressed or FFh released, bx = its scan code, into MAIN's key table cs:81E3h): the game reads the table once a
    # frame (2 BIOS ticks), so a key pressed and let go between two reads was never seen. A release less than
    # KEY_HOLD ticks after the press is kept back (key_pending) until key_settle lets it through. Runs inside the
    # keyboard interrupt: its own data only, nothing of rules_handler's
    a.label('key_handler')
    a.b(0x55, 0x8b, 0xec, 0x1e, 0x56, 0x52)                  # push bp / mov bp, sp / push ds si dx
    a.b(0x8e, 0x5e, 0x04)                                    # mov ds, [bp+4]     MAIN's code segment
    a.b(0x06, 0x33, 0xf6, 0x8e, 0xc6, 0x26, 0x8b, 0x16, 0x6c, 0x04, 0x07)   # push es / xor si,si / mov es,si / mov dx,es:[046Ch] / pop es
    a.b(0x0a, 0xc0); a.short(0x75, 'kh_release')             # or al, al / jnz kh_release
    a.near(0xe8, 'cheat_key')                                # call cheat_key   CF = 1: a cheat code's key
    a.short(0x73, 'kh_press'); a.near(0xe9, 'kh_end')        # jnc kh_press / jmp kh_end   kept from the game
    a.label('kh_press')
    # D39: the keyboard's auto-repeat sends a held key's press again: that is no new press
    a.b(0x80, 0xbf, KEY_TABLE & 0xff, KEY_TABLE >> 8, 0xff); a.short(0x74, 'kp_new')   # cmp byte [bx+81E3h], 0FFh / je
    a.b(0x2e, 0x80, 0xbf); a.word('key_pending'); a.b(0x00); a.short(0x74, 'kp_held')   # cmp byte cs:[bx+key_pending], 0 / je
    a.label('kp_new')
    a.near(0xe8, 'kh_dir_new')                               # call kh_dir_new
    a.b(0x8b, 0xf3, 0xd1, 0xe6)                              # mov si, bx / shl si, 1
    a.b(0x2e, 0x89, 0x94); a.word('key_tick')                # mov cs:[si+key_tick], dx
    a.label('kp_held')
    a.b(0x88, 0x87, KEY_TABLE & 0xff, KEY_TABLE >> 8)        # mov [bx+81E3h], al   pressed
    a.b(0x50, 0x51, 0xb8, ILOG_KEY_DOWN, 0x00, 0x8a, 0xe3, 0x33, 0xc9)   # push ax cx / mov ax, kind / mov ah, bl / xor cx, cx
    a.near(0xe8, 'ilog_put'); a.b(0x59, 0x58)                # call ilog_put / pop cx ax
    a.b(0x2e, 0xc6, 0x87); a.word('key_pending'); a.b(0x00)  # mov byte cs:[bx+key_pending], 0
    a.near(0xe8, 'kh_buffer')                                # call kh_buffer
    a.short(0xeb, 'kh_end')                                  # jmp kh_end
    a.label('kh_release')
    a.b(0x50, 0x51, 0xb8, ILOG_KEY_UP, 0x00, 0x8a, 0xe3, 0x33, 0xc9)   # push ax cx / mov ax, kind / mov ah, bl / xor cx, cx
    a.near(0xe8, 'ilog_put'); a.b(0x59, 0x58)                # call ilog_put / pop cx ax
    a.near(0xe8, 'kh_let_go')                                # call kh_let_go
    a.b(0x8b, 0xf3, 0xd1, 0xe6)                              # mov si, bx / shl si, 1
    a.b(0x2e, 0x8b, 0xb4); a.word('key_tick')                # mov si, cs:[si+key_tick]
    a.b(0xf7, 0xde, 0x03, 0xf2)                              # neg si / add si, dx   ticks held
    a.b(0x83, 0xfe, KEY_HOLD); a.short(0x73, 'kh_store')     # cmp si, KEY_HOLD / jae kh_store
    a.b(0x2e, 0xc6, 0x87); a.word('key_pending'); a.b(0x01)  # mov byte cs:[bx+key_pending], 1
    a.b(0x2e, 0xc6, 0x06); a.word('key_pending_any'); a.b(0x01)   # mov byte cs:[key_pending_any], 1
    a.short(0xeb, 'kh_end')                                  # jmp kh_end
    a.label('kh_store')
    a.b(0x88, 0x87, KEY_TABLE & 0xff, KEY_TABLE >> 8)        # mov [bx+81E3h], al   released
    a.label('kh_end')
    a.b(0x5a, 0x5e, 0x1f, 0x5d, 0xcf)                        # pop dx si ds bp / iret
    # kh_buffer (a key pressed, bx = scan code, dx = now, ds = MAIN's code segment): the input buffer. A player's
    # fire key notes fire and the directions held (the bits as 1000:83C0 makes them); a direction pressed soon after
    # is added
    a.label('kh_buffer')
    def recent_ticks(p):                                     # flags: now (dx) against rel_tick + input_recent_direction
        a.b(0x52, 0x2e, 0x2b, 0x16); a.word('rel_tick', 2 * p)   # push dx / sub dx, cs:[rel_tick+2p]
        a.b(0x51, 0x32, 0xed, 0x2e, 0x8a, 0x0e); a.word('rules_table', G_INPUT_RECENT)   # push cx / xor ch, ch / mov cl, cs:[input_recent_direction]
        a.b(0x3b, 0xd1, 0x59, 0x5a)                          # cmp dx, cx / pop cx / pop dx
    for p, (fire, dirs) in enumerate(PLAYER_KEYS):
        a.b(0x80, 0xfb, fire); a.short(0x75, f'kb_dirs{p}')  # cmp bl, fire / jne kb_dirs
        a.b(0x50, 0xb0, 0x10)                                # push ax / mov al, 10h
        for scan, bit in dirs:
            a.b(0x80, 0x3e, (KEY_TABLE + scan) & 0xff, (KEY_TABLE + scan) >> 8, 0xff)   # cmp byte [table+scan], 0FFh
            a.short(0x74, f'kb_n{p}_{scan:x}'); a.b(0x0c, bit)   # je / or al, bit   held
            a.label(f'kb_n{p}_{scan:x}')
        # a direction let go input_recent_direction ticks or less before (the hand left it on the way to fire), unless
        # one of the same axis is held. D39: kh_let_go notes only short presses, and a new direction drops the notes
        a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_INPUT_RECENT); a.b(0x00); a.short(0x74, f'kb_old{p}')   # 0 = off
        recent_ticks(p); a.short(0x77, f'kb_old{p}')          # ja
        a.b(0x2e, 0x8a, 0x26); a.word('rel_bits', p)          # mov ah, cs:[rel_bits+p]
        a.b(0xa8, 0x03); a.short(0x74, f'kb_h{p}'); a.b(0x80, 0xe4, 0x0c)   # test al, 3 / jz / and ah, 0Ch
        a.label(f'kb_h{p}')
        a.b(0xa8, 0x0c); a.short(0x74, f'kb_v{p}'); a.b(0x80, 0xe4, 0x03)   # test al, 0Ch / jz / and ah, 3
        a.label(f'kb_v{p}')
        a.b(0x0a, 0xc4)                                      # or al, ah
        a.label(f'kb_old{p}')
        a.b(0x2e, 0xa2); a.word('buf_bits', p)               # mov cs:[buf_bits+p], al
        a.b(0x2e, 0x89, 0x16); a.word('buf_tick', 2 * p)     # mov cs:[buf_tick+2p], dx
        a.b(0x58, 0xc3)                                      # pop ax / ret
        a.label(f'kb_dirs{p}')
        for scan, bit in dirs:
            a.b(0x80, 0xfb, scan); a.short(0x75, f'kb_d{p}_{scan:x}')   # cmp bl, scan / jne
            a.b(0x2e, 0xf6, 0x06); a.word('buf_bits', p); a.b(0x10)     # test byte cs:[buf_bits+p], 10h
            a.short(0x74, f'kb_d{p}_{scan:x}')               # jz   no fire noted
            a.b(0x52, 0x2e, 0x2b, 0x16); a.word('buf_tick', 2 * p)      # push dx / sub dx, cs:[buf_tick+2p]
            a.b(0x83, 0xfa, DIR_AFTER_FIRE, 0x5a); a.short(0x77, f'kb_d{p}_{scan:x}')   # cmp dx, DIR_AFTER_FIRE / pop dx / ja   D39: too late
            a.b(0x2e, 0x80, 0x0e); a.word('buf_bits', p); a.b(bit)      # or byte cs:[buf_bits+p], bit
            a.label(f'kb_d{p}_{scan:x}')
    a.b(0xc3)                                                # ret

    # kh_let_go (a key let go, bx = scan code, dx = now): a player's direction is noted with the time (rel_bits,
    # rel_tick); the notes of an earlier moment are dropped first
    a.label('kh_let_go')
    for p, (fire, dirs) in enumerate(PLAYER_KEYS):
        for scan, bit in dirs:
            a.b(0x80, 0xfb, scan); a.short(0x75, f'klg{p}_{scan:x}')   # cmp bl, scan / jne
            a.b(0x56, 0x52, 0x8b, 0xf3, 0xd1, 0xe6, 0x2e, 0x2b, 0x94); a.word('key_tick')   # push si dx / mov si, bx / shl si, 1 / sub dx, cs:[si+key_tick]
            a.b(0x83, 0xfa, DIR_CHORD_MAX, 0x5a, 0x5e); a.short(0x76, f'klh{p}_{scan:x}'); a.b(0xc3)   # cmp dx, DIR_CHORD_MAX / pop dx si / jbe / ret   D39: walking
            a.label(f'klh{p}_{scan:x}')
            recent_ticks(p); a.short(0x76, f'klk{p}_{scan:x}')   # jbe
            a.b(0x2e, 0xc6, 0x06); a.word('rel_bits', p); a.b(0x00)   # mov byte cs:[rel_bits+p], 0
            a.label(f'klk{p}_{scan:x}')
            a.b(0x2e, 0x80, 0x0e); a.word('rel_bits', p); a.b(bit)    # or byte cs:[rel_bits+p], bit
            a.b(0x2e, 0x89, 0x16); a.word('rel_tick', 2 * p); a.b(0xc3)   # mov cs:[rel_tick+2p], dx / ret
            a.label(f'klg{p}_{scan:x}')
    a.b(0xc3)                                                # ret

    # kh_dir_new (D39; a key newly pressed, bx = scan code): a player's new direction starts another move: the
    # directions let go before it no longer belong to an attack
    a.label('kh_dir_new')
    for p, (fire, dirs) in enumerate(PLAYER_KEYS):
        for scan, bit in dirs:
            a.b(0x80, 0xfb, scan); a.short(0x75, f'kdn{p}_{scan:x}')   # cmp bl, scan / jne
            a.b(0x2e, 0xc6, 0x06); a.word('rel_bits', p); a.b(0x00, 0xc3)   # mov byte cs:[rel_bits+p], 0 / ret
            a.label(f'kdn{p}_{scan:x}')
    a.b(0xc3)                                                # ret

    # --- D33: co-op lairs on the map ---
    # coop_list (1000:08CA, xor ax,ax as the list of choices is done): on a human's turn with a lair among the
    # choices, the other players' knights listed (type 1: alive; +20h <> 4) fight the lair together with this one:
    # one "Lair with" + its name, or with 2-3 of them "Lair together (N knights)" (as many as there are inputs: the
    # two key sets, the third (I J K L, B) and the joysticks that answer). With 2 or more knights to fight and
    # 2 or more partners (or no room), those knights become one "Battle with ..." that lists them on its own.
    # Then the list in its fixed order (choice_order, or here)
    a.label('rules_coop_list')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_COOP_LAIRS); a.b(0x00); a.short(0x74, 'cl_off')
    a.b(0x83, 0x3e, COMPUTER_TURN & 0xff, COMPUTER_TURN >> 8, 0x00); a.short(0x74, 'cl_on')   # not the computer's turn
    a.label('cl_off')
    a.near(0xe9, 'cl_done')
    a.label('cl_on')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57)                  # push ax bx cx dx si di
    a.b(0x0e, 0x07, 0xbf); a.word('battle_list'); a.b(0x33, 0xc0, 0xb9, 0x14, 0x00, 0xfc, 0xf3, 0xab)   # push cs / pop es / rep stosw: none yet
    a.b(0x1e, 0x07)                                          # push ds / pop es
    a.b(0x2e, 0xc6, 0x06); a.word('cl_used'); a.b(0x00)
    a.b(0xbe, CHOICES & 0xff, CHOICES >> 8, 0x33, 0xd2, 0x33, 0xdb, 0xb9, CHOICE_COUNT, 0x00)   # mov si / dl lair / bl knights, bh partners / cx
    a.label('cl_scan')
    a.b(0x8b, 0x04, 0x0b, 0x44, 0x02); a.short(0x74, 'cl_sn')   # empty
    a.b(0x2e, 0xfe, 0x06); a.word('cl_used')
    a.b(0x8b, 0x44, 0x04, 0x3d, 0x02, 0x00); a.short(0x75, 'cl_s1'); a.b(0xb2, 0x01)   # mov ax, [si+4] / cmp ax, 2 / jne / mov dl, 1
    a.label('cl_s1')
    a.b(0x3d, 0x01, 0x00); a.short(0x75, 'cl_sn')            # a knight to fight
    a.b(0x8a, 0xc3, 0xb4, 0x08, 0xf6, 0xe4, 0x05); a.word('battle_list'); a.b(0x8b, 0xf8)   # di = battle_list + 8 bl
    a.near(0xe8, 'copy8'); a.b(0xfe, 0xc3)                   # kept for "Battle with ..." / inc bl
    a.b(0x8b, 0x3c, 0x83, 0x7d, 0x20, COMPUTER); a.short(0x74, 'cl_sn')   # mov di, [si] / the computer's: no partner
    a.b(0x80, 0xff, COOP_PARTNERS); a.short(0x73, 'cl_sn')
    a.b(0x53, 0x8a, 0xdf, 0x32, 0xff, 0xd1, 0xe3, 0x2e, 0x89, 0xbf); a.word('lair_partners'); a.b(0x5b, 0xfe, 0xc7)   # lair_partners[bh] = di / inc bh
    a.label('cl_sn')
    a.b(0x83, 0xc6, CHOICE_SIZE); a.short(0xe2, 'cl_scan')
    a.b(0x0a, 0xd2); a.short(0x74, 'cl_plain')               # no lair
    a.b(0x0a, 0xff); a.short(0x74, 'cl_plain')               # no partner
    a.b(0x80, 0xff, 0x03); a.short(0x72, 'cl_n')             # 3 partners: as many as the inputs
    a.b(0x53, 0x2e, 0xc6, 0x06); a.word('cl_max'); a.b(0x02)  # push bx / the key sets: 2 partners
    a.b(0xb4, 0x01); a.near(0xe8, 'joy_present'); a.short(0x72, 'cl_ja')
    a.b(0x2e, 0xfe, 0x06); a.word('cl_max')
    a.label('cl_ja')
    a.b(0xb4, 0x04); a.near(0xe8, 'joy_present'); a.short(0x72, 'cl_jb')
    a.b(0x2e, 0xfe, 0x06); a.word('cl_max')
    a.label('cl_jb')
    a.b(0x5b, 0x2e, 0x3a, 0x3e); a.word('cl_max'); a.short(0x76, 'cl_n')   # pop bx / cmp bh, cs:[cl_max] / jbe
    a.b(0x2e, 0x8a, 0x3e); a.word('cl_max')
    a.label('cl_n')
    a.b(0x2e, 0x88, 0x3e); a.word('lair_pn'); a.b(0x2e, 0x88, 0x1e); a.word('battle_n')   # the partners, the knights
    a.b(0x8a, 0xc7, 0x04, 0x31, 0x2e, 0xa2); a.word('together_text', TOGETHER_DIGIT)   # mov al, bh / add al, '1'
    a.b(0x32, 0xf6, 0x80, 0xfb, 0x02); a.short(0x72, 'cl_build')   # xor dh, dh / cmp bl, 2 / jb   one knight: as it is
    a.b(0x80, 0xff, 0x02); a.short(0x73, 'cl_one')
    a.b(0x2e, 0x80, 0x3e); a.word('cl_used'); a.b(CHOICE_COUNT - 1); a.short(0x72, 'cl_build')   # room: as it is
    a.label('cl_one')
    a.b(0xb6, 0x01)                                          # mov dh, 1   "Battle with ..."
    a.label('cl_build')
    a.near(0xe8, 'coop_build')
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58)                  # pop di si dx cx bx ax
    a.short(0xeb, 'cl_ret')
    a.label('cl_plain')
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58)
    a.label('cl_done')
    a.near(0xe8, 'choice_order')                             # call choice_order
    a.label('cl_ret')
    a.b(0x33, 0xc0); a.near(0xe9, 'rules_done')              # xor ax, ax   (replaced)
    # copy8: 8 bytes from ds:si to cs:di, di after them (keeps si, cx)
    a.label('copy8')
    a.b(0x51, 0x56, 0xb9, 0x08, 0x00)
    a.label('c8_loop')
    a.b(0x8a, 0x04, 0x2e, 0x88, 0x05, 0x46, 0x47); a.short(0xe2, 'c8_loop')
    a.b(0x5e, 0x59, 0xc3)
    # coop_build (dh = 1: the knights to fight as one "Battle with ..."): the list again in the fixed order (the
    # place and the lair, the graves and the knights, "Lair with"), through choice_tmp and choice_order's end
    a.label('coop_build')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57)                  # (as choice_order: popped at co_fill's end)
    a.b(0xbf); a.word('choice_tmp')
    for k in range(2):
        a.b(0xbe, CHOICES & 0xff, CHOICES >> 8, 0xb9, CHOICE_COUNT, 0x00)
        a.label(f'cb_e{k}')
        a.b(0x8b, 0x04, 0x0b, 0x44, 0x02); a.short(0x74, f'cb_n{k}')
        a.b(0x8b, 0x44, 0x04)                                # mov ax, [si+4]
        if k == 0:                                           # the place, the lair
            a.b(0x3d, 0x01, 0x00); a.short(0x74, f'cb_n{k}'); a.b(0x3d, 0x21, 0x00); a.short(0x74, f'cb_n{k}')
        else:                                                # the graves, the knights (unless "Battle with ...")
            a.b(0x3d, 0x21, 0x00); a.short(0x74, 'cb_c1'); a.b(0x3d, 0x01, 0x00); a.short(0x75, f'cb_n{k}')
            a.b(0x0a, 0xf6); a.short(0x75, f'cb_n{k}')
            a.label('cb_c1')
        a.near(0xe8, 'copy8')
        a.label(f'cb_n{k}')
        a.b(0x83, 0xc6, CHOICE_SIZE); a.short(0xe2, f'cb_e{k}')
    def entry(src, typ):
        a.b(0x2e, 0xa1); a.word(src)                         # mov ax, cs:[src]   the object
        a.b(0x2e, 0x89, 0x05, 0x2e, 0xc7, 0x45, 0x02, 0x00, 0x00, 0x2e, 0xc7, 0x45, 0x04, typ, 0x00)
        a.b(0x2e, 0xc7, 0x45, 0x06, 0x00, 0x00, 0x83, 0xc7, CHOICE_SIZE)
    a.b(0x0a, 0xf6); a.short(0x74, 'cb_coop')
    entry('battle_list', BATTLE_TYPE)
    a.label('cb_coop')
    a.b(0x81, 0xff); a.word('choice_tmp', CHOICE_SIZE * (CHOICE_COUNT - 1)); a.short(0x73, 'cb_end')   # no room
    entry('lair_partners', COOP_TYPE)
    a.label('cb_end')
    a.b(0x8b, 0xc7, 0x2d); a.word('choice_tmp'); a.b(0x05, CHOICES & 0xff, CHOICES >> 8, 0xa3, 0x46, 0x09)   # [0946h] the next free
    a.near(0xe9, 'co_fill')
    # choice_order: the list in a fixed order: the place or lair first, then the knights to fight (and graves),
    # then "Lair with"; the same order within each (through choice_tmp)
    a.label('choice_order')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57)                  # push ax bx cx dx si di
    a.b(0xbf); a.word('choice_tmp'); a.b(0x33, 0xd2)         # mov di, choice_tmp / xor dx, dx   dl = the class
    a.label('co_class')
    a.b(0xbe, CHOICES & 0xff, CHOICES >> 8, 0xb9, CHOICE_COUNT, 0x00)   # mov si, 043Ch / mov cx, 5
    a.label('co_entry')
    a.b(0x8b, 0x04, 0x0b, 0x44, 0x02); a.short(0x74, 'co_skip')   # mov ax, [si] / or ax, [si+2] / jz   empty
    a.b(0x8b, 0x44, 0x04, 0x32, 0xf6)                        # mov ax, [si+4] / xor dh, dh   class 0
    a.b(0x3d, 0x01, 0x00); a.short(0x74, 'co_c1'); a.b(0x3d, 0x21, 0x00); a.short(0x75, 'co_c2')
    a.label('co_c1')
    a.b(0xb6, 0x01)                                          # mov dh, 1   a knight to fight, a grave
    a.label('co_c2')
    a.b(0x3d, COOP_TYPE, 0x00); a.short(0x75, 'co_cmp'); a.b(0xb6, 0x02)   # "Lair with": 2
    a.label('co_cmp')
    a.b(0x3a, 0xf2); a.short(0x75, 'co_skip')                # cmp dh, dl / jne
    a.b(0xbb, 0x08, 0x00)                                    # mov bx, 8
    a.label('co_copy')
    a.b(0x8a, 0x04, 0x2e, 0x88, 0x05, 0x46, 0x47, 0x4b); a.short(0x75, 'co_copy')   # mov al, [si] / mov cs:[di], al / inc si, di / dec bx
    a.b(0x83, 0xee, 0x08)                                    # sub si, 8
    a.label('co_skip')
    a.b(0x83, 0xc6, CHOICE_SIZE, 0x49); a.short(0x75, 'co_entry')   # add si, 8 / dec cx / jnz
    a.b(0xfe, 0xc2, 0x80, 0xfa, 0x03); a.short(0x72, 'co_class')     # inc dl / cmp dl, 3 / jb
    a.label('co_fill')                                       # the rest empty (coop_build too)
    a.b(0x81, 0xff); a.word('choice_tmp', CHOICE_SIZE * CHOICE_COUNT); a.short(0x73, 'co_back')
    a.b(0x2e, 0xc6, 0x05, 0x00, 0x47); a.short(0xeb, 'co_fill')   # mov byte cs:[di], 0 / inc di
    a.label('co_back')
    a.b(0xbe); a.word('choice_tmp'); a.b(0xbf, CHOICES & 0xff, CHOICES >> 8, 0xb9, CHOICE_SIZE * CHOICE_COUNT, 0x00)
    a.label('co_back_b')
    a.b(0x2e, 0x8a, 0x04, 0x88, 0x05, 0x46, 0x47); a.short(0xe2, 'co_back_b')   # mov al, cs:[si] / mov [di], al / inc si, di / loop
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)            # pop di si dx cx bx ax / ret
    # coop_text (1000:B137, cmp word [bx+4],2 in OrderOpt, bx = the entry, the caller's bp = where the text goes):
    # "Lair with " and the knight's name, "Lair together (N knights)" or "Battle with ...", then on at OrderOpt's ret
    a.label('rules_coop_text')
    a.b(0x8b, 0x5e, 0xfe)                                    # mov bx, [bp-2]   the game's bx: the entry
    a.b(0x83, 0x7f, 0x04, COOP_TYPE); a.short(0x74, 'ct_coop')   # cmp word [bx+4], COOP_TYPE / je
    a.b(0x83, 0x7f, 0x04, BATTLE_TYPE); a.short(0x74, 'ct_battle')
    a.b(0x83, 0x7f, 0x04, 0x02); a.near(0xe9, 'rules_flags')  # cmp word [bx+4], 2   (replaced)
    a.label('ct_battle')
    a.b(0x56, 0x57, 0x50, 0xbe); a.word('battle_text'); a.b(0x32, 0xe4); a.short(0xeb, 'ct_write')   # no name
    a.label('ct_coop')
    a.b(0x56, 0x57, 0x50, 0xbe); a.word('coop_text'); a.b(0xb4, 0x01)   # mov si, coop_text / mov ah, 1: the name
    a.b(0x2e, 0x80, 0x3e); a.word('lair_pn'); a.b(0x02); a.short(0x72, 'ct_write')
    a.b(0xbe); a.word('together_text'); a.b(0x32, 0xe4)
    a.label('ct_write')
    a.b(0x8b, 0x7e, 0x00)                                    # mov di, [bp]   the caller's bp
    a.label('ct_word')
    a.b(0x2e, 0x8a, 0x04, 0x0a, 0xc0); a.short(0x74, 'ct_name')   # mov al, cs:[si] / or al, al / jz
    a.b(0x88, 0x05, 0x46, 0x47); a.short(0xeb, 'ct_word')    # mov [di], al / inc si / inc di
    a.label('ct_name')
    a.b(0x0a, 0xe4); a.short(0x75, 'ct_knight')
    a.b(0xc6, 0x05, 0x00, 0x47); a.short(0xeb, 'ct_done')    # mov byte [di], 0 / inc di
    a.label('ct_knight')
    a.b(0x8b, 0x37, 0x8b, 0x74, 0x4c)                        # mov si, [bx] / mov si, [si+4Ch]   the knight's name
    a.label('ct_copy')
    a.b(0x8a, 0x04, 0x88, 0x05, 0x46, 0x47, 0x0a, 0xc0); a.short(0x75, 'ct_copy')   # mov al,[si] / mov [di],al / inc si,di / or al,al / jnz
    a.label('ct_done')
    a.b(0x89, 0x7e, 0x00)                                    # mov [bp], di   the caller's bp after the 0, as OrderOpt leaves it
    a.b(0xc7, 0x46, 0x02, ORDER_OPT_RET & 0xff, ORDER_OPT_RET >> 8)   # on at its ret
    a.b(0x58, 0x5f, 0x5e); a.near(0xe9, 'rules_done')        # pop ax di si
    # coop_pick (1000:B089, mov ax,ds:[bp] in StackDecision, the caller's bp = the chosen entry + 4, di = its object):
    # "Lair with" notes the partners and goes on as the lair's own choice (di = the lair, ax = 2); "Battle with ..."
    # puts the knights to fight in the list and draws it again (DisplayStack)
    a.label('rules_coop_pick')
    a.b(0x56, 0x8b, 0x76, 0x00, 0x8b, 0x04)                  # push si / mov si, [bp] / mov ax, [si]   (replaced)
    a.b(0x2e, 0xc7, 0x06); a.word('coop_partner'); a.b(0x00, 0x00)   # mov word cs:[coop_partner], 0
    a.b(0x3d, BATTLE_TYPE, 0x00); a.short(0x74, 'cp_battle')
    a.b(0x3d, COOP_TYPE, 0x00); a.short(0x75, 'cp_end')      # cmp ax, COOP_TYPE / jne
    a.b(0xbe, CHOICES & 0xff, CHOICES >> 8)                  # mov si, 043Ch
    a.label('cp_lair')
    a.b(0x83, 0x7c, 0x04, 0x02); a.short(0x74, 'cp_found')   # cmp word [si+4], 2 / je
    a.b(0x83, 0xc6, CHOICE_SIZE)
    a.b(0x81, 0xfe, (CHOICES + CHOICE_SIZE * CHOICE_COUNT) & 0xff, (CHOICES + CHOICE_SIZE * CHOICE_COUNT) >> 8)
    a.short(0x72, 'cp_lair')                                 # cmp si, the list's end / jb
    a.b(0xb8, 0x01, 0x00); a.short(0xeb, 'cp_end')           # (no lair: cannot be; as a knight's fight)
    a.label('cp_found')
    for k in range(COOP_PARTNERS):                           # the partners as the list had them
        a.b(0x2e, 0xa1); a.word('lair_partners', 2 * k); a.b(0x2e, 0xa3); a.word('coop_partners', 2 * k)
    a.b(0x2e, 0xa0); a.word('lair_pn'); a.b(0x2e, 0xa2); a.word('coop_pn')
    a.b(0x2e, 0xa1); a.word('lair_partners'); a.b(0x2e, 0xa3); a.word('coop_partner')   # (the first: co-op on)
    a.b(0x8b, 0x3c, 0xb8, 0x02, 0x00)                        # mov di, [si] / mov ax, 2   the lair
    a.label('cp_end')
    a.b(0x5e); a.near(0xe9, 'rules_done')                    # pop si
    a.label('cp_battle')
    a.b(0x51, 0xbe); a.word('battle_list'); a.b(0xbf, CHOICES & 0xff, CHOICES >> 8, 0xb9, CHOICE_SIZE * CHOICE_COUNT, 0x00)
    a.label('cp_copy')
    a.b(0x2e, 0x8a, 0x04, 0x88, 0x05, 0x46, 0x47); a.short(0xe2, 'cp_copy')   # mov al, cs:[si] / mov [di], al / inc si, di / loop
    a.b(0x2e, 0xa0); a.word('battle_n'); a.b(0xb4, CHOICE_SIZE, 0xf6, 0xe4, 0x05, CHOICES & 0xff, CHOICES >> 8, 0xa3, 0x46, 0x09)   # [0946h]
    a.b(0xc7, 0x46, 0x02, DISPLAY_STACK & 0xff, DISPLAY_STACK >> 8)   # DisplayStack again (nothing on the stack)
    a.b(0x59, 0x5e); a.near(0xe9, 'rules_done')              # pop cx si

    # coop_setup (1000:058B, call 1F2C in the lair visit, InitLair): with partners, as the co-op practice sets a
    # lair up (state 0: all the knights' strength and HP for the monsters, the lair's set-up; then for each partner
    # its fields, 1F76, and its registration, 2998), each call back to this int; then on to the fight (058E). The
    # partners' own fields are kept and put back at the end. Inputs: the visit's knight keeps its own, each partner
    # its own unless taken, else the first free of player 1's keys, player 2's, joystick A, joystick B (those that
    # answer, with 3-4 knights) and the third key set
    a.label('rules_coop_setup')
    a.b(0x2e, 0x83, 0x3e); a.word('coop_partner'); a.b(0x00); a.short(0x75, 'cs_on')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x2c, 0x1f)   # as the game: call 1F2C
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x8e, 0x05)      # then on to the fight (058E)
    a.near(0xe9, 'call_game')
    a.label('cs_on')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x8b, 0x05)      # every call back to this int (058B)
    a.b(0x2e, 0xa0); a.word('coop_state')                    # mov al, cs:[coop_state]
    a.b(0x0a, 0xc0); a.short(0x74, 'cs_s0'); a.near(0xe9, 'cs_sn')
    a.label('cs_s0')
    a.b(0x57, 0x56, 0x06, 0x51, 0x52)                        # push di si es cx dx
    for p in range(COOP_PARTNERS):                           # the partners' own fields
        a.b(0x2e, 0x80, 0x3e); a.word('coop_pn'); a.b(p + 1)
        a.short(0x73, f'cs_sv{p}'); a.near(0xe9, 'cs_saved')
        a.label(f'cs_sv{p}')
        a.b(0x2e, 0x8b, 0x3e); a.word('coop_partners', 2 * p)
        for k, off in enumerate(COOP_SAVE):
            a.b(0x8b, 0x45, off, 0x2e, 0xa3); a.word('coop_saved', 2 * (p * len(COOP_SAVE) + k))   # mov ax, [di+off] / mov cs:[..], ax
    a.label('cs_saved')
    a.b(0xa1, 0xe8, 0x77, 0x2e, 0xa3); a.word('knight_list'); a.b(0x2e, 0xa3); a.word('lair_list')   # the visit's knight first
    for p in range(COOP_PARTNERS):
        a.b(0x2e, 0xa1); a.word('coop_partners', 2 * p)
        a.b(0x2e, 0xa3); a.word('knight_list', 2 + 2 * p); a.b(0x2e, 0xa3); a.word('lair_list', 2 + 2 * p)
    a.b(0x2e, 0xa0); a.word('coop_pn'); a.b(0xfe, 0xc0, 0x2e, 0xa2); a.word('coop')   # co-op: 1 + the partners
    for flag in ('k1_out', 'multi', 'mon_mode', 'teams', 'bk', 'bk_count', 'vs_monsters', 'init_state', 'joy_seen'):
        a.b(0x2e, 0xc6, 0x06); a.word(flag); a.b(0x00)
    a.b(0x2e, 0xc7, 0x06); a.word('dragon_victim'); a.b(0x00, 0x00)
    a.b(0x2e, 0xc7, 0x06); a.word('rat_victim'); a.b(0x00, 0x00)
    a.b(0x0e, 0x07, 0x57, 0xbf); a.word('last_target')       # push cs / pop es / push di / mov di, last_target
    a.b(0x33, 0xc0, 0xb9, 0x2a, 0x00, 0xfc, 0xf3, 0xab, 0x5f)   # xor ax, ax / mov cx, 42 / cld / rep stosw / pop di
    a.b(0x2e, 0x80, 0x3e); a.word('coop_pn'); a.b(0x02); a.short(0x72, 'cs_inputs')   # 3-4 knights: the joysticks
    a.b(0xb4, 0x01); a.near(0xe8, 'joy_present'); a.short(0x72, 'cs_ja')
    a.b(0x2e, 0x80, 0x0e); a.word('joy_seen'); a.b(0x04)
    a.label('cs_ja')
    a.b(0xb4, 0x04); a.near(0xe8, 'joy_present'); a.short(0x72, 'cs_inputs')
    a.b(0x2e, 0x80, 0x0e); a.word('joy_seen'); a.b(0x08)
    a.label('cs_inputs')
    a.b(0x8b, 0x3e, 0xe8, 0x77); a.near(0xe8, 'ctl_class'); a.b(0x8a, 0xd8)   # mov di, [77E8h] / its own / mov bl, al
    for p in range(COOP_PARTNERS):
        a.b(0x2e, 0x80, 0x3e); a.word('coop_pn'); a.b(p + 1); a.short(0x72, 'cs_in_end')
        a.b(0x2e, 0x8b, 0x3e); a.word('coop_partners', 2 * p); a.near(0xe8, 'ctl_class')
        a.b(0x84, 0xd8); a.short(0x74, f'cs_keep{p}')        # test al, bl / jz   its own is free
        a.near(0xe8, 'ctl_free'); a.b(0x88, 0x45, 0x09, 0x8a, 0xc4)   # mov [di+9], al / mov al, ah
        a.label(f'cs_keep{p}')
        a.b(0x0a, 0xd8)                                      # or bl, al
    a.label('cs_in_end')
    a.b(0x80, 0xe3, 0x0c, 0x2e, 0x88, 0x1e); a.word('joy_own')   # and bl, 0Ch / mov cs:[joy_own], bl   a joystick of its own
    a.b(0x5a, 0x59, 0x07, 0x5e, 0x5f)                        # pop dx cx es si di
    a.near(0xe8, 'combine')                                  # all the knights' strength and HP
    a.b(0x2e, 0xc6, 0x06); a.word('coop_state'); a.b(0x01)
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x2c, 0x1f)   # the lair's set-up (1F2C)
    a.near(0xe9, 'call_game')
    a.label('cs_sn')                                         # state 2p+1: partner p's fields, 2p+2: registered
    a.b(0x8a, 0xd8, 0xfe, 0xcb, 0xd0, 0xeb, 0x2e, 0x3a, 0x1e); a.word('coop_pn'); a.short(0x72, 'cs_p')   # bl = p / cmp bl, pn / jb
    a.b(0x2e, 0xc6, 0x06); a.word('coop_state'); a.b(0x00)
    a.b(0xc7, 0x46, 0x02, 0x8e, 0x05)                        # mov word [bp+2], 058Eh   on to the fight
    a.near(0xe9, 'rules_done')
    a.label('cs_p')
    a.b(0x32, 0xff, 0xd1, 0xe3, 0x2e, 0x8b, 0xbf); a.word('coop_partners')   # xor bh, bh / shl bx, 1 / mov di, the partner
    a.b(0x2e, 0xfe, 0x06); a.word('coop_state')
    a.b(0xa8, 0x01); a.short(0x74, 'cs_reg')                 # test al, 1 / jz   even: registered
    a.b(0x3c, 0x01); a.short(0x75, 'cs_fields'); a.near(0xe8, 'uncombine')   # the first: the visit's knight's own back
    a.label('cs_fields')
    a.b(0xc6, 0x45, 0x35, 0x06)                              # mov byte [di+35h], 6
    a.b(0x2e, 0x8b, 0x87); a.word('lair_xs'); a.b(0x89, 0x45, 0x02)   # mov ax, cs:[bx+lair_xs] / mov [di+2], ax
    a.b(0xc7, 0x45, 0x04, 0x00, 0x00, 0xc7, 0x45, 0x06, 0x64, 0x00, 0xc6, 0x45, 0x08, 0x03)   # height 0, depth 100, facing left
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x76, 0x1f)   # its fields (1F76)
    a.near(0xe9, 'call_game')
    a.label('cs_reg')
    a.b(0xc7, 0x45, 0x18, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8, 0xbe, STANDING & 0xff, STANDING >> 8)   # the knights' bank / mov si, 15E4h
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x98, 0x29)   # registered (2998)
    a.near(0xe9, 'call_game')
    # ctl_class (di = a knight): al = its input's bit: 1 player 1's keys, 2 player 2's, 4 joystick A, 8 joystick B,
    # 10h the third key set
    a.label('ctl_class')
    a.b(0x8a, 0x45, 0x09)                                    # mov al, [di+9]
    for value, bit in ((1, 2), (JOY_A_CONTROL, 4), (JOY_B_CONTROL, 8), (KEYS3_CONTROL, 0x10)):
        a.b(0xb4, bit, 0x3c, value); a.short(0x74, 'ccl_end')
    a.b(0xb4, 0x01)
    a.label('ccl_end')
    a.b(0x8a, 0xc4, 0xc3)                                    # mov al, ah / ret
    # ctl_free (bl = the bits taken): al = the first free input (2 player 1's keys, 1 player 2's, 5 and 6 the
    # joysticks seen, 7 the third key set), ah = its bit
    a.label('ctl_free')
    a.b(0xb8, 0x02, 0x01, 0x84, 0xe3); a.short(0x74, 'cf_end')   # mov ax, 0102h / test bl, ah / jz
    a.b(0xb8, 0x01, 0x02, 0x84, 0xe3); a.short(0x74, 'cf_end')
    for value, bit in ((JOY_A_CONTROL, 4), (JOY_B_CONTROL, 8)):
        a.b(0xb0, value, 0xb4, bit, 0x2e, 0x84, 0x26); a.word('joy_seen'); a.short(0x74, f'cf_no{value}')
        a.b(0x84, 0xe3); a.short(0x74, 'cf_end')
        a.label(f'cf_no{value}')
    a.b(0xb8, KEYS3_CONTROL, 0x10)                           # the third key set (the list left one for it)
    a.label('cf_end')
    a.b(0xc3)

    # coop_end (1000:0597, test word [0942h],1 after the lair's fight; WhoLived did the fight's own knight): each
    # partner fallen gets its HP back and one life less, as the game's knight; their fields and the knight list
    # back. coop_alive: bit 0 the visit's knight stands, bit 1 + p partner p. The lair is won when a knight stands:
    # a fallen knight of the visit with a partner standing still wins it
    a.label('rules_coop_end')
    a.b(0x2e, 0x83, 0x3e); a.word('coop_partner'); a.b(0x00); a.short(0x75, 'ce_on'); a.near(0xe9, 'ce_test')
    a.label('ce_on')
    a.b(0x50, 0x56, 0x57)                                    # push ax si di
    a.b(0x2e, 0xc6, 0x06); a.word('coop_alive'); a.b(0x00)
    a.b(0xf6, 0x06, 0x42, 0x09, 0x01); a.short(0x75, 'ce_parts')   # test byte [0942h], 1 / jnz
    a.b(0x2e, 0x80, 0x0e); a.word('coop_alive'); a.b(0x01)
    a.label('ce_parts')
    for p in range(COOP_PARTNERS):
        a.b(0x2e, 0x80, 0x3e); a.word('coop_pn'); a.b(p + 1); a.short(0x73, f'ce_p{p}'); a.near(0xe9, 'ce_back')
        a.label(f'ce_p{p}')
        a.b(0x2e, 0x8b, 0x3e); a.word('coop_partners', 2 * p)
        a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7f, f'ce_up{p}')   # cmp word [di+38h], 0 / jg
        a.b(0x8b, 0x45, MAX_HP_FIELD, 0x89, 0x45, 0x38)      # mov ax, [di+3Ch] / mov [di+38h], ax
        a.b(0x80, 0x7d, 0x31, 0x00); a.short(0x7e, f'ce_done{p}'); a.b(0xfe, 0x4d, 0x31)   # lives: one less
        a.short(0xeb, f'ce_done{p}')
        a.label(f'ce_up{p}')
        a.b(0x2e, 0x80, 0x0e); a.word('coop_alive'); a.b(2 << p)   # it stands
        a.label(f'ce_done{p}')
        for k, off in enumerate(COOP_SAVE):
            a.b(0x2e, 0xa1); a.word('coop_saved', 2 * (p * len(COOP_SAVE) + k)); a.b(0x89, 0x45, off)   # its own fields back
    a.label('ce_back')
    a.b(0x2e, 0xa1); a.word('lair_list'); a.b(0xa3, 0xe8, 0x77)   # mov ax, the visit's knight / mov [77E8h], ax
    a.b(0xf6, 0x06, 0x42, 0x09, 0x01); a.short(0x74, 'ce_list')   # test byte [0942h], 1 / jz
    a.b(0x2e, 0xf6, 0x06); a.word('coop_alive'); a.b(0x0e); a.short(0x74, 'ce_list')
    a.b(0x80, 0x26, 0x42, 0x09, 0xfe)                        # and byte [0942h], 0FEh   a partner won the lair
    a.label('ce_list')
    for k, rec in enumerate(KNIGHTS):                        # the practice's list again
        a.b(0x2e, 0xc7, 0x06); a.word('knight_list', 2 * k); a.b(rec & 0xff, rec >> 8)
    a.b(0x2e, 0xc6, 0x06); a.word('coop'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('joy_own'); a.b(0x00)
    a.b(0x2e, 0x80, 0x3e); a.word('coop_alive'); a.b(0x00); a.short(0x75, 'ce_pop')
    a.b(0x2e, 0xc7, 0x06); a.word('coop_partner'); a.b(0x00, 0x00)   # all fell: no chest
    a.label('ce_pop')
    a.b(0x5f, 0x5e, 0x58)                                    # pop di si ax
    a.label('ce_test')
    a.b(0xf7, 0x06, 0x42, 0x09, 0x01, 0x00)                  # test word [0942h], 1   (replaced)
    a.near(0xe9, 'rules_flags')

    # coop_loot (1000:05C6, call BFAC with ax = 2: the lair's chest for [77E8h]): with partners, the chest for each
    # knight standing in turn: full, in a random order, the lair's gold and items put back between them (each
    # gets all of it) but the keys and the Moonstones (the first takes those); shared, the visit's knight first
    # (if it stands), the rest in a random order, the last taking all the gold left. Then [77E8h] the visit's
    # knight again
    a.label('rules_coop_loot')
    a.near(0xe8, 'loot_cap')                                 # catchup: at most +50 % gold
    a.b(0x2e, 0x83, 0x3e); a.word('coop_partner'); a.b(0x00); a.short(0x75, 'clt_on')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xac, 0xbf)   # as the game: call BFAC
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xc9, 0x05)
    a.near(0xe9, 'call_game')
    a.label('clt_on')
    a.b(0x56, 0x57, 0x51)                                    # push si di cx
    a.b(0x2e, 0x80, 0x3e); a.word('coop_lstate'); a.b(0x00); a.short(0x74, 'clt_first'); a.near(0xe9, 'clt_next')
    a.label('clt_first')
    a.b(0x8b, 0x36, 0x62, 0x69, 0x8b, 0x44, 0x06, 0x2e, 0xa3); a.word('coop_gold')   # mov si, [6962h] / the lair's gold
    a.b(0x8b, 0x34, 0xbf); a.word('coop_items'); a.b(0xb9, LAIR_ITEMS, 0x00)   # mov si, [si] / mov di, coop_items / mov cx, 24
    a.label('clt_save')
    a.b(0x8a, 0x04, 0x2e, 0x88, 0x05, 0x46, 0x47); a.short(0xe2, 'clt_save')   # mov al, [si] / mov cs:[di], al / inc si, di
    a.near(0xe8, 'coop_order_make')
    a.near(0xe8, 'shared_chest')                             # coop_lairs = shared: the chest a little fuller, the share
    a.label('clt_next')
    a.b(0x2e, 0xfe, 0x06); a.word('coop_lstate')             # inc byte cs:[coop_lstate]   the chest's number
    a.b(0x2e, 0xa0); a.word('coop_lstate'); a.b(0x2e, 0x3a, 0x06); a.word('coop_count'); a.short(0x76, 'clt_turn')
    a.b(0x2e, 0xa1); a.word('lair_list'); a.b(0xa3, 0xe8, 0x77, 0xa3, 0x79, 0x89)   # the visit's knight again ([77E8h], [8979h])
    a.b(0x2e, 0xc6, 0x06); a.word('coop_lstate'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('coop_share'); a.b(0x00)
    a.b(0x2e, 0xc7, 0x06); a.word('coop_partner'); a.b(0x00, 0x00)
    a.b(0xc7, 0x46, 0x02, 0xc9, 0x05)                        # mov word [bp+2], 05C9h   on (CheckLairClear)
    a.b(0x59, 0x5f, 0x5e); a.near(0xe9, 'rules_done')
    a.label('clt_turn')
    a.b(0x8a, 0xd8, 0xfe, 0xcb, 0x32, 0xff, 0x2e, 0x8a, 0x9f); a.word('coop_order')   # bl = the chest's number - 1 / bl = its knight's place
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0xbf); a.word('lair_list')   # shl bx, 1 / mov di, cs:[bx+lair_list]
    a.b(0x89, 0x3e, 0xe8, 0x77, 0x89, 0x3e, 0x79, 0x89)      # mov [77E8h], di / mov [8979h], di   (the item screen's knight)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_COOP_LAIRS); a.b(COOP_MODES['shared']); a.short(0x75, 'clt_full')
    # shared: nothing put back; the last one takes all the gold that is left with one click
    a.b(0x2e, 0x3a, 0x06); a.word('coop_count'); a.short(0x75, 'clt_open')
    a.b(0x2e, 0xc6, 0x06); a.word('coop_last'); a.b(0x01); a.short(0xeb, 'clt_open')
    a.label('clt_full')
    a.b(0x3c, 0x01); a.short(0x74, 'clt_open')               # the first: as it is
    a.b(0x8b, 0x36, 0x62, 0x69, 0x2e, 0xa1); a.word('coop_gold'); a.b(0x89, 0x44, 0x06)   # the gold
    a.b(0x8b, 0x34, 0xbf); a.word('coop_items'); a.b(0xb9, LAIR_ITEMS, 0x00, 0x33, 0xdb)   # mov si, [si] / di / cx / xor bx, bx
    a.label('clt_back')
    a.b(0x83, 0xfb, KEYS_ITEM); a.short(0x74, 'clt_keep'); a.b(0x83, 0xfb, MOONSTONES_ITEM); a.short(0x74, 'clt_keep')
    a.b(0x2e, 0x8a, 0x05, 0x88, 0x00)                        # mov al, cs:[di] / mov [bx+si], al
    a.label('clt_keep')
    a.b(0x47, 0x43); a.short(0xe2, 'clt_back')               # inc di / inc bx / loop
    a.label('clt_open')
    a.b(0x59, 0x5f, 0x5e)                                    # pop cx di si
    a.b(0xb8, 0x02, 0x00)                                    # mov ax, 2   the lair's chest
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xac, 0xbf)   # call BFAC
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xc6, 0x05)      # back to this int
    a.near(0xe9, 'call_game')
    # coop_order_make: coop_order = the places (0 the visit's knight, 1 + p partner p) of the knights standing,
    # coop_count of them, in a random order; shared: the visit's knight first if it stands
    a.label('coop_order_make')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56)                        # push ax bx cx dx si
    a.b(0x33, 0xdb, 0xbe); a.word('coop_order')              # xor bx, bx / mov si, coop_order
    a.label('com_pos')
    a.b(0xb0, 0x01, 0x8a, 0xcb, 0xd2, 0xe0, 0x2e, 0x84, 0x06); a.word('coop_alive'); a.short(0x74, 'com_next')   # its bit
    a.b(0x2e, 0x88, 0x1c, 0x46)                              # mov cs:[si], bl / inc si
    a.label('com_next')
    a.b(0xfe, 0xc3, 0x2e, 0x3a, 0x1e); a.word('coop_pn'); a.short(0x76, 'com_pos')   # inc bl / cmp bl, pn / jbe
    a.b(0x8b, 0xc6, 0x2d); a.word('coop_order'); a.b(0x2e, 0xa2); a.word('coop_count')
    a.b(0x2e, 0xc6, 0x06); a.word('coop_start'); a.b(0x00)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_COOP_LAIRS); a.b(COOP_MODES['shared']); a.short(0x75, 'com_shuffle')
    a.b(0x2e, 0xf6, 0x06); a.word('coop_alive'); a.b(0x01); a.short(0x74, 'com_shuffle')
    a.b(0x2e, 0xc6, 0x06); a.word('coop_start'); a.b(0x01)   # the visit's knight stays first
    a.label('com_shuffle')
    a.b(0x2e, 0x8a, 0x0e); a.word('coop_count'); a.b(0xfe, 0xc9)   # cl = the last place
    a.label('com_swap')
    a.b(0x2e, 0x3a, 0x0e); a.word('coop_start'); a.short(0x7e, 'com_end')   # cmp cl, start / jle
    a.near(0xe8, 'game_random')                              # (keeps bx, cx)
    a.b(0x33, 0xd2, 0x8a, 0xd9, 0x2e, 0x2a, 0x1e); a.word('coop_start'); a.b(0xfe, 0xc3, 0x32, 0xff, 0xf7, 0xf3)   # dx = r % (cl - start + 1)
    a.b(0x2e, 0x02, 0x16); a.word('coop_start')              # add dl, start   j
    a.b(0x8a, 0xd9, 0x32, 0xff, 0x2e, 0x8a, 0x87); a.word('coop_order')   # mov bl, cl / xor bh, bh / mov al, order[i]
    a.b(0x8a, 0xda, 0x2e, 0x86, 0x87); a.word('coop_order')  # mov bl, dl / xchg al, order[j]
    a.b(0x8a, 0xd9, 0x2e, 0x88, 0x87); a.word('coop_order')  # mov bl, cl / mov order[i], al
    a.b(0xfe, 0xc9); a.short(0xeb, 'com_swap')
    a.label('com_end')
    a.b(0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)

    # shared_chest (coop_lairs = shared, before the first chest; ds = MAIN's data): with n knights standing the
    # lair's gold and items grow by extra_loot_per_knight percent for each past the first (an item's fraction by
    # chance), and coop_gold_share = the gold / n rounded up: what a click on the gold takes (gold_click)
    a.label('shared_chest')
    a.b(0x2e, 0xc6, 0x06); a.word('coop_share'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('coop_last'); a.b(0x00)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_COOP_LAIRS); a.b(COOP_MODES['shared']); a.short(0x74, 'sc_on'); a.b(0xc3)
    a.label('sc_on')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56)                        # push ax bx cx dx si
    a.b(0x2e, 0xa0); a.word('coop_count')                    # al = the knights standing
    a.b(0x32, 0xe4, 0x2e, 0xa3); a.word('coop_n')            # xor ah, ah / mov cs:[coop_n], ax   knights standing
    a.b(0x48, 0x2e, 0x8a, 0x16); a.word('rules_table', G_COOP_EXTRA); a.b(0x32, 0xf6, 0xf7, 0xe2)   # dec ax / mov dl, extra / xor dh, dh / mul dx
    a.b(0x2e, 0xa3); a.word('coop_pct')                      # mov cs:[coop_pct], ax   the extra, percent
    a.b(0x8b, 0x36, 0x62, 0x69, 0x8b, 0x44, 0x06)            # mov si, [6962h] / mov ax, [si+6]   the gold
    a.near(0xe8, 'grow')                                     # ax + ax * pct / 100 (the rest by chance)
    a.b(0x89, 0x44, 0x06)                                    # mov [si+6], ax
    a.b(0x2e, 0x8b, 0x0e); a.word('coop_n'); a.b(0x03, 0xc1, 0x48, 0x33, 0xd2, 0xf7, 0xf1)   # add ax, n / dec ax / xor dx, dx / div n   rounded up
    a.b(0x2e, 0xa3); a.word('coop_gold_share')
    a.b(0x8b, 0x34, 0x33, 0xdb)                              # mov si, [si] / xor bx, bx   its items
    a.label('sc_item')
    a.b(0x83, 0xfb, KEYS_ITEM); a.short(0x74, 'sc_next'); a.b(0x83, 0xfb, MOONSTONES_ITEM); a.short(0x74, 'sc_next')
    a.b(0x8a, 0x00, 0x32, 0xe4); a.near(0xe8, 'grow'); a.b(0x88, 0x00)   # mov al, [bx+si] / xor ah, ah / call grow / mov [bx+si], al
    a.label('sc_next')
    a.b(0x43, 0x83, 0xfb, LAIR_ITEMS); a.short(0x72, 'sc_item')
    a.b(0x2e, 0xc6, 0x06); a.word('coop_share'); a.b(0x01)
    a.b(0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)                  # pop si dx cx bx ax / ret
    # grow: ax = ax + ax * coop_pct / 100, the remainder (of 100) as a chance of one more (keeps bx cx si)
    a.label('grow')
    a.b(0x53, 0x51, 0x8b, 0xc8)                              # push bx cx / mov cx, ax
    a.b(0x2e, 0xf7, 0x26); a.word('coop_pct')                # mul word cs:[coop_pct]
    a.b(0xbb, 0x64, 0x00, 0xf7, 0xf3)                        # mov bx, 100 / div bx   ax = the extra, dx = its remainder
    a.b(0x03, 0xc8, 0x52)                                    # add cx, ax / push dx
    a.near(0xe8, 'game_random')
    a.b(0x33, 0xd2, 0xf7, 0xf3, 0x58, 0x3b, 0xd0); a.short(0x73, 'gr_no'); a.b(0x41)   # xor dx, dx / div bx / pop ax / cmp dx, ax / jae / inc cx
    a.label('gr_no')
    a.b(0x8b, 0xc1, 0x59, 0x5b, 0xc3)                        # mov ax, cx / pop cx bx / ret
    # gold_click (1000:CED3, call D6E1 as the item screen's gold is clicked): in a shared chest the click may take
    # the share (the last knight: all); gold_step counts it down
    a.label('rules_gold_click')
    a.b(0x50, 0x2e, 0xa1); a.word('coop_gold_share')         # push ax / mov ax, cs:[coop_gold_share]
    a.b(0x2e, 0x80, 0x3e); a.word('coop_last'); a.b(0x00); a.short(0x74, 'gk_set'); a.b(0xb8, 0xff, 0xff)   # the last: all
    a.label('gk_set')
    a.b(0x2e, 0xa3); a.word('coop_gold_left'); a.b(0x58)     # mov cs:[coop_gold_left], ax / pop ax
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe1, 0xd6)   # call D6E1   (replaced)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xd6, 0xce)
    a.near(0xe9, 'call_game')
    # gold_step (1000:CEFA, dec word [di] as a gold piece leaves the chest, di = the chest's gold): a shared chest's
    # click stops at its share: on at the loop's end (CF04) instead
    a.label('rules_gold_step')
    a.b(0x2e, 0x80, 0x3e); a.word('coop_share'); a.b(0x00); a.short(0x74, 'gs_game')
    a.b(0x2e, 0x83, 0x3e); a.word('coop_gold_left'); a.b(0x00); a.short(0x75, 'gs_count')
    a.b(0xc7, 0x46, 0x02, 0x04, 0xcf); a.near(0xe9, 'rules_done')   # mov word [bp+2], 0CF04h   this click's share is taken
    a.label('gs_count')
    a.b(0x2e, 0xff, 0x0e); a.word('coop_gold_left')          # dec word cs:[coop_gold_left]
    a.label('gs_game')
    a.b(0xff, 0x0d); a.near(0xe9, 'rules_done')              # dec word [di]   (replaced)

    # --- D36: the item screen's pointer ---
    # pointer (1000:D08C, call 83C0 in MovePointer, then the bits move [0E492h] x / [0E494h] y by 2): the game's
    # call first (this int again), then the move here by the time held, and only fire left for the game's test
    a.label('rules_pointer')
    a.b(0x2e, 0x80, 0x3e); a.word('ptr_back'); a.b(0x00); a.short(0x75, 'pt_move')
    a.b(0x2e, 0xc6, 0x06); a.word('ptr_back'); a.b(0x01)
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x50, 0x8b, 0x46, 0x02, 0x48, 0x48, 0x2e, 0xa3); a.word('call_ret'); a.b(0x58)   # this site's int again
    a.near(0xe9, 'call_game')
    a.label('pt_move')
    a.b(0x2e, 0xc6, 0x06); a.word('ptr_back'); a.b(0x00)
    a.b(0x50, 0x51, 0x52, 0x56)                              # push ax cx dx si
    a.b(0x8b, 0x5e, 0xfe, 0x8b, 0x36, 0x88, 0xed, 0x80, 0x7c, 0x09, 0x01); a.short(0x75, 'pt_bits'); a.b(0x8b, 0xd8)   # bx = the game's bx, or ax for +9 = 1
    a.label('pt_bits')
    a.b(0x83, 0xe3, 0x0f)                                    # and bx, 0Fh   the directions
    a.b(0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0x8b, 0x0e, 0x6c, 0x04, 0x1f)   # push ds / ds = 0 / mov cx, [046Ch] / pop ds   the tick
    a.b(0x0b, 0xdb); a.short(0x75, 'pt_held')
    a.b(0x2e, 0xc6, 0x06); a.word('ptr_bits'); a.b(0x00); a.near(0xe9, 'pt_done')   # nothing held
    a.label('pt_held')
    a.b(0x2e, 0x3a, 0x1e); a.word('ptr_bits'); a.short(0x74, 'pt_same')
    a.b(0x2e, 0x88, 0x1e); a.word('ptr_bits'); a.b(0x2e, 0x89, 0x0e); a.word('ptr_t0'); a.b(0x2e, 0x89, 0x0e); a.word('ptr_t')
    a.b(0xba, PTR_STEP, 0x00); a.short(0xeb, 'pt_go')        # a new press: one step now
    a.label('pt_same')
    a.b(0x8b, 0xc1, 0x2e, 0x2b, 0x06); a.word('ptr_t0')      # mov ax, cx / sub ax, held since
    a.b(0x33, 0xd2, 0x3d, PTR_DELAY, 0x00); a.short(0x73, 'pt_fast')   # xor dx, dx / held long enough
    a.b(0x2e, 0x89, 0x0e); a.word('ptr_t'); a.short(0xeb, 'pt_done')   # not yet: no move, none saved up
    a.label('pt_fast')
    a.b(0xb2, PTR_SLOW, 0x3d, PTR_FAST_AFTER, 0x00); a.short(0x72, 'pt_speed'); a.b(0xb2, PTR_FAST)
    a.label('pt_speed')
    a.b(0x8b, 0xc1, 0x2e, 0x2b, 0x06); a.word('ptr_t'); a.b(0x2e, 0x89, 0x0e); a.word('ptr_t')   # the ticks since the last move
    a.b(0x3d, 0x08, 0x00); a.short(0x76, 'pt_n'); a.b(0xb8, 0x08, 0x00)   # (a long pause: 8 at most)
    a.label('pt_n')
    a.b(0xf6, 0xe2, 0x8b, 0xd0)                              # mul dl / mov dx, ax   the step
    a.label('pt_go')
    a.b(0xf6, 0xc3, 0x01); a.short(0x74, 'pt_l'); a.b(0x01, 0x16, 0x92, 0xe4)   # right: x +
    a.label('pt_l')
    a.b(0xf6, 0xc3, 0x02); a.short(0x74, 'pt_d'); a.b(0x29, 0x16, 0x92, 0xe4)   # left
    a.label('pt_d')
    a.b(0xf6, 0xc3, 0x04); a.short(0x74, 'pt_u'); a.b(0x01, 0x16, 0x94, 0xe4)   # down: y +
    a.label('pt_u')
    a.b(0xf6, 0xc3, 0x08); a.short(0x74, 'pt_done'); a.b(0x29, 0x16, 0x94, 0xe4)   # up
    a.short(0xeb, 'pt_done')
    a.label('pt_done')
    a.b(0x5e, 0x5a, 0x59, 0x58)                              # pop si dx cx ax
    a.b(0x81, 0x66, 0xfe, 0x10, 0x00, 0x25, 0x10, 0x00)      # and word [bp-2], 10h / and ax, 10h   fire only for the game
    a.near(0xe9, 'rules_done')

    # --- D35: sword enchantments ---
    # ench_of (si = a knight): al = its sword's enchantment (0: none, a computer's knight, the rule off, another
    # sword than the one enchanted: then it is gone; Gore with gore off: none for now); keeps the rest
    a.label('ench_of')
    a.b(0x53, 0x52, 0x57, 0x8b, 0xfe, 0x32, 0xc0)            # push bx dx di / mov di, si / xor al, al
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_ENCHANT); a.b(0x00); a.short(0x74, 'eo_end')
    a.near(0xe8, 'knight_no'); a.short(0x72, 'eo_end')
    a.b(0x83, 0x7c, 0x20, COMPUTER); a.short(0x74, 'eo_end')
    a.b(0x2e, 0x8a, 0x87); a.word('ench_k'); a.b(0x0a, 0xc0); a.short(0x74, 'eo_end')
    a.b(0x50, 0x2e, 0x8a, 0x87); a.word('ench_w'); a.b(0x3a, 0x44, 0x40, 0x58); a.short(0x74, 'eo_same')   # the sword enchanted?
    a.b(0x2e, 0xc6, 0x87); a.word('ench_k'); a.b(0x00, 0x32, 0xc0); a.short(0xeb, 'eo_end')   # gone with it
    a.label('eo_same')
    a.b(0x3c, E_GORE); a.short(0x75, 'eo_end')
    a.b(0x83, 0x3e, GORE & 0xff, GORE >> 8, 0x00); a.short(0x74, 'eo_end'); a.b(0x32, 0xc0)   # gore off ([0700h] <> 0): no effect
    a.label('eo_end')
    a.b(0x5f, 0x5a, 0x5b, 0xc3)
    # holder_slot (the item screen: [0ED92h] 2 a lair's chest, 0Ah the dragon's hoard): bx = its byte in
    # lair_ench / hoard_ench (0 not decided, 1 none, 1 + an enchantment); CF = 1 for anything else
    a.label('holder_slot')
    a.b(0x50, 0x52, 0x83, 0x3e, 0x92, 0xed, 0x02); a.short(0x75, 'xhs_dragon')
    a.b(0xa1, 0x62, 0x69, 0x2d, LAIR_FIRST, 0x00); a.short(0x72, 'xhs_no')   # mov ax, [6962h] / sub ax, 2 / jb
    a.b(0x33, 0xd2, 0xbb, LAIR_SIZE, 0x00, 0xf7, 0xf3, 0x0b, 0xd2); a.short(0x75, 'xhs_no')
    a.b(0x3d, LAIR_COUNT, 0x00); a.short(0x73, 'xhs_no')
    a.b(0x8b, 0xd8, 0x81, 0xc3); a.word('lair_ench'); a.short(0xeb, 'xhs_yes')   # mov bx, ax / add bx, lair_ench
    a.label('xhs_dragon')
    a.b(0x83, 0x3e, 0x92, 0xed, 0x0a); a.short(0x75, 'xhs_no')
    a.b(0xbb); a.word('hoard_ench')
    a.label('xhs_yes')
    a.b(0x5a, 0x58, 0xf8, 0xc3)
    a.label('xhs_no')
    a.b(0x5a, 0x58, 0xf9, 0xc3)
    # holder_get (si = the chest's item table): al = its enchantment, 0 none; decided the first time (the chance %,
    # not with the Sword of Sharpness there; Gore only with gore on)
    a.label('holder_get')
    a.b(0x53, 0x32, 0xc0)                                    # push bx / xor al, al
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_ENCHANT); a.b(0x00); a.short(0x74, 'xhg_end')
    a.near(0xe8, 'holder_slot'); a.short(0x72, 'xhg_end')
    a.b(0x2e, 0x8a, 0x07, 0x0a, 0xc0); a.short(0x75, 'xhg_have')   # mov al, cs:[bx] / or al, al / jnz
    a.b(0x2e, 0xc6, 0x07, 0x01)                              # decided: none
    a.b(0x80, 0x7c, 0x04, 0x00); a.short(0x75, 'xhg_none')    # cmp byte [si+4], 0 / jne   the Sword of Sharpness there
    a.b(0x52, 0x51); a.near(0xe8, 'game_random'); a.b(0x33, 0xd2, 0xb9, 100, 0x00, 0xf7, 0xf1)   # push dx cx / dx = 0-99
    a.b(0x2e, 0x3a, 0x16); a.word('rules_table', G_ENCH_CHANCE); a.short(0x73, 'xhg_pop')   # cmp dl, the chance / jae
    a.near(0xe8, 'game_random'); a.b(0x33, 0xd2, 0xb9, len(ENCH_NAMES), 0x00)   # the enchantment: 1-8
    a.b(0x83, 0x3e, GORE & 0xff, GORE >> 8, 0x00); a.short(0x74, 'xhg_div'); a.b(0x49)   # gore off ([0700h] <> 0): of the 7 others
    a.label('xhg_div')
    a.b(0xf7, 0xf1, 0x42, 0x83, 0x3e, GORE & 0xff, GORE >> 8, 0x00); a.short(0x74, 'xhg_set')   # div cx / inc dx
    a.b(0x83, 0xfa, E_GORE); a.short(0x72, 'xhg_set'); a.b(0x42)   # from Gore on: one more
    a.label('xhg_set')
    a.b(0xfe, 0xc2, 0x2e, 0x88, 0x17)                        # inc dl / mov cs:[bx], dl   1 + it
    a.label('xhg_pop')
    a.b(0x59, 0x5a, 0x2e, 0x8a, 0x07)                        # pop cx dx / mov al, cs:[bx]
    a.label('xhg_have')
    a.b(0xfe, 0xc8)                                          # dec al   (1: none -> 0)
    a.short(0xeb, 'xhg_end')
    a.label('xhg_none')
    a.b(0x32, 0xc0)
    a.label('xhg_end')
    a.b(0x5b, 0xc3)
    # ench_put (es = ds, di = MAIN's data, cs:si = a text): copied, di after it (no end); ench_name_put (al = an
    # enchantment): its name
    a.label('ench_put')
    a.b(0x50)
    a.label('ep_loop')
    a.b(0x2e, 0x8a, 0x04, 0x0a, 0xc0); a.short(0x74, 'ep_end'); a.b(0x88, 0x05, 0x46, 0x47); a.short(0xeb, 'ep_loop')
    a.label('ep_end')
    a.b(0x58, 0xc3)
    a.label('ench_name_put')
    a.b(0x56, 0x53, 0x32, 0xe4, 0x48, 0xd1, 0xe0, 0x8b, 0xd8, 0x2e, 0x8b, 0xb7); a.word('ench_names')   # bx = (al - 1) * 2 / mov si, cs:[bx+ench_names]
    a.near(0xe8, 'ench_put'); a.b(0x5b, 0x5e, 0xc3)
    # ench_desc (dx = the panel's part of ENCH_AREA, its text at dx + 20, al = the gadget's flags): a gadget's
    # descriptor of 10 bytes (as 1000:D5F0 makes them) at [0E4A8h] + 10 k in that part, [0E4A4h] = 2 k for it
    a.label('ench_desc')
    a.b(0x50, 0x53, 0x51, 0x52, 0x57, 0x8a, 0xc8)            # push ax bx cx dx di / mov cl, al
    a.b(0x8b, 0xc2, 0x2b, 0x06, 0xa8, 0xe4, 0x05, 0x09, 0x00, 0x52, 0x33, 0xd2, 0xbb, 0x0a, 0x00, 0xf7, 0xf3, 0x5a)   # ax = (dx - [0E4A8h] + 9) / 10   k
    a.b(0x8b, 0xd8, 0xd1, 0xe3, 0x89, 0x1e, 0xa4, 0xe4)      # mov bx, ax / shl bx, 1 / mov [0E4A4h], bx
    a.b(0xbb, 0x0a, 0x00, 0x52, 0xf7, 0xe3, 0x5a, 0x03, 0x06, 0xa8, 0xe4, 0x8b, 0xf8)   # di = [0E4A8h] + 10 k
    a.b(0x83, 0xc2, 0x14, 0x89, 0x15, 0xc7, 0x45, 0x02, 0x00, 0x00, 0xc7, 0x45, 0x04, 0x03, 0x00)   # [di] = the text / 0 / 3
    a.b(0x32, 0xed, 0x89, 0x4d, 0x06, 0xc7, 0x45, 0x08, 0x00, 0x00)   # [di+6] = the flags / [di+8] = 0
    a.b(0x5f, 0x5a, 0x59, 0x5b, 0x58, 0xc3)
    # ench_part: dx = ENCH_AREA's part of the panel ([0E4AEh] 0: the first, else the second)
    a.label('ench_part')
    a.b(0xba, ENCH_AREA & 0xff, ENCH_AREA >> 8, 0x83, 0x3e, 0xae, 0xe4, 0x00); a.short(0x74, 'ept_end')
    a.b(0x83, 0xc2, 0x40)
    a.label('ept_end')
    a.b(0xc3)

    # ench_icon (1000:C8E5, cmp word [si+4],0 in DisplayMSword, si = a chest's or the hoard's items): with an
    # enchantment there, its icon in the magic sword's place ("Enchantment of ..."), item ENCH_ITEM to take
    a.label('rules_ench_icon')
    a.b(0x50); a.near(0xe8, 'holder_get'); a.b(0x0a, 0xc0); a.short(0x75, 'ei_on')
    a.b(0x58, 0x83, 0x7c, 0x04, 0x00); a.near(0xe9, 'rules_flags')   # pop ax / cmp word [si+4], 0   (replaced)
    a.label('ei_on')
    a.b(0x52, 0x57, 0x56, 0x06, 0x1e, 0x07)                  # push dx di si es / push ds / pop es
    a.b(0xba, (ENCH_AREA + 0x40) & 0xff, (ENCH_AREA + 0x40) >> 8, 0x8b, 0xfa, 0x83, 0xc7, 0x14)   # the second part / di = its text
    a.b(0xbe); a.word('ench_text'); a.near(0xe8, 'ench_put'); a.near(0xe8, 'ench_name_put')
    a.b(0xc6, 0x05, 0x00, 0xb0, 0x23); a.near(0xe8, 'ench_desc')   # its end / flags 23h: one to take
    a.b(0x07, 0x5e, 0x5f, 0x5a, 0x58)
    for addr, value in ((0xe49a, ENCH_ICON), (0xe49c, ENCH_X), (0xe49e, ENCH_Y), (0xe4a0, 0), (0xe4a2, 1), (0xe4a6, ENCH_ITEM)):
        a.b(0xc7, 0x06, addr & 0xff, addr >> 8, value & 0xff, value >> 8)
    a.b(0x56, 0x8b, 0x36, 0x88, 0xed, 0x8b, 0x74, 0x40, 0x83, 0xfe, 0x16); a.short(0x72, 'ei_icon')   # the knight's sword (+40h)
    a.b(0x83, 0xfe, SHARPNESS); a.short(0x73, 'ei_icon'); a.b(0x89, 0x36, 0x9a, 0xe4)   # 16h-18h: its picture
    a.label('ei_icon')
    a.b(0x5e)
    a.b(0xb9, 0x01, 0x00, 0xc7, 0x46, 0x02, 0x18, 0xc9)      # mov cx, 1 / on at C918 (PlaceIcons)
    a.near(0xe9, 'rules_done')
    # ench_name (1000:C51D, mov [0E4A4h],ax as the item screen's knight panel shows the sword): an enchanted sword's
    # text "<sword> of <enchantment>", its gadget's flags as the game's
    a.label('rules_ench_name')
    a.b(0xa3, 0xa4, 0xe4)                                    # (replaced)
    a.b(0x50, 0x56, 0x8b, 0x36, 0x90, 0xe4); a.near(0xe8, 'ench_of'); a.b(0x0a, 0xc0); a.short(0x75, 'en_on')
    a.b(0x5e, 0x58); a.near(0xe9, 'rules_done')
    a.label('en_on')
    a.b(0x53, 0x52, 0x57, 0x06, 0x1e, 0x07, 0x50)            # push bx dx di es / push ds / pop es / push ax
    a.near(0xe8, 'ench_part'); a.b(0x8b, 0xfa, 0x83, 0xc7, 0x14)   # dx = the part / di = its text
    a.b(0x8b, 0x44, 0x40)                                    # mov ax, [si+40h]   the sword
    for value, name in WEAPON_NAMES:
        a.b(0x3d, value, 0x00); a.short(0x75, f'en_n{value:x}'); a.b(0xbe); a.word(f'wname_{value:x}'); a.short(0xeb, 'en_name')
        a.label(f'en_n{value:x}')
    a.b(0xbe); a.word('wname_16')
    a.label('en_name')
    a.near(0xe8, 'ench_put'); a.b(0xbe); a.word('ench_of_text'); a.near(0xe8, 'ench_put')
    a.b(0x58); a.near(0xe8, 'ench_name_put'); a.b(0xc6, 0x05, 0x00)   # pop ax / its name / the end
    a.b(0xa1, 0xa4, 0xe4, 0xd1, 0xe8, 0xbb, 0x0a, 0x00, 0x52, 0xf7, 0xe3, 0x5a, 0x03, 0x06, 0xa8, 0xe4, 0x8b, 0xd8)   # bx = the game's descriptor
    a.b(0x8a, 0x47, 0x06); a.near(0xe8, 'ench_desc')         # its flags / ours
    a.b(0x07, 0x5f, 0x5a, 0x5b, 0x5e, 0x58); a.near(0xe9, 'rules_done')
    # ench_take (1000:CD9F, cmp bx,4 / jne CDA7 in HGTakeMagic: a click that takes an item, bx = it): the
    # enchantment (ENCH_ITEM) onto the clicking knight's sword ([0ED88h]), replacing one it had; not a computer's
    # knight, not the Sword of Sharpness (then it stays). The screen again (CDC4); bx 4 as the game (CEAD), else CDA7
    a.label('rules_ench_take')
    a.b(0x8b, 0x5e, 0xfe, 0x83, 0xfb, 0x04)                  # mov bx, [bp-2] (the game's bx) / cmp bx, 4
    a.short(0x75, 'et_not4'); a.b(0xc7, 0x46, 0x02, 0xad, 0xce); a.near(0xe9, 'rules_done')
    a.label('et_not4')
    a.b(0x83, 0xfb, ARM_ITEM); a.short(0x75, 'et_not_arm'); a.near(0xe9, 'arm_take')
    a.label('et_not_arm')
    a.b(0x83, 0xfb, ENCH_ITEM); a.short(0x74, 'et_ours'); a.b(0xc7, 0x46, 0x02, 0xa7, 0xcd); a.near(0xe9, 'rules_done')
    a.label('et_ours')
    a.b(0xc7, 0x46, 0x02, 0xd5, 0xcd)                        # CDD5: nothing (ret)
    a.b(0x50, 0x52, 0x56, 0x57)
    a.near(0xe8, 'holder_slot'); a.short(0x72, 'et_pop')
    a.b(0x2e, 0x8a, 0x07, 0x2c, 0x01); a.short(0x76, 'et_pop')   # mov al, cs:[bx] / sub al, 1 / jbe   none
    a.b(0x8b, 0x36, 0x88, 0xed, 0x83, 0x7c, 0x20, COMPUTER); a.short(0x74, 'et_pop')   # the knight
    a.b(0x8b, 0x54, 0x40, 0x83, 0xfa, 0x16); a.short(0x72, 'et_pop'); a.b(0x83, 0xfa, SHARPNESS); a.short(0x73, 'et_pop')   # a sword it may have
    a.b(0x53, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.short(0x72, 'et_pop_bx')   # (knight_no: dx gone)
    a.b(0x2e, 0x88, 0x87); a.word('ench_k'); a.b(0x8b, 0x54, 0x40, 0x2e, 0x88, 0x97); a.word('ench_w')   # its enchantment, the sword
    a.b(0x5b, 0x2e, 0xc6, 0x07, 0x01)                        # pop bx / the chest's: none
    a.b(0xc7, 0x46, 0x02, 0xc4, 0xcd); a.short(0xeb, 'et_pop')   # the screen again
    a.label('et_pop_bx')
    a.b(0x5b)
    a.label('et_pop')
    a.b(0x5f, 0x5e, 0x5a, 0x58); a.near(0xe9, 'rules_done')
    # ench_tkwp (1000:CE91, mov bp,[di+40h] in TKWP: the knight si takes the sword of the knight di if it is no
    # worse than its own, di gets a long sword either way): the enchantment goes with the sword taken (to a
    # player's knight), the sword left gets none
    a.label('rules_ench_tkwp')
    a.b(0x50, 0x53, 0x52, 0x51)
    a.b(0x8b, 0x45, 0x40, 0x89, 0x46, 0x00)                  # mov ax, [di+40h] / mov [bp], ax   (replaced: the game's bp)
    a.b(0x3d, 0x16, 0x00); a.short(0x74, 'ek_pop')           # the other's a long sword: nothing taken
    a.b(0x56, 0x8b, 0xf7); a.near(0xe8, 'ench_of'); a.b(0x8a, 0xc8); a.near(0xe8, 'ench_clear'); a.b(0x5e)   # cl = its enchantment / the other's: none
    a.b(0x8b, 0x45, 0x40, 0x3b, 0x44, 0x40); a.short(0x7c, 'ek_pop')   # cmp [di+40h], [si+40h] / jl   not taken
    a.near(0xe8, 'ench_clear')                               # the taker's own sword goes
    a.b(0x0a, 0xc9); a.short(0x74, 'ek_pop'); a.b(0x83, 0x7c, 0x20, COMPUTER); a.short(0x74, 'ek_pop')
    a.b(0x57, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.b(0x5f); a.short(0x72, 'ek_pop')
    a.b(0x2e, 0x88, 0x8f); a.word('ench_k'); a.b(0x8b, 0x45, 0x40, 0x2e, 0x88, 0x87); a.word('ench_w')   # its enchantment, the sword
    a.label('ek_pop')
    a.b(0x59, 0x5a, 0x5b, 0x58); a.near(0xe9, 'rules_done')
    # ench_clear (si = a knight): its enchantment gone (keeps everything)
    a.label('ench_clear')
    a.b(0x53, 0x52, 0x57, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.short(0x72, 'ec_end')
    a.b(0x2e, 0xc6, 0x87); a.word('ench_k'); a.b(0x00)
    a.label('ec_end')
    a.b(0x5f, 0x5a, 0x5b, 0xc3)

    # ench_hit (1000:2DA4, cmp dx,10h / jne / shl ax,1 in 2D73, a knight's (si) blow's damage ax by its attack dx;
    # the caller's struck object: di, or the si it pushed (Balok 3776, demon 5215, mudman 55BF), or [77E8h] (troll
    # 56D2); not the monsters' numbers (AdjustLevel 28D2)): the chop doubles, with Smite triples; the banes double
    # or kill at once their monsters
    a.label('rules_ench_hit')
    a.b(0xc7, 0x46, 0x02, 0xab, 0x2d)                        # on at 2DABh
    a.b(0x53, 0x51)                                          # push bx cx
    a.b(0x8b, 0x4e, 0x0e, 0x81, 0xf9, 0xd2, 0x28); a.short(0x75, 'eh_on')   # mov cx, the return / cmp cx, 28D2h
    a.b(0x83, 0xfa, CHOP); a.short(0x75, 'eh_pop0'); a.b(0xd1, 0xe0)   # as the game
    a.label('eh_pop0')
    a.near(0xe9, 'eh_pop')
    a.label('eh_on')
    a.b(0x50); a.near(0xe8, 'ench_of'); a.b(0x8a, 0xd8, 0x58)   # bl = the enchantment
    a.b(0x83, 0xfa, CHOP); a.short(0x75, 'eh_bane')
    a.b(0x80, 0xfb, E_SMITE); a.short(0x75, 'eh_two'); a.b(0x8b, 0xd0, 0xd1, 0xe0, 0x03, 0xc2); a.short(0xeb, 'eh_bane')   # three times (dx: 2DAB sets it again)
    a.label('eh_two')
    a.b(0xd1, 0xe0)
    a.label('eh_bane')
    a.near(0xe8, 'saber_mon')                                # D51: a lightsaber kills a monster at once
    a.b(0x0a, 0xdb); a.short(0x75, 'eh_target'); a.near(0xe9, 'eh_pop')
    a.label('eh_target')
    a.b(0x57, 0x8b, 0x7e, 0x0c)                              # push di / mov di, [bp+0Ch]   the struck: the caller's di as a rule
    for ret in (0x3776, 0x5215, 0x55bf):
        a.b(0x81, 0xf9, ret & 0xff, ret >> 8); a.short(0x75, f'eh_r{ret:x}'); a.b(0x8b, 0x7e, 0x10); a.short(0xeb, 'eh_who')
        a.label(f'eh_r{ret:x}')
    a.b(0x81, 0xf9, 0xd2, 0x56); a.short(0x75, 'eh_who'); a.b(0x8b, 0x3e, 0xe8, 0x77)
    a.label('eh_who')
    a.b(0x81, 0xff, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8); a.short(0x75, 'eh_mon')
    a.b(0x80, 0xfb, E_DRAGON); a.short(0x75, 'eh_none'); a.short(0xeb, 'eh_double')
    a.label('eh_mon')
    a.b(0x8a, 0x4d, 0x35)                                    # mov cl, [di+35h]   its type
    rules_ = ((E_TROGG, (AXE_TROGG, HAMMER_TROGG, SPEAR_TROGG), 'kill'), (E_RAT, (RATMAN, AXE_TROGG), 'kill'),
              (E_DESERT, (BALOK_TYPE, HAMMER_TROGG), 'double'), (E_SWAMP, (MUD_TYPE,), 'double'), (E_SWAMP, (TROLL_TYPE,), 'kill'))
    for n, (ench, types, what) in enumerate(rules_):
        a.b(0x80, 0xfb, ench); a.short(0x75, f'eh_x{n}')
        for t in types:
            a.b(0x80, 0xf9, t); a.short(0x74, f'eh_{what}')
        a.label(f'eh_x{n}')
    a.short(0xeb, 'eh_none')
    a.label('eh_double')
    a.b(0xd1, 0xe0); a.short(0xeb, 'eh_none')
    a.label('eh_kill')
    a.b(0xb8, ENCH_KILL & 0xff, ENCH_KILL >> 8)
    a.label('eh_none')
    a.b(0x5f)
    a.label('eh_pop')
    a.b(0x59, 0x5b); a.near(0xe9, 'rules_done')
    # fireblock (1000:43D1, mov word [si+28h],10h after mov ax,1Eh (custom rules: the dragon's damage): the dragon's
    # fire on the knight di): with Fireblock, while it blocks, no harm (on at 2D5E, the struck call's end, its
    # script as it was)
    a.label('rules_fireblock')
    a.b(0xc7, 0x44, 0x28, 0x10, 0x00)                        # (replaced)
    a.b(0x83, 0x7d, 0x28, KNIGHT_BLOCK); a.short(0x75, 'fb_end')
    a.b(0x56, 0x50, 0x8b, 0xf7); a.near(0xe8, 'ench_of'); a.b(0x3c, E_FIRE, 0x58, 0x5e); a.short(0x75, 'fb_end')
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d)
    a.label('fb_end')
    a.near(0xe9, 'rules_done')
    # gore_hitter ([bp] = the hitting animation (hit_pair)): ZF = 1 if its object is a knight with Gore
    a.label('gore_hitter')
    a.b(0x50, 0x56, 0x8b, 0x76, 0x00, 0x8b, 0x74, 0x16); a.near(0xe8, 'ench_of'); a.b(0x3c, E_GORE, 0x5e, 0x58, 0xc3)

    # --- D37: armour enchantments (as D35's for the swords) ---
    # arm_of (si = a knight): al = its armour's enchantment (0: none, a computer's knight, the rule off, another armour
    # than the one enchanted: then it is gone); keeps the rest
    a.label('arm_of')
    a.b(0x53, 0x52, 0x57, 0x8b, 0xfe, 0x32, 0xc0)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_ARM_ENCH); a.b(0x00); a.short(0x74, 'x37_ao_end')
    a.near(0xe8, 'knight_no'); a.short(0x72, 'x37_ao_end')
    a.b(0x83, 0x7c, 0x20, COMPUTER); a.short(0x74, 'x37_ao_end')
    a.b(0x2e, 0x8a, 0x87); a.word('arm_k'); a.b(0x0a, 0xc0); a.short(0x74, 'x37_ao_end')
    a.b(0x50, 0x2e, 0x8a, 0x87); a.word('arm_w'); a.b(0x3a, 0x44, 0x42, 0x58); a.short(0x74, 'x37_ao_end')   # the armour enchanted?
    a.b(0x2e, 0xc6, 0x87); a.word('arm_k'); a.b(0x00, 0x32, 0xc0)   # gone with it
    a.label('x37_ao_end')
    a.b(0x5f, 0x5a, 0x5b, 0xc3)
    # spell_safe: ZF = 1 if the knight whose turn it is ([77E8h]) has Spellproof
    a.label('spell_safe')
    a.b(0x50, 0x56, 0x8b, 0x36, 0xe8, 0x77); a.near(0xe8, 'arm_of'); a.b(0x3c, A_SPELL, 0x5e, 0x58, 0xc3)
    # arm_get (si = the chest's item table): al = its armour enchantment, 0 none; decided the first time (the chance %;
    # Venomproof only with the ratmen's disease on). Each holder's byte is 25 after its sword's (holder_slot)
    a.label('arm_get')
    a.b(0x53, 0x32, 0xc0)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_ARM_ENCH); a.b(0x00); a.short(0x74, 'x37_ag_end')
    a.near(0xe8, 'holder_slot'); a.short(0x72, 'x37_ag_end')
    a.b(0x83, 0xc3, LAIR_COUNT + 1)
    a.b(0x2e, 0x8a, 0x07, 0x0a, 0xc0); a.short(0x75, 'x37_ag_have')
    a.b(0x2e, 0xc6, 0x07, 0x01)                              # decided: none
    a.b(0x52, 0x51); a.near(0xe8, 'game_random'); a.b(0x33, 0xd2, 0xb9, 100, 0x00, 0xf7, 0xf1)
    a.b(0x2e, 0x3a, 0x16); a.word('rules_table', G_ARM_CHANCE); a.short(0x73, 'x37_ag_pop')
    a.near(0xe8, 'game_random'); a.b(0x33, 0xd2, 0xb9, len(ARM_NAMES), 0x00)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_DISEASE); a.b(0x00); a.short(0x75, 'x37_ag_div'); a.b(0x49)   # no disease: of the 8 others
    a.label('x37_ag_div')
    a.b(0xf7, 0xf1, 0x42)                                    # div cx / inc dx
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_DISEASE); a.b(0x00); a.short(0x75, 'x37_ag_set')
    a.b(0x83, 0xfa, A_VENOM); a.short(0x72, 'x37_ag_set'); a.b(0x42)
    a.label('x37_ag_set')
    a.b(0xfe, 0xc2, 0x2e, 0x88, 0x17)                        # inc dl / mov cs:[bx], dl   1 + it
    a.label('x37_ag_pop')
    a.b(0x59, 0x5a, 0x2e, 0x8a, 0x07)
    a.label('x37_ag_have')
    a.b(0xfe, 0xc8)
    a.label('x37_ag_end')
    a.b(0x5b, 0xc3)
    a.label('arm_name_put')                                  # al = an enchantment: its name (ench_put)
    a.b(0x56, 0x53, 0x32, 0xe4, 0x48, 0xd1, 0xe0, 0x8b, 0xd8, 0x2e, 0x8b, 0xb7); a.word('arm_names')
    a.near(0xe8, 'ench_put'); a.b(0x5b, 0x5e, 0xc3)
    # arm_desc (dx = the panel's descriptor window, cs:[arm_tp] = its text, al = the flags): as ench_desc
    a.label('arm_desc')
    a.b(0x50, 0x53, 0x51, 0x52, 0x57, 0x8a, 0xc8)
    a.b(0x8b, 0xc2, 0x2b, 0x06, 0xa8, 0xe4, 0x05, 0x09, 0x00, 0x52, 0x33, 0xd2, 0xbb, 0x0a, 0x00, 0xf7, 0xf3, 0x5a)
    a.b(0x8b, 0xd8, 0xd1, 0xe3, 0x89, 0x1e, 0xa4, 0xe4)
    a.b(0xbb, 0x0a, 0x00, 0x52, 0xf7, 0xe3, 0x5a, 0x03, 0x06, 0xa8, 0xe4, 0x8b, 0xf8)
    a.b(0x2e, 0x8b, 0x16); a.word('arm_tp'); a.b(0x89, 0x15, 0xc7, 0x45, 0x02, 0x00, 0x00, 0xc7, 0x45, 0x04, 0x03, 0x00)
    a.b(0x32, 0xed, 0x89, 0x4d, 0x06, 0xc7, 0x45, 0x08, 0x00, 0x00)
    a.b(0x5f, 0x5a, 0x59, 0x5b, 0x58, 0xc3)
    # arm_part: dx = the panel's window, di = cs:[arm_tp] = its text ([0E4AEh] 0: the first, else the second)
    a.label('arm_part')
    a.b(0xba, ARM_WINDOWS[0] & 0xff, ARM_WINDOWS[0] >> 8, 0xbf, ARM_TEXTS[0] & 0xff, ARM_TEXTS[0] >> 8)
    a.b(0x83, 0x3e, 0xae, 0xe4, 0x00); a.short(0x74, 'x37_ap_end')
    a.b(0xba, ARM_WINDOWS[1] & 0xff, ARM_WINDOWS[1] >> 8, 0xbf, ARM_TEXTS[1] & 0xff, ARM_TEXTS[1] >> 8)
    a.label('x37_ap_end')
    a.b(0x2e, 0x89, 0x3e); a.word('arm_tp'); a.b(0xc3)
    # arm_icon (1000:C8D7, mov si,6E26h after DisplayMSword): an armour enchantment in the chest or hoard: its icon (the
    # picture of the knight's own armour) where a knight's panel has the armour; PlaceIcons, then this site again
    a.label('rules_arm_icon')
    a.b(0x2e, 0x80, 0x3e); a.word('ai_back'); a.b(0x00); a.short(0x74, 'x37_ai_first')
    a.b(0x2e, 0xc6, 0x06); a.word('ai_back'); a.b(0x00); a.short(0xeb, 'x37_ai_end')
    a.label('x37_ai_first')
    a.b(0x50, 0x56, 0x8b, 0x36, 0x90, 0xe4); a.near(0xe8, 'arm_get'); a.b(0x0a, 0xc0); a.short(0x75, 'x37_ai_on')
    a.b(0x5e, 0x58)
    a.label('x37_ai_end')
    a.b(0xbe, 0x26, 0x6e); a.near(0xe9, 'rules_done')
    a.label('x37_ai_on')
    a.b(0x52, 0x57, 0x06, 0x1e, 0x07)
    a.b(0xba, ARM_WINDOWS[1] & 0xff, ARM_WINDOWS[1] >> 8, 0xbf, ARM_TEXTS[1] & 0xff, ARM_TEXTS[1] >> 8)
    a.b(0x2e, 0x89, 0x3e); a.word('arm_tp')
    a.b(0xbe); a.word('ench_text'); a.near(0xe8, 'ench_put'); a.near(0xe8, 'arm_name_put')
    a.b(0xc6, 0x05, 0x00, 0xb0, 0x23); a.near(0xe8, 'arm_desc')
    a.b(0x07, 0x5f, 0x5a)
    for addr, value in ((0xe49c, ARM_X), (0xe49e, ARM_Y), (0xe4a0, 0), (0xe4a2, 1), (0xe4a6, ARM_ITEM)):
        a.b(0xc7, 0x06, addr & 0xff, addr >> 8, value & 0xff, value >> 8)
    a.b(0x8b, 0x36, 0x88, 0xed, 0x8b, 0x74, 0x42, 0x89, 0x36, 0x9a, 0xe4)   # the picture: the knight's armour
    a.b(0x2e, 0xc6, 0x06); a.word('ai_back'); a.b(0x01)
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x5d, 0xcb)   # PlaceIcons (CB5D)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xd7, 0xc8)
    a.b(0xb9, 0x01, 0x00, 0x5e, 0x58); a.near(0xe9, 'call_game')
    # arm_name (1000:C54A, mov [0E4A4h],ax as the panel shows the armour): "<armour> of <enchantment>"
    a.label('rules_arm_name')
    a.b(0xa3, 0xa4, 0xe4, 0x50, 0x56, 0x8b, 0x36, 0x90, 0xe4); a.near(0xe8, 'arm_of'); a.b(0x0a, 0xc0); a.short(0x75, 'x37_an_on')
    a.b(0x5e, 0x58); a.near(0xe9, 'rules_done')
    a.label('x37_an_on')
    a.b(0x53, 0x52, 0x57, 0x06, 0x1e, 0x07, 0x50)
    a.near(0xe8, 'arm_part'); a.b(0x8b, 0x44, 0x42)          # mov ax, [si+42h]
    for value, name in ARMOUR_NAMES:
        a.b(0x3d, value, 0x00); a.short(0x75, f'an_n{value:x}'); a.b(0xbe); a.word(f'aname_{value:x}'); a.short(0xeb, 'x37_an_name')
        a.label(f'an_n{value:x}')
    a.b(0xbe); a.word('aname_1b')
    a.label('x37_an_name')
    a.near(0xe8, 'ench_put'); a.b(0xbe); a.word('ench_of_text'); a.near(0xe8, 'ench_put')
    a.b(0x58); a.near(0xe8, 'arm_name_put'); a.b(0xc6, 0x05, 0x00)
    a.b(0xa1, 0xa4, 0xe4, 0xd1, 0xe8, 0xbb, 0x0a, 0x00, 0x52, 0xf7, 0xe3, 0x5a, 0x03, 0x06, 0xa8, 0xe4, 0x8b, 0xd8)
    a.b(0x8a, 0x47, 0x06); a.near(0xe8, 'arm_desc')
    a.b(0x07, 0x5f, 0x5a, 0x5b, 0x5e, 0x58); a.near(0xe9, 'rules_done')
    # arm_take (from ench_take, bx = ARM_ITEM): onto the clicking knight's armour, replacing one it had
    a.label('arm_take')
    a.b(0xc7, 0x46, 0x02, 0xd5, 0xcd, 0x50, 0x52, 0x56, 0x57)
    a.near(0xe8, 'holder_slot'); a.short(0x72, 'x37_at_pop'); a.b(0x83, 0xc3, LAIR_COUNT + 1)
    a.b(0x2e, 0x8a, 0x07, 0x2c, 0x01); a.short(0x76, 'x37_at_pop')
    a.b(0x8b, 0x36, 0x88, 0xed, 0x83, 0x7c, 0x20, COMPUTER); a.short(0x74, 'x37_at_pop')
    a.b(0x53, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.short(0x72, 'x37_at_pop_bx')
    a.b(0x50); a.near(0xe8, 'arm_of'); a.b(0x8a, 0xd0, 0x58)  # dl = the old one
    a.b(0x2e, 0x88, 0x87); a.word('arm_k'); a.b(0x8a, 0x74, 0x42, 0x2e, 0x88, 0xb7); a.word('arm_w')
    a.b(0x3c, A_ADAMANT); a.short(0x75, 'x37_at_done'); a.b(0x80, 0xfa, A_ADAMANT); a.short(0x74, 'x37_at_done')
    a.b(0x83, 0x44, 0x38, 0x0a)                              # the 10 HP at once (CDC4 raises the maximum)
    a.label('x37_at_done')
    a.b(0x5b, 0x2e, 0xc6, 0x07, 0x01, 0xc7, 0x46, 0x02, 0xc4, 0xcd); a.short(0xeb, 'x37_at_pop')
    a.label('x37_at_pop_bx')
    a.b(0x5b)
    a.label('x37_at_pop')
    a.b(0x5f, 0x5e, 0x5a, 0x58); a.near(0xe9, 'rules_done')
    # arm_tkar (1000:CE5B, mov bp,[di+42h] in TKAR): as ench_tkwp: the enchantment goes with the armour taken
    a.label('rules_arm_tkar')
    a.b(0x50, 0x53, 0x52, 0x51, 0x8b, 0x45, 0x42, 0x89, 0x46, 0x00, 0x3d, 0x1b, 0x00); a.short(0x74, 'x37_ak_pop')
    a.b(0x56, 0x8b, 0xf7); a.near(0xe8, 'arm_of'); a.b(0x8a, 0xc8); a.near(0xe8, 'arm_clear'); a.b(0x5e)
    a.b(0x8b, 0x45, 0x42, 0x3b, 0x44, 0x42); a.short(0x7c, 'x37_ak_pop')
    a.near(0xe8, 'arm_clear')
    a.b(0x0a, 0xc9); a.short(0x74, 'x37_ak_pop'); a.b(0x83, 0x7c, 0x20, COMPUTER); a.short(0x74, 'x37_ak_pop')
    a.b(0x57, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.b(0x5f); a.short(0x72, 'x37_ak_pop')
    a.b(0x2e, 0x88, 0x8f); a.word('arm_k'); a.b(0x8a, 0x55, 0x42, 0x2e, 0x88, 0x97); a.word('arm_w')
    a.b(0x80, 0xf9, A_ADAMANT); a.short(0x75, 'x37_ak_pop'); a.b(0x83, 0x44, 0x38, 0x0a)
    a.label('x37_ak_pop')
    a.b(0x59, 0x5a, 0x5b, 0x58); a.near(0xe9, 'rules_done')
    a.label('arm_clear')                                     # si = a knight: its enchantment gone
    a.b(0x53, 0x52, 0x57, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.short(0x72, 'x37_ac_end')
    a.b(0x2e, 0xc6, 0x87); a.word('arm_k'); a.b(0x00)
    a.label('x37_ac_end')
    a.b(0x5f, 0x5a, 0x5b, 0xc3)
    # arm_reborn (from lives, si = a knight that lost a fight with Rebirth): no life lost, at Stonehenge, the armour plain
    a.label('arm_reborn')
    a.near(0xe8, 'arm_clear')
    for pos, value in ((0x5c, STONEHENGE_X), (0x5e, STONEHENGE_Y), (0x2a, STONEHENGE_X >> 3), (0x2c, STONEHENGE_Y >> 3)):
        a.b(0xc7, 0x44, pos, value & 0xff, value >> 8)
    a.near(0xe9, 'lives_end')
    # turn_move (1000:A6C4, mov al,[di+3Eh]): a turn's movement: endurance * 2 + 4 + the armour's value (Mithril: not
    # below 0), at least 1. Worked out here so that it is right after any change of armour or enchantment
    a.label('rules_turn_move')
    a.near(0xe8, 'horse_turn')                               # D38: a new turn starts on foot
    a.b(0x53, 0x33, 0xc0, 0x8a, 0x45, 0x30, 0xd1, 0xe0, 0x05, 0x04, 0x00)
    a.b(0x8b, 0x5d, 0x42, 0x83, 0xeb, 0x1b, 0x83, 0xfb, 0x03); a.short(0x77, 'x37_tv_min')
    a.b(0x2e, 0x8a, 0x9f); a.word('rules_table', G_ARMOUR_MOVE)
    a.b(0x56, 0x8b, 0xf7, 0x50); a.near(0xe8, 'arm_of'); a.b(0x3c, A_MITHRIL, 0x58, 0x5e); a.short(0x74, 'x37_tv_neg')
    a.b(0x50); a.near(0xe8, 'horse_of'); a.b(0x0a, 0xc0, 0x58); a.short(0x74, 'x37_tv_add')   # D38: mounted, as Mithril
    a.label('x37_tv_neg')
    a.b(0x0a, 0xdb); a.short(0x79, 'x37_tv_add'); a.b(0x32, 0xdb)
    a.label('x37_tv_add')
    a.b(0x93, 0x98, 0x03, 0xc3)                              # xchg ax, bx / cbw / add ax, bx
    a.label('x37_tv_min')
    a.b(0x50); a.near(0xe8, 'horse_of'); a.b(0x0a, 0xc0); a.short(0x74, 'x38_tv_none')   # D38: the horse's movement
    a.b(0x8a, 0xd8, 0x32, 0xff, 0x58, 0x2e, 0x8a, 0x9f); a.word('rules_table', G_HORSE_MOVE - 1)
    a.b(0x93, 0x98, 0x03, 0xc3); a.short(0xeb, 'x38_tv_clamp')
    a.label('x38_tv_none')
    a.b(0x58)
    a.label('x38_tv_clamp')
    a.b(0x3d, 0x01, 0x00); a.short(0x7d, 'x37_tv_end'); a.b(0xb8, 0x01, 0x00)
    a.label('x37_tv_end')
    a.b(0x32, 0xe4, 0x5b); a.near(0xe9, 'rules_done')
    # arm_danu (1000:A643, mov word [si+46h],0 where the next knight's turn begins): Danu: 10 HP, up to the maximum
    a.label('rules_arm_danu')
    a.b(0xc7, 0x44, 0x46, 0x00, 0x00, 0x50); a.near(0xe8, 'arm_of'); a.b(0x3c, A_DANU); a.short(0x75, 'x37_ad_end')
    a.b(0x80, 0x7c, 0x31, 0x00); a.short(0x7e, 'x37_ad_end'); a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'x37_ad_end')
    a.b(0x8b, 0x44, 0x38, 0x05, 0x0a, 0x00, 0x3b, 0x44, 0x3c); a.short(0x7e, 'x37_ad_set'); a.b(0x8b, 0x44, 0x3c)
    a.label('x37_ad_set')
    a.b(0x89, 0x44, 0x38)
    a.label('x37_ad_end')
    a.b(0x58); a.near(0xe9, 'rules_done')
    # arm_dragon (1000:A5F1, call A72D before the dragon's attack, call 0CF3): the knight with Wyrm is left alone
    a.label('rules_arm_dragon')
    a.b(0x50, 0x56, 0x8b, 0x36, 0xe8, 0x77); a.near(0xe8, 'arm_of'); a.b(0x3c, A_WYRM, 0x5e, 0x58); a.short(0x75, 'x37_ar_fight')
    a.b(0xc7, 0x46, 0x02, 0xfb, 0xa5); a.near(0xe9, 'rules_done')
    a.label('x37_ar_fight')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x2d, 0xa7)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xf4, 0xa5); a.near(0xe9, 'call_game')
    # arm_fire (1000:4405, mov cl,[bx+8], the talismans halving the dragon's damage on di): Fireproof counts as one more
    a.label('rules_arm_fire')
    a.b(0x8b, 0x5e, 0xfe, 0x8a, 0x4f, 0x08, 0x50, 0x56, 0x8b, 0xf7); a.near(0xe8, 'arm_of'); a.b(0x3c, A_FIRE, 0x5e, 0x58); a.short(0x75, 'x37_af_end')
    a.b(0xfe, 0xc1)
    a.label('x37_af_end')
    a.near(0xe9, 'rules_done')
    # arm_venom (1000:42A7, before the ratman's bite sets [di+60h]): Venomproof: no disease
    a.label('rules_arm_venom')
    a.b(0xc7, 0x06, 0x3a, 0x78, 0x48, 0x3a, 0x50, 0x56, 0x8b, 0xf7); a.near(0xe8, 'arm_of'); a.b(0x3c, A_VENOM, 0x5e, 0x58); a.short(0x75, 'x37_av_end')
    a.b(0xc7, 0x46, 0x02, 0xb1, 0x42)
    a.label('x37_av_end')
    a.near(0xe9, 'rules_done')
    # arm_target (1000:CB04, mov di,8979h as the item screen takes the next knight [bx+si] for a scroll): past a
    # Spellproof knight (unless every other one is)
    a.label('rules_arm_target')
    a.b(0x8b, 0x5e, 0xfe, 0x56, 0x8b, 0x30); a.near(0xe8, 'arm_of'); a.b(0x3c, A_SPELL, 0x5e); a.short(0x75, 'x37_atg_take')
    a.b(0x2e, 0xfe, 0x06); a.word('sp_tries'); a.b(0x2e, 0x80, 0x3e); a.word('sp_tries'); a.b(0x04); a.short(0x73, 'x37_atg_take')
    a.b(0xc7, 0x46, 0x02, 0xec, 0xca); a.near(0xe9, 'rules_done')
    a.label('x37_atg_take')
    a.b(0x2e, 0xc6, 0x06); a.word('sp_tries'); a.b(0x00, 0xbf, 0x79, 0x89); a.near(0xe9, 'rules_done')
    # arm_ai_wyrm, arm_ai_acq (1000:ADCC, ADF6, cmp word [si+46h],0 as a computer's knight would read a scroll at
    # its target): not at a Spellproof knight
    for name, out in (('wyrm', 0xadf1), ('acq', 0xae0e)):
        a.label(f'rules_arm_ai_{name}')
        a.b(0x50, 0x56, 0x8b, 0x74, 0x46, 0x0b, 0xf6); a.short(0x74, f'ai_{name}_no')
        a.near(0xe8, 'arm_of'); a.b(0x3c, A_SPELL); a.short(0x75, f'ai_{name}_no')
        a.b(0x5e, 0x58, 0xc7, 0x46, 0x02, out & 0xff, out >> 8); a.near(0xe9, 'rules_done')
        a.label(f'ai_{name}_no')
        a.b(0x5e, 0x58, 0x83, 0x7c, 0x46, 0x00); a.near(0xe9, 'rules_flags')
    # arm_hawk (1000:CD2E, call AB63, a cursed Hawk): Spellproof: a good one (CD23)
    a.label('rules_arm_hawk')
    a.near(0xe8, 'spell_safe'); a.short(0x75, 'x37_ah_curse')
    a.b(0xc7, 0x46, 0x02, 0x23, 0xcd); a.near(0xe9, 'rules_done')
    a.label('x37_ah_curse')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x63, 0xab)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x31, 0xcd); a.near(0xe9, 'call_game')
    # arm_prot (1000:CD71, mov word [0930h],1, a cursed Scroll of Protection): not with Spellproof
    a.label('rules_arm_prot')
    a.near(0xe8, 'spell_safe'); a.short(0x74, 'x37_apr_end')
    a.b(0xc7, 0x06, 0x30, 0x09, 0x01, 0x00)
    a.label('x37_apr_end')
    a.near(0xe9, 'rules_done')

    # --- D38: horses ---
    # horse_turn (di = the knight whose turn starts): it counts as standing where it is
    a.label('horse_turn')
    a.b(0x53, 0x8b, 0x5d, 0x5c, 0x2e, 0x89, 0x1e); a.word('horse_x')   # push bx / mov bx, [di+5Ch] / mov cs:[horse_x], bx
    a.b(0x8b, 0x5d, 0x5e, 0x2e, 0x89, 0x1e); a.word('horse_y')         # mov bx, [di+5Eh] / mov cs:[horse_y], bx
    a.b(0x2e, 0xc6, 0x06); a.word('horse_ride'); a.b(0x00, 0x5b, 0xc3)  # mov byte cs:[horse_ride], 0 / pop bx / ret
    # horse_riding (di = the knight drawn; keeps all but flags): CF = 1 while the horse shows: from its first step until it
    # has stood HORSE_IDLE ticks. The input is cleared just before the icon is drawn (A4CD), so its position tells
    a.label('horse_riding')
    a.b(0x53, 0x8b, 0x5d, 0x5c, 0x2e, 0x3b, 0x1e); a.word('horse_x'); a.short(0x75, 'x38_hr_moved')
    a.b(0x8b, 0x5d, 0x5e, 0x2e, 0x3b, 0x1e); a.word('horse_y'); a.short(0x75, 'x38_hr_moved')
    a.b(0x2e, 0x80, 0x3e); a.word('horse_ride'); a.b(0x00); a.short(0x74, 'x38_hr_no')
    a.b(0x06, 0x33, 0xdb, 0x8e, 0xc3, 0x26, 0x8b, 0x1e, 0x6c, 0x04, 0x07)   # bx = the BIOS tick
    a.b(0x2e, 0x2b, 0x1e); a.word('horse_tick'); a.b(0x83, 0xfb, HORSE_IDLE); a.short(0x72, 'x38_hr_yes')
    a.b(0x2e, 0xc6, 0x06); a.word('horse_ride'); a.b(0x00)
    a.label('x38_hr_no')
    a.b(0xf8, 0x5b, 0xc3)                                    # clc / pop bx / ret
    a.label('x38_hr_moved')
    a.b(0x8b, 0x5d, 0x5c, 0x2e, 0x89, 0x1e); a.word('horse_x')
    a.b(0x8b, 0x5d, 0x5e, 0x2e, 0x89, 0x1e); a.word('horse_y')
    a.b(0x06, 0x33, 0xdb, 0x8e, 0xc3, 0x26, 0x8b, 0x1e, 0x6c, 0x04, 0x07)   # bx = the BIOS tick
    a.b(0x2e, 0x89, 0x1e); a.word('horse_tick')
    a.b(0x2e, 0xc6, 0x06); a.word('horse_ride'); a.b(0x01)
    a.label('x38_hr_yes')
    a.b(0xf9, 0x5b, 0xc3)                                    # stc / pop bx / ret
    # horse_of (di = a knight): al = its horse (0: none, a computer's or the rule off); keeps the rest
    a.label('horse_of')
    a.b(0x53, 0x52, 0x2e, 0x80, 0x3e); a.word('rules_table', G_HORSES); a.b(0x00); a.short(0x74, 'x38_ho_no')
    a.near(0xe8, 'knight_no'); a.short(0x72, 'x38_ho_no')
    a.b(0x2e, 0x8a, 0x87); a.word('horse_k'); a.short(0xeb, 'x38_ho_end')
    a.label('x38_ho_no')
    a.b(0x32, 0xc0)
    a.label('x38_ho_end')
    a.b(0x5a, 0x5b, 0xc3)
    # gold5 (D41; 1000:C3BE item screen, B32B tavern, BDCB donation: call 7D7F, which makes only three digits): ax as up to five
    # digits at the game's bx, left-aligned, no leading zeros; bx = its end, as 7D7F
    a.label('rules_gold5')
    a.b(0x8b, 0x5e, 0xfe, 0xb9, 0x0a, 0x00, 0x33, 0xf6)
    a.label('x41_g_div')
    a.b(0x33, 0xd2, 0xf7, 0xf1, 0x52, 0x46, 0x0b, 0xc0); a.short(0x75, 'x41_g_div')
    a.label('x41_g_put')
    a.b(0x58, 0x04, 0x30, 0x88, 0x07, 0x43, 0x4e); a.short(0x75, 'x41_g_put')
    a.b(0xc6, 0x07, 0x00, 0x89, 0x5e, 0xfe); a.near(0xe9, 'rules_done')
    # visit_tavern, visit_merchant (D43; the town's calls of B1E0 and BFAC): the knight's gold is noted, the visit runs and comes back to
    # this site; if the gold grew and is above max_gold, it comes down (gold that was there before, a cheat's, is left alone)
    a.label('rules_visit_tavern')
    a.b(0xbb, 0xe0, 0xb1); a.near(0xe9, 'gold_visit')
    a.label('rules_visit_merchant')
    a.b(0xbb, 0xac, 0xbf)
    a.label('gold_visit')
    a.b(0x2e, 0x80, 0x3e); a.word('gv_flag'); a.b(0x00); a.short(0x75, 'x43_gv_back')
    a.b(0x2e, 0xc6, 0x06); a.word('gv_flag'); a.b(0x01, 0x2e, 0x89, 0x1e); a.word('call_target')
    a.b(0x50, 0x56, 0x8b, 0x36, 0xe8, 0x77, 0x8b, 0x44, 0x32, 0x2e, 0xa3); a.word('gv_start')
    a.b(0x5e, 0x8b, 0x46, 0x02, 0x2d, 0x02, 0x00, 0x2e, 0xa3); a.word('call_ret'); a.b(0x58); a.near(0xe9, 'call_game')
    a.label('x43_gv_back')
    a.b(0x2e, 0xc6, 0x06); a.word('gv_flag'); a.b(0x00, 0x50, 0x56, 0x8b, 0x36, 0xe8, 0x77, 0x8b, 0x44, 0x32)
    a.b(0x2e, 0x3b, 0x06); a.word('gv_start'); a.short(0x7e, 'x43_gv_end')
    a.b(0x2e, 0x3b, 0x06); a.word('rules_table', G_MAX_GOLD); a.short(0x7e, 'x43_gv_end')
    a.b(0x2e, 0xa1); a.word('rules_table', G_MAX_GOLD); a.b(0x89, 0x44, 0x32)
    a.label('x43_gv_end')
    a.b(0x5e, 0x58); a.near(0xe9, 'rules_done')
    # gold999 (D41; 1000:B491, B4E3, mov ax,[si+32h] for the dice result's line): only the number shown stops at 999
    a.label('rules_gold999')
    a.b(0x8b, 0x44, 0x32, 0x3d, 0xe7, 0x03); a.short(0x7e, 'x41_g9_end'); a.b(0xb8, 0xe7, 0x03)
    a.label('x41_g9_end')
    a.near(0xe9, 'rules_done')
    # gold_add (D41; 1000:0BBE, add [si+32h],ax: the winner of a duel, the game's only uncapped gain): stops at 32767
    a.label('rules_gold_add')
    a.b(0x01, 0x44, 0x32); a.short(0x71, 'x41_ga_end'); a.b(0xc7, 0x44, 0x32, 0xff, 0x7f)
    a.label('x41_ga_end')
    a.near(0xe9, 'rules_done')
    # horse_roll: slot 4 for this stay in town (1 empty, 4 or 5 a horse); keeps the registers
    a.label('horse_roll')
    a.b(0x50, 0x51)
    a.near(0xe8, 'game_random'); a.b(0x32, 0xe4, 0xb1, 0x64, 0xf6, 0xe1)   # xor ah, ah / mov cl, 100 / mul cl: ah = 0-99
    a.b(0xb0, 0x01, 0x2e, 0x3a, 0x26); a.word('rules_table', G_HORSE_CHANCE); a.short(0x73, 'x38_hi_store')
    a.near(0xe8, 'game_random'); a.near(0xe8, 'game_random')   # the second call: the first follows the roll too closely for an even split
    a.b(0x24, 0x01, 0x04, 0x04)                              # and al, 1 / add al, 4
    a.label('x38_hi_store')
    a.b(0x2e, 0xa2); a.word('horse_s'); a.b(0x59, 0x58, 0xc3)
    # horse_town_w, _h (D40; 1000:0D59 WaterDeep, 1000:0E14 HighWood: the call before the town's loop, which the shops come
    # back into below it): the roll, kept in this program's memory and so in a save, then the replaced call
    a.label('rules_horse_town_w')
    a.near(0xe8, 'horse_roll')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xf9, 0x8f)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x5c, 0x0d); a.near(0xe9, 'call_game')
    a.label('rules_horse_town_h')
    a.near(0xe8, 'horse_roll')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe2, 0x8f)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x17, 0x0e); a.near(0xe9, 'call_game')
    # horse_panel (D40; 1000:C55C, DisplayKnight's mov si,[0E490h] after the armour): the first panel's horse as an icon of
    # field 36h, type 2 (rules_sell takes the click). PlaceIcons, then this site again
    a.label('rules_horse_panel')
    a.b(0x2e, 0x80, 0x3e); a.word('hp_back'); a.b(0x00); a.short(0x74, 'x40_hp_first')
    a.b(0x2e, 0xc6, 0x06); a.word('hp_back'); a.b(0x00)
    a.label('x40_hp_end')
    a.b(0x8b, 0x36, 0x90, 0xe4); a.near(0xe9, 'rules_done')
    a.label('x40_hp_first')
    a.b(0x83, 0x3e, 0x98, 0xe4, 0x00); a.short(0x75, 'x40_hp_end')
    a.b(0x8b, 0x3e, 0x90, 0xe4); a.near(0xe8, 'horse_of'); a.b(0x0a, 0xc0); a.short(0x74, 'x40_hp_end')
    a.b(0x8a, 0xd8, 0x32, 0xff, 0xfe, 0xc8, 0xb1, HORSE_TEXT_SIZE, 0xf6, 0xe1, 0x05); a.word('rules_table', G_HORSE_SELL); a.b(0x8b, 0xf0)   # bx = the horse, si = its text
    a.b(0xbf, HORSE_PANEL_TEXT & 0xff, HORSE_PANEL_TEXT >> 8, 0x2e, 0x89, 0x3e); a.word('arm_tp')
    a.b(0xb2, 0x01, 0x83, 0x3e, 0x92, 0xed, 0x05); a.short(0x75, 'x40_hp_plain')   # dl = 1: the whole text, at the merchant if it buys
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_SELLING); a.b(0x00); a.short(0x75, 'x40_hp_copy')
    a.label('x40_hp_plain')
    a.b(0xb2, 0x00, 0x83, 0xc6, 0x05)                        # only the name: after "Sell ", up to " for"
    a.label('x40_hp_copy')
    a.b(0x06, 0x1e, 0x07, 0x1e, 0x0e, 0x1f, 0xfc)            # es = MAIN's data, ds = here
    a.label('x40_hp_loop')
    a.b(0xac, 0x0a, 0xc0); a.short(0x74, 'x40_hp_stop'); a.b(0x0a, 0xd2); a.short(0x75, 'x40_hp_put')
    a.b(0x3c, 0x20); a.short(0x75, 'x40_hp_put'); a.b(0x80, 0x3c, 0x66); a.short(0x74, 'x40_hp_stop')
    a.label('x40_hp_put')
    a.b(0xaa); a.short(0xeb, 'x40_hp_loop')
    a.label('x40_hp_stop')
    a.b(0x32, 0xc0, 0xaa, 0x1f, 0x07)
    a.b(0xba, HORSE_PANEL_WINDOW & 0xff, HORSE_PANEL_WINDOW >> 8, 0xb0, 0x23); a.near(0xe8, 'arm_desc')
    a.b(0x8a, 0xc3, 0x32, 0xe4, 0x05, HORSE_FRAME_SHOP - 1, 0x00, 0xa3, 0x9a, 0xe4)
    for addr, value in ((0xe49c, HORSE_PANEL_X), (0xe49e, HORSE_PANEL_Y), (0xe4a0, 0), (0xe4a2, 2), (0xe4a6, HORSE_FIELD)):
        a.b(0xc7, 0x06, addr & 0xff, addr >> 8, value & 0xff, value >> 8)
    a.b(0x2e, 0xc6, 0x06); a.word('hp_back'); a.b(0x01)
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x5d, 0xcb)   # PlaceIcons
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x5c, 0xc5)
    a.b(0xb9, 0x01, 0x00); a.near(0xe9, 'call_game')
    # horse_icons (1000:CA76, mov cx,0Dh in DisplayMerchant): the horse slots, one PlaceIcons per pass, then this site again
    a.label('rules_horse_icons')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_HORSES); a.b(0x00); a.short(0x75, 'x38_hi_on'); a.near(0xe9, 'x38_hi_end')
    a.label('x38_hi_on')
    a.b(0x2e, 0x8a, 0x1e); a.word('hi_state'); a.b(0x80, 0xfb, 0x04); a.short(0x72, 'x38_hi_go'); a.near(0xe9, 'x38_hi_reset')
    a.label('x38_hi_go')
    a.b(0x2e, 0x80, 0x3e); a.word('horse_s'); a.b(0x00); a.short(0x75, 'x38_hi_rolled')
    a.near(0xe8, 'horse_roll')
    a.label('x38_hi_rolled')
    a.b(0x32, 0xff, 0x8a, 0xc3, 0xfe, 0xc0, 0x80, 0xfb, 0x03); a.short(0x75, 'x38_hi_place')   # xor bh, bh / al = slot + 1
    a.b(0x2e, 0xa0); a.word('horse_s'); a.b(0x3c, 0x04); a.short(0x73, 'x38_hi_place'); a.near(0xe9, 'x38_hi_reset')
    a.label('x38_hi_place')
    a.b(0x50, 0x8a, 0xd0, 0xfe, 0xca, 0xb0, HORSE_TEXT_SIZE, 0xf6, 0xe2, 0x05); a.word('rules_table', G_HORSE_TEXT); a.b(0x8b, 0xf0)   # si = this horse's text
    a.b(0x8a, 0xc3, 0xb2, HORSE_TEXT_SIZE, 0xf6, 0xe2, 0x05, (HORSE_AREA + 4 * HORSE_WINDOW) & 0xff, (HORSE_AREA + 4 * HORSE_WINDOW) >> 8, 0x8b, 0xf8)   # di = this slot's text
    a.b(0x2e, 0x89, 0x3e); a.word('arm_tp')
    a.b(0x06, 0x1e, 0x07, 0x1e, 0x0e, 0x1f, 0xb9, HORSE_TEXT_SIZE, 0x00, 0xfc, 0xf3, 0xa4, 0x1f, 0x07)   # the text into MAIN's data
    a.b(0x8a, 0xc3, 0xb2, HORSE_WINDOW, 0xf6, 0xe2, 0x05, HORSE_AREA & 0xff, HORSE_AREA >> 8, 0x8b, 0xd0, 0xb0, 0x23); a.near(0xe8, 'arm_desc')
    a.b(0x58, 0x32, 0xe4, 0xb1, 0x04, 0x8a, 0xd0, 0xd2, 0xe2, 0x80, 0xca, 0x0a, 0x32, 0xf6, 0x89, 0x16, 0xa2, 0xe4)   # [0E4A2h] = horse << 4 | 0Ah: a purchase of dx = the horse
    a.b(0x05, HORSE_FRAME_SHOP - 1, 0x00, 0xa3, 0x9a, 0xe4)
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('hi_x'); a.b(0xa3, 0x9c, 0xe4)
    for addr, value in ((0xe49e, HORSE_ICON_Y), (0xe4a0, 0), (0xe4a6, HORSE_FIELD)):
        a.b(0xc7, 0x06, addr & 0xff, addr >> 8, value & 0xff, value >> 8)
    a.b(0x2e, 0xfe, 0x06); a.word('hi_state')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x5d, 0xcb)   # PlaceIcons
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x76, 0xca)
    a.b(0xb9, 0x01, 0x00); a.near(0xe9, 'call_game')
    a.label('x38_hi_reset')
    a.b(0x2e, 0xc6, 0x06); a.word('hi_state'); a.b(0x00)
    a.label('x38_hi_end')
    a.b(0xb9, 0x0d, 0x00); a.near(0xe9, 'rules_done')
    a.label('hi_x')
    for x in HORSE_X: a.b(x & 0xff, x >> 8)
    # horse_buy (1000:CF0C, BuyGoods' mov si,[0ED88h]): the horses' field: dx = the horse. Not the one it has; no money back
    a.label('rules_horse_buy')
    a.b(0x8b, 0x36, 0x88, 0xed, 0x83, 0x7e, 0xfe, HORSE_FIELD); a.short(0x75, 'x42_goods'); a.near(0xe9, 'x38_hb_horse')
    a.label('x42_goods')
    # D40: a worse sword or armour than the knight's own is free in exchange (the Sword of Sharpness stays); else as before
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TRADE_IN); a.b(0x00); a.short(0x75, 'x40_tr_on')
    a.label('x40_tr_end')
    a.near(0xe9, 'rules_done')
    a.label('x40_tr_on')
    a.b(0x8b, 0x5e, 0xfe, 0x83, 0xfb, 0x40); a.short(0x74, 'x40_tr_sword'); a.b(0x83, 0xfb, 0x42); a.short(0x75, 'x40_tr_end')
    a.b(0x8b, 0xca, 0x80, 0xf9, 0x04); a.short(0x75, 'x40_tr_a3'); a.b(0xb1, 0x03)   # cx = the armour bought: 1, 2, 4 mean 1Ch, 1Dh, 1Eh
    a.label('x40_tr_a3')
    a.b(0x83, 0xc1, 0x1b, 0x8b, 0x44, 0x42, 0x3b, 0xc1); a.short(0x77, 'x40_tr_arm'); a.short(0x74, 'x40_tr_end')
    # D42: a better armour than chain or plate: half of the old one's price is credited (padded: the game buys it)
    a.b(0x3d, 0x1b, 0x00); a.short(0x74, 'x40_tr_end')
    a.b(0x2d, 0x1c, 0x00, 0xd1, 0xe0, 0x05, 0x06, 0x00, 0x8b, 0xd8, 0x8b, 0xc1, 0x2d, 0x1c, 0x00, 0xd1, 0xe0, 0x05, 0x06, 0x00)
    a.near(0xe8, 'x42_pay'); a.short(0x73, 'x42_a_ok'); a.near(0xe9, 'x38_hb_no')
    a.label('x42_a_ok')
    a.b(0x8b, 0xd9, 0x83, 0xeb, 0x1b, 0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('rules_table', G_ARMOUR_HP); a.b(0x01, 0x44, 0x38)   # its hit points, as the game adds them
    a.b(0x89, 0x4c, 0x42); a.near(0xe9, 'x40_tr_done')
    a.label('x40_tr_arm')
    a.b(0x2d, 0x1b, 0x00, 0xd1, 0xe0, 0x8b, 0xd8, 0x2e, 0x8b, 0x87); a.word('rules_table', G_ARMOUR_HP); a.b(0x29, 0x44, 0x38)   # its hit points go
    a.b(0x8b, 0xd9, 0x83, 0xeb, 0x1b, 0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('rules_table', G_ARMOUR_HP); a.b(0x01, 0x44, 0x38)   # the new one's come
    a.b(0x83, 0x7c, 0x38, 0x01); a.short(0x7d, 'x40_tr_hp'); a.b(0xc7, 0x44, 0x38, 0x01, 0x00)
    a.label('x40_tr_hp')
    a.b(0x89, 0x4c, 0x42); a.near(0xe9, 'x40_tr_done')
    a.label('x40_tr_sword')
    a.b(0x8b, 0x44, 0x40, 0x3d, 0x19, 0x00); a.short(0x75, 'x42_s_on'); a.near(0xe9, 'x38_hb_no')
    a.label('x42_s_on')
    a.b(0x8b, 0xca, 0x83, 0xc1, 0x16, 0x3b, 0xc1); a.short(0x77, 'x42_s_free'); a.short(0x74, 'x42_end')
    a.b(0x3d, 0x16, 0x00); a.short(0x74, 'x42_end')          # D42: a better sword: the credit (the long sword: the game buys it)
    a.b(0x2d, 0x17, 0x00, 0xd1, 0xe0, 0x05, 0x02, 0x00, 0x8b, 0xd8, 0x8b, 0xc1, 0x2d, 0x17, 0x00, 0xd1, 0xe0, 0x05, 0x02, 0x00)
    a.near(0xe8, 'x42_pay'); a.short(0x73, 'x42_s_free'); a.near(0xe9, 'x38_hb_no')
    a.label('x42_end')
    a.near(0xe9, 'rules_done')
    # x42_pay: bx, ax = the old and the new item's offset in the price tables: pays the price less half the old one's. CF = 1: too little gold
    a.label('x42_pay')
    a.b(0x8b, 0xf8, 0x2e, 0x8b, 0x87); a.word('rules_table', G_SELL); a.b(0x2e, 0x8b, 0x95); a.word('rules_table', G_BUY)
    a.b(0x2b, 0xd0); a.short(0x73, 'x42_p_net'); a.b(0x33, 0xd2)
    a.label('x42_p_net')
    a.b(0x39, 0x54, 0x32); a.short(0x7c, 'x42_p_no'); a.b(0x29, 0x54, 0x32, 0xf8, 0xc3)
    a.label('x42_p_no')
    a.b(0xf9, 0xc3)
    a.label('x42_s_free')
    a.b(0x89, 0x4c, 0x40)
    a.label('x40_tr_done')
    a.b(0xc7, 0x46, 0x02, 0x3c, 0xcf); a.short(0xeb, 'x38_hb_end')   # on as a purchase ends
    a.label('x38_hb_horse')
    a.b(0x8a, 0xc2, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.short(0x72, 'x38_hb_no')
    a.b(0x2e, 0x3a, 0x87); a.word('horse_k'); a.short(0x74, 'x38_hb_no')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TRADE_IN); a.b(0x00); a.short(0x74, 'x38_hb_pay')
    a.b(0x2e, 0x8a, 0xa7); a.word('horse_k'); a.b(0x80, 0xfc, 0x04); a.short(0x76, 'x40_hb_rank'); a.b(0xb4, 0x04)   # a better horse (4 and 5 alike): free
    a.label('x40_hb_rank')
    a.b(0x3a, 0xe0); a.short(0x77, 'x40_hb_free')
    a.label('x38_hb_pay')
    a.b(0x8b, 0xcb, 0x32, 0xe4, 0x8b, 0xd8, 0xd1, 0xe3, 0x2e, 0x8b, 0x97); a.word('rules_table', G_HORSE_PRICE - 2)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TRADE_IN); a.b(0x00); a.short(0x74, 'x42_h_check')   # D42: half of the old horse's price
    a.b(0x8b, 0xd9, 0x2e, 0x8a, 0x9f); a.word('horse_k'); a.b(0x32, 0xff, 0x0a, 0xdb); a.short(0x74, 'x42_h_check')
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x9f); a.word('rules_table', G_HORSE_PRICE - 2); a.b(0xd1, 0xeb, 0x2b, 0xd3); a.short(0x73, 'x42_h_check'); a.b(0x33, 0xd2)
    a.label('x42_h_check')
    a.b(0x39, 0x54, 0x32); a.short(0x7c, 'x38_hb_no'); a.b(0x29, 0x54, 0x32, 0x8b, 0xd9)
    a.label('x40_hb_free')
    a.b(0x2e, 0x88, 0x87); a.word('horse_k')
    a.b(0xc7, 0x46, 0x02, 0x3c, 0xcf); a.short(0xeb, 'x38_hb_end')   # on as a purchase ends
    a.label('x38_hb_no')
    a.b(0xc7, 0x46, 0x02, 0x8b, 0xcf)                        # the ret
    a.label('x38_hb_end')
    a.near(0xe9, 'rules_done')
    # horse_terrain (1000:A918, mov si,0C42Ah): with a horse the cell lets through the horse's share of the steps, in eighths
    a.label('rules_horse_terrain')
    a.b(0x57, 0x8b, 0x3e, 0xe8, 0x77); a.near(0xe8, 'horse_of'); a.b(0x5f, 0x0a, 0xc0); a.short(0x75, 'x38_ht_on')
    a.b(0xbe, 0x2a, 0xc4); a.near(0xe9, 'rules_done')
    a.label('x38_ht_on')
    a.b(0x8b, 0x5e, 0xfe, 0x32, 0xe4, 0x8b, 0xf0, 0x8a, 0x87, 0x2a, 0xc4, 0x0a, 0xc0); a.short(0x74, 'x38_ht_ret')
    a.b(0xff, 0x06, 0x4a, 0xcd, 0x8a, 0x1e, 0x4a, 0xcd, 0x80, 0xe3, 0x07, 0x3c, 0x03); a.short(0x74, 'x38_ht_hard')
    a.b(0x2e, 0x8a, 0x94); a.word('rules_table', G_HORSE_SOFT - 1); a.short(0xeb, 'x38_ht_rate')
    a.label('x38_ht_hard')
    a.b(0x2e, 0x8a, 0x94); a.word('rules_table', G_HORSE_HARD - 1)
    a.label('x38_ht_rate')
    a.b(0x8a, 0xc3, 0xf6, 0xe2, 0x24, 0x07, 0x02, 0xc2, 0x3c, 0x08); a.short(0x73, 'x38_ht_ret')   # (step * share) & 7 + share >= 8: it moves
    a.b(0xc7, 0x06, 0x4c, 0xcd, 0x01, 0x00)
    a.label('x38_ht_ret')
    a.b(0xc7, 0x46, 0x02, 0x34, 0xa9); a.near(0xe9, 'rules_done')

    # knight_reset (si = a knight being set up for a new game): its sword's and armour's enchantments and its
    # horse cleared; for knight 1 the chests' enchantments too
    a.label('knight_reset')
    a.b(0x53, 0x52, 0x57, 0x8b, 0xfe); a.near(0xe8, 'knight_no'); a.short(0x72, 'ddr_end')   # push bx dx di / mov di, si / call knight_no / jc
    a.b(0x2e, 0xc6, 0x87); a.word('ench_k'); a.b(0x00)    # D35: its sword's enchantment
    a.b(0x2e, 0xc6, 0x87); a.word('arm_k'); a.b(0x00)     # D37: its armour's
    a.b(0x2e, 0xc6, 0x87); a.word('horse_k'); a.b(0x00)   # D38: its horse
    a.b(0x0b, 0xdb); a.short(0x75, 'ddr_end')                # knight 1: the chests' too
    a.b(0x50, 0x51, 0x57, 0x06, 0x0e, 0x07, 0xbf); a.word('lair_ench'); a.b(0xb9, 2 * (LAIR_COUNT + 1), 0x00, 0x32, 0xc0, 0xfc, 0xf3, 0xaa, 0x07, 0x5f, 0x59, 0x58)
    a.label('ddr_end')
    a.b(0x5f, 0x5a, 0x5b, 0xc3)

    # ilog_put (input_log on; al = kind, ah = knight or scan code, cl, ch = its two values): one entry, the BIOS tick
    # first, into the fight's log; keeps all registers. Also from the keyboard interrupt
    a.label('ilog_put')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_INPUT_LOG); a.b(0x00)   # cmp byte cs:[input_log], 0
    a.short(0x75, 'ilp_on'); a.b(0xc3)                       # jne / ret
    a.label('ilp_on')
    a.b(0x53, 0x52, 0x9c, 0xfa)                              # push bx dx / pushf / cli
    a.b(0x2e, 0x8b, 0x1e); a.word('ilog_n')                  # mov bx, cs:[ilog_n]
    a.b(0x81, 0xfb, ILOG_MAX & 0xff, ILOG_MAX >> 8); a.short(0x72, 'ilp_room')   # cmp bx, ILOG_MAX / jb
    a.b(0x2e, 0xff, 0x06); a.word('ilog_lost'); a.short(0xeb, 'ilp_end')   # inc word cs:[ilog_lost] / jmp
    a.label('ilp_room')
    a.b(0x2e, 0xff, 0x06); a.word('ilog_n')                  # inc word cs:[ilog_n]
    a.b(0x50, 0x8b, 0xc3, 0xd1, 0xe3, 0x03, 0xd8, 0xd1, 0xe3)   # push ax / mov ax, bx / shl bx, 1 / add bx, ax / shl bx, 1   * 6
    a.b(0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0x8b, 0x16, 0x6c, 0x04, 0x1f, 0x58)   # push ds / xor ax,ax / mov ds,ax / mov dx,[046Ch] / pop ds / pop ax
    a.b(0x2e, 0x89, 0x97); a.word('ilog')                    # mov cs:[bx+ilog], dx
    a.b(0x2e, 0x89, 0x87); a.word('ilog', 2)                 # mov cs:[bx+ilog+2], ax
    a.b(0x2e, 0x89, 0x8f); a.word('ilog', 4)                 # mov cs:[bx+ilog+4], cx
    a.label('ilp_end')
    a.b(0x9d, 0x5a, 0x5b, 0xc3)                              # popf / pop dx bx / ret
    # log_knight (al = kind, cl, ch, di = a knight): ilog_put with the knight's number (FFh for another object)
    a.label('log_knight')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_INPUT_LOG); a.b(0x00)
    a.short(0x75, 'lk_on'); a.b(0xc3)
    a.label('lk_on')
    a.b(0x50, 0x53, 0x52)                                    # push ax bx dx
    a.near(0xe8, 'knight_no'); a.short(0x73, 'lk_put'); a.b(0xb3, 0xff)   # call knight_no / jnc / mov bl, FFh
    a.label('lk_put')
    a.b(0x8a, 0xe3); a.near(0xe8, 'ilog_put')                # mov ah, bl / call ilog_put
    a.b(0x5a, 0x5b, 0x58, 0xc3)                              # pop dx bx ax / ret
    # log_read (al = kind, cl = the bits as read, ch = as used, di = the knight): only when they changed for it
    a.label('log_read')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_INPUT_LOG); a.b(0x00)
    a.short(0x75, 'lr_on'); a.b(0xc3)
    a.label('lr_on')
    a.b(0x53, 0x52, 0x50)                                    # push bx dx ax
    a.near(0xe8, 'knight_no'); a.short(0x72, 'lr_end')       # call knight_no / jc
    a.b(0xd1, 0xe3, 0x2e, 0x3b, 0x8f); a.word('last_read'); a.short(0x74, 'lr_end')   # shl bx,1 / cmp cx, cs:[bx+last_read] / je
    a.b(0x2e, 0x89, 0x8f); a.word('last_read'); a.b(0xd1, 0xeb)   # mov cs:[bx+last_read], cx / shr bx,1
    a.b(0x8a, 0xe3); a.near(0xe8, 'ilog_put')                # mov ah, bl / call ilog_put
    a.label('lr_end')
    a.b(0x58, 0x5a, 0x5b, 0xc3)                              # pop ax dx bx / ret
    # ilog_dump (fight end, DS = CS): the fight's entries appended to C:\INPUT.LOG after a 6-byte header ('IL',
    # entries, entries lost); clobbers ax bx cx dx
    a.label('ilog_dump')
    a.b(0x80, 0x3e); a.word('rules_table', G_INPUT_LOG); a.b(0x00); a.short(0x75, 'ild_on'); a.b(0xc3)
    a.label('ild_on')
    a.b(0x83, 0x3e); a.word('ilog_n'); a.b(0x00); a.short(0x75, 'ild_go'); a.b(0xc3)   # cmp word [ilog_n], 0 / jne / ret
    a.label('ild_go')
    a.b(0xb8, 0x01, 0x3d, 0xba); a.word('ilog_path'); a.b(0xcd, 0x21)   # mov ax, 3D01h / mov dx, ilog_path / int 21h
    a.short(0x73, 'ild_open')
    a.b(0xb4, 0x3c, 0x33, 0xc9, 0xcd, 0x21); a.short(0x72, 'ild_end')   # mov ah, 3Ch / xor cx, cx / int 21h / jc
    a.label('ild_open')
    a.b(0x8b, 0xd8, 0xb8, 0x02, 0x42, 0x33, 0xc9, 0x33, 0xd2, 0xcd, 0x21)   # mov bx, ax / mov ax, 4202h / xor cx,cx / xor dx,dx / int 21h
    a.b(0xb4, 0x40, 0xb9, 0x06, 0x00, 0xba); a.word('ilog_hdr'); a.b(0xcd, 0x21)   # header
    a.b(0xa1); a.word('ilog_n'); a.b(0x8b, 0xc8, 0xd1, 0xe1, 0x03, 0xc8, 0xd1, 0xe1)   # mov ax, [ilog_n] / mov cx, ax / shl cx,1 / add cx,ax / shl cx,1
    a.b(0xb4, 0x40, 0xba); a.word('ilog'); a.b(0xcd, 0x21)   # mov ah, 40h / mov dx, ilog / int 21h
    a.b(0xb4, 0x3e, 0xcd, 0x21)                              # close
    a.label('ild_end')
    a.b(0xc7, 0x06); a.word('ilog_n'); a.b(0x00, 0x00)
    a.b(0xc7, 0x06); a.word('ilog_lost'); a.b(0x00, 0x00, 0xc3)

    # key_settle (from key_check, ds any): releases kept back longer than KEY_HOLD ticks go into the key table
    a.label('key_settle')
    a.b(0x2e, 0x80, 0x3e); a.word('key_pending_any'); a.b(0x00)   # cmp byte cs:[key_pending_any], 0
    a.short(0x75, 'ks_go'); a.b(0xc3)                        # jne ks_go / ret
    a.label('ks_go')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x1e, 0x9c, 0xfa)      # push ax bx cx dx si ds / pushf / cli
    a.b(0x8e, 0x5e, 0x04)                                    # mov ds, [bp+4]     MAIN's code segment (int 63h frame)
    a.b(0x06, 0x33, 0xf6, 0x8e, 0xc6, 0x26, 0x8b, 0x16, 0x6c, 0x04, 0x07)   # push es / xor si,si / mov es,si / mov dx,es:[046Ch] / pop es
    a.b(0x2e, 0xc6, 0x06); a.word('key_pending_any'); a.b(0x00)   # mov byte cs:[key_pending_any], 0
    a.b(0x33, 0xdb, 0xb9, 0x80, 0x00)                        # xor bx, bx / mov cx, 128
    a.label('ks_loop')
    a.b(0x2e, 0x80, 0xbf); a.word('key_pending'); a.b(0x00)  # cmp byte cs:[bx+key_pending], 0
    a.short(0x74, 'ks_next')                                 # je ks_next
    a.b(0x8b, 0xf3, 0xd1, 0xe6)                              # mov si, bx / shl si, 1
    a.b(0x8b, 0xc2, 0x2e, 0x2b, 0x84); a.word('key_tick')    # mov ax, dx / sub ax, cs:[si+key_tick]
    a.b(0x3d, KEY_HOLD, 0x00); a.short(0x72, 'ks_wait')      # cmp ax, KEY_HOLD / jb ks_wait
    a.b(0xc6, 0x87, KEY_TABLE & 0xff, KEY_TABLE >> 8, 0xff)  # mov byte [bx+81E3h], 0FFh   released now
    a.b(0x2e, 0xc6, 0x87); a.word('key_pending'); a.b(0x00)  # mov byte cs:[bx+key_pending], 0
    a.short(0xeb, 'ks_next')                                 # jmp ks_next
    a.label('ks_wait')
    a.b(0x2e, 0xc6, 0x06); a.word('key_pending_any'); a.b(0x01)   # mov byte cs:[key_pending_any], 1
    a.label('ks_next')
    a.b(0x43, 0xe2); a.b(0x00); ks_loop_at = len(a.code) - 1     # inc bx / loop ks_loop
    a.code[ks_loop_at] = (a.labels['ks_loop'] - (a.org + ks_loop_at + 1)) & 0xff
    a.b(0x9d, 0x1f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)      # popf / pop ds si dx cx bx ax / ret

    # key_check (1000:828B, replaces cmp byte cs:[bx+81E3h],0FFh in the game's key test, bx = scan code): first
    # the releases due, then the test as the game's
    a.label('rules_key_check')
    a.near(0xe8, 'key_settle')                               # call key_settle
    a.b(0x8b, 0x5e, 0xfe)                                    # mov bx, [bp-2]     the game's bx: the scan code
    a.b(0x1e, 0x8e, 0x5e, 0x04)                              # push ds / mov ds, [bp+4]
    a.b(0x80, 0xbf, KEY_TABLE & 0xff, KEY_TABLE >> 8, 0xff)  # cmp byte [bx+81E3h], 0FFh   (replaced)
    a.b(0x1f)                                                # pop ds
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # input (1000:3F16, replaces mov [di+26h],ax: a knight's input bits as it reads them, ax, when its last move is
    # over, di = the knight): with input_buffer on, a fire key pressed in the last BUF_TICKS ticks (during the move:
    # the game never saw it) gives that attack now, with the directions noted with it; the player's own fire now
    # uses the press as it is
    # With a fire key pressed now, the directions noted with that press (also those let go just before it, kh_buffer)
    # are added, unless one of the same axis is held. Then the chord window (input_chord): a back direction without
    # fire waits that many ticks before it turns the knight, so back + up + fire keeps the facing it started from
    a.label('rules_input')
    a.near(0xe8, 'td_hold')                                  # D46: a staggered knight reads no keys
    a.b(0x53, 0x51, 0x52, 0x56, 0x9c, 0xfa)                  # push bx cx dx si / pushf / cli
    a.b(0x8a, 0xc8)                                          # mov cl, al   as read, for the log
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_INPUT_BUFFER); a.b(0x00)   # cmp byte cs:[input_buffer], 0
    a.short(0x75, 'ib_on'); a.near(0xe9, 'ib_chord')
    a.label('ib_on')
    a.b(0x33, 0xf6, 0x80, 0x7d, 0x09, 0x02)                  # xor si, si / cmp byte [di+9], 2   player 1 (arrows)
    a.short(0x74, 'ib_player')                               # je ib_player
    a.b(0x46, 0x80, 0x7d, 0x09, 0x01)                        # inc si / cmp byte [di+9], 1   player 2 (W A S D)
    a.short(0x74, 'ib_player')
    a.b(0x46, 0x80, 0x7d, 0x09, KEYS3_CONTROL)               # inc si / cmp byte [di+9], 7   the third key set
    a.short(0x75, 'ib_chord')                                # jne ib_chord
    a.label('ib_player')
    a.b(0x2e, 0x8a, 0x94); a.word('buf_bits')                # mov dl, cs:[si+buf_bits]
    a.b(0x0a, 0xd2); a.short(0x74, 'ib_chord')               # or dl, dl / jz ib_chord
    a.b(0x2e, 0xc6, 0x84); a.word('buf_bits'); a.b(0x00)     # mov byte cs:[si+buf_bits], 0   used, or too old
    a.b(0x1e, 0x33, 0xdb, 0x8e, 0xdb, 0x8b, 0x1e, 0x6c, 0x04, 0x1f)   # push ds / xor bx,bx / mov ds,bx / mov bx,[046Ch] / pop ds
    a.b(0xd1, 0xe6, 0x2e, 0x2b, 0x9c); a.word('buf_tick'); a.b(0xd1, 0xee)   # shl si,1 / sub bx, cs:[si+buf_tick] / shr si,1
    a.b(0x83, 0xfb, BUF_TICKS); a.short(0x77, 'ib_chord')    # cmp bx, BUF_TICKS / ja ib_chord   too old
    a.b(0xa8, 0x10); a.short(0x75, 'ib_merge')               # test al, 10h / jnz ib_merge   fire now
    a.b(0xf6, 0xc2, 0x0f); a.short(0x74, 'ib_fire')          # test dl, 0Fh / jz ib_fire
    a.b(0x32, 0xe4, 0x8a, 0xc2)                              # xor ah, ah / mov al, dl   fire and its directions
    a.short(0xeb, 'ib_chord')
    a.label('ib_fire')
    a.b(0x0c, 0x10); a.short(0xeb, 'ib_chord')               # or al, 10h   fire, the directions held now
    a.label('ib_merge')
    a.b(0x80, 0xe2, 0x0f)                                    # and dl, 0Fh
    a.b(0xa8, 0x03); a.short(0x74, 'ib_mh'); a.b(0x80, 0xe2, 0x0c)   # test al, 3 / jz / and dl, 0Ch
    a.label('ib_mh')
    a.b(0xa8, 0x0c); a.short(0x74, 'ib_mv'); a.b(0x80, 0xe2, 0x03)   # test al, 0Ch / jz / and dl, 3
    a.label('ib_mv')
    a.b(0x0a, 0xc2)                                          # or al, dl
    a.label('ib_chord')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_INPUT_CHORD); a.b(0x00)   # cmp byte cs:[input_chord], 0
    a.short(0x74, 'ib_log')
    a.near(0xe8, 'knight_no'); a.short(0x72, 'ib_log')       # call knight_no / jc   (bx = 0-3)
    a.b(0xa8, 0x10); a.short(0x75, 'ich_clear')              # test al, 10h / jnz   fire: no wait
    a.b(0xb2, 0x02, 0x80, 0x7d, 0x08, 0x03); a.short(0x75, 'ich_back'); a.b(0xb2, 0x01)   # mov dl, 2 (left) / cmp [di+8], 3 / jne / mov dl, 1
    a.label('ich_back')
    a.b(0x84, 0xc2); a.short(0x74, 'ich_clear')              # test al, dl / jz   no back direction
    a.b(0x2e, 0x8a, 0xa7); a.word('chord_on')                # mov ah, cs:[bx+chord_on]
    a.b(0x80, 0xfc, 0x02); a.short(0x74, 'ib_log')           # cmp ah, 2 / je   waited already: it turns
    a.b(0xd1, 0xe3, 0x1e, 0x33, 0xd2, 0x8e, 0xda, 0x8b, 0x16, 0x6c, 0x04, 0x1f)   # shl bx,1 / push ds / xor dx,dx / mov ds,dx / mov dx,[046Ch] / pop ds
    a.b(0x0a, 0xe4); a.short(0x75, 'ich_wait')               # or ah, ah / jnz ich_wait
    a.b(0x2e, 0x89, 0x97); a.word('chord_tick')              # mov cs:[bx+chord_tick], dx   it starts
    a.b(0xd1, 0xeb, 0x2e, 0xc6, 0x87); a.word('chord_on'); a.b(0x01)   # shr bx,1 / mov byte cs:[bx+chord_on], 1
    a.short(0xeb, 'ich_hold')
    a.label('ich_wait')
    a.b(0x2e, 0x2b, 0x97); a.word('chord_tick'); a.b(0xd1, 0xeb)   # sub dx, cs:[bx+chord_tick] / shr bx,1   ticks waited
    a.b(0x50, 0x2e, 0xa0); a.word('rules_table', G_INPUT_CHORD); a.b(0x32, 0xe4)   # push ax / mov al, cs:[input_chord] / xor ah, ah
    a.b(0x3b, 0xd0, 0x58); a.short(0x72, 'ich_hold')         # cmp dx, ax / pop ax / jb   still waiting
    a.b(0x2e, 0xc6, 0x87); a.word('chord_on'); a.b(0x02)     # mov byte cs:[bx+chord_on], 2   the turn now
    a.short(0xeb, 'ib_log')
    a.label('ich_hold')
    a.b(0x33, 0xc0); a.short(0xeb, 'ib_log')                 # xor ax, ax   stands this frame
    a.label('ich_clear')
    a.b(0x2e, 0xc6, 0x87); a.word('chord_on'); a.b(0x00)     # mov byte cs:[bx+chord_on], 0
    a.label('ib_log')
    a.b(0x50, 0x8a, 0xe8, 0xb0, ILOG_READ)                   # push ax / mov ch, al / mov al, kind   (cl = as read)
    a.near(0xe8, 'log_read'); a.b(0x58)                      # call log_read / pop ax
    a.b(0x9d, 0x5e, 0x5a, 0x59, 0x5b)                        # popf / pop si dx cx bx
    a.b(0x89, 0x45, 0x26)                                    # mov [di+26h], ax   (replaced)
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # --- D25: knights turn in place and walk up close ---
    # face_right, face_left (1000:3F83, 3F92: mov byte [di+8],1 / 3 as a knight's input turns it, di = the knight):
    # the pose is drawn mirrored about the object's x, and the standing knight spans x-13..x+23 facing right, so a
    # turn moved the body 10 to the side and the first step of the walk came at once: the knight hopped. A turn
    # now moves x so the body stays (front and back foot change places), and takes no step that frame (walk_block)
    a.label('rules_face_right')
    a.b(0x50, 0xb0, 0x01); a.short(0xeb, 'face')             # push ax / mov al, 1 / jmp face
    a.label('rules_face_left')
    a.b(0x50, 0xb0, 0x03)                                    # push ax / mov al, 3
    a.label('face')
    a.b(0x38, 0x45, 0x08); a.short(0x74, 'face_keep')        # cmp [di+8], al / je   no turn
    a.near(0xe8, 'turn_note')                                # call turn_note   when and from which facing
    a.near(0xe8, 'face_turn')                                # call face_turn
    a.label('face_keep')
    a.b(0x58); a.near(0xe9, 'rules_done')                    # pop ax / jmp rules_done
    # face_turn (al = the new facing, 1 or 3, di = the knight, which faces the other way): the turn, as above
    a.label('face_turn')
    a.b(0x50)                                                # push ax
    a.b(0x53, 0x56, 0xbb, TURN_SHIFT, 0x00)                  # push bx si / mov bx, TURN_SHIFT
    a.b(0x3c, 0x03); a.short(0x74, 'face_add'); a.b(0xf7, 0xdb)   # cmp al, 3 / je / neg bx
    a.label('face_add')
    a.b(0x01, 0x5d, 0x02)                                    # add [di+2], bx    the object
    a.b(0xbe, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0x51, 0xb9, ANIM_COUNT, 0x00)   # mov si, 947Eh / push cx / mov cx, 10
    a.label('face_anim')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'face_next')        # cmp byte [si], 0 / je
    a.b(0x39, 0x7c, 0x16); a.short(0x75, 'face_next')        # cmp [si+16h], di / jne
    a.b(0x01, 0x5c, 0x04)                                    # add [si+4], bx    its animation
    a.label('face_next')
    a.b(0x83, 0xc6, ANIM_SIZE); a.short(0xe2, 'face_anim')   # add si, 24h / loop face_anim
    a.b(0x59, 0x5e, 0x5b)                                    # pop cx si bx
    a.b(0x2e, 0xc6, 0x06); a.word('turned'); a.b(0x01)       # mov byte cs:[turned], 1
    a.b(0x88, 0x45, 0x08, 0x58, 0xc3)                        # mov [di+8], al / pop ax / ret   (replaced)

    # turn_note (di = a knight that turns now): the BIOS tick and its facing before the turn, for fire_facing; only
    # with up or down held as it turns (back + up together): a turn made on its own (back alone, then an attack up
    # the new way, as against ratmen) stays a turn
    a.label('turn_note')
    a.b(0x50, 0x53, 0x52)                                    # push ax bx dx
    a.near(0xe8, 'knight_no'); a.short(0x72, 'tn_end')       # call knight_no / jc   not one of the four
    a.b(0x8a, 0x45, 0x08, 0xf6, 0x45, 0x26, 0x0c); a.short(0x75, 'tn_up')   # mov al, [di+8] / test byte [di+26h], 0Ch / jnz   up or down held
    a.b(0x32, 0xc0)                                          # xor al, al   none noted
    a.label('tn_up')
    a.b(0x2e, 0x88, 0x87); a.word('turn_from')               # mov cs:[bx+turn_from], al
    a.b(0xd1, 0xe3, 0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f)   # shl bx, 1 / push ds / xor ax,ax / mov ds,ax / mov ax,[046Ch] / pop ds
    a.b(0x2e, 0x89, 0x87); a.word('turn_tick')               # mov cs:[bx+turn_tick], ax
    a.label('tn_end')
    a.b(0x5a, 0x5b, 0x58, 0xc3)                              # pop dx bx ax / ret
    # knight_no (di = a record): bx = 0-3 for the four knights' records, CF = 1 for anything else
    a.label('knight_no')
    a.b(0x50, 0x8b, 0xc7, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # push ax / mov ax, di / sub ax, 6C9Eh
    a.short(0x72, 'kn_no')                                   # jb kn_no
    a.b(0x33, 0xd2, 0xbb, SLOT_SIZE, 0x00, 0xf7, 0xf3)       # xor dx, dx / mov bx, 62h / div bx
    a.b(0x0b, 0xd2); a.short(0x75, 'kn_no')                  # or dx, dx / jnz kn_no
    a.b(0x3d, 0x04, 0x00); a.short(0x73, 'kn_no')            # cmp ax, 4 / jae kn_no
    a.b(0x8b, 0xd8, 0x58, 0xf8, 0xc3)                        # mov bx, ax / pop ax / clc / ret
    a.label('kn_no')
    a.b(0x58, 0xf9, 0xc3)                                    # pop ax / stc / ret

    # fire_facing (1000:40AC, replaces cmp byte [di+8],3 where a knight's fire picks its move from the facing's table,
    # ax = its directions * 2, di = the knight): a back + up (or down) attack starts with the back direction, which
    # turned the knight a frame or two before the fire was read, so back + up threw no dagger but gave the upward
    # thrust the other way. An attack with up or down and left or right within TURN_GRACE ticks of a turn undoes the
    # turn and is read with the facing from before it; up + forward still gives the upward thrust
    a.label('rules_fire_facing')
    a.b(0x50, 0x53, 0x52)                                    # push ax bx dx
    a.b(0xa8, 0x18); a.short(0x74, 'ff_cmp')                 # test al, 18h / jz   neither up nor down (bits * 2)
    a.b(0xa8, 0x06); a.short(0x74, 'ff_cmp')                 # test al, 06h / jz   neither right nor left
    a.near(0xe8, 'knight_no'); a.short(0x72, 'ff_cmp')       # call knight_no / jc
    a.b(0x2e, 0x8a, 0x87); a.word('turn_from')               # mov al, cs:[bx+turn_from]
    a.b(0x0a, 0xc0); a.short(0x74, 'ff_cmp')                 # or al, al / jz   no turn noted
    a.b(0x2e, 0xc6, 0x87); a.word('turn_from'); a.b(0x00)    # mov byte cs:[bx+turn_from], 0   once
    a.b(0x38, 0x45, 0x08); a.short(0x74, 'ff_cmp')           # cmp [di+8], al / je   faces that way already
    a.b(0xd1, 0xe3, 0x1e, 0x33, 0xd2, 0x8e, 0xda, 0x8b, 0x16, 0x6c, 0x04, 0x1f)   # shl bx,1 / push ds / xor dx,dx / mov ds,dx / mov dx,[046Ch] / pop ds
    a.b(0x2e, 0x2b, 0x97); a.word('turn_tick')               # sub dx, cs:[bx+turn_tick]
    a.b(0x83, 0xfa, TURN_GRACE); a.short(0x77, 'ff_cmp')     # cmp dx, TURN_GRACE / ja   too long ago
    a.near(0xe8, 'face_turn')                                # call face_turn   back to the facing before
    a.b(0x2e, 0xc6, 0x06); a.word('turned'); a.b(0x00)       # mov byte cs:[turned], 0   (no step to hold back)
    a.label('ff_cmp')
    a.b(0x5a, 0x5b, 0x58)                                    # pop dx bx ax
    a.b(0x50, 0x51, 0x8a, 0xc8, 0xd0, 0xe9, 0x8a, 0x6d, 0x08, 0xb0, ILOG_MOVE)   # push ax cx / mov cl, al / shr cl,1 / mov ch, [di+8] / mov al, kind
    a.near(0xe8, 'log_knight'); a.b(0x59, 0x58)              # call log_knight / pop cx ax   the attack and its facing
    a.b(0x80, 0x7d, 0x08, 0x03)                              # cmp byte [di+8], 3   (replaced)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # walk_block (1000:3FAC, replaces mov si,[77E8h] after 9FDF has checked the step against the others' boxes,
    # ax = the directions allowed, [783Dh] the x step): a turn takes no step; a step left or right blocked by a
    # figure ahead (its box, the drawn frame's extent, within 10 in depth and overlapping in height, as 9FDF) is
    # cut to the gap, so the knights come up to touching instead of stopping up to a whole step (25) apart
    a.label('rules_walk_block')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('turned'); a.b(0x00)       # cmp byte cs:[turned], 0
    a.short(0x74, 'wb_check')                                # je wb_check
    a.b(0x2e, 0xc6, 0x06); a.word('turned'); a.b(0x00)       # mov byte cs:[turned], 0
    a.b(0xc7, 0x06, 0x3d, 0x78, 0x00, 0x00)                  # mov word [783Dh], 0   turning: no step
    a.near(0xe9, 'rules_done')
    a.label('wb_check')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_LUNAR); a.short(0x74, 'wb_earth')
    a.b(0xd1, 0x3e, 0x3d, 0x78, 0xd1, 0x3e, 0x3f, 0x78)      # LUNAR: sar word [783Dh], 1 / sar word [783Fh], 1   half steps
    a.label('wb_earth')
    a.b(0x53, 0x51, 0x52, 0x55, 0x57)                        # push bx cx dx bp di
    a.b(0x8b, 0x0e, 0x3d, 0x78, 0xbb, 0x01, 0x00)            # mov cx, [783Dh] / mov bx, 1   right
    a.b(0x0b, 0xc9); a.short(0x75, 'wb_dir')                 # or cx, cx / jnz
    a.near(0xe9, 'wb_depth')                                 # no step in x
    a.label('wb_dir')
    a.short(0x7f, 'wb_bit'); a.b(0xb3, 0x02)                 # jg wb_bit / mov bl, 2   left
    a.label('wb_bit')
    a.b(0x85, 0xc3); a.short(0x74, 'wb_blocked')             # test ax, bx / jz wb_blocked
    a.near(0xe9, 'wb_depth')                                 # allowed
    a.label('wb_blocked')
    a.b(0xba, 0xff, 0x7f)                                    # mov dx, 7FFFh   the least gap ahead
    a.b(0xbd, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8)            # mov bp, 947Eh
    a.b(0x50, 0x51, 0xb9, ANIM_COUNT, 0x00)                  # push ax cx / mov cx, 10
    a.label('wb_loop')
    a.b(0x3e, 0x80, 0x7e, 0x00, 0x00); a.short(0x74, 'wb_next')   # cmp byte ds:[bp], 0 / je
    a.b(0x3e, 0x8b, 0x7e, 0x16)                              # mov di, ds:[bp+16h]
    a.b(0x3b, 0xfe); a.short(0x74, 'wb_next')                # cmp di, si / je   itself
    a.b(0x83, 0x7d, 0x22, 0x00); a.short(0x74, 'wb_next')    # cmp word [di+22h], 0 / je   no box
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'wb_next')    # cmp word [di+38h], 0 / jle  down
    a.b(0x8b, 0x45, 0x06, 0x2b, 0x44, 0x06)                  # mov ax, [di+6] / sub ax, [si+6]
    a.short(0x79, 'wb_dz'); a.b(0xf7, 0xd8)                  # jns / neg ax
    a.label('wb_dz')
    a.b(0x83, 0xf8, 0x0a); a.short(0x7f, 'wb_next')          # cmp ax, 10 / jg   another depth
    a.b(0x8b, 0x45, 0x4e, 0x3b, 0x44, 0x50); a.short(0x7d, 'wb_next')   # mov ax,[di+4Eh] / cmp ax,[si+50h] / jge   below
    a.b(0x8b, 0x45, 0x50, 0x3b, 0x44, 0x4e); a.short(0x7e, 'wb_next')   # mov ax,[di+50h] / cmp ax,[si+4Eh] / jle   above
    a.b(0x80, 0xfb, 0x01); a.short(0x75, 'wb_left')          # cmp bl, 1 / jne wb_left
    a.b(0x8b, 0x45, 0x02, 0x3b, 0x44, 0x02)                  # mov ax, [di+2] / cmp ax, [si+2]
    a.short(0x7c, 'wb_next')                                 # jl wb_next   behind (moving right)
    a.b(0x8b, 0x45, 0x22, 0x2b, 0x44, 0x24)                  # mov ax, [di+22h] / sub ax, [si+24h]   its left - my right
    a.short(0xeb, 'wb_gap')
    a.label('wb_left')
    a.b(0x8b, 0x45, 0x02, 0x3b, 0x44, 0x02)                  # mov ax, [di+2] / cmp ax, [si+2]
    a.short(0x7f, 'wb_next')                                 # jg wb_next   behind (moving left)
    a.b(0x8b, 0x44, 0x22, 0x2b, 0x45, 0x24)                  # mov ax, [si+22h] / sub ax, [di+24h]   my left - its right
    a.label('wb_gap')
    a.b(0x3b, 0xc2); a.short(0x7d, 'wb_next'); a.b(0x8b, 0xd0)   # cmp ax, dx / jge / mov dx, ax
    a.label('wb_next')
    a.b(0x83, 0xc5, ANIM_SIZE); a.short(0xe2, 'wb_loop')     # add bp, 24h / loop wb_loop
    a.b(0x59, 0x58)                                          # pop cx ax
    a.b(0x83, 0xfa, 0x00); a.short(0x7e, 'wb_depth')         # cmp dx, 0 / jle   touching already (or overlapping)
    a.b(0x81, 0xfa, 0xff, 0x7f); a.short(0x74, 'wb_depth')   # cmp dx, 7FFFh / je   nothing ahead: blocked otherwise
    a.b(0x8b, 0xf9)                                          # mov di, cx      the step
    a.b(0x0b, 0xff); a.short(0x7f, 'wb_abs'); a.b(0xf7, 0xdf)   # or di, di / jg / neg di   (x)
    a.label('wb_abs')
    a.b(0x3b, 0xd7); a.short(0x7e, 'wb_cut'); a.b(0x8b, 0xd7)   # cmp dx, di / jle / mov dx, di
    a.label('wb_cut')
    a.b(0x0b, 0xc9); a.short(0x7f, 'wb_store'); a.b(0xf7, 0xda)   # or cx, cx / jg / neg dx
    a.label('wb_store')
    a.b(0x89, 0x16, 0x3d, 0x78, 0x0b, 0xc3)                  # mov [783Dh], dx / or ax, bx   the step allowed, cut
    # depth: the game refuses a step in depth once a figure overlapping in x and height is within 20 (A0AB),
    # whatever the step; now within DEPTH_GAP (A0AB patched), and a step that would come nearer than that is cut
    a.label('wb_depth')
    a.b(0x8b, 0x0e, 0x3f, 0x78, 0x0b, 0xc9); a.short(0x75, 'wz_go')   # mov cx, [783Fh] / or cx, cx / jnz
    a.near(0xe9, 'wb_pop')
    a.label('wz_go')
    a.b(0xbb, 0x04, 0x00); a.short(0x7f, 'wz_bit'); a.b(0xb3, 0x08)   # mov bx, 4 / jg / mov bl, 8
    a.label('wz_bit')
    a.b(0x85, 0xc3); a.short(0x75, 'wz_scan')                # test ax, bx / jnz wz_scan
    a.near(0xe9, 'wb_pop')                                   # refused already
    a.label('wz_scan')
    a.b(0xba, 0xff, 0x7f, 0xbd, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8)   # mov dx, 7FFFh / mov bp, 947Eh
    a.b(0x50, 0x51, 0xb9, ANIM_COUNT, 0x00)                  # push ax cx / mov cx, 10
    a.label('wz_loop')
    a.b(0x3e, 0x80, 0x7e, 0x00, 0x00); a.short(0x74, 'wz_next')
    a.b(0x3e, 0x8b, 0x7e, 0x16, 0x3b, 0xfe); a.short(0x74, 'wz_next')   # mov di, ds:[bp+16h] / cmp di, si / je
    a.b(0x83, 0x7d, 0x22, 0x00); a.short(0x74, 'wz_next')
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'wz_next')
    a.b(0x8b, 0x45, 0x22, 0x3b, 0x44, 0x24); a.short(0x7d, 'wz_next')   # its left >= my right: apart
    a.b(0x8b, 0x45, 0x24, 0x3b, 0x44, 0x22); a.short(0x7e, 'wz_next')   # its right <= my left
    a.b(0x8b, 0x45, 0x4e, 0x3b, 0x44, 0x50); a.short(0x7d, 'wz_next')   # height apart
    a.b(0x8b, 0x45, 0x50, 0x3b, 0x44, 0x4e); a.short(0x7e, 'wz_next')
    a.b(0x8b, 0x45, 0x06, 0x2b, 0x44, 0x06)                  # mov ax, [di+6] / sub ax, [si+6]   its depth - mine
    a.b(0x80, 0xfb, 0x04); a.short(0x74, 'wz_dir')           # cmp bl, 4 / je   moving deeper
    a.b(0xf7, 0xd8)                                          # neg ax
    a.label('wz_dir')
    a.b(0x0b, 0xc0); a.short(0x7e, 'wz_next')                # or ax, ax / jle   behind
    a.b(0x2d, DEPTH_GAP, 0x00)                               # sub ax, DEPTH_GAP   the room left
    a.b(0x3b, 0xc2); a.short(0x7d, 'wz_next'); a.b(0x8b, 0xd0)   # cmp ax, dx / jge / mov dx, ax
    a.label('wz_next')
    a.b(0x83, 0xc5, ANIM_SIZE); a.short(0xe2, 'wz_loop')
    a.b(0x59, 0x58)                                          # pop cx ax
    a.b(0x81, 0xfa, 0xff, 0x7f); a.short(0x75, 'wz_some'); a.near(0xe9, 'wb_pop')   # none ahead
    a.label('wz_some')
    a.b(0x83, 0xfa, 0x00); a.short(0x7f, 'wz_room')          # cmp dx, 0 / jg
    a.b(0x33, 0xd2, 0xf7, 0xd3, 0x23, 0xc3, 0xf7, 0xd3)      # xor dx, dx / not bx / and ax, bx / not bx   no room: refused
    a.label('wz_room')
    a.b(0x8b, 0xf9, 0x0b, 0xff); a.short(0x7f, 'wz_abs'); a.b(0xf7, 0xdf)   # mov di, cx / or di, di / jg / neg di
    a.label('wz_abs')
    a.b(0x3b, 0xd7); a.short(0x7e, 'wz_cut'); a.b(0x8b, 0xd7)   # cmp dx, di / jle / mov dx, di
    a.label('wz_cut')
    a.b(0x0b, 0xc9); a.short(0x7f, 'wz_store'); a.b(0xf7, 0xda)   # or cx, cx / jg / neg dx
    a.label('wz_store')
    a.b(0x89, 0x16, 0x3f, 0x78)                              # mov [783Fh], dx
    a.label('wb_pop')
    a.b(0x5f, 0x5d, 0x5a, 0x59, 0x5b)                        # pop di bp dx cx bx
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # --- cheat codes (custom rules cheat_codes = yes) ---
    # cheat_key (from key_handler, a key pressed, bx = scan code, dx = now, ds = MAIN's code segment): each code of
    # the current context (cheat_ctx, set by the item screen's, the fight's and the map's loops) keeps its progress;
    # a key that a code goes on with at its second key or later is kept from the game (CF = 1: the table is not
    # written), so E in HEREBEDRAGONS does not end the turn; a code typed whole is noted (cheat_pending) for its
    # loop to carry out. A pause of CHEAT_TIMEOUT ticks starts the codes over
    a.label('cheat_key')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_CHEATS); a.b(0x00)   # cmp byte cs:[cheat_codes], 0
    a.short(0x75, 'ck_on'); a.b(0xf8, 0xc3)                  # jne ck_on / clc / ret
    a.label('ck_on')
    a.b(0x50, 0x51, 0x52, 0x56, 0x57)                        # push ax cx dx si di
    a.b(0x8b, 0xc2, 0x2e, 0x2b, 0x06); a.word('cheat_last')  # mov ax, dx / sub ax, cs:[cheat_last]
    a.b(0x2e, 0x89, 0x16); a.word('cheat_last')              # mov cs:[cheat_last], dx
    a.b(0x3d, CHEAT_TIMEOUT, 0x00); a.short(0x76, 'ck_go')   # cmp ax, TIMEOUT / jbe ck_go
    a.near(0xe8, 'cheat_reset')                              # call cheat_reset   a pause: start over
    a.label('ck_go')
    a.b(0x33, 0xd2)                                          # xor dx, dx       dl = keep from the game, dh = reset
    a.b(0xbe); a.word('cheat_tab'); a.b(0xbf); a.word('cheat_prog')   # mov si, cheat_tab / mov di, cheat_prog
    a.label('ck_loop')
    a.b(0x2e, 0x8a, 0x0c, 0x0a, 0xc9); a.short(0x75, 'ck_one')   # mov cl, cs:[si] / or cl, cl / jnz ck_one
    a.near(0xe9, 'ck_done')
    a.label('ck_one')
    a.b(0x2e, 0x8a, 0x44, 0x01, 0x2e, 0x84, 0x06); a.word('cheat_ctx')   # mov al, cs:[si+1] / test cs:[cheat_ctx], al
    a.short(0x75, 'ck_here')                                 # jnz ck_here
    a.b(0x2e, 0xc6, 0x05, 0x00); a.short(0xeb, 'ck_next')    # mov byte cs:[di], 0 / jmp ck_next   another context
    a.label('ck_here')
    a.b(0x2e, 0x8a, 0x05, 0x32, 0xe4)                        # mov al, cs:[di] / xor ah, ah   the progress
    a.b(0x56, 0x03, 0xf0, 0x2e, 0x38, 0x5c, 0x03, 0x5e)      # push si / add si, ax / cmp cs:[si+3], bl / pop si
    a.short(0x75, 'ck_first'); a.b(0xfe, 0xc0)               # jne ck_first / inc al
    a.short(0xeb, 'ck_set')
    a.label('ck_first')
    a.b(0x32, 0xc0, 0x2e, 0x38, 0x5c, 0x03)                  # xor al, al / cmp cs:[si+3], bl
    a.short(0x75, 'ck_set'); a.b(0xfe, 0xc0)                 # jne ck_set / inc al   the first key again
    a.label('ck_set')
    a.b(0x3a, 0xc1); a.short(0x72, 'ck_store')               # cmp al, cl / jb ck_store
    a.b(0x2e, 0x8a, 0x44, 0x02, 0x2e, 0xa2); a.word('cheat_pending')   # mov al, cs:[si+2] / mov cs:[cheat_pending], al
    a.b(0xb6, 0x01, 0xb2, 0x01, 0x32, 0xc0)                  # mov dh, 1 / mov dl, 1 / xor al, al   typed whole
    a.label('ck_store')
    a.b(0x2e, 0x88, 0x05, 0x3c, 0x02); a.short(0x72, 'ck_next')   # mov cs:[di], al / cmp al, 2 / jb ck_next
    a.b(0xb2, 0x01)                                          # mov dl, 1        keep this key from the game
    a.label('ck_next')
    a.b(0x32, 0xed, 0x03, 0xf1, 0x83, 0xc6, 0x03, 0x47)      # xor ch, ch / add si, cx / add si, 3 / inc di
    a.near(0xe9, 'ck_loop')
    a.label('ck_done')
    a.b(0x0a, 0xd2); a.short(0x74, 'ck_no_code')             # D55: a key of a code: its time (code_t)
    a.b(0x50, 0x2e, 0xa1); a.word('cheat_last'); a.b(0x2e, 0xa3); a.word('code_t'); a.b(0x58)
    a.label('ck_no_code')
    a.b(0x0a, 0xf6); a.short(0x74, 'ck_menu')                # or dh, dh / jz ck_menu
    a.near(0xe8, 'cheat_reset')                              # call cheat_reset
    a.b(0x2e, 0xc6, 0x06); a.word('snd_req'); a.b(0x01)      # typed whole: its sound
    a.label('ck_menu')
    # the first menu: D and J (keys the menu acts on at once) first wait for a code's next letter; a key the codes
    # go on with uses the held one up, any other lets it through first
    a.b(0x2e, 0x80, 0x3e); a.word('cheat_ctx'); a.b(CHEAT_MENU); a.short(0x75, 'ck_ret')
    a.b(0x0a, 0xd2); a.short(0x74, 'ck_free')                # or dl, dl / jz ck_free
    a.b(0x2e, 0xc6, 0x06); a.word('held_scan'); a.b(0x00)    # a code's key: the held one is part of it
    a.short(0xeb, 'ck_ret')
    a.label('ck_free')
    a.near(0xe8, 'held_replay')                              # the held key (if any) to the game
    for scan in HOLD_KEYS:
        a.b(0x80, 0xfb, scan); a.short(0x74, 'ck_hold')
    a.short(0xeb, 'ck_ret')
    a.label('ck_hold')
    # D55: D, J, G, B, P within CHEAT_TIMEOUT of a code's key (a code mistyped or left unfinished, as BEATEMUP): kept
    # from the game, so it starts no practice
    a.b(0x50, 0x2e, 0xa1); a.word('cheat_last'); a.b(0x2e, 0x2b, 0x06); a.word('code_t')   # push ax / mov ax, now / sub ax, cs:[code_t]
    a.b(0x3d, CHEAT_TIMEOUT, 0x00, 0x58); a.short(0x77, 'ck_hold_it')   # cmp ax, timeout / pop ax / ja
    a.b(0xb2, 0x01); a.short(0xeb, 'ck_ret')                 # mov dl, 1   swallowed
    a.label('ck_hold_it')
    a.b(0x2e, 0x88, 0x1e); a.word('held_scan'); a.b(0xb2, 0x01)   # mov cs:[held_scan], bl / mov dl, 1   kept back
    a.label('ck_ret')
    a.b(0x80, 0xfa, 0x01, 0xf5)                              # cmp dl, 1 / cmc   CF = dl
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x58, 0xc3)                  # pop di si dx cx ax / ret
    # held_replay (ds = MAIN's code segment): the held key goes to the game now, pressed and let go KEY_HOLD ticks
    # later (key_settle), as a short press
    a.label('held_replay')
    a.b(0x50, 0x53, 0x52, 0x56)                              # push ax bx dx si
    a.b(0x2e, 0x8a, 0x1e); a.word('held_scan'); a.b(0x32, 0xff, 0x0a, 0xdb); a.short(0x74, 'hr_pop')   # mov bl, cs:[held_scan] / xor bh, bh / or bl, bl / jz
    a.b(0x2e, 0xc6, 0x06); a.word('held_scan'); a.b(0x00)
    a.b(0xc6, 0x87, KEY_TABLE & 0xff, KEY_TABLE >> 8, 0x00)  # mov byte [bx+81E3h], 0   pressed
    a.b(0x06, 0x33, 0xf6, 0x8e, 0xc6, 0x26, 0x8b, 0x16, 0x6c, 0x04, 0x07)   # push es / xor si,si / mov es,si / mov dx,es:[046Ch] / pop es
    a.b(0x8b, 0xf3, 0xd1, 0xe6, 0x2e, 0x89, 0x94); a.word('key_tick')   # mov si, bx / shl si, 1 / mov cs:[si+key_tick], dx
    a.b(0x2e, 0xc6, 0x87); a.word('key_pending'); a.b(0x01)  # its release kept back
    a.b(0x2e, 0xc6, 0x06); a.word('key_pending_any'); a.b(0x01)
    a.label('hr_pop')
    a.b(0x5e, 0x5a, 0x5b, 0x58, 0xc3)                        # pop si dx bx ax / ret
    a.label('cheat_reset')                                   # every code's progress to 0
    a.b(0x50, 0x51, 0x57, 0x06, 0x0e, 0x07, 0xbf); a.word('cheat_prog')   # push ax cx di es / push cs / pop es / mov di, cheat_prog
    a.b(0xb9, len(CHEATS), 0x00, 0x32, 0xc0, 0xfc, 0xf3, 0xaa)   # mov cx, n / xor al, al / cld / rep stosb
    a.b(0x07, 0x5f, 0x59, 0x58, 0xc3)                        # pop es di cx ax / ret

    # items_loop (1000:BFEC, replaces call D086 in the item screen's loop): the item codes, for the knight whose
    # turn it is; the screen then draws itself again ([0ED86h]), and a change of constitution, endurance or armour
    # recomputes max HP and movement (1000:0279) before the loop goes on (this site again)
    a.label('rules_items_loop')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_wait'); a.b(0x00); a.short(0x74, 'sxil_nw')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x00, 0x2e, 0xa1); a.word('snd_ax')   # back from the sound: ax again
    a.short(0xeb, 'sxil_go')
    a.label('sxil_nw')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_req'); a.b(0x00); a.short(0x74, 'sxil_go')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_req'); a.b(0x00, 0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x01)
    a.b(0x2e, 0xa3); a.word('snd_ax'); a.b(0x8b, 0x46, 0x02, 0x2d, 0x02, 0x00)   # mov cs:[snd_ax], ax / mov ax, [bp+2] / sub ax, 2
    a.b(0x2e, 0xa3); a.word('call_ret')                      # this site's int 63h again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(SOUND & 0xff, SOUND >> 8)
    a.b(0xb8, CHEAT_SOUND, 0x00); a.near(0xe9, 'call_game')  # mov ax, sound id / 1000:5970
    a.label('sxil_go')
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_ctx'); a.b(CHEAT_ITEMS)   # mov byte cs:[cheat_ctx], 1
    a.b(0x2e, 0xa0); a.word('cheat_pending')                 # mov al, cs:[cheat_pending]
    a.b(0x0a, 0xc0); a.short(0x74, 'il_game')                # or al, al / jz il_game
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_pending'); a.b(0x00)   # mov byte cs:[cheat_pending], 0
    a.b(0x3c, 40); a.short(0x73, 'il_game')                  # cmp al, 40 / jae il_game   not an item code
    a.b(0x56, 0x57, 0x8b, 0x36, 0xe8, 0x77, 0x8b, 0x7c, 0x44)   # push si di / mov si, [77E8h] / mov di, [si+44h]
    a.near(0xe8, 'cheat_items')                              # call cheat_items   CF = 1: recompute
    a.b(0x5f, 0x5e)                                          # pop di si
    a.b(0xc7, 0x06, ITEMS_REDRAW & 0xff, ITEMS_REDRAW >> 8, 0x01, 0x00)   # mov word [0ED86h], 1   redraw
    a.short(0x73, 'il_game')                                 # jnc il_game
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(RECALC & 0xff, RECALC >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(ITEMS_SITE & 0xff, ITEMS_SITE >> 8)
    a.near(0xe9, 'call_game')                                # 0279, then this site again
    a.label('il_game')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(ITEMS_CALL & 0xff, ITEMS_CALL >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b((ITEMS_SITE + 3) & 0xff, (ITEMS_SITE + 3) >> 8)
    a.near(0xe9, 'call_game')                                # call D086 (replaced), on at BFEF

    # cheat_items (al = the code, si = the knight, di = its item table): CF = 1 when max HP and movement must be
    # computed again
    a.label('cheat_items')
    def case(name):
        a.b(0x3c, CHEAT_ID[name]); a.short(0x75, f'ci_n_{name}')
    def end(name, recalc=False):
        a.b(0xf9 if recalc else 0xf8, 0xc3)                  # stc / clc, ret
        a.label(f'ci_n_{name}')
    def inc_item(off):
        a.b(0xff, 0x45, off)                                 # inc word [di+off]
    # IDKFA: one more of every magic item, the Sword of Sharpness, the keys, the Moonstones, battle armour, daggers
    case('IDKFA')
    for off in (0x00, 0x02, 0x06, 0x08, 0x0a, 0x0c, 0x0e, 0x10, 0x12):
        inc_item(off)
    a.b(0xc7, 0x45, 0x04, 0x01, 0x00, 0xc7, 0x45, 0x14, 0x0f, 0x00, 0xc7, 0x45, 0x16, 0x0f, 0x00)   # sharpness, keys, stones
    a.b(0xc7, 0x44, 0x42, 0x1e, 0x00, 0xc6, 0x44, 0x34, 99)  # battle armour / 99 daggers
    end('IDKFA', True)
    case('KONAMI'); a.b(0xc6, 0x44, 0x31, 99); end('KONAMI')   # 99 lives
    for name in ('HESOYAM', 'ROSEBUD', 'KLAPAUCIUS', 'MOTHERLODE'):
        case(name)
        a.b(0x81, 0x44, 0x32, 20000 & 0xff, 20000 >> 8)      # add word [si+32h], 20000
        a.short(0x71, f'ci_g_{name}'); a.b(0xc7, 0x44, 0x32, 0xff, 0x7f)   # jno / mov word [si+32h], 7FFFh     gold is signed
        a.label(f'ci_g_{name}')
        end(name)
    case('POINTTAKEN'); a.b(0xc6, 0x44, 0x34, 99); end('POINTTAKEN')
    case('TINMAN')                                           # the next better armour
    a.b(0x83, 0x7c, 0x42, 0x1e); a.short(0x7d, 'ci_tin'); a.b(0xff, 0x44, 0x42)   # cmp word [si+42h], 1Eh / jge / inc
    a.label('ci_tin')
    end('TINMAN', True)
    case('SIRLOIN')                                          # the next better sword, up to the claymore
    a.b(0x83, 0x7c, 0x40, 0x18); a.short(0x7d, 'ci_sir'); a.b(0xff, 0x44, 0x40)   # cmp word [si+40h], 18h / jge / inc
    a.label('ci_sir')
    end('SIRLOIN')
    case('HEADSROLL'); a.b(0xc7, 0x45, 0x04, 0x01, 0x00); end('HEADSROLL', True)   # Sword of Sharpness (0279 arms it)
    for name, off in (('WYRMPROOF', 0x08), ('MINEALLMINE', 0x0e), ('HASTALAVISTA', 0x0a), ('SPECIALDELIVERY', 0x10),
                      ('NOTTODAY', 0x12), ('FLYBYKNIGHT', 0x0c), ('FLESHWOUND', 0x00), ('PEEPINGTOM', 0x02)):
        case(name); inc_item(off); end(name)
    case('KEYMASTER'); a.b(0xc7, 0x45, 0x14, 0x0f, 0x00); end('KEYMASTER')
    for name, bit in (('FULLMOONEY', 2), ('DARKSIDE', 1), ('COMINGSOON', 4), ('GOINGGONE', 8)):
        case(name); a.b(0x80, 0x4d, 0x16, bit); end(name)    # or byte [di+16h], bit
    case('KNIGHTRIDER')                                      # haste for good: this turn too
    a.near(0xe8, 'knight_bit')                               # call knight_bit   al = this knight's bit
    a.b(0x2e, 0x08, 0x06); a.word('knight_haste')            # or cs:[knight_haste], al
    a.b(0x83, 0x3e, 0xa2, 0xcc, 0x00); a.short(0x75, 'ci_kr')   # cmp word [0CCA2h], 0 / jne   a scroll already
    a.b(0xd1, 0x26, 0xac, 0xcc)                              # shl word [0CCACh], 1
    a.label('ci_kr')
    end('KNIGHTRIDER')
    case('LIVEANDLEARN'); a.b(0x83, 0x44, 0x36, 10); end('LIVEANDLEARN')   # +10 XP
    case('SIRLIFTSALOT'); a.b(0xc6, 0x44, 0x2e, 5); end('SIRLIFTSALOT')
    case('BUILTTOLAST'); a.b(0xc6, 0x44, 0x2f, 5); end('BUILTTOLAST', True)
    case('AREWETHEREYET'); a.b(0xc6, 0x44, 0x30, 5); end('AREWETHEREYET', True)
    # DANUBLESS: full HP; at full HP a life more (up to max_lives); at full HP and lives a healing potion more
    case('DANUBLESS')
    a.b(0x8b, 0x44, 0x3c, 0x39, 0x44, 0x38); a.short(0x7d, 'ci_dan_hp')   # mov ax, [si+3Ch] / cmp [si+38h], ax / jge   full already
    a.b(0x89, 0x44, 0x38)                                    # mov [si+38h], ax   full
    a.near(0xe9, 'ci_dan_end')
    a.label('ci_dan_hp')
    a.b(0x2e, 0xa0); a.word('rules_table', G_MAX_LIVES)      # mov al, cs:[max_lives]
    a.b(0x38, 0x44, 0x31); a.short(0x7e, 'ci_dan_life')      # cmp [si+31h], al / jle   (below the cap)
    a.label('ci_dan_potion')
    inc_item(0x00)                                           # a healing potion
    a.short(0xeb, 'ci_dan_end')
    a.label('ci_dan_life')
    a.short(0x74, 'ci_dan_potion')                           # at the cap: the potion
    a.b(0xfe, 0x44, 0x31)                                    # inc byte [si+31h]
    a.label('ci_dan_end')
    end('DANUBLESS')
    case('PUTARINGONIT'); inc_item(0x06); end('PUTARINGONIT', True)   # a Ring of Protection (0279: its HP)
    case('MOONMAX'); a.b(0xc6, 0x44, 0x2e, 5, 0xc6, 0x44, 0x2f, 5, 0xc6, 0x44, 0x30, 5); end('MOONMAX', True)
    a.b(0xf8, 0xc3)                                          # clc / ret
    # knight_bit: si = a knight record -> al = 1 << its number (0 if not a knight)
    a.label('knight_bit')
    a.b(0xb0, 0x01)
    for n, rec in enumerate(KNIGHTS):
        a.b(0x81, 0xfe, rec & 0xff, rec >> 8); a.short(0x74, 'kb_ret'); a.b(0xd0, 0xe0)   # cmp si, rec / je / shl al, 1
    a.b(0x32, 0xc0)
    a.label('kb_ret')
    a.b(0xc3)

    # turn_haste (1000:A6D2, replaces cmp word [0CCA2h],0 where the turn's budget is doubled by a Scroll of Haste):
    # also for a knight with KNIGHTRIDER (ZF = 0: double)
    a.label('rules_turn_haste')
    a.b(0x83, 0x3e, 0xa2, 0xcc, 0x01); a.short(0x75, 'th_not_cursed')   # cmp word [0CCA2h], 1 / jne
    a.b(0xd1, 0x2e, 0xac, 0xcc, 0xc7, 0x46, 0x02, 0xdd, 0xa6)   # shr word [0CCACh], 1 / mov word [bp+2], 0A6DDh   half
    a.near(0xe9, 'rules_done')
    a.label('th_not_cursed')
    a.b(0x83, 0x3e, 0xa2, 0xcc, 0x00); a.short(0x75, 'th_flags')   # cmp word [0CCA2h], 0 / jne th_flags
    a.b(0x56, 0x50, 0x8b, 0x36, 0xe8, 0x77)                  # push si ax / mov si, [77E8h]
    a.near(0xe8, 'knight_bit')
    a.b(0x2e, 0x84, 0x06); a.word('knight_haste')            # test cs:[knight_haste], al   ZF = 0: hasted
    a.b(0x58, 0x5e)                                          # pop ax si
    a.label('th_flags')
    a.near(0xe9, 'rules_flags')

    # cheat_map (from turn_moves, every pass of the map loop): the map codes for the knight whose turn it is.
    # CF = 1: a game routine to call (call_target), returning to the map loop's site (A568h) again
    a.label('cheat_map')
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_ctx'); a.b(CHEAT_MAP)   # mov byte cs:[cheat_ctx], 4
    # ONEMORETURN: the movement used stays as it was when typed, until something ends the turn
    a.b(0x2e, 0x80, 0x3e); a.word('one_more'); a.b(0x00); a.short(0x74, 'cm_pending')
    a.b(0x50, 0xa1, 0x98, 0xcc, 0x3b, 0x06, 0xac, 0xcc); a.short(0x7d, 'cm_om_end')   # push ax / mov ax,[CC98h] / cmp ax,[CCACh] / jge
    a.b(0x2e, 0xa1); a.word('one_more_used'); a.b(0xa3, 0x98, 0xcc)   # mov ax, cs:[one_more_used] / mov [0CC98h], ax
    a.b(0x58); a.short(0xeb, 'cm_pending')
    a.label('cm_om_end')
    a.b(0x58, 0x2e, 0xc6, 0x06); a.word('one_more'); a.b(0x00)   # pop ax / mov byte cs:[one_more], 0
    a.label('cm_pending')
    a.b(0x2e, 0xa0); a.word('cheat_pending')                 # mov al, cs:[cheat_pending]
    a.b(0x3c, 60); a.short(0x73, 'cm_go')                    # cmp al, 60 / jae cm_go
    a.b(0x3c, 40); a.short(0x72, 'cm_none')                  # a fight code: for the next fight of the game
    a.b(0x50, 0xb4, 0x02); a.near(0xe8, 'queue_code'); a.b(0x58)
    a.label('cm_none')
    a.b(0xf8, 0xc3)                                          # clc / ret
    a.label('cm_go')
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_pending'); a.b(0x00)
    a.b(0x56, 0x57, 0x53, 0x8b, 0x36, 0xe8, 0x77, 0x8b, 0x7c, 0x44)   # push si di bx / mov si, [77E8h] / mov di, [si+44h]
    def mcase(name):
        a.b(0x3c, CHEAT_ID[name]); a.short(0x74, f'cm_y_{name}'); a.near(0xe9, f'cm_n_{name}')
        a.label(f'cm_y_{name}')
    def mend(name, call=None):
        if call:
            a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(call & 0xff, call >> 8)
            a.b(0x5b, 0x5f, 0x5e, 0xf9, 0xc3)                # pop bx di si / stc / ret
        else:
            a.near(0xe9, 'cm_done')
        a.label(f'cm_n_{name}')
    mcase('WEPL'); a.b(0xc7, 0x45, 0x14, 0x0f, 0x00); mend('WEPL')
    mcase('MOONWALK')                                        # the moon's next phase, as 1000:1167 and 118D
    a.b(0xff, 0x06, 0xb1, 0x05, 0xc7, 0x06, 0x8b, 0x89, 0x00, 0x00)   # inc word [05B1h] / mov word [898Bh], 0
    a.b(0xa1, 0xb3, 0x05, 0x40, 0x25, 0x07, 0x00, 0xa3, 0xb3, 0x05)   # mov ax,[05B3h] / inc ax / and ax,7 / mov [05B3h],ax
    a.b(0x8b, 0xd8, 0x8a, 0x87, 0xa9, 0x05, 0x98, 0xa3, 0x89, 0x89)   # mov bx,ax / mov al,[bx+05A9h] / cbw / mov [8989h],ax
    mend('MOONWALK', MOON_DRAW)                              # the map's moon drawn again
    mcase('HOMESICK')                                        # to its home village (where it started)
    a.near(0xe8, 'section'); a.short(0x72, 'cm_hs_end')      # call section / jc   not a knight
    a.b(0x2e, 0x8b, 0x1e); a.word('rec4')                    # mov bx, cs:[rec4]
    for pos, cell, add in ((0x5c, 0x2a, 0), (0x5e, 0x2c, 2)):
        a.b(0x2e, 0x8b, 0x87); a.word('start_pos', add)      # mov ax, cs:[bx+start_pos]
        a.b(0x89, 0x44, pos, 0xd1, 0xe8, 0xd1, 0xe8, 0xd1, 0xe8, 0x89, 0x44, cell)
    a.label('cm_hs_end')
    mend('HOMESICK')
    mcase('ONEMORETURN')
    a.b(0xa1, 0x98, 0xcc, 0x2e, 0xa3); a.word('one_more_used')   # mov ax, [0CC98h] / mov cs:[one_more_used], ax
    a.b(0x2e, 0xc6, 0x06); a.word('one_more'); a.b(0x01)
    mend('ONEMORETURN')
    for name in ('HEREBEDRAGONS', 'DRAGONSLAYER'):           # the dragon alive again; the map set-up brings it
        mcase(name)
        a.b(0x80, 0x3e, (DRAGON_RECORD + 0x31) & 0xff, (DRAGON_RECORD + 0x31) >> 8, 0x00)   # cmp byte [6E57h], 0
        a.short(0x7f, f'cm_{name}_alive'); a.b(0xc6, 0x06, (DRAGON_RECORD + 0x31) & 0xff, (DRAGON_RECORD + 0x31) >> 8, 0x01)
        a.label(f'cm_{name}_alive')
        a.b(0xc7, 0x06, 0xb2, 0xcc, 0x00, 0x00, 0xc7, 0x06, 0xb0, 0xcc, 0x00, 0x00)   # [0CCB2h] = 0 (alive), [0CCB0h] = 0 (set up)
        a.b(0x83, 0x3e, 0xb1, 0x05, 0x00); a.short(0x75, f'cm_{name}_day'); a.b(0xc7, 0x06, 0xb1, 0x05, 0x01, 0x00)   # it flies from [05B1h] >= 1
        a.label(f'cm_{name}_day')
        if name == 'DRAGONSLAYER':
            a.b(0x89, 0x36, (DRAGON_RECORD + 0x46) & 0xff, (DRAGON_RECORD + 0x46) >> 8)   # mov [6E6Ch], si   this knight
        else:
            a.b(0xc7, 0x06, (DRAGON_RECORD + 0x46) & 0xff, (DRAGON_RECORD + 0x46) >> 8, 0x00, 0x00)   # none: a random one
        mend(name)
    mcase('FROGPRINCE')                                      # a frog for three days (as Math's), or a knight again
    a.b(0x80, 0x7c, 0x3a, 0x00); a.short(0x74, 'cm_frog'); a.b(0xc6, 0x44, 0x3a, 0x00)   # cmp byte [si+3Ah],0 / je / mov 0
    a.near(0xe9, 'cm_done')
    a.label('cm_frog')
    a.b(0xc6, 0x44, 0x3a, 0x03)
    mend('FROGPRINCE')
    mcase('BACKFORSECONDS'); mend('BACKFORSECONDS', LAIRS_SETUP)   # the new game's lair set-up (1000:1E2D) again
    mcase('SIRWALKSALOT'); a.b(0x2e, 0x80, 0x36); a.word('map_flags'); a.b(MAP_WALK); mend('SIRWALKSALOT')   # on / off
    mcase('SIRPICKSALOT'); a.b(0x2e, 0x80, 0x36); a.word('map_flags'); a.b(MAP_ANY_KEYS); mend('SIRPICKSALOT')
    mcase('IDROPPEDMYKEY')
    a.b(0x2e, 0xc6, 0x06); a.word('key_show'); a.b(0x01, 0x2e, 0xc6, 0x06); a.word('keys_shown'); a.b(0x01)
    mend('IDROPPEDMYKEY')
    mcase('BLACKDEATH')                                      # the computer's knights as the B key's Black Knights
    a.b(0x2e, 0xc6, 0x06); a.word('bd_on'); a.b(0x01)        # their fights: the TOOEASY rules (hard_flags)
    a.b(0x06, 0x8e, 0x46, 0x04)                              # push es / mov es, [bp+4]   MAIN's code segment
    for site, value in zip(BLACK_SITES, STRONG_BLACK):       # their fight colours black (+20h = 4)
        a.b(0x26, 0xc7, 0x06, site & 0xff, site >> 8, value & 0xff, value >> 8)
    a.b(0x07)
    for rec in KNIGHTS:
        a.b(0xbe, rec & 0xff, rec >> 8, 0x83, 0x7c, 0x20, 0x04); a.short(0x75, f'cm_bd_{rec:x}')   # mov si, rec / cmp word [si+20h], 4
        a.b(0xc6, 0x44, 0x2e, 5, 0xc6, 0x44, 0x2f, 5, 0xc6, 0x44, 0x30, 5)   # strength, constitution, endurance 5
        a.b(0xc7, 0x44, 0x42, 0x1e, 0x00)                    # battle armour
        a.b(0xc7, 0x44, 0x40, CLAYMORE, 0x00)                # the claymore (0279 arms a Sword of Sharpness it holds)
        a.b(0xc7, 0x44, 0x38, 0xe7, 0x03)                    # HP 999: 0279 brings it to the new max
        a.label(f'cm_bd_{rec:x}')
    mend('BLACKDEATH', RECALC)
    a.label('cm_done')
    a.b(0x5b, 0x5f, 0x5e, 0xf8, 0xc3)                        # pop bx di si / clc / ret

    # cheat_fight (from practice_frame, every frame of every fight): the fight codes; they stay on until typed
    # again (IDDQD: this fight only; one human knight in it)
    a.label('cheat_fight')
    a.near(0xe8, 'gore_lock')                                # call gore_lock   [Parental] gore_off_lock
    a.near(0xe8, 'hard_flags')                               # call hard_flags   TOOEASY, anticheese, Black Knights
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_ctx'); a.b(CHEAT_FIGHT)   # mov byte cs:[cheat_ctx], 2
    a.b(0x50, 0x53, 0x51)                                    # push ax bx cx
    a.b(0x2e, 0x80, 0x3e); a.word('dragon_ctl'); a.b(0x00); a.short(0x74, 'cf_no_hot')
    a.b(0x83, 0x26, 0x86, 0x77, 0xcf)                        # and word [7786h], 0FFCFh   no flight of its own
    a.near(0xe8, 'k1_away')                                  # knight 1 out of the fight (1-3 knights)
    a.label('cf_no_hot')
    a.near(0xe8, 'cheat_monster')                            # call cheat_monster
    a.near(0xe8, 'air_frame')                                # ROCKETMAN, LUNAR
    a.near(0xe8, 'mine_frame')                               # MINEFIELD
    a.near(0xe8, 'darts_frame')                              # D48: DARTS
    a.near(0xe8, 'df_frame')                                 # D49: DAGGERFALL
    a.near(0xe8, 'saber_finish')                             # D51: LIGHTSABER's deaths
    a.near(0xe8, 'score_frame')                              # D52: the practice score shown
    a.b(0x2e, 0x80, 0x3e); a.word('hard_eff'); a.b(0x00); a.short(0x74, 'cf_no_hard')
    a.b(0xc7, 0x06, 0xec, 0x77, 0x00, 0x00, 0xc7, 0x06, 0xee, 0x77, 0x00, 0x00)   # TOOEASY: [77ECh] = [77EEh] = 0
    a.label('cf_no_hard')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_FORE)   # test byte cs:[cheat_flags], FORE
    a.short(0x74, 'cf_pending')
    for t in KNIGHT_STRIKES:                                 # FORE: the knights' blows fling as a troll's
        a.b(0xc7, 0x06, (REACTIONS + t) & 0xff, (REACTIONS + t) >> 8, FLING & 0xff, FLING >> 8)
    a.label('cf_pending')
    a.b(0x2e, 0x80, 0x3e); a.word('fight_begun'); a.b(0x00); a.short(0x75, 'cf_begun')
    a.b(0x2e, 0xc6, 0x06); a.word('fight_begun'); a.b(0x01)
    a.near(0xe8, 'queue_apply')                              # the codes queued for this fight
    a.near(0xe8, 'score_start')                              # D52: the practice score
    a.label('cf_begun')
    a.near(0xe8, 'bars_frame')                               # D54: BEATEMUP's HP bars
    a.b(0x2e, 0xa0); a.word('cheat_pending')
    a.b(0x3c, 40); a.short(0x72, 'cf_out'); a.b(0x3c, 60); a.short(0x72, 'cf_code')
    a.label('cf_out')
    a.near(0xe9, 'cf_pop')
    a.label('cf_code')   # 40-59: a fight code
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_pending'); a.b(0x00)
    a.b(0x8a, 0xc8)                                          # mov cl, al   the code
    a.near(0xe8, 'fight_code'); a.near(0xe9, 'cf_pop')
    # humans_in_fight: cx = the human knights (+35h = 6, in the four knights' records) among the fight's figures
    a.label('humans_in_fight')
    a.b(0x53, 0x56, 0x52, 0x33, 0xc9)                        # push bx si dx / xor cx, cx
    a.b(0xbe, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xba, ANIM_COUNT, 0x00)   # mov si, 947Eh / mov dx, 10
    a.label('hif_loop')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'hif_next')         # cmp byte [si], 0 / je
    a.b(0x8b, 0x5c, 0x16)                                    # mov bx, [si+16h]
    a.b(0x81, 0xfb, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'hif_next')
    a.b(0x81, 0xfb, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8); a.short(0x77, 'hif_next')
    a.b(0x80, 0x7f, 0x35, 0x06); a.short(0x75, 'hif_next'); a.b(0x41)   # cmp byte [bx+35h], 6 / jne / inc cx
    a.label('hif_next')
    a.b(0x83, 0xc6, ANIM_SIZE, 0x4a); a.short(0x75, 'hif_loop')   # add si, 24h / dec dx / jnz
    a.b(0x5a, 0x5e, 0x5b, 0xc3)                              # pop dx si bx / ret

    # fight_code (cl = a fight code, ds = the game's): carries it out (a flag toggled, or the monsters' counts)
    a.label('fight_code')
    a.b(0x50)                                                # push ax
    for name, flag in (('ROCKETMAN', CF_ROCKET), ('JUSTFLESHWOUND', CF_FLESH), ('THERECANBEONLYONE', CF_ONLYONE),
                       ('ABACABB', CF_ABACABB), ('FINISHHIM', CF_FINISH), ('LUNAR', CF_LUNAR)):
        a.b(0x80, 0xf9, CHEAT_ID[name]); a.short(0x75, f'cf_n_{name}')
        a.b(0x2e, 0x80, 0x36); a.word('cheat_flags'); a.b(flag)   # xor byte cs:[cheat_flags], flag
        a.label(f'cf_n_{name}')
    for name, flag in (('DARTS', F2_DARTS), ('LIGHTSABER', F2_SABER), ('GUNSHOT', F2_GUNSHOT)):   # D48, D64: this fight
        a.b(0x80, 0xf9, CHEAT_ID[name]); a.short(0x75, f'cf_n_{name}')
        a.b(0x2e, 0x80, 0x36); a.word('cheat_flags2'); a.b(flag)   # xor byte cs:[cheat_flags2], flag
        a.label(f'cf_n_{name}')
    a.b(0x80, 0xf9, CHEAT_ID['BEATEMUP']); a.short(0x75, 'cf_n_bars')   # D54: the HP bars
    a.b(0x2e, 0xc6, 0x06); a.word('bars_on'); a.b(0x01)
    a.label('cf_n_bars')
    a.b(0x80, 0xf9, CHEAT_ID['DAGGERFALL']); a.short(0x75, 'cf_n_dfall')   # D48: daggers from the sky
    a.b(0x2e, 0xc6, 0x06); a.word('df_on'); a.b(0x01)
    a.b(0x50, 0xa1, RANDOM_STATE & 0xff, RANDOM_STATE >> 8, 0x2e, 0x33, 0x06); a.word('df_last')
    a.b(0x2e, 0xa3); a.word('df_rng'); a.b(0x58)            # seed the rain from the game's state and previous drop time
    a.label('cf_n_dfall')
    a.b(0x80, 0xf9, CHEAT_ID['MINEFIELD']); a.short(0x75, 'cf_n_mine')   # once a fight
    a.b(0x2e, 0x83, 0x3e); a.word('mine_live'); a.b(0x00); a.short(0x75, 'cf_n_mine')
    a.b(0x2e, 0xc6, 0x06); a.word('mine_req'); a.b(0x01)
    a.label('cf_n_mine')
    a.b(0x80, 0xf9, CHEAT_ID['FORE']); a.short(0x75, 'cf_n_fore')
    a.b(0x2e, 0x80, 0x36); a.word('cheat_flags'); a.b(CF_FORE)
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_FORE)
    a.short(0x75, 'cf_fore_on')
    for i, t in enumerate(KNIGHT_STRIKES):                   # off: the reactions as they were
        a.b(0x2e, 0xa1); a.word('fore_saved', 2 * i); a.b(0xa3, (REACTIONS + t) & 0xff, (REACTIONS + t) >> 8)
    a.short(0xeb, 'cf_n_fore')
    a.label('cf_fore_on')
    for i, t in enumerate(KNIGHT_STRIKES):                   # on: keep them
        a.b(0xa1, (REACTIONS + t) & 0xff, (REACTIONS + t) >> 8); a.b(0x2e, 0xa3); a.word('fore_saved', 2 * i)
    a.label('cf_n_fore')
    # IDDQD: every human knight against the monsters (co-op too); nothing while human knights fight each other
    # (no co-op and two or more of them in the fight)
    a.b(0x80, 0xf9, CHEAT_ID['IDDQD']); a.short(0x75, 'cf_n_iddqd')
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00); a.short(0x75, 'cf_iddqd')
    a.b(0x51); a.near(0xe8, 'humans_in_fight'); a.b(0x83, 0xf9, 0x02, 0x59); a.short(0x73, 'cf_n_iddqd')   # push cx / call / cmp cx, 2 / pop cx / jae
    a.label('cf_iddqd')
    a.b(0x2e, 0x80, 0x36); a.word('cheat_flags'); a.b(CF_IDDQD)
    a.label('cf_n_iddqd')
    a.b(0x80, 0xf9, CHEAT_ID['FAIRFIGHT']); a.short(0x75, 'cf_n_fair')   # all the monsters still to come, at once (up to 6)
    a.b(0xa1, 0x6a, 0x09, 0x03, 0x06, 0x6e, 0x09)            # mov ax, [096Ah] / add ax, [096Eh]
    a.b(0x3d, FAIR_MAX, 0x00); a.short(0x7e, 'cf_fair_set'); a.b(0xb8, FAIR_MAX, 0x00)   # cmp ax, 6 / jle / mov ax, 6
    a.label('cf_fair_set')
    a.b(0x3b, 0x06, 0x6c, 0x09); a.short(0x7e, 'cf_n_fair'); a.b(0xa3, 0x6c, 0x09)   # cmp ax, [096Ch] / jle / mov [096Ch], ax
    a.label('cf_n_fair')
    a.b(0x80, 0xf9, CHEAT_ID['YOUANDWHATARMY']); a.short(0x75, 'cf_army_no')   # twice as many in all: those to come and on screen
    a.b(0xa1, 0x6a, 0x09, 0x03, 0x06, 0x6e, 0x09, 0x01, 0x06, 0x6a, 0x09)   # mov ax,[096Ah] / add ax,[096Eh] / add [096Ah],ax
    a.label('cf_army_no')
    a.b(0x58, 0xc3)                                          # pop ax / ret
    a.label('cf_pop')
    a.near(0xe8, 'cheat_finish')                             # call cheat_finish
    a.b(0x59, 0x5b, 0x58, 0xc3)                              # pop cx bx ax / ret

    # queue_code (al = a fight code typed in the first menu, ah = 1, or on the map, ah = 2): noted for the next
    # practice fight (1) or the next fight of the game (2); the queued codes it clashes with are dropped
    a.label('queue_code')
    a.b(0x3c, CHEAT_ID['BEATEMUP']); a.short(0x75, 'qc_code'); a.b(0x80, 0xfc, 0x01); a.short(0x75, 'qc_code')   # D57: BEATEMUP in the first menu:
    a.b(0x2e, 0xc6, 0x06); a.word('bars_keep'); a.b(0x01)    # every practice fight from now on (until the game is started again)
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_pending'); a.b(0x00, 0xc3)
    a.label('qc_code')
    a.b(0x53, 0x2e, 0xc6, 0x06); a.word('cheat_pending'); a.b(0x00)   # push bx / the code used
    a.b(0x2e, 0x88, 0x26); a.word('q_where')                 # mov cs:[q_where], ah
    a.b(0x8a, 0xd8, 0x80, 0xeb, 40, 0x32, 0xff, 0xd1, 0xe3)  # mov bl, al / sub bl, 40 / xor bh, bh / shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('q_clear')                 # mov bx, cs:[bx+q_clear]   its bit, and those it clashes with
    a.b(0x2e, 0x21, 0x1e); a.word('q_codes')                 # and cs:[q_codes], bx   (bx = ~(clash))
    a.b(0x8a, 0xd8, 0x80, 0xeb, 40, 0x32, 0xff, 0xd1, 0xe3)
    a.b(0x2e, 0x8b, 0x9f); a.word('q_bit')                   # mov bx, cs:[bx+q_bit]
    a.b(0x2e, 0x09, 0x1e); a.word('q_codes')                 # or cs:[q_codes], bx
    a.b(0x5b, 0xc3)                                          # pop bx / ret
    # queue_apply (a fight's first frame): the codes queued for this kind of fight are carried out: a flag only if
    # it is off (and noted in q_added, turned off again at the fight's end), the others once
    a.label('queue_apply')
    a.b(0x2e, 0x83, 0x3e); a.word('q_codes'); a.b(0x00); a.short(0x75, 'qa_some'); a.b(0xc3)
    a.label('qa_some')
    a.b(0x50, 0x53, 0x51)                                    # push ax bx cx
    a.b(0xb0, 0x02, 0x83, 0x3e, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION); a.short(0x75, 'qa_kind')
    a.b(0xb0, 0x01)                                          # al = 1 practice, 2 the game
    a.label('qa_kind')
    a.b(0x2e, 0x3a, 0x06); a.word('q_where'); a.short(0x74, 'qa_this'); a.near(0xe9, 'qa_pop')   # not this kind: kept for the next
    a.label('qa_this')
    a.b(0x2e, 0x8b, 0x1e); a.word('q_codes'); a.b(0x2e, 0xc7, 0x06); a.word('q_codes'); a.b(0x00, 0x00)
    for i, name in enumerate(CHEAT_FIGHT_CODES):
        a.b(0xf7, 0xc3, (1 << i) & 0xff, (1 << i) >> 8); a.short(0x74, f'qa_n{i}')   # test bx, its bit
        if name in FIGHT_FLAGS:
            f = FIGHT_FLAGS[name]
            a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(f); a.short(0x75, f'qa_n{i}')   # on already
            a.b(0x2e, 0x80, 0x0e); a.word('q_added'); a.b(f)
        a.b(0xb1, CHEAT_ID[name]); a.near(0xe8, 'fight_code')
        a.label(f'qa_n{i}')
    a.label('qa_pop')
    a.b(0x59, 0x5b, 0x58, 0xc3)                              # pop cx bx ax / ret

    # cheat_finish (every fight frame): FINISHHIM / ABACABB: a human's knight that has just begun to slump after a
    # deadly blow (its animation's script 130E-1327, HP 0 or less) dies at once by that blow: pick_death's death
    # (D20); else FINISHHIM: the beheading after a knight's or a Black Knight's blow, ABACABB: the beheading always
    a.label('cheat_finish')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_FINISH | CF_ABACABB)
    a.short(0x75, 'fi_go')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_ENCHANT); a.b(0x00); a.short(0x75, 'fi_go'); a.b(0xc3)   # D35: Gore
    a.label('fi_go')
    a.b(0x50, 0x53, 0x51, 0x56, 0x57)                        # push ax bx cx si di
    a.b(0xbf, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8, 0xb9, 0x04, 0x00)   # mov di, 6C9Eh / mov cx, 4
    a.label('fi_loop')
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x75, 'fi_next')    # cmp byte [di+35h], 6 / jne   a human's
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7f, 'fi_next')    # cmp word [di+38h], 0 / jg    alive
    a.near(0xe8, 'anim_of'); a.short(0x75, 'fi_next')        # call anim_of / jnz
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_FINISH | CF_ABACABB); a.short(0x75, 'fi_code')
    a.near(0xe8, 'gore_victim'); a.short(0x75, 'fi_next')    # D35: else only a Gore sword's kill
    a.label('fi_code')
    a.b(0x8b, 0x47, 0x02, 0x3d, SLUMP & 0xff, SLUMP >> 8); a.short(0x72, 'fi_next')   # mov ax, [bx+2] / cmp ax, 130Eh / jb
    a.b(0x3d, (SLUMP + 0x1a) & 0xff, (SLUMP + 0x1a) >> 8); a.short(0x73, 'fi_next')   # cmp ax, 1328h / jae   lying already
    a.b(0xff, 0x36, 0xe8, 0x77, 0xff, 0x36, 0x3a, 0x78)      # push word [77E8h] / push word [783Ah]
    a.b(0x89, 0x3e, 0xe8, 0x77, 0xc7, 0x06, 0x3a, 0x78, BEHEADING & 0xff, BEHEADING >> 8)   # [77E8h] = it / [783Ah] = 1386h
    a.b(0x53); a.near(0xe8, 'pick_death'); a.b(0x5b)         # push bx / call pick_death / pop bx
    a.b(0xa1, 0x3a, 0x78)                                    # mov ax, [783Ah]   the death picked
    a.b(0x8f, 0x06, 0x3a, 0x78, 0x8f, 0x06, 0xe8, 0x77)      # pop word [783Ah] / pop word [77E8h]
    a.b(0x3d, BEHEADING & 0xff, BEHEADING >> 8); a.short(0x75, 'fi_set')   # cmp ax, 1386h / jne fi_set   a new death
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_ABACABB); a.short(0x75, 'fi_set')   # ABACABB: the beheading
    a.b(0x56, 0x53); a.near(0xe8, 'knight_slot')             # push si bx / call knight_slot   bx = its number * 2
    a.b(0x2e, 0x8a, 0xa7); a.word('last_strike', 1); a.b(0x5b, 0x5e)   # mov ah, cs:[bx+last_strike+1] / pop bx si   the type
    a.b(0x80, 0xfc, 0x06); a.short(0x74, 'fi_beheading')     # a knight's blow
    a.b(0x80, 0xfc, COMPUTER_TYPE); a.short(0x75, 'fi_next')
    a.label('fi_beheading')
    a.b(0xb8, BEHEADING & 0xff, BEHEADING >> 8)
    a.label('fi_set')
    a.near(0xe8, 'set_script')                               # call set_script   (bx = the animation)
    a.label('fi_next')
    a.b(0x83, 0xc7, SLOT_SIZE); a.short(0xe2, 'fi_loop')     # add di, 62h / loop fi_loop
    a.b(0x5f, 0x5e, 0x59, 0x5b, 0x58, 0xc3)                  # pop di si cx bx ax / ret

    # gore_victim (di = a knight): ZF = 1 if the last blow on it was a Gore knight's (hit_pair's last_hitter)
    a.label('gore_victim')
    a.b(0x50, 0x53, 0x56, 0x8b, 0xf7); a.near(0xe8, 'knight_slot')   # push ax bx si / mov si, di / bx = its number * 2
    a.b(0x2e, 0x8b, 0xb7); a.word('last_hitter'); a.b(0x0b, 0xf6); a.short(0x74, 'gv_no')
    a.near(0xe8, 'ench_of'); a.b(0x3c, E_GORE); a.short(0xeb, 'gv_end')
    a.label('gv_no')
    a.b(0x0c, 0x01)                                          # or al, 1   ZF = 0
    a.label('gv_end')
    a.b(0x5e, 0x5b, 0x58, 0xc3)
    # obj_index: si = an object -> bx = its number * 2 (knights 0-3, monster slots 4-23, the dragon 24), CF = 1 if none
    a.label('obj_index')
    a.b(0x50, 0x52, 0x8b, 0xc6, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # push ax dx / mov ax, si / sub ax, 6C9Eh
    a.short(0x72, 'oi_none')
    a.b(0x81, 0xfe, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8); a.short(0x73, 'oi_dragon')   # cmp si, 6E26h / jae
    a.b(0x33, 0xd2, 0xbb, SLOT_SIZE, 0x00, 0xf7, 0xf3)       # xor dx,dx / mov bx, 62h / div bx
    a.b(0x0b, 0xd2); a.short(0x74, 'oi_ok')                  # or dx, dx / jz oi_ok   a knight
    a.short(0xeb, 'oi_none')
    a.label('oi_dragon')
    a.short(0x75, 'oi_slot')                                 # jne oi_slot   (flags of cmp si, 6E26h)
    a.b(0xb8, 24, 0x00); a.short(0xeb, 'oi_ok')
    a.label('oi_slot')
    a.b(0x8b, 0xc6, 0x2d, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8); a.short(0x72, 'oi_none')   # mov ax, si / sub ax, 6F08h
    a.b(0x33, 0xd2, 0xbb, SLOT_SIZE, 0x00, 0xf7, 0xf3, 0x0b, 0xd2); a.short(0x75, 'oi_none')
    a.b(0x3d, MONSTER_COUNT, 0x00); a.short(0x73, 'oi_none')
    a.b(0x05, 0x04, 0x00)                                    # add ax, 4
    a.label('oi_ok')
    a.b(0xd1, 0xe0, 0x8b, 0xd8, 0x5a, 0x58, 0xf8, 0xc3)      # shl ax, 1 / mov bx, ax / pop dx ax / clc / ret
    a.label('oi_none')
    a.b(0x5a, 0x58, 0xf9, 0xc3)                              # pop dx ax / stc / ret

    # cheat_object (from update, every object's turn, si = it, di = its animation): the HP codes and ROCKETMAN.
    # A fall in HP since the object's last turn (prev_hp) is taken back (JUSTFLESHWOUND: the humans' knights;
    # IDDQD: the one human knight) or made a kill (THERECANBEONLYONE, anyone), but an instant kill (marked by
    # instant_kill, cheat_killed) stays
    a.label('cheat_object')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_CHEATS); a.b(0x00); a.short(0x75, 'co_on')
    a.b(0xc3)
    a.label('co_on')
    a.b(0x50, 0x53, 0x51, 0x52)                              # push ax bx cx dx
    a.near(0xe8, 'obj_index'); a.short(0x73, 'co_obj'); a.near(0xe9, 'co_pop')
    a.label('co_obj')
    a.b(0x8b, 0x44, 0x38, 0x2e, 0x8b, 0x8f); a.word('prev_hp')   # mov ax, [si+38h] / mov cx, cs:[bx+prev_hp]
    a.b(0x81, 0xf9, 0x00, 0x80); a.short(0x74, 'co_keep')   # cmp cx, 8000h / je   none yet
    a.b(0x3b, 0xc1); a.short(0x7d, 'co_keep')                # cmp ax, cx / jge   no fall
    a.b(0xd1, 0xfb, 0x2e, 0x80, 0xbf); a.word('cheat_killed'); a.b(0x00)   # sar bx, 1 / cmp byte cs:[bx+cheat_killed], 0
    a.b(0x9c, 0xd1, 0xe3, 0x9d); a.short(0x75, 'co_keep')    # pushf / shl bx, 1 / popf / jne   an instant kill
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_ONLYONE); a.short(0x74, 'co_flesh')
    a.b(0xb8, 0xff, 0xff); a.short(0xeb, 'co_set')           # mov ax, -1   one hit kills
    a.label('co_flesh')
    a.b(0x83, 0xfb, 0x08); a.short(0x73, 'co_keep')          # cmp bx, 8 / jae   not a knight
    a.b(0x80, 0x7c, 0x35, 0x06); a.short(0x75, 'co_keep')    # cmp byte [si+35h], 6 / jne   not a human's
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_FLESH | CF_IDDQD); a.short(0x75, 'co_undo')
    a.b(0x2e, 0x80, 0x3e); a.word('easy_eff'); a.b(0x00); a.short(0x74, 'co_keep')   # TOOHARD: half the fall
    a.b(0x8b, 0xd1, 0x2b, 0xd0, 0x42, 0xd1, 0xea)            # mov dx, cx / sub dx, ax / inc dx / shr dx, 1   half the loss, rounded up
    a.b(0x8b, 0xc1, 0x2b, 0xc2); a.short(0xeb, 'co_set')     # mov ax, cx / sub ax, dx
    a.label('co_undo')
    a.b(0x8b, 0xc1)                                          # mov ax, cx   the hit undone
    a.label('co_set')
    a.b(0x89, 0x44, 0x38)                                    # mov [si+38h], ax
    a.label('co_keep')
    a.b(0x2e, 0x89, 0x87); a.word('prev_hp')                 # mov cs:[bx+prev_hp], ax
    a.b(0xd1, 0xfb, 0x2e, 0xc6, 0x87); a.word('cheat_killed'); a.b(0x00, 0xd1, 0xe3)   # sar bx,1 / mov cs:[bx+killed],0 / shl bx,1
    # LUNAR: a blow sends the one hit flying a little away from the striker (a blow that flings: farther), by the
    # moon's gravity (air_frame); not a hold or the dragon's bite (the mudman, the Balok, the dragon strike), not
    # the dragon itself, not one that has fallen
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_LUNAR); a.short(0x74, 'co_pop')
    a.b(0x83, 0x7c, 0x0e, 0x00); a.short(0x74, 'co_pop')     # cmp word [si+0Eh], 0   not hit
    a.b(0x83, 0xfb, 48); a.short(0x73, 'co_pop')             # the dragon
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'co_pop')     # fallen
    a.b(0x57, 0x8b, 0x7c, 0x0e)                              # push di / mov di, [si+0Eh]   the striker
    for t in (MUDMAN, BALOK_TYPE, 0x0a):
        a.b(0x80, 0x7d, 0x35, t); a.short(0x74, 'co_kb_end')
    a.b(0xb2, KB_X, 0xb6, (-KB_Y) & 0xff)                    # mov dl, 2 / mov dh, -3
    a.b(0x53, 0x8b, 0x5c, 0x14, 0x03, 0x5d, 0x28)            # push bx / mov bx, [si+14h] / add bx, [di+28h]   its reaction
    a.b(0x81, 0x3f, FLING & 0xff, FLING >> 8, 0x5b); a.short(0x75, 'co_kb_dir')   # cmp word [bx], 1202h / pop bx / jne
    a.b(0xb2, KB_FLING_X, 0xb6, (-KB_FLING_Y) & 0xff)        # a fling: farther
    a.label('co_kb_dir')
    a.b(0x8b, 0x44, 0x02, 0x3b, 0x45, 0x02); a.short(0x7d, 'co_kb_set'); a.b(0xf6, 0xda)   # x >= the striker's: away right; neg dl
    a.label('co_kb_set')
    a.b(0xd1, 0xfb)                                          # sar bx, 1   the object's number
    a.b(0x2e, 0x88, 0x97); a.word('air_vx'); a.b(0x2e, 0x88, 0xb7); a.word('air_vy')   # mov cs:[bx+air_vx], dl / [bx+air_vy], dh
    a.b(0x2e, 0xc6, 0x87); a.word('air_on'); a.b(0x01, 0xd1, 0xe3)   # mov byte cs:[bx+air_on], 1 / shl bx, 1
    a.label('co_kb_end')
    a.b(0x5f)                                                # pop di
    a.label('co_pop')
    a.b(0x5a, 0x59, 0x5b, 0x58, 0xc3)                        # pop dx cx bx ax / ret

    # HOTSTUFF (typed in the first menu, then the D key's practice with 2-4 knights): player 1 is the dragon, the
    # other knights fight it. The dragon's update (1000:384F) runs when its move is over: its moves (3BF4) take
    # player 1's directions instead of the AI's (56E5, which sets +26h: 1 right, 2 left, 4 nearer, 8 farther, as a
    # knight's input bits), it makes no flights of its own (3886: on to the attacks), and its attack is the fire key
    # with a direction: forward (right) = the far fire (4092), forward and down = the near fire and its flame (4442,
    # 3B08), else the claw and bite (463A, which eats a knight it holds)
    a.label('rules_dragon_move')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x27, 0x3c)          # call_ret = 3C27h
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe5, 0x56)       # call_target = 56E5h (the AI)
    a.b(0x2e, 0x80, 0x3e); a.word('dragon_ctl'); a.b(0x00); a.short(0x74, 'dm_go')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)   # 83C0h: bx = player 1's bits
    a.label('dm_go')
    a.near(0xe9, 'call_game')
    a.label('rules_dragon_input')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('dragon_ctl'); a.b(0x00); a.short(0x74, 'di_end')
    a.b(0x50, 0x8b, 0x46, 0xfe)                              # push ax / mov ax, [bp-2]   83C0's bx
    a.b(0x2e, 0xa2); a.word('dragon_bits')                   # mov cs:[dragon_bits], al
    a.b(0x24, 0x0f)                                          # and al, 0Fh   the directions
    a.b(0x83, 0x7c, 0x06, DRAGON_Z_MIN); a.short(0x7f, 'di_far'); a.b(0x24, 0xf7)   # cmp word [si+6], 90 / jg / and al, ~8
    a.label('di_far')
    a.b(0x81, 0x7c, 0x06, DRAGON_Z_MAX & 0xff, DRAGON_Z_MAX >> 8); a.short(0x7c, 'di_near'); a.b(0x24, 0xfb)   # cmp word [si+6], 200 / jl / and al, ~4
    a.label('di_near')
    a.b(0x88, 0x44, 0x26, 0xc6, 0x44, 0x27, 0x00, 0x58)      # mov [si+26h], al / mov byte [si+27h], 0 / pop ax
    a.label('di_end')
    a.near(0xe9, 'rules_done')
    a.label('rules_dragon_range')
    a.b(0x2e, 0x80, 0x3e); a.word('dragon_ctl'); a.b(0x00); a.short(0x74, 'dr_ai')
    a.b(0xc7, 0x46, 0x02, 0xe6, 0x39)                        # mov word [bp+2], 39E6h   on to the attacks
    a.near(0xe9, 'rules_done')
    a.label('dr_ai')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe2, 0x3c)       # 3CE2h (replaced call)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x89, 0x38)
    a.near(0xe9, 'call_game')
    a.label('rules_dragon_attack')
    a.b(0x83, 0x26, 0x86, 0x77, 0xbf)                        # and word [7786h], 0FFBFh   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('dragon_ctl'); a.b(0x00); a.short(0x75, 'da_ctl')
    a.near(0xe9, 'rules_done')
    a.label('da_ctl')
    a.b(0xc7, 0x46, 0x02, 0xc0, 0x3b)                        # mov word [bp+2], 3BC0h   the update's end
    # a knight close in front of it (PAW_X, within PAW_Z in depth, as one steps up or down too): the paw at once,
    # whatever the keys say: the claw's swing as attack PAW_TYPE, which the knights take as a fling to the right
    # (a troll's blow: 1202h, the record 7818h), not the bite that eats
    a.b(0x50, 0x53, 0x51, 0x33, 0xc9)                        # push ax bx cx / xor cx, cx
    a.label('dp_loop')
    a.b(0x8b, 0xd9, 0xd1, 0xe3)                              # mov bx, cx / shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('knight_list')             # mov bx, cs:[bx+knight_list]
    a.b(0x83, 0x7f, 0x38, 0x00); a.short(0x7e, 'dp_next')    # cmp word [bx+38h], 0 / jle   down
    a.b(0x8b, 0x47, 0x02, 0x2b, 0x45, 0x02, 0x3d, PAW_X, 0x00); a.short(0x77, 'dp_next')   # x - its x above PAW_X (or behind)
    a.b(0x8b, 0x47, 0x06, 0x2b, 0x45, 0x06); a.short(0x79, 'dp_abs'); a.b(0xf7, 0xd8)
    a.label('dp_abs')
    a.b(0x3d, PAW_Z, 0x00); a.short(0x7f, 'dp_next')
    a.b(0xc7, 0x45, 0x28, PAW_TYPE, 0x00, 0xc7, 0x06, 0x3a, 0x78, 0x3a, 0x46)   # [di+28h] = 6 / [783Ah] = 463Ah
    a.b(0xc6, 0x06, 0x32, 0x78, 0x01, 0xc7, 0x06, 0x2e, 0x78, 0x18, 0x78)       # [7832h] = 1 (right) / [782Eh] = 7818h
    rx = REACTIONS + PAW_TYPE
    a.b(0x2e, 0x80, 0x3e); a.word('paw_set'); a.b(0x00); a.short(0x75, 'dp_set')
    a.b(0xa1, rx & 0xff, rx >> 8, 0x2e, 0xa3); a.word('paw_saved')   # the fight's own reaction, back at its end
    a.b(0x2e, 0xc6, 0x06); a.word('paw_set'); a.b(0x01)
    a.label('dp_set')
    a.b(0xc7, 0x06, rx & 0xff, rx >> 8, FLING & 0xff, FLING >> 8)
    a.b(0x59, 0x5b, 0x58); a.near(0xe9, 'rules_done')
    a.label('dp_next')
    a.b(0x41, 0x2e, 0x3a, 0x0e); a.word('coop'); a.short(0x72, 'dp_loop')   # inc cx / cmp cl, cs:[coop] / jb
    a.b(0x59, 0x5b, 0x58)                                    # pop cx bx ax
    a.b(0x50, 0x2e, 0xa0); a.word('dragon_bits')             # push ax / mov al, cs:[dragon_bits]
    a.b(0xa8, 0x10); a.short(0x74, 'da_pop')                 # test al, 10h / jz   no attack
    a.b(0x24, 0x05, 0x3c, 0x05); a.short(0x75, 'da_far')     # and al, 5 / cmp al, 5 / jne   forward and down?
    a.b(0xc7, 0x45, 0x28, 0x10, 0x00, 0xc7, 0x06, 0x3a, 0x78, 0x42, 0x44)   # [di+28h] = 10h / [783Ah] = 4442h   near fire
    a.b(0x83, 0x0e, 0x86, 0x77, 0x40, 0x58)                  # or word [7786h], 40h / pop ax
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x08, 0x3b)       # its flame: 3B08h, then 3BC0h
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xc0, 0x3b)
    a.near(0xe9, 'call_game')
    a.label('da_far')
    a.b(0x3c, 0x01); a.short(0x75, 'da_bite')                # forward alone
    a.b(0xc7, 0x06, 0xee, 0x77, 0x02, 0x00, 0xc7, 0x45, 0x28, 0x04, 0x00)   # [77EEh] = 2 / [di+28h] = 4
    a.b(0xc7, 0x06, 0x3a, 0x78, 0x92, 0x40); a.short(0xeb, 'da_pop')       # [783Ah] = 4092h   far fire
    a.label('da_bite')
    a.b(0x81, 0x26, 0x86, 0x77, 0x7f, 0xff, 0xc7, 0x45, 0x28, 0x02, 0x00)   # and [7786h], 0FF7Fh / [di+28h] = 2
    a.b(0xc7, 0x06, 0x3a, 0x78, 0x3a, 0x46)                  # [783Ah] = 463Ah   claw and bite
    a.label('da_pop')
    a.b(0x58)
    a.near(0xe9, 'rules_done')

    # hard_rest (TOOEASY, every object's turn, si = it): a monster (or the dragon) hit again within HARD_REST
    # ticks of its last counted hit does not flinch: the hit is dropped, as K6 does for the dragon and the Guardian
    # (its +0Eh, and the striker's +0Ch), so a knight can no longer keep it reeling with quick blows; it strikes back
    a.label('hard_rest')
    a.b(0x2e, 0x80, 0x3e); a.word('hard_eff'); a.b(0x00); a.short(0x75, 'hr2_on'); a.b(0xc3)
    a.label('hr2_on')
    a.b(0x83, 0x7c, 0x0e, 0x00); a.short(0x75, 'hr2_hit'); a.b(0xc3)   # cmp word [si+0Eh], 0 / jne   hit
    a.label('hr2_hit')
    a.b(0x50, 0x53, 0x52, 0x57, 0x06)                        # push ax bx dx di es
    a.near(0xe8, 'obj_index'); a.short(0x72, 'hr2_pop')      # call obj_index / jc
    a.b(0x83, 0xfb, 0x08); a.short(0x72, 'hr2_pop')          # cmp bx, 8 / jb   a knight: not this
    a.b(0x33, 0xd2, 0x8e, 0xc2, 0x26, 0x8b, 0x16, 0x6c, 0x04)   # xor dx, dx / mov es, dx / mov dx, es:[046Ch]
    a.b(0x2e, 0x8b, 0x87); a.word('hard_hit')                # mov ax, cs:[bx+hard_hit]
    a.b(0x0b, 0xc0); a.short(0x74, 'hr2_count')              # or ax, ax / jz   none yet
    a.b(0xf7, 0xd8, 0x03, 0xc2, 0x3d, HARD_REST, 0x00); a.short(0x72, 'hr2_drop')   # neg ax / add ax, dx / cmp ax, 6 / jb
    a.label('hr2_count')
    a.b(0x0b, 0xd2, 0x75, 0x01, 0x42)                        # or dx, dx / jnz +1 / inc dx   (0 = none)
    a.b(0x2e, 0x89, 0x97); a.word('hard_hit')                # mov cs:[bx+hard_hit], dx
    a.short(0xeb, 'hr2_pop')
    a.label('hr2_drop')
    a.b(0x8b, 0x7c, 0x0e, 0xc7, 0x44, 0x0e, 0x00, 0x00)      # mov di, [si+0Eh] / mov word [si+0Eh], 0
    a.b(0x39, 0x75, 0x0c); a.short(0x75, 'hr2_pop')          # cmp [di+0Ch], si / jne
    a.b(0xc7, 0x45, 0x0c, 0x00, 0x00)                        # mov word [di+0Ch], 0
    a.label('hr2_pop')
    a.b(0x07, 0x5f, 0x5a, 0x5b, 0x58, 0xc3)                  # pop es di dx bx ax / ret

    # DIRTYRAT (typed in a practice fight with 2-4 knights, one with ratmen): player 1's knight leaves the fight and
    # player 1 is a ratman (mon_obj, taken from the ratmen in the fight). The ratman's update (1000:30E4) decides at
    # 3150 when no move of its own is going on (its +48h/+49h modes, cleared for this one by cheat_monster): here the
    # keys (1000:83C0, called first and this site again): a direction = a leap that way (the ratmen's own way of
    # moving: the path record 77CCh, 2B99, then 326B as its own leap; shorter in time than the AI's), fire = its
    # swing (4, 3730h), fire and down = its thrust (2, 3642h), the secondary button = its leap up into the tree
    # (31B5, the AI's; in the tree: rat_tree), else it stands
    a.label('rules_rat_decide')
    a.b(0x8b, 0x3e, 0xe8, 0x77)                              # mov di, [77E8h]   the ratman
    a.b(0x2e, 0x3b, 0x3e); a.word('mon_obj'); a.short(0x74, 'rd_mine')   # cmp di, cs:[mon_obj] / je
    a.label('rd_ai')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xff, 0x3c)   # call 3CFF (replaced), on at 3153
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x53, 0x31)
    a.near(0xe9, 'call_game')
    a.label('rd_mine')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_have'); a.b(0x00); a.short(0x75, 'rd_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x01)     # first the keys: 83C0h, then here again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x50, 0x31)
    a.near(0xe9, 'call_game')
    a.label('rd_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x00)
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]   83C0's bx: player 1's bits
    a.b(0xa8, 0x01); a.short(0x74, 'rd_left'); a.b(0xc6, 0x45, 0x08, 0x01)   # right: faces right
    a.label('rd_left')
    a.b(0xa8, 0x02); a.short(0x74, 'rd_sec'); a.b(0xc6, 0x45, 0x08, 0x03)   # left: faces left
    a.label('rd_sec')
    a.b(0x50, 0xb0, 0x00); a.near(0xe8, 'sec_input'); a.b(0x58)   # the secondary button: up into the tree
    a.short(0x74, 'rd_fire')
    a.b(0x83, 0x3e, 0xae, 0x69, 0x00); a.short(0x74, 'rd_fire')   # cmp word [69AEh], 0 / je   no tree
    a.b(0xc7, 0x46, 0x02, 0xb5, 0x31); a.near(0xe9, 'rules_done')   # mov word [bp+2], 31B5h   its leap there
    a.label('rd_fire')
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d)                        # mov word [bp+2], 2D5Eh   the update's end
    a.b(0xa8, 0x10); a.short(0x74, 'rd_move')
    a.b(0xa8, 0x04); a.short(0x75, 'rd_thrust')
    a.b(0xc7, 0x45, 0x28, 0x04, 0x00, 0xc7, 0x06, 0x3a, 0x78, 0x30, 0x37)   # swing: [di+28h] = 4 / [783Ah] = 3730h
    a.near(0xe9, 'rules_done')
    a.label('rd_thrust')
    a.b(0xc7, 0x45, 0x28, 0x02, 0x00, 0xc7, 0x06, 0x3a, 0x78, 0x42, 0x36)   # thrust: 2 / 3642h
    a.near(0xe9, 'rules_done')
    a.label('rd_move')
    a.b(0xa8, 0x0f); a.short(0x75, 'rd_leap'); a.near(0xe9, 'rules_done')   # no direction: it stands
    a.label('rd_leap')
    a.b(0x53, 0x51, 0x52)                                    # push bx cx dx
    a.b(0x8b, 0x5d, 0x02, 0x8b, 0x4d, 0x06)                  # mov bx, [di+2] / mov cx, [di+6]   from here
    a.b(0xa8, 0x01); a.short(0x74, 'rl_l'); a.b(0x83, 0xc3, MON_LEAP_X)   # right: x + 30
    a.label('rl_l')
    a.b(0xa8, 0x02); a.short(0x74, 'rl_u'); a.b(0x83, 0xeb, MON_LEAP_X)   # left: x - 30
    a.label('rl_u')
    a.b(0xa8, 0x08); a.short(0x74, 'rl_d'); a.b(0x83, 0xe9, MON_LEAP_Z)   # up: farther
    a.label('rl_d')
    a.b(0xa8, 0x04); a.short(0x74, 'rl_clamp'); a.b(0x83, 0xc1, MON_LEAP_Z)   # down: nearer
    a.label('rl_clamp')
    for reg_cmp, lo, hi, name in ((0xfb, MON_X_MIN, MON_X_MAX, 'x'), (0xf9, MON_Z_MIN, MON_Z_MAX, 'z')):
        mov = 0xbb if reg_cmp == 0xfb else 0xb9
        a.b(0x81, reg_cmp, lo & 0xff, lo >> 8); a.short(0x7d, f'rl_{name}1'); a.b(mov, lo & 0xff, lo >> 8)
        a.label(f'rl_{name}1')
        a.b(0x81, reg_cmp, hi & 0xff, hi >> 8); a.short(0x7e, f'rl_{name}2'); a.b(mov, hi & 0xff, hi >> 8)
        a.label(f'rl_{name}2')
    # the path record as the AI fills it (1000:31E4): object, from x, z, height -20 (from the tree its height); to
    # x, z, ground; its steps (the AI's 0Eh, fewer: faster)
    a.b(0x89, 0x3e, 0xcc, 0x77, 0x8b, 0x45, 0x02, 0xa3, 0xd0, 0x77, 0x8b, 0x45, 0x06, 0xa3, 0xd2, 0x77)
    a.b(0x8b, 0x45, 0x04, 0x3d, 0xec, 0xff); a.short(0x7c, 'rl_high')   # mov ax, [di+4] / cmp ax, -20 / jl
    a.b(0xb8, 0xec, 0xff)                                    # mov ax, -20   from the ground as the AI's (31F6)
    a.label('rl_high')                                       # (from the tree: its height)
    a.b(0xa3, 0xd4, 0x77, 0x89, 0x1e, 0xd6, 0x77, 0x89, 0x0e, 0xd8, 0x77)
    a.b(0xc7, 0x06, 0xda, 0x77, 0x00, 0x00, 0xc7, 0x06, 0xdc, 0x77, RAT_LEAP_STEPS, 0x00)   # RAT_LEAP_STEPS (0Eh)
    a.b(0xc7, 0x06, 0xde, 0x77, 0x00, 0x00)
    a.b(0xc7, 0x45, 0x4a, 0x1e, 0x00)                        # mov word [di+4Ah], 1Eh
    a.b(0x5a, 0x59, 0x5b)                                    # pop dx cx bx
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x99, 0x2b)   # 2B99h, then 326Bh: the leap as its own
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x6b, 0x32)
    a.near(0xe9, 'call_game')

    # CLUBMEMBER (as DIRTYRAT, a practice with trolls; off the play area it walks back in first): player 1 is a troll. The troll's update (1000:55D0) decides
    # at 5605 (call 56E5, the AI's step: +26h as a knight's input bits, ax = 0 when it is close enough to strike):
    # here the keys (83C0, then this site again). A direction = a step that way (5608, the AI's own walk; left and
    # right also turn it), fire = its club swing (4, 5695: 5B50h and its fling), fire and down = its other blow
    # (10h, 56B5: 5B9Eh), else it stands
    a.label('rules_troll_decide')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   the troll
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x74, 'td_mine')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe5, 0x56)   # call 56E5 (replaced), on at 5608
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x08, 0x56)
    a.near(0xe9, 'call_game')
    a.label('td_mine')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_have'); a.b(0x00); a.short(0x75, 'td_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x01)     # first the keys: 83C0h, then here again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x05, 0x56)
    a.near(0xe9, 'call_game')
    a.label('td_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x00)
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]   player 1's bits
    # off the play area (beyond MON_X_MIN-MON_X_MAX; a troll stands off the screen's edge, x 400, as it strikes
    # from there): it walks back in by itself, whatever the direction keys (fire still strikes: a knight in its way
    # can keep it there), and never walks out
    a.b(0x81, 0x7c, 0x02, MON_X_MAX & 0xff, MON_X_MAX >> 8); a.short(0x7e, 'td_in_r')   # cmp word [si+2], 300 / jle
    a.b(0x25, 0x10, 0x00, 0x0c, 0x02); a.short(0xeb, 'td_in')   # and ax, 10h / or al, 2   left (fire kept)
    a.label('td_in_r')
    a.b(0x83, 0x7c, 0x02, MON_X_MIN); a.short(0x7d, 'td_in')   # cmp word [si+2], 10 / jge
    a.b(0x25, 0x10, 0x00, 0x0c, 0x01)                        # and ax, 10h / or al, 1   right (fire kept)
    a.label('td_in')
    a.b(0xa8, 0x01); a.short(0x74, 'td_left'); a.b(0xc6, 0x44, 0x08, 0x01)   # right: faces right
    a.label('td_left')
    a.b(0xa8, 0x02); a.short(0x74, 'td_fire'); a.b(0xc6, 0x44, 0x08, 0x03)   # left: faces left
    a.label('td_fire')
    a.b(0xa8, 0x10); a.short(0x74, 'td_move')
    a.b(0xc7, 0x46, 0x02, 0x95, 0x56)                        # mov word [bp+2], 5695h   the push (the club, a fling)
    a.b(0xa8, 0x08); a.short(0x74, 'td_done')                # up (and forward) + fire:
    a.b(0xc7, 0x46, 0x02, 0xb5, 0x56)                        # mov word [bp+2], 56B5h   the overhead blow
    a.label('td_done')
    a.near(0xe9, 'rules_done')
    a.label('td_move')
    a.b(0x24, 0x0f); a.short(0x75, 'td_step')
    a.b(0xc6, 0x44, 0x0a, 0x00, 0x8b, 0x44, 0x10, 0xa3, 0x3a, 0x78)   # mov byte [si+0Ah], 0 / mov ax, [si+10h] / mov [783Ah], ax
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d)                        # mov word [bp+2], 2D5Eh   it stands
    a.near(0xe9, 'rules_done')
    a.label('td_step')
    a.b(0x30, 0xe4, 0x89, 0x44, 0x26)                        # xor ah, ah / mov [si+26h], ax
    for v in (0x7bf5, 0x7bf7, 0x7bf9, 0x7bfb, 0x7bff):      # as 56E5 leaves them: no speed yet; 7BFFh: a depth step
        a.b(0xc7, 0x06, v & 0xff, v >> 8, 0x00, 0x00)
    a.b(0xa8, 0x0c); a.short(0x74, 'td_flat'); a.b(0xc7, 0x06, 0xff, 0x7b, 0x01, 0x00)
    a.label('td_flat')
    a.b(0xb8, 0x01, 0x00)                                    # mov ax, 1   a step
    a.b(0xc7, 0x46, 0x02, 0x08, 0x56)                        # mov word [bp+2], 5608h
    a.near(0xe9, 'rules_done')

    # sec_input (al = an input: 0 player 1's keys, 1 player 2's, 5 joystick A, 6 joystick B; [bp+4] = MAIN's CS):
    # ZF = 0 if its secondary button is down. Player 1: right Shift, player 2: left Shift, a controller: button 2
    # (rules.py: it no longer fires). Without the four separate inputs (multi) joystick A is also player 1's, B 2's
    a.label('sec_input')
    a.b(0x50, 0x53, 0x52, 0x06, 0x8e, 0x46, 0x04)            # push ax bx dx es / mov es, [bp+4]
    k = KEY_TABLE + 0x36
    a.b(0xb4, 0x20, 0xbb, k & 0xff, k >> 8)                  # mov ah, 20h / mov bx, 81E3h + 36h   right Shift
    a.b(0x3c, 0x01); a.short(0x75, 'si_a')
    k = KEY_TABLE + 0x2a
    a.b(0xb4, 0x80, 0xbb, k & 0xff, k >> 8)                  # mov ah, 80h / mov bx, 81E3h + 2Ah   left Shift
    a.label('si_a')
    a.b(0x3c, JOY_A_CONTROL); a.short(0x75, 'si_b'); a.b(0xb4, 0x20); a.short(0xeb, 'si_joy')
    a.label('si_b')
    a.b(0x3c, JOY_B_CONTROL); a.short(0x75, 'si_k3'); a.b(0xb4, 0x80); a.short(0xeb, 'si_joy')
    a.label('si_k3')
    a.b(0x3c, KEYS3_CONTROL); a.short(0x75, 'si_keys')
    a.b(0x26, 0x80, 0x3e, (KEY_TABLE + KEYS3_SECONDARY) & 0xff, (KEY_TABLE + KEYS3_SECONDARY) >> 8, 0xff)
    a.short(0x75, 'si_yes'); a.short(0xeb, 'si_no')          # N
    a.label('si_keys')
    a.b(0x26, 0x80, 0x3f, 0xff); a.short(0x75, 'si_yes')     # cmp byte es:[bx], 0FFh / jne   down
    a.b(0x2e, 0x83, 0x3e); a.word('multi'); a.b(0x00); a.short(0x75, 'si_no')
    a.b(0x2e, 0x80, 0x3e); a.word('joy_own'); a.b(0x00); a.short(0x75, 'si_no')
    a.label('si_joy')
    a.b(0xba, 0x01, 0x02, 0xec, 0x84, 0xc4); a.short(0x74, 'si_yes')   # mov dx, 201h / in al, dx / test ah, al / jz
    a.label('si_no')
    a.b(0x33, 0xc0); a.short(0xeb, 'si_pop')                 # xor ax, ax   ZF = 1
    a.label('si_yes')
    a.b(0xb0, 0x01, 0x0a, 0xc0)                              # mov al, 1 / or al, al   ZF = 0
    a.label('si_pop')
    a.b(0x07, 0x5a, 0x5b, 0x58, 0xc3)                        # pop es dx bx ax / ret

    # JUMPSCARE (as DIRTYRAT, a practice with Baloks): player 1 is a Balok. The Balok's update (1000:35A5) decides
    # at 35EC once no jump, hit or hold of its own is going on: here the keys (83C0, then this site again). The
    # Balok moves only by jumps (the path record 77CCh, 2B0A, then 3681 as its own jump): a direction = a hop that
    # way (left and right also turn it; up and down farther and nearer); a hop up or down crushes a knight it comes
    # down on, as the computer's Balok does (balok_land), one only left or right does not; fire = its swing (4,
    # 363A: 4A0Ah and its fling); fire and down = its grab (10h, 3659: 4A8Eh, then its bite or squeeze as the
    # game's); the secondary button = with a knight in front within BALOK_GRAB_X (level within BALOK_GRAB_Z) the
    # same grab, and the knight it holds is crushed to death (balok_crush); else its big jump forward (up or down:
    # also farther or nearer), which crushes a knight it comes down on
    a.label('rules_balok_decide')
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x74, 'bd_mine')   # cmp si, cs:[mon_obj] / je
    a.b(0x83, 0x7d, 0x38, 0x00)                              # cmp word [di+38h], 0   (replaced)
    a.near(0xe9, 'rules_flags')
    a.label('bd_mine')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_have'); a.b(0x00); a.short(0x75, 'bd_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x01)     # first the keys: 83C0h, then here again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xec, 0x35)
    a.near(0xe9, 'call_game')
    a.label('bd_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x00)
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]   player 1's bits
    a.b(0xa8, 0x01); a.short(0x74, 'bd_left'); a.b(0xc6, 0x44, 0x08, 0x01)   # right: faces right
    a.label('bd_left')
    a.b(0xa8, 0x02); a.short(0x74, 'bd_sec'); a.b(0xc6, 0x44, 0x08, 0x03)    # left: faces left
    a.label('bd_sec')
    a.b(0x50, 0xb0, 0x00); a.near(0xe8, 'sec_input'); a.b(0x58)   # push ax / mov al, 0 / call sec_input / pop ax
    a.short(0x74, 'bd_fire')
    a.b(0x57)                                                # push di
    a.b(0x2e, 0xc7, 0x06); a.word('nk_rx'); a.b(BALOK_GRAB_X, 0x00)
    a.b(0x2e, 0xc7, 0x06); a.word('nk_rz'); a.b(BALOK_GRAB_Z, 0x00)
    a.near(0xe8, 'nearest_knight')                           # call nearest_knight   di
    a.b(0x0b, 0xff); a.short(0x74, 'bd_big')                 # or di, di / jz   none near: the big jump
    a.b(0x8b, 0x5d, 0x02, 0x3b, 0x5c, 0x02, 0xb3, 0x01)      # mov bx, [di+2] / cmp bx, [si+2] / mov bl, 1
    a.short(0x7d, 'bd_side'); a.b(0xb3, 0x03)                # jge / mov bl, 3   the side it is on
    a.label('bd_side')
    a.b(0x38, 0x5c, 0x08); a.short(0x75, 'bd_big')           # cmp [si+8], bl / jne   behind it: the big jump
    a.b(0x5f)                                                # pop di
    a.b(0x2e, 0xc6, 0x06); a.word('mon_crush'); a.b(0x01)    # the crushing grab
    a.b(0xc7, 0x46, 0x02, 0x59, 0x36)                        # mov word [bp+2], 3659h   the grab
    a.near(0xe9, 'rules_done')
    a.label('bd_big')
    a.b(0x5f)                                                # pop di
    a.b(0x2e, 0xc6, 0x06); a.word('mon_jump'); a.b(0x01)     # the big jump: it crushes a knight below
    a.b(0x53, 0x51, 0x52, 0x8b, 0x5c, 0x02, 0x8b, 0x4c, 0x06)   # push bx cx dx / mov bx, [si+2] / mov cx, [si+6]
    a.b(0x80, 0x7c, 0x08, 0x01); a.short(0x75, 'bj_l')       # cmp byte [si+8], 1 / jne   forward:
    a.b(0x83, 0xc3, BALOK_JUMP_X); a.short(0xeb, 'bj_z')     # add bx, 100
    a.label('bj_l')
    a.b(0x83, 0xeb, BALOK_JUMP_X)                            # sub bx, 100
    a.label('bj_z')
    a.b(0xa8, 0x08); a.short(0x74, 'bj_d'); a.b(0x83, 0xe9, BALOK_JUMP_Z)   # up: farther
    a.label('bj_d')
    a.b(0xa8, 0x04); a.short(0x74, 'bj_go'); a.b(0x83, 0xc1, BALOK_JUMP_Z)  # down: nearer
    a.label('bj_go')
    a.near(0xe9, 'bd_launch')
    a.label('bd_fire')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_crush'); a.b(0x00)
    a.b(0xa8, 0x10); a.short(0x74, 'bd_move')
    a.b(0xc7, 0x46, 0x02, 0x3a, 0x36)                        # mov word [bp+2], 363Ah   the swing
    a.b(0xa8, 0x04); a.short(0x74, 'bd_done')
    a.b(0xc7, 0x46, 0x02, 0x59, 0x36)                        # mov word [bp+2], 3659h   the grab
    a.label('bd_done')
    a.near(0xe9, 'rules_done')
    a.label('bd_move')
    a.b(0xa8, 0x0f); a.short(0x75, 'bd_hop')
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d)                        # mov word [bp+2], 2D5Eh   it stands
    a.near(0xe9, 'rules_done')
    a.label('bd_hop')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_jump'); a.b(0x00)     # only left or right: no crush
    a.b(0xa8, 0x0c); a.short(0x74, 'bd_flat')                # test al, 0Ch / jz   up or down:
    a.b(0x2e, 0xc6, 0x06); a.word('mon_jump'); a.b(0x01)     # it crushes a knight it comes down on
    a.label('bd_flat')
    a.b(0x53, 0x51, 0x52, 0x8b, 0x5c, 0x02, 0x8b, 0x4c, 0x06)
    a.b(0xa8, 0x01); a.short(0x74, 'bh_l'); a.b(0x83, 0xc3, BALOK_HOP_X)
    a.label('bh_l')
    a.b(0xa8, 0x02); a.short(0x74, 'bh_u'); a.b(0x83, 0xeb, BALOK_HOP_X)
    a.label('bh_u')
    a.b(0xa8, 0x08); a.short(0x74, 'bh_d'); a.b(0x83, 0xe9, BALOK_HOP_Z)
    a.label('bh_d')
    a.b(0xa8, 0x04); a.short(0x74, 'bd_launch'); a.b(0x83, 0xc1, BALOK_HOP_Z)
    a.label('bd_launch')                                     # bx, cx = where to; pushed bx cx dx
    for reg_cmp, lo, hi, name in ((0xfb, MON_X_MIN, MON_X_MAX, 'x'), (0xf9, MON_Z_MIN, MON_Z_MAX, 'z')):
        mov = 0xbb if reg_cmp == 0xfb else 0xb9
        a.b(0x81, reg_cmp, lo & 0xff, lo >> 8); a.short(0x7d, f'bl_{name}1'); a.b(mov, lo & 0xff, lo >> 8)
        a.label(f'bl_{name}1')
        a.b(0x81, reg_cmp, hi & 0xff, hi >> 8); a.short(0x7e, f'bl_{name}2'); a.b(mov, hi & 0xff, hi >> 8)
        a.label(f'bl_{name}2')
    # the path record as the AI fills it (1000:2A9A): object, from x, z, height; to x, z, ground; landing +5Ch/+5Eh
    a.b(0x89, 0x36, 0xcc, 0x77, 0x8b, 0x44, 0x02, 0xa3, 0xd0, 0x77, 0x8b, 0x44, 0x06, 0xa3, 0xd2, 0x77)
    a.b(0x8b, 0x44, 0x04, 0xa3, 0xd4, 0x77, 0x89, 0x1e, 0xd6, 0x77, 0x89, 0x0e, 0xd8, 0x77)
    a.b(0xc7, 0x06, 0xda, 0x77, 0x00, 0x00, 0x89, 0x5c, 0x5c, 0x89, 0x4c, 0x5e)
    a.b(0x5a, 0x59, 0x5b)                                    # pop dx cx bx
    a.b(0xc6, 0x44, 0x49, 0x00, 0x8b, 0xfe)                  # mov byte [si+49h], 0   no pause / mov di, si
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x0a, 0x2b)   # 2B0Ah (the path's steps), then 3681h: its jump
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x81, 0x36)
    a.near(0xe9, 'call_game')

    # balok_land (1000:3711, mov si,[77E8h]: the Balok's jump on its way down, low enough; the game then kills its
    # knight within 10 in x): after a hop up or down or its big jump (mon_jump), player 1's Balok crushes the
    # knight it comes down on (any knight within BALOK_REACH_X in x and BALOK_REACH_Z in depth), as the game's
    # (371D: on it, the sound, 0AB2 for [0978h]); one a jump. The
    # dragon or the Guardian there takes one blow of the Balok's (its +0Eh) instead of dying
    a.label('rules_balok_land')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   (replaced)
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x74, 'bk_mine')
    a.label('bk_game')
    a.near(0xe9, 'rules_done')
    a.label('bk_mine')
    a.b(0xc7, 0x46, 0x02, 0x5a, 0x37)                        # mov word [bp+2], 375Ah   no kill
    a.b(0x2e, 0x80, 0x3e); a.word('mon_jump'); a.b(0x00); a.short(0x75, 'bk_scan')
    a.near(0xe9, 'rules_done')
    a.label('bk_scan')
    a.b(0x50, 0x53, 0x51, 0x33, 0xc9)                        # push ax bx cx / xor cx, cx
    a.label('bk_loop')
    a.b(0x8b, 0xd9, 0xd1, 0xe3)                              # mov bx, cx / shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('knight_list')             # mov bx, cs:[bx+knight_list]
    a.near(0xe8, 'bk_near'); a.short(0x74, 'bk_knight')
    a.b(0x41, 0x2e, 0x3a, 0x0e); a.word('coop'); a.short(0x72, 'bk_loop')   # inc cx / cmp cl, cs:[coop] / jb
    a.b(0xbb, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8, 0x83, 0x3f, 0x00); a.short(0x74, 'bk_slots')
    a.near(0xe8, 'bk_near'); a.short(0x74, 'bk_big')
    a.label('bk_slots')
    a.b(0xbb, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00)
    a.label('bk_sl')
    a.b(0x83, 0x3f, 0x00); a.short(0x74, 'bk_next')
    a.b(0x80, 0x7f, 0x35, GUARDIAN_TYPE); a.short(0x75, 'bk_next')
    a.near(0xe8, 'bk_near'); a.short(0x74, 'bk_big')
    a.label('bk_next')
    a.b(0x83, 0xc3, SLOT_SIZE); a.short(0xe2, 'bk_sl')
    a.short(0xeb, 'bk_pop')
    a.label('bk_knight')                                     # the game's kill of its knight: this one
    a.b(0x89, 0x1e, 0x78, 0x09, 0x89, 0x1e, 0xea, 0x77, 0x8b, 0xfb)   # mov [0978h], bx / mov [77EAh], bx / mov di, bx
    a.b(0xc7, 0x46, 0x02, 0x1d, 0x37)                        # mov word [bp+2], 371Dh
    a.short(0xeb, 'bk_one')
    a.label('bk_big')
    a.b(0x89, 0x77, 0x0e)                                    # mov [bx+0Eh], si   hit by the Balok
    a.label('bk_one')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_jump'); a.b(0x00)     # one kill or blow a jump
    a.label('bk_pop')
    a.b(0x59, 0x5b, 0x58)
    a.near(0xe9, 'rules_done')
    a.label('bk_near')                                       # bx = an object: ZF = 1 if standing and under the Balok
    a.b(0x83, 0x7f, 0x38, 0x00); a.short(0x7e, 'bn_no')      # cmp word [bx+38h], 0 / jle
    for off, reach in ((2, BALOK_REACH_X), (6, BALOK_REACH_Z)):
        a.b(0x8b, 0x47, off, 0x2b, 0x44, off); a.short(0x79, f'bn_abs{off}'); a.b(0xf7, 0xd8)   # mov ax,[bx+o] / sub ax,[si+o] / neg
        a.label(f'bn_abs{off}')
        a.b(0x3d, reach, 0x00); a.short(0x7f, 'bn_no')       # cmp ax, reach / jg
    a.b(0x33, 0xc0, 0xc3)                                    # xor ax, ax / ret   ZF = 1
    a.label('bn_no')
    a.b(0x0c, 0x01, 0xc3)                                    # or al, 1 / ret     ZF = 0

    # balok_crush (1000:37FC, mov di,[0978h]: the Balok has shaken the knight it holds; it dies if its HP are gone,
    # else it is let go): after player 1's crushing grab (the secondary button) the knight held has none left
    a.label('rules_balok_crush')
    a.b(0x8b, 0x3e, 0x78, 0x09)                              # mov di, [0978h]   (replaced)
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x75, 'bc_end')   # cmp si, cs:[mon_obj] / jne
    a.b(0x2e, 0x80, 0x3e); a.word('mon_crush'); a.b(0x00); a.short(0x74, 'bc_end')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_crush'); a.b(0x00)
    a.b(0xc7, 0x45, 0x38, 0x00, 0x00)                        # mov word [di+38h], 0   37CD: its bite or squeeze
    a.label('bc_end')
    a.near(0xe9, 'rules_done')

    # TROGLIFE (as DIRTYRAT; one of the trogg lairs at random): player 1 is a trogg (types 0Ch, 0Eh, 10h; handler
    # 1000:2DEB). It decides at 2E19 (call 56E5, the AI's step): here the keys. A direction = a step that way (2E37,
    # the AI's own walk; left and right also turn it); fire = its blow (4, the script at +4 of its type's table
    # [si+16h]); fire and down = its other blow (10h, at +10h); the spear troggs (10h) have the one thrust (2, 2432h)
    a.label('rules_trogg_decide')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x74, 'tg_mine')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe5, 0x56)   # call 56E5 (replaced), on at 2E1C
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x1c, 0x2e)
    a.near(0xe9, 'call_game')
    a.label('tg_mine')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_have'); a.b(0x00); a.short(0x75, 'tg_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x01)
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x19, 0x2e)
    a.near(0xe9, 'call_game')
    a.label('tg_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x00)
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]   player 1's bits
    a.b(0xa8, 0x01); a.short(0x74, 'tg_left'); a.b(0xc6, 0x44, 0x08, 0x01)   # right: faces right
    a.label('tg_left')
    a.b(0xa8, 0x02); a.short(0x74, 'tg_faced'); a.b(0xc6, 0x44, 0x08, 0x03)  # left: faces left
    a.label('tg_faced')
    a.b(0xa8, 0x10); a.short(0x74, 'tg_move')
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d, 0x8b, 0x7c, 0x16)      # mov word [bp+2], 2D5Eh / mov di, [si+16h]
    a.b(0x80, 0x7c, 0x35, 0x10); a.short(0x75, 'tg_blow')    # cmp byte [si+35h], 10h   a spear trogg
    a.b(0xc7, 0x44, 0x28, 0x02, 0x00, 0xc7, 0x06, 0x3a, 0x78, 0x32, 0x24)   # [si+28h] = 2 / [783Ah] = 2432h
    a.near(0xe9, 'rules_done')
    a.label('tg_blow')
    a.b(0xa8, 0x08); a.short(0x75, 'tg_other')               # up (and forward) + fire: the overhead blow (10h)
    a.b(0xc7, 0x44, 0x28, 0x04, 0x00, 0x8b, 0x45, 0x04)      # [si+28h] = 4 / mov ax, [di+4]
    a.short(0xeb, 'tg_script')
    a.label('tg_other')
    a.b(0xc7, 0x44, 0x28, 0x10, 0x00, 0x8b, 0x45, 0x10)      # [si+28h] = 10h / mov ax, [di+10h]
    a.label('tg_script')
    a.b(0xa3, 0x3a, 0x78); a.near(0xe9, 'rules_done')        # mov [783Ah], ax
    a.label('tg_move')
    a.b(0x24, 0x0f); a.short(0x75, 'tg_step')
    a.b(0xc6, 0x44, 0x0a, 0x00, 0xc7, 0x46, 0x02, 0x5e, 0x2d)   # mov byte [si+0Ah], 0 / [bp+2] = 2D5Eh   it stands
    a.near(0xe9, 'rules_done')
    a.label('tg_step')
    a.b(0x30, 0xe4, 0x89, 0x44, 0x26)                        # xor ah, ah / mov [si+26h], ax
    for v in (0x7bf5, 0x7bf7, 0x7bf9, 0x7bfb):              # as 56E5 leaves them
        a.b(0xc7, 0x06, v & 0xff, v >> 8, 0x00, 0x00)
    a.b(0xc7, 0x46, 0x02, 0x37, 0x2e)                        # mov word [bp+2], 2E37h   the walk
    a.near(0xe9, 'rules_done')

    # SWAMPTHING (as DIRTYRAT, the mudmen's lair): player 1 is a mudman (type 2; handler 1000:52FA). It decides at
    # 5363 (call 56E5) once it is up and holds no one: here the keys. A direction = a step (538B, its own walk);
    # fire = its blow (546E: 55C4h; a knight it hits it holds MUD_HOLD updates, the game's 40 for its own, and pulls
    # under unless the knight breaks free with fire and down); the secondary button (or fire and down) = it sinks
    # into the mud (54B2) and comes up beside the nearest knight (mud_rise) and pulls it under
    a.label('rules_mud_decide')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x74, 'md_mine')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe5, 0x56)   # call 56E5 (replaced), on at 5366
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x66, 0x53)
    a.near(0xe9, 'call_game')
    a.label('md_mine')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_have'); a.b(0x00); a.short(0x75, 'md_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x01)
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x63, 0x53)
    a.near(0xe9, 'call_game')
    a.label('md_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x00)
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]   player 1's bits
    a.b(0xa8, 0x01); a.short(0x74, 'md_left'); a.b(0xc6, 0x44, 0x08, 0x01)   # right: faces right
    a.label('md_left')
    a.b(0xa8, 0x02); a.short(0x74, 'md_faced'); a.b(0xc6, 0x44, 0x08, 0x03)  # left: faces left
    a.label('md_faced')
    a.b(0x50, 0xb0, 0x00); a.near(0xe8, 'sec_input'); a.b(0x58)   # the secondary button?
    a.short(0x75, 'md_sink')
    a.b(0x50, 0x24, 0x14, 0x3c, 0x14, 0x58); a.short(0x75, 'md_fire')   # fire and down?
    a.label('md_sink')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_dive'); a.b(0x01)     # its own dive: the grab from below may follow
    a.b(0xc7, 0x46, 0x02, 0xb2, 0x54); a.near(0xe9, 'rules_done')   # mov word [bp+2], 54B2h
    a.label('md_fire')
    a.b(0xa8, 0x10); a.short(0x74, 'md_move')
    a.b(0xc7, 0x46, 0x02, 0x6e, 0x54); a.near(0xe9, 'rules_done')   # mov word [bp+2], 546Eh   its blow
    a.label('md_move')
    a.b(0x24, 0x0f); a.short(0x75, 'md_step')
    a.b(0xc6, 0x44, 0x0a, 0x00, 0xc7, 0x46, 0x02, 0x5e, 0x2d)   # it stands
    a.near(0xe9, 'rules_done')
    a.label('md_step')
    a.b(0x30, 0xe4, 0x89, 0x44, 0x26)                        # mov [si+26h], ax
    for v in (0x7bf5, 0x7bf7):
        a.b(0xc7, 0x06, v & 0xff, v >> 8, 0x00, 0x00)
    a.b(0xc7, 0x46, 0x02, 0x8b, 0x53)                        # mov word [bp+2], 538Bh   the walk
    a.near(0xe9, 'rules_done')

    # mud_escape (1000:550A, call 83C0 while a mudman holds a knight: fire and down breaks free): the game reads
    # player 1's keys, the right ones only for knight 1. In co-op the knight held ([77EAh]) breaks free by its own
    # input (+9: 1 player 2, 5 joystick A, 6 joystick B, 7 the third key set); so player 1 as a mudman cannot let
    # its knight go
    # SWAMPTHING: player 1's mudman (si) holds a knight MUD_HOLD of its updates at most ([si+0Bh], 40 at 55B1)
    a.label('rules_mud_escape')
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x75, 'held_keys')   # cmp si, cs:[mon_obj] / jne
    a.b(0x80, 0x7c, 0x0b, MUD_HOLD); a.short(0x76, 'held_keys')   # cmp byte [si+0Bh], MUD_HOLD / jbe
    a.b(0xc6, 0x44, 0x0b, MUD_HOLD)                          # mov byte [si+0Bh], MUD_HOLD
    # held_keys (a call 83C0 as the knight a monster holds may break free: [bp+2] = the site + 2): the input of
    # that knight ([77EAh]), as mud_escape above
    a.label('held_keys')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x50, 0x8b, 0x46, 0x02)                              # push ax / mov ax, [bp+2]
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00); a.short(0x75, 'me_coop')
    a.b(0x40); a.short(0xeb, 'me_ret')                       # inc ax   (replaced) on after the call
    a.label('me_coop')
    a.b(0x2e, 0x80, 0x3e); a.word('mh_have'); a.b(0x00); a.short(0x75, 'me_keys_pop')
    a.b(0x2e, 0xc6, 0x06); a.word('mh_have'); a.b(0x01)
    a.b(0x48, 0x48)                                          # dec ax / dec ax   83C0, then this site again
    a.label('me_ret')
    a.b(0x2e, 0xa3); a.word('call_ret'); a.b(0x58)           # mov cs:[call_ret], ax / pop ax
    a.near(0xe9, 'call_game')
    a.label('me_keys_pop')
    a.b(0x58)                                                # pop ax
    a.label('me_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mh_have'); a.b(0x00)
    a.b(0x56, 0x51, 0x8b, 0x36, 0xea, 0x77, 0x8a, 0x4c, 0x09)   # push si cx / mov si, [77EAh] / mov cl, [si+9]
    a.b(0x80, 0xf9, 0x01); a.short(0x74, 'me_set')           # 1: player 2's, ax
    a.b(0x80, 0xf9, JOY_A_CONTROL); a.short(0x75, 'me_b'); a.b(0x2e, 0xa1); a.word('joy_a'); a.short(0xeb, 'me_set')
    a.label('me_b')
    a.b(0x80, 0xf9, JOY_B_CONTROL); a.short(0x75, 'me_k3'); a.b(0x2e, 0xa1); a.word('joy_b'); a.short(0xeb, 'me_set')
    a.label('me_k3')
    a.b(0x80, 0xf9, KEYS3_CONTROL); a.short(0x75, 'me_pop'); a.near(0xe8, 'keys3_bits')
    a.label('me_set')
    a.b(0x89, 0x46, 0xfe)                                    # mov [bp-2], ax   returned as bx
    a.label('me_pop')
    a.b(0x59, 0x5e); a.near(0xe9, 'rules_done')              # pop cx si

    # keys3_bits ([bp+4] = MAIN's CS): ax = the third key set's bits, as 1000:83C0 makes them
    a.label('keys3_bits')
    a.b(0x06, 0x8e, 0x46, 0x04, 0x33, 0xc0)                  # push es / mov es, [bp+4] / xor ax, ax
    fire, dirs = PLAYER_KEYS[2]
    for scan, bit in ((fire, 0x10),) + dirs:
        a.b(0x26, 0x80, 0x3e, (KEY_TABLE + scan) & 0xff, (KEY_TABLE + scan) >> 8, 0xff, 0x74, 0x02, 0x0c, bit)
    a.b(0x07, 0xc3)                                          # pop es / ret

    # hard_step (TOOEASY; 1000:573B, mov bp,[si+54h] in the AI's step 56E5 of the trolls, troggs, mudmen, the
    # Guardian and the computer knights; si = it, di = its knight): the common cheese was to step up or down and
    # strike as the monster came level: off its level but within its striking range in x ([si+52h]) the step
    # moved it only in depth, into the knight's blade. Now, off its knight's level, it keeps HARD_KEEP beyond its
    # striking range in x (backing off when nearer) while it moves to that level, and comes in only when level
    # (then as the game: in range, it strikes)
    # (from troll_back, K26's hook at this site, which sets the game's bp)
    a.label('hard_step')
    a.b(0x50)                                                # push ax
    a.b(0x2e, 0x80, 0x3e); a.word('cheese_eff'); a.b(0x00); a.short(0x74, 'hs_pop')
    a.b(0x83, 0x3e, 0xff, 0x7b, 0x00); a.short(0x74, 'hs_pop')   # cmp word [7BFFh], 0 / je   level: as the game
    a.b(0x53, 0x8b, 0x5d, 0x02, 0x2b, 0x5c, 0x02, 0x8b, 0xc3)    # push bx / mov bx, [di+2] / sub bx, [si+2] / mov ax, bx
    a.short(0x79, 'hs_abs'); a.b(0xf7, 0xd8)                 # jns / neg ax
    a.label('hs_abs')
    a.b(0x2d, HARD_KEEP, 0x00, 0x3b, 0x44, 0x52); a.short(0x7d, 'hs_depth')   # sub ax, HARD_KEEP / cmp ax, [si+52h] / jge
    a.b(0x0b, 0xdb); a.short(0x78, 'hs_right')               # or bx, bx / js   knight on the left: away right
    a.b(0x80, 0x4c, 0x26, 0x02); a.short(0xeb, 'hs_depth')   # or byte [si+26h], 2   away left
    a.label('hs_right')
    a.b(0x80, 0x4c, 0x26, 0x01)                              # or byte [si+26h], 1
    a.label('hs_depth')
    a.b(0x5b, 0xc7, 0x46, 0x02, 0x8b, 0x57)                  # pop bx / mov word [bp+2], 578Bh   ax = 1: it moves
    a.label('hs_pop')
    a.b(0x58); a.near(0xe9, 'rules_done')

    # dragon_hit (D46, anticheese = yes; 1000:3AB4, mov ax,[si+28h] once a knight's blow has cost the dragon its HP, di = the dragon, si = the
    # knight): blows in a row without the knight losing HP in between (and none 30 s apart): the 4th may end in the dragon's deadly bite
    # (50 %), the 5th and later more likely (80 %): its claw-and-bite kill (3AF3, as when its bite lands)
    a.label('rules_dragon_hit')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_CHOP_CHEESE); a.b(0x02); a.short(0x74, 'dk_on'); a.near(0xe9, 'dk_done')
    a.label('dk_on')
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7f, 'dk_alive'); a.near(0xe9, 'dk_done')   # cmp word [di+38h], 0 / jg   dying: as the game
    a.label('dk_alive')
    a.b(0x50, 0x53, 0x52, 0x87, 0xf7); a.near(0xe8, 'knight_no'); a.b(0x87, 0xf7); a.short(0x73, 'dk_k'); a.near(0xe9, 'dk_pop')   # push ax bx dx / xchg si, di / call knight_no / xchg / jnc
    a.label('dk_k')
    a.b(0xd1, 0xe3); a.near(0xe8, 'td_now'); a.b(0x8b, 0xd0, 0x2e, 0x2b, 0x87); a.word('dg_tick')   # shl bx,1 / call td_now / mov dx, ax / sub ax, cs:[bx+dg_tick]
    a.b(0x3d, 0x22, 0x02); a.short(0x77, 'dk_reset')         # cmp ax, 546 / ja   30 s since the last
    a.b(0x8b, 0x44, 0x38, 0x2e, 0x3b, 0x87); a.word('dg_hp'); a.short(0x7c, 'dk_reset')   # mov ax, [si+38h] / cmp ax, cs:[bx+dg_hp] / jl   hurt in between
    a.b(0x2e, 0xff, 0x87); a.word('dg_n'); a.short(0xeb, 'dk_store')   # inc word cs:[bx+dg_n]
    a.label('dk_reset')
    a.b(0x2e, 0xc7, 0x87); a.word('dg_n'); a.b(0x01, 0x00)   # mov word cs:[bx+dg_n], 1
    a.label('dk_store')
    a.b(0x2e, 0x89, 0x97); a.word('dg_tick'); a.b(0x8b, 0x44, 0x38, 0x2e, 0x89, 0x87); a.word('dg_hp')   # the tick, the knight's HP now
    a.b(0x2e, 0x8b, 0x87); a.word('dg_n'); a.b(0x3d, 0x04, 0x00); a.short(0x72, 'dk_pop')   # mov ax, cs:[bx+dg_n] / cmp ax, 4 / jb
    a.b(0xb2, 50); a.short(0x74, 'dk_roll'); a.b(0xb2, 80)   # mov dl, 50 / je / mov dl, 80
    a.label('dk_roll')
    a.near(0xe8, 'game_random'); a.b(0x52, 0x53, 0x33, 0xd2, 0xbb, 0x64, 0x00, 0xf7, 0xf3, 0x8a, 0xc2, 0x5b, 0x5a)   # push dx bx / dx = ax % 100 / mov al, dl / pop bx dx
    a.b(0x3a, 0xc2); a.short(0x73, 'dk_pop')                 # cmp al, dl / jae   not this time
    a.b(0x2e, 0xc7, 0x87); a.word('dg_n'); a.b(0x00, 0x00, 0x5a, 0x5b, 0x58)   # the run ends / pop dx bx ax
    a.b(0x89, 0x75, 0x0c, 0xc7, 0x45, 0x28, 0x02, 0x00, 0xc7, 0x46, 0x02, 0xf3, 0x3a)   # mov [di+0Ch], si / mov word [di+28h], 2 / mov word [bp+2], 3AF3h
    a.near(0xe9, 'rules_done')
    a.label('dk_pop')
    a.b(0x5a, 0x5b, 0x58)                                    # pop dx bx ax
    a.label('dk_done')
    a.b(0x8b, 0x44, 0x28); a.near(0xe9, 'rules_done')        # mov ax, [si+28h]   (replaced)

    # dragon_long (D46, anticheese = yes; 1000:389C, or word [7786h],10h: the long fire starts, di = the dragon): its head follows the knight's
    # depth 5 a tick for 13 ticks (3985). Now only up to a random 10-69 from where it started; begun near the top it always leaves the bottom
    # 20 clear of its fire, near the bottom the top, from the middle it may reach an edge
    a.label('rules_dragon_long')
    a.b(0x83, 0x0e, 0x86, 0x77, 0x10)                        # (replaced)
    a.b(0x2e, 0xc6, 0x06); a.word('dd_on'); a.b(0x00)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_CHOP_CHEESE); a.b(0x02); a.short(0x75, 'dl_end')
    a.b(0x2e, 0x80, 0x3e); a.word('dragon_ctl'); a.b(0x00); a.short(0x75, 'dl_end')   # HOTSTUFF: the player's dragon
    a.b(0x50, 0x53, 0x52); a.near(0xe8, 'game_random'); a.b(0x33, 0xd2, 0xbb, 0x3c, 0x00, 0xf7, 0xf3, 0x83, 0xc2, 0x0a)   # push ax bx dx / dx = 10 + random % 60
    a.b(0x8b, 0x45, 0x06, 0x8b, 0xd8, 0x2b, 0xda, 0x03, 0xc2)   # mov ax, [di+6] / mov bx, ax / sub bx, dx / add ax, dx   bx = lo, ax = hi
    a.b(0x83, 0x7d, 0x06, DD_TOP + DD_NEAR); a.short(0x7d, 'dl_nt')   # cmp word [di+6], top + near / jge
    a.b(0x3d, DD_BOTTOM - DD_GAP, 0x00); a.short(0x7e, 'dl_nt'); a.b(0xb8, DD_BOTTOM - DD_GAP, 0x00)   # hi = min(hi, bottom - gap)
    a.label('dl_nt')
    a.b(0x81, 0x7d, 0x06, (DD_BOTTOM - DD_NEAR) & 0xff, (DD_BOTTOM - DD_NEAR) >> 8); a.short(0x7e, 'dl_nb')   # cmp word [di+6], bottom - near / jle
    a.b(0x83, 0xfb, DD_TOP + DD_GAP); a.short(0x7d, 'dl_nb'); a.b(0xbb, DD_TOP + DD_GAP, 0x00)   # lo = max(lo, top + gap)
    a.label('dl_nb')
    a.b(0x2e, 0x89, 0x1e); a.word('dd_lo'); a.b(0x2e, 0xa3); a.word('dd_hi')   # mov cs:[dd_lo], bx / mov cs:[dd_hi], ax
    a.b(0x2e, 0xc6, 0x06); a.word('dd_on'); a.b(0x01, 0x5a, 0x5b, 0x58)   # dd_on = 1 / pop dx bx ax
    a.label('dl_end')
    a.near(0xe9, 'rules_done')
    # dragon_depth (D46; 1000:39A6, mov ax,di after the head's depth step): kept within the long fire's reach
    a.label('rules_dragon_depth')
    a.b(0x2e, 0x80, 0x3e); a.word('dd_on'); a.b(0x00); a.short(0x74, 'ddp_end')
    a.b(0xf7, 0x06, 0x86, 0x77, 0x20, 0x00); a.short(0x74, 'ddp_end')   # test word [7786h], 20h / jz   the low fire
    a.b(0x50, 0x8b, 0x45, 0x06, 0x2e, 0x3b, 0x06); a.word('dd_lo'); a.short(0x7d, 'ddp_lo'); a.b(0x2e, 0xa1); a.word('dd_lo')   # ax = max(z, lo)
    a.label('ddp_lo')
    a.b(0x2e, 0x3b, 0x06); a.word('dd_hi'); a.short(0x7e, 'ddp_hi'); a.b(0x2e, 0xa1); a.word('dd_hi')   # ax = min(ax, hi)
    a.label('ddp_hi')
    a.b(0x89, 0x45, 0x06, 0x58)                              # mov [di+6], ax / pop ax
    a.label('ddp_end')
    a.b(0x8b, 0xc7); a.near(0xe9, 'rules_done')              # mov ax, di  (replaced)

    # gore_lock ([Parental] age_rating K12; from the fight frame, the map loop and the first menu): the game's blood
    # option (DS:0700, set in its options) is kept at off, so gore off (D22) holds whatever is chosen there
    a.label('gore_lock')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_AGE); a.b(12); a.short(0x75, 'gl_ret')
    a.b(0xc7, 0x06, GORE & 0xff, GORE >> 8, 0x01, 0x00)      # mov word [0700h], 1   blood off
    a.label('gl_ret')
    a.b(0xc3)

    # hard_flags (every fight frame, from cheat_fight): hard_eff = the TOOEASY rules (TOOEASY, or a Black Knights'
    # fight), cheese_eff = the anti-cheese rules (those, or anticheese = true). A Black Knights' fight: the B key's
    # practice (bk), or, once BLACKDEATH was typed, a fight with a computer knight (+20h = 4) in it. Worked out each
    # frame from the state, so after such a fight the rules are again those from before it
    a.label('hard_flags')
    a.b(0x50, 0x53, 0x51, 0x56)                              # push ax bx cx si
    a.b(0x2e, 0xa0); a.word('hard_ai')                       # mov al, cs:[hard_ai]   TOOEASY (1), TOOHARD (2)
    a.b(0x2e, 0xc6, 0x06); a.word('easy_eff'); a.b(0x00)
    a.b(0x3c, EASY); a.short(0x75, 'hf_not_easy')
    a.b(0x2e, 0xc6, 0x06); a.word('easy_eff'); a.b(0x01)     # TOOHARD (a Black Knights' fight turns it off below)
    a.label('hf_not_easy')
    a.b(0x3c, HARD); a.b(0xb0, 0x00); a.short(0x75, 'hf_ai'); a.b(0xb0, 0x01)   # cmp al, 1 / mov al, 0 / jne / mov al, 1
    a.label('hf_ai')
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00); a.short(0x75, 'hf_black')
    a.b(0x2e, 0x80, 0x3e); a.word('bd_on'); a.b(0x00); a.short(0x74, 'hf_set')
    a.b(0xbe, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # the fight's figures
    a.label('hf_loop')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'hf_next')          # cmp byte [si], 0 / je   free
    a.b(0x8b, 0x5c, 0x16)                                    # mov bx, [si+16h]   its object
    a.b(0x81, 0xfb, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'hf_next')
    a.b(0x81, 0xfb, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8); a.short(0x77, 'hf_next')
    a.b(0x83, 0x7f, 0x20, 0x04); a.short(0x74, 'hf_black')   # cmp word [bx+20h], 4   a computer knight
    a.label('hf_next')
    a.b(0x83, 0xc6, ANIM_SIZE); a.short(0xe2, 'hf_loop')
    a.short(0xeb, 'hf_set')
    a.label('hf_black')
    a.b(0xb0, 0x01)                                          # mov al, 1
    a.b(0x2e, 0xc6, 0x06); a.word('easy_eff'); a.b(0x00)     # a Black Knights' fight: always the harder rules
    a.label('hf_set')
    a.b(0x2e, 0xa2); a.word('hard_eff')                      # mov cs:[hard_eff], al
    a.b(0x2e, 0x0a, 0x06); a.word('rules_table', G_ANTICHEESE)   # or al, cs:[anticheese]
    a.b(0x2e, 0xa2); a.word('cheese_eff')                    # mov cs:[cheese_eff], al
    a.b(0x5e, 0x59, 0x5b, 0x58, 0xc3)                        # pop si cx bx ax / ret

    # lair_loot (catchup; 1000:05B6, mov word [di+8],1 when a lair is won the first time, di = the lair, before its
    # chest (the item screen, mode 2): its gold +6, its items at [di]). In the game (not a practice), for a human
    # knight (+9 not 4): behind the leading human knight by CU_STEP points or more (knight_score), the chest holds
    # more: level = the gap / CU_STEP (at most 4): +10 gold and one more magic item per level, and from level 3 a
    # Scroll of Acquisition too. And low on life: on its last life, or HP at most a quarter of its maximum, 10 %
    # that a healing potion is in it; both, 25 %
    a.label('rules_lair_loot')
    a.b(0xc7, 0x45, 0x08, 0x01, 0x00)                        # mov word [di+8], 1   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_CATCHUP); a.b(0x00); a.short(0x75, 'll_on')
    a.near(0xe9, 'rules_done')
    a.label('ll_on')
    a.b(0x83, 0x3e, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION); a.short(0x75, 'll_game')
    a.near(0xe9, 'rules_done')
    a.label('ll_game')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56)                        # push ax bx cx dx si
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   the knight who won
    a.b(0x80, 0x7c, 0x09, COMPUTER_CONTROL); a.short(0x75, 'll_human')
    a.near(0xe9, 'll_pop')
    a.label('ll_human')
    a.b(0x8b, 0x45, 0x06, 0x2e, 0xa3); a.word('loot_base')   # mov ax, [di+6] / mov cs:[loot_base], ax   the lair's own gold
    a.b(0x2e, 0xc6, 0x06); a.word('loot_capped'); a.b(0x01)
    a.b(0x2e, 0xc6, 0x06); a.word('loot_potion'); a.b(0x00)
    a.near(0xe8, 'knight_score'); a.b(0x8b, 0xd0)            # call knight_score / mov dx, ax   its score
    a.b(0x56, 0x33, 0xc9)                                    # push si / xor cx, cx   the leader's
    for rec in KNIGHTS:
        a.b(0xbe, rec & 0xff, rec >> 8, 0x80, 0x7c, 0x09, COMPUTER_CONTROL); a.short(0x74, f'll_k{rec:x}')
        a.near(0xe8, 'knight_score'); a.b(0x3b, 0xc1); a.short(0x7e, f'll_k{rec:x}'); a.b(0x8b, 0xc8)   # cmp ax, cx / jle / mov cx, ax
        a.label(f'll_k{rec:x}')
    a.b(0x5e, 0x8b, 0xc1, 0x2b, 0xc2)                        # pop si / mov ax, cx / sub ax, dx   the gap
    a.b(0x33, 0xd2, 0xb9, CU_STEP, 0x00, 0xf7, 0xf1)         # xor dx, dx / mov cx, CU_STEP / div cx   the level
    a.b(0x3d, CU_MAX, 0x00); a.short(0x76, 'll_lvl'); a.b(0xb8, CU_MAX, 0x00)
    a.label('ll_lvl')
    a.b(0x2e, 0xa2); a.word('cu_level')                      # mov cs:[cu_level], al
    a.b(0x8b, 0x1d, 0x8b, 0xc8)                              # mov bx, [di]   the chest's items / mov cx, ax
    a.b(0x0b, 0xc9); a.short(0x75, 'll_gold'); a.near(0xe9, 'll_potion')   # or cx, cx / jnz / level 0: no more
    a.label('ll_gold')
    a.b(0xb2, 10, 0xf6, 0xe2, 0x01, 0x45, 0x06)              # mov dl, 10 / mul dl / add [di+6], ax   +10 gold a level
    a.label('ll_item')
    a.near(0xe8, 'cu_random'); a.b(0x8a, 0xc4, 0x24, 0x07, 0x32, 0xe4)   # call cu_random / mov al, ah / and al, 7 / xor ah, ah
    a.b(0x56, 0x8b, 0xf0, 0x2e, 0x8a, 0x84); a.word('cu_items'); a.b(0x5e)   # push si / mov si, ax / mov al, cs:[si+cu_items] / pop si
    a.b(0x0a, 0xc0); a.short(0x75, 'll_add')                 # or al, al / jnz   not a potion
    a.near(0xe8, 'potion_ok'); a.short(0x73, 'll_other')     # a potion only if allowed
    a.b(0x2e, 0xc6, 0x06); a.word('loot_potion'); a.b(0x01); a.short(0xeb, 'll_add')
    a.label('ll_other')                                      # else one of the others, drawn
    a.near(0xe8, 'cu_random'); a.b(0x8a, 0xc4, 0x32, 0xe4, 0x53, 0xb3, len(CU_ITEMS) - 1, 0xf6, 0xf3, 0x5b)   # mov al, ah / xor ah, ah / push bx / mov bl, 7 / div bl / pop bx
    a.b(0x8a, 0xc4, 0xfe, 0xc0, 0x32, 0xe4)                  # mov al, ah / inc al / xor ah, ah   1-7
    a.b(0x56, 0x8b, 0xf0, 0x2e, 0x8a, 0x84); a.word('cu_items'); a.b(0x5e)
    a.label('ll_add')
    a.b(0x32, 0xe4, 0x56, 0x8b, 0xf0); a.near(0xe8, 'cu_add'); a.b(0x5e)   # xor ah, ah / push si / mov si, ax / call cu_add / pop si
    a.short(0xe2, 'll_item')                                 # loop ll_item
    a.b(0x2e, 0x80, 0x3e); a.word('cu_level'); a.b(CU_SCROLL); a.short(0x72, 'll_potion')
    a.b(0xb0, ACQUISITION); a.near(0xe8, 'loot_has'); a.short(0x75, 'll_potion')   # not if it has one
    a.b(0x56, 0xbe, ACQUISITION, 0x00); a.near(0xe8, 'cu_add'); a.b(0x5e)   # a Scroll of Acquisition
    a.label('ll_potion')
    a.b(0x8b, 0x1d, 0x32, 0xc9)                              # mov bx, [di] / xor cl, cl   the chance
    a.b(0x80, 0x7c, 0x31, 0x01); a.short(0x7f, 'll_hp'); a.b(0xb1, CU_LOW)   # cmp byte [si+31h], 1 / jg / mov cl, 10
    a.label('ll_hp')
    a.b(0x8b, 0x44, 0x38, 0xd1, 0xe0, 0xd1, 0xe0, 0x3b, 0x44, 0x3c); a.short(0x7f, 'll_roll')   # HP * 4 > max?
    a.b(0x80, 0xc1, CU_LOW, 0x80, 0xf9, CU_LOW); a.short(0x76, 'll_roll'); a.b(0xb1, CU_BOTH)   # add cl, 10 / both: 25
    a.label('ll_roll')
    a.b(0x0a, 0xc9); a.short(0x74, 'll_pop')                 # or cl, cl / jz   no chance
    a.near(0xe8, 'potion_ok'); a.short(0x73, 'll_pop')       # not if it has one or one was added
    a.near(0xe8, 'cu_random'); a.b(0x8a, 0xc4, 0xb4, 100, 0xf6, 0xe4)   # mov al, ah / mov ah, 100 / mul ah   ah = 0-99
    a.b(0x3a, 0xe1); a.short(0x73, 'll_pop')                 # cmp ah, cl / jae
    a.b(0x56, 0x33, 0xf6); a.near(0xe8, 'cu_add'); a.b(0x5e) # a healing potion (+0)
    a.b(0x2e, 0xc6, 0x06); a.word('loot_potion'); a.b(0x01)
    a.label('ll_pop')
    a.b(0x5e, 0x5a, 0x59, 0x5b, 0x58)                        # pop si dx cx bx ax
    a.near(0xe9, 'rules_done')
    # loot_has (si = a knight, al = an item): ZF = 1 if it has none (keeps everything)
    a.label('loot_has')
    a.b(0x53, 0x50, 0x8b, 0x5c, 0x44, 0x32, 0xe4, 0x03, 0xd8, 0x80, 0x3f, 0x00, 0x58, 0x5b, 0xc3)   # push bx ax / mov bx, [si+44h] / xor ah, ah / add bx, ax / cmp byte [bx], 0 / pop ax bx
    # potion_ok (si = the knight of the chest): CF = 1 if a healing potion may be added: it has none and none was
    # added to this chest yet (catchup)
    a.label('potion_ok')
    a.b(0x2e, 0x80, 0x3e); a.word('loot_potion'); a.b(0x00); a.short(0x75, 'po_no')
    a.b(0x50, 0x32, 0xc0); a.near(0xe8, 'loot_has'); a.b(0x58); a.short(0x75, 'po_no')   # push ax / xor al, al / call loot_has / pop ax / jnz
    a.b(0xf9, 0xc3)
    a.label('po_no')
    a.b(0xf8, 0xc3)
    # loot_cap (05C6, before the chest): with catchup's extra in this chest, all the gold
    # at most the lair's own + LOOT_GOLD_MAX %; and a new chest may have its potion again
    a.label('loot_cap')
    a.b(0x2e, 0x80, 0x3e); a.word('loot_capped'); a.b(0x00); a.short(0x74, 'lc_end')
    a.b(0x2e, 0xc6, 0x06); a.word('loot_capped'); a.b(0x00)
    a.b(0x50, 0x52, 0x56, 0x2e, 0xa1); a.word('loot_base')   # push ax dx si / mov ax, cs:[loot_base]
    a.b(0x52, 0xba, LOOT_GOLD_MAX, 0x00, 0x50, 0xf7, 0xe2, 0xbe, 0x64, 0x00, 0xf7, 0xf6, 0x5a, 0x03, 0xc2, 0x5a)   # ax = base + base * 50 / 100
    a.b(0x8b, 0x36, 0x62, 0x69, 0x39, 0x44, 0x06); a.short(0x76, 'lc_pop'); a.b(0x89, 0x44, 0x06)   # cmp [si+6], ax / jbe / mov [si+6], ax
    a.label('lc_pop')
    a.b(0x5e, 0x5a, 0x58)
    a.label('lc_end')
    a.b(0x2e, 0xc6, 0x06); a.word('loot_potion'); a.b(0x00, 0xc3)
    a.label('cu_add')                                        # bx = an item table, si = the item: one more (at most 9)
    a.b(0x80, 0x38, 0x09); a.short(0x73, 'cua_ret'); a.b(0xfe, 0x00)   # cmp byte [bx+si], 9 / jae / inc byte [bx+si]
    a.label('cua_ret')
    a.b(0xc3)
    a.label('cu_random')                                     # ax = the next number (an LCG, with the BIOS tick)
    a.b(0x52, 0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0x8b, 0x16, 0x6c, 0x04, 0x1f)   # push dx ds / ds = 0 / mov dx, [046Ch] / pop ds
    a.b(0x2e, 0xa1); a.word('cu_seed'); a.b(0x33, 0xc2)      # mov ax, cs:[cu_seed] / xor ax, dx
    a.b(0xba, 25173 & 0xff, 25173 >> 8, 0xf7, 0xe2, 0x05, 13849 & 0xff, 13849 >> 8)   # mov dx, 25173 / mul dx / add ax, 13849
    a.b(0x2e, 0xa3); a.word('cu_seed'); a.b(0x5a, 0xc3)      # mov cs:[cu_seed], ax / pop dx / ret
    # knight_score (si = a knight): ax = how far it has got: each Moonstone 40, key 15, life 10, point of strength,
    # constitution and endurance 5, experience point 5, and 0-10 by its HP of its maximum
    a.label('knight_score')
    a.b(0x53, 0x51, 0x52, 0x57, 0x8b, 0x7c, 0x44, 0x33, 0xdb)   # push bx cx dx di / mov di, [si+44h] / xor bx, bx
    for field, weight in ((0x16, 40), (0x14, 15)):          # the Moonstones, the keys: bits 1, 2, 4, 8
        a.b(0x8a, 0x45, field, 0xb9, 0x04, 0x00)             # mov al, [di+field] / mov cx, 4
        lbl = f'ks_bit{field:x}'
        a.label(lbl)
        a.b(0xd0, 0xe8, 0x73, 0x03, 0x83, 0xc3, weight)      # shr al, 1 / jnc +3 / add bx, weight
        a.b(0xe2); a.b(0x00); at = len(a.code) - 1
        a.code[at] = (a.labels[lbl] - (a.org + at + 1)) & 0xff
    a.b(0x8a, 0x44, 0x31, 0x98, 0xb1, 10, 0xf6, 0xe9, 0x03, 0xd8)   # mov al, [si+31h] / cbw / mov cl, 10 / imul cl / add bx, ax
    a.b(0x8a, 0x44, 0x2e, 0x98, 0x8b, 0xd0)                  # mov al, [si+2Eh] / cbw / mov dx, ax   strength
    a.b(0x8a, 0x44, 0x2f, 0x98, 0x03, 0xd0)                  # + constitution
    a.b(0x8a, 0x44, 0x30, 0x98, 0x03, 0xd0)                  # + endurance
    a.b(0x03, 0x54, 0x36)                                    # + experience
    a.b(0x6b, 0xc2, 0x05, 0x03, 0xd8)                        # imul ax, dx, 5 / add bx, ax
    a.b(0x8b, 0x44, 0x38, 0x85, 0xc0); a.short(0x7e, 'ks_end')   # mov ax, [si+38h] / test ax, ax / jle
    a.b(0x8b, 0x4c, 0x3c, 0x85, 0xc9); a.short(0x7e, 'ks_end')   # mov cx, [si+3Ch] / test cx, cx / jle
    a.b(0xba, 0x0a, 0x00, 0xf7, 0xe2, 0xf7, 0xf1, 0x03, 0xd8)    # mov dx, 10 / mul dx / div cx / add bx, ax
    a.label('ks_end')
    a.b(0x8b, 0xc3, 0x5f, 0x5a, 0x59, 0x5b, 0xc3)            # mov ax, bx / pop di dx cx bx / ret

    # cheat_monster (every fight frame, DIRTYRAT): player 1's knight out of the fight; player 1's monster: the
    # first of its type standing, without the AI's own modes
    a.label('cheat_monster')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_ctl'); a.b(0x00); a.short(0x75, 'cmo_on'); a.b(0xc3)
    a.label('cmo_on')
    a.b(0x50, 0x51, 0x56)                                    # push ax cx si
    a.near(0xe8, 'k1_away')                                  # knight 1 out of the fight (1-3 knights)
    a.b(0x2e, 0x8b, 0x36); a.word('mon_obj'); a.b(0x0b, 0xf6); a.short(0x74, 'cmo_find')   # still standing?
    a.b(0x83, 0x3c, 0x00); a.short(0x74, 'cmo_find')         # cmp word [si], 0   gone
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7f, 'cmo_have')   # cmp word [si+38h], 0 / jg
    a.label('cmo_find')
    a.b(0x2e, 0xc7, 0x06); a.word('mon_obj'); a.b(0x00, 0x00)
    a.b(0xbe, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00)
    a.b(0x2e, 0xa0); a.word('mon_ctl')                       # mov al, cs:[mon_ctl]   the type
    a.label('cmo_loop')
    a.b(0x83, 0x3c, 0x00); a.short(0x74, 'cmo_next')
    a.b(0x38, 0x44, 0x35); a.short(0x74, 'cmo_type')         # cmp [si+35h], al / je
    a.b(0x3c, TROGG_ANY); a.short(0x75, 'cmo_next')          # TROGLIFE: any trogg
    for t in (0x0c, 0x0e, 0x10):
        a.b(0x80, 0x7c, 0x35, t); a.short(0x74, 'cmo_type')
    a.short(0xeb, 'cmo_next')
    a.label('cmo_type')
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'cmo_next')
    # a ratman still coming in (its AI modes are cleared below) waits; the others take the keys only where their
    # AI decides anyway (a troll may stand off the screen's edge, x 400, and strike from there)
    a.b(0x80, 0x7c, 0x35, 0x12); a.short(0x75, 'cmo_in')    # cmp byte [si+35h], 12h / jne
    a.b(0x83, 0x7c, 0x02, MON_X_MIN); a.short(0x7c, 'cmo_next')   # cmp word [si+2], 10 / jl   still coming in
    a.b(0x81, 0x7c, 0x02, MON_X_MAX & 0xff, MON_X_MAX >> 8); a.short(0x7f, 'cmo_next')
    a.label('cmo_in')
    a.b(0x80, 0x7c, 0x35, MUDMAN); a.short(0x75, 'cmo_up')   # a mudman:
    a.b(0xf6, 0x44, 0x48, 0x08); a.short(0x74, 'cmo_next')   # test byte [si+48h], 8 / jz   still in the mud
    a.label('cmo_up')
    a.b(0x2e, 0x89, 0x36); a.word('mon_obj'); a.short(0xeb, 'cmo_have')
    a.label('cmo_next')
    a.b(0x83, 0xc6, SLOT_SIZE); a.short(0xe2, 'cmo_loop')
    a.short(0xeb, 'cmo_pop')
    a.label('cmo_have')
    a.b(0x80, 0x7c, 0x35, 0x12); a.short(0x75, 'cmo_pop')    # cmp byte [si+35h], 12h   a ratman:
    a.b(0x80, 0x64, 0x48, 0x81, 0xc6, 0x44, 0x49, 0x00)      # and byte [si+48h], 81h / mov byte [si+49h], 0   no AI modes
    a.label('cmo_pop')
    a.b(0x5e, 0x59, 0x58, 0xc3)                              # pop si cx ax / ret

    # air_frame (every fight frame, from cheat_fight; [bp+4] = MAIN's CS): ROCKETMAN and LUNAR.
    # ROCKETMAN: a human's knight rises while its secondary button is held (sec_input: right Shift, left Shift, N,
    # a controller's button 2) and falls when it is let go; it walks and strikes in the air (a new move takes its
    # height from the object).
    # LUNAR: objects set going (a blow, lunar_hit; a jump) fly by the moon's gravity: x and height change by their
    # speeds each frame (air_vx, air_vy), the fall speed grows by 1 every other frame, until they land; a human's
    # knight on the ground jumps (straight up) with its secondary button
    a.label('air_frame')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_ROCKET | CF_LUNAR); a.short(0x75, 'af_go'); a.b(0xc3)
    a.label('af_go')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56)                        # push ax bx cx dx si
    a.b(0x2e, 0x80, 0x36); a.word('air_tick'); a.b(0x01)     # xor byte cs:[air_tick], 1
    a.b(0x33, 0xc9)                                          # xor cx, cx   the object's number
    a.label('af_loop')
    a.b(0x83, 0xf9, 0x04); a.short(0x73, 'af_mon')
    a.b(0x8b, 0xd9, 0xd1, 0xe3, 0x2e, 0x8b, 0xb7); a.word('knight_list')   # mov bx, cx / shl bx, 1 / mov si, cs:[bx+knight_list]
    a.short(0xeb, 'af_have')
    a.label('af_mon')
    a.b(0x8b, 0xc1, 0x2d, 0x04, 0x00, 0xba, SLOT_SIZE, 0x00, 0xf7, 0xe2, 0x05, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)
    a.b(0x8b, 0xf0, 0x83, 0x3c, 0x00); a.short(0x75, 'af_have')   # mov si, ax / cmp word [si], 0 / jne
    a.near(0xe9, 'af_next')
    a.label('af_have')
    a.b(0x8b, 0xd9)                                          # mov bx, cx
    a.b(0x83, 0xf9, 0x04); a.short(0x73, 'af_phys')          # a knight,
    a.b(0x80, 0x7c, 0x35, 0x06); a.short(0x75, 'af_phys')    # a human's,
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'af_phys')    # standing:
    a.b(0x50, 0x8a, 0x44, 0x09); a.near(0xe8, 'sec_input'); a.b(0x58)   # its secondary button
    a.b(0xb2, 0x00, 0x74, 0x02, 0xb2, 0x01)                  # mov dl, 0 / jz +2 / mov dl, 1
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_ROCKET); a.short(0x74, 'af_jump')
    # ROCKETMAN and LUNAR both: the button lifts it faster (ROCKET_MOON_RISE), and let go it floats down by the
    # moon's gravity (the LUNAR flight from standing still in the air)
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_LUNAR); a.short(0x74, 'af_rocket')
    a.near(0xe9, 'af_both')
    a.label('af_rocket')
    a.b(0x8b, 0x44, 0x04, 0x0a, 0xd2); a.short(0x74, 'af_rfall')   # mov ax, [si+4] / or dl, dl / jz
    a.b(0x2d, ROCKET_RISE, 0x00, 0x3d, (-ROCKET_TOP) & 0xff, ((-ROCKET_TOP) >> 8) & 0xff)   # sub ax, rise / cmp ax, -top
    a.short(0x7d, 'af_rset'); a.b(0xb8, (-ROCKET_TOP) & 0xff, ((-ROCKET_TOP) >> 8) & 0xff); a.short(0xeb, 'af_rset')
    a.label('af_rfall')
    a.b(0x0b, 0xc0); a.short(0x7d, 'af_next_n')              # on the ground
    a.b(0x05, ROCKET_FALL, 0x00); a.short(0x7e, 'af_rset'); a.b(0x33, 0xc0)
    a.label('af_rset')
    a.near(0xe8, 'air_sety')
    a.label('af_next_n')
    a.near(0xe9, 'af_next')
    a.label('af_jump')
    a.b(0x0a, 0xd2); a.short(0x74, 'af_phys')                # secondary button: a moon jump, from the ground
    a.b(0x2e, 0x80, 0xbf); a.word('air_on'); a.b(0x00); a.short(0x75, 'af_phys')
    a.b(0x83, 0x7c, 0x04, 0x00); a.short(0x75, 'af_phys')
    a.b(0x2e, 0xc6, 0x87); a.word('air_on'); a.b(0x01)
    a.b(0x2e, 0xc6, 0x87); a.word('air_vx'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x87); a.word('air_vy'); a.b((-LUNAR_JUMP) & 0xff)
    a.label('af_phys')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_LUNAR); a.short(0x74, 'af_next')
    a.b(0x2e, 0x80, 0xbf); a.word('air_on'); a.b(0x00); a.short(0x74, 'af_next')
    a.b(0x2e, 0x8a, 0x87); a.word('air_vx'); a.b(0x98, 0x0b, 0xc0); a.short(0x74, 'af_y')   # mov al, cs:[bx+air_vx] / cbw / or ax, ax
    a.b(0x8b, 0x54, 0x02, 0x03, 0xd0)                        # mov dx, [si+2] / add dx, ax   the new x
    a.b(0x83, 0xfa, MON_X_MIN); a.short(0x7d, 'af_x1'); a.b(0xba, MON_X_MIN, 0x00)
    a.label('af_x1')
    a.b(0x81, 0xfa, MON_X_MAX & 0xff, MON_X_MAX >> 8); a.short(0x7e, 'af_x2'); a.b(0xba, MON_X_MAX & 0xff, MON_X_MAX >> 8)
    a.label('af_x2')
    a.b(0x8b, 0xc2, 0x2b, 0x44, 0x02, 0x89, 0x54, 0x02)      # mov ax, dx / sub ax, [si+2] / mov [si+2], dx
    a.near(0xe8, 'air_addx')                                 # its animations by as much
    a.label('af_y')
    a.b(0x2e, 0x8a, 0x87); a.word('air_vy'); a.b(0x98, 0x03, 0x44, 0x04)   # mov al, cs:[bx+air_vy] / cbw / add ax, [si+4]
    a.b(0x2e, 0x80, 0x3e); a.word('air_tick'); a.b(0x00); a.short(0x74, 'af_grav')
    a.b(0x2e, 0xfe, 0x87); a.word('air_vy')                  # inc byte cs:[bx+air_vy]   the moon's gravity
    a.label('af_grav')
    a.b(0x0b, 0xc0); a.short(0x7c, 'af_sety')                # in the air
    a.b(0x33, 0xc0, 0x2e, 0xc6, 0x87); a.word('air_on'); a.b(0x00)   # landed
    a.b(0x2e, 0xc6, 0x87); a.word('air_vx'); a.b(0x00, 0x2e, 0xc6, 0x87); a.word('air_vy'); a.b(0x00)
    a.label('af_sety')
    a.near(0xe8, 'air_sety')
    a.label('af_next')
    a.b(0x41, 0x83, 0xf9, 24); a.short(0x73, 'af_end'); a.near(0xe9, 'af_loop')   # the dragon (24) is not moved
    a.label('af_end')
    a.b(0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)                  # pop si dx cx bx ax / ret
    a.label('af_both')
    a.b(0x8b, 0x44, 0x04, 0x0a, 0xd2); a.short(0x74, 'af_mfall')   # mov ax, [si+4] / or dl, dl / jz
    a.b(0x2e, 0xc6, 0x87); a.word('air_on'); a.b(0x00)       # rising: no moon flight
    a.b(0x2d, ROCKET_MOON_RISE, 0x00, 0x3d, (-ROCKET_TOP) & 0xff, ((-ROCKET_TOP) >> 8) & 0xff)
    a.short(0x7d, 'af_b_set'); a.b(0xb8, (-ROCKET_TOP) & 0xff, ((-ROCKET_TOP) >> 8) & 0xff)
    a.label('af_b_set')
    a.near(0xe9, 'af_rset')
    a.label('af_mfall')
    a.b(0x0b, 0xc0); a.short(0x7d, 'af_mf_phys')                # on the ground: as LUNAR
    a.b(0x2e, 0x80, 0xbf); a.word('air_on'); a.b(0x00); a.short(0x75, 'af_mf_phys')   # floating down already
    a.b(0x2e, 0xc6, 0x87); a.word('air_on'); a.b(0x01)
    a.b(0x2e, 0xc6, 0x87); a.word('air_vx'); a.b(0x00, 0x2e, 0xc6, 0x87); a.word('air_vy'); a.b(0x00)
    a.label('af_mf_phys')
    a.near(0xe9, 'af_phys')
    for name, store in (('air_sety', (0x89, 0x47, 0x06)), ('air_addx', (0x01, 0x47, 0x04))):
        # air_sety: ax = the height of object si (and its animations); air_addx: ax added to its animations' x
        a.label(name)
        if name == 'air_sety':
            a.b(0x89, 0x44, 0x04)                            # mov [si+4], ax
        a.b(0x53, 0x51, 0xbb, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # push bx cx / mov bx, 947Eh / mov cx, 10
        a.label(name + '_l')
        a.b(0x80, 0x3f, 0x00); a.short(0x74, name + '_n')    # cmp byte [bx], 0 / je
        a.b(0x39, 0x77, 0x16); a.short(0x75, name + '_n')    # cmp [bx+16h], si / jne
        a.b(*store)                                          # mov [bx+6], ax / add [bx+4], ax
        a.label(name + '_n')
        a.b(0x83, 0xc3, ANIM_SIZE); a.short(0xe2, name + '_l')
        a.b(0x59, 0x5b, 0xc3)                                # pop cx bx / ret

    # mon_walk (LUNAR; 1000:4E97, mov si,[77E8h] at the walk of the trolls and troggs, speeds [7BF5h], [7BF7h]): at
    # half speed
    a.label('rules_mon_walk')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   (replaced)
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags'); a.b(CF_LUNAR); a.short(0x74, 'mw_end')
    a.b(0xd1, 0x3e, 0xf5, 0x7b, 0xd1, 0x3e, 0xf7, 0x7b)      # sar word [7BF5h], 1 / sar word [7BF7h], 1
    a.label('mw_end')
    # D46: anticheese = yes: a monster does not walk in under a knight's chop in the air (the walk's steps off while it lasts)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_CHOP_CHEESE); a.b(0x02); a.short(0x75, 'mw_done')
    a.b(0x80, 0x7c, 0x35, COMPUTER_TYPE); a.short(0x74, 'mw_done')   # cmp byte [si+35h], 8 / je   the knights' own rule
    a.b(0x50, 0x8b, 0x1e, 0xea, 0x77, 0x80, 0x7f, 0x35, 0x06); a.short(0x75, 'mw_pop')   # push ax / mov bx, [77EAh] / cmp byte [bx+35h], 6 / jne
    a.b(0x83, 0x7f, 0x28, 0x10); a.short(0x75, 'mw_pop')     # cmp word [bx+28h], 10h / jne
    a.b(0x83, 0x7f, 0x38, 0x00); a.short(0x7e, 'mw_pop')     # cmp word [bx+38h], 0 / jle
    a.b(0x83, 0x7f, 0x0c, 0x00); a.short(0x75, 'mw_pop')     # cmp word [bx+0Ch], 0 / jne   it has hit
    a.b(0x8b, 0x44, 0x02, 0x2b, 0x47, 0x02, 0x79, 0x02, 0xf7, 0xd8, 0x83, 0xf8, 0x70); a.short(0x77, 'mw_pop')   # ax = |x - foe's x| / cmp ax, 70h / ja
    a.b(0xc7, 0x44, 0x26, 0x00, 0x00)                        # mov word [si+26h], 0
    a.label('mw_pop')
    a.b(0x58)                                                # pop ax
    a.label('mw_done')
    a.near(0xe9, 'rules_done')

    # k1_away (a monster code's fight with 1-3 knights, k1_out): knight 1 (player 1 is the monster) is out of it:
    # down, off the screen (x -400), its animation too, so it is never seen there nor seen falling
    a.label('k1_away')
    a.b(0x2e, 0x80, 0x3e); a.word('k1_out'); a.b(0x00); a.short(0x75, 'ka_go'); a.b(0xc3)
    a.label('ka_go')
    a.b(0x56, 0x51)                                          # push si cx
    a.b(0x83, 0x3e, (KNIGHTS[0] + 0x38) & 0xff, (KNIGHTS[0] + 0x38) >> 8, 0x00); a.short(0x7e, 'ka_x')
    a.b(0xc7, 0x06, (KNIGHTS[0] + 0x38) & 0xff, (KNIGHTS[0] + 0x38) >> 8, 0x00, 0x00)
    a.label('ka_x')
    a.b(0xc7, 0x06, (KNIGHTS[0] + 2) & 0xff, (KNIGHTS[0] + 2) >> 8, 0x70, 0xfe)
    a.b(0xbe, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)
    a.label('ka_loop')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'ka_next')
    a.b(0x81, 0x7c, 0x16, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x75, 'ka_next')
    a.b(0xc7, 0x44, 0x04, 0x70, 0xfe)                        # mov word [si+4], -400
    a.label('ka_next')
    a.b(0x83, 0xc6, ANIM_SIZE); a.short(0xe2, 'ka_loop')
    a.b(0x59, 0x5e, 0xc3)                                    # pop cx si / ret

    # mud_rise (SWAMPTHING; 1000:54C7, call 3C97 as a mudman comes up out of the mud: level with its knight and
    # 20-80 away, it grabs it from below and pulls it under): player 1's mudman does that only after its own dive
    # (the secondary button), and it comes up where it went down: the knight it fights was seldom just there. Now
    # it comes up MUD_GRAB_X beside the nearest knight standing within MUD_REACH_X in x and MUD_REACH_Z in depth,
    # level with it, facing it, and pulls it under (54DB, as the game's); with none near it stands up (54F1), as it
    # does coming up otherwise (its first rise)
    a.label('rules_mud_rise')
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x74, 'mr_mine')
    a.near(0xe9, 'mr_game')
    a.label('mr_mine')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_dive'); a.b(0x00); a.short(0x75, 'mr_dive')
    a.label('mr_stand')
    a.b(0xc7, 0x46, 0x02, 0xf1, 0x54); a.near(0xe9, 'rules_done')   # mov word [bp+2], 54F1h
    a.label('mr_dive')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_dive'); a.b(0x00)
    a.b(0x2e, 0xc7, 0x06); a.word('nk_rx'); a.b(MUD_REACH_X, 0x00)   # mov word cs:[nk_rx], MUD_REACH_X
    a.b(0x2e, 0xc7, 0x06); a.word('nk_rz'); a.b(MUD_REACH_Z, 0x00)   # mov word cs:[nk_rz], MUD_REACH_Z
    a.near(0xe8, 'nearest_knight')                           # call nearest_knight   di
    a.b(0x0b, 0xff); a.short(0x74, 'mr_stand')               # or di, di / jz   none near
    a.b(0x50)                                                # push ax
    a.b(0x89, 0x3e, 0x78, 0x09, 0x89, 0x3e, 0xea, 0x77)      # mov [0978h], di / mov [77EAh], di
    a.b(0x8b, 0x45, 0x06, 0x89, 0x44, 0x06)                  # mov ax, [di+6] / mov [si+6], ax   level with it
    a.b(0x8b, 0x45, 0x02, 0x39, 0x44, 0x02); a.short(0x7c, 'mr_left')   # mov ax, [di+2] / cmp [si+2], ax / jl
    a.b(0x05, MUD_GRAB_X, 0x00, 0xc6, 0x44, 0x08, 0x03); a.short(0xeb, 'mr_set')   # add ax, 40 / facing left
    a.label('mr_left')
    a.b(0x2d, MUD_GRAB_X, 0x00, 0xc6, 0x44, 0x08, 0x01)      # sub ax, 40 / facing right
    a.label('mr_set')
    a.b(0x89, 0x44, 0x02, 0x58)                              # mov [si+2], ax / pop ax
    a.b(0xc7, 0x46, 0x02, 0xdb, 0x54); a.near(0xe9, 'rules_done')   # mov word [bp+2], 54DBh   the pull from below
    a.label('mr_game')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x97, 0x3c)   # call 3C97 (replaced), on at 54CA
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xca, 0x54)
    a.near(0xe9, 'call_game')

    # nearest_knight (si = a monster; cs:[nk_rx], cs:[nk_rz] = how far in x and depth): di = the nearest knight
    # standing within both (by x + depth), 0 if none
    a.label('nearest_knight')
    a.b(0x50, 0x53, 0x51, 0x52)                              # push ax bx cx dx
    a.b(0x33, 0xff, 0xba, 0xff, 0xff, 0x33, 0xc9)            # xor di, di / mov dx, 0FFFFh / xor cx, cx
    a.label('nk_loop')
    a.b(0x8b, 0xd9, 0xd1, 0xe3)                              # mov bx, cx / shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('knight_list')             # mov bx, cs:[bx+knight_list]
    a.b(0x83, 0x7f, 0x38, 0x00); a.short(0x7e, 'nk_next')    # cmp word [bx+38h], 0 / jle   down
    for off, reach in ((2, 'nk_rx'), (6, 'nk_rz')):
        a.b(0x8b, 0x47, off, 0x2b, 0x44, off); a.short(0x79, f'nk_abs{off}'); a.b(0xf7, 0xd8)   # |[bx+o] - [si+o]|
        a.label(f'nk_abs{off}')
        a.b(0x2e, 0x3b, 0x06); a.word(reach); a.short(0x7f, 'nk_next')   # cmp ax, cs:[reach] / jg
        if off == 2:
            a.b(0x2e, 0xa3); a.word('mr_dist')               # mov cs:[mr_dist], ax
    a.b(0x2e, 0x03, 0x06); a.word('mr_dist')                 # add ax, cs:[mr_dist]
    a.b(0x3b, 0xc2); a.short(0x73, 'nk_next')                # cmp ax, dx / jae
    a.b(0x8b, 0xd0, 0x8b, 0xfb)                              # mov dx, ax / mov di, bx   the nearest yet
    a.label('nk_next')
    a.b(0x41, 0x2e, 0x3a, 0x0e); a.word('coop'); a.short(0x72, 'nk_loop')   # inc cx / cmp cl, cs:[coop] / jb
    a.b(0x5a, 0x59, 0x5b, 0x58, 0xc3)                        # pop dx cx bx ax / ret

    # rat_tree (DIRTYRAT; 1000:32C4, mov si,[77E8h]: a ratman sits in the tree and counts [si+4Ah] down to its jump
    # at its knight, 3221): player 1's ratman stays there and takes the keys (83C0, then this site again). The
    # secondary button = it hangs the knight below it (the nearest standing within RAT_HANG_X in x and RAT_HANG_Z in
    # depth; 3589, as when a knight walks into it, and the knight breaks free with fire and down); fire = its jump
    # at the knight (32EC); a direction = a leap down that way (as rat_decide's)
    a.label('rules_rat_tree')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77E8h]   (replaced)
    a.b(0x2e, 0x3b, 0x36); a.word('mon_obj'); a.short(0x74, 'rt_mine')
    a.near(0xe9, 'rules_done')
    a.label('rt_mine')
    a.b(0x2e, 0x80, 0x3e); a.word('mon_have'); a.b(0x00); a.short(0x75, 'rt_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x01)     # first the keys: 83C0h, then here again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(PLAYER_INPUT & 0xff, PLAYER_INPUT >> 8)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0xc4, 0x32)
    a.near(0xe9, 'call_game')
    a.label('rt_keys')
    a.b(0x2e, 0xc6, 0x06); a.word('mon_have'); a.b(0x00)
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]   player 1's bits
    a.b(0xa8, 0x01); a.short(0x74, 'rt_left'); a.b(0xc6, 0x44, 0x08, 0x01)   # right: faces right
    a.label('rt_left')
    a.b(0xa8, 0x02); a.short(0x74, 'rt_sec'); a.b(0xc6, 0x44, 0x08, 0x03)    # left: faces left
    a.label('rt_sec')
    a.b(0x50, 0xb0, 0x00); a.near(0xe8, 'sec_input'); a.b(0x58)   # the secondary button?
    a.short(0x74, 'rt_fire')
    a.b(0x2e, 0xc7, 0x06); a.word('nk_rx'); a.b(RAT_HANG_X, 0x00)
    a.b(0x2e, 0xc7, 0x06); a.word('nk_rz'); a.b(RAT_HANG_Z, 0x00)
    a.near(0xe8, 'nearest_knight')                           # call nearest_knight   di
    a.b(0x0b, 0xff); a.short(0x74, 'rt_stay')                # or di, di / jz   none below
    a.b(0x89, 0x3e, 0x78, 0x09, 0x89, 0x3e, 0xea, 0x77)      # mov [0978h], di / mov [77EAh], di
    a.b(0x87, 0xf7)                                          # xchg si, di   3589: di = the ratman, si = the knight
    a.b(0xc7, 0x46, 0x02, 0x89, 0x35); a.near(0xe9, 'rules_done')   # mov word [bp+2], 3589h   the hanging
    a.label('rt_fire')
    a.b(0xa8, 0x10); a.short(0x74, 'rt_move')
    a.b(0xc7, 0x46, 0x02, 0xec, 0x32); a.near(0xe9, 'rules_done')   # mov word [bp+2], 32ECh   its jump at the knight
    a.label('rt_move')
    a.b(0xa8, 0x0f); a.short(0x74, 'rt_stay')
    a.b(0x83, 0x26, 0x9c, 0x77, 0xfb, 0xc7, 0x44, 0x48, 0x00, 0x00)   # and word [779Ch], 0FFFBh / mov word [si+48h], 0
    a.b(0x8b, 0xfe); a.near(0xe9, 'rd_leap')                 # mov di, si / jmp rd_leap   out of the tree
    a.label('rt_stay')
    a.b(0xc7, 0x44, 0x4a, 0x02, 0x00)                        # mov word [si+4Ah], 2   its count never ends
    a.near(0xe9, 'rules_done')

    # rat_escape (DIRTYRAT, co-op; 1000:32F9, 335F, call 83C0 while a ratman hangs a knight or rides on its back:
    # fire and down breaks free): as mud_escape, the knight held (rat_victim, noted by rat_hang and rat_ride) breaks
    # free by its own input; the game read player 1's keys, and in co-op it held the knight it fights now
    a.label('rules_rat_escape')
    a.b(0x50, 0x2e, 0xa1); a.word('rat_victim')              # push ax / mov ax, cs:[rat_victim]
    a.b(0x0b, 0xc0); a.short(0x74, 're_go')                  # or ax, ax / jz
    a.b(0xa3, 0x78, 0x09, 0xa3, 0xea, 0x77)                  # mov [0978h], ax / mov [77EAh], ax
    a.label('re_go')
    a.b(0x58); a.near(0xe9, 'held_keys')                     # pop ax / jmp held_keys
    # rat_hang (1000:3597), rat_ride (1000:3576): a ratman takes hold of a knight (si; it hangs it from the tree, or
    # jumps on its back): noted
    for name, script in (('rat_hang', 0x3bd4), ('rat_ride', 0x3800)):
        a.label('rules_' + name)
        a.b(0xc7, 0x06, 0x3a, 0x78, script & 0xff, script >> 8)   # mov word [783Ah], script   (replaced)
        a.b(0x2e, 0x89, 0x36); a.word('rat_victim')          # mov cs:[rat_victim], si
        a.near(0xe9, 'rules_done')

    # cheat_fight_end (from fight_end): IDDQD ends, the HP memory is cleared for the next fight
    a.label('cheat_fight_end')
    a.b(0x50, 0x51, 0x57, 0x06, 0x0e, 0x07)                  # push ax cx di es / push cs / pop es
    a.b(0x2e, 0x80, 0x26); a.word('cheat_flags'); a.b(0xff ^ CF_IDDQD)
    a.b(0x2e, 0xc6, 0x06); a.word('fight_begun'); a.b(0x00)
    a.b(0xbf); a.word('air_on'); a.b(0xb9, 3 * 25, 0x00, 0x32, 0xc0, 0xfc, 0xf3, 0xaa)   # air_on, air_vx, air_vy = 0
    a.b(0x2e, 0xf6, 0x06); a.word('q_added'); a.b(CF_FORE); a.short(0x74, 'cfe_fore')   # a queued FORE: off as typed again
    a.b(0x51, 0xb1, CHEAT_ID['FORE']); a.near(0xe8, 'fight_code'); a.b(0x59)
    a.label('cfe_fore')
    a.b(0x2e, 0xa0); a.word('q_added'); a.b(0x0c, CF_FORE, 0xf6, 0xd0)   # mov al, cs:[q_added] / or al, FORE / not al
    a.b(0x2e, 0x20, 0x06); a.word('cheat_flags')             # and cs:[cheat_flags], al
    a.b(0x2e, 0xc6, 0x06); a.word('q_added'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('dragon_ctl'); a.b(0x00)   # HOTSTUFF: this practice only
    a.b(0x2e, 0xc6, 0x06); a.word('mon_ctl'); a.b(0x00)      # DIRTYRAT ...: this fight only
    a.b(0x2e, 0xc6, 0x06); a.word('mon_dive'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('mon_crush'); a.b(0x00)
    a.b(0x2e, 0xc7, 0x06); a.word('mine_live'); a.b(0x00, 0x00)   # MINEFIELD: this fight only
    a.b(0x2e, 0xc6, 0x06); a.word('mine_vis'); a.b(0x00)
    a.near(0xe8, 'd48_fight_end')                            # D48: DARTS, DAGGERFALL, LIGHTSABER: this fight only
    a.near(0xe8, 'score_end')                                # D52: the practice fight's winner counted
    a.b(0x2e, 0xc6, 0x06); a.word('mine_req'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('mine_todo'); a.b(0x00)
    a.b(0x2e, 0x80, 0x3e); a.word('paw_set'); a.b(0x00); a.short(0x74, 'cfe_paw')   # HOTSTUFF's paw: the reaction back
    a.b(0x2e, 0xa1); a.word('paw_saved'); a.b(0xa3, (REACTIONS + PAW_TYPE) & 0xff, (REACTIONS + PAW_TYPE) >> 8)
    a.b(0x2e, 0xc6, 0x06); a.word('paw_set'); a.b(0x00)
    a.label('cfe_paw')
    a.b(0x2e, 0xc7, 0x06); a.word('mon_obj'); a.b(0x00, 0x00)
    a.b(0xbf); a.word('prev_hp'); a.b(0xb8, 0x00, 0x80, 0xb9, 25, 0x00, 0xfc, 0xf3, 0xab)   # prev_hp = 8000h x 25
    a.b(0x07, 0x5f, 0x59, 0x58, 0xc3)

    # action_done (K22; 1000:A5B8, replaces jmp A4B0 after a place's action, 1000:B000): the loop went back to its
    # start and read the input again before the end-of-turn check (A5FB), so Enter pressed as the action ended
    # (a fight, the city) started another action in the same turn. When the action used up the turn
    # ([CC98h] >= [CCACh], as the fight end 1000:038D and the places set it), go on to the checks instead
    a.label('rules_action_done')
    a.b(0xc7, 0x46, 0x02, MAP_LOOP & 0xff, MAP_LOOP >> 8)     # mov word [bp+2], A4B0h   as the game
    a.b(0x2e, 0xf6, 0x06); a.word('rules_table', G_EXPLOIT_FIXES); a.b(NO_EXTRA_TURN)   # test flags, extra turn
    a.short(0x74, 'ad_end')                                  # jz ad_end             speedrun mode: as the game
    a.b(0x50, 0xa1, 0x98, 0xcc, 0x3b, 0x06, 0xac, 0xcc, 0x58)   # push ax / mov ax, [CC98h] / cmp ax, [CCACh] / pop ax
    a.short(0x7c, 'ad_end')                                  # jl ad_end             steps left: on with the turn
    a.b(0xc7, 0x46, 0x02, AFTER_ACTION & 0xff, AFTER_ACTION >> 8)   # mov word [bp+2], A5BBh
    a.label('ad_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # potion_life (K23; 1000:CCB6-CCC2, the healing potion at full hit points: inc byte [si+31h], then lives 6 and
    # above become 5, compared unsigned): a lost Guardian fight takes one life at the fight's end and two more in the
    # Valley (1000:0FFF, no floor), and a lost fight leaves full hit points; a potion then took -2 (FEh) to -1 (FFh),
    # which the unsigned compare made 5. Now a knight without lives gets none back, and the cap is max_lives (5 in the game)
    a.label('rules_potion_life')
    a.b(0x2e, 0xf6, 0x06); a.word('rules_table', G_EXPLOIT_FIXES); a.b(POTION_LIFE)   # test flags, potion
    a.short(0x75, 'pl_fixed')                                # jnz pl_fixed
    a.b(0xfe, 0x44, 0x31, 0x80, 0x7c, 0x31, 0x06)            # inc byte [si+31h] / cmp byte [si+31h], 6   as the game
    a.short(0x72, 'pl_end')                                  # jb pl_end
    a.short(0xeb, 'pl_five')                                 # jmp pl_five
    a.label('pl_fixed')
    a.b(0x80, 0x7c, 0x31, 0x00)                              # cmp byte [si+31h], 0
    a.short(0x7e, 'pl_end')                                  # jle pl_end           no lives: none back
    a.b(0xfe, 0x44, 0x31, 0x50)                              # inc byte [si+31h] / push ax
    a.b(0x2e, 0xa0); a.word('rules_table', G_MAX_LIVES)      # mov al, cs:[max_lives]
    a.b(0x38, 0x44, 0x31); a.short(0x7e, 'pl_pop')           # cmp [si+31h], al / jle pl_pop
    a.b(0x88, 0x44, 0x31)                                    # mov [si+31h], al      the cap
    a.label('pl_pop')
    a.b(0x58)                                                # pop ax
    a.short(0xeb, 'pl_end')                                  # jmp pl_end
    a.label('pl_five')
    a.b(0xc6, 0x44, 0x31, 0x05)                              # mov byte [si+31h], 5
    a.label('pl_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # instant_kill (K25; 1000:0AB3, mov si,[8979h] in the routine 0AB2 that monsters' instant kills call: the troll's
    # club, the mudman, the Balok, the dragon...; it sets the knight's HP to -1): in co-op [8979h] is the first
    # knight standing, so another knight died while the one hit kept its HP and stood up again. In co-op the knight
    # the monster fights ([0978h], set for each object, D15) dies
    # The knight's own handler also calls it (1000:3EEA, when the dragon has eaten it, [77F0h] = 1) with si = that
    # knight, and so does a knight's death script (script call 1000:9DB3: di = the script's object, the knight
    # dying; [0978h] is then the first knight standing): then that knight is the one
    # The mudman's hold ends with the kill at 1000:554B (si = the mudman, di as a call left it): the knight it holds
    a.label('rules_instant_kill')
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'ik_coop')                                 # jne ik_coop
    a.near(0xe9, 'ik_game')                                  # jmp ik_game
    a.label('ik_coop')
    # the dragon has eaten a knight (dragon_eat): the knight's handler that kills (1000:3EEA, returning to 3EED)
    # runs for the next knight standing; the one eaten dies
    a.b(0x81, 0x7e, 0x0a, DRAGON_ATE & 0xff, DRAGON_ATE >> 8)   # cmp word [bp+10], 3EEDh
    a.short(0x75, 'ik_not_eaten')                            # jne ik_not_eaten
    a.b(0x2e, 0x83, 0x3e); a.word('dragon_victim'); a.b(0x00)   # cmp word cs:[dragon_victim], 0
    a.short(0x74, 'ik_not_eaten')                            # je ik_not_eaten
    a.label('ik_eaten')
    a.b(0x2e, 0x8b, 0x36); a.word('dragon_victim')           # mov si, cs:[dragon_victim]
    a.near(0xe9, 'ik_end')                                   # jmp ik_end
    a.label('ik_not_eaten')
    # the dragon's eating script (46F8) kills too (script call at 47B6: di = the dragon): the knight eaten
    a.b(0x81, 0xff, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)   # cmp di, 6E26h
    a.short(0x75, 'ik_not_dragon')                           # jne ik_not_dragon
    a.b(0x2e, 0x83, 0x3e); a.word('dragon_victim'); a.b(0x00)   # cmp word cs:[dragon_victim], 0
    a.short(0x75, 'ik_eaten')                                # jne ik_eaten
    a.label('ik_not_dragon')
    a.b(0x81, 0x7e, 0x0a, MUD_LET_GO & 0xff, MUD_LET_GO >> 8)   # cmp word [bp+10], 554Eh   (bp+8: the pushed si)
    a.short(0x75, 'ik_knights')                              # jne ik_knights
    a.b(0x2e, 0x83, 0x3e); a.word('mud_victim'); a.b(0x00)   # cmp word cs:[mud_victim], 0
    a.short(0x74, 'ik_knights')                              # je ik_knights
    a.b(0x2e, 0x8b, 0x36); a.word('mud_victim')              # mov si, cs:[mud_victim]
    a.short(0xeb, 'ik_end')                                  # jmp ik_end
    # K28: a monster's script calls the kill too (1000:9DB3, di = the monster): the Balok's bite and squeeze
    # (scripts 4E04, 50C4) and the mudman's pull from below (594C, a second kill after 54E0). [0978h] then is the
    # knight nearest it, another one: the knight it holds dies
    a.label('ik_knights')
    a.b(0x81, 0xff, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)   # cmp di, 6F08h
    a.short(0x72, 'ik_not_held')                             # jb ik_not_held
    a.b(0x80, 0x7d, 0x35, BALOK_TYPE)                        # cmp byte [di+35h], 18h
    a.short(0x75, 'ik_mudman')                               # jne ik_mudman
    a.b(0x2e, 0x83, 0x3e); a.word('balok_victim'); a.b(0x00) # cmp word cs:[balok_victim], 0
    a.short(0x74, 'ik_not_held')                             # je ik_not_held
    a.b(0x2e, 0x8b, 0x36); a.word('balok_victim')            # mov si, cs:[balok_victim]
    a.short(0xeb, 'ik_end')                                  # jmp ik_end
    a.label('ik_mudman')
    a.b(0x80, 0x7d, 0x35, MUDMAN)                            # cmp byte [di+35h], 2
    a.short(0x75, 'ik_not_held')                             # jne ik_not_held
    a.b(0x2e, 0x83, 0x3e); a.word('mud_victim'); a.b(0x00)   # cmp word cs:[mud_victim], 0
    a.short(0x74, 'ik_not_held')                             # je ik_not_held
    a.b(0x2e, 0x8b, 0x36); a.word('mud_victim')              # mov si, cs:[mud_victim]
    a.short(0xeb, 'ik_end')                                  # jmp ik_end
    a.label('ik_not_held')
    for rec in KNIGHTS:
        a.b(0x81, 0xfe, rec & 0xff, rec >> 8)                # cmp si, knight
        a.short(0x74, 'ik_end')                              # je ik_end
    for rec in KNIGHTS:
        a.b(0x81, 0xff, rec & 0xff, rec >> 8)                # cmp di, knight
        a.short(0x74, 'ik_di')                               # je ik_di
    a.b(0x8b, 0x36, 0x78, 0x09)                              # mov si, [0978h]
    a.short(0xeb, 'ik_end')                                  # jmp ik_end
    a.label('ik_di')
    a.b(0x8b, 0xf7)                                          # mov si, di
    a.short(0xeb, 'ik_end')                                  # jmp ik_end
    a.label('ik_game')
    a.b(0x8b, 0x36, 0x79, 0x89)                              # mov si, [8979h]   (replaced)
    a.label('ik_end')
    a.b(0x53); a.near(0xe8, 'obj_index'); a.short(0x72, 'ik_unmarked')   # push bx / call obj_index / jc
    a.b(0xd1, 0xfb, 0x2e, 0xc6, 0x87); a.word('cheat_killed'); a.b(0x01)   # sar bx, 1 / mov byte cs:[bx+cheat_killed], 1
    a.label('ik_unmarked')
    a.b(0x5b)                                                # pop bx
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # dragon_eat (K25; 1000:3AF3, replaces mov ax,[di+0Ch]: the dragon's bite on the knight it touched, which 98A2
    # then takes off the screen): the knight eaten, for instant_kill
    a.label('rules_dragon_eat')
    a.b(0x8b, 0x45, 0x0c)                                    # mov ax, [di+0Ch]   (replaced)
    a.b(0x2e, 0xa3); a.word('dragon_victim')                 # mov cs:[dragon_victim], ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # dragon_ate (K25; 1000:3AF9, replaces mov word [77F0h],1 after the bite): the flag made the next knight's
    # handler that ran kill itself and set its next script to 0 (1000:3EEA); in co-op another knight than the one
    # eaten, whose own handler no longer runs (98A2 took its animation off). In co-op the eating script's kill
    # (instant_kill) is enough: no flag
    a.label('rules_dragon_ate')
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'da_end')                                  # jne da_end
    a.b(0xc7, 0x06, 0xf0, 0x77, 0x01, 0x00)                  # mov word [77F0h], 1   (replaced)
    a.label('da_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # dragon_front (from update, the dragon's turn): the dragon always faces right (1000:3C2B sets +8 to 1 after
    # 3CFF has turned it to its knight) and keeps to x 30-100, so a knight that went past its x to the left edge
    # was behind it: never attacked, while its own blows hurt the dragon. The knights of the fight stay at least
    # DRAGON_FRONT in front of the dragon (its body is a wall); DRAGON_FRONT is the distance it backs off from
    # nearer knights itself (+54h), so it attacks them there
    a.label('dragon_front')
    a.b(0x50, 0x53, 0x51)                                    # push ax bx cx
    a.b(0xa1, (DRAGON_RECORD + 2) & 0xff, (DRAGON_RECORD + 2) >> 8)   # mov ax, [6E28h]   the dragon's x
    a.b(0x05, DRAGON_FRONT, 0x00)                            # add ax, DRAGON_FRONT
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'df_coop')                                 # jne df_coop
    a.b(0x8b, 0x1e, 0x79, 0x89)                              # mov bx, [8979h]   the one knight
    a.near(0xe8, 'df_one')                                   # call df_one
    a.short(0xeb, 'df_end')                                  # jmp df_end
    a.label('df_coop')
    a.b(0x33, 0xc9)                                          # xor cx, cx
    a.label('df_loop')
    a.b(0x8b, 0xd9, 0xd1, 0xe3)                              # mov bx, cx / shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('knight_list')             # mov bx, cs:[bx+knight_list]
    a.near(0xe8, 'df_one')                                   # call df_one
    a.b(0x41)                                                # inc cx
    a.b(0x2e, 0x3a, 0x0e); a.word('coop')                    # cmp cl, cs:[coop]
    a.short(0x72, 'df_loop')                                 # jb df_loop
    a.label('df_end')
    a.b(0x59, 0x5b, 0x58, 0xc3)                              # pop cx bx ax / ret
    a.label('df_one')                                        # bx = a knight, ax = the least x
    a.b(0x83, 0x7f, 0x38, 0x00); a.short(0x7e, 'df_ret')     # cmp word [bx+38h], 0 / jle   down
    a.b(0x39, 0x47, 0x02); a.short(0x7d, 'df_ret')           # cmp [bx+2], ax / jge
    a.b(0x89, 0x47, 0x02)                                    # mov [bx+2], ax
    # and its animation's x (+4), which the knight's moves start from
    a.b(0x56, 0x51, 0xbe, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # push si cx / mov si, 947Eh / mov cx, 10
    a.label('df_anim')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'df_anim_next')     # cmp byte [si], 0 / je   free
    a.b(0x39, 0x5c, 0x16); a.short(0x75, 'df_anim_next')     # cmp [si+16h], bx / jne
    a.b(0x89, 0x44, 0x04)                                    # mov [si+4], ax
    a.label('df_anim_next')
    a.b(0x83, 0xc6, ANIM_SIZE); a.short(0xe2, 'df_anim')     # add si, 24h / loop df_anim
    a.b(0x59, 0x5e)                                          # pop cx si
    a.label('df_ret')
    a.b(0xc3)                                                # ret

    # knight_down (K25; 1000:3ED0, the knight's handler, replaces mov word [7834h],0; si = the knight): it never looks
    # at the HP, so after an instant kill the knight played the monster's kill and got up again. In co-op a knight
    # with HP 0 or less gets the fall (1000:44AA: the death script, as when a blow takes the last HP) once, and then
    # nothing new (1000:3AEA: script -1, its last frame stays)
    # D20: also in the 3-4 knight practice, where a knight down stood up again once its last script ended (its HP
    # still 0), and stays where it lies there; a knight that died one of the new deaths (its script in DS:F480-FE50)
    # has fallen already
    a.label('rules_knight_down')
    a.b(0xc7, 0x06, 0x34, 0x78, 0x00, 0x00)                  # mov word [7834h], 0   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'kd_go')                                   # jne kd_go
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x75, 'kd_go')                                  # jne kd_go
    # D46: a knight whose extended death has ended stays down in a duel too (its control would read the keys and stand it up)
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7f, 'kdd_up')   # cmp word [si+38h], 0 / jg
    a.b(0x81, 0x7d, 0x02, D20_BASE & 0xff, D20_BASE >> 8); a.short(0x72, 'kdd_up')   # cmp [di+2], F480h / jb
    a.b(0x81, 0x7d, 0x02, D20_END & 0xff, D20_END >> 8); a.short(0x73, 'kdd_up')     # cmp [di+2], FE50h / jae
    a.b(0x89, 0x36, 0xe8, 0x77, 0xc7, 0x46, 0x02, 0xea, 0x3a); a.near(0xe9, 'rules_done')   # mov [77E8h], si / mov word [bp+2], 3AEAh   nothing new: it stays down
    a.label('kdd_up')
    a.near(0xe9, 'kd_end')
    a.label('kd_go')
    a.b(0x81, 0xfe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)      # cmp si, 6C9Eh
    a.short(0x72, 'kd_not')                                  # jb kd_not            not a knight
    a.b(0x81, 0xfe, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8)      # cmp si, 6DC4h
    a.short(0x76, 'kd_knight')                               # jbe kd_knight
    a.label('kd_not')
    a.near(0xe9, 'kd_end')                                   # jmp kd_end
    a.label('kd_knight')
    a.b(0x50, 0x51)                                          # push ax / push cx
    a.b(0x8b, 0xc6, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # mov ax, si / sub ax, 6C9Eh
    a.b(0xb1, 0x62, 0xf6, 0xf1, 0x8a, 0xd8, 0x32, 0xff)      # mov cl, 62h / div cl / mov bl, al / xor bh, bh
    a.b(0x83, 0x7c, 0x38, 0x00)                              # cmp word [si+38h], 0
    a.short(0x7f, 'kd_up')                                   # jg kd_up
    a.b(0x89, 0x36, 0xe8, 0x77)                              # mov [77E8h], si      for 1000:2D5E
    a.b(0x2e, 0x80, 0xbf); a.word('down'); a.b(0x00)         # cmp byte cs:[bx+down], 0
    a.b(0xc7, 0x46, 0x02, 0xea, 0x3a)                        # mov word [bp+2], 3AEAh   nothing new (flags kept)
    a.short(0x74, 'kd_fall')                                 # je kd_fall
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'kd_hold')                                 # je kd_hold  the 3-4 knight practice: it stays
    # after the fall the knight goes off the screen (x 480, as far right as monsters wait), so that a knight down
    # can never be seen standing again; di = its animation slot (the update pass, 1000:98FC)
    a.b(0xc7, 0x44, 0x02, 0xe0, 0x01, 0xc7, 0x45, 0x04, 0xe0, 0x01)   # mov word [si+2], 480 / mov word [di+4], 480
    a.short(0xeb, 'kd_pop')                                  # jmp kd_pop
    a.label('kd_fall')
    a.b(0x2e, 0xc6, 0x87); a.word('down'); a.b(0x01)         # mov byte cs:[bx+down], 1
    a.b(0x53, 0xd1, 0xe3, 0x2e, 0xc7, 0x87); a.word('held'); a.b(0x00, 0x00, 0x5b)   # D60: push bx / shl bx, 1 / mov word cs:[bx+held], 0 / pop bx
    a.b(0x81, 0x7d, 0x02, D20_BASE & 0xff, D20_BASE >> 8); a.short(0x72, 'kd_fall_now')   # cmp [di+2], F480h / jb
    a.b(0x81, 0x7d, 0x02, D20_END & 0xff, D20_END >> 8); a.short(0x72, 'kd_d20')         # cmp [di+2], FE50h / jb
    a.label('kd_fall_now')
    a.b(0xc7, 0x46, 0x02, 0xaa, 0x44)                        # mov word [bp+2], 44AAh   the fall
    a.short(0xeb, 'kd_pop')                                  # jmp kd_pop
    a.label('kd_d20')
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00); a.short(0x75, 'kd_pop')   # cmp byte cs:[coop], 0 / jne kd_pop
    a.label('kd_hold')
    a.near(0xe8, 'hold_body')                                # call hold_body   D60: the 3-4 knight practice
    a.short(0xeb, 'kd_pop')                                  # jmp kd_pop
    a.label('kd_up')
    a.b(0x2e, 0xc6, 0x87); a.word('down'); a.b(0x00)         # mov byte cs:[bx+down], 0
    a.b(0x53, 0xd1, 0xe3, 0x2e, 0xc7, 0x87); a.word('held'); a.b(0x00, 0x00, 0x5b)   # D60: push bx / shl bx, 1 / mov word cs:[bx+held], 0 / pop bx
    a.label('kd_pop')
    a.b(0x59, 0x58)                                          # pop cx / pop ax
    a.label('kd_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # D60: hold_body (di = the animation slot, si = a knight's record, from knight_down and bk_down in the 3-4 knight
    # practice; the knight is dead and lies). There no knight down is drawn into the background (rules_draw: knights
    # 3 and 4 lay blue), so the body was only the pixels its last frame left on the screen: once its script had ended
    # (FF FF, slot +1 = 0) nothing drew it again, and whatever was drawn over it later (the others fighting on) took
    # it away. Once that script has ended, the slot plays its last repeated frame again: the counters' (+1Ch) restart
    # point (+2, the death's last frame, set by 84h: D20's 84 02, the plain fall's 84 50), repeated (count FFh,
    # kept up by hold_refresh), drawn live in the knight's own colours. cs:[held + 2 * knight] = that frame.
    a.label('hold_body')
    a.b(0x81, 0xfe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'hb_ret')   # cmp si, 6C9Eh / jb
    a.b(0x81, 0xfe, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8); a.short(0x77, 'hb_ret')   # cmp si, 6DC4h / ja
    a.b(0x80, 0x7d, 0x01, 0x00); a.short(0x75, 'hb_ret')     # cmp byte [di+1], 0 / jne   its script still plays
    a.b(0x50, 0x53, 0x51)                                    # push ax bx cx
    a.b(0x8b, 0x5d, 0x1c, 0x8b, 0x4f, 0x02)                  # mov bx, [di+1Ch] / mov cx, [bx+2]   the last frame
    a.short(0xe3, 'hb_pop')                                  # jcxz hb_pop
    a.b(0xc6, 0x07, 0xff, 0xc6, 0x47, 0x01, 0x01)            # mov byte [bx], 0FFh / mov byte [bx+1], 1   repeated
    a.b(0x89, 0x4d, 0x02, 0xc6, 0x45, 0x01, 0x01)            # mov [di+2], cx / mov byte [di+1], 1   playing
    a.b(0x8b, 0xc6, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # mov ax, si / sub ax, 6C9Eh
    a.b(0xb3, 0x62, 0xf6, 0xf3, 0x8a, 0xd8, 0x32, 0xff, 0xd1, 0xe3)   # mov bl, 62h / div bl / mov bl, al / xor bh, bh / shl bx, 1
    a.b(0x2e, 0x89, 0x8f); a.word('held')                    # mov cs:[bx+held], cx
    a.label('hb_pop')
    a.b(0x59, 0x5b, 0x58)                                    # pop cx bx ax
    a.label('hb_ret')
    a.b(0xc3)                                                # ret
    # hold_refresh (D60, from rules_draw in the 3-4 knight practice; di = the animation slot, bx = its object): a dead
    # knight's slot that repeats its held frame gets its count back to FFh, so that the repeat never runs out (it would
    # go on in the script: D20's end of the fight, native 0231, again)
    a.label('hold_refresh')
    a.b(0x81, 0xfb, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'hrf_ret')   # cmp bx, 6C9Eh / jb
    a.b(0x81, 0xfb, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8); a.short(0x77, 'hrf_ret')   # cmp bx, 6DC4h / ja
    a.b(0x83, 0x7f, 0x38, 0x00); a.short(0x7f, 'hrf_ret')     # cmp word [bx+38h], 0 / jg   standing
    a.b(0x50, 0x53, 0x56)                                    # push ax bx si
    a.b(0x8b, 0xc3, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # mov ax, bx / sub ax, 6C9Eh
    a.b(0xb3, 0x62, 0xf6, 0xf3, 0x8a, 0xd8, 0x32, 0xff, 0xd1, 0xe3)   # mov bl, 62h / div bl / mov bl, al / xor bh, bh / shl bx, 1
    a.b(0x2e, 0x8b, 0x87); a.word('held')                    # mov ax, cs:[bx+held]
    a.b(0x0b, 0xc0); a.short(0x74, 'hrf_pop')                 # or ax, ax / jz   not held
    a.b(0x8b, 0x75, 0x1c, 0x3b, 0x44, 0x02); a.short(0x75, 'hrf_pop')   # mov si, [di+1Ch] / cmp ax, [si+2] / jne
    a.b(0x80, 0x7c, 0x01, 0x00); a.short(0x74, 'hrf_pop')     # cmp byte [si+1], 0 / je
    a.b(0xc6, 0x04, 0xff)                                    # mov byte [si], 0FFh
    a.label('hrf_pop')
    a.b(0x5e, 0x5b, 0x58)                                    # pop si bx ax
    a.label('hrf_ret')
    a.b(0xc3)                                                # ret

    # troll_target (K25; 1000:55F9, mov si,6C9Eh / cmp word [si+38h],0: the troll (handler 55D0) looks only at knight
    # 1's HP, so in co-op it went idle, often off the screen, once knight 1 was down): in co-op the knight it fights
    # mud_target, mud_grab, mud_pull (K25): the mudman keeps its hold in one game-wide state ([7B8Ch]: 1 holding,
    # 2 pulling under, 4 pulled from below, 40h let go) but each frame acted on the knight it fights now ([77EAh] =
    # [0978h]). In co-op that changes: it held one knight and pulled another under, or let another go (the pause is
    # a toggle, 1000:9892), so knights stayed frozen and the wrong one died. The knight it takes hold of
    # (1000:559C, mov ax,[si+0Ch]; 54DB, mov ax,di) stays its knight while the state lasts (1000:52FE, mov ax,[0978h])
    # A pull from below (4) is never cleared: the game's fight is over then. In co-op, once the mudman that pulled has
    # left, the others fight on. It has left when its object is no longer in use or no longer rising under a knight
    # (+48h 8 and 10h): its slot can hold a new mudman by then (the top-up), which stood still for good
    a.label('rules_mud_target')
    a.b(0xa1, 0x78, 0x09)                                    # mov ax, [0978h]   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'mud_end')                                 # je mud_end
    a.b(0xf6, 0x06, 0x8c, 0x7b, 0x04)                        # test byte [7B8Ch], 4
    a.short(0x74, 'mud_held')                                # jz mud_held
    a.b(0x53, 0x2e, 0x8b, 0x1e); a.word('mud_puller')        # push bx / mov bx, cs:[mud_puller]
    a.b(0x0b, 0xdb); a.short(0x74, 'mud_free')               # or bx, bx / jz mud_free
    a.b(0x83, 0x3f, 0x00); a.short(0x74, 'mud_free')         # cmp word [bx], 0 / je mud_free
    a.b(0x8a, 0x5f, 0x48, 0x80, 0xe3, MUD_PULLING)           # mov bl, [bx+48h] / and bl, 18h
    a.b(0x80, 0xfb, MUD_PULLING); a.short(0x74, 'mud_pulling')   # cmp bl, 18h / je mud_pulling
    a.label('mud_free')
    a.b(0x80, 0x26, 0x8c, 0x7b, 0xfb)                        # and byte [7B8Ch], 0FBh
    a.b(0x2e, 0xc7, 0x06); a.word('mud_victim'); a.b(0x00, 0x00)   # mov word cs:[mud_victim], 0
    a.b(0x2e, 0xc7, 0x06); a.word('mud_puller'); a.b(0x00, 0x00)   # mov word cs:[mud_puller], 0
    a.label('mud_pulling')
    a.b(0x5b)                                                # pop bx
    a.label('mud_held')
    a.b(0xf7, 0x06, 0x8c, 0x7b, 0x47, 0x00)                  # test word [7B8Ch], 47h
    a.short(0x74, 'mud_end')                                 # jz mud_end         holding none
    a.b(0x2e, 0x83, 0x3e); a.word('mud_victim'); a.b(0x00)   # cmp word cs:[mud_victim], 0
    a.short(0x74, 'mud_end')                                 # je mud_end
    a.b(0x2e, 0xa1); a.word('mud_victim')                    # mov ax, cs:[mud_victim]
    a.label('mud_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('rules_mud_grab')
    a.b(0x8b, 0x44, 0x0c)                                    # mov ax, [si+0Ch]  (replaced) the knight it touched
    a.short(0xeb, 'mud_keep')                                # jmp mud_keep
    a.label('rules_mud_pull')
    a.b(0x8b, 0xc7)                                          # mov ax, di        (replaced)
    a.b(0x2e, 0x89, 0x36); a.word('mud_puller')              # mov cs:[mud_puller], si   the mudman pulling
    a.label('mud_keep')
    a.b(0x2e, 0xa3); a.word('mud_victim')                    # mov cs:[mud_victim], ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # balok_target, balok_grab (K28): the Balok's hold ([7794h]: 1 grabbing, 20h shaking) pauses the knight it
    # touched (1000:37A7, mov ax,di / call 9892) and lets go of the knight it fights then ([0978h], 37FC: pause
    # toggled, placed beside it). In co-op that can be another: the knight held stayed frozen and the fight stuck.
    # The knight it takes hold of stays its knight while the hold lasts (1000:35AF, mov ax,[0978h]); and the Balok's
    # frames of the hold draw that knight in its colours (draw)
    a.label('rules_balok_target')
    a.b(0xa1, 0x78, 0x09)                                    # mov ax, [0978h]   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'bt_end')                                  # je bt_end
    a.b(0xf7, 0x06, 0x94, 0x77, 0x21, 0x00)                  # test word [7794h], 21h
    a.short(0x74, 'bt_end')                                  # jz bt_end          holding none
    a.b(0x2e, 0x83, 0x3e); a.word('balok_victim'); a.b(0x00) # cmp word cs:[balok_victim], 0
    a.short(0x74, 'bt_end')                                  # je bt_end
    a.b(0x2e, 0xa1); a.word('balok_victim')                  # mov ax, cs:[balok_victim]
    a.b(0xa3, 0x78, 0x09)                                    # mov [0978h], ax   (37FC and 3816 read it)
    a.label('bt_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('rules_balok_grab')
    a.b(0x8b, 0xc7)                                          # mov ax, di        (replaced) the knight it touched
    a.b(0x2e, 0xa3); a.word('balok_victim')                  # mov cs:[balok_victim], ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # trogg_impale (K28; 1000:2F90, mov ax,si / call 98A2: the spear trogg takes a fallen knight off the screen, si,
    # and plays its frames with the knight on its spear, script 2488): the trogg's own frames draw that knight with
    # pixels 6-8, so the draw recolours them as the knight; each trogg (di) keeps its own
    # D20: a slumped knight (KN*.OB, HE*.OB) gets the thrust instead (as a knight's), and the trogg goes back to
    # standing (2F9E)
    a.label('rules_trogg_impale')
    a.b(0x50, 0x53, 0x56, 0x57, 0x87, 0xf7)                  # push ax bx si di / xchg si, di   si: the trogg
    a.near(0xe8, 'd20_state')                                # call d20_state   ZF = 1: the new deaths
    a.short(0x75, 'ti_spear')                                # jne ti_spear
    a.near(0xe8, 'slumped')                                  # call slumped   (di: the knight; bx: its animation)
    a.short(0x75, 'ti_spear')                                # jnz ti_spear
    a.near(0xe8, 'de_side')                                  # call de_side   CF = 1 from the front
    a.b(0xb8, D20['thrust_back'] & 0xff, D20['thrust_back'] >> 8); a.short(0x73, 'ti_set')
    a.b(0xb8, D20['thrust_front'] & 0xff, D20['thrust_front'] >> 8)
    a.label('ti_set')
    a.near(0xe8, 'set_script')                               # call set_script
    a.b(0xc7, 0x46, 0x02, 0x9e, 0x2f)                        # mov word [bp+2], 2F9Eh
    a.b(0x5f, 0x5e, 0x5b, 0x58)                              # pop di si bx ax
    a.near(0xe9, 'rules_done')
    a.label('ti_spear')
    a.b(0x5f, 0x5e, 0x5b, 0x58)                              # pop di si bx ax
    a.b(0x8b, 0xc6)                                          # mov ax, si        (replaced)
    a.b(0x53); a.near(0xe8, 'slot_index')                    # push bx / call slot_index (bx = di's index * 2)
    a.short(0x72, 'ti_end')                                  # jc ti_end
    a.b(0x2e, 0x89, 0x87); a.word('impaled')                 # mov cs:[bx+impaled], ax
    a.label('ti_end')
    a.b(0x5b)                                                # pop bx
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    # spear_on (D20; 1000:4357, mov di,[di+0Eh] / si = 2488h: the spear trogg's blow on a fallen knight, with
    # blood on, takes it on the spear): a slumped knight goes to its death instead (2D5E picks the thrust)
    a.label('rules_spear_on')
    a.near(0xe8, 'd20_state')                                # call d20_state   ZF = 1: the new deaths
    a.short(0x75, 'so_spear')                                # jne so_spear
    a.b(0x53); a.near(0xe8, 'slumped'); a.b(0x5b)            # push bx / call slumped / pop bx
    a.short(0x75, 'so_spear')                                # jnz so_spear
    a.b(0xc7, 0x06, 0x3a, 0x78, 0x28, 0x13)                  # mov word [783Ah], 1328h   a next script to pick on
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d)                        # mov word [bp+2], 2D5Eh
    a.near(0xe9, 'rules_done')
    a.label('so_spear')
    a.b(0x8b, 0x7d, 0x0e)                                    # mov di, [di+0Eh]   (replaced)
    a.near(0xe9, 'rules_done')
    # slumped: di = an object -> ZF = 1 if it is a player's knight drawn from KN*.OB or HE*.OB in the slumped pose
    # (script 130E-134B), bx = its animation
    a.label('slumped')
    a.near(0xe8, 'victim_slot'); a.short(0x72, 'sl_no')      # call victim_slot / jc   a knight or a monster slot
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x74, 'sl_type')    # cmp byte [di+35h], 6 / je   a player's knight
    a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, 'sl_no')   # or the computer's (a Black Knight)
    a.label('sl_type')
    a.near(0xe8, 'anim_of'); a.short(0x75, 'sl_no')          # call anim_of / jnz
    a.b(0x50, 0x8b, 0x47, 0x18, 0x3d, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8); a.short(0x74, 'sl_bank')
    a.b(0x3d, HE_BANK & 0xff, HE_BANK >> 8); a.short(0x75, 'sl_pop')
    a.label('sl_bank')
    a.b(0x8b, 0x47, 0x02, 0x3d, SLUMP & 0xff, SLUMP >> 8); a.short(0x72, 'sl_nz')   # mov ax, [bx+2] / cmp / jb
    a.b(0x3d, SLUMP_END & 0xff, SLUMP_END >> 8); a.short(0x73, 'sl_nz')            # cmp ax, 134Ch / jae
    a.b(0x3b, 0xc0)                                          # cmp ax, ax   ZF = 1
    a.short(0xeb, 'sl_pop')
    a.label('sl_nz')
    a.b(0x0b, 0xe4)                                          # or sp, sp   ZF = 0 (sp is never 0)
    a.label('sl_pop')
    a.b(0x58, 0xc3)                                          # pop ax / ret
    a.label('sl_no')
    a.b(0x0b, 0xe4, 0xc3)                                    # or sp, sp / ret   ZF = 0
    # set_script: bx = an animation, ax = a script: as 1000:97FA (its counters cleared, the script started)
    a.label('set_script')
    a.b(0x06, 0x1e, 0x07, 0x57, 0x51, 0x50, 0x8b, 0x7f, 0x1c)   # push es / push ds / pop es / push di cx ax / mov di, [bx+1Ch]
    a.b(0xb9, 0x0d, 0x00, 0x33, 0xc0, 0xfc, 0xf3, 0xab)      # mov cx, 13 / xor ax, ax / cld / rep stosw
    a.b(0x58, 0x59, 0x5f, 0x07)                              # pop ax cx di es
    a.b(0x89, 0x47, 0x02, 0xc6, 0x47, 0x01, 0x01, 0xc3)      # mov [bx+2], ax / mov byte [bx+1], 1 / ret

    # slot_index: di = an object -> bx = its monster slot * 2, CF = 1 if not in a monster slot
    a.label('slot_index')
    a.b(0x50, 0x52, 0x8b, 0xc7)                              # push ax dx / mov ax, di
    a.b(0x2d, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)      # sub ax, 6F08h
    a.short(0x72, 'si_end')                                  # jb si_end            CF
    a.b(0x33, 0xd2, 0xbb, SLOT_SIZE, 0x00, 0xf7, 0xf3)       # xor dx, dx / mov bx, 62h / div bx
    a.b(0x8b, 0xd8, 0xd1, 0xe3)                              # mov bx, ax / shl bx, 1
    a.b(0x3d, MONSTER_COUNT, 0x00, 0xf5)                     # cmp ax, 20 / cmc       CF if 20 or more
    a.label('si_end')
    a.b(0x5a, 0x58, 0xc3)                                    # pop dx ax / ret

    # death (D20; 1000:2D5E, mov di,[77E8h]: an object's handler ends with its next script in [783Ah]): a knight
    # (a player's, drawn from KN*.OB) in the slumped pose of its fall that is hit again gets a death by the blow:
    # a knight's or Black Knight's up strike splits it, its down and forward thrust goes through the helmet, its
    # back strike down through the helmet, its up and forward strike lifts it on the sword; a dagger stays in the
    # helmet; the axe trogg splits, a ratman's thrust goes through. Through the helmet and the dagger: from the
    # front or from behind, by the side the blow comes from and the way the knight faces (anim +14h bit 1: drawn
    # mirrored, its face to the left)
    # death_animations (custom rules): extended = these deaths and a slump of 29 frames; vanilla = the game's (its
    # beheading, a slump of 20); off = also no blood: the game's gore setting ([0700h]) held at 1 in a fight
    a.label('rules_death')
    a.b(0x8b, 0x3e, 0xe8, 0x77)                              # mov di, [77E8h]   (replaced)
    a.near(0xe8, 'td_note_attack')                           # D46
    a.near(0xe8, 'pick_death')                               # call pick_death
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    # pick_death (di = the knight, [783Ah] its next script): the death for a slumped knight hit again, into
    # [783Ah] (also for FINISHHIM and ABACABB, cheat_finish)
    a.label('pick_death')
    a.b(0x50, 0x53, 0x51, 0x56)                              # push ax bx cx si
    a.b(0x2e, 0xa0); a.word('rules_table', G_DEATHS)         # mov al, cs:[death_animations]
    a.b(0x0a, 0xc0); a.short(0x75, 'de_not_on')              # or al, al / jnz de_not_on
    a.near(0xe8, 'deaths_gore')                              # D22: gore off or below K18: no fatalities
    a.short(0x74, 'de_on')                                   # je de_on             extended
    a.label('de_not_on')
    a.b(0xc6, 0x06, 0x13, 0x13, 0x14)                        # mov byte [1313h], 20   the slump's frames
    a.b(0x3c, DEATHS['off']); a.short(0x75, 'de_off_done')   # cmp al, 2 / jne
    a.b(0xc7, 0x06, 0x00, 0x07, 0x01, 0x00)                  # mov word [0700h], 1   no blood
    a.label('de_off_done')
    a.near(0xe8, 'deaths_gore')                              # suppress the vanilla beheading too, in every death mode
    a.short(0x74, 'de_vanilla_done')
    a.b(0x81, 0x3e, 0x3a, 0x78, BEHEADING & 0xff, BEHEADING >> 8)   # cmp word [783Ah], 1386h
    a.short(0x75, 'de_vanilla_done')
    a.b(0xc7, 0x06, 0x3a, 0x78, PLAIN_DEATH & 0xff, PLAIN_DEATH >> 8)   # mov word [783Ah], 1310h
    a.label('de_vanilla_done')
    a.near(0xe9, 'de_done')
    a.label('de_on')
    a.b(0xc6, 0x06, 0x13, 0x13, SLUMP_FRAMES)                # mov byte [1313h], 29
    a.b(0x8b, 0x36, 0x3a, 0x78)                              # mov si, [783Ah]   its next script
    a.b(0x8d, 0x44, 0x01, 0x3d, 0x01, 0x00)                  # lea ax, [si+1] / cmp ax, 1
    a.short(0x77, 'de_some')                                 # ja de_some        not 0 or FFFFh
    a.near(0xe9, 'de_done')
    a.label('de_some')
    a.near(0xe8, 'victim_slot'); a.short(0x72, 'de_done_1')  # call victim_slot / jc   a knight or a monster slot
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x74, 'de_type')    # cmp byte [di+35h], 6 / je   a player's knight
    a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, 'de_done_1')   # or the computer's (a Black Knight)
    a.label('de_type')
    a.b(0xbb, 0x7e, 0x94, 0xb9, 0x0a, 0x00)                  # mov bx, 947Eh / mov cx, 10   its animation
    a.label('de_slot')
    a.b(0x39, 0x7f, 0x16); a.short(0x74, 'de_found')         # cmp [bx+16h], di / je de_found
    a.b(0x83, 0xc3, 0x24); a.short(0xe2, 'de_slot')          # add bx, 24h / loop de_slot
    a.label('de_done_1')
    a.near(0xe9, 'de_done')
    a.label('de_found')
    a.b(0x8b, 0x47, 0x02)                                    # mov ax, [bx+2]   its script now
    a.b(0x3d, SLUMP & 0xff, SLUMP >> 8); a.short(0x72, 'de_done_1')            # cmp ax, 130Eh / jb
    a.b(0x3d, SLUMP_END & 0xff, SLUMP_END >> 8); a.short(0x73, 'de_done_1')    # cmp ax, 1328h / jae
    # drawn from the knights' banks (the animation's own table: a duel's second knight uses HE*.OB, 8949h)
    a.b(0x8b, 0x47, 0x18, 0x3d, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8); a.short(0x74, 'de_bank')   # mov ax, [bx+18h] / cmp
    a.b(0x3d, HE_BANK & 0xff, HE_BANK >> 8); a.short(0x75, 'de_done_1')
    a.label('de_bank')
    # a dagger that hit it (+0Eh): its death, at the head if the dagger's top is less than 12 below the knight's
    # (a dagger from the right was not always noted at the hit)
    a.b(0x8b, 0x75, 0x0e, 0x0b, 0xf6); a.short(0x74, 'de_table')   # mov si, [di+0Eh] / or si, si / jz
    a.b(0x80, 0x7c, 0x35, DAGGER); a.short(0x75, 'de_table')       # cmp byte [si+35h], 1Ah / jne
    a.b(0x57, 0x53, 0x8b, 0xfe); a.near(0xe8, 'anim_of')           # push di bx / mov di, si / call anim_of
    a.b(0xb0, 0x00); a.short(0x75, 'de_dh_done')                   # mov al, 0 / jnz   (mov keeps ZF)
    a.b(0x8b, 0x4f, 0x0c, 0x5b, 0x53, 0x2b, 0x4f, 0x0c)            # mov cx, [bx+0Ch] / pop bx / push bx / sub cx, [bx+0Ch]
    a.b(0x83, 0xf9, HEAD_ZONE); a.short(0x7d, 'de_dh_done')        # cmp cx, 12 / jge
    a.b(0xfe, 0xc0)                                                # inc al
    a.label('de_dh_done')
    a.b(0x5b, 0x5f)                                                # pop bx di
    a.near(0xe9, 'de_dagger')                                      # jmp de_dagger   (al: the height)
    a.label('de_done_2')
    a.near(0xe9, 'de_done')
    a.label('de_table')
    # who hit it and how, as noted at the hit (hit_pair): a strike's +28h may be over by now
    a.b(0x53); a.near(0xe8, 'victim_slot')                   # push bx / call victim_slot
    a.b(0x2e, 0x8b, 0xb7); a.word('last_hitter')             # mov si, cs:[bx+last_hitter]
    a.b(0x2e, 0x8b, 0x87); a.word('last_strike'); a.b(0x5b)  # mov ax, cs:[bx+last_strike] / pop bx
    a.b(0x0b, 0xf6); a.short(0x74, 'de_done_2')              # or si, si / jz
    a.b(0x80, 0xfc, 0x06); a.short(0x74, 'de_knight')        # cmp ah, 6 / je    (ah: its type, al: its strike)
    a.b(0x80, 0xfc, COMPUTER_TYPE); a.short(0x74, 'de_knight')
    a.b(0x80, 0xfc, DAGGER_TYPE); a.short(0x74, 'de_dagger')
    a.b(0x80, 0xfc, SPEAR_TROGG); a.short(0x74, 'de_thrust')
    a.b(0x80, 0xfc, AXE_TROGG); a.short(0x75, 'de_ratman')
    a.b(0x3c, UP); a.short(0x74, 'de_split'); a.short(0xeb, 'de_done_2')   # its swing: the game's beheading
    a.label('de_ratman')
    a.b(0x80, 0xfc, RATMAN); a.short(0x75, 'de_done_2')
    a.b(0x3c, DOWN_FORWARD); a.short(0x74, 'de_thrust'); a.short(0xeb, 'de_done_2')
    a.label('de_knight')
    a.b(0x3c, UP); a.short(0x74, 'de_split')
    a.b(0x3c, DOWN_FORWARD); a.short(0x74, 'de_thrust')
    a.b(0x3c, BACK); a.short(0x74, 'de_back'); a.short(0xeb, 'de_done_2')
    a.label('de_split')
    a.b(0xb8, D20['split'] & 0xff, D20['split'] >> 8); a.short(0xeb, 'de_set')
    a.label('de_back')
    a.b(0xb8, D20['back'] & 0xff, D20['back'] >> 8); a.short(0xeb, 'de_set')
    a.label('de_dagger')
    a.b(0x8a, 0xc8)                                          # mov cl, al   1: at the head's height (hit_pair)
    a.near(0xe8, 'de_side')                                  # call de_side   CF = 1 from the front
    a.short(0x72, 'de_dagger_front')
    a.b(0x0a, 0xc9, 0xb8, D20['dagger_waist_back'] & 0xff, D20['dagger_waist_back'] >> 8); a.short(0x74, 'de_set')   # or cl, cl / mov ax / jz
    a.b(0xb8, D20['dagger_back'] & 0xff, D20['dagger_back'] >> 8); a.short(0xeb, 'de_set')
    a.label('de_dagger_front')
    a.b(0x0a, 0xc9, 0xb8, D20['dagger_waist_front'] & 0xff, D20['dagger_waist_front'] >> 8); a.short(0x74, 'de_set')
    a.b(0xb8, D20['dagger_front'] & 0xff, D20['dagger_front'] >> 8); a.short(0xeb, 'de_set')
    a.label('de_thrust')
    a.near(0xe8, 'de_side')
    a.b(0xb8, D20['thrust_back'] & 0xff, D20['thrust_back'] >> 8); a.short(0x73, 'de_set')
    a.b(0xb8, D20['thrust_front'] & 0xff, D20['thrust_front'] >> 8)
    a.label('de_set')
    a.b(0xa3, 0x3a, 0x78)                                    # mov [783Ah], ax
    a.label('de_done')
    a.b(0x5e, 0x59, 0x5b, 0x58, 0xc3)                        # pop si cx bx ax / ret
    # dagger_near (D20; 1000:3E59, cmp word [si+0Ch],0 in the dagger's handler: has it hit): a dagger flies at a
    # standing knight's height and went over a knight slumped on its knees. Its box (animation +0Ah, +0Ch, +0Eh,
    # +10h: left, top, width, height) against a slumped knight's, up to 14 above it and 8 apart in depth: the
    # knight gets the dagger's death (from the front if the dagger flies against the way it faces) and the dagger
    # ends as after a hit (3EB0)
    a.label('rules_dagger_near')
    # D49: a dagger from the sky (its own thrower, +5Ch) falls until it hits or leaves the screen.
    a.b(0x39, 0x74, DAGGER_OWNER); a.short(0x75, 'dn_thrown')   # cmp [si+5Ch], si / jne
    a.b(0x83, 0x7c, 0x0c, 0x00); a.short(0x75, 'dn_fall_end') # cmp word [si+0Ch], 0 / jne   already hit
    a.b(0xc7, 0x06, 0x3a, 0x78, DF_SCRIPT & 0xff, DF_SCRIPT >> 8)   # mov word [783Ah], its script
    a.b(0x83, 0x44, 0x04, DF_FALL)                           # add word [si+4], fall   (down the screen)
    a.b(0x50, 0x8b, 0x44, 0x04, 0x03, 0x44, 0x06, 0x3d, DF_BOTTOM & 0xff, DF_BOTTOM >> 8, 0x58)   # push ax / mov ax, [si+4] / add ax, [si+6] / cmp ax, 200 / pop ax
    a.short(0x7c, 'dn_fall_alive')                           # jl   until it is past the screen's bottom
    a.label('dn_fall_end')
    a.b(0xc7, 0x46, 0x02, 0xb0, 0x3e)                        # mov word [bp+2], 3EB0h   the dagger ends
    a.near(0xe9, 'rules_done')
    a.label('dn_fall_alive')
    a.b(0xc7, 0x46, 0x02, 0x5f, 0x3e)                        # mov word [bp+2], 3E5Fh   continue after the hit check
    a.near(0xe9, 'rules_done')
    a.label('dn_thrown')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_GUNSHOT); a.short(0x74, 'dn_ngun')   # D64: GUNSHOT: a ball
    a.near(0xe8, 'gun_write'); a.near(0xe8, 'gun_bank')      # (also one thrown before the code)
    a.b(0xc7, 0x06, 0x3a, 0x78, GUN_FLY & 0xff, GUN_FLY >> 8)   # mov word [783Ah], its flight
    a.label('dn_ngun')
    a.b(0x50, 0x53, 0x51, 0x57, 0x56)                        # push ax bx cx di si
    a.near(0xe8, 'd20_state')                                # call d20_state   ZF = 1: the new deaths
    a.short(0x74, 'dn_on'); a.near(0xe9, 'dn_none')          # jne dn_none
    a.label('dn_on')
    a.b(0x8b, 0xfe); a.near(0xe8, 'anim_of')                 # mov di, si / call anim_of   the dagger's
    a.short(0x74, 'dn_have')                                 # jz dn_have
    a.near(0xe9, 'dn_none')
    a.label('dn_have')
    a.b(0x8b, 0xf3)                                          # mov si, bx      the dagger's animation
    a.b(0xbf, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8, 0xb9, 4 + MONSTER_COUNT, 0x00)   # mov di, 6C9Eh / mov cx, 24
    a.label('dn_knight')
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x74, 'dn_type')    # cmp byte [di+35h], 6 / je
    a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, 'dn_next_1')   # or a computer's knight
    a.label('dn_type')
    a.near(0xe8, 'anim_of'); a.short(0x75, 'dn_next_1')      # call anim_of / jnz
    a.b(0x8b, 0x47, 0x18, 0x3d, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8); a.short(0x74, 'dn_bank')   # its bank table
    a.b(0x3d, HE_BANK & 0xff, HE_BANK >> 8); a.short(0x75, 'dn_next_1')
    a.label('dn_bank')
    a.b(0x8b, 0x47, 0x02)                                    # mov ax, [bx+2]
    a.b(0x3d, SLUMP & 0xff, SLUMP >> 8); a.short(0x72, 'dn_next_1')          # cmp ax, 130Eh / jb
    a.b(0x3d, SLUMP_END & 0xff, SLUMP_END >> 8); a.short(0x72, 'dn_depth')   # cmp ax, 134Ch / jb dn_depth
    a.label('dn_next_1')
    a.near(0xe9, 'dn_next')
    a.label('dn_depth')
    a.b(0x8b, 0x47, 0x08, 0x2b, 0x44, 0x08)                  # mov ax, [bx+8] / sub ax, [si+8]   depth apart
    a.b(0x83, 0xc0, DAGGER_NEARER, 0x3d, DAGGER_NEARER + DAGGER_BEHIND, 0x00); a.short(0x77, 'dn_next_1')   # add ax, 16 / cmp ax, 24 / ja
    a.b(0x8b, 0x44, 0x0a, 0x3b, 0x47, 0x0a); a.short(0x7c, 'dn_left')   # mov ax, [si+0Ah] / cmp ax, [bx+0Ah] / jl
    a.b(0x8b, 0x47, 0x0a, 0x03, 0x47, 0x0e, 0x3b, 0x44, 0x0a); a.short(0x7e, 'dn_next_1')   # knight's right <= dagger's left
    a.short(0xeb, 'dn_across')
    a.label('dn_left')
    a.b(0x03, 0x44, 0x0e, 0x3b, 0x47, 0x0a); a.short(0x7e, 'dn_next_1')   # add ax, [si+0Eh] / cmp ax, [bx+0Ah] / jle
    a.label('dn_across')
    a.b(0x8b, 0x44, 0x0c, 0x3b, 0x47, 0x0c); a.short(0x7c, 'dn_above')  # mov ax, [si+0Ch] / cmp ax, [bx+0Ch] / jl
    a.b(0x8b, 0x47, 0x0c, 0x03, 0x47, 0x10, 0x3b, 0x44, 0x0c); a.short(0x7e, 'dn_next_1')   # knight's bottom <= dagger's top
    a.short(0xeb, 'dn_hit')
    a.label('dn_above')
    a.b(0x03, 0x44, 0x10, 0x83, 0xc0, DAGGER_REACH, 0x3b, 0x47, 0x0c); a.short(0x7e, 'dn_next_1')   # its bottom + 14 <= top
    a.label('dn_hit')
    a.b(0x8b, 0x4c, 0x0c, 0x2b, 0x4f, 0x0c, 0x83, 0xe9, HEAD_ZONE)   # mov cx, [si+0Ch] / sub cx, [bx+0Ch] / sub cx, 12
    #                                                          ch bit 7: at the head's height
    a.b(0x8a, 0x44, 0x14, 0x32, 0x47, 0x14, 0xa8, 0x02)      # mov al, [si+14h] / xor al, [bx+14h] / test al, 2
    a.short(0x75, 'dn_front')                                # jnz dn_front   against the way it faces
    a.b(0xf6, 0xc5, 0x80, 0xb8, D20['dagger_waist_back'] & 0xff, D20['dagger_waist_back'] >> 8); a.short(0x74, 'dn_set')   # test ch, 80h / mov ax / jz
    a.b(0xb8, D20['dagger_back'] & 0xff, D20['dagger_back'] >> 8); a.short(0xeb, 'dn_set')
    a.label('dn_front')
    a.b(0xf6, 0xc5, 0x80, 0xb8, D20['dagger_waist_front'] & 0xff, D20['dagger_waist_front'] >> 8); a.short(0x74, 'dn_set')
    a.b(0xb8, D20['dagger_front'] & 0xff, D20['dagger_front'] >> 8)
    a.label('dn_set')
    a.b(0x06, 0x1e, 0x07, 0x8b, 0x7f, 0x1c, 0x50, 0xb9, 0x0d, 0x00, 0x33, 0xc0, 0xfc, 0xf3, 0xab, 0x58, 0x07)
    #                                                          push es / push ds / pop es / mov di, [bx+1Ch] / push ax /
    #                                                          mov cx, 13 / xor ax, ax / cld / rep stosw / pop ax / pop es
    a.b(0x89, 0x47, 0x02, 0xc6, 0x47, 0x01, 0x01)            # mov [bx+2], ax / mov byte [bx+1], 1   as 1000:97FA
    a.b(0xc7, 0x46, 0x02, 0xb0, 0x3e)                        # mov word [bp+2], 3EB0h   the dagger ends
    a.b(0x5e, 0x5f, 0x59, 0x5b, 0x58)                        # pop si di cx bx ax
    a.near(0xe9, 'rules_done')
    a.label('dn_next')
    a.b(0x83, 0xc7, SLOT_SIZE)                               # add di, 62h
    a.b(0x81, 0xff, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8); a.short(0x75, 'dn_count')   # cmp di, 6E26h / jne
    a.b(0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)      # mov di, 6F08h   then the monster slots (Black Knights)
    a.label('dn_count')
    a.b(0x49); a.short(0x74, 'dn_none')                      # dec cx / jz dn_none
    a.near(0xe9, 'dn_knight')                                # jmp dn_knight
    a.label('dn_none')
    a.b(0x5e, 0x5f, 0x59, 0x5b, 0x58)                        # pop si di cx bx ax
    a.b(0x83, 0x7c, 0x0c, 0x00)                              # cmp word [si+0Ch], 0   (replaced)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags
    # anim_of: di = an object -> bx = its animation, ZF = 1 (ZF = 0: none)
    a.label('anim_of')
    a.b(0x51, 0xbb, 0x7e, 0x94, 0xb9, 0x0a, 0x00)            # push cx / mov bx, 947Eh / mov cx, 10
    a.label('ao_loop')
    a.b(0x80, 0x3f, 0x00); a.short(0x74, 'ao_next')          # cmp byte [bx], 0 / je   not in use
    a.b(0x39, 0x7f, 0x16); a.short(0x74, 'ao_end')           # cmp [bx+16h], di / je ao_end
    a.label('ao_next')
    a.b(0x83, 0xc3, 0x24); a.short(0xe2, 'ao_loop')          # add bx, 24h / loop
    a.b(0x0b, 0xdb)                                          # or bx, bx   (not 0: ZF = 0)
    a.label('ao_end')
    a.b(0x59, 0xc3)                                          # pop cx / ret

    # strike_on (D20; 1000:4159, cmp word [di+28h],4 / jne 413B: a knight whose blow hit a fallen knight goes on with
    # the blow only for the forward sweep, which takes the head off; after any other it stood up at once): the
    # blows of the new deaths (up, down and forward, back) go on too
    a.label('rules_strike_on')
    a.b(0x50, 0x8b, 0x45, 0x28)                              # push ax / mov ax, [di+28h]
    a.near(0xe8, 'd20_state')                                # call d20_state   ZF = 1: the new deaths
    a.short(0x75, 'so_game')                                 # jne so_game
    for strike in (UP, DOWN_FORWARD, BACK):
        a.b(0x3d, strike, 0x00); a.short(0x74, 'so_end')     # cmp ax, strike / je so_end   (ZF = 1)
    a.label('so_game')
    a.b(0x3d, 0x04, 0x00)                                    # cmp ax, 4   (replaced)
    a.label('so_end')
    a.b(0x58)                                                # pop ax
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # knight_slot: di = a knight's record -> bx = its number * 2
    a.label('knight_slot')
    a.b(0x50, 0x51, 0x8b, 0xc7, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)   # push ax cx / mov ax, di / sub ax, 6C9Eh
    a.b(0xb1, SLOT_SIZE, 0xf6, 0xf1, 0x32, 0xe4, 0xd1, 0xe0, 0x8b, 0xd8)    # mov cl, 62h / div cl / xor ah, ah / shl ax, 1 / mov bx, ax
    a.b(0x59, 0x58, 0xc3)                                    # pop cx ax / ret

    # victim_slot (D20): di = an object -> bx = its number * 2 (knights 0-3, monster slots 4-23; the Black Knights
    # of B and BLACKDEATH are monsters), CF = 1 if neither
    a.label('victim_slot')
    a.b(0x56, 0x8b, 0xf7); a.near(0xe8, 'obj_index'); a.b(0x5e)   # push si / mov si, di / call obj_index / pop si
    a.short(0x72, 'vs_end')                                  # jc vs_end
    a.b(0x83, 0xfb, 48, 0xf5)                                # cmp bx, 48 / cmc   the dragon: CF = 1
    a.label('vs_end')
    a.b(0xc3)
    # de_side: CF = 1 if the blow (si) comes from the side the knight (di, animation bx) faces
    a.label('de_side')
    a.b(0x8b, 0x44, 0x02, 0x2b, 0x45, 0x02)                  # mov ax, [si+2] / sub ax, [di+2]
    a.b(0xf6, 0x47, 0x14, 0x02); a.short(0x74, 'ds_right')   # test byte [bx+14h], 2 / jz   face to the right
    a.b(0xf7, 0xd8)                                          # neg ax
    a.label('ds_right')
    a.b(0x0b, 0xc0); a.short(0x78, 'ds_behind')              # or ax, ax / js ds_behind
    a.b(0xf9, 0xc3)                                          # stc / ret
    a.label('ds_behind')
    a.b(0xf8, 0xc3)                                          # clc / ret

    # --- D19: Black Knights ---
    # black_knight: bx = an object -> ZF = 1 if it is a Black Knight of this practice (a computer knight in a slot)
    a.label('black_knight')
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00)           # cmp byte cs:[bk], 0
    a.short(0x74, 'bkq_no')                                  # je bkq_no
    a.b(0x81, 0xfb, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)   # cmp bx, 6F08h
    a.short(0x72, 'bkq_no')                                  # jb bkq_no
    end_slots = MONSTER_SLOTS + MONSTER_COUNT * SLOT_SIZE
    a.b(0x81, 0xfb, end_slots & 0xff, end_slots >> 8)        # cmp bx, 76B0h
    a.short(0x73, 'bkq_no')                                  # jae bkq_no
    a.b(0x80, 0x7f, 0x35, COMPUTER_TYPE, 0xc3)               # cmp byte [bx+35h], 8 / ret
    a.label('bkq_no')
    a.b(0x50, 0x33, 0xc0, 0x40, 0x58, 0xc3)                  # push ax / xor ax, ax / inc ax / pop ax / ret   ZF = 0

    # bk_collide (1000:A008, cmp word [di+22h],0 in the walk's collision test 9FDF: si moves, di is another fighter
    # in an animation slot, ZF = 1 = it does not block): in a Black Knight practice two Black Knights never block
    # each other. With 3-4 knights two came in at the same place (one each side, as many as the knights), and two
    # bodies that overlap block each other in every direction: they stood there for good
    a.label('rules_bk_collide')
    a.b(0x83, 0x7d, 0x22, 0x00); a.short(0x74, 'bcl_flags')  # cmp word [di+22h], 0 / je   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00); a.short(0x74, 'bcl_nz')   # not a Black Knight practice
    a.b(0x8b, 0xde); a.near(0xe8, 'black_knight'); a.short(0x75, 'bcl_nz')   # mov bx, si / call black_knight / jnz
    a.b(0x8b, 0xdf); a.near(0xe8, 'black_knight'); a.short(0x74, 'bcl_flags')  # mov bx, di / call / jz   both: ZF = 1
    a.label('bcl_nz')
    a.b(0x83, 0x7d, 0x22, 0x00)                              # cmp word [di+22h], 0   ZF = 0
    a.label('bcl_flags')
    a.near(0xe9, 'rules_flags')

    # map_keys (D26; 1000:A536, mov [CC9Ah],bx: the map loop's input, bx = 83C0's bits for a human, the AI's for a
    # computer knight): after a human's turn start (map_hold, set by the int 65h) the input stays empty while a
    # direction or fire is still held from the turn before, so the next knight moves only on a new press
    a.label('rules_map_keys')
    a.b(0x8b, 0x5e, 0xfe)                                    # mov bx, [bp-2]   the game's bx
    a.b(0x2e, 0x80, 0x3e); a.word('map_hold'); a.b(0x00); a.short(0x74, 'mk2_set')   # cmp byte cs:[map_hold], 0 / je
    a.b(0x56, 0x8b, 0x36, 0xe8, 0x77, 0x83, 0x7c, 0x20, COMPUTER, 0x5e)   # push si / mov si, [77E8h] / cmp word [si+20h], 4 / pop si
    a.short(0x74, 'mk2_set')                                 # je mk2_set   a computer's turn: its own moves
    a.b(0xf6, 0xc3, 0x1f); a.short(0x74, 'mk2_free')         # test bl, 1Fh / jz mk2_free
    a.b(0x33, 0xdb, 0x89, 0x5e, 0xfe); a.short(0xeb, 'mk2_set')   # xor bx, bx / mov [bp-2], bx   still held: nothing
    a.label('mk2_free')
    a.b(0x2e, 0xc6, 0x06); a.word('map_hold'); a.b(0x00)     # all let go: the keys count again
    a.label('mk2_set')
    a.b(0x89, 0x1e, 0x9a, 0xcc)                              # mov [CC9Ah], bx   (replaced)
    a.near(0xe9, 'rules_done')

    # --- K33: limits and checks ---
    # game_over (1000:A67B, inc word [0CCAAh], a dead human's turn): the game counted dead humans up to the number of
    # players, and every normal turn's end cleared the count: a frog's skipped turn did not (one dead, one frog: a
    # false Game Over on the second day), a computer's did (two dead with a computer between them: no end at all).
    # Now the game ends when no human knight can play again: none has lives, and none comes back (rules' modes)
    a.label('rules_game_over')
    a.b(0x56, 0x51, 0xbe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8, 0xb9, 0x04, 0x00)   # push si cx / mov si, 6C9Eh / mov cx, 4
    a.label('go_loop')
    a.b(0x83, 0x7c, 0x20, COMPUTER); a.short(0x74, 'go_next')   # cmp word [si+20h], 4 / je
    a.b(0x80, 0x7c, 0x31, 0x00); a.short(0x7f, 'go_alive')   # cmp byte [si+31h], 0 / jg
    a.near(0xe8, 'section'); a.short(0x72, 'go_next')        # call section / jc
    a.b(0x2e, 0x80, 0x7f, 0x07, MODES['permadeath']); a.short(0x75, 'go_alive')   # cmp byte cs:[bx+7], permadeath / jne
    a.label('go_next')
    a.b(0x83, 0xc6, SLOT_SIZE); a.short(0xe2, 'go_loop')     # add si, 62h / loop
    a.b(0x59, 0x5e, 0xc7, 0x46, 0x02, 0x88, 0xa6)            # pop cx si / mov word [bp+2], 0A688h   Game Over
    a.near(0xe9, 'rules_done')
    a.label('go_alive')
    a.b(0x59, 0x5e, 0xc7, 0x46, 0x02, 0x0d, 0xa6)            # pop cx si / mov word [bp+2], 0A60Dh   the next knight
    a.near(0xe9, 'rules_done')
    # loot_hp (1000:CE75, sub [di+38h],ax: a knight's armour is taken): never below 1 (a frog is looted with its wounds)
    a.label('rules_loot_hp')
    a.b(0x29, 0x45, 0x38); a.short(0x7f, 'lh_end')           # sub [di+38h], ax / jg
    a.b(0xc7, 0x45, 0x38, 0x01, 0x00)                        # mov word [di+38h], 1
    a.label('lh_end')
    a.near(0xe9, 'rules_done')
    # auto_loot_hp (1000:0BAD, a computer or the dragon takes armour; ax = the bonus of the winner's OLD armour; the
    # winner already wears the new one, the loser's +42h is still the armour taken): the loser loses that armour's
    # bonus, not above 1 HP left, and the winner gains the difference
    a.label('rules_auto_loot_hp')
    a.b(0x51, 0x8b, 0xc8, 0x8b, 0x5d, 0x42)                  # push cx / mov cx, ax / mov bx, [di+42h]
    a.b(0x8a, 0x87, (0xf452 - 0x1b) & 0xff, (0xf452 - 0x1b) >> 8, 0x98)   # mov al, [bx+0F452h-1Bh] / cbw
    a.b(0x29, 0x45, 0x38); a.short(0x7f, 'al_ok')            # sub [di+38h], ax / jg
    a.b(0xc7, 0x45, 0x38, 0x01, 0x00)                        # mov word [di+38h], 1
    a.label('al_ok')
    a.b(0x2b, 0xc1, 0x01, 0x44, 0x38, 0x59)                  # sub ax, cx / add [si+38h], ax / pop cx
    a.near(0xe9, 'rules_done')
    # path_none (1000:2CFB, mov ax,-1: a flying object, ax, has no path slot): the callers store bx, cx, dx as its
    # place, which were anything: they get the place it is at, so it lands there
    a.label('rules_path_none')
    a.b(0x8b, 0xf0, 0x8b, 0x44, 0x02, 0x89, 0x46, 0xfe)      # mov si, ax / mov ax, [si+2] / mov [bp-2], ax   its bx
    a.b(0x8b, 0x4c, 0x06, 0x8b, 0x54, 0x04, 0xb8, 0xff, 0xff)   # mov cx, [si+6] / mov dx, [si+4] / mov ax, -1
    a.near(0xe9, 'rules_done')
    # mythral_table (1000:BC2E, mov cx,[si+2]: the modifier for a donation; above the table's last limit si is past
    # it, which max_gold above 250 makes possible): the last entry
    a.label('rules_mythral_table')
    a.b(0x81, 0xfe, 0x90, 0xe4); a.short(0x72, 'mt_ok')      # cmp si, 0E490h / jb
    a.b(0xbe, 0x8c, 0xe4)                                    # mov si, 0E48Ch
    a.label('mt_ok')
    a.b(0x8b, 0x4c, 0x02); a.near(0xe9, 'rules_done')        # mov cx, [si+2]

    # game_roll: ax = the game's 0-100 roll, as 1000:BF82 (7 random bits, 100-127 minus 27); keeps bx, cx
    a.label('game_roll')
    a.near(0xe8, 'game_random')
    a.b(0x25, 0x7f, 0x00, 0x3d, 0x64, 0x00); a.short(0x72, 'gro_end')   # and ax, 7Fh / cmp ax, 100 / jb
    a.b(0x2d, 0x1b, 0x00)                                    # sub ax, 27
    a.label('gro_end')
    a.b(0xc3)

    # healer (1000:BCAC, the donation [0E243h] is made; custom rules): first the full heal's price if the knight is
    # hurt or diseased, then the life point's price per life up to max_lives. What cannot buy a whole one is a chance:
    # 4 of 10 gives the heal 40 % of the time, the 2 left of 27 a life 2/15 of the time. Money nothing can use is
    # returned. The prices are the game's own immediates (custom rules patch them)
    a.label('rules_healer')
    a.b(0x52, 0x57, 0x06, 0x8e, 0x46, 0x04)                  # push dx di es / mov es, [bp+4]   MAIN's code
    a.b(0x8b, 0x36, 0xe8, 0x77, 0x8b, 0x1e, 0x43, 0xe2)      # mov si, [77E8h] / mov bx, [0E243h]
    a.b(0x2e, 0x89, 0x1e); a.word('heal_given')              # mov cs:[heal_given], bx
    a.b(0x33, 0xff)                                          # xor di, di   1 cured, 2 something bought
    a.b(0x8b, 0x44, 0x38, 0x3b, 0x44, 0x3c); a.short(0x75, 'hl_hp')   # mov ax, [si+38h] / cmp ax, [si+3Ch] / jne
    a.b(0x83, 0x7c, 0x60, 0x00); a.short(0x74, 'hl_lives')   # cmp word [si+60h], 0 / je
    a.label('hl_hp')
    a.b(0x26, 0x8a, 0x0e, 0xdb, 0xbc, 0x32, 0xed)            # mov cl, es:[0BCDBh] / xor ch, ch   the heal's price
    a.b(0x3b, 0xd9); a.short(0x7c, 'hl_hp_try')              # cmp bx, cx / jl
    a.b(0x2b, 0xd9); a.short(0xeb, 'hl_heal')                # sub bx, cx / jmp
    a.label('hl_hp_try')
    a.near(0xe8, 'heal_roll'); a.b(0xbb, 0x00, 0x00); a.short(0x73, 'hl_end')   # call heal_roll / mov bx, 0 / jnc
    a.label('hl_heal')
    a.b(0x8b, 0x44, 0x3c, 0x89, 0x44, 0x38)                  # mov ax, [si+3Ch] / mov [si+38h], ax
    a.b(0x83, 0xcf, 0x02, 0x83, 0x7c, 0x60, 0x00); a.short(0x74, 'hl_lives')   # or di, 2 / cmp word [si+60h], 0 / je
    a.b(0xc7, 0x44, 0x60, 0x00, 0x00, 0x83, 0xcf, 0x01)      # mov word [si+60h], 0 / or di, 1
    a.label('hl_lives')
    a.b(0x26, 0x8a, 0x0e, 0xee, 0xbc, 0x32, 0xed)            # mov cl, es:[0BCEEh] / xor ch, ch   a life's price
    a.label('hl_life')
    a.b(0x8a, 0x44, 0x31, 0x2e, 0x3a, 0x06); a.word('rules_table', G_MAX_LIVES); a.short(0x7d, 'hl_change')   # cap: jge
    a.b(0x3b, 0xd9); a.short(0x7c, 'hl_life_try')            # cmp bx, cx / jl
    a.b(0x2b, 0xd9, 0xfe, 0x44, 0x31, 0x83, 0xcf, 0x02); a.short(0xeb, 'hl_life')   # sub bx, cx / inc lives / or di, 2
    a.label('hl_life_try')
    a.b(0x0b, 0xdb); a.short(0x74, 'hl_end')                 # or bx, bx / jz
    a.near(0xe8, 'heal_roll'); a.b(0xbb, 0x00, 0x00); a.short(0x73, 'hl_end')   # call heal_roll / mov bx, 0 / jnc
    a.b(0xfe, 0x44, 0x31, 0x83, 0xcf, 0x02); a.short(0xeb, 'hl_end')   # inc lives / or di, 2
    a.label('hl_change')
    a.b(0x01, 0x5c, 0x32, 0x01, 0x1e, 0x45, 0xe2, 0x33, 0xdb)   # add [si+32h], bx / add [0E245h], bx / xor bx, bx
    a.label('hl_end')
    a.b(0x89, 0x1e, 0x43, 0xe2)                              # mov [0E243h], bx
    # the game's reply (BCF4): bx > 9 thanks, else sorry; cx bit 0: also cured
    a.b(0xb8, 0x0a, 0x00, 0xf7, 0xc7, 0x02, 0x00); a.short(0x75, 'hl_say')   # mov ax, 10 / test di, 2 / jnz
    a.b(0x2e, 0x83, 0x3e); a.word('heal_given'); a.b(0x0a); a.short(0x7d, 'hl_say')   # cmp cs:[heal_given], 10 / jge
    a.b(0xb8, 0x09, 0x00)                                    # mov ax, 9
    a.label('hl_say')
    a.b(0x89, 0x46, 0xfe, 0x8b, 0xcf, 0x83, 0xe1, 0x01)      # mov [bp-2], ax / mov cx, di / and cx, 1
    a.b(0x07, 0x5f, 0x5a, 0xc7, 0x46, 0x02, 0xf4, 0xbc)      # pop es di dx / mov word [bp+2], 0BCF4h
    a.near(0xe9, 'rules_done')
    a.label('heal_roll')                                     # bx of cx (bx < cx): CF = 1 with that chance
    a.near(0xe8, 'game_random')
    a.b(0x25, 0xff, 0x7f, 0x33, 0xd2, 0xf7, 0xf1, 0x3b, 0xd3, 0xc3)   # and ax, 7FFFh / xor dx, dx / div cx / cmp dx, bx / ret

    # curse_roll: the same deterministic curse stream and checkpoint as Hawk and Protection; keeps bx, cx, dx.
    a.label('curse_roll')
    a.b(0x53, 0x51, 0x52, 0xbb, 0x06, 0x00)                  # push bx cx dx / mov bx, 3 * 2
    a.near(0xe8, 'fate_prepare')
    a.b(0x5a, 0x59, 0x5b)                                    # pop dx cx bx
    a.near(0xe9, 'game_roll')

    # haste_curse (1000:CCCF, mov word [0CCA2h],-1): cursed, [0CCA2h] = 1: the turn's budget is halved (turn_haste)
    a.label('rules_haste_curse')
    a.near(0xe8, 'spell_safe'); a.short(0x75, 'hc_roll')     # D37: Spellproof: never cursed
    a.b(0xc7, 0x06, 0xa2, 0xcc, 0xff, 0xff); a.near(0xe9, 'rules_done')
    a.label('hc_roll')
    a.near(0xe8, 'curse_roll')
    a.b(0x2e, 0x3a, 0x06); a.word('rules_table', G_HASTE_CURSE)   # cmp al, cs:[limit]
    a.b(0xc7, 0x06, 0xa2, 0xcc, 0x01, 0x00)                  # mov word [0CCA2h], 1   (keeps the flags)
    a.short(0x7e, 'hc_end')                                  # jle hc_end
    a.b(0xc7, 0x06, 0xa2, 0xcc, 0xff, 0xff)                  # mov word [0CCA2h], -1
    a.label('hc_end')
    a.near(0xe9, 'rules_done')

    # wyrm_curse (1000:C03C, mov word [0F37Ah],0, the dragon's target just set to the knight chosen): cursed, the
    # dragon goes for the reader ([77E8h])
    a.label('rules_wyrm_curse')
    a.b(0xc7, 0x06, 0x7a, 0xf3, 0x00, 0x00)                  # (replaced)
    a.near(0xe8, 'spell_safe'); a.short(0x74, 'wc_end')      # D37: Spellproof: never cursed
    a.near(0xe8, 'curse_roll')
    a.b(0x2e, 0x3a, 0x06); a.word('rules_table', G_WYRM_CURSE); a.short(0x7f, 'wc_end')   # cmp al, cs:[limit] / jg
    a.b(0xa1, 0xe8, 0x77, 0xa3, (DRAGON_RECORD + 0x46) & 0xff, (DRAGON_RECORD + 0x46) >> 8)   # mov ax, [77E8h] / mov [dragon+46h], ax
    a.label('wc_end')
    a.near(0xe9, 'rules_done')

    # dragon_scroll (1000:0D15, call 2444: the dragon's fight begins, a human's knight): the duels' offer of the Scroll
    # of Protection (04E8, with the knight as the one attacked), then 04E8 returns to this site. Avoided: the dragon
    # flies off and the turn ends (113E); else the fight
    a.label('rules_dragon_scroll')
    a.b(0x2e, 0x80, 0x3e); a.word('ds_have'); a.b(0x00); a.short(0x75, 'ds_back')
    a.b(0x2e, 0xc6, 0x06); a.word('ds_have'); a.b(0x01)
    a.b(0xa1, 0x79, 0x89, 0x2e, 0xa3); a.word('ds_old', 0)   # mov ax, [8979h] / mov cs:[ds_old], ax
    a.b(0xa1, 0x7b, 0x89, 0x2e, 0xa3); a.word('ds_old', 2)   # mov ax, [897Bh] / mov cs:[ds_old+2], ax
    a.b(0xa1, 0x78, 0x09, 0xa3, 0x7b, 0x89)                  # mov ax, [0978h] / mov [897Bh], ax
    a.b(0xc7, 0x06, 0x79, 0x89, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8)   # mov word [8979h], dragon
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0xe8, 0x04)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x15, 0x0d)
    a.near(0xe9, 'call_game')
    a.label('ds_back')
    a.b(0x2e, 0xc6, 0x06); a.word('ds_have'); a.b(0x00)
    a.b(0x8b, 0xd8)                                          # mov bx, ax   its answer
    a.b(0x2e, 0xa1); a.word('ds_old', 0); a.b(0xa3, 0x79, 0x89)   # [8979h] back
    a.b(0x2e, 0xa1); a.word('ds_old', 2); a.b(0xa3, 0x7b, 0x89)   # [897Bh] back
    a.b(0x0b, 0xdb); a.short(0x74, 'ds_fight')               # or bx, bx / jz
    a.b(0xc7, 0x06, 0xb0, 0xcc, 0x00, 0x00)                  # mov word [0CCB0h], 0   the dragon flies off
    a.b(0xc7, 0x46, 0x02, 0x3e, 0x11); a.near(0xe9, 'rules_done')   # mov word [bp+2], 113Eh   the turn ends
    a.label('ds_fight')
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x44, 0x24)
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x18, 0x0d)
    a.near(0xe9, 'call_game')

    # in_valley: si = a knight -> CF = 1 if it touches the Valley's icon (x and y measured with 1000:0653)
    a.label('in_valley')
    a.b(0x81, 0x7c, 0x5c, VALLEY_X[0], 0x00); a.short(0x7c, 'iv_no')   # cmp word [si+5Ch], x0 / jl
    a.b(0x81, 0x7c, 0x5c, VALLEY_X[1], 0x00); a.short(0x7f, 'iv_no')
    a.b(0x83, 0x7c, 0x5e, VALLEY_Y[0]); a.short(0x7c, 'iv_no')
    a.b(0x83, 0x7c, 0x5e, VALLEY_Y[1]); a.short(0x7f, 'iv_no')
    a.b(0xf9, 0xc3)                                          # stc / ret
    a.label('iv_no')
    a.b(0xf8, 0xc3)                                          # clc / ret
    # hawk_land (1000:AB7D, add word [si+5Ch],20h, the last step of a cursed Hawk's random place): not in the Valley
    a.label('rules_hawk_land')
    a.b(0x83, 0x44, 0x5c, 0x20)                              # (replaced)
    a.near(0xe8, 'in_valley'); a.short(0x73, 'hk_end')
    a.b(0xc7, 0x44, 0x5e, VALLEY_Y[0] - 1, 0x00)             # mov word [si+5Eh], y0 - 1   just north of it
    a.label('hk_end')
    a.near(0xe9, 'rules_done')
    # hawk_guard (from turn_moves, every pass of the map loop): the Hawk's flight ([0CC9Eh]) cannot enter the Valley:
    # the knight goes back to its last place outside. Speedrun mode: as the game
    a.label('hawk_guard')
    a.b(0x83, 0x3e, 0x9e, 0xcc, 0x00); a.short(0x75, 'hg_on')
    a.b(0x2e, 0xc6, 0x06); a.word('hawk_ok'); a.b(0x00, 0xc3)
    a.label('hg_on')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_EXPLOIT_FIXES); a.b(0x00); a.short(0x75, 'hg_go'); a.b(0xc3)
    a.label('hg_go')
    a.b(0x50, 0x56, 0x8b, 0x36, 0xe8, 0x77)                  # push ax si / mov si, [77E8h]
    a.near(0xe8, 'in_valley'); a.short(0x72, 'hg_in')
    a.b(0x8b, 0x44, 0x5c, 0x2e, 0xa3); a.word('hawk_pos', 0)   # mov ax, [si+5Ch] / mov cs:[hawk_pos], ax
    a.b(0x8b, 0x44, 0x5e, 0x2e, 0xa3); a.word('hawk_pos', 2)
    a.b(0x2e, 0xc6, 0x06); a.word('hawk_ok'); a.b(0x01); a.short(0xeb, 'hg_end')
    a.label('hg_in')
    a.b(0x2e, 0x80, 0x3e); a.word('hawk_ok'); a.b(0x00); a.short(0x74, 'hg_end')
    a.b(0x2e, 0xa1); a.word('hawk_pos', 0); a.b(0x89, 0x44, 0x5c)
    a.b(0x2e, 0xa1); a.word('hawk_pos', 2); a.b(0x89, 0x44, 0x5e)
    a.label('hg_end')
    a.b(0x5e, 0x58, 0xc3)                                    # pop si ax / ret

    # knight_flash (D61, from practice_frame: once a fight frame, as the game's COLCON): the knights in the new entries
    # (D13, D15, D33) pulse at 1-10 HP as the game's glow does entries 6-11 (1000:08F8, 4A05, 4B28): each word of a
    # group steps one unit a channel every GLOW_SPEEDS frames towards its slot's glow target (KnightGlowColours'
    # words, 1000:09A5, which custom colours set) and back. glow_cur holds a pulsing group's words for new_entries
    # (FFFFh: the colour as it is). A group whose targets are its words (black, purple, grey) does not pulse
    a.label('knight_flash')
    a.near(0xe8, 'colours_active'); a.short(0x75, 'kf_on'); a.b(0xc3)
    a.label('kf_on')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x06)            # push ax bx cx dx si di es
    a.b(0x8e, 0x46, 0x04, 0x33, 0xd2)                        # mov es, [bp+4] (MAIN's code: the words) / xor dx, dx
    a.b(0x80, 0x3e, GAME_ENDING & 0xff, GAME_ENDING >> 8, 0x00); a.short(0x75, 'kf_go')   # cmp byte [897Dh], 0 / jne
    a.near(0xe9, 'kf_groups')                                # the fight ends: every group stops
    a.label('kf_go')
    for rec in KNIGHTS:                                      # dl: the groups of the knights at 1-10 HP
        practice_group = {0x6d62: SLOT_GROUP[1], 0x6dc4: SLOT_GROUP[3]}.get(rec)   # RECOLOUR: 32-34, 35-37
        coop_group = {0x6d00: SLOT_GROUP[2], 0x6d62: SLOT_GROUP[1], 0x6dc4: SLOT_GROUP[3]}.get(rec)   # COOP_RECOLOUR
        a.b(0xa1, (rec + 0x38) & 0xff, (rec + 0x38) >> 8, 0x3d, 0x00, 0x00); a.short(0x7e, f'kf_n{rec:x}')   # HP <= 0
        a.b(0x3d, 0x0a, 0x00); a.short(0x7f, f'kf_n{rec:x}')   # cmp ax, 10 / jg
        a.b(0x2e, 0x83, 0x3e); a.word('coop_partner'); a.b(0x00); a.short(0x74, f'kf_c{rec:x}')
        a.b(0x8b, 0x1e, (rec + 0x20) & 0xff, (rec + 0x20) >> 8, 0x83, 0xfb, 0x04); a.short(0x77, f'kf_n{rec:x}')   # mov bx, [+20h] / cmp bx, 4 / ja
        a.b(0x2e, 0x8a, 0x8f); a.word('slot_group'); a.short(0xeb, f'kf_b{rec:x}')   # D33 co-op lair: by its slot
        a.label(f'kf_c{rec:x}')
        if coop_group is None:
            a.short(0xeb, f'kf_n{rec:x}')                    # knight 1: the game's glow (entries 6-8)
        else:
            a.b(0xb1, coop_group)                            # mov cl, group
            if practice_group is None:
                a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00); a.short(0x74, f'kf_n{rec:x}')   # co-op only
            elif practice_group != coop_group:
                a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00); a.short(0x75, f'kf_b{rec:x}')
                a.b(0xb1, practice_group)
        a.label(f'kf_b{rec:x}')
        a.b(0xb0, 0x01, 0xd2, 0xe0, 0x0a, 0xd0)              # mov al, 1 / shl al, cl / or dl, al
        a.label(f'kf_n{rec:x}')
    a.b(0x80, 0xe2, 0xff ^ (1 << NO_GLOW_GROUP))             # and dl, not the Black Knights' group
    a.label('kf_groups')
    for g in range(len(GLOW_GROUP_SLOTS)):                   # dh = 1: a word changed
        if g != NO_GLOW_GROUP:
            a.b(0xbe, 6 * g, 0x00, 0xb0, 1 << g)             # mov si, 6 x group / mov al, its bit
            a.near(0xe8, 'glow_group')
    a.b(0x0a, 0xf6); a.short(0x74, 'kf_pop')                 # or dh, dh / jz kf_pop
    a.b(0xba, 0xc8, 0x03, 0xb0, NEW_ENTRIES, 0xee)           # mov dx, 3C8h / mov al, 32 / out dx, al
    a.b(0x2e, 0xc6, 0x06); a.word('level'); a.b(0x10)        # mov byte cs:[level], 16
    a.near(0xe8, 'dac_new')                                  # the new colours with the pulse
    a.label('kf_pop')
    a.b(0x07, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)      # pop es di si dx cx bx ax / ret

    # glow_group: si = the group's word offset (6 x group), al = its bit in dl (1: a knight of it at 1-10 HP). Starts,
    # steps or stops it; dh = 1 when a word changed. es = MAIN's code segment
    def cs_si(op, label, n, *rest):                          # op cs:[si + label + 2n]
        a.b(0x2e, *op); a.word(label, 2 * n)
        if rest:
            a.b(*rest)
    a.label('glow_group')
    a.b(0x84, 0xc2); a.short(0x75, 'gg_on')                  # test dl, al / jnz gg_on
    cs_si((0x83, 0xbc), 'glow_cur', 0, 0xff); a.short(0x74, 'gg_ret')   # cmp word cs:[si+glow_cur], -1 / je
    for n in range(3):
        cs_si((0xc7, 0x84), 'glow_cur', n, 0xff, 0xff)       # mov word cs:[si+glow_cur+2n], FFFFh   its colour back
    a.b(0xb6, 0x01)                                          # mov dh, 1
    a.label('gg_ret')
    a.b(0xc3)
    a.label('gg_on')
    cs_si((0x83, 0xbc), 'glow_cur', 0, 0xff); a.short(0x74, 'gg_new'); a.near(0xe9, 'gg_step')   # cmp word cs:[si+glow_cur], -1 / jne
    a.label('gg_new')
    for n in range(3):                                       # start: the words as they are, the targets
        cs_si((0x8b, 0x9c), 'colour_sites', n); a.b(0x26, 0x8b, 0x07)   # mov bx, cs:[si+colour_sites+2n] / mov ax, es:[bx]
        cs_si((0x89, 0x84), 'glow_base', n)                  # mov cs:[si+glow_base+2n], ax
        cs_si((0x8b, 0x9c), 'glow_sites', n); a.b(0x26, 0x8b, 0x07)   # mov bx, cs:[si+glow_sites+2n] / mov ax, es:[bx]
        cs_si((0x89, 0x84), 'glow_tgt', n)                   # mov cs:[si+glow_tgt+2n], ax
        cs_si((0xc7, 0x84), 'glow_cnt', n, GLOW_SPEEDS[n], 0x00)   # mov word cs:[si+glow_cnt+2n], speed
    for n in range(3):
        cs_si((0x8b, 0x84), 'glow_base', n); cs_si((0x3b, 0x84), 'glow_tgt', n)   # mov ax, base / cmp ax, target
        a.short(0x75, 'gg_start')                            # jne gg_start
    a.b(0xc3)                                                # targets = words: no pulse
    a.label('gg_start')
    for n in range(3):
        cs_si((0x8b, 0x84), 'glow_base', n); cs_si((0x89, 0x84), 'glow_cur', n)   # mov ax, base / mov cur, ax
    a.b(0xc3)
    a.label('gg_step')
    for n in range(3):
        cs_si((0xff, 0x8c), 'glow_cnt', n); a.short(0x75, f'gg_s{n}')   # dec word cs:[si+glow_cnt+2n] / jnz
        cs_si((0xc7, 0x84), 'glow_cnt', n, GLOW_SPEEDS[n], 0x00)
        cs_si((0x8b, 0x84), 'glow_cur', n); cs_si((0x8b, 0x8c), 'glow_tgt', n)   # mov ax, cur / mov cx, target
        a.near(0xe8, 'glow_dyn')                             # call glow_dyn   (the game's DYNAMIC, 1000:4B28)
        cs_si((0x89, 0x84), 'glow_cur', n); a.b(0xb6, 0x01)  # mov cur, ax / mov dh, 1
        a.b(0x3b, 0xc1); a.short(0x75, f'gg_s{n}')           # cmp ax, cx / jne   arrived: target and base swap
        cs_si((0x8b, 0x84), 'glow_base', n); cs_si((0x89, 0x84), 'glow_tgt', n)   # mov ax, base / mov target, ax
        cs_si((0x89, 0x8c), 'glow_base', n)                  # mov cs:[si+glow_base+2n], cx
        a.label(f'gg_s{n}')
    a.b(0xc3)
    a.label('glow_dyn')                                      # ax one unit a channel towards cx; bx, di clobbered
    for mask, unit in ((0x00f, 0x001), (0x0f0, 0x010), (0xf00, 0x100)):
        a.b(0x8b, 0xd8, 0x81, 0xe3, mask & 0xff, mask >> 8)  # mov bx, ax / and bx, mask
        a.b(0x8b, 0xf9, 0x81, 0xe7, mask & 0xff, mask >> 8)  # mov di, cx / and di, mask
        a.b(0x3b, 0xdf); a.short(0x74, f'gd_{unit:x}')       # cmp bx, di / je
        a.short(0x72, f'gd_up{unit:x}')                      # jb up
        a.b(0x2d, unit & 0xff, unit >> 8); a.short(0xeb, f'gd_{unit:x}')   # sub ax, unit
        a.label(f'gd_up{unit:x}')
        a.b(0x05, unit & 0xff, unit >> 8)                    # add ax, unit
        a.label(f'gd_{unit:x}')
    a.b(0xc3)

    # glow_k1 / glow_k2 (D61; 1000:08F8, 0955 in KnightGlowOn, replace cmp word [0412h] / [0418h], 0): the game's
    # glow of knight 1 (entries 6-8) and 2 (9-11) only at 1-10 HP and not for the computer's slot 4. One that heals
    # above 10 HP (or dies) stops: its slots' target and original become the words it had before the glow, with one
    # more arrival, so COLCON (4A3F) steps them back and frees the slots itself; the game may start it again
    for kind, rec_ptr, var, entry, go, skip in (('glow_k1', 0x8979, 0x0412, 6, 0x08ff, 0x0947),
                                                ('glow_k2', 0x897b, 0x0418, 9, 0x095c, 0x09a4)):
        a.label('rules_' + kind)
        a.b(0x50, 0x56, 0x57)                                # push ax si di
        a.b(0x8b, 0x3e, rec_ptr & 0xff, rec_ptr >> 8, 0x8b, 0x45, 0x38)   # mov di, [rec] / mov ax, [di+38h]
        a.b(0x3d, 0x00, 0x00); a.short(0x7e, kind + '_off')  # cmp ax, 0 / jle
        a.b(0x3d, 0x0a, 0x00); a.short(0x7f, kind + '_off')  # cmp ax, 10 / jg
        a.b(0x83, 0x7d, 0x20, 0x04); a.short(0x73, kind + '_off')   # cmp word [di+20h], 4 / jae
        a.b(0x83, 0x3e, var & 0xff, var >> 8, 0x00); a.short(0x74, kind + '_new'); a.near(0xe9, kind + '_skip')   # glowing already
        a.label(kind + '_new')
        a.b(0x8b, 0x36, 0xc6, 0x7a)                          # mov si, [7AC6h]   the palette: the words before it
        for n in range(3):
            a.b(0x8b, 0x44, 2 * (entry + n)); a.b(0x2e, 0xa3); a.word('glow_old', 2 * (3 * (entry // 9) + n))
        a.b(0xc7, 0x46, 0x02, go & 0xff, go >> 8)            # mov word [bp+2], go   the game starts it
        a.short(0xeb, kind + '_pop')
        a.label(kind + '_off')
        a.b(0x83, 0x3e, var & 0xff, var >> 8, 0x00); a.short(0x75, kind + '_stop'); a.near(0xe9, kind + '_skip')   # not glowing
        a.label(kind + '_stop')
        for n in range(3):
            a.b(0x8b, 0x36, (var + 2 * n) & 0xff, (var + 2 * n) >> 8)   # mov si, [var+2n]   its slot
            a.b(0x81, 0xfe, 0x02, 0x7b); a.short(0x72, f'{kind}_n{n}')   # cmp si, 7B02h / jb
            a.b(0x81, 0xfe, 0x3e, 0x7b); a.short(0x77, f'{kind}_n{n}')   # cmp si, 7B3Eh / ja
            a.b(0x2e, 0xa1); a.word('glow_old', 2 * (3 * (entry // 9) + n))   # mov ax, cs:[glow_old+n]
            a.b(0x89, 0x44, 0x02, 0x89, 0x44, 0x08)          # mov [si+2], ax / mov [si+8], ax
            a.b(0xc7, 0x44, 0x0a, 0x01, 0x00)                # mov word [si+0Ah], 1   freed at its next arrival
            a.label(f'{kind}_n{n}')
        a.b(0xc7, 0x06, var & 0xff, var >> 8, 0x00, 0x00)    # mov word [var], 0
        a.label(kind + '_skip')
        a.b(0xc7, 0x46, 0x02, skip & 0xff, skip >> 8)        # mov word [bp+2], skip
        a.label(kind + '_pop')
        a.b(0x5f, 0x5e, 0x58)                                # pop di si ax
        a.near(0xe9, 'rules_done')

    # --- MINEFIELD (a fight code) ---
    # Ten mines at random places on the ground: the knights' small black shadow frame, drawn into the fight's background
    # ([80B9h] = 0AC00h, copied to the screen every frame), so it stays under everyone and takes no object slot. Spent
    # mines stay drawn. mine_frame (every fight frame): an object on the ground on a mine sets it off, a knight only with
    # its feet on the mark (MINE_FOOT_*). A knight, a human's or a computer's (the Black Knights too),
    # is crushed as by the troll (16E2h), or gets the plain death where the game's rules forbid that; other enemies
    # take a deadly blow from a dummy knight (MINE_HITTER) through their own hit reactions. Not the dragon or Guardian
    a.label('mine_frame')
    a.b(0x2e, 0x80, 0x3e); a.word('mine_vis'); a.b(0x00); a.short(0x74, 'mnf_shown')   # D50: shown long enough?
    a.b(0x50, 0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f)   # push ax / push ds / ds = 0 / mov ax, [046Ch] / pop ds
    a.b(0x2e, 0x2b, 0x06); a.word('mine_t'); a.b(0x3d, MINE_SHOW, 0x00, 0x58); a.short(0x72, 'mnf_shown')   # sub ax, cs:[mine_t] / cmp ax, 91 / pop ax / jb
    a.b(0x2e, 0xc6, 0x06); a.word('mine_vis'); a.b(0x00)
    a.b(0x53, 0x2e, 0xc6, 0x06); a.word('mine_mode'); a.b(0x01, 0x33, 0xdb)   # push bx / mode 1 / xor bx, bx
    a.label('mnf_hide')
    a.near(0xe8, 'mine_rect'); a.b(0x43, 0x43, 0x83, 0xfb, 2 * MINE_COUNT); a.short(0x72, 'mnf_hide')   # inc bx (x2) / cmp bx, 20 / jb
    a.b(0x5b)                                                # pop bx
    a.label('mnf_shown')
    a.b(0x2e, 0x80, 0x3e); a.word('mine_req'); a.b(0x00); a.short(0x74, 'mnf_on')
    a.b(0x2e, 0xc6, 0x06); a.word('mine_req'); a.b(0x00)
    a.near(0xe8, 'mine_place')
    a.label('mnf_on')
    a.b(0x2e, 0x83, 0x3e); a.word('mine_live'); a.b(0x00); a.short(0x75, 'mnf_go'); a.b(0xc3)
    a.label('mnf_go')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57)                  # push ax bx cx dx si di
    a.b(0xbb, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # mov bx, 947Eh / mov cx, 10
    a.label('mnf_slot')
    a.b(0x80, 0x3f, 0x00); a.short(0x74, 'mnf_next_s')       # cmp byte [bx], 0 / je
    a.b(0x8b, 0x77, 0x16, 0x81, 0xfe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'mnf_next_s')   # mov si, [bx+16h] / cmp si, 6C9Eh / jb
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'mnf_next_s')   # cmp word [si+38h], 0 / jle   down
    a.b(0x83, 0x7c, 0x04, 0x00); a.short(0x75, 'mnf_next_s')   # cmp word [si+4], 0 / jne   in the air
    a.b(0x8a, 0x44, 0x35)                                    # mov al, [si+35h]
    for t in MINE_TYPES:
        a.b(0x3c, t); a.short(0x74, 'mnf_type')
    a.label('mnf_next_s')
    a.near(0xe9, 'mnf_next')
    a.label('mnf_type')
    a.b(0x3c, MUDMAN); a.short(0x75, 'mnf_scan')             # a mudman in the mud walks on nothing
    a.b(0xf6, 0x44, 0x48, 0x08); a.short(0x74, 'mnf_next_s')
    a.label('mnf_scan')
    a.b(0x33, 0xff, 0xba, 0x01, 0x00)                        # xor di, di / mov dx, 1   mine number * 2, its bit
    a.label('mnf_mine')
    a.b(0x2e, 0x85, 0x16); a.word('mine_live'); a.short(0x74, 'mnf_nm')   # test cs:[mine_live], dx / jz
    a.b(0x8a, 0x44, 0x35)                                    # mov al, [si+35h]
    a.b(0x3c, 0x06); a.short(0x74, 'mnf_feet')               # a human's knight
    a.b(0x3c, COMPUTER_TYPE); a.short(0x74, 'mnf_feet')      # or a computer's: by its feet; others by x and depth
    a.b(0x8b, 0x44, 0x02, 0x2e, 0x2b, 0x85); a.word('mine_x'); a.short(0x79, 'mnf_ax'); a.b(0xf7, 0xd8)   # |x - mine x|
    a.label('mnf_ax')
    a.b(0x3d, MINE_REACH_X, 0x00); a.short(0x7f, 'mnf_nm')
    a.b(0x8b, 0x44, 0x06, 0x2e, 0x2b, 0x85); a.word('mine_z'); a.short(0x79, 'mnf_az'); a.b(0xf7, 0xd8)   # |depth - mine depth|
    a.label('mnf_az')
    a.b(0x3d, MINE_REACH_Z, 0x00); a.short(0x7e, 'mnf_boom')
    a.label('mnf_nm')
    a.b(0xd1, 0xe2, 0x83, 0xc7, 0x02, 0x83, 0xff, 2 * MINE_COUNT); a.short(0x72, 'mnf_mine')   # shl dx, 1 / add di, 2 / cmp di, 20 / jb
    a.near(0xe9, 'mnf_next')
    a.label('mnf_feet')
    a.b(0x8b, 0x44, 0x02, 0x2e, 0x2b, 0x85); a.word('mine_x')   # mov ax, [si+2] / sub ax, cs:[di+mine_x]   x - mine x
    a.b(0xf6, 0x47, 0x14, 0x02); a.short(0x75, 'mnf_f_mir')  # test byte [bx+14h], 2 / jnz   drawn mirrored
    a.b(0x83, 0xc0, MINE_FOOT_RIGHT); a.short(0xeb, 'mnf_f_x')   # add ax, 19
    a.label('mnf_f_mir')
    a.b(0x83, 0xc0, MINE_FOOT_MIRRORED)                      # add ax, 12
    a.label('mnf_f_x')
    a.b(0x83, 0xf8, MINE_FOOT_WIDTH); a.short(0x77, 'mnf_nm')   # cmp ax, 32 / ja   the mark's centre is not under the feet
    a.b(0x8b, 0x44, 0x06, 0x2e, 0x2b, 0x85); a.word('mine_z')   # mov ax, [si+6] / sub ax, cs:[di+mine_z]
    a.b(0x83, 0xc0, MINE_FOOT_Z + MINE_FOOT_REACH)           # add ax, 29
    a.b(0x83, 0xf8, 2 * MINE_FOOT_REACH); a.short(0x77, 'mnf_nm')   # cmp ax, 4 / ja
    a.label('mnf_boom')
    a.b(0xf7, 0xd2, 0x2e, 0x21, 0x16); a.word('mine_live')   # not dx / and cs:[mine_live], dx   spent
    a.b(0x2e, 0xc7, 0x06); a.word('snd_id'); a.b(MINE_SOUND, 0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('snd_req'); a.b(0x01)      # the blast, in the next frame
    a.b(0x80, 0x7c, 0x35, 0x06); a.short(0x74, 'mnf_knight')   # a human's knight
    a.b(0x80, 0x7c, 0x35, COMPUTER_TYPE); a.short(0x74, 'mnf_knight')   # or a computer's (a Black Knight): blown up too
    # a script chained to come (the last frames of a swing, op 82h) would cut the hit reaction off after a frame and
    # leave it standing with no HP: the script goes on, without the chain (set_script clears them)
    a.b(0x8b, 0x47, 0x02); a.near(0xe8, 'set_script')        # mov ax, [bx+2] / call set_script
    a.b(0xc7, 0x44, 0x38, 0x01, 0x00)                        # mov word [si+38h], 1
    a.b(0xc7, 0x44, 0x0e, MINE_HITTER & 0xff, MINE_HITTER >> 8)   # mov word [si+0Eh], the dummy: its hit reaction, with no HP left
    a.short(0xeb, 'mnf_next')
    a.label('mnf_knight')
    a.b(0xc7, 0x44, 0x0c, 0x00, 0x00, 0xc7, 0x44, 0x0e, 0x00, 0x00)   # no hit or touch pending
    a.b(0xc7, 0x44, 0x38, 0xff, 0xff)                        # mov word [si+38h], -1
    a.b(0x53); a.near(0xe8, 'obj_index'); a.short(0x72, 'mnf_nk')   # push bx / call obj_index / jc   as an instant kill
    a.b(0xd1, 0xfb, 0x2e, 0xc6, 0x87); a.word('cheat_killed'); a.b(0x01)   # sar bx, 1 / mov byte cs:[bx+cheat_killed], 1
    a.label('mnf_nk')
    a.b(0x5b, 0xb8, PLAIN_DEATH & 0xff, PLAIN_DEATH >> 8)    # pop bx / mov ax, the plain death
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_DEATHS); a.b(DEATHS['off']); a.short(0x74, 'mnf_set')
    a.near(0xe8, 'deaths_gore'); a.short(0x75, 'mnf_set')    # gore on, K18?
    a.b(0xb8, CRUSH & 0xff, CRUSH >> 8)                      # mov ax, 16E2h   as the troll's crush
    a.label('mnf_set')
    a.near(0xe8, 'set_script')                               # bx = its animation
    a.label('mnf_next')
    a.b(0x83, 0xc3, ANIM_SIZE)                               # add bx, 24h
    a.b(0x49); a.short(0x74, 'mnf_end'); a.near(0xe9, 'mnf_slot')   # dec cx / jz / jmp
    a.label('mnf_end')
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)            # pop di si dx cx bx ax / ret
    # mine_place: the ten mines, not within MINE_CLEAR of a knight standing; the dummy knight (ds = MAIN's data)
    a.label('mine_place')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x06, 0x1e, 0x07, 0xfc)   # push ax bx cx dx si di es / push ds / pop es / cld
    a.b(0xbf, MINE_HITTER & 0xff, MINE_HITTER >> 8, 0xb9, SLOT_SIZE, 0x00, 0x32, 0xc0, 0xf3, 0xaa)   # the dummy: zeros
    h = MINE_HITTER
    a.b(0xc6, 0x06, (h + 0x35) & 0xff, (h + 0x35) >> 8, 0x06)   # type: a knight's
    a.b(0xc7, 0x06, (h + 0x28) & 0xff, (h + 0x28) >> 8, 0x04, 0x00)   # move: a swing
    a.b(0xc7, 0x06, (h + 0x1a) & 0xff, (h + 0x1a) >> 8, h & 0xff, h >> 8)   # its damage table: itself
    a.b(0xc7, 0x06, (h + 0x04) & 0xff, (h + 0x04) >> 8, 0xe7, 0x03)   # ... [+4] = 999 for the swing
    a.b(0xc7, 0x06, (h + 0x44) & 0xff, (h + 0x44) >> 8, (h + 0x48) & 0xff, (h + 0x48) >> 8)   # items: none
    a.b(0x33, 0xff)                                          # xor di, di   mine number * 2
    a.label('mnp_mine')
    a.b(0xba, 0x08, 0x00)                                    # mov dx, 8   tries
    a.label('mnp_try')
    a.near(0xe8, 'game_random')
    a.b(0x25, 0xff, 0x7f, 0x52, 0x33, 0xd2, 0xb9, MINE_SPAN_X & 0xff, MINE_SPAN_X >> 8, 0xf7, 0xf1)   # and ax, 7FFFh / push dx / xor dx, dx / mov cx, span / div cx
    a.b(0x83, 0xc2, MINE_X0, 0x8b, 0xda)                     # add dx, x0 / mov bx, dx   x
    a.near(0xe8, 'game_random')
    a.b(0x25, 0xff, 0x7f, 0x33, 0xd2, 0xb9, MINE_SPAN_Z, 0x00, 0xf7, 0xf1)   # and ax, 7FFFh / xor dx, dx / mov cx, span / div cx
    a.b(0x83, 0xc2, MINE_Z0, 0x8b, 0xca, 0x5a)               # add dx, z0 / mov cx, dx   depth / pop dx
    a.b(0xbe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)            # mov si, 6C9Eh
    a.label('mnp_k')
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'mnp_kn')     # standing?
    a.b(0x8b, 0x44, 0x02, 0x2b, 0xc3); a.short(0x79, 'mnp_a1'); a.b(0xf7, 0xd8)   # |its x - x|
    a.label('mnp_a1')
    a.b(0x3d, MINE_CLEAR_X, 0x00); a.short(0x7f, 'mnp_kn')
    a.b(0x8b, 0x44, 0x06, 0x2b, 0xc1, 0x83, 0xc0, MINE_FOOT_Z); a.short(0x79, 'mnp_a2'); a.b(0xf7, 0xd8)   # |its depth - the depth its feet would set it off|
    a.label('mnp_a2')
    a.b(0x3d, MINE_CLEAR_Z, 0x00); a.short(0x7f, 'mnp_kn')
    a.b(0x4a); a.short(0x75, 'mnp_try')                      # dec dx / jnz   too near: again (at last, where it fell)
    a.short(0xeb, 'mnp_set')
    a.label('mnp_kn')
    a.b(0x83, 0xc6, SLOT_SIZE, 0x81, 0xfe, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8); a.short(0x72, 'mnp_k')
    a.label('mnp_set')
    a.b(0x2e, 0x89, 0x9d); a.word('mine_x'); a.b(0x2e, 0x89, 0x8d); a.word('mine_z')   # mov cs:[di+mine_x], bx / cs:[di+mine_z], cx
    a.b(0x83, 0xc7, 0x02, 0x83, 0xff, 2 * MINE_COUNT); a.short(0x72, 'mnp_mine')
    a.b(0x2e, 0xc7, 0x06); a.word('mine_live'); a.b(((1 << MINE_COUNT) - 1) & 0xff, ((1 << MINE_COUNT) - 1) >> 8)
    a.b(0x2e, 0xc6, 0x06); a.word('mine_todo'); a.b(MINE_COUNT)
    a.b(0x07, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)      # pop es di si dx cx bx ax / ret

    # --- DARTS (D48, a fight code) ---
    # darts_frame (every fight frame): a knight in the fight (a human's or a computer's) with no dagger is lent one
    # (darts_lent); the thrower gets every dagger it throws back (rules_dagger_thrower), so it never runs out
    a.label('darts_frame')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_DARTS); a.short(0x75, 'drf_go'); a.b(0xc3)
    a.label('drf_go')
    a.b(0x50, 0x53, 0x51, 0x56)                              # push ax bx cx si
    a.b(0xbb, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # mov bx, 947Eh / mov cx, 10
    a.label('drf_slot')
    a.b(0x80, 0x3f, 0x00); a.short(0x74, 'drf_next')         # cmp byte [bx], 0 / je
    a.b(0x8b, 0x77, 0x16, 0x81, 0xfe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'drf_next')   # mov si, [bx+16h] / cmp si, 6C9Eh / jb
    a.b(0x8a, 0x44, 0x35, 0x3c, 0x06); a.short(0x74, 'drf_knight')   # mov al, [si+35h] / cmp al, 6 / je
    a.b(0x3c, COMPUTER_TYPE); a.short(0x75, 'drf_next')
    a.label('drf_knight')
    a.b(0x80, 0x7c, 0x34, 0x00); a.short(0x75, 'drf_next')   # cmp byte [si+34h], 0 / jne
    a.b(0xc6, 0x44, 0x34, 0x01)                              # mov byte [si+34h], 1   lent
    a.b(0x53); a.near(0xe8, 'obj_index'); a.short(0x72, 'drf_nl')   # push bx / call obj_index / jc
    a.b(0xd1, 0xfb, 0x2e, 0xc6, 0x87); a.word('darts_lent'); a.b(0x01)   # sar bx, 1 / mov byte cs:[bx+darts_lent], 1
    a.label('drf_nl')
    a.b(0x5b)                                                # pop bx
    a.label('drf_next')
    a.b(0x83, 0xc3, ANIM_SIZE); a.short(0xe2, 'drf_slot')    # add bx, 24h / loop
    a.b(0x5e, 0x59, 0x5b, 0x58, 0xc3)                        # pop si cx bx ax / ret
    # d48_fight_end (from cheat_fight_end, es = cs): the new fight codes end; the four knights give a lent dagger back
    a.label('d48_fight_end')
    a.b(0x2e, 0xc6, 0x06); a.word('bars_on'); a.b(0x00, 0x2e, 0xc6, 0x06); a.word('bars_n'); a.b(0x00)   # D54: off, not laid out
    a.b(0xbf); a.word('sab_kind'); a.b(0xb9, 25, 0x00, 0x32, 0xc0, 0xfc, 0xf3, 0xaa)   # D51: sab_kind = 0
    a.b(0x2e, 0xc6, 0x06); a.word('cheat_flags2'); a.b(0x00)
    a.b(0x2e, 0xc6, 0x06); a.word('df_on'); a.b(0x00)
    for k, rec in enumerate(KNIGHTS):
        a.b(0x2e, 0x80, 0x3e); a.word('darts_lent', k); a.b(0x00); a.short(0x74, f'dfe_n{k}')
        a.b(0xc6, 0x06, (rec + 0x34) & 0xff, (rec + 0x34) >> 8, 0x00)   # mov byte [rec+34h], 0
        a.label(f'dfe_n{k}')
    a.b(0xbf); a.word('darts_lent'); a.b(0xb9, 25, 0x00, 0x32, 0xc0, 0xfc, 0xf3, 0xaa)   # darts_lent = 0
    a.b(0xc3)

    # --- DAGGERFALL (D49, a fight code typed in the first menu or on the map) ---
    # df_frame (every fight frame): a dagger due every DF_EVERY ticks
    a.label('df_frame')
    a.b(0x2e, 0x80, 0x3e); a.word('df_on'); a.b(0x00); a.short(0x75, 'dff_go'); a.b(0xc3)
    a.label('dff_go')
    a.b(0x50, 0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f)   # push ax / push ds / ds = 0 / mov ax, [046Ch] / pop ds
    a.b(0x50, 0x2e, 0x2b, 0x06); a.word('df_last'); a.b(0x3d, DF_EVERY, 0x00, 0x58); a.short(0x72, 'dff_pop')   # push ax / sub ax, cs:[df_last] / cmp ax, every / pop ax / jb
    a.b(0x2e, 0xa3); a.word('df_last')                       # mov cs:[df_last], ax
    a.b(0x2e, 0xc6, 0x06); a.word('df_due'); a.b(0x01)
    a.label('dff_pop')
    a.b(0x58, 0xc3)                                          # pop ax / ret
    # df_spawn (ds = MAIN's data): CF = 1 when no animation or object slot is free; else di = the dagger's record
    # (a free one of the fight's objects, as 1000:2A1E and 3E89), si = its script (written at DF_SCRIPT)
    a.label('df_spawn')
    a.b(0x50, 0x53, 0x51, 0x52)                              # push ax bx cx dx
    a.b(0xbb, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # mov bx, 947Eh / mov cx, 10
    a.label('dfs_anim')
    a.b(0x80, 0x3f, 0x00); a.short(0x74, 'dfs_anim_ok')      # cmp byte [bx], 0 / je
    a.b(0x83, 0xc3, ANIM_SIZE); a.short(0xe2, 'dfs_anim')
    a.short(0xeb, 'dfs_none')
    a.label('dfs_anim_ok')
    a.b(0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00)   # mov di, 6F08h / mov cx, 20
    a.label('dfs_rec')
    a.b(0x83, 0x3d, 0x00); a.short(0x74, 'dfs_rec_ok')       # cmp word [di], 0 / je
    a.b(0x83, 0xc7, SLOT_SIZE); a.short(0xe2, 'dfs_rec')
    a.label('dfs_none')
    a.b(0x5a, 0x59, 0x5b, 0x58, 0xf9, 0xc3)                  # pop dx cx bx ax / stc / ret
    a.label('dfs_rec_ok')
    a.b(0x06, 0x1e, 0x07, 0x57, 0xb9, SLOT_SIZE, 0x00, 0x32, 0xc0, 0xfc, 0xf3, 0xaa, 0x5f, 0x07)   # the record zeroed
    for field, span, base in ((0x02, DF_SPAN_X, DF_X0), (0x06, DD_BOTTOM - DD_TOP + 1, DD_TOP)):
        a.near(0xe8, 'df_random')
        a.b(0xb9, span & 0xff, span >> 8, 0xf7, 0xe1)     # mov cx, span / mul cx   scale to the range via dx
        a.b(0x83, 0xc2, base, 0x89, 0x55, field)             # add dx, base / mov [di+field], dx
    a.b(0x83, 0xc2, DF_START, 0xf7, 0xda, 0x89, 0x55, 0x04)  # add dx, start / neg dx / mov [di+4], dx   just above the screen
    a.near(0xe8, 'df_random'); a.b(0x8a, 0xc4, 0x24, 0x02, 0x0c, 0x01, 0x88, 0x45, 0x08)   # mov al, ah / and al, 2 / or al, 1 / mov [di+8], al   facing 1 or 3
    a.b(0xc7, 0x05, 0x01, 0x00)                              # mov word [di], 1
    a.b(0xc7, 0x45, 0x18, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8)   # mov word [di+18h], the knights' banks
    a.b(0xc7, 0x45, 0x1a, DF_DAMAGE & 0xff, DF_DAMAGE >> 8)  # mov word [di+1Ah], 772Ah   as a thrown dagger
    a.b(0xc7, 0x45, 0x28, 0x06, 0x00, 0xc6, 0x45, 0x35, DAGGER)   # mov word [di+28h], 6 / mov byte [di+35h], 1Ah
    a.b(0x89, 0x7d, DAGGER_OWNER)                            # mov [di+5Ch], di   its own thrower: from the sky
    a.b(0xbe); a.word('df_src'); a.b(0xbb, DF_SCRIPT & 0xff, DF_SCRIPT >> 8, 0xb9, 0x10, 0x00)   # mov si, df_src / mov bx, DF_SCRIPT / mov cx, 16
    a.label('dfs_copy')
    a.b(0x2e, 0x8a, 0x04, 0x88, 0x07, 0x46, 0x43); a.short(0xe2, 'dfs_copy')   # mov al, cs:[si] / mov [bx], al / inc si / inc bx / loop
    a.b(0xbe, DF_SCRIPT & 0xff, DF_SCRIPT >> 8)              # mov si, DF_SCRIPT
    a.b(0x5a, 0x59, 0x5b, 0x58, 0xf8, 0xc3)                  # pop dx cx bx ax / clc / ret

    # Three calls per drop. The game's RNG can repeat the same 21 positions in a stationary fight.
    a.label('df_random')
    a.b(0x2e, 0xa1); a.word('df_rng')                       # mov ax, cs:[df_rng]
    a.b(0x69, 0xc0, struct.pack('<H', DF_RNG_MULT))           # imul ax, ax, multiplier
    a.b(0x05, struct.pack('<H', DF_RNG_ADD))                 # add ax, increment
    a.b(0x2e, 0xa3); a.word('df_rng'); a.b(0xc3)             # mov cs:[df_rng], ax / ret

    # At A12E the game skips weapon pairs more than ten units apart in depth. Falling blades strike
    # across the screen, so let them reach the pixel test at A133 at any depth.
    a.label('rules_falling_dagger_depth')
    a.b(0x83, 0xfa, 0x0a); a.short(0x7e, 'dfz_end')          # cmp dx, 10 / jle   (replaced)
    a.b(0x8b, 0x5e, 0x00)                                    # mov bx, [bp]   attacker animation
    a.b(0x83, 0x7f, 0x1a, DAGGER); a.short(0x75, 'dfz_skip') # cmp word [bx+1Ah], DAGGER / jne
    a.b(0x8b, 0x5f, 0x16, 0x39, 0x5f, DAGGER_OWNER)          # mov bx, [bx+16h] / cmp [bx+5Ch], bx
    a.short(0x74, 'dfz_end')                                 # je   the dagger's own thrower marks a falling dagger
    a.label('dfz_skip')
    a.b(0xc7, 0x46, 0x02, 0x76, 0xa1)                        # mov word [bp+2], A176h   next target
    a.label('dfz_end')
    a.near(0xe9, 'rules_done')

    # A1A6 tests weapon points against the target sprite's opaque pixels. COLLIDE.HIT has points for the
    # thrown dagger in KN4.OB. Supply the rotated frame's points and enter the same test at A1FB.
    a.label('rules_falling_dagger_hit')
    a.b(0xc7, 0x06, 0xc2, 0xc2, 0x00, 0x00)                  # mov word [C2C2h], 0   (replaced)
    a.b(0x83, 0x7d, 0x04, BALL_PIC); a.short(0x75, 'dfh_nball')   # D64: cmp word [di+4], the ball / jne
    a.b(0x8b, 0x5e, 0x00, 0x8b, 0x5f, 0x16)                  # mov bx, [bp] / mov bx, [bx+16h]   attacker
    a.b(0x80, 0x7f, 0x35, DAGGER); a.short(0x75, 'dfh_end')  # cmp byte [bx+35h], DAGGER / jne
    # the width of a frame drawn mirrored (facing left), as A1AC-A1CA, which A1FB needs for the points
    a.b(0x8b, 0x45, 0x04, 0xd1, 0xe0, 0xd1, 0xe0, 0x03, 0x45, 0x04, 0xd1, 0xe0)   # mov ax, [di+4] / ax * 10
    a.b(0xc4, 0x1d, 0x03, 0xd8)                              # les bx, [di] / add bx, ax
    a.b(0x26, 0xf6, 0x47, 0x12, 0x01); a.short(0x75, 'dfh_ball')   # test byte es:[bx+12h], 1 / jnz   not mirrored
    a.b(0x26, 0x8b, 0x47, 0x0e, 0x86, 0xe0, 0xa3, 0xc2, 0xc2)   # mov ax, es:[bx+0Eh] / xchg al, ah / mov [C2C2h], ax
    a.label('dfh_ball')
    a.b(0xc7, 0x46, 0xfe, GUN_POINTS & 0xff, GUN_POINTS >> 8)   # mov word [bp-2], its points (gun_write)   the game's bx
    a.b(0xc7, 0x46, 0x02, 0xfb, 0xa1); a.near(0xe9, 'rules_done')   # mov word [bp+2], A1FBh
    a.label('dfh_nball')
    a.b(0x83, 0x7d, 0x04, DF_PIC); a.short(0x75, 'dfh_end')  # cmp word [di+4], frame / jne
    a.b(0x8b, 0x5e, 0x00, 0x8b, 0x5f, 0x16)                  # mov bx, [bp] / mov bx, [bx+16h]   attacker
    a.b(0x80, 0x7f, 0x35, DAGGER); a.short(0x75, 'dfh_end')  # cmp byte [bx+35h], DAGGER / jne
    a.b(0x39, 0x5f, DAGGER_OWNER); a.short(0x75, 'dfh_end')   # cmp [bx+5Ch], bx / jne   a thrown dagger
    xs, ys = zip(*DF_HIT_POINTS)
    # The COLLIDE.HIT loader (887F) stores count, the unused second field, max x/y, then the point pairs.
    hit_data = bytes((len(xs), 0, max(xs), max(ys))) + bytes(n for point in DF_HIT_POINTS for n in point)
    if DF_HIT_DATA + len(hit_data) > KEY_LIST:
        raise ValueError("D62: the falling dagger's hit points run into KEY_LIST")
    for offset in range(0, len(hit_data), 2):
        a.b(0xc7, 0x06, struct.pack('<H', DF_HIT_DATA + offset), hit_data[offset:offset + 2])
    a.b(0xc7, 0x46, 0xfe, struct.pack('<H', DF_HIT_DATA))     # mov word [bp-2], points   the game's bx
    a.b(0xc7, 0x46, 0x02, 0xfb, 0xa1)                        # mov word [bp+2], A1FBh
    a.label('dfh_end')
    a.near(0xe9, 'rules_done')

    # mine_shown (D50): the mines are drawn: the time (ax kept)
    a.label('mine_shown')
    a.b(0x50, 0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f)   # push ax / push ds / ds = 0 / mov ax, [046Ch] / pop ds
    a.b(0x2e, 0xa3); a.word('mine_t'); a.b(0x2e, 0xc6, 0x06); a.word('mine_vis'); a.b(0x01, 0x58, 0xc3)   # ... / pop ax / ret
    # mine_rect (D50; bx = the mine's number * 2, cs:[mine_mode]): its MINE_W x MINE_H pixels in the background page
    # (unchained: plane = x & 3, offset = y * 80 + x / 4): 0 kept in mine_bg, 1 put back where the mark's colour is.
    # The VGA registers it uses are kept and set back (the game copies the background with the latches)
    a.label('mine_rect')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x55, 0x06)      # push ax bx cx dx si di bp es
    a.b(0xb8, MINE_BG_PAGE & 0xff, MINE_BG_PAGE >> 8, 0x8e, 0xc0)   # mov ax, 0AC00h / mov es, ax
    a.b(0xba, 0xc4, 0x03, 0xec, 0x50)                        # mov dx, 3C4h / in al, dx / push ax   sequencer index
    a.b(0xb0, 0x02, 0xee, 0x42, 0xec, 0x50, 0x4a)            # mov al, 2 / out dx, al / inc dx / in al, dx / push ax / dec dx   map mask
    a.b(0xb2, 0xce, 0xec, 0x50)                              # mov dl, 0CEh / in al, dx / push ax   graphics index
    for idx in (1, 4, 5, 8):                                 # set/reset enable, read map, mode, bit mask
        a.b(0xb0, idx, 0xee, 0x42, 0xec, 0x50, 0x4a)         # mov al, idx / out dx, al / inc dx / in al, dx / push ax / dec dx
    a.b(0xb8, 0x01, 0x00, 0xef, 0xb8, 0x08, 0xff, 0xef)      # set/reset off / bit mask FFh
    a.b(0xb0, 0x05, 0xee, 0x42, 0xec, 0x24, 0xf4, 0xee, 0x4a)   # mode: read mode 0, write mode 0 (the rest kept)
    a.b(0x8b, 0xc3, 0xd1, 0xe8, 0xb1, MINE_W * MINE_H, 0xf6, 0xe1, 0x05); a.word('mine_bg'); a.b(0x8b, 0xf0)   # si = mine_bg + n * 27
    a.b(0x2e, 0x8b, 0xbf); a.word('mine_z'); a.b(0x83, 0xc7, MINE_DRAW_Y)   # mov di, cs:[bx+mine_z] / add di, 22   y
    a.b(0x2e, 0x8b, 0xaf); a.word('mine_x'); a.b(0x83, 0xc5, MINE_DRAW_X & 0xff)   # mov bp, cs:[bx+mine_x] / add bp, -4   x
    a.b(0xb5, MINE_H)                                        # mov ch, 3
    a.label('mr_row')
    a.b(0x55, 0xb1, MINE_W)                                  # push bp / mov cl, 9
    a.label('mr_col')
    a.b(0x81, 0xfd, 0x40, 0x01); a.short(0x73, 'mr_next')    # cmp bp, 320 / jae   off the screen
    a.b(0x81, 0xff, 0xc8, 0x00); a.short(0x73, 'mr_next')    # cmp di, 200 / jae
    a.b(0x8b, 0xc7, 0x8b, 0xd8, 0xd1, 0xe0, 0xd1, 0xe0, 0x03, 0xc3)   # mov ax, di / mov bx, ax / shl ax, 1 (x2) / add ax, bx   5y
    a.b(0xd1, 0xe0, 0xd1, 0xe0, 0xd1, 0xe0, 0xd1, 0xe0)      # shl ax, 1 (x4)   80y
    a.b(0x8b, 0xdd, 0xd1, 0xeb, 0xd1, 0xeb, 0x03, 0xd8)      # mov bx, bp / shr bx, 1 (x2) / add bx, ax   the offset
    a.b(0x8b, 0xc5, 0x24, 0x03, 0x8a, 0xe0)                  # mov ax, bp / and al, 3 / mov ah, al   the plane
    a.b(0xba, 0xce, 0x03, 0xb0, 0x04, 0xee, 0x42, 0x8a, 0xc4, 0xee)   # mov dx, 3CEh / mov al, 4 / out dx, al / inc dx / mov al, ah / out dx, al
    a.b(0x26, 0x8a, 0x07)                                    # mov al, es:[bx]
    a.b(0x2e, 0x80, 0x3e); a.word('mine_mode'); a.b(0x00); a.short(0x75, 'mr_back')
    a.b(0x2e, 0x88, 0x04); a.short(0xeb, 'mr_next')          # mov cs:[si], al / jmp
    a.label('mr_back')
    a.b(0x3c, MINE_COLOUR); a.short(0x75, 'mr_next')         # cmp al, 5 / jne   something else is drawn there now
    a.b(0xb0, 0x01, 0x51, 0x8a, 0xcc, 0xd2, 0xe0, 0x59)      # mov al, 1 / push cx / mov cl, ah / shl al, cl / pop cx
    a.b(0xba, 0xc4, 0x03, 0x8a, 0xe0, 0xb0, 0x02, 0xef)      # mov dx, 3C4h / mov ah, al / mov al, 2 / out dx, ax   map mask
    a.b(0x2e, 0x8a, 0x04, 0x26, 0x88, 0x07)                  # mov al, cs:[si] / mov es:[bx], al
    a.label('mr_next')
    a.b(0x46, 0x45, 0xfe, 0xc9); a.short(0x75, 'mr_col')     # inc si / inc bp / dec cl / jnz
    a.b(0x5d, 0x47, 0xfe, 0xcd); a.short(0x75, 'mr_row')     # pop bp / inc di / dec ch / jnz
    a.b(0xba, 0xce, 0x03)                                    # mov dx, 3CEh
    for idx in (8, 5, 4, 1):
        a.b(0x58, 0x8a, 0xe0, 0xb0, idx, 0xef)               # pop ax / mov ah, al / mov al, idx / out dx, ax
    a.b(0x58, 0xee, 0xb2, 0xc4)                              # pop ax / out dx, al / mov dl, 0C4h
    a.b(0x58, 0x8a, 0xe0, 0xb0, 0x02, 0xef, 0x58, 0xee)      # map mask back / sequencer index back
    a.b(0x07, 0x5d, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)   # pop es bp di si dx cx bx ax / ret

    # --- LIGHTSABER (D51, a fight code) ---
    # saber_glow (D57; from recolour, ds = es = the frame converted, one byte a pixel, rows of [637Bh] / [8168h] bytes;
    # bp = the handler's frame; saber_frame = its KN4.OB frame): the blade's and the swings' pixels 1-2 in the colour the
    # knight's pixel 8 shows (the glow), then the blade's straight centre line (SABER_LINES) white. The daggers are kept
    a.label('saber_glow')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x55)            # push ax bx cx dx si di bp
    a.b(0x2e, 0xa0); a.word('saber_frame'); a.b(0x3c, 0x09); a.short(0x74, 'sgl_end1'); a.b(0x3c, 0x0a); a.short(0x75, 'sgl_sw')   # frames 9, 10: daggers
    a.label('sgl_end1')
    a.near(0xe9, 'sgl_end')
    a.label('sgl_sw')
    a.b(0x2e, 0xa0); a.word('rc_xlat', 8); a.b(0x2e, 0xa2); a.word('sab_g')   # mov al, cs:[rc_xlat+8] / mov cs:[sab_g], al
    a.b(0x1e, 0x8e, 0x5e, 0x04, 0x8b, 0x0e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)   # push ds / mov ds, [bp+4] / mov cx, [637Bh]   the bytes
    a.b(0x8e, 0x5e, 0x0c, 0x8b, 0x1e, 0x68, 0x81, 0x1f)      # mov ds, [bp+12] / mov bx, [8168h] / pop ds   the rows
    a.b(0x0b, 0xdb); a.short(0x75, 'sgl_rows'); a.near(0xe9, 'sgl_end')   # or bx, bx / jnz
    a.label('sgl_rows')
    a.b(0x8b, 0xc1, 0x33, 0xd2, 0xf7, 0xf3, 0x8b, 0xe8)      # mov ax, cx / xor dx, dx / div bx / mov bp, ax   bp = the row's bytes
    a.b(0x0b, 0xed); a.short(0x75, 'sgl_go'); a.near(0xe9, 'sgl_end')
    a.label('sgl_go')
    a.b(0x2e, 0x8a, 0x26); a.word('sab_g'); a.b(0x33, 0xf6)  # mov ah, cs:[sab_g] / xor si, si
    a.label('sgl_px')
    a.b(0x8a, 0x04, 0x3c, 0x01); a.short(0x74, 'sgl_dark'); a.b(0x3c, 0x02); a.short(0x75, 'sgl_next')   # mov al, [si] / 1 or 2?
    a.label('sgl_dark')
    a.b(0x88, 0x24)                                          # mov [si], ah   the glow
    a.label('sgl_next')
    a.b(0x46, 0x3b, 0xf1); a.short(0x72, 'sgl_px')           # inc si / cmp si, cx / jb
    a.b(0x2e, 0x8a, 0x1e); a.word('saber_frame'); a.b(0x80, 0xfb, SABER_FRAMES_TAB); a.short(0x73, 'sgl_end')   # mov bl, frame / cmp bl, n / jae
    a.b(0x32, 0xff, 0xd1, 0xe3, 0x2e, 0x8b, 0xb7); a.word('saber_ltab'); a.b(0x0b, 0xf6); a.short(0x74, 'sgl_end')   # xor bh, bh / shl bx, 1 / mov si, cs:[bx+saber_ltab] / or si, si / jz
    # D59: the line's first and middle points must fall on the blade (now the glow's colour): as the frame is
    # (sab_k = -1), or mirrored in the row with the padding k = 0-15 to its left (x' = row - 1 - x - k)
    a.b(0x2e, 0xc7, 0x06); a.word('sab_k'); a.b(0xff, 0xff)
    a.label('sgl_try')
    a.b(0x2e, 0x8a, 0x5c, 0x01, 0x2e, 0x8a, 0x44, 0x02); a.near(0xe8, 'sgl_map'); a.short(0x72, 'sgl_nk')   # the first point
    a.b(0x2e, 0xa0); a.word('sab_g'); a.b(0x38, 0x05); a.short(0x75, 'sgl_nk')   # mov al, cs:[sab_g] / cmp [di], al / jne
    a.b(0x2e, 0x8a, 0x1c, 0xd0, 0xeb, 0x32, 0xff, 0xd1, 0xe3, 0x56, 0x03, 0xf3)   # mov bl, cs:[si] (n) / shr bl, 1 / xor bh, bh / shl bx, 1 / push si / add si, bx
    a.b(0x2e, 0x8a, 0x5c, 0x01, 0x2e, 0x8a, 0x44, 0x02, 0x5e); a.near(0xe8, 'sgl_map'); a.short(0x72, 'sgl_nk')   # the middle point / pop si
    a.b(0x2e, 0xa0); a.word('sab_g'); a.b(0x38, 0x05); a.short(0x74, 'sgl_found')
    a.label('sgl_nk')
    a.b(0x2e, 0xff, 0x06); a.word('sab_k'); a.b(0x2e, 0x83, 0x3e); a.word('sab_k'); a.b(0x10); a.short(0x7c, 'sgl_try')   # inc / cmp sab_k, 16 / jl
    a.short(0xeb, 'sgl_end')                                 # nowhere: no line
    a.label('sgl_found')
    a.b(0x46)                                                # inc si   past the count
    a.label('sgl_ln')
    a.b(0x2e, 0x8a, 0x1c, 0x80, 0xfb, 0xff); a.short(0x74, 'sgl_end')   # mov bl, cs:[si] (x) / cmp bl, FFh / je
    a.b(0x2e, 0x8a, 0x44, 0x01); a.near(0xe8, 'sgl_map'); a.short(0x72, 'sgl_lnx')   # mov al, cs:[si+1] (y) / its place
    a.b(0xc6, 0x05, SABER_WHITE)                             # mov byte [di], 1   white
    a.label('sgl_lnx')
    a.b(0x46, 0x46); a.short(0xeb, 'sgl_ln')
    a.label('sgl_end')
    a.b(0x5d, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)      # pop bp di si dx cx bx ax / ret
    # sgl_map (bl = x, al = y of a frame's pixel; bp = the row's bytes, cx = all; sab_k): di = its byte, CF = 1 outside
    a.label('sgl_map')
    a.b(0x53, 0x32, 0xff, 0x2e, 0x8b, 0x16); a.word('sab_k'); a.b(0x83, 0xfa, 0xff); a.short(0x74, 'sgm_xy')   # push bx / xor bh, bh / mov dx, cs:[sab_k] / cmp dx, -1 / je
    a.b(0x50, 0x8b, 0xc5, 0x48, 0x2b, 0xc3, 0x2b, 0xc2, 0x8b, 0xd8, 0x58)   # push ax / mov ax, bp / dec ax / sub ax, bx / sub ax, dx / mov bx, ax / pop ax
    a.b(0x0b, 0xdb); a.short(0x78, 'sgm_out'); a.b(0x3b, 0xdd); a.short(0x73, 'sgm_out')   # or bx, bx / js / cmp bx, bp / jae
    a.label('sgm_xy')
    a.b(0x32, 0xe4, 0xf7, 0xe5, 0x03, 0xc3, 0x8b, 0xf8, 0x3b, 0xf9); a.short(0x73, 'sgm_out')   # xor ah, ah / mul bp / add ax, bx / mov di, ax / cmp di, cx / jae
    a.b(0x5b, 0xf8, 0xc3)                                    # pop bx / clc / ret
    a.label('sgm_out')
    a.b(0x5b, 0xf9, 0xc3)                                    # pop bx / stc / ret
    # saber_mon (from ench_hit: ax = a knight's (si) blow's damage, [bp+0Eh] where 2D73 returns): a lightsaber's blow on a
    # monster (SABER_MONSTERS) kills it at once (ax = ENCH_KILL); knights: saber_knight
    a.label('saber_mon')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_SABER); a.short(0x75, 'sbm_go'); a.b(0xc3)
    a.label('sbm_go')
    a.b(0x53, 0x51, 0x57)                                    # push bx cx di
    a.b(0x80, 0x7c, 0x35, 0x06); a.short(0x74, 'sbm_knight')  # cmp byte [si+35h], 6 / je   a knight's blow
    a.b(0x80, 0x7c, 0x35, COMPUTER_TYPE); a.short(0x75, 'sbm_pop')
    a.label('sbm_knight')
    a.b(0x8b, 0x7e, 0x0c, 0x8b, 0x4e, 0x0e)                  # mov di, [bp+0Ch] / mov cx, [bp+0Eh]   the struck, as ench_hit
    for ret in (0x3776, 0x5215, 0x55bf):
        a.b(0x81, 0xf9, ret & 0xff, ret >> 8); a.short(0x75, f'sbm_r{ret:x}'); a.b(0x8b, 0x7e, 0x10); a.short(0xeb, 'sbm_who')
        a.label(f'sbm_r{ret:x}')
    a.b(0x81, 0xf9, 0xd2, 0x56); a.short(0x75, 'sbm_who'); a.b(0x8b, 0x3e, 0xe8, 0x77)
    a.label('sbm_who')
    a.b(0x81, 0xff, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8); a.short(0x74, 'sbm_pop')
    a.b(0x8a, 0x5d, 0x35)                                    # mov bl, [di+35h]
    for t in SABER_MONSTERS:
        a.b(0x80, 0xfb, t); a.short(0x74, 'sbm_kill')
    a.short(0xeb, 'sbm_pop')
    a.label('sbm_kill')
    a.b(0xb8, ENCH_KILL & 0xff, ENCH_KILL >> 8)
    a.label('sbm_pop')
    a.b(0x5f, 0x59, 0x5b, 0xc3)                              # pop di cx bx / ret
    # saber_knight (from td_adjust: ax = a blow's damage, si = the striker, di = the struck): a knight's lightsaber blow
    # on a knight that was not blocked (td_mist: a mistimed block) kills (ENCH_KILL), its death noted (sab_kind) and
    # kept from the HP codes (cheat_killed)
    a.label('saber_knight')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_SABER); a.short(0x75, 'sbk_go'); a.b(0xc3)
    a.label('sbk_go')
    a.b(0x53, 0x51)                                          # push bx cx
    a.b(0x2e, 0x80, 0x3e); a.word('td_mist'); a.b(0x00); a.short(0x75, 'sbk_pop')
    for reg, tag in ((0x7c, 's'), (0x7d, 'v')):              # [si+35h], then [di+35h]: a human's or computer's knight
        a.b(0x8a, 0x4c if reg == 0x7c else 0x4d, 0x35, 0x80, 0xf9, 0x06); a.short(0x74, f'sbk_{tag}')   # mov cl, [x+35h] / cmp cl, 6 / je
        a.b(0x80, 0xf9, COMPUTER_TYPE); a.short(0x75, 'sbk_pop')
        a.label(f'sbk_{tag}')
    a.b(0x8b, 0x5c, 0x28)                                    # mov bx, [si+28h]   the blow
    for move, kind in SABER_KINDS:
        a.b(0xb1, kind, 0x83, 0xfb, move); a.short(0x74, 'sbk_kill')   # mov cl, kind / cmp bx, move / je
    a.short(0xeb, 'sbk_pop')
    a.label('sbk_kill')
    a.b(0xb8, ENCH_KILL & 0xff, ENCH_KILL >> 8)
    a.b(0x56, 0x8b, 0xf7); a.near(0xe8, 'obj_index'); a.b(0x5e); a.short(0x72, 'sbk_pop')   # push si / mov si, di / call obj_index / pop si / jc
    a.b(0xd1, 0xfb, 0x2e, 0x88, 0x8f); a.word('sab_kind')    # sar bx, 1 / mov cs:[bx+sab_kind], cl
    a.b(0x2e, 0xc6, 0x87); a.word('cheat_killed'); a.b(0x01)   # mov byte cs:[bx+cheat_killed], 1
    a.label('sbk_pop')
    a.b(0x59, 0x5b, 0xc3)                                    # pop cx bx / ret
    # saber_finish (every fight frame): a knight struck down by a lightsaber (sab_kind) gets its death as its slump
    # begins (script 130E-1327): the split, the beheading or the run through (from the side the striker stands)
    a.label('saber_finish')
    a.b(0x50, 0x53, 0x51, 0x56, 0x57)                        # push ax bx cx si di
    a.b(0x33, 0xc9)                                          # xor cx, cx   the object's number
    a.label('sbf_loop')
    a.b(0x8b, 0xd9, 0x2e, 0x8a, 0x87); a.word('sab_kind'); a.b(0x0a, 0xc0); a.short(0x75, 'sbf_some')   # mov bx, cx / mov al, cs:[bx+sab_kind] / or al, al / jnz
    a.near(0xe9, 'sbf_next')
    a.label('sbf_some')
    a.b(0xbf, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8, 0x83, 0xf9, 0x04); a.short(0x72, 'sbf_rec')   # mov di, 6C9Eh / cmp cx, 4 / jb
    a.b(0xbf, (MONSTER_SLOTS - 4 * SLOT_SIZE) & 0xff, (MONSTER_SLOTS - 4 * SLOT_SIZE) >> 8)   # the monster slots after
    a.label('sbf_rec')
    a.b(0x50, 0xb0, SLOT_SIZE, 0xf6, 0xe1, 0x03, 0xf8, 0x58)   # push ax / mov al, 62h / mul cl / add di, ax / pop ax
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'sbf_down')    # cmp word [di+38h], 0 / jle
    a.b(0x2e, 0xc6, 0x87); a.word('sab_kind'); a.b(0x00); a.near(0xe9, 'sbf_next')   # up again: forgotten
    a.label('sbf_down')
    a.b(0x50); a.near(0xe8, 'anim_of'); a.b(0x58); a.short(0x74, 'sbf_anim'); a.near(0xe9, 'sbf_next')   # push ax / call anim_of / pop ax / jz
    a.label('sbf_anim')
    a.b(0x81, 0x7f, 0x02, SLUMP & 0xff, SLUMP >> 8); a.short(0x73, 'sbf_s1'); a.near(0xe9, 'sbf_next')   # cmp word [bx+2], 130Eh / jae
    a.label('sbf_s1')
    a.b(0x81, 0x7f, 0x02, (SLUMP + 0x1a) & 0xff, (SLUMP + 0x1a) >> 8); a.short(0x72, 'sbf_s2'); a.near(0xe9, 'sbf_next')   # cmp word [bx+2], 1328h / jb
    a.label('sbf_s2')
    a.b(0x56, 0x53); a.near(0xe8, 'sbf_clear'); a.b(0x5b, 0x5e)   # push si bx / the note off / pop bx si
    a.b(0xb8, PLAIN_DEATH & 0xff, PLAIN_DEATH >> 8)          # mov ax, the plain death
    a.near(0xe8, 'deaths_gore'); a.short(0x75, 'sbf_set')     # gore off or below K18: plain
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_DEATHS); a.b(DEATHS['off']); a.short(0x74, 'sbf_set')   # off: plain
    a.b(0xb8, BEHEADING & 0xff, BEHEADING >> 8)              # the beheading
    a.near(0xe8, 'd20_state'); a.short(0x75, 'sbf_set')       # vanilla: always the beheading
    a.b(0x2e, 0x8a, 0x26); a.word('sab_last')                # mov ah, cs:[sab_last]   the kind
    a.b(0x80, 0xfc, 0x02); a.short(0x75, 'sbf_n_split')
    a.b(0xb8, D20['split'] & 0xff, D20['split'] >> 8); a.short(0xeb, 'sbf_set')
    a.label('sbf_n_split')
    a.b(0x80, 0xfc, 0x03); a.short(0x75, 'sbf_beh')
    a.b(0x56, 0x2e, 0x8b, 0x36); a.word('sab_striker')      # push si / mov si, cs:[sab_striker]
    a.b(0x0b, 0xf6); a.short(0x74, 'sbf_front')               # or si, si / jz   (from the front)
    a.near(0xe8, 'de_side')                                  # CF = 1 from the front
    a.b(0xb8, D20['thrust_back'] & 0xff, D20['thrust_back'] >> 8); a.short(0x73, 'sbf_side')
    a.label('sbf_front')
    a.b(0xb8, D20['thrust_front'] & 0xff, D20['thrust_front'] >> 8)
    a.label('sbf_side')
    a.b(0x5e); a.short(0xeb, 'sbf_set')
    a.label('sbf_beh')
    a.b(0xb8, BEHEADING & 0xff, BEHEADING >> 8)
    a.label('sbf_set')
    a.near(0xe8, 'set_script')                               # bx = its animation
    a.label('sbf_next')
    a.b(0x41, 0x83, 0xf9, 4 + MONSTER_COUNT); a.short(0x73, 'sbf_end'); a.near(0xe9, 'sbf_loop')   # inc cx / cmp cx, 24 / jae
    a.label('sbf_end')
    a.b(0x5f, 0x5e, 0x59, 0x5b, 0x58, 0xc3)                  # pop di si cx bx ax / ret
    # sf_clear (cx = the object's number): its note off; sab_last = the kind, sab_striker = who struck it (last_hitter)
    a.label('sbf_clear')
    a.b(0x8b, 0xd9, 0x2e, 0x8a, 0x87); a.word('sab_kind'); a.b(0x2e, 0xa2); a.word('sab_last')   # mov bx, cx / mov al, cs:[bx+sab_kind] / mov cs:[sab_last], al
    a.b(0x2e, 0xc6, 0x87); a.word('sab_kind'); a.b(0x00)
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('last_hitter'); a.b(0x2e, 0xa3); a.word('sab_striker')   # shl bx, 1 / mov ax, cs:[bx+last_hitter] / mov cs:[sab_striker], ax
    a.b(0xc3)

    # --- D52: the practice score ---
    # score_start (a fight's first frame): in a practice, its kind (score_sig); its entry (score_cur), a new one
    # (the next free, or the oldest) if none; shown if the previous practice fight was of this kind
    a.label('score_start')
    a.b(0x83, 0x3e, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION); a.short(0x74, 'd52ss_go'); a.b(0xc3)
    a.label('d52ss_go')
    a.b(0x2e, 0x80, 0x3e); a.word('bars_keep'); a.b(0x00); a.short(0x74, 'ss_nokeep')   # D57: BEATEMUP from the first menu:
    a.b(0x2e, 0xc6, 0x06); a.word('bars_on'); a.b(0x01)      # every practice fight
    a.label('ss_nokeep')
    a.b(0x50, 0x53, 0x51, 0x56, 0x57, 0x06, 0x1e)            # push ax bx cx si di es ds
    for k, name in enumerate(SCORE_SIG_LABELS):
        a.b(0x2e, 0xa0); a.word(name); a.b(0x2e, 0xa2); a.word('score_sig', k)   # mov al, cs:[name] / mov cs:[score_sig+k], al
    for k, rec in enumerate(KNIGHTS):
        a.b(0xbf, rec & 0xff, rec >> 8); a.near(0xe8, 'anim_of'); a.b(0xb0, 0xff); a.short(0x75, f'd52ss_k{k}')   # in the fight?
        a.b(0x8a, 0x65, 0x20, 0x80, 0xe4, 0x0f)              # mov ah, [di+20h] / and ah, 0Fh   its colour slot
        a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x75, f'd52ss_c{k}'); a.b(0x8a, 0xc4, 0x0c, 0x10); a.short(0xeb, f'd52ss_k{k}')   # a human's: 10h + slot
        a.label(f'd52ss_c{k}')
        a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, f'd52ss_k{k}'); a.b(0x8a, 0xc4, 0x0c, 0x20)   # the computer's: 20h + slot
        a.label(f'd52ss_k{k}')
        a.b(0x2e, 0xa2); a.word('score_sig', 8 + k)
    a.near(0xe8, 'knight_order')                             # D56: the knights from the left
    a.b(0x0e, 0x1f, 0x0e, 0x07, 0xfc)                        # push cs / pop ds / push cs / pop es / cld
    a.b(0xbe); a.word('score_sig'); a.b(0xbf); a.word('score_prev'); a.b(0xb9, SCORE_SIG, 0x00, 0xf3, 0xa6)   # repe cmpsb
    a.b(0x9c)                                                # pushf   ZF: the same kind as the previous
    a.b(0xbe); a.word('score_sig'); a.b(0xbf); a.word('score_prev'); a.b(0xb9, SCORE_SIG, 0x00, 0xf3, 0xa4)   # rep movsb
    a.b(0x33, 0xdb)                                          # xor bx, bx   the entry
    a.label('d52ss_find')
    a.b(0xb0, 0x01, 0x8a, 0xcb, 0xd2, 0xe0, 0x84, 0x06); a.word('score_used'); a.short(0x74, 'd52ss_nf')   # mov al,1 / mov cl,bl / shl al,cl / test [score_used], al / jz
    a.b(0x8a, 0xc3, 0xb4, SCORE_ENTRY, 0xf6, 0xe4, 0x05); a.word('score_tab'); a.b(0x8b, 0xf8)   # mov al,bl / mov ah,16 / mul ah / add ax, score_tab / mov di, ax
    a.b(0xbe); a.word('score_sig'); a.b(0xb9, SCORE_SIG, 0x00, 0xf3, 0xa6); a.short(0x74, 'd52ss_old')   # repe cmpsb / je
    a.label('d52ss_nf')
    a.b(0x43, 0x80, 0xfb, SCORE_KINDS); a.short(0x72, 'd52ss_find')   # inc bx / cmp bl, 8 / jb
    for_free = 'd52ss_free'
    a.b(0x33, 0xdb)                                          # xor bx, bx   a free one
    a.label(for_free)
    a.b(0xb0, 0x01, 0x8a, 0xcb, 0xd2, 0xe0, 0x84, 0x06); a.word('score_used'); a.short(0x74, 'd52ss_take')
    a.b(0x43, 0x80, 0xfb, SCORE_KINDS); a.short(0x72, for_free)
    a.b(0x8a, 0x1e); a.word('score_next'); a.b(0xfe, 0x06); a.word('score_next')   # mov bl, [score_next] / inc [score_next]
    a.b(0x80, 0x26); a.word('score_next'); a.b(SCORE_KINDS - 1)   # and [score_next], 7
    a.label('d52ss_take')
    a.b(0xb0, 0x01, 0x8a, 0xcb, 0xd2, 0xe0, 0x08, 0x06); a.word('score_used')   # its bit on
    a.b(0x8a, 0xc3, 0xb4, SCORE_ENTRY, 0xf6, 0xe4, 0x05); a.word('score_tab'); a.b(0x8b, 0xf8)   # di = the entry
    a.b(0xbe); a.word('score_sig'); a.b(0xb9, SCORE_SIG, 0x00, 0xf3, 0xa4)   # the kind
    a.b(0x33, 0xc0, 0xab, 0xab)                              # xor ax, ax / stosw / stosw   no wins yet
    a.b(0x32, 0xff); a.short(0xeb, 'd52ss_found')            # xor bh, bh   a new kind: not shown
    a.label('d52ss_old')
    a.b(0xb7, 0x01)                                          # mov bh, 1   played before (D56): shown
    a.label('d52ss_found')
    a.b(0x88, 0x1e); a.word('score_cur')                     # mov [score_cur], bl
    a.b(0xc6, 0x06); a.word('score_won'); a.b(0x00, 0xc6, 0x06); a.word('score_saved'); a.b(0x00)   # D56
    a.b(0xc6, 0x06); a.word('score_live'); a.b(0x00)
    a.b(0xc7, 0x06); a.word('score_col'); a.b(0xff, 0xff, 0xc7, 0x06); a.word('score_col', 2); a.b(0xff, 0xff)
    a.b(0xc6, 0x06); a.word('score_pend'); a.b(0x00)
    a.b(0x80, 0x3e); a.word('bars_on'); a.b(0x00); a.short(0x74, 'ss_nobars'); a.b(0xb7, 0x01)   # D57: with BEATEMUP always shown
    a.label('ss_nobars')
    a.b(0x9d, 0x0a, 0xff); a.short(0x74, 'd52ss_pop')        # popf / or bh, bh / jz   (D56: not the previous kind only)
    a.b(0xc6, 0x06); a.word('score_pend'); a.b(0x01)
    a.b(0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x2e, 0xa3); a.word('score_t0')   # ds = 0 / mov ax, [046Ch] / mov cs:[score_t0], ax
    a.label('d52ss_pop')
    a.b(0x1f, 0x07, 0x5f, 0x5e, 0x59, 0x5b, 0x58, 0xc3)      # pop ds es di si cx bx ax / ret
    # score_frame (every fight frame): shown once every human knight's colour is seen, or after SCORE_WAIT ticks
    # score_settled (D56, D57; at pf_cmp, the practice frame's end, after its own rules set [897Dh]: the game sets it
    # as a knight falls even when the practice goes on, 1 vs 1 vs 1 or co-op): as the end begins the winner is
    # counted and the score drawn (again) at once. Keeps the flags
    a.label('score_settled')
    a.b(0x9c)                                                # pushf
    a.b(0x83, 0x3e, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION); a.short(0x75, 'sfw_no')
    a.b(0x80, 0x3e, GAME_ENDING & 0xff, GAME_ENDING >> 8, 0x00); a.short(0x74, 'sfw_end')
    a.b(0x2e, 0xc6, 0x06); a.word('score_live'); a.b(0x01); a.short(0xeb, 'sfw_no')   # the fight goes on
    a.label('sfw_end')
    a.b(0x2e, 0x80, 0x3e); a.word('score_live'); a.b(0x00); a.short(0x74, 'sfw_no')   # an end only after it went on
    a.b(0x2e, 0x80, 0x3e); a.word('score_won'); a.b(0x00); a.short(0x75, 'sfw_no')
    a.near(0xe8, 'score_count')
    a.b(0x2e, 0x80, 0x3e); a.word('score_won'); a.b(0x00); a.short(0x74, 'sfw_no')   # not counted (Esc)
    a.b(0x2e, 0xc6, 0x06); a.word('score_pend'); a.b(0x00); a.near(0xe8, 'score_draw')
    a.label('sfw_no')
    a.b(0x9d, 0xc3)                                          # popf / ret
    a.label('score_frame')
    a.b(0x2e, 0x80, 0x3e); a.word('score_pend'); a.b(0x00); a.short(0x75, 'd52sfr_go'); a.b(0xc3)
    a.label('d52sfr_go')
    a.b(0x50, 0x53)                                          # push ax bx
    a.b(0x33, 0xdb)                                          # xor bx, bx
    a.label('d52sfr_k')
    a.b(0x2e, 0x8a, 0x87); a.word('score_sig', 8); a.b(0x24, 0xf0, 0x3c, 0x10); a.short(0x75, 'd52sfr_n')   # a human's knight in it?
    a.b(0x2e, 0x80, 0xbf); a.word('score_col'); a.b(0xff); a.short(0x74, 'd52sfr_wait')   # its colour not seen yet
    a.label('d52sfr_n')
    a.b(0x43, 0x83, 0xfb, 0x04); a.short(0x72, 'd52sfr_k')      # inc bx / cmp bx, 4 / jb
    a.short(0xeb, 'd52sfr_draw')
    a.label('d52sfr_wait')
    a.b(0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f)   # push ds / ds = 0 / mov ax, [046Ch] / pop ds
    a.b(0x2e, 0x2b, 0x06); a.word('score_t0'); a.b(0x3d, SCORE_WAIT, 0x00); a.short(0x72, 'd52sfr_pop')
    a.label('d52sfr_draw')
    a.b(0x2e, 0xc6, 0x06); a.word('score_pend'); a.b(0x00)
    a.near(0xe8, 'score_draw')
    a.label('d52sfr_pop')
    a.b(0x5b, 0x58, 0xc3)                                    # pop bx ax / ret
    # score_colour (from draw, di = the animation; recolour, rc_shift as it is drawn): a knight's pixel 7 as drawn
    a.label('score_colour')
    a.b(0x2e, 0x80, 0x3e); a.word('score_pend'); a.b(0x00); a.short(0x75, 'd52scc_go')
    a.b(0x2e, 0x80, 0x3e); a.word('bars_on'); a.b(0x00); a.short(0x75, 'd52scc_go'); a.b(0xc3)   # D54: the bars too
    a.label('d52scc_go')
    a.b(0x50, 0x53, 0x8b, 0x5d, 0x16)                        # push ax bx / mov bx, [di+16h]
    a.b(0x81, 0xfb, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'd52scc_pop')
    a.b(0x81, 0xfb, KNIGHTS[3] & 0xff, KNIGHTS[3] >> 8); a.short(0x77, 'd52scc_pop')
    a.b(0x57, 0x8b, 0xfb); a.near(0xe8, 'knight_slot'); a.b(0x5f, 0xd1, 0xeb)   # push di / mov di, bx / call knight_slot / pop di / shr bx, 1
    a.b(0x2e, 0x80, 0xbf); a.word('score_col'); a.b(0xff); a.short(0x75, 'd52scc_pop')   # seen already
    a.b(0x2e, 0xa0); a.word('recolour'); a.b(0x0a, 0xc0); a.short(0x74, 'd52scc_native')
    a.b(0xfe, 0xc0, 0x2e, 0x02, 0x06); a.word('rc_shift'); a.short(0xeb, 'd52scc_set')   # inc al / add al, cs:[rc_shift]
    a.label('d52scc_native')
    a.b(0xb0, 0x07, 0x81, 0x7d, 0x18, HE_BANK & 0xff, HE_BANK >> 8); a.short(0x75, 'd52scc_set'); a.b(0xb0, 0x0a)   # 7, the HE look's 10
    a.label('d52scc_set')
    a.b(0x2e, 0x88, 0x87); a.word('score_col')
    a.label('d52scc_pop')
    a.b(0x5b, 0x58, 0xc3)
    # score_kind (si = an entry): ZF = 0 when the fight has a computer side
    a.label('score_kind')
    a.b(0x50)
    for k in SCORE_COMPUTER:
        a.b(0x2e, 0x80, 0x7c, k, 0x00); a.short(0x75, 'd52sk2_end')   # cmp byte cs:[si+k], 0 / jne
    for k in range(4):
        a.b(0x2e, 0x8a, 0x44, 8 + k, 0x24, 0xf0, 0x3c, 0x20); a.short(0x74, 'd52sk2_comp')   # mov al, cs:[si+8+k] / and al, 0F0h / cmp al, 20h / je
    a.b(0x32, 0xc0); a.short(0xeb, 'd52sk2_end')                # xor al, al   ZF = 1
    a.label('d52sk2_comp')
    a.b(0x0c, 0x01)                                          # or al, 1   ZF = 0
    a.label('d52sk2_end')
    a.b(0x58, 0xc3)
    # score_entry: si = score_cur's entry
    a.label('score_entry')
    a.b(0x50, 0x2e, 0xa0); a.word('score_cur'); a.b(0xb4, SCORE_ENTRY, 0xf6, 0xe4, 0x05); a.word('score_tab'); a.b(0x8b, 0xf0, 0x58, 0xc3)
    # score_end (from cheat_fight_end): a practice fight not ended by Esc: its winner counted (at most 99): the
    # players' side if a human's knight stands, else the computer's; without a computer side each human's knight standing
    a.label('score_end')
    a.b(0x83, 0x3e, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION); a.short(0x74, 'd52se_p'); a.b(0xc3)
    a.label('d52se_p')
    a.b(0x2e, 0x80, 0x3e); a.word('score_cur'); a.b(0xff); a.short(0x75, 'd52se_go'); a.b(0xc3)
    a.label('d52se_go')
    a.near(0xe8, 'score_count')                              # D56: unless counted already
    a.b(0x2e, 0xc6, 0x06); a.word('score_cur'); a.b(0xff, 0x2e, 0xc6, 0x06); a.word('score_pend'); a.b(0x00)
    a.b(0xc3)
    # score_count (D56): the winner counted once a fight (score_won), not after Esc (score_cur valid)
    a.label('score_count')
    a.b(0x2e, 0x80, 0x3e); a.word('score_cur'); a.b(0xff); a.short(0x75, 'scn_cur'); a.b(0xc3)
    a.label('scn_cur')
    a.b(0x2e, 0x80, 0x3e); a.word('score_won'); a.b(0x00); a.short(0x74, 'scn_go'); a.b(0xc3)
    a.label('scn_go')
    a.b(0x50, 0x53, 0x51, 0x56)                              # push ax bx cx si
    a.b(0x2e, 0x80, 0x3e); a.word('quitting'); a.b(0x00); a.short(0x74, 'd52se_count'); a.near(0xe9, 'd52se_done')
    a.label('d52se_count')
    a.b(0x2e, 0xc6, 0x06); a.word('score_won'); a.b(0x01)
    a.near(0xe8, 'score_entry'); a.b(0x32, 0xc9)             # xor cl, cl   human knights standing
    for k, rec in enumerate(KNIGHTS):
        a.b(0x2e, 0x8a, 0x44, 8 + k, 0x24, 0xf0, 0x3c, 0x10); a.short(0x75, f'd52se_n{k}')   # a human's knight in it?
        a.b(0x83, 0x3e, (rec + 0x38) & 0xff, (rec + 0x38) >> 8, 0x00); a.short(0x7e, f'd52se_n{k}')   # cmp word [rec+38h], 0 / jle
        a.b(0xfe, 0xc1)                                      # inc cl
        a.near(0xe8, 'score_kind'); a.short(0x75, f'd52se_n{k}')   # a computer side: counted below
        a.b(0x2e, 0x80, 0x7c, SCORE_SIG + k, SCORE_MAX); a.short(0x73, f'd52se_n{k}')   # cmp byte cs:[si+12+k], 99 / jae
        a.b(0x2e, 0xfe, 0x44, SCORE_SIG + k)                 # inc byte cs:[si+12+k]
        a.label(f'd52se_n{k}')
    a.near(0xe8, 'score_kind'); a.short(0x74, 'd52se_done')     # no computer side: done
    a.b(0xbb, SCORE_SIG + 1, 0x00, 0x0a, 0xc9); a.short(0x75, 'd52se_side'); a.b(0x4b)   # mov bx, 13 (the players) / or cl, cl / jnz / dec bx (the computer)
    a.label('d52se_side')
    a.b(0x2e, 0x80, 0x38, SCORE_MAX); a.short(0x73, 'd52se_done')   # cmp byte cs:[bx+si], 99 / jae
    a.b(0x2e, 0xfe, 0x00)                                    # inc byte cs:[bx+si]
    a.label('d52se_done')
    a.b(0x5e, 0x59, 0x5b, 0x58, 0xc3)                        # pop si cx bx ax / ret
    # score_reset: every kind's wins gone (Select Knight)
    a.label('score_reset')
    a.b(0x50, 0x51, 0x57, 0x06, 0x0e, 0x07, 0xfc)            # push ax cx di es / push cs / pop es / cld
    a.b(0xbf); a.word('score_tab'); a.b(0xb9, SCORE_KINDS * SCORE_ENTRY + 2, 0x00, 0x32, 0xc0, 0xf3, 0xaa)   # the table, score_used, score_next
    a.b(0xbf); a.word('score_prev'); a.b(0xb9, SCORE_SIG, 0x00, 0xb0, 0xff, 0xf3, 0xaa)   # no previous kind
    a.b(0x2e, 0xc6, 0x06); a.word('score_cur'); a.b(0xff, 0x2e, 0xc6, 0x06); a.word('score_pend'); a.b(0x00)
    a.b(0x07, 0x5f, 0x59, 0x58, 0xc3)
    # score_text: score_txt for score_cur's entry: the computer's - the players' (one human's knight: in its colour),
    # or each human's knight's wins in its colour, with " - " between
    a.label('score_text')
    a.b(0x50, 0x53, 0x51, 0x56, 0x57)
    a.near(0xe8, 'score_entry'); a.b(0xbf); a.word('score_txt')
    a.near(0xe8, 'score_kind'); a.short(0x75, 'd52st_comp'); a.near(0xe9, 'd52st_knights')
    a.label('d52st_comp')
    a.near(0xe8, 'comp_colour'); a.b(0x2e, 0x8a, 0x44, SCORE_SIG); a.near(0xe8, 'd52st_num')   # the computer's wins (D56: its colour)
    a.near(0xe8, 'd52st_dash')
    a.b(0xb4, SCORE_WHITE, 0x32, 0xc9, 0x33, 0xdb)           # mov ah, white / xor cl, cl (humans) / xor bx, bx
    a.label('d52st_hk')
    a.b(0x2e, 0x8a, 0x40, 8, 0x24, 0xf0, 0x3c, 0x10); a.short(0x75, 'd52st_hn')   # mov al, cs:[bx+si+8] / and al, F0h / cmp al, 10h / jne
    a.b(0xfe, 0xc1, 0x2e, 0x8a, 0xa7); a.word('score_col')   # inc cl / mov ah, cs:[bx+score_col]
    a.label('d52st_hn')
    a.b(0x43, 0x83, 0xfb, 0x04); a.short(0x72, 'd52st_hk')      # inc bx / cmp bx, 4 / jb
    a.b(0x80, 0xf9, 0x01); a.short(0x74, 'd52st_one'); a.b(0xb4, SCORE_WHITE)   # cmp cl, 1 / je / mov ah, white
    a.label('d52st_one')
    a.b(0x80, 0xfc, 0xff); a.short(0x75, 'd52st_pl'); a.b(0xb4, SCORE_WHITE)   # not seen: white
    a.label('d52st_pl')
    a.b(0x2e, 0x8a, 0x44, SCORE_SIG + 1); a.near(0xe8, 'd52st_num')   # the players' wins
    a.near(0xe9, 'd52st_end')
    a.label('d52st_knights')
    a.b(0x33, 0xc9)                                          # xor cx, cx   cl: none written yet, ch: the place (D56)
    a.label('d52st_k')
    a.b(0x8a, 0xdd, 0x32, 0xff, 0x2e, 0x8a, 0x9f); a.word('score_ord')   # mov bl, ch / xor bh, bh / mov bl, cs:[bx+score_ord]
    a.b(0x80, 0xfb, 0xff); a.short(0x74, 'd52st_kn')         # cmp bl, FFh / je
    a.b(0x2e, 0x8a, 0x40, 8, 0x24, 0xf0, 0x3c, 0x10); a.short(0x75, 'd52st_kn')   # a human's knight in it?
    a.b(0x0a, 0xc9); a.short(0x74, 'd52st_first'); a.near(0xe8, 'd52st_dash')
    a.label('d52st_first')
    a.b(0xb1, 0x01, 0x2e, 0x8a, 0xa7); a.word('score_col')   # mov cl, 1 / mov ah, cs:[bx+score_col]
    a.b(0x80, 0xfc, 0xff); a.short(0x75, 'd52st_kc'); a.b(0xb4, SCORE_WHITE)
    a.label('d52st_kc')
    a.b(0x2e, 0x8a, 0x40, SCORE_SIG); a.near(0xe8, 'd52st_num')   # mov al, cs:[bx+si+12] / its wins
    a.label('d52st_kn')
    a.b(0xfe, 0xc5, 0x80, 0xfd, 0x04); a.short(0x72, 'd52st_k')   # inc ch / cmp ch, 4 / jb
    a.label('d52st_end')
    a.b(0x2e, 0xc6, 0x05, 0xff)                              # mov byte cs:[di], FFh
    a.b(0x5f, 0x5e, 0x59, 0x5b, 0x58, 0xc3)
    a.label('d52st_num')                                        # al = a number (0-99), ah = its colour -> cs:[di]
    a.b(0x53, 0x51, 0x8a, 0xdc)                              # push bx cx / mov bl, ah   the colour
    a.b(0x3c, 0x0a); a.short(0x72, 'd52stn_one')                # cmp al, 10 / jb
    a.b(0x32, 0xe4, 0xb1, 0x0a, 0xf6, 0xf1)                  # xor ah, ah / mov cl, 10 / div cl   al tens, ah ones
    a.b(0x2e, 0x88, 0x05, 0x2e, 0x88, 0x5d, 0x01, 0x83, 0xc7, 0x02, 0x8a, 0xc4)   # the tens / mov al, ah
    a.label('d52stn_one')
    a.b(0x2e, 0x88, 0x05, 0x2e, 0x88, 0x5d, 0x01, 0x83, 0xc7, 0x02)   # mov cs:[di], al / mov cs:[di+1], bl / add di, 2
    a.b(0x59, 0x5b, 0xc3)                                    # pop cx bx / ret
    a.label('d52st_dash')                                       # " - " in white
    a.b(0x2e, 0xc7, 0x05, SCORE_SPACE, SCORE_WHITE, 0x2e, 0xc7, 0x45, 0x02, 10, SCORE_WHITE)
    a.b(0x2e, 0xc7, 0x45, 0x04, SCORE_SPACE, SCORE_WHITE, 0x83, 0xc7, 0x06, 0xc3)   # ... / add di, 6 / ret
    # score_draw: score_txt into the background page at the top centre, each glyph doubled with a black shadow
    a.label('score_draw')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x55, 0x06)      # push ax bx cx dx si di bp es
    a.b(0xb8, MINE_BG_PAGE & 0xff, MINE_BG_PAGE >> 8, 0x8e, 0xc0)   # D56: es = the background page
    a.near(0xe8, 'vga_keep')
    a.b(0x2e, 0xa0); a.word('score_saved'); a.b(0x2e, 0xa2); a.word('box_mode')   # 0 the first time: keep it; else put it back
    a.near(0xe8, 'score_box'); a.b(0x2e, 0xc6, 0x06); a.word('score_saved'); a.b(0x01)
    a.near(0xe8, 'vga_back')
    a.near(0xe8, 'score_text')
    a.b(0xbe); a.word('score_txt'); a.b(0x33, 0xdb)          # mov si, score_txt / xor bx, bx   the width
    a.label('d52sd_w')
    a.b(0x2e, 0x8a, 0x04, 0x3c, 0xff); a.short(0x74, 'd52sd_wend')   # mov al, cs:[si] / cmp al, FFh / je
    a.b(0x83, 0xc3, 0x08, 0x3c, SCORE_SPACE); a.short(0x75, 'd52sd_wn'); a.b(0x83, 0xeb, 0x04)   # add bx, 8 / cmp al, 11 / jne / sub bx, 4
    a.label('d52sd_wn')
    a.b(0x46, 0x46); a.short(0xeb, 'd52sd_w')
    a.label('d52sd_wend')
    a.b(0x4b, 0x4b, 0xd1, 0xeb, 0xb9, 0xa0, 0x00, 0x2b, 0xcb)   # dec bx (x2) / shr bx, 1 / mov cx, 160 / sub cx, bx   x
    a.b(0xb8, MINE_BG_PAGE & 0xff, MINE_BG_PAGE >> 8, 0x8e, 0xc0)   # es = the background page
    a.near(0xe8, 'vga_keep')
    a.b(0xbf); a.word('score_txt')
    a.label('d52sd_g')
    a.b(0x2e, 0x8a, 0x05, 0x3c, 0xff); a.short(0x74, 'd52sd_end')   # mov al, cs:[di] / cmp al, FFh / je
    a.b(0x3c, SCORE_SPACE); a.short(0x75, 'd52sd_glyph'); a.b(0x83, 0xc1, 0x04); a.short(0xeb, 'd52sd_next')
    a.label('d52sd_glyph')
    a.b(0x32, 0xe4, 0xb3, 0x05, 0xf6, 0xe3, 0x05); a.word('score_font'); a.b(0x8b, 0xf0)   # xor ah,ah / mov bl,5 / mul bl / add ax, score_font / mov si, ax
    a.b(0xba, SCORE_Y + 1, 0x00, 0x41, 0xb0, SCORE_SHADOW); a.near(0xe8, 'sp_glyph'); a.b(0x49)   # the shadow, 1 right and down
    a.b(0xba, SCORE_Y, 0x00, 0x2e, 0x8a, 0x45, 0x01); a.near(0xe8, 'sp_glyph')   # mov dx, y / mov al, cs:[di+1]
    a.b(0x83, 0xc1, 0x08)                                    # add cx, 8
    a.label('d52sd_next')
    a.b(0x47, 0x47); a.short(0xeb, 'd52sd_g')
    a.label('d52sd_end')
    a.near(0xe8, 'vga_back')
    a.b(0x07, 0x5d, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)
    # sp_glyph: cs:si = a glyph's five rows (bits 2-0), cx = x, dx = y, al = colour: each pixel a 2 x 2 block
    a.label('sp_glyph')
    a.b(0x53, 0x51, 0x52, 0x56, 0x55, 0xbd, 0x05, 0x00)      # push bx cx dx si bp / mov bp, 5
    a.label('d52spg_row')
    a.b(0x2e, 0x8a, 0x1c, 0x51, 0xb7, 0x03)                  # mov bl, cs:[si] / push cx / mov bh, 3
    a.label('d52spg_col')
    a.b(0xf6, 0xc3, 0x04); a.short(0x74, 'd52spg_skip')         # test bl, 4 / jz
    a.near(0xe8, 'sp_plot'); a.b(0x41); a.near(0xe8, 'sp_plot'); a.b(0x42); a.near(0xe8, 'sp_plot'); a.b(0x49); a.near(0xe8, 'sp_plot'); a.b(0x4a)
    a.label('d52spg_skip')
    a.b(0xd0, 0xe3, 0x83, 0xc1, 0x02, 0xfe, 0xcf); a.short(0x75, 'd52spg_col')   # shl bl, 1 / add cx, 2 / dec bh / jnz
    a.b(0x59, 0x46, 0x83, 0xc2, 0x02, 0x4d); a.short(0x75, 'd52spg_row')   # pop cx / inc si / add dx, 2 / dec bp / jnz
    a.b(0x5d, 0x5e, 0x5a, 0x59, 0x5b, 0xc3)
    # sp_plot: cx = x, dx = y, al = colour into es (unchained, 80 bytes a line; write mode 0 set by vga_keep)
    a.label('sp_plot')
    a.b(0x81, 0xf9, 0x40, 0x01); a.short(0x73, 'd52spp_ret')    # cmp cx, 320 / jae
    a.b(0x81, 0xfa, 0xc8, 0x00); a.short(0x73, 'd52spp_ret')    # cmp dx, 200 / jae
    a.b(0x50, 0x53, 0x51, 0x52, 0x57)                        # push ax bx cx dx di
    a.b(0x8b, 0xfa, 0xd1, 0xe7, 0xd1, 0xe7, 0x03, 0xfa)      # mov di, dx / shl di, 1 (x2) / add di, dx   5y
    a.b(0xd1, 0xe7, 0xd1, 0xe7, 0xd1, 0xe7, 0xd1, 0xe7)      # shl di, 1 (x4)   80y
    a.b(0x8b, 0xd9, 0xd1, 0xeb, 0xd1, 0xeb, 0x03, 0xfb)      # mov bx, cx / shr bx, 1 (x2) / add di, bx
    a.b(0x80, 0xe1, 0x03, 0xb4, 0x01, 0xd2, 0xe4)            # and cl, 3 / mov ah, 1 / shl ah, cl
    a.b(0x50, 0xba, 0xc4, 0x03, 0xb0, 0x02, 0xef, 0x58)      # push ax / mov dx, 3C4h / mov al, 2 / out dx, ax / pop ax
    a.b(0x26, 0x88, 0x05)                                    # mov es:[di], al
    a.b(0x5f, 0x5a, 0x59, 0x5b, 0x58)
    a.label('d52spp_ret')
    a.b(0xc3)
    # vga_keep / vga_back: the VGA registers sp_plot changes kept on the stack (under the caller's return) and set
    # back; vga_keep sets write mode 0, bit mask FFh, set/reset off
    a.label('vga_keep')
    a.b(0x5e)                                                # pop si   the return
    a.b(0xba, 0xc4, 0x03, 0xec, 0x50)                        # mov dx, 3C4h / in al, dx / push ax
    a.b(0xb0, 0x02, 0xee, 0x42, 0xec, 0x50, 0x4a)            # map mask
    a.b(0xb2, 0xce, 0xec, 0x50)                              # graphics index
    for idx in (1, 4, 5, 8):                                 # (D56: the read map too)
        a.b(0xb0, idx, 0xee, 0x42, 0xec, 0x50, 0x4a)
    a.b(0xb8, 0x01, 0x00, 0xef, 0xb8, 0x08, 0xff, 0xef)      # set/reset off / bit mask FFh
    a.b(0xb0, 0x05, 0xee, 0x42, 0xec, 0x24, 0xf4, 0xee, 0x4a)   # write mode 0
    a.b(0xff, 0xe6)                                          # jmp si
    a.label('vga_back')
    a.b(0x5e, 0xba, 0xce, 0x03)                              # pop si / mov dx, 3CEh
    for idx in (8, 5, 4, 1):
        a.b(0x58, 0x8a, 0xe0, 0xb0, idx, 0xef)
    a.b(0x58, 0xee, 0xb2, 0xc4)
    a.b(0x58, 0x8a, 0xe0, 0xb0, 0x02, 0xef, 0x58, 0xee)
    a.b(0xff, 0xe6)                                          # jmp si

    # choose_keys (D53; 1000:15B5, test bx,10h in ChooseLoop, the Select Knight screen): the practice scores are
    # cleared (a new campaign); Esc goes back to the first menu: ChooseFINI's end (1627: the screen's list, a fade),
    # then StartAgain (00A8) instead of the campaign's set-up (ChooseKnight's return, 00D6, the game's stack top)
    a.label('rules_choose_keys')
    a.near(0xe8, 'score_reset')
    a.b(0x06, 0x8e, 0x46, 0x04, 0x26, 0x80, 0x3e, (KEY_TABLE + ESC) & 0xff, (KEY_TABLE + ESC) >> 8, 0xff, 0x07)   # push es / mov es, [bp+4] / cmp byte es:[81E4h], FFh / pop es
    a.short(0x74, 'd52chk_play')                                # je   Esc not held
    a.b(0x06, 0x8e, 0x46, 0x04, 0x26, 0xc6, 0x06, (KEY_TABLE + ESC) & 0xff, (KEY_TABLE + ESC) >> 8, 0xff, 0x07)   # Esc taken (let go)
    a.b(0xc7, 0x46, 0x02, 0x27, 0x16, 0xc7, 0x46, 0x08, 0xa8, 0x00)   # mov word [bp+2], 1627h / mov word [bp+8], 00A8h
    a.near(0xe9, 'rules_done')
    a.label('d52chk_play')
    a.b(0xf7, 0x46, 0xfe, 0x10, 0x00)                        # test word [bp-2], 10h   (replaced)
    a.near(0xe9, 'rules_flags')

    # --- D54: BEATEMUP, the HP bars ---
    # bars_frame (every fight frame from the first's set-up on): laid out once; a bar whose length or colour changed is
    # drawn again (into the background page, as the score)
    a.label('bars_frame')
    a.b(0x2e, 0x80, 0x3e); a.word('bars_on'); a.b(0x00); a.short(0x75, 'brf_go'); a.b(0xc3)
    a.label('brf_go')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x55, 0x06)      # push ax bx cx dx si di bp es
    a.b(0x2e, 0x80, 0x3e); a.word('bars_n'); a.b(0x00); a.short(0x75, 'brf_have')
    a.near(0xe8, 'bars_layout')
    a.b(0x2e, 0x80, 0x3e); a.word('bars_n'); a.b(0x00); a.short(0x75, 'brf_have'); a.near(0xe9, 'brf_out')
    a.label('brf_have')
    a.b(0xb8, MINE_BG_PAGE & 0xff, MINE_BG_PAGE >> 8, 0x8e, 0xc0)   # es = the background page
    a.near(0xe8, 'vga_keep')
    a.b(0x33, 0xdb)                                          # xor bx, bx   the bar
    a.label('brf_bar')
    a.near(0xe8, 'bars_value')                               # ax = left, cx = full, dl = colour
    a.b(0x52, 0x8b, 0xf1, 0x0b, 0xf6); a.short(0x74, 'brf_zero')   # push dx / mov si, cx / or si, si / jz
    a.b(0x3b, 0xc1); a.short(0x76, 'brf_ok'); a.b(0x8b, 0xc1)   # cmp ax, cx / jbe / mov ax, cx
    a.label('brf_ok')
    a.b(0x2e, 0xf7, 0x26); a.word('bars_w'); a.b(0xf7, 0xf6); a.short(0xeb, 'brf_got')   # mul word cs:[bars_w] / div si
    a.label('brf_zero')
    a.b(0x33, 0xc0)
    a.label('brf_got')
    a.b(0x5a, 0x8b, 0xfb, 0xd1, 0xe7)                        # pop dx / mov di, bx / shl di, 1
    a.b(0x2e, 0x3b, 0x85); a.word('bars_len'); a.short(0x75, 'brf_draw')   # cmp ax, cs:[di+bars_len] / jne
    a.b(0x2e, 0x3a, 0x97); a.word('bars_col'); a.short(0x74, 'brf_next')   # cmp dl, cs:[bx+bars_col] / je
    a.label('brf_draw')
    a.b(0x2e, 0x89, 0x85); a.word('bars_len'); a.b(0x2e, 0x88, 0x97); a.word('bars_col')   # the new length, colour
    a.b(0x50, 0x2e, 0x8b, 0x8d); a.word('bars_x'); a.b(0x8b, 0xf0, 0x8a, 0xc2); a.near(0xe8, 'bars_rect')   # push ax / mov cx, x / mov si, ax / mov al, dl / filled
    a.b(0x58, 0x2e, 0x8b, 0x8d); a.word('bars_x'); a.b(0x03, 0xc8)   # pop ax / mov cx, x / add cx, ax
    a.b(0x2e, 0x8b, 0x36); a.word('bars_w'); a.b(0x2b, 0xf0, 0xb0, BARS_EMPTY); a.near(0xe8, 'bars_rect')   # mov si, w / sub si, ax / the rest black
    a.label('brf_next')
    a.b(0x43, 0x2e, 0x3a, 0x1e); a.word('bars_n'); a.short(0x73, 'brf_end'); a.near(0xe9, 'brf_bar')   # inc bx / cmp bl, cs:[bars_n] / jae
    a.label('brf_end')
    a.near(0xe8, 'vga_back')
    a.label('brf_out')
    a.b(0x07, 0x5d, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)   # pop es bp di si dx cx bx ax / ret
    # bars_rect: cx = x, si = width, al = colour: BARS_H rows from bars_y (es = the page, the VGA set by vga_keep)
    a.label('bars_rect')
    a.b(0x53, 0x51, 0x52, 0x56, 0x55, 0x0b, 0xf6); a.short(0x74, 'brr_end')   # push bx cx dx si bp / or si, si / jz
    a.b(0x2e, 0x8b, 0x16); a.word('bars_y'); a.b(0xbd, BARS_H, 0x00)   # mov dx, cs:[bars_y] / mov bp, 4
    a.label('brr_row')
    a.b(0x51, 0x8b, 0xde)                                    # push cx / mov bx, si
    a.label('brr_col')
    a.near(0xe8, 'sp_plot'); a.b(0x41, 0x4b); a.short(0x75, 'brr_col')   # inc cx / dec bx / jnz
    a.b(0x59, 0x42, 0x4d); a.short(0x75, 'brr_row')          # pop cx / inc dx / dec bp / jnz
    a.label('brr_end')
    a.b(0x5d, 0x5e, 0x5a, 0x59, 0x5b, 0xc3)
    # bars_layout (the first frame): who is in the fight; the bars, their width and places; below the score if it shows
    a.label('bars_layout')
    a.near(0xe8, 'knight_order')                             # D56: the knights from the left as they start
    a.b(0x2e, 0xc7, 0x06); a.word('score_col'); a.b(0xff, 0xff, 0x2e, 0xc7, 0x06); a.word('score_col', 2); a.b(0xff, 0xff)   # colours as drawn from now
    a.b(0x2e, 0xc7, 0x06); a.word('bars_full'); a.b(0x00, 0x00, 0x2e, 0xc7, 0x06); a.word('bars_top'); a.b(0x00, 0x00)
    a.b(0x32, 0xd2, 0x32, 0xf6, 0x33, 0xdb)                  # xor dl, dl (humans) / xor dh, dh (computer's records) / xor bx, bx
    for k, rec in enumerate(KNIGHTS):
        a.b(0xbf, rec & 0xff, rec >> 8); a.near(0xe8, 'anim_of'); a.short(0x75, f'bl_k{k}')   # in the fight?
        a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x75, f'bl_c{k}'); a.b(0x80, 0xca, 1 << k); a.short(0xeb, f'bl_k{k}')   # a human's
        a.label(f'bl_c{k}')
        a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, f'bl_k{k}'); a.b(0x80, 0xce, 1 << k)   # the computer's
        a.label(f'bl_k{k}')
    a.b(0x2e, 0x88, 0x16); a.word('bars_hum'); a.b(0x2e, 0x88, 0x36); a.word('bars_crec')
    a.b(0xbf, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8); a.near(0xe8, 'anim_of'); a.b(0xb0, 0x00); a.short(0x75, 'bl_nd'); a.b(0xb0, 0x01)
    a.label('bl_nd')
    a.b(0x2e, 0xa2); a.word('bars_drag')
    # a computer's side: its knight records, the dragon, monsters to come or on the screen, a monster in a slot
    a.b(0x33, 0xdb)                                          # xor bx, bx   the bars (anim_of used bx)
    a.b(0x2e, 0x80, 0x3e); a.word('score_cur'); a.b(0xff); a.short(0x74, 'bl_campaign')   # D59: a practice:
    a.b(0x56); a.near(0xe8, 'score_entry'); a.near(0xe8, 'score_kind'); a.b(0x5e)   # push si / its kind / pop si
    a.short(0x74, 'bl_humans_j'); a.short(0xeb, 'bl_comp')   # no computer's side: none
    a.label('bl_humans_j')
    a.near(0xe9, 'bl_humans')
    a.label('bl_campaign')
    a.b(0x0a, 0xf0); a.short(0x75, 'bl_comp')                # or dh, al / jnz
    a.b(0x83, 0x3e, 0x6a, 0x09, 0x00); a.short(0x75, 'bl_comp')   # cmp word [096Ah], 0 / jne
    a.b(0x83, 0x3e, 0x6e, 0x09, 0x00); a.short(0x75, 'bl_comp')
    a.b(0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00)
    a.label('bl_slot')
    a.b(0x83, 0x3d, 0x00); a.short(0x74, 'bl_sn'); a.b(0x8a, 0x45, 0x35)   # cmp word [di], 0 / je / mov al, [di+35h]
    for t in BARS_COMP:
        a.b(0x3c, t); a.short(0x74, 'bl_comp')
    a.label('bl_sn')
    a.b(0x83, 0xc7, SLOT_SIZE); a.short(0xe2, 'bl_slot')
    a.short(0xeb, 'bl_humans')
    a.label('bl_comp')
    a.b(0x2e, 0xc6, 0x87); a.word('bars_who'); a.b(BARS_COMP_SIDE, 0x43)   # mov byte cs:[bx+bars_who], FEh / inc bx
    a.label('bl_humans')
    a.b(0x2e, 0x80, 0x3e); a.word('teams'); a.b(0x00); a.short(0x74, 'bl_each')   # teams (D12): the two teams
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00); a.short(0x74, 'bl_each')
    a.b(0x2e, 0xc7, 0x06); a.word('bars_who'); a.b(BARS_TEAM, BARS_TEAM + 1); a.b(0xbb, 0x02, 0x00); a.short(0xeb, 'bl_n')
    a.label('bl_each')
    a.b(0x33, 0xf6)                                          # xor si, si   the place from the left (D56)
    a.label('bl_h')
    a.b(0x2e, 0x8a, 0x84); a.word('score_ord'); a.b(0x3c, 0xff); a.short(0x74, 'bl_hn')   # mov al, cs:[si+score_ord] / cmp al, FFh / je
    a.b(0x51, 0x8a, 0xc8, 0xb4, 0x01, 0xd2, 0xe4, 0x59, 0x84, 0xe2); a.short(0x74, 'bl_hn')   # push cx / mov cl, al / mov ah, 1 / shl ah, cl / pop cx / test dl, ah / jz
    a.b(0x2e, 0x88, 0x87); a.word('bars_who'); a.b(0x43)     # mov cs:[bx+bars_who], al / inc bx
    a.label('bl_hn')
    a.b(0x46, 0x83, 0xfe, 0x04); a.short(0x72, 'bl_h')       # inc si / cmp si, 4 / jb
    a.label('bl_n')
    a.b(0x2e, 0x88, 0x1e); a.word('bars_n'); a.b(0x0b, 0xdb); a.short(0x75, 'bl_w'); a.b(0xc3)   # mov cs:[bars_n], bl / none: ret
    a.label('bl_w')
    a.b(0x8b, 0xcb, 0x8b, 0xc3, 0x48, 0xba, BARS_GAP, 0x00, 0xf7, 0xe2)   # mov cx, bx / mov ax, bx / dec ax / mov dx, gap / mul dx
    a.b(0xf7, 0xd8, 0x05, BARS_SPAN & 0xff, BARS_SPAN >> 8, 0x33, 0xd2, 0xf7, 0xf1)   # neg ax / add ax, span / xor dx, dx / div cx
    a.b(0x2e, 0xa3); a.word('bars_w')                        # the width
    a.b(0x05, BARS_GAP, 0x00, 0xba, BARS_X, 0x00, 0x33, 0xdb)   # add ax, gap / mov dx, x / xor bx, bx
    a.label('bl_x')
    a.b(0x2e, 0x89, 0x97); a.word('bars_x'); a.b(0x03, 0xd0)   # mov cs:[bx+bars_x], dx / add dx, ax
    a.b(0x2e, 0xc7, 0x87); a.word('bars_len'); a.b(0xff, 0xff)   # not drawn yet
    a.b(0x43, 0x43); a.short(0xe2, 'bl_x')                   # inc bx (x2) / loop
    a.label('bl_y')
    a.b(0xb8, BARS_Y, 0x00, 0x2e, 0x80, 0x3e); a.word('score_pend'); a.b(0x00); a.short(0x74, 'bl_yset'); a.b(0xb8, BARS_Y_SCORE, 0x00)
    a.label('bl_yset')
    a.b(0x2e, 0xa3); a.word('bars_y'); a.b(0xc3)
    # bars_value (bx = a bar): ax = the HP left, cx = full, dl = its colour; keeps bx
    a.label('bars_value')
    a.b(0x53, 0x56, 0x57)                                    # push bx si di
    a.b(0x2e, 0x8a, 0x87); a.word('bars_who'); a.b(0x3c, BARS_COMP_SIDE); a.short(0x75, 'bv_kn'); a.near(0xe9, 'bv_comp')
    a.label('bv_kn')
    a.b(0x33, 0xf6, 0x33, 0xc9, 0x3c, BARS_TEAM); a.short(0x72, 'bv_one')   # xor si, si (left) / xor cx, cx / cmp al, 10h / jb
    a.b(0x24, 0x01, 0x32, 0xe4, 0x8b, 0xd8)                  # and al, 1 / xor ah, ah / mov bx, ax   the team: records n, n + 2
    a.near(0xe8, 'bv_rec'); a.b(0x43, 0x43); a.near(0xe8, 'bv_rec'); a.b(0x4b, 0x4b); a.short(0xeb, 'bv_col')
    a.label('bv_one')
    a.b(0x32, 0xe4, 0x8b, 0xd8); a.near(0xe8, 'bv_rec')      # xor ah, ah / mov bx, ax / its record
    a.label('bv_col')
    a.b(0x2e, 0x8a, 0x97); a.word('score_col'); a.b(0x80, 0xfa, 0xff); a.short(0x75, 'bv_kc'); a.b(0xb2, SCORE_WHITE)   # its colour, or white
    a.label('bv_kc')
    a.b(0x8b, 0xc6); a.near(0xe9, 'bv_end')                  # mov ax, si
    a.label('bv_comp')
    a.b(0x33, 0xf6)                                          # xor si, si   the sum
    a.b(0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00)
    a.label('bv_slot')
    a.b(0x83, 0x3d, 0x00); a.short(0x74, 'bv_sn'); a.b(0x8a, 0x45, 0x35)   # in use? its type
    for t in BARS_COMP:
        a.b(0x3c, t); a.short(0x74, 'bv_add')
    a.short(0xeb, 'bv_sn')
    a.label('bv_add')
    a.near(0xe8, 'bv_hp')
    a.label('bv_sn')
    a.b(0x83, 0xc7, SLOT_SIZE); a.short(0xe2, 'bv_slot')
    for k, rec in enumerate(KNIGHTS):                        # the computer's knight records
        a.b(0x2e, 0xf6, 0x06); a.word('bars_crec'); a.b(1 << k); a.short(0x74, f'bv_c{k}')
        a.b(0xbf, rec & 0xff, rec >> 8); a.near(0xe8, 'bv_hp')
        a.label(f'bv_c{k}')
    a.b(0x2e, 0x80, 0x3e); a.word('bars_drag'); a.b(0x00); a.short(0x74, 'bv_nd')
    a.b(0xbf, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8); a.near(0xe8, 'bv_hp')
    a.label('bv_nd')
    a.b(0xa1, 0x6a, 0x09, 0x2e, 0xf7, 0x26); a.word('bars_top'); a.b(0x0b, 0xd2); a.short(0x74, 'bv_sum'); a.b(0xb8, 0xff, 0xff)   # mov ax, [096Ah] / mul word cs:[bars_top] / or dx, dx / jz / at most FFFFh
    a.label('bv_sum')
    a.b(0x03, 0xf0); a.short(0x73, 'bv_full'); a.b(0xbe, 0xff, 0xff)   # add si, ax / jnc / mov si, FFFFh
    a.label('bv_full')
    a.b(0x2e, 0x3b, 0x36); a.word('bars_full'); a.short(0x76, 'bv_fk'); a.b(0x2e, 0x89, 0x36); a.word('bars_full')   # the most seen
    a.label('bv_fk')
    a.b(0x2e, 0x8b, 0x0e); a.word('bars_full'); a.b(0x8b, 0xc6, 0xb2, BARS_YELLOW)   # mov cx, full / mov ax, si / mov dl, yellow
    a.label('bv_end')
    a.b(0x5f, 0x5e, 0x5b, 0xc3)                              # pop di si bx / ret
    a.label('bv_rec')                                        # bx = a knight record's number: if a human's in the fight, si += HP left, cx += max HP
    a.b(0x50, 0x53, 0x52, 0x57)                              # push ax bx dx di
    a.b(0x51, 0x8a, 0xcb, 0xb0, 0x01, 0xd2, 0xe0, 0x59)      # push cx / mov cl, bl / mov al, 1 / shl al, cl / pop cx
    a.b(0x2e, 0x84, 0x06); a.word('bars_hum'); a.short(0x74, 'bvr_end')   # test cs:[bars_hum], al / jz   not in the fight
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0xbf); a.word('bars_recs')   # shl bx, 1 / mov di, cs:[bx+bars_recs]
    a.b(0x8b, 0x45, 0x38, 0x0b, 0xc0); a.short(0x7f, 'bvr_pos'); a.b(0x33, 0xc0)   # mov ax, [di+38h] / or ax, ax / jg / xor ax, ax
    a.label('bvr_pos')
    a.b(0x03, 0xf0, 0x3b, 0x45, 0x3c); a.short(0x7d, 'bvr_big'); a.b(0x8b, 0x45, 0x3c)   # add si, ax / cmp ax, [di+3Ch] / jge / mov ax, [di+3Ch]
    a.label('bvr_big')
    a.b(0x03, 0xc8)                                          # add cx, ax   full: its max HP (or more, if above it)
    a.label('bvr_end')
    a.b(0x5f, 0x5a, 0x5b, 0x58, 0xc3)                        # pop di dx bx ax / ret
    a.label('bv_hp')                                         # di = an object: si += its HP if above 0; bars_top = the most
    a.b(0x8b, 0x45, 0x38, 0x0b, 0xc0); a.short(0x7e, 'bvh_end')   # mov ax, [di+38h] / or ax, ax / jle
    a.b(0x2e, 0x3b, 0x06); a.word('bars_top'); a.short(0x76, 'bvh_add'); a.b(0x2e, 0xa3); a.word('bars_top')
    a.label('bvh_add')
    a.b(0x03, 0xf0); a.short(0x73, 'bvh_end'); a.b(0xbe, 0xff, 0xff)   # add si, ax / jnc / mov si, FFFFh
    a.label('bvh_end')
    a.b(0xc3)

    # --- D56: the score's order, colours and box ---
    # knight_order: score_ord = the knight records with an animation, by their x now (the fight's start) from the left
    a.label('knight_order')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x33, 0xd2)      # push ax bx cx dx si di / xor dx, dx   dl: in it, dh: placed
    for k, rec in enumerate(KNIGHTS):
        a.b(0xbf, rec & 0xff, rec >> 8); a.near(0xe8, 'anim_of'); a.short(0x75, f'ko_n{k}'); a.b(0x80, 0xca, 1 << k)
        a.label(f'ko_n{k}')
    a.b(0x33, 0xc9)                                          # xor cx, cx   cl: the place
    a.label('ko_rank')
    a.b(0xb5, 0xff, 0xbe, 0xff, 0x7f, 0x33, 0xdb)            # mov ch, FFh (none) / mov si, 7FFFh / xor bx, bx
    a.label('ko_k')
    a.b(0x2e, 0x8a, 0x87); a.word('ord_bits'); a.b(0x84, 0xc2); a.short(0x74, 'ko_kn')   # mov al, cs:[bx+ord_bits] / test dl, al / jz
    a.b(0x84, 0xc6); a.short(0x75, 'ko_kn')                  # test dh, al / jnz   placed already
    a.b(0x53, 0xd1, 0xe3, 0x2e, 0x8b, 0xbf); a.word('bars_recs'); a.b(0x5b)   # push bx / shl bx, 1 / mov di, cs:[bx+bars_recs] / pop bx
    a.b(0x8b, 0x45, 0x02, 0x3b, 0xc6); a.short(0x7d, 'ko_kn'); a.b(0x8b, 0xf0, 0x8a, 0xeb)   # mov ax, [di+2] / cmp ax, si / jge / mov si, ax / mov ch, bl
    a.label('ko_kn')
    a.b(0x43, 0x83, 0xfb, 0x04); a.short(0x72, 'ko_k')       # inc bx / cmp bx, 4 / jb
    a.b(0x8a, 0xd9, 0x32, 0xff, 0x2e, 0x88, 0xaf); a.word('score_ord')   # mov bl, cl / xor bh, bh / mov cs:[bx+score_ord], ch
    a.b(0x80, 0xfd, 0xff); a.short(0x74, 'ko_next')          # cmp ch, FFh / je
    a.b(0x8a, 0xdd, 0x2e, 0x0a, 0xb7); a.word('ord_bits')    # mov bl, ch / or dh, cs:[bx+ord_bits]
    a.label('ko_next')
    a.b(0xfe, 0xc1, 0x80, 0xf9, 0x04); a.short(0x72, 'ko_rank')   # inc cl / cmp cl, 4 / jb
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)
    # comp_colour (si = the entry): ah = the computer's wins' colour: the dragon's practice red, the Guardian's turquoise
    a.label('comp_colour')
    a.b(0xb4, SCORE_WHITE)
    a.b(0x2e, 0x80, 0x3c, DRAGON_CHOICE); a.short(0x74, 'cc_red')   # cmp byte cs:[si], 10   (monster)
    a.b(0x2e, 0x80, 0x7c, 0x06, 0x00); a.short(0x75, 'cc_red')     # cmp byte cs:[si+6], 0 / jne   (dragon_ctl)
    a.b(0x2e, 0x80, 0x3c, GUARDIAN_CHOICE); a.short(0x75, 'cc_end')
    a.b(0x2e, 0xc6, 0x06); a.word('pal_mode'); a.b(0x01); a.short(0xeb, 'cc_pick')
    a.label('cc_red')
    a.b(0x2e, 0xc6, 0x06); a.word('pal_mode'); a.b(0x00)
    a.label('cc_pick')
    a.near(0xe8, 'pal_pick')
    a.label('cc_end')
    a.b(0xc3)
    # pal_pick (ds = MAIN's data): ah = the fight palette's entry 1-31 (DS:7A80, 0RGB) reddest (r - max(g, b)) or, with
    # pal_mode 1, most turquoise (min(g, b) - r)
    a.label('pal_pick')
    a.b(0x53, 0x51, 0x52, 0x56, 0x50)                        # push bx cx dx si ax
    a.b(0xbe, (FIGHT_PALETTE + 2) & 0xff, (FIGHT_PALETTE + 2) >> 8, 0xb9, 0x01, 0x00, 0xb2, 0x80, 0xb6, 0x01)   # mov si, 7A82h / mov cx, 1 / mov dl, -128 / mov dh, 1
    a.label('pp_loop')
    a.b(0x8b, 0x1c, 0x8a, 0xc7, 0x24, 0x0f)                  # mov bx, [si] / mov al, bh / and al, 0Fh   r
    a.b(0x8a, 0xe3, 0xd0, 0xec, 0xd0, 0xec, 0xd0, 0xec, 0xd0, 0xec, 0x80, 0xe3, 0x0f)   # mov ah, bl / shr ah, 1 (x4)   g / and bl, 0Fh   b
    a.b(0x2e, 0x80, 0x3e); a.word('pal_mode'); a.b(0x00); a.short(0x75, 'pp_cyan')
    a.b(0x3a, 0xe3); a.short(0x73, 'pp_max'); a.b(0x8a, 0xe3)   # cmp ah, bl / jae / mov ah, bl   max(g, b)
    a.label('pp_max')
    a.b(0x2a, 0xc4); a.short(0xeb, 'pp_cmp')                 # sub al, ah   r - max
    a.label('pp_cyan')
    a.b(0x3a, 0xe3); a.short(0x76, 'pp_min'); a.b(0x8a, 0xe3)   # cmp ah, bl / jbe / mov ah, bl   min(g, b)
    a.label('pp_min')
    a.b(0x2a, 0xe0, 0x8a, 0xc4)                              # sub ah, al / mov al, ah   min - r
    a.label('pp_cmp')
    a.b(0x3a, 0xc2); a.short(0x7e, 'pp_next'); a.b(0x8a, 0xd0, 0x8a, 0xf1)   # cmp al, dl / jle / mov dl, al / mov dh, cl
    a.label('pp_next')
    a.b(0x46, 0x46, 0x41, 0x83, 0xf9, 0x20); a.short(0x72, 'pp_loop')   # add si, 2 / inc cx / cmp cx, 32 / jb
    a.b(0x58, 0x8a, 0xe6, 0x5e, 0x5a, 0x59, 0x5b, 0xc3)      # pop ax / mov ah, dh / pop si dx cx bx / ret
    # score_box (es = the background page, VGA set by vga_keep; box_mode 0 keep, 1 put back): the score's box
    a.label('score_box')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57)
    a.b(0xbe); a.word('score_bg'); a.b(0xba, SCORE_Y, 0x00)  # mov si, score_bg / mov dx, y
    a.label('sbx_row')
    a.b(0xb9, SCORE_BOX_X & 0xff, SCORE_BOX_X >> 8)          # mov cx, x
    a.label('sbx_col')
    a.b(0x8b, 0xfa, 0xd1, 0xe7, 0xd1, 0xe7, 0x03, 0xfa, 0xd1, 0xe7, 0xd1, 0xe7, 0xd1, 0xe7, 0xd1, 0xe7)   # di = 80 y
    a.b(0x8b, 0xd9, 0xd1, 0xeb, 0xd1, 0xeb, 0x03, 0xfb)      # + x / 4
    a.b(0x8a, 0xe1, 0x80, 0xe4, 0x03)                        # mov ah, cl / and ah, 3   the plane
    a.b(0x52, 0xba, 0xce, 0x03, 0xb0, 0x04, 0xee, 0x42, 0x8a, 0xc4, 0xee, 0x5a)   # push dx / read map = the plane / pop dx
    a.b(0x2e, 0x80, 0x3e); a.word('box_mode'); a.b(0x00); a.short(0x75, 'sbx_back')
    a.b(0x26, 0x8a, 0x05, 0x2e, 0x88, 0x04); a.short(0xeb, 'sbx_next')   # mov al, es:[di] / mov cs:[si], al
    a.label('sbx_back')
    a.b(0x51, 0x8a, 0xcc, 0xb0, 0x01, 0xd2, 0xe0, 0x59)      # push cx / mov cl, ah / mov al, 1 / shl al, cl / pop cx
    a.b(0x52, 0x8a, 0xe0, 0xb0, 0x02, 0xba, 0xc4, 0x03, 0xef, 0x5a)   # push dx / mov ah, al / mov al, 2 / mov dx, 3C4h / out dx, ax / pop dx
    a.b(0x2e, 0x8a, 0x04, 0x26, 0x88, 0x05)                  # mov al, cs:[si] / mov es:[di], al
    a.label('sbx_next')
    a.b(0x46, 0x41, 0x81, 0xf9, (SCORE_BOX_X + SCORE_BOX_W) & 0xff, (SCORE_BOX_X + SCORE_BOX_W) >> 8); a.short(0x72, 'sbx_col')
    a.b(0x42, 0x83, 0xfa, SCORE_Y + SCORE_BOX_H); a.short(0x72, 'sbx_row')
    a.b(0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)

    # --- IDROPPEDMYKEY ---
    # key_stage (from turn_moves): a text screen of who or what holds each key, and back to the map. The lairs holding
    # one glow on the map until the turn ends (lair_icon). The text goes in a free part of MAIN's data, KEY_TEXT
    a.label('key_stage')
    a.b(0x2e, 0xa0); a.word('key_show'); a.b(0x2e, 0xfe, 0x06); a.word('key_show')   # mov al, cs:[key_show] / inc cs:[key_show]
    a.b(0x3c, 0x01); a.short(0x75, 'kxs_2')
    a.b(0xb8, 0x2d, 0xa7); a.short(0xeb, 'kxs_call')         # mov ax, 0A72Dh
    a.label('kxs_2')
    a.b(0x3c, 0x02); a.short(0x75, 'kxs_3')
    a.near(0xe8, 'key_text')
    a.b(0xbe, KEY_LIST & 0xff, KEY_LIST >> 8, 0xb8, 0xc4, 0x90); a.short(0xeb, 'kxs_call')   # mov si, the list / mov ax, 90C4h
    a.label('kxs_3')
    a.b(0x3c, 0x03); a.short(0x75, 'kxs_4')
    a.b(0xb8, 0x25, 0x84); a.short(0xeb, 'kxs_call')         # mov ax, 8425h   fire
    a.label('kxs_4')
    a.b(0x3c, 0x04); a.short(0x75, 'kxs_end')
    a.b(0xb8, 0xbc, 0xa3)                                    # mov ax, 0A3BCh   the map again
    a.label('kxs_call')
    a.b(0x2e, 0xa3); a.word('call_target')
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(TURN_MOVES_SITE & 0xff, TURN_MOVES_SITE >> 8)
    a.near(0xe9, 'call_game')
    a.label('kxs_end')
    a.b(0x2e, 0xc6, 0x06); a.word('key_show'); a.b(0x00)
    a.b(0xc7, 0x46, 0x02, MAP_LOOP & 0xff, MAP_LOOP >> 8); a.near(0xe9, 'rules_done')   # on at the map loop's start
    a.label('key_text')
    a.b(0x06, 0x1e, 0x07, 0xfc, 0xbf, KEY_TEXT & 0xff, KEY_TEXT >> 8)   # push es / push ds / pop es / cld / mov di, the text
    for n, (bit, name) in enumerate(KEY_REGIONS):
        e = KEY_LIST + 10 * n
        a.b(0x89, 0x3e, e & 0xff, e >> 8)                    # mov [entry], di
        for off, v in ((2, 0), (4, 0x37 + 0x14 * n), (6, 1), (8, e + 10)):
            a.b(0xc7, 0x06, (e + off) & 0xff, (e + off) >> 8, v & 0xff, v >> 8)
        a.b(0xbe); a.word(f'kxt_{n}'); a.near(0xe8, 'kx_copy_cs')
        a.b(0xb0, bit); a.near(0xe8, 'key_holder')           # mov al, bit / call key_holder
        a.short(0x72, f'kxt_ds{n}'); a.near(0xe8, 'kx_copy_cs'); a.short(0xeb, f'kxt_e{n}')
        a.label(f'kxt_ds{n}')
        a.near(0xe8, 'kx_copy_ds')
        a.label(f'kxt_e{n}')
        a.b(0x32, 0xc0, 0xaa)                                # xor al, al / stosb   its end
    e = KEY_LIST + 10 * len(KEY_REGIONS)
    for off, v in ((0, 0x0632), (2, 0), (4, 0xb6), (6, 1), (8, 0)):   # the game's "Press fire to continue"
        a.b(0xc7, 0x06, (e + off) & 0xff, (e + off) >> 8, v & 0xff, v >> 8)
    a.b(0x07, 0xc3)                                          # pop es / ret
    a.label('kx_copy_cs')
    a.b(0x2e, 0xac, 0x0a, 0xc0); a.short(0x74, 'kxc_e'); a.b(0xaa); a.short(0xeb, 'kx_copy_cs')   # lodsb cs: / or al, al / jz / stosb
    a.label('kxc_e')
    a.b(0xc3)
    a.label('kx_copy_ds')
    a.b(0xac, 0x0a, 0xc0); a.short(0x74, 'kxd_e'); a.b(0xaa); a.short(0xeb, 'kx_copy_ds')
    a.label('kxd_e')
    a.b(0xc3)
    # key_holder (al = a key's bit): CF = 1 si = a knight's name in MAIN's data; CF = 0 si = a text here
    a.label('key_holder')
    a.b(0x53, 0x51)                                          # push bx cx
    for rec in KNIGHTS:
        a.b(0x8b, 0x1e, (rec + 0x44) & 0xff, (rec + 0x44) >> 8, 0x84, 0x47, 0x14); a.short(0x74, f'kh_n{rec:x}')   # mov bx, [rec+44h] / test [bx+14h], al / jz
        a.b(0x8b, 0x36, (rec + 0x4c) & 0xff, (rec + 0x4c) >> 8, 0xf9); a.near(0xe9, 'kh_ret')   # mov si, [rec+4Ch] / stc
        a.label(f'kh_n{rec:x}')
    r = DRAGON_RECORD + 0x44
    a.b(0x8b, 0x1e, r & 0xff, r >> 8, 0x84, 0x47, 0x14); a.short(0x74, 'kh_nd')
    a.b(0xbe); a.word('kxt_dragon'); a.short(0xeb, 'kh_clc')
    a.label('kh_nd')
    a.b(0x84, 0x06, (TEMPLE_ITEMS + 0x14) & 0xff, (TEMPLE_ITEMS + 0x14) >> 8); a.short(0x74, 'kh_nt')   # test [temple+14h], al / jz
    a.b(0xbe); a.word('kxt_temple'); a.short(0xeb, 'kh_clc')
    a.label('kh_nt')
    a.b(0xbe, 0x02, 0x00, 0xb9, 0x18, 0x00)                  # mov si, 2 / mov cx, 24   the lairs
    a.label('kh_lair')
    a.b(0x8b, 0x1c, 0x84, 0x47, 0x14); a.short(0x75, 'kh_inlair')   # mov bx, [si] / test [bx+14h], al / jnz
    a.b(0x83, 0xc6, 0x12); a.short(0xe2, 'kh_lair')          # add si, 12h / loop
    a.b(0xbe); a.word('kxt_none'); a.short(0xeb, 'kh_clc')
    a.label('kh_inlair')
    a.b(0xbe); a.word('kxt_lair')
    a.label('kh_clc')
    a.b(0xf8)
    a.label('kh_ret')
    a.b(0x59, 0x5b, 0xc3)                                    # pop cx bx / ret
    # lair_icon (1000:A45F, mov ax,14h: a lair's icon on the map): after IDROPPEDMYKEY, this turn, one holding a key glows
    # D45: black_knight_ai = smart (0 = classic: the game's own code). bk_track (1000:4BCD, or ax,ax after MonsterTrack in
    # ControlBlackKnight: si = the knight, di = its foe, ax = 0: in place to attack, [7BFBh] = in line in depth, [si+26h] = the
    # steps asked for). Against a foe who stands off the line: far off the knight lines up first; at the edge of reach (between
    # [si+54h] and [si+52h]) it waits a random moment instead of stepping in; a foe seen swinging on a previous tick is
    # recovering, so the knight goes in, or strikes when in line; on the first sight of a swing it sometimes blocks.
    # [si+4Ah] = 1-11 ticks to wait, 80h+ = stepping in; [si+4Bh] = 1 if the foe was swinging on the last tick.
    # bk_down (1000:4B85, mov [77E8h],si: a computer knight's control; di = its animation): dead and its extended death over: it stays down
    a.label('rules_bk_down')
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7f, 'bkd_up')   # cmp word [si+38h], 0 / jg
    a.b(0x81, 0x7d, 0x02, D20_BASE & 0xff, D20_BASE >> 8); a.short(0x72, 'bkd_up')   # cmp [di+2], F480h / jb
    a.b(0x81, 0x7d, 0x02, D20_END & 0xff, D20_END >> 8); a.short(0x73, 'bkd_up')     # cmp [di+2], FE50h / jae
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00); a.short(0x74, 'bkd_stay')   # D60: cmp byte cs:[multi], 0 / je
    a.near(0xe8, 'hold_body')                                # call hold_body   its body stays in sight
    a.label('bkd_stay')
    a.b(0x89, 0x36, 0xe8, 0x77, 0xc7, 0x46, 0x02, 0xea, 0x3a); a.near(0xe9, 'rules_done')   # mov [77E8h], si / mov word [bp+2], 3AEAh   nothing new: it stays down
    a.label('bkd_up')
    a.b(0x89, 0x36, 0xe8, 0x77); a.near(0xe9, 'rules_done')  # mov [77E8h], si   (replaced)
    a.label('rules_bk_track')
    a.b(0x87, 0xfe); a.near(0xe8, 'td_held'); a.b(0x87, 0xfe); a.short(0x73, 'bkt_free')   # xchg di, si / call td_held / xchg di, si / jnc
    a.b(0x87, 0xfe); a.near(0xe8, 'td_stag_script'); a.b(0x87, 0xfe, 0xa3, 0x3a, 0x78)   # the stagger plays on: mov [783Ah], its script
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d)                        # mov word [bp+2], 2D5Eh
    a.near(0xe9, 'rules_done')
    a.label('bkt_free')
    a.b(0x2e, 0x80, 0x3e); a.word('dummy'); a.b(0x00); a.short(0x75, 'bkd_on'); a.near(0xe9, 'bkd_off')
    # D46: the practice Purple Knight (P key): walks to its foe (never strikes: [7BFBh] = 0), and against a chop in the air ripostes half the time
    a.label('bkd_on')
    a.b(0xc7, 0x06, 0xfb, 0x7b, 0x00, 0x00, 0x83, 0x7d, 0x28, 0x10); a.short(0x75, 'bkd_stand')   # mov word [7BFBh], 0 / cmp word [di+28h], 10h / jne
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'bkd_stand')   # cmp word [di+38h], 0 / jle
    a.b(0x83, 0x7d, 0x0c, 0x00); a.short(0x75, 'bkd_stand')   # cmp word [di+0Ch], 0 / jne   its chop has hit
    a.b(0x50, 0x57); a.near(0xe8, 'td_slot'); a.short(0x72, 'bkd_pop'); a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('td_atk')   # push ax di / call td_slot / jc / shl bx,1 / mov ax, cs:[bx+td_atk]
    a.b(0x8b, 0xfe); a.near(0xe8, 'td_slot'); a.short(0x72, 'bkd_pop'); a.b(0xd1, 0xe3, 0x2e, 0x3b, 0x87); a.word('td_rolled'); a.short(0x74, 'bkd_pop')   # mov di, si / call td_slot / jc / shl bx,1 / cmp ax, cs:[bx+td_rolled] / je   once per chop
    a.b(0x2e, 0x89, 0x87); a.word('td_rolled'); a.near(0xe8, 'game_random'); a.b(0xa8, 0x01); a.short(0x74, 'bkd_pop')   # mov cs:[bx+td_rolled], ax / call game_random / test al, 1 / jz
    a.b(0xd1, 0xeb, 0x2e, 0xc6, 0x87); a.word('td_fk'); a.b(0x02)   # shr bx,1 / mov byte cs:[bx+td_fk], 2   its riposte
    a.b(0x5f, 0x58, 0xc7, 0x44, 0x28, 0x02, 0x00, 0xc7, 0x06, 0x3a, 0x78, 0x2a, 0x10, 0xc7, 0x46, 0x02, 0x5e, 0x2d)   # pop di ax / mov word [si+28h], 2 / mov word [783Ah], 102Ah / mov word [bp+2], 2D5Eh
    a.near(0xe9, 'rules_done')
    a.label('bkd_pop')
    a.b(0x5f, 0x58)                                          # pop di ax
    a.label('bkd_stand')
    a.b(0xc7, 0x44, 0x28, 0x00, 0x00)                        # mov word [si+28h], 0   no attack of its own in the air
    a.b(0x0b, 0xc0); a.short(0x75, 'bkd_walk')               # or ax, ax / jnz
    a.near(0xe8, 'dm_attack'); a.short(0x73, 'bkd_still')    # call dm_attack / jnc   an attack of its own now?
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d); a.near(0xe9, 'rules_done')
    a.label('bkd_still')
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d); a.near(0xe9, 'rules_done')   # in place: stands ([783Ah] is its own standing script)
    a.label('bkd_walk')
    a.b(0x83, 0x7c, 0x02, 0x0a); a.short(0x7c, 'bkd_off_scr')   # cmp word [si+2], 10 / jl   not yet on the screen
    a.b(0x81, 0x7c, 0x02, 0x36, 0x01); a.short(0x7e, 'bkd_go')    # cmp word [si+2], 310 / jle
    a.label('bkd_off_scr')
    a.near(0xe8, 'dm_wait')                                  # call dm_wait   10 s from when it comes in
    a.label('bkd_go')
    a.b(0x0b, 0xc0); a.near(0xe9, 'rules_flags')             # or ax, ax  (replaced)
    a.label('bkd_off')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_BK_AI); a.b(0x00); a.short(0x75, 'bkt_smart')
    a.label('bkt_game')
    a.b(0x0b, 0xc0); a.near(0xe9, 'rules_flags')             # or ax, ax  (replaced)
    a.label('bkt_smart')
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'bkt_game')   # cmp word [di+38h], 0 / jle   the foe is down: as the game
    a.b(0x50, 0x8b, 0x44, 0x02, 0x2b, 0x45, 0x02, 0x79, 0x02, 0xf7, 0xd8, 0x8b, 0xc8)   # push ax / cx = |x - foe's x|
    a.b(0x8a, 0x54, 0x4b, 0xc6, 0x44, 0x4b, 0x00)            # mov dl, [si+4Bh] / mov byte [si+4Bh], 0
    a.b(0x8b, 0x45, 0x28, 0x0b, 0xc0); a.short(0x74, 'bkt_idle')   # mov ax, [di+28h] / or ax, ax / jz   the foe's move
    a.b(0x3d, 0x08, 0x00); a.short(0x74, 'bkt_idle')         # cmp ax, 8 / je      block
    a.b(0x3d, 0x0e, 0x00); a.short(0x74, 'bkt_idle')         # cmp ax, 0Eh / je    special defence
    a.b(0xc6, 0x44, 0x4b, 0x01); a.short(0xeb, 'bkt_seen')   # mov byte [si+4Bh], 1 / jmp
    a.label('bkt_idle')
    a.b(0x33, 0xc0)                                          # xor ax, ax
    a.label('bkt_seen')
    a.b(0x3d, 0x10, 0x00); a.short(0x74, 'bkt_chop'); a.near(0xe9, 'bkt_nochop')   # cmp ax, 10h / je
    # D46: a foe's chop in the air: no walking in under it. In reach: step away; further off: wait. (No strike now: [7BFBh] = 0 and ax != 0 on return)
    a.label('bkt_chop')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_CHOP_CHEESE); a.b(0x00); a.short(0x75, 'bkt_cheese'); a.near(0xe9, 'bkt_nochop')   # anticheese = no
    a.label('bkt_cheese')
    a.b(0xc7, 0x06, 0xfb, 0x7b, 0x00, 0x00, 0xc6, 0x44, 0x26, 0x00)   # mov word [7BFBh], 0 / mov byte [si+26h], 0
    a.b(0x83, 0xf9, 0x70); a.short(0x77, 'bkt_cdone')         # cmp cx, 70h / ja
    a.b(0x8b, 0x44, 0x02, 0x3b, 0x45, 0x02, 0xb0, 0x02); a.short(0x7c, 'bkt_cdir'); a.b(0xb0, 0x01)   # mov ax,[si+2] / cmp ax,[di+2] / mov al, 2 (left) / jl / mov al, 1
    a.label('bkt_cdir')
    a.b(0x88, 0x44, 0x26)                                     # mov [si+26h], al
    a.label('bkt_cdone')
    a.b(0xc6, 0x44, 0x4a, 0x00, 0x58, 0xb8, 0x01, 0x00, 0x0b, 0xc0); a.near(0xe9, 'rules_flags')   # mov byte [si+4Ah], 0 / pop ax / mov ax, 1 / or ax, ax
    a.label('bkt_nochop')
    a.b(0x83, 0x3e, 0xfb, 0x7b, 0x00); a.short(0x74, 'bkt_off')   # cmp word [7BFBh], 0 / je   not in line
    a.b(0xc6, 0x44, 0x4a, 0x00, 0x0a, 0xd2); a.short(0x74, 'bkt_end')   # mov byte [si+4Ah], 0 / or dl, dl / jz
    a.b(0x83, 0xf9, 0x5f); a.short(0x7f, 'bkt_end')          # cmp cx, 5Fh / jg    out of reach of a blow
    a.b(0xb8, 0xf1, 0x4c); a.short(0xeb, 'bkt_goto')         # mov ax, 4CF1h       strike (the game's choice of blow)
    a.label('bkt_off')
    a.b(0x3b, 0x4c, 0x52); a.short(0x7e, 'bkt_near')         # cmp cx, [si+52h] / jle
    a.b(0x80, 0x64, 0x26, 0xfc); a.short(0xeb, 'bkt_end')    # and byte [si+26h], 0FCh / jmp   far off: only in depth
    a.label('bkt_near')
    a.b(0x3b, 0x4c, 0x54); a.short(0x7e, 'bkt_end')          # cmp cx, [si+54h] / jle   too close: backs off, as the game
    a.b(0x0a, 0xd2); a.short(0x74, 'bkt_first')              # or dl, dl / jz
    a.b(0xc6, 0x44, 0x4a, 0x88); a.short(0xeb, 'bkt_end')    # mov byte [si+4Ah], 88h / jmp   the foe recovers: step in
    a.label('bkt_first')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'bkt_first_game')   # D46: the roll at the hit defends instead
    a.near(0xe9, 'bkt_phase')
    a.label('bkt_first_game')
    a.b(0x3d, 0x04, 0x00); a.short(0x74, 'bkt_can')          # cmp ax, 4 / je    the moves the game's block answers
    a.b(0x3d, 0x10, 0x00); a.short(0x74, 'bkt_can')          # cmp ax, 10h / je
    a.b(0x3d, 0x02, 0x00); a.short(0x75, 'bkt_phase')        # cmp ax, 2 / jne
    a.label('bkt_can')
    a.b(0x8a, 0x45, 0x08, 0x3a, 0x44, 0x08); a.short(0x74, 'bkt_phase')   # mov al, [di+8] / cmp al, [si+8] / je   not face to face
    a.near(0xe8, 'game_random'); a.b(0xa8, 0x03); a.short(0x75, 'bkt_phase')   # one in four
    a.b(0xb8, 0x63, 0x4c)                                    # mov ax, 4C63h     the game's block (BKBlock, after its roll)
    a.label('bkt_goto')
    a.b(0x8b, 0x7c, 0x16, 0x89, 0x4e, 0xfe, 0x89, 0x46, 0x02, 0x58)   # mov di, [si+16h] / mov [bp-2], cx / mov [bp+2], ax / pop ax
    a.near(0xe9, 'rules_done')
    a.label('bkt_end')
    a.b(0x58, 0x0b, 0xc0); a.near(0xe9, 'rules_flags')       # pop ax / or ax, ax  (replaced)
    a.label('bkt_phase')
    a.b(0x8a, 0x44, 0x4a, 0xa8, 0x80); a.short(0x74, 'bkt_wait')   # mov al, [si+4Ah] / test al, 80h / jz
    a.b(0x24, 0x7f); a.short(0x74, 'bkt_over')               # and al, 7Fh / jz
    a.b(0xfe, 0x4c, 0x4a); a.short(0xeb, 'bkt_end')          # dec byte [si+4Ah] / jmp   stepping in
    a.label('bkt_over')
    a.b(0xc6, 0x44, 0x4a, 0x00); a.short(0xeb, 'bkt_end')    # mov byte [si+4Ah], 0 / jmp
    a.label('bkt_wait')
    a.b(0x3c, 0x0c); a.short(0x72, 'bkt_val')                # cmp al, 12 / jb
    a.b(0x32, 0xc0)                                          # xor al, al        (a stale value from another use of the field)
    a.label('bkt_val')
    a.b(0x0a, 0xc0); a.short(0x75, 'bkt_set')                # or al, al / jnz
    a.near(0xe8, 'game_random'); a.b(0x24, 0x07, 0x04, 0x04)  # and al, 7 / add al, 4   4-11 ticks
    a.label('bkt_set')
    a.b(0xfe, 0xc8, 0x88, 0x44, 0x4a); a.short(0x75, 'bkt_stand')   # dec al / mov [si+4Ah], al / jnz
    a.b(0xc6, 0x44, 0x4a, 0x88)                              # mov byte [si+4Ah], 88h     waited enough: step in
    a.label('bkt_stand')
    a.b(0xc6, 0x44, 0x26, 0x00); a.short(0xeb, 'bkt_end')    # mov byte [si+26h], 0 / jmp   stand this tick
    # bk_lair (1000:A9B6, mov si, 0CCD2h: the 24 lairs are sorted by distance, dword each: distance, record): the nearest lair
    # not stood on that still holds items or gold, one in four looking at the next. None: the game's own choice
    a.label('rules_bk_lair')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_BK_AI); a.b(0x00); a.short(0x74, 'bkl_game')
    a.b(0x33, 0xd2, 0xb9, 0x18, 0x00, 0xbe, 0xd2, 0xcc)      # xor dx, dx / mov cx, 24 / mov si, 0CCD2h
    a.label('bkl_loop')
    a.b(0x83, 0x3c, 0x08); a.short(0x72, 'bkl_next')         # cmp word [si], 8 / jb    stands on it
    a.b(0x8b, 0x5c, 0x02, 0x83, 0x7f, 0x0a, 0x00); a.short(0x7c, 'bkl_next')   # mov bx, [si+2] / cmp word [bx+0Ah], 0 / jl
    a.b(0x83, 0x7f, 0x06, 0x00); a.short(0x75, 'bkl_has')    # cmp word [bx+6], 0 / jne   gold
    a.b(0x51, 0x56, 0x8b, 0x37, 0xb9, 0x18, 0x00, 0x33, 0xc0)   # push cx si / mov si, [bx] / mov cx, 24 / xor ax, ax
    a.label('bkl_items')
    a.b(0x0a, 0x04, 0x46); a.short(0xe2, 'bkl_items'); a.b(0x5e, 0x59, 0x0a, 0xc0)   # or al, [si] / inc si / loop / pop si cx / or al, al
    a.short(0x74, 'bkl_next')
    a.label('bkl_has')
    a.b(0x8b, 0xd3); a.near(0xe8, 'game_random'); a.b(0xa8, 0x03); a.short(0x75, 'bkl_take')   # mov dx, bx / one in four goes on
    a.label('bkl_next')
    a.b(0x83, 0xc6, 0x04); a.short(0xe2, 'bkl_loop'); a.b(0x0b, 0xd2); a.short(0x74, 'bkl_game')   # add si, 4 / loop / or dx, dx / jz
    a.label('bkl_take')
    a.b(0x89, 0x16, 0x32, 0xcd, 0xc7, 0x46, 0x02, 0xd1, 0xa9)   # mov [0CD32h], dx / mov word [bp+2], 0A9D1h
    a.near(0xe9, 'rules_done')
    a.label('bkl_game')
    a.b(0xbe, 0xd2, 0xcc); a.near(0xe9, 'rules_done')        # mov si, 0CCD2h  (replaced)
    # bk_target (1000:ABD7, cmp word [si+46h],0: ax, bx = the knight's map place, about to pick its goal): all four keys: Stonehenge
    # at once, whatever else it was after, and the turn ends there. (No computer knight can enter the Valley: that stays a player's.)
    a.label('rules_bk_target')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_BK_AI); a.b(0x00); a.short(0x74, 'bkg_game')
    a.b(0x8b, 0x5c, 0x44, 0x80, 0x7f, 0x14, 0x0f); a.short(0x75, 'bkg_game')   # mov bx, [si+44h] / cmp byte [bx+14h], 0Fh / jne
    a.b(0xb9, STONEHENGE_X & 0xff, STONEHENGE_X >> 8, 0xba, STONEHENGE_Y & 0xff, STONEHENGE_Y >> 8)   # mov cx, x / mov dx, y
    a.b(0x50, 0x2b, 0xc1, 0x79, 0x02, 0xf7, 0xd8, 0x8b, 0x5e, 0xfe, 0x2b, 0xda, 0x79, 0x02, 0xf7, 0xdb, 0x03, 0xc3)   # push ax / ax = |ax - x| + |bx - y|
    a.b(0x83, 0xf8, 0x08, 0x58); a.short(0x7e, 'bkg_there')  # cmp ax, 8 / pop ax / jle
    a.b(0xc7, 0x46, 0x02, 0x0a, 0xac); a.near(0xe9, 'rules_done')   # mov word [bp+2], 0AC0Ah
    a.label('bkg_there')
    a.b(0xa1, 0xac, 0xcc, 0xa3, 0x98, 0xcc, 0x33, 0xc0)      # mov ax, [0CCACh] / mov [0CC98h], ax / xor ax, ax   the turn is over
    a.b(0xc7, 0x46, 0x02, 0x89, 0xac); a.near(0xe9, 'rules_done')   # mov word [bp+2], 0AC89h   ret
    a.label('bkg_game')
    a.b(0x83, 0x7c, 0x46, 0x00); a.near(0xe9, 'rules_flags')  # cmp word [si+46h], 0  (replaced)
    # bk_shop (1000:AE78, mov si,[77E8h] in KnightSupplies): under half its HP, with lives to spare and the healer's price in hand,
    # a knight goes to town for a full heal (marker 38h in [0C426h]) and forgets the knight it was after
    a.label('rules_bk_shop')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_BK_AI); a.b(0x00); a.short(0x74, 'bks_end')
    a.b(0x8b, 0x44, 0x38, 0xd1, 0xe0, 0x3b, 0x44, 0x3c); a.short(0x7d, 'bks_end')   # mov ax, [si+38h] / shl ax, 1 / cmp ax, [si+3Ch] / jge
    a.b(0x80, 0x7c, 0x31, 0x02); a.short(0x7e, 'bks_end')    # cmp byte [si+31h], 2 / jle   a life point comes first
    a.b(0x33, 0xc0, 0x2e, 0xa0); a.word('rules_table', G_BK_HEAL)   # xor ax, ax / mov al, cs:[heal]
    a.b(0x3b, 0x44, 0x32); a.short(0x7f, 'bks_end')          # cmp ax, [si+32h] / jg
    a.b(0xa3, 0x24, 0xc4, 0xc7, 0x06, 0x26, 0xc4, 0x38, 0x00)   # mov [0C424h], ax / mov word [0C426h], 38h
    a.b(0xc7, 0x44, 0x46, 0x00, 0x00, 0xc7, 0x46, 0x02, 0x82, 0xae)   # mov word [si+46h], 0 / mov word [bp+2], 0AE82h   ret
    a.label('bks_end')
    a.near(0xe9, 'rules_done')
    # bk_town (1000:AFA3, mov si,[77E8h] in KnightInTown): pays and takes the heal bk_shop chose
    a.label('rules_bk_town')
    a.b(0x8b, 0x36, 0xe8, 0x77, 0x81, 0x3e, 0x26, 0xc4, 0x38, 0x00); a.short(0x75, 'bkw_end')   # (replaced) / cmp word [0C426h], 38h / jne
    a.b(0xa1, 0x24, 0xc4, 0x29, 0x44, 0x32, 0x8b, 0x44, 0x3c, 0x89, 0x44, 0x38)   # mov ax, [0C424h] / sub [si+32h], ax / HP = max
    a.b(0xc7, 0x46, 0x02, 0xc9, 0xaf)                        # mov word [bp+2], 0AFC9h   ret
    a.label('bkw_end')
    a.near(0xe9, 'rules_done')
    # D44: computer_knights = off. no_computer (1000:00DF, jmp A4B0 at the end of a new campaign's set-up; a practice does
    # not come here): the computer's knights start dead, so the turn loop passes them (A66C) and they are never targets
    a.label('rules_no_computer')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_COMPUTER); a.b(0x00); a.short(0x75, 'nc_go')
    a.b(0x56, 0x51, 0xbe, 0x9e, 0x6c, 0xb9, 0x04, 0x00)      # push si cx / mov si, 6C9Eh / mov cx, 4
    a.label('nc_loop')
    a.b(0x83, 0x7c, 0x20, 0x04); a.short(0x75, 'nc_next')    # cmp word [si+20h], 4 / jne
    a.b(0xc6, 0x44, 0x31, 0x00)                              # mov byte [si+31h], 0
    a.label('nc_next')
    a.b(0x83, 0xc6, 0x62); a.short(0xe2, 'nc_loop'); a.b(0x59, 0x5e)   # add si, 62h / loop / pop cx si
    a.label('nc_go')
    a.b(0xc7, 0x46, 0x02, 0xb0, 0xa4)                        # mov word [bp+2], 0A4B0h
    a.near(0xe9, 'rules_done')
    # map_others (1000:A410, cmp di,si / je A43E: si = a knight to draw, di = the active one): a removed knight leaves no grave
    a.label('rules_map_others')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_COMPUTER); a.b(0x00); a.short(0x75, 'mo_same')
    a.b(0x83, 0x7c, 0x20, 0x04); a.short(0x74, 'mo_skip')    # cmp word [si+20h], 4 / je
    a.label('mo_same')
    a.b(0x3b, 0xfe); a.short(0x75, 'mo_end')                 # cmp di, si / jne
    a.label('mo_skip')
    a.b(0xc7, 0x46, 0x02, 0x3e, 0xa4)                        # mov word [bp+2], 0A43Eh
    a.label('mo_end')
    a.near(0xe9, 'rules_done')
    a.label('rules_lair_icon')
    a.b(0xb8, 0x14, 0x00)                                    # (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('keys_shown'); a.b(0x00); a.short(0x74, 'li_end')
    a.b(0x8b, 0x1c, 0x80, 0x7f, 0x14, 0x00); a.short(0x74, 'li_end')   # mov bx, [si] / cmp byte [bx+14h], 0 / je
    a.b(0xb8, 0x1f, 0x00)                                    # mov ax, 1Fh   the glow
    a.label('li_end')
    a.near(0xe9, 'rules_done')
    # valley_keys (1000:0FD2, cmp byte [si+14h],0Fh: all four keys?): SIRPICKSALOT: any number will do
    a.label('rules_valley_keys')
    a.b(0x2e, 0xf6, 0x06); a.word('map_flags'); a.b(MAP_ANY_KEYS); a.short(0x74, 'vk_game')
    a.b(0x3b, 0xf6); a.short(0xeb, 'vk_end')                 # cmp si, si   ZF = 1
    a.label('vk_game')
    a.b(0x80, 0x7c, 0x14, 0x0f)                              # (replaced)
    a.label('vk_end')
    a.near(0xe9, 'rules_flags')

    # spawn_init (1000:2824, call bx: a new monster's fields by its type, [0974h]; di = the object, its place set):
    # a Black Knight practice makes it the next Black Knight instead: a copy of knight n (n = the count so far) as a
    # computer knight, walking in from the left or right. The first sets the counts: as many at once and to defeat
    # as the knights, and the set-up's spawn loop (1000:27F0, cx) makes that many
    # A monster code's fight (mon_ctl) has player 1's monster only: one at once and one to defeat ([096Ch],
    # [096Ah]), and the set-up's spawn loop makes just this one
    a.label('rules_spawn_init')
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00)           # cmp byte cs:[bk], 0
    a.short(0x75, 'sp_bk')                                   # jne sp_bk
    a.b(0x2e, 0x80, 0x3e); a.word('mon_ctl'); a.b(0x00); a.short(0x74, 'sp_game')   # a monster code's fight?
    a.b(0xc7, 0x06, 0x6c, 0x09, 0x01, 0x00)                  # mov word [096Ch], 1   one at once
    a.b(0x83, 0x3e, 0x6a, 0x09, 0x01); a.short(0x7e, 'sp_one')   # cmp word [096Ah], 1 / jle
    a.b(0xc7, 0x06, 0x6a, 0x09, 0x01, 0x00)                  # mov word [096Ah], 1   one to defeat
    a.label('sp_one')
    a.b(0x81, 0x7e, 0x08, 0xf7, 0x27); a.short(0x75, 'sp_game')   # cmp word [bp+8], 27F7h   the set-up's loop?
    a.b(0xb9, 0x01, 0x00)                                    # mov cx, 1   the loop's count: this one is the last
    a.label('sp_game')
    a.b(0x50, 0xa1, 0x74, 0x09)                              # push ax / mov ax, [0974h]
    a.b(0x2e, 0xa3); a.word('call_target'); a.b(0x58)        # mov cs:[call_target], ax / pop ax
    a.b(0x2e, 0xc7, 0x06); a.word('call_ret'); a.b(0x26, 0x28)   # mov word cs:[call_ret], 2826h
    a.near(0xe9, 'call_game')                                # jmp call_game   as the game
    a.label('sp_bk')
    a.b(0x50, 0x51, 0x56, 0x57, 0x06)                        # push ax cx si di es
    a.b(0x1e, 0x07, 0xfc)                                    # push ds / pop es / cld
    a.b(0x2e, 0x80, 0x3e); a.word('bk_count'); a.b(0x00)     # cmp byte cs:[bk_count], 0
    a.short(0x75, 'sp_copy')                                 # jne sp_copy
    a.b(0x2e, 0xa0); a.word('coop'); a.b(0x32, 0xe4)         # mov al, cs:[coop] / xor ah, ah   the knights
    a.b(0xa3, 0x6a, 0x09, 0xa3, 0x6c, 0x09)                  # mov [096Ah], ax / mov [096Ch], ax
    a.b(0x81, 0x7e, 0x08, 0xf7, 0x27)                        # cmp word [bp+8], 27F7h   the set-up's loop?
    a.short(0x75, 'sp_items')                                # jne sp_items
    a.b(0x89, 0x46, 0xfa)                                    # mov [bp-6], ax           its cx: that many
    a.label('sp_items')
    for field, script in REACTION_DEFAULTS:                  # not the trolls' throw: as in a knight's fight
        a.b(0xc7, 0x06, (REACTIONS + field) & 0xff, (REACTIONS + field) >> 8, script & 0xff, script >> 8)
    a.b(0x57, 0xbf, BK_ITEMS & 0xff, BK_ITEMS >> 8)          # push di / mov di, item table
    a.b(0xb9, 0x18, 0x00, 0x32, 0xc0, 0xf3, 0xaa, 0x5f)      # mov cx, 24 / xor al, al / rep stosb / pop di
    a.b(0x2e, 0x80, 0x3e); a.word('dummy'); a.b(0x00); a.short(0x75, 'sp_colour')   # D46: or the practice knight
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x02)           # cmp byte cs:[bk], 2
    a.short(0x75, 'sp_copy')                                 # jne sp_copy
    a.label('sp_colour')
    a.near(0xe8, 'bk_colours_on')                            # call bk_colours_on
    a.label('sp_copy')
    a.b(0x2e, 0xa0); a.word('bk_count')                      # mov al, cs:[bk_count]
    a.b(0xb4, SLOT_SIZE, 0xf6, 0xe4)                         # mov ah, 62h / mul ah
    a.b(0x05, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8, 0x8b, 0xf0)   # add ax, 6C9Eh / mov si, ax   knight n
    a.b(0x57, 0xb9, SLOT_SIZE, 0x00, 0xf3, 0xa4, 0x5f)       # push di / mov cx, 62h / rep movsb / pop di
    a.b(0xc7, 0x05, 0x01, 0x00)                              # mov word [di], 1          in use
    a.b(0xc6, 0x45, 0x35, COMPUTER_TYPE, 0xc6, 0x45, 0x09, 0x04)   # mov byte [di+35h], 8 / mov byte [di+9], 4
    a.b(0xc7, 0x45, 0x20, 0x04, 0x00)                        # mov word [di+20h], 4      computer
    a.b(0xc7, 0x45, 0x18, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8)   # mov word [di+18h], 8933h  the knights' bank
    for field in (0x0c, 0x0e, 0x26, 0x28):
        a.b(0xc7, 0x45, field, 0x00, 0x00)                   # mov word [di+field], 0
    a.b(0xc7, 0x45, 0x44, BK_ITEMS & 0xff, BK_ITEMS >> 8)    # mov word [di+44h], item table
    a.b(0x2e, 0x8a, 0x1e); a.word('bk_count'); a.b(0x32, 0xff)   # mov bl, cs:[bk_count] / xor bh, bh
    a.b(0x2e, 0x8a, 0x87); a.word('bk_face')                 # mov al, cs:[bx+bk_face]
    a.b(0x88, 0x45, 0x08, 0xd1, 0xe3)                        # mov [di+8], al / shl bx, 1
    a.b(0x2e, 0x8b, 0x87); a.word('bk_x'); a.b(0x89, 0x45, 0x02)   # mov ax, cs:[bx+bk_x] / mov [di+2], ax
    a.b(0xc7, 0x45, 0x04, 0x00, 0x00)                        # mov word [di+4], 0
    # the set-up runs before the practice's knights are made ready, so a knight's record may still hold a fall of
    # the last fight (HP 0 or less): the Black Knight came in down. It starts with its full HP
    a.b(0x8b, 0x45, 0x3c, 0x85, 0xc0)                        # mov ax, [di+3Ch] / test ax, ax   max HP
    a.short(0x7f, 'sp_hp')                                   # jg sp_hp
    a.b(0xb8, BK_HP, 0x00, 0x89, 0x45, 0x3c)                 # mov ax, 30 / mov [di+3Ch], ax
    a.label('sp_hp')
    a.b(0x89, 0x45, 0x38)                                    # mov [di+38h], ax
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x02)           # cmp byte cs:[bk], 2
    a.short(0x75, 'sp_count')                                # jne sp_count
    a.b(0xc6, 0x45, 0x2e, STRONG, 0xc6, 0x45, 0x2f, STRONG, 0xc6, 0x45, 0x30, STRONG)   # strength, con., endurance
    a.b(0xc7, 0x45, 0x40, CLAYMORE, 0x00, 0xc7, 0x45, 0x42, BATTLE_ARMOUR, 0x00)   # weapon, armour
    a.b(0xc7, 0x45, 0x38, STRONG_HP, 0x00, 0xc7, 0x45, 0x3c, STRONG_HP, 0x00)   # HP, max HP
    a.b(0xc7, 0x45, 0x3e, STRONG_MOVE, 0x00)                 # mov word [di+3Eh], movement
    a.b(0xc6, 0x45, 0x34, B_DAGGERS)                         # mov byte [di+34h], daggers
    a.label('sp_count')
    a.b(0x2e, 0xfe, 0x06); a.word('bk_count')                # inc byte cs:[bk_count]
    a.b(0x07, 0x5f, 0x5e, 0x59, 0x58)                        # pop es di si cx ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done   on at 2826 (the registration)

    # bk_colours_on / off: the B key's knights wear STRONG_BLACK: the fight palette words of +20h = 4 (in MAIN's code,
    # [bp+4]) hold it for the practice, which entries 41-43 are made from; put back at the practice's end
    a.label('bk_colours_on')
    a.b(0x06, 0x50, 0x8e, 0x46, 0x04)                        # push es ax / mov es, [bp+4]
    a.b(0x2e, 0x80, 0x3e); a.word('bk_saved'); a.b(0x00)     # cmp byte cs:[bk_saved], 0
    a.b(0x74, 0x03); a.near(0xe9, 'bkc_end')                                 # jne bkc_end
    for n, (site, value) in enumerate(zip(BLACK_SITES, STRONG_BLACK)):
        a.b(0x26, 0xa1, site & 0xff, site >> 8)              # mov ax, es:[site]
        a.b(0x2e, 0xa3); a.word('bk_old', 2 * n)             # mov cs:[bk_old+n], ax
        a.b(0x2e, 0x80, 0x3e); a.word('dummy'); a.b(0x00); a.short(0x74, f'bkc_b{n}')   # D46: the practice knight in white
        a.b(0x26, 0xc7, 0x06, site & 0xff, site >> 8, DUMMY_WHITE[n] & 0xff, DUMMY_WHITE[n] >> 8); a.short(0xeb, f'bkc_n{n}')
        a.label(f'bkc_b{n}')
        a.b(0x26, 0xc7, 0x06, site & 0xff, site >> 8, value & 0xff, value >> 8)   # mov word es:[site], value
        a.label(f'bkc_n{n}')
    a.b(0x2e, 0xc6, 0x06); a.word('bk_saved'); a.b(0x01)     # mov byte cs:[bk_saved], 1
    a.near(0xe9, 'bkc_end')                                 # jmp bkc_end
    a.label('bk_colours_off')
    a.b(0x06, 0x50, 0x8e, 0x46, 0x04)                        # push es ax / mov es, [bp+4]
    a.b(0x2e, 0x80, 0x3e); a.word('bk_saved'); a.b(0x00)     # cmp byte cs:[bk_saved], 0
    a.b(0x75, 0x03); a.near(0xe9, 'bkc_end')                                 # je bkc_end
    for n, site in enumerate(BLACK_SITES):
        a.b(0x2e, 0xa1); a.word('bk_old', 2 * n)             # mov ax, cs:[bk_old+n]
        a.b(0x26, 0xa3, site & 0xff, site >> 8)              # mov es:[site], ax
    a.b(0x2e, 0xc6, 0x06); a.word('bk_saved'); a.b(0x00)     # mov byte cs:[bk_saved], 0
    a.label('bkc_end')
    a.b(0x58, 0x07, 0xc3)                                    # pop ax es / ret

    # top_up (1000:0243, mov ax,[096Ch]: the next monster comes while fewer are on the screen than at once; the
    # fight's start brings the first ones so): in a Black Knight practice none comes after all of them have
    a.label('rules_top_up')
    a.b(0xa1, 0x6c, 0x09)                                    # mov ax, [096Ch]   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00)           # cmp byte cs:[bk], 0
    a.short(0x74, 'tu_end')                                  # je tu_end
    a.b(0x50, 0x2e, 0xa0); a.word('bk_count')                # push ax / mov al, cs:[bk_count]
    a.b(0x2e, 0x3a, 0x06); a.word('coop'); a.b(0x58)         # cmp al, cs:[coop] / pop ax
    a.short(0x72, 'tu_end')                                  # jb tu_end         not all here yet (the fight's start)
    a.b(0xa1, 0x6e, 0x09)                                    # mov ax, [096Eh]   as many as on the screen: no more
    a.label('tu_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # hit_pair (1000:A14C, or ax,ax after the hit test of a weapon (bp = its animation slot) against a body (bx)):
    # Black Knights do not hurt each other, nor do their daggers
    # The knockback of a blow (the hit's script calls 1000:44DE) goes [782Eh]'s table of steps in [7832h]'s direction,
    # which the monsters set as they strike (1000:56A3) but a knight never does: in a new session [782Eh] = 0 and the
    # steps came from DS:0 (434), a knight flew across the screen. Never 0 now; and in a Black Knight practice a
    # knight's or Black Knight's blow pushes the way the striker faces
    a.label('rules_hit_pair')
    a.b(0x0b, 0xc0)                                          # or ax, ax   (replaced)
    a.short(0x75, 'hp_hit')                                  # jnz hp_hit
    a.near(0xe9, 'hp_flags')                                 # jmp hp_flags   (ZF kept)
    a.label('hp_hit')
    a.near(0xe8, 'td_collide')                               # D46: a blow that lands first stops an overhead chop
    a.b(0x53, 0x8b, 0x5e, 0x00, 0x8b, 0x5f, 0x16)            # push bx / mov bx, [bp+0] / mov bx, [bx+16h]   the game's bp
    a.b(0x83, 0x3e, 0x2e, 0x78, 0x00)                        # cmp word [782Eh], 0
    a.short(0x75, 'hp_table')                                # jne hp_table
    a.b(0xc7, 0x06, 0x2e, 0x78, KNOCKBACK & 0xff, KNOCKBACK >> 8)   # mov word [782Eh], 7818h
    a.label('hp_table')
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00)           # cmp byte cs:[bk], 0
    a.short(0x74, 'hp_pop')                                  # je hp_pop
    a.b(0x80, 0x7f, 0x35, 0x06); a.short(0x74, 'hp_dir')     # cmp byte [bx+35h], 6 / je hp_dir
    a.b(0x80, 0x7f, 0x35, COMPUTER_TYPE); a.short(0x75, 'hp_dagger')   # cmp byte [bx+35h], 8 / jne hp_dagger
    a.label('hp_dir')
    a.b(0x50, 0x8a, 0x47, 0x08, 0xa2, 0x32, 0x78, 0x58)      # push ax / mov al, [bx+8] / mov [7832h], al / pop ax
    a.label('hp_dagger')
    a.b(0x80, 0x7f, 0x35, DAGGER)                            # cmp byte [bx+35h], 1Ah   a dagger: its thrower
    a.short(0x75, 'hp_att')                                  # jne hp_att
    a.b(0x8b, 0x5f, DAGGER_OWNER)                            # mov bx, [bx+5Ch]
    a.label('hp_att')
    a.near(0xe8, 'black_knight')                             # call black_knight
    a.short(0x75, 'hp_pop')                                  # jnz hp_pop
    a.b(0x8b, 0x5e, 0xfe, 0x8b, 0x5f, 0x16)                  # mov bx, [bp-2] / mov bx, [bx+16h]   the game's bx
    a.near(0xe8, 'black_knight')                             # call black_knight
    a.short(0x75, 'hp_pop')                                  # jnz hp_pop
    a.b(0x33, 0xc0)                                          # xor ax, ax   no hit
    a.label('hp_pop')
    # D20: a hit on a player's knight: who hit it (a dagger: the dagger) and its strike (+28h) and type, for its
    # death if it is slumped (death)
    a.b(0x0b, 0xc0); a.short(0x74, 'hp_noted')               # or ax, ax / jz hp_noted
    a.b(0x56, 0x57, 0x8b, 0x76, 0x00, 0x8b, 0x74, 0x16)      # push si di / mov si, [bp+0] / mov si, [si+16h]   hitter
    a.b(0x8b, 0x7e, 0xfe, 0x8b, 0x7d, 0x16)                  # mov di, [bp-2] / mov di, [di+16h]   hit
    a.b(0x53); a.near(0xe8, 'victim_slot')                   # push bx / call victim_slot   a knight or a monster
    a.short(0x72, 'hp_nk_pop')                               # jc hp_nk_pop
    a.b(0x2e, 0x89, 0xb7); a.word('last_hitter')             # mov cs:[bx+last_hitter], si
    a.b(0x50, 0x8a, 0x44, 0x28, 0x8a, 0x64, 0x35)            # push ax / mov al, [si+28h] / mov ah, [si+35h]
    a.b(0x80, 0xfc, DAGGER); a.short(0x75, 'hp_strike')      # cmp ah, 1Ah / jne hp_strike
    # a dagger: al = 1 if it is at the knight's head (its box's top, animation +0Ch, less than 12 below the knight's)
    a.b(0x56, 0x57, 0x8b, 0x76, 0x00, 0x8b, 0x7e, 0xfe)      # push si di / mov si, [bp+0] / mov di, [bp-2]   animations
    a.b(0x8b, 0x74, 0x0c, 0x2b, 0x75, 0x0c, 0xb0, 0x00)      # mov si, [si+0Ch] / sub si, [di+0Ch] / mov al, 0
    a.b(0x83, 0xfe, HEAD_ZONE); a.short(0x7d, 'hp_low')      # cmp si, 12 / jge hp_low
    a.b(0xfe, 0xc0)                                          # inc al
    a.label('hp_low')
    a.b(0x5f, 0x5e)                                          # pop di si
    a.label('hp_strike')
    a.b(0x2e, 0x89, 0x87); a.word('last_strike'); a.b(0x58, 0x5b)   # mov cs:[bx+last_strike], ax / pop ax / pop bx
    a.short(0xeb, 'hp_not_knight')
    a.label('hp_nk_pop')
    a.b(0x5b)                                                # pop bx
    a.label('hp_not_knight')
    a.b(0x5f, 0x5e)                                          # pop di si
    a.label('hp_noted')
    a.b(0x0b, 0xc0); a.short(0x74, 'hp_no_marker')           # or ax, ax / jz hp_no_marker
    a.near(0xe8, 'td_quiet'); a.short(0x72, 'hp_no_marker')  # D46: a defence in time: no marker or extra blood
    a.near(0xe8, 'spawn_marker')                             # call spawn_marker   D22: gore off
    a.near(0xe8, 'spawn_blood')                              # call spawn_blood    ABACABB
    a.label('hp_no_marker')
    a.b(0x5b, 0x0b, 0xc0)                                    # pop bx / or ax, ax
    a.label('hp_flags')
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # dagger_thrower, dagger_owner (1000:3E3B, mov dl,1Ah, di = the thrower; 3E40, mov word [di+1Ah],772Ah, di = the
    # new dagger): the dagger keeps who threw it, so a Black Knight's daggers hurt the knights (practice_hit) and
    # not the other Black Knights (hit_pair)
    # ck_throw (1000:4D45, cmp byte [si+35h],0 before a computer knight's throw, si = it; ZF = 1: no throw, it walks on
    # to its knight): the game threw every time its knight was over 100 away and it had a dagger, and the Black Knights
    # never run out of them: they threw one after another, even from off the screen where they come in
    a.label('rules_ck_throw')
    a.b(0x50, 0x51)                                          # push ax cx
    a.b(0x32, 0xc0)                                          # xor al, al          no throw
    a.b(0x2e, 0x80, 0x3e); a.word('dummy'); a.b(0x00); a.short(0x75, 'ckt_set')   # D46: the practice Purple Knight throws nothing
    a.b(0x80, 0x7c, 0x34, 0x00); a.short(0x74, 'ckt_set')    # cmp byte [si+34h], 0 / je   no daggers (the game's test)
    a.b(0x83, 0x7c, 0x02, THROW_X_MIN); a.short(0x7c, 'ckt_set')   # cmp word [si+2], 10 / jl   off the screen
    a.b(0x81, 0x7c, 0x02, THROW_X_MAX & 0xff, THROW_X_MAX >> 8); a.short(0x7f, 'ckt_set')   # cmp word [si+2], 300 / jg
    a.b(0xbb, ANIM_SLOTS & 0xff, ANIM_SLOTS >> 8, 0xb9, ANIM_COUNT, 0x00)   # mov bx, 947Eh / mov cx, 10
    a.label('ckt_slot')
    a.b(0x80, 0x3f, 0x00); a.short(0x74, 'ckt_next')         # cmp byte [bx], 0 / je   free
    a.b(0x53, 0x8b, 0x5f, 0x16)                              # push bx / mov bx, [bx+16h]
    a.b(0x80, 0x7f, 0x35, DAGGER); a.short(0x75, 'ckt_pop')  # cmp byte [bx+35h], 1Ah / jne
    a.b(0x39, 0x77, DAGGER_OWNER); a.short(0x75, 'ckt_pop')  # cmp [bx+5Ch], si / jne
    a.b(0x5b); a.short(0xeb, 'ckt_set')                      # pop bx / jmp   one of its own is in the air
    a.label('ckt_pop')
    a.b(0x5b)                                                # pop bx
    a.label('ckt_next')
    a.b(0x83, 0xc3, ANIM_SIZE); a.short(0xe2, 'ckt_slot')    # add bx, 24h / loop
    a.near(0xe8, 'game_random')                              # call game_random
    a.b(0x24, THROW_CHANCE); a.short(0x75, 'ckt_no')         # and al, 3 / jnz   no throw this time
    a.b(0xb0, 0x01); a.short(0xeb, 'ckt_set')                # mov al, 1   throw
    a.label('ckt_no')
    a.b(0x32, 0xc0)                                          # xor al, al
    a.label('ckt_set')
    a.b(0x0a, 0xc0, 0x59, 0x58)                              # or al, al / pop cx ax   ZF = 1: no throw
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # ck_shot (1000:4D53, mov [783Ah],ax: a computer knight's throw, ax = its script): D64 GUNSHOT: a shot
    a.label('rules_ck_shot')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_GUNSHOT); a.short(0x74, 'cks_set')
    a.near(0xe8, 'gun_write'); a.b(0xb8, GUN_SHOT & 0xff, GUN_SHOT >> 8)   # call gun_write / mov ax, the shot
    a.label('cks_set')
    a.b(0xa3, 0x3a, 0x78)                                    # mov [783Ah], ax   (replaced)
    a.near(0xe9, 'rules_done')
    # gun_write (ds = MAIN's data): GUNSHOT's scripts and hit points at GUN_AREA (all registers kept)
    a.label('gun_write')
    a.b(0x50, 0x51, 0x56, 0x57, 0xbe); a.word('gun_src')     # push ax cx si di / mov si, gun_src
    a.b(0xbf, GUN_AREA & 0xff, GUN_AREA >> 8, 0xb9, len(GUN_SRC), 0x00)   # mov di, GUN_AREA / mov cx, length
    a.label('gw_copy')
    a.b(0x2e, 0x8a, 0x04, 0x88, 0x05, 0x46, 0x47); a.short(0xe2, 'gw_copy')   # mov al, cs:[si] / mov [di], al / inc si / inc di / loop
    a.b(0x5f, 0x5e, 0x59, 0x58, 0xc3)                        # pop di si cx ax / ret
    # gun_bank (si = a dagger): it and its animation draw from the knights' banks (KN*.OB, where the ball is), also
    # when a duel's second knight (HE*.OB) fired it
    a.label('gun_bank')
    a.b(0x53, 0x57, 0xc7, 0x44, 0x18, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8)   # push bx di / mov word [si+18h], banks
    a.b(0x8b, 0xfe); a.near(0xe8, 'anim_of'); a.short(0x75, 'gb_end')   # mov di, si / call anim_of / jnz
    a.b(0xc7, 0x47, 0x18, KNIGHT_BANK & 0xff, KNIGHT_BANK >> 8)   # mov word [bx+18h], banks
    a.label('gb_end')
    a.b(0x5f, 0x5b, 0xc3)                                    # pop di bx / ret

    a.label('rules_dagger_thrower')
    a.b(0xb2, DAGGER)                                        # mov dl, 1Ah   (replaced)
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_GUNSHOT); a.short(0x74, 'dth_ngun')   # D64: GUNSHOT: a ball
    a.near(0xe8, 'gun_write'); a.b(0xbe, GUN_BALL & 0xff, GUN_BALL >> 8)   # call gun_write / mov si, its first frame
    a.label('dth_ngun')
    a.b(0x2e, 0x89, 0x3e); a.word('thrower')                 # mov cs:[thrower], di
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_DARTS); a.short(0x74, 'dth_bk')   # D48: DARTS: a knight's
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x74, 'dth_back')   # cmp byte [di+35h], 6 / je   (a human's)
    a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, 'dth_bk')   # or a computer's: the one thrown back
    a.label('dth_back')
    a.b(0xfe, 0x45, 0x34); a.short(0xeb, 'dth_end')          # inc byte [di+34h]
    a.label('dth_bk')
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x02)           # cmp byte cs:[bk], 2   the B key's knights:
    a.short(0x75, 'dth_end')                                  # jne dt_end            never out of daggers
    a.b(0x8b, 0xdf); a.near(0xe8, 'black_knight')            # mov bx, di / call black_knight
    a.short(0x75, 'dth_end')                                  # jnz dt_end
    a.b(0xfe, 0x45, 0x34)                                    # inc byte [di+34h]     the one thrown back
    a.label('dth_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('rules_dagger_owner')
    a.b(0xc7, 0x45, 0x1a, 0x2a, 0x77)                        # mov word [di+1Ah], 772Ah   (replaced)
    a.b(0x50, 0x2e, 0xa1); a.word('thrower')                 # push ax / mov ax, cs:[thrower]
    a.b(0x89, 0x45, DAGGER_OWNER, 0x58)                      # mov [di+5Ch], ax / pop ax
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_GUNSHOT); a.short(0x74, 'dow_end')   # D64: the ball's banks
    a.b(0x56, 0x8b, 0xf7); a.near(0xe8, 'gun_bank'); a.b(0x5e)   # push si / mov si, di / call gun_bank / pop si
    a.label('dow_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # dagger_damage (1000:44C2, sub [di+38h],ax: the damage of a dagger (or mudman) hit, si = it): the B key's Black
    # Knights' daggers do double
    # gun_kill (si = the striker, di = the one hit, ax = the damage): D64 GUNSHOT: a ball (a thrown dagger, not one
    # from the sky) that does any damage takes all of the target's HP
    a.label('gun_kill')
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_GUNSHOT); a.short(0x74, 'gk_end')
    a.b(0x80, 0x7c, 0x35, DAGGER); a.short(0x75, 'gk_end')   # cmp byte [si+35h], 1Ah / jne
    a.b(0x39, 0x74, DAGGER_OWNER); a.short(0x74, 'gk_end')   # cmp [si+5Ch], si / je   from the sky
    a.b(0x0b, 0xc0); a.short(0x74, 'gk_end')                 # or ax, ax / jz   no damage (Daggerward)
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'gk_end')     # cmp word [di+38h], 0 / jle
    a.b(0x8b, 0x45, 0x38)                                    # mov ax, [di+38h]
    a.label('gk_end')
    a.b(0xc3)
    # gun_monster (1000:2F46, sub [di+38h],ax: a monster struck, si = the striker; a dagger did 3): D64 GUNSHOT
    a.label('rules_gun_monster')
    a.near(0xe8, 'gun_kill'); a.b(0x29, 0x45, 0x38)          # call gun_kill / sub [di+38h], ax   (replaced)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags   (as the sub left them)

    a.label('rules_dagger_damage')
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x02)           # cmp byte cs:[bk], 2
    a.short(0x75, 'dd_sub')                                  # jne dd_sub
    a.b(0x80, 0x7c, 0x35, DAGGER); a.short(0x75, 'dd_sub')   # cmp byte [si+35h], 1Ah / jne dd_sub
    a.b(0x53, 0x8b, 0x5c, DAGGER_OWNER)                      # push bx / mov bx, [si+5Ch]   the thrower
    a.near(0xe8, 'black_knight'); a.b(0x5b)                  # call black_knight / pop bx
    a.short(0x75, 'dd_sub')                                  # jnz dd_sub
    a.b(0xd1, 0xe0)                                          # shl ax, 1
    a.label('dd_sub')
    a.b(0x80, 0x7c, 0x35, DAGGER); a.short(0x75, 'dd_plain')   # D37: a dagger on a knight with Daggerward: no damage
    a.b(0x50, 0x56, 0x8b, 0xf7); a.near(0xe8, 'arm_of'); a.b(0x3c, A_DAGGER, 0x5e, 0x58); a.short(0x75, 'dd_plain'); a.b(0x33, 0xc0)
    a.label('dd_plain')
    a.near(0xe8, 'td_adjust')                                # D46: a fifth (mistimed block) or double (counter)
    a.near(0xe8, 'gun_kill')                                 # D64: a ball takes all
    a.b(0x29, 0x45, 0x38)                                    # sub [di+38h], ax   (replaced)
    a.b(0xb8, 0x26, 0x44); a.near(0xe9, 'td_after_hit')      # mov ax, 4426h   the blocked reaction if it was a mistimed block

    # D46: timed_defence. A block (move 8) or dodge (move Eh) counts only if it started after the attack's animation did (td_atk, td_note_attack)
    # and within defence_window ticks of its own start; holding it does not restart it. The game's own 4219 still runs first; td_check and td_monster decide from its answer ([77FCh], 1 = no damage).
    # Per record: td_stag (no input until), td_atk (its attack's start), td_pause (a computer knight's attacks without defence);
    # per human knight: td_start, td_seen (the block's start, last seen), td_fast (the next swing starts past its wind-up).
    a.label('td_now')                                        # ax = the BIOS tick
    a.b(0x1e, 0x33, 0xc0, 0x8e, 0xd8, 0xa1, 0x6c, 0x04, 0x1f, 0xc3)   # push ds / xor ax,ax / mov ds,ax / mov ax,[046Ch] / pop ds / ret
    a.label('td_active')                                     # ax = a word "until": CF = 1 while it runs (at most 199 ticks ahead)
    a.b(0x52, 0x8b, 0xd0); a.near(0xe8, 'td_now')            # push dx / mov dx, ax / call td_now
    a.b(0x2b, 0xd0, 0x4a, 0x81, 0xfa, 0xc7, 0x00, 0x5a, 0xc3)   # sub dx, ax / dec dx / cmp dx, 199 / pop dx / ret
    a.label('td_slot')                                       # di = a record: bx = 0-3 knights, 4-23 monster slots; CF = 1 for anything else
    a.b(0x50, 0x52, 0x8b, 0xc7, 0x2d, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8); a.short(0x72, 'tsl_no')   # push ax dx / mov ax, di / sub ax, knights / jb
    a.b(0x3d, (4 * SLOT_SIZE) & 0xff, (4 * SLOT_SIZE) >> 8); a.short(0x72, 'tsl_div')   # cmp ax, 4 records / jb
    a.b(0x8b, 0xc7, 0x2d, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8); a.short(0x72, 'tsl_no')   # mov ax, di / sub ax, monster slots / jb
    a.b(0x33, 0xd2, 0xbb, SLOT_SIZE, 0x00, 0xf7, 0xf3, 0x0b, 0xd2); a.short(0x75, 'tsl_no')   # xor dx,dx / mov bx, size / div bx / or dx,dx / jnz
    a.b(0x3d, MONSTER_COUNT, 0x00); a.short(0x73, 'tsl_no'); a.b(0x05, 0x04, 0x00); a.short(0xeb, 'tsl_end')   # cmp ax, count / jae / add ax, 4 / jmp
    a.label('tsl_div')
    a.b(0x33, 0xd2, 0xbb, SLOT_SIZE, 0x00, 0xf7, 0xf3, 0x0b, 0xd2); a.short(0x75, 'tsl_no')   # xor dx,dx / mov bx, size / div bx / or dx,dx / jnz
    a.label('tsl_end')
    a.b(0x8b, 0xd8, 0x5a, 0x58, 0xf8, 0xc3)                  # mov bx, ax / pop dx ax / clc / ret
    a.label('tsl_no')
    a.b(0x5a, 0x58, 0xf9, 0xc3)                              # pop dx ax / stc / ret
    a.label('td_held')                                       # di = a record: CF = 1 while it is staggered; keeps all registers
    a.b(0xf8, 0x9c, 0x50, 0x53); a.near(0xe8, 'td_slot'); a.short(0x72, 'tdh_no')   # clc / pushf / push ax bx / call td_slot / jc
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('td_stag'); a.near(0xe8, 'td_active'); a.short(0x73, 'tdh_no')   # shl bx,1 / mov ax, cs:[bx+td_stag] / call td_active / jnc
    a.b(0x5b, 0x58, 0x9d, 0xf9, 0xc3)                        # pop bx ax / popf / stc / ret
    a.label('tdh_no')
    a.b(0x5b, 0x58, 0x9d, 0xf8, 0xc3)                        # pop bx ax / popf / clc / ret
    a.label('td_stag_script')                                # di = a knight: ax = its stagger's script: with gore on the flinch C90h (the hit reaction's
    a.b(0xb8, 0x90, 0x0c, 0x83, 0x3e, 0x00, 0x07, 0x00); a.short(0x74, 'tss_end')   # frames have blood), with gore off its hit reaction / mov ax, 0C90h / cmp word [0700h], 0 / je
    a.b(0x53, 0x8b, 0x5d, 0x14, 0x8b, 0x47, 0x04, 0x5b, 0x0b, 0xc0); a.short(0x75, 'tss_end'); a.b(0xb8, 0x90, 0x0c)   # push bx / mov bx,[di+14h] / mov ax,[bx+4] / pop bx / or ax,ax / jnz / mov ax, 0C90h
    a.label('tss_end')
    a.b(0xc3)
    a.label('td_hold')                                       # the input read (ax, di = the knight): nothing while staggered, and the stagger plays on
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tdo_end')   # timed_defence off
    a.near(0xe8, 'td_held'); a.short(0x73, 'tdo_end')        # call td_held / jnc
    a.near(0xe8, 'td_stag_script'); a.b(0xa3, 0x3a, 0x78, 0x33, 0xc0)   # call td_stag_script / mov [783Ah], ax / xor ax, ax
    a.label('tdo_end')
    a.b(0xc3)
    a.label('td_cut')                                        # di = a record, ax = a script: it replaces the record's running script at once
    a.b(0x53); a.near(0xe8, 'anim_of'); a.short(0x75, 'tc_end')   # push bx / call anim_of / jnz
    a.b(0x89, 0x47, 0x02, 0xc6, 0x47, 0x01, 0x01, 0x8b, 0x5f, 0x1c)   # mov [bx+2], ax / mov byte [bx+1], 1 / mov bx, [bx+1Ch]
    a.b(0xc6, 0x47, 0x01, 0x00, 0xc6, 0x47, 0x05, 0x00, 0xc7, 0x47, 0x0a, 0x00, 0x00, 0xc6, 0x47, 0x12, 0x00)   # its repeat, loop, return and jump states off
    a.label('tc_end')
    a.b(0x5b, 0xc3)                                          # pop bx / ret
    a.label('td_stagger')                                    # si = the attacker (a knight), al = ticks: its hit reaction now, then no input for that long
    a.b(0x50, 0x53, 0x57, 0x8b, 0xfe, 0x32, 0xe4, 0x50); a.near(0xe8, 'td_slot'); a.short(0x72, 'tsg_no')   # push ax bx di / mov di, si / xor ah,ah / push ax / call td_slot / jc
    a.near(0xe8, 'td_now'); a.b(0x5a, 0x03, 0xc2, 0xd1, 0xe3, 0x2e, 0x89, 0x87); a.word('td_stag')   # call td_now / pop dx / add ax, dx / shl bx,1 / mov cs:[bx+td_stag], ax
    a.near(0xe8, 'td_stag_script'); a.near(0xe8, 'td_cut')   # call td_stag_script / call td_cut
    a.b(0x51, 0x53); a.near(0xe8, 'anim_of'); a.b(0xb1, 0x00); a.short(0x75, 'tsg_log'); a.b(0x8b, 0x4f, 0x02)   # log: the script its animation runs now (0: none found)
    a.label('tsg_log')
    a.b(0x5b, 0x50, 0xb0, ILOG_STAGGER); a.near(0xe8, 'log_knight'); a.b(0x58, 0x59); a.short(0xeb, 'tsg_end')
    a.label('tsg_no')
    a.b(0x58)                                                # pop ax
    a.label('tsg_end')
    a.b(0x5f, 0x5b, 0x58, 0xc3)                              # pop di bx ax / ret

    # td_collide (from hit_pair, [bp-2] = the struck figure's object, [bp] = the striker's): an overhead chop still in the air when a blow other than
    # a chop lands on its knight is cut (script 11E6h is just the end), so the knight takes the blow at once and the chop never lands
    a.label('td_collide')
    a.b(0x9c, 0x50, 0x53, 0x56, 0x57)                        # pushf / push ax bx si di
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tcl_end')
    a.b(0x8b, 0x5e, 0xfe, 0x8b, 0x7f, 0x16, 0x8b, 0x76, 0x00, 0x8b, 0x74, 0x16)   # mov bx,[bp-2] / mov di,[bx+16h] / mov si,[bp] / mov si,[si+16h]
    a.b(0x83, 0x7d, 0x28, 0x10); a.short(0x75, 'tcl_end')    # cmp word [di+28h], 10h / jne
    a.b(0x83, 0x7d, 0x0c, 0x00); a.short(0x75, 'tcl_end')    # cmp word [di+0Ch], 0 / jne   its chop has already hit
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'tcl_end')    # cmp word [di+38h], 0 / jle
    a.b(0x83, 0x7c, 0x28, 0x10); a.short(0x74, 'tcl_end')    # cmp word [si+28h], 10h / je   chop against chop
    for reg in (0x45, 0x44):                                 # both are knights: al = [di+35h], [si+35h]
        a.b(0x8a, reg, 0x35, 0x3c, 0x06); a.short(0x74, f'tcl_k{reg:x}'); a.b(0x3c, COMPUTER_TYPE); a.short(0x75, 'tcl_end'); a.label(f'tcl_k{reg:x}')
    a.b(0xb8, 0xe6, 0x11); a.near(0xe8, 'td_cut')            # mov ax, 11E6h / call td_cut
    a.label('tcl_end')
    a.b(0x5f, 0x5e, 0x5b, 0x58, 0x9d, 0xc3)                  # pop di si bx ax / popf / ret

    # td_move (1000:40CA, mov [di+28h],ax: a human knight's move): the start of a block or dodge (a gap of more than 4 ticks ends a hold); a swing while
    # the bonus runs starts at 0EAAh, past the wind-up frames of 0E90h. A dodge has no once-only rule with timed defence
    a.label('rules_td_move')
    a.b(0x89, 0x45, 0x28)                                    # (replaced)
    a.b(0x3d, 0x06, 0x00); a.short(0x75, 'tm_ngun')          # cmp ax, 6 / jne   D64: GUNSHOT: the throw is a shot
    a.b(0x2e, 0xf6, 0x06); a.word('cheat_flags2'); a.b(F2_GUNSHOT); a.short(0x74, 'tm_ngun')
    a.near(0xe8, 'gun_write')                                # call gun_write
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tm_gun')
    a.b(0x52); a.near(0xe8, 'knight_no'); a.short(0x72, 'tm_gfk'); a.b(0x2e, 0xc6, 0x87); a.word('td_fk'); a.b(0x00)   # as below
    a.label('tm_gfk')
    a.b(0x5a)                                                # pop dx
    a.label('tm_gun')
    a.b(0xc7, 0x06, 0x3a, 0x78, GUN_SHOT & 0xff, GUN_SHOT >> 8); a.near(0xe9, 'tmv_go')   # mov word [783Ah], the shot
    a.label('tm_ngun')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tm_done')
    a.b(0x52); a.near(0xe8, 'knight_no'); a.short(0x72, 'tm_nfk'); a.b(0x2e, 0xc6, 0x87); a.word('td_fk'); a.b(0x00)   # push dx / call knight_no / jc / mov byte cs:[bx+td_fk], 0
    a.label('tm_nfk')
    a.b(0x5a)                                                # pop dx
    a.b(0x3d, 0x0a, 0x00); a.short(0x75, 'tm_nb')             # cmp ax, 0Ah / jne
    a.b(0xc7, 0x06, 0x3a, 0x78, 0xb6, 0x0d); a.near(0xe9, 'tmv_go')   # mov word [783Ah], 0DB6h   the back thrust at once: the fastest blow
    a.label('tm_nb')
    a.b(0x3d, 0x02, 0x00); a.short(0x75, 'tm_nr')             # cmp ax, 2 / jne
    a.near(0xe8, 'td_foe_chop'); a.short(0x73, 'tm_done')     # call td_foe_chop / jnc   a riposte only against a chop in the air
    a.b(0x52); a.near(0xe8, 'knight_no'); a.short(0x72, 'tm_rfk'); a.b(0x2e, 0xc6, 0x87); a.word('td_fk'); a.b(0x02)   # the riposte
    a.label('tm_rfk')
    a.b(0x5a)                                                # pop dx
    a.b(0xc7, 0x06, 0x3a, 0x78, 0x2a, 0x10); a.near(0xe9, 'tmv_go')   # mov word [783Ah], 102Ah   the lunge past its wind-up
    a.label('tm_nr')
    a.b(0x3d, 0x04, 0x00); a.short(0x74, 'tm_swing')         # cmp ax, 4 / je
    a.b(0x3d, 0x08, 0x00); a.short(0x74, 'tm_def')           # cmp ax, 8 / je
    a.b(0x3d, 0x0e, 0x00); a.short(0x75, 'tm_done')          # cmp ax, 0Eh / jne
    a.b(0x80, 0x65, 0x48, 0x7f)                              # and byte [di+48h], 7Fh
    a.label('tm_def')
    a.b(0x50, 0x52); a.near(0xe8, 'knight_no'); a.short(0x72, 'tm_pop')   # push ax dx / call knight_no / jc
    a.b(0xd1, 0xe3); a.near(0xe8, 'td_now'); a.b(0x8b, 0xd0, 0x2e, 0x2b, 0x87); a.word('td_seen')   # shl bx,1 / call td_now / mov dx, ax / sub ax, cs:[bx+td_seen]
    a.b(0x3d, 0x04, 0x00); a.short(0x76, 'tm_held')          # cmp ax, 4 / jbe
    a.b(0x2e, 0x89, 0x97); a.word('td_start')                # mov cs:[bx+td_start], dx
    a.label('tm_held')
    a.b(0x2e, 0x89, 0x97); a.word('td_seen')                 # mov cs:[bx+td_seen], dx
    a.label('tm_pop')
    a.b(0x5a, 0x58)                                          # pop dx ax
    a.label('tm_done')
    a.near(0xe9, 'rules_done')
    a.label('tm_swing')
    a.b(0x50, 0x52); a.near(0xe8, 'knight_no'); a.short(0x72, 'tm_pop')   # push ax dx / call knight_no / jc
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x87); a.word('td_fast'); a.near(0xe8, 'td_active'); a.short(0x73, 'tm_pop')   # shl bx,1 / mov ax, cs:[bx+td_fast] / call td_active / jnc
    a.b(0x2e, 0xc7, 0x87); a.word('td_fast'); a.b(0x00, 0x00)   # mov word cs:[bx+td_fast], 0   once
    a.b(0xd1, 0xeb, 0x2e, 0xc6, 0x87); a.word('td_fk'); a.b(0x01)   # shr bx,1 / mov byte cs:[bx+td_fk], 1   the fast swing
    a.b(0x5a, 0x58, 0xc7, 0x06, 0x3a, 0x78, 0xaa, 0x0e)       # pop dx ax / mov word [783Ah], 0EAAh
    a.label('tmv_go')
    a.b(0xc7, 0x46, 0x02, 0x5e, 0x2d); a.near(0xe9, 'rules_done')   # mov word [bp+2], 2D5Eh
    # td_foe_chop (di = the knight): CF = 1 if a knight facing it has a chop in the air
    a.label('td_foe_chop')
    a.b(0x50, 0x51, 0x56, 0xbe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8, 0xb9, 0x04, 0x00); a.near(0xe8, 'td_scan'); a.short(0x72, 'tfc_end')   # push ax cx si / mov si, knights / mov cx, 4 / call td_scan / jc
    a.b(0xbe, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb9, MONSTER_COUNT, 0x00); a.near(0xe8, 'td_scan')   # mov si, monster slots / mov cx, count / call td_scan
    a.label('tfc_end')
    a.b(0x5e, 0x59, 0x58, 0xc3)                               # pop si cx ax / ret
    a.label('td_scan')
    a.b(0x3b, 0xf7); a.short(0x74, 'ts_next')                 # cmp si, di / je
    a.b(0x8a, 0x44, 0x35, 0x3c, 0x06); a.short(0x74, 'ts_k'); a.b(0x3c, COMPUTER_TYPE); a.short(0x75, 'ts_next')   # type: a knight
    a.label('ts_k')
    a.b(0x83, 0x7c, 0x28, 0x10); a.short(0x75, 'ts_next')     # cmp word [si+28h], 10h / jne
    a.b(0x83, 0x7c, 0x38, 0x00); a.short(0x7e, 'ts_next')     # cmp word [si+38h], 0 / jle
    a.b(0x83, 0x7c, 0x0c, 0x00); a.short(0x75, 'ts_next')     # cmp word [si+0Ch], 0 / jne   its chop has hit
    a.b(0x8a, 0x44, 0x08, 0x3a, 0x45, 0x08); a.short(0x74, 'ts_next')   # mov al,[si+8] / cmp al,[di+8] / je   same facing
    a.b(0xf9, 0xc3)                                           # stc / ret
    a.label('ts_next')
    a.b(0x83, 0xc6, SLOT_SIZE); a.short(0xe2, 'td_scan'); a.b(0xf8, 0xc3)   # add si, size / loop / clc / ret

    # td_check (1000:441F and 4D6C, cmp word [77FCh],0 after CheckBlock: di = the struck knight, si = what struck it, a knight or (at 4D6C) a dagger)
    a.label('rules_td_check')
    a.b(0x50, 0x51, 0x52)                                    # push ax cx dx
    a.b(0x2e, 0xc6, 0x06); a.word('td_mist'); a.b(0x00)      # mov byte cs:[td_mist], 0
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x75, 'tk_on')
    a.label('tk_game_1')
    a.near(0xe9, 'tk_game')
    a.label('tk_on')
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'tk_game_1')  # cmp word [di+38h], 0 / jle
    a.near(0xe8, 'td_kind')                                  # call td_kind   cl: 1 swing, 3 thrust or chop, 0 anything else
    a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x74, 'tk_cpu')   # cmp byte [di+35h], 8 / je
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x75, 'tk_game_1')  # cmp byte [di+35h], 6 / jne
    a.near(0xe8, 'td_judge'); a.b(0x3c, 0x02); a.short(0x74, 'tk_mist_1'); a.b(0x0a, 0xc0); a.short(0x74, 'tk_none')   # call td_judge / cmp al, 2 / je / or al, al / jz
    a.b(0x3c, 0x01); a.short(0x74, 'tk_h_block')              # cmp al, 1 / je
    a.b(0x80, 0xf9, 0x04); a.short(0x75, 'tk_h_stag'); a.near(0xe9, 'tk_stop')   # cmp cl, 4 / jne   a dodged thrust: stagger; a dodged chop just misses
    a.label('tk_h_block')
    a.b(0x53, 0x52); a.near(0xe8, 'knight_no'); a.short(0x72, 'tk_h_nf'); a.b(0xd1, 0xe3); a.near(0xe8, 'td_now')   # push bx dx / call knight_no / jc / shl bx,1 / call td_now
    a.b(0x33, 0xd2, 0x2e, 0x8a, 0x16); a.word('rules_table', G_TD_FAST); a.b(0x03, 0xc2, 0x2e, 0x89, 0x87); a.word('td_fast')   # xor dx,dx / mov dl, cs:[fast] / add ax, dx / mov cs:[bx+td_fast], ax
    a.label('tk_h_nf')
    a.b(0x5a, 0x5b)                                          # pop dx bx
    a.label('tk_h_stag')
    a.b(0x2e, 0xa0); a.word('rules_table', G_TD_STAGGER); a.near(0xe8, 'td_stagger'); a.near(0xe9, 'tk_stop')   # mov al, cs:[stagger] / call td_stagger / jmp
    a.label('tk_mist_1')
    a.near(0xe9, 'tk_mist')
    a.label('tk_none')
    a.b(0xc7, 0x06, 0xfc, 0x77, 0x00, 0x00); a.near(0xe9, 'tk_game')   # mov word [77FCh], 0   no defence
    # a computer knight: smart ones roll once per attack, classic ones keep the game's block
    a.label('tk_cpu')
    a.b(0x2e, 0x80, 0x3e); a.word('dummy'); a.b(0x00); a.short(0x75, 'tk_smart')   # the practice Purple Knight
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_BK_AI); a.b(0x00); a.short(0x75, 'tk_smart'); a.near(0xe9, 'tk_game')
    a.label('tk_smart')
    a.near(0xe8, 'td_cpu')
    a.b(0x3c, 0x01); a.short(0x74, 'tk_c_good')
    a.b(0x3c, 0x02); a.short(0x74, 'tk_c_mis'); a.near(0xe9, 'tk_none')
    a.label('tk_c_mis')
    a.b(0xc7, 0x45, 0x28, 0x08, 0x00)                        # mov word [di+28h], 8   shows a block
    a.label('tk_mist')
    a.b(0x2e, 0xc6, 0x06); a.word('td_mist'); a.b(0x01)      # mov byte cs:[td_mist], 1
    a.near(0xe9, 'tk_none')
    a.label('tk_c_good')
    a.b(0xb8, 0x08, 0x00, 0x80, 0xf9, 0x01); a.short(0x74, 'tk_c_move'); a.b(0xb0, 0x0e)   # mov ax, 8 / cmp cl, 1 / je / mov al, 0Eh
    a.label('tk_c_move')
    a.b(0x89, 0x45, 0x28, 0x80, 0xf9, 0x04); a.short(0x74, 'tk_stop_c')   # mov [di+28h], ax / cmp cl, 4 / je   a dodged chop: no stagger
    a.b(0x2e, 0xa0); a.word('rules_table', G_TD_STAGGER); a.b(0xd0, 0xe8); a.near(0xe8, 'td_stagger')   # mov al, cs:[stagger] / shr al, 1 / call td_stagger
    a.label('tk_stop_c')
    a.label('tk_stop')
    a.b(0xc7, 0x06, 0xfc, 0x77, 0x01, 0x00)                  # mov word [77FCh], 1
    a.label('tk_game')
    a.b(0x8a, 0x0e, 0xfc, 0x77, 0x8a, 0x6c, 0x28, 0xb0, ILOG_DEFENCE); a.near(0xe8, 'log_knight')   # log: defended (1) or not, the blow's move
    a.b(0x5a, 0x59, 0x58, 0x83, 0x3e, 0xfc, 0x77, 0x00); a.near(0xe9, 'rules_flags')   # pop dx cx ax / cmp word [77FCh], 0  (replaced)
    # td_cpu (di = a computer knight, si = its attacker, cl = td_kind): al = 1 defends in time (it succeeds), 2 too late, 0 no defence. The roll is made once per
    # attack, at the first contact (td_quiet, so no marker follows a defence) and kept by the attack's start (td_atk) in td_roll / td_rolled.
    # The practice Purple Knight always defends what can be defended
    a.label('td_cpu')
    a.b(0x53, 0x52, 0x0a, 0xc9); a.b(0x75, 0x03); a.near(0xe9, 'tcp_none')   # push bx dx / or cl, cl / jz
    a.b(0x2e, 0x80, 0x3e); a.word('dummy'); a.b(0x00); a.short(0x74, 'tcp_cpu')   # cmp byte cs:[dummy], 0 / je
    a.b(0xb0, 0x01); a.near(0xe9, 'tcp_end')                 # mov al, 1
    a.label('tcp_cpu')
    a.near(0xe8, 'td_slot'); a.short(0x72, 'tcp_none_1')     # call td_slot / jc
    a.b(0x53, 0xd1, 0xe3); a.near(0xe8, 'td_now'); a.b(0x2e, 0x2b, 0x87); a.word('td_atk'); a.b(0x5b, 0x3d, TD_OWN_ATTACK, 0x00); a.short(0x73, 'tcp_free')   # its own attack began under 30 ticks ago:
    a.label('tcp_none_1')
    a.near(0xe9, 'tcp_none')                                 # no defence
    a.label('tcp_free')
    a.b(0x90); a.b(0x73, 0x03); a.near(0xe9, 'tcp_none')       # call td_slot / jc
    a.b(0x53, 0x57, 0x8b, 0xfe); a.near(0xe8, 'td_slot'); a.short(0x72, 'tcp_na')   # push bx di / mov di, si / call td_slot / jc
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x97); a.word('td_atk'); a.short(0xeb, 'tcp_st')   # shl bx,1 / mov dx, cs:[bx+td_atk] / jmp
    a.label('tcp_na')
    a.b(0x33, 0xd2)                                          # xor dx, dx
    a.label('tcp_st')
    a.b(0x5f, 0x5b, 0x53, 0xd1, 0xe3, 0x2e, 0x3b, 0x97); a.word('td_rolled'); a.b(0x5b); a.short(0x75, 'tcp_fresh')   # pop di bx / push bx / shl bx,1 / cmp dx, cs:[bx+td_rolled] / pop bx / jne
    a.b(0x2e, 0x8a, 0x87); a.word('td_roll'); a.b(0x0a, 0xc0); a.short(0x74, 'tcp_fresh'); a.near(0xe9, 'tcp_map')   # mov al, cs:[bx+td_roll] / or al, al / jz / jmp
    a.label('tcp_fresh')
    a.b(0x2e, 0x80, 0xbf); a.word('td_pause'); a.b(0x00); a.short(0x74, 'tcp_r')   # cmp byte cs:[bx+td_pause], 0 / je
    a.b(0x2e, 0xfe, 0x8f); a.word('td_pause'); a.b(0xb0, 0x03); a.near(0xe9, 'tcp_store')   # dec byte cs:[bx+td_pause] / mov al, 3
    a.label('tcp_r')
    a.b(0x52); a.near(0xe8, 'game_random')                   # push dx / call game_random (keeps bx, cx)
    a.b(0x53, 0x33, 0xd2, 0xbb, 0x64, 0x00, 0xf7, 0xf3, 0x5b)   # push bx / xor dx,dx / mov bx, 100 / div bx / pop bx   dl = 0-99
    a.b(0x2e, 0xa1); a.word('rules_table', G_TD_PURPLE); a.b(0x83, 0xfb, 0x04); a.short(0x72, 'tcp_pct')   # mov ax, cs:[purple] / cmp bx, 4 / jb
    a.b(0x2e, 0xa1); a.word('rules_table', G_TD_BLACK)       # mov ax, cs:[black]
    a.label('tcp_pct')
    a.b(0x80, 0xf9, 0x03); a.short(0x72, 'tcp_cmp'); a.b(0xd0, 0xe8, 0x32, 0xe4)   # cmp cl, 3 / jb / shr al, 1 / xor ah, ah   thrust, chop: half, no mistiming
    a.label('tcp_cmp')
    a.b(0x38, 0xc2); a.short(0x72, 'tcp_good')               # cmp dl, al / jb
    a.b(0x02, 0xc4, 0x38, 0xc2, 0xb0, 0x03); a.short(0x73, 'tcp_s'); a.b(0xb0, 0x02); a.short(0xeb, 'tcp_s')   # add al, ah / cmp dl, al / mov al, 3 / jae / mov al, 2 / jmp
    a.label('tcp_good')
    a.b(0x2e, 0xa0); a.word('rules_table', G_TD_PAUSE); a.b(0x2e, 0x88, 0x87); a.word('td_pause'); a.b(0xb0, 0x01)   # mov al, cs:[pause] / mov cs:[bx+td_pause], al / mov al, 1
    a.label('tcp_s')
    a.b(0x5a)                                                # pop dx
    a.label('tcp_store')
    a.b(0x2e, 0x88, 0x87); a.word('td_roll'); a.b(0x53, 0xd1, 0xe3, 0x2e, 0x89, 0x97); a.word('td_rolled'); a.b(0x5b)   # mov cs:[bx+td_roll], al / push bx / shl bx,1 / mov cs:[bx+td_rolled], dx / pop bx
    a.label('tcp_map')
    a.b(0x3c, 0x03); a.short(0x75, 'tcp_end')                # cmp al, 3 / jne
    a.label('tcp_none')
    a.b(0x32, 0xc0)                                          # xor al, al
    a.label('tcp_end')
    a.b(0x5a, 0x5b, 0xc3)                                    # pop dx bx / ret
    # dm_attack (si = the practice knight in place, di = its foe): CF = 1 and its attack's script in [783Ah] when it is due: 10 s (182 ticks) after its
    # foe's last attack, then every 4-6 s; a chop, a lunge or a swing at random. A new attack of the foe (its td_atk) starts the 10 s again
    a.label('dm_attack')
    a.b(0x50, 0x53, 0x52, 0x57); a.near(0xe8, 'td_slot'); a.b(0x73, 0x03); a.near(0xe9, 'dma_no')   # push ax bx dx di / call td_slot (the foe) / jc
    a.b(0xd1, 0xe3, 0x2e, 0x8b, 0x97); a.word('td_atk')      # shl bx,1 / mov dx, cs:[bx+td_atk]
    a.b(0x8b, 0xfe); a.near(0xe8, 'td_slot'); a.b(0x73, 0x03); a.near(0xe9, 'dma_no'); a.b(0xd1, 0xe3)   # mov di, si / call td_slot / jc / shl bx,1
    a.b(0x2e, 0x3b, 0x97); a.word('dm_seen'); a.short(0x74, 'dma_same')   # cmp dx, cs:[bx+dm_seen] / je
    a.b(0x2e, 0x89, 0x97); a.word('dm_seen'); a.short(0xeb, 'dma_reset')   # mov cs:[bx+dm_seen], dx / jmp
    a.label('dma_same')
    a.b(0x2e, 0x83, 0xbf); a.word('dm_next'); a.b(0x00); a.short(0x75, 'dma_have')   # cmp word cs:[bx+dm_next], 0 / jne
    a.label('dma_reset')
    a.near(0xe8, 'td_now'); a.b(0x05, 0xb6, 0x00, 0x2e, 0x89, 0x87); a.word('dm_next'); a.near(0xe9, 'dma_no')   # call td_now / add ax, 182 / mov cs:[bx+dm_next], ax
    a.label('dma_have')
    a.near(0xe8, 'td_now'); a.b(0x2e, 0x2b, 0x87); a.word('dm_next'); a.b(0xf6, 0xc4, 0x80); a.b(0x74, 0x03); a.near(0xe9, 'dma_no')   # now - next < 0: not yet
    a.near(0xe8, 'game_random'); a.b(0x33, 0xd2, 0x53, 0xbb, 0x25, 0x00, 0xf7, 0xf3, 0x5b)   # dx = random 0-36
    a.near(0xe8, 'td_now'); a.b(0x03, 0xc2, 0x05, 0x49, 0x00, 0x2e, 0x89, 0x87); a.word('dm_next')   # next = now + 73-109 (4-6 s)
    a.b(0x2e, 0x8b, 0x97); a.word('dm_seq'); a.b(0x52, 0x42, 0x83, 0xfa, 0x03); a.short(0x72, 'dma_seq'); a.b(0x33, 0xd2)   # mov dx, cs:[bx+dm_seq] / inc dx / cmp dx, 3 / jb / xor dx, dx
    a.label('dma_seq')
    a.b(0x2e, 0x89, 0x97); a.word('dm_seq'); a.b(0x5a)       # mov cs:[bx+dm_seq], dx / pop dx   this one: 0 swing, 1 lunge, 2 chop
    a.b(0xb8, 0x04, 0x00, 0x0b, 0xd2); a.short(0x74, 'dma_set'); a.b(0xb0, 0x02, 0x4a); a.short(0x74, 'dma_set'); a.b(0xb0, 0x10)   # mov ax, 4 / or dx,dx / jz / mov al, 2 / dec dx / jz / mov al, 10h
    a.label('dma_set')
    a.b(0x53, 0xd1, 0xeb, 0x2e, 0xc6, 0x87); a.word('td_fk'); a.b(0x00, 0x5b)   # push bx / shr bx,1 / mov byte cs:[bx+td_fk], 0 / pop bx   an ordinary blow
    a.b(0x89, 0x44, 0x28, 0x8b, 0x5c, 0x16, 0x03, 0xd8, 0x8b, 0x07, 0xa3, 0x3a, 0x78)   # mov [si+28h], ax / mov bx,[si+16h] / add bx, ax / mov ax,[bx] / mov [783Ah], ax
    a.b(0x5f, 0x5a, 0x5b, 0x58, 0xf9, 0xc3)                  # pop di dx bx ax / stc / ret
    a.label('dma_no')
    a.b(0x5f, 0x5a, 0x5b, 0x58, 0xf8, 0xc3)                  # pop di dx bx ax / clc / ret
    a.label('dm_wait')                                       # si = the practice knight: its first attack 10 s from now
    a.b(0x50, 0x53, 0x57, 0x8b, 0xfe); a.near(0xe8, 'td_slot'); a.short(0x72, 'dmw_end')   # push ax bx di / mov di, si / call td_slot / jc
    a.b(0xd1, 0xe3); a.near(0xe8, 'td_now'); a.b(0x05, 0xb6, 0x00, 0x2e, 0x89, 0x87); a.word('dm_next')   # shl bx,1 / call td_now / add ax, 182 / mov cs:[bx+dm_next], ax
    a.label('dmw_end')
    a.b(0x5f, 0x5b, 0x58, 0xc3)                              # pop di bx ax / ret
    # td_fast_dmg (ax = a blow's base damage, si = the striker): the fast swing does a lunge's (move 2), the riposte a backward thrust's (move 0Ah)
    a.label('td_fast_dmg')
    a.b(0x53, 0x57, 0x8b, 0xfe); a.near(0xe8, 'td_slot'); a.short(0x72, 'tfd_end')   # push bx di / mov di, si / call td_slot / jc
    a.b(0x2e, 0x80, 0xbf); a.word('td_fk'); a.b(0x01); a.short(0x75, 'tfd_r')   # cmp byte cs:[bx+td_fk], 1 / jne
    a.b(0x83, 0x7c, 0x28, 0x04); a.short(0x75, 'tfd_end'); a.b(0x8b, 0x5c, 0x1a, 0x8b, 0x47, 0x02); a.short(0xeb, 'tfd_end')   # the swing: mov bx,[si+1Ah] / mov ax,[bx+2]
    a.label('tfd_r')
    a.b(0x2e, 0x80, 0xbf); a.word('td_fk'); a.b(0x02); a.short(0x75, 'tfd_end')   # cmp byte cs:[bx+td_fk], 2 / jne
    a.b(0x83, 0x7c, 0x28, 0x02); a.short(0x75, 'tfd_end'); a.b(0x8b, 0x5c, 0x1a, 0x8b, 0x47, 0x0a)   # the lunge: mov bx,[si+1Ah] / mov ax,[bx+0Ah]
    a.label('tfd_end')
    a.b(0x5f, 0x5b, 0xc3)                                    # pop di bx / ret
    a.label('td_kind')                                       # si = what struck: cl = 1 swing, 3 thrust, 4 chop, 0 anything else (daggers)
    a.b(0x8b, 0x44, 0x28, 0xb1, 0x01, 0x3d, 0x04, 0x00); a.short(0x74, 'tkd_end')   # mov ax,[si+28h] / mov cl, 1 / cmp ax, 4 / je
    a.b(0xb1, 0x03)                                          # mov cl, 3
    for move in (0x02, 0x0a, 0x0c):
        a.b(0x3d, move, 0x00); a.short(0x74, 'tkd_end')      # cmp ax, move / je
    a.b(0xb1, 0x04, 0x3d, 0x10, 0x00); a.short(0x74, 'tkd_end')   # mov cl, 4 / cmp ax, 10h / je   the chop
    a.b(0xb1, 0x00)                                          # mov cl, 0
    a.label('tkd_end')
    a.b(0xc3)
    a.label('td_judge')                                      # di = a human knight, si = its attacker, cl = td_kind: al = 0 no defence, 1 block in time, 2 block too early or late, 3 dodge in time
    a.b(0x53, 0x52); a.near(0xe8, 'knight_no'); a.short(0x72, 'tj_none'); a.b(0xd1, 0xe3)   # push bx dx / call knight_no / jc / shl bx,1
    a.b(0x80, 0xf9, 0x01); a.short(0x75, 'tj_dodge')          # cmp cl, 1 / jne
    a.b(0x83, 0x7d, 0x28, 0x08); a.short(0x75, 'tj_none')     # cmp word [di+28h], 8 / jne
    a.b(0x8a, 0x45, 0x08, 0x3a, 0x44, 0x08); a.short(0x74, 'tj_none')   # mov al,[di+8] / cmp al,[si+8] / je   from behind
    a.near(0xe8, 'td_window'); a.b(0xb0, 0x02); a.short(0x73, 'tj_end'); a.b(0xb0, 0x01); a.short(0xeb, 'tj_end')   # call td_window / mov al, 2 / jnc / mov al, 1 / jmp
    a.label('tj_dodge')
    a.b(0x80, 0xf9, 0x03); a.short(0x72, 'tj_none')           # cmp cl, 3 / jb   a thrust or a chop
    a.b(0x83, 0x7d, 0x28, 0x0e); a.short(0x75, 'tj_none')     # cmp word [di+28h], 0Eh / jne
    a.near(0xe8, 'td_window'); a.b(0xb0, 0x03); a.short(0x72, 'tj_end')   # call td_window / mov al, 3 / jc
    a.label('tj_none')
    a.b(0x32, 0xc0)                                          # xor al, al
    a.label('tj_end')
    a.b(0x5a, 0x5b, 0xc3)                                    # pop dx bx / ret
    a.label('td_window')                                     # bx = knight * 2, si = the attacker: CF = 1 if the defence started after the attack and within defence_window
    a.b(0x50, 0x52); a.near(0xe8, 'td_now'); a.b(0x8b, 0xd0, 0x2e, 0x2b, 0x87); a.word('td_start')   # push ax dx / call td_now / mov dx, ax / sub ax, cs:[bx+td_start]
    a.b(0x51, 0x33, 0xc9, 0x2e, 0x8a, 0x0e); a.word('rules_table', G_TD_WINDOW); a.b(0x3b, 0xc1, 0x59); a.short(0x77, 'tw_fail')   # push cx / xor cx,cx / mov cl, cs:[window] / cmp ax, cx / pop cx / ja
    a.b(0x53, 0x57, 0x8b, 0xfe); a.near(0xe8, 'td_slot'); a.short(0x72, 'tw_pass')   # push bx di / mov di, si / call td_slot / jc
    a.b(0xd1, 0xe3, 0x2e, 0x2b, 0x97); a.word('td_atk'); a.b(0x3b, 0xc2, 0x5f, 0x5b); a.short(0x77, 'tw_fail'); a.short(0xeb, 'tw_ok')   # shl bx,1 / sub dx, cs:[bx+td_atk] / cmp ax, dx / pop di bx / ja / jmp
    a.label('tw_pass')
    a.b(0x5f, 0x5b)                                          # pop di bx
    a.label('tw_ok')
    a.b(0x5a, 0x58, 0xf9, 0xc3)                              # pop dx ax / stc / ret
    a.label('tw_fail')
    a.b(0x5a, 0x58, 0xf8, 0xc3)                              # pop dx ax / clc / ret
    # td_note_attack (di = an object at the end of its control, [783Ah] its next script): a knight's new attack: when it started, per record
    a.label('td_note_attack')
    a.b(0x50, 0x53, 0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tna_end')   # push ax bx / timed_defence off
    a.b(0x81, 0x3e, 0x3a, 0x78, 0xff, 0xff); a.short(0x74, 'tna_end')   # cmp word [783Ah], 0FFFFh / je   no new script
    a.b(0x8a, 0x45, 0x35, 0x3c, 0x06); a.short(0x74, 'tna_k'); a.b(0x3c, COMPUTER_TYPE); a.short(0x75, 'tna_end')   # a knight
    a.label('tna_k')
    a.b(0x8b, 0x45, 0x28)                                    # mov ax, [di+28h]
    for move in (0x02, 0x04, 0x0a, 0x0c):
        a.b(0x3d, move, 0x00); a.short(0x74, 'tna_go')
    a.b(0x3d, 0x10, 0x00); a.short(0x75, 'tna_end')          # cmp ax, 10h / jne
    a.label('tna_go')
    a.b(0x8b, 0x1e, 0x3a, 0x78)                              # mov bx, [783Ah]   the new script: the move's own, or a fast start
    for fast in (0x0eaa, 0x0db6, 0x102a):
        a.b(0x81, 0xfb, fast & 0xff, fast >> 8); a.short(0x74, f'tna_new_{fast:x}')
    a.b(0x53, 0x8b, 0x5d, 0x16, 0x03, 0xd8, 0x8b, 0x07, 0x5b, 0x3b, 0xc3); a.short(0x74, 'tna_new')   # push bx / mov bx,[di+16h] / add bx, ax / mov ax,[bx] / pop bx / cmp ax, bx / je
    a.near(0xe9, 'tna_end')
    for fast in (0x0eaa, 0x0db6, 0x102a):
        a.label(f'tna_new_{fast:x}')
    a.label('tna_new')
    a.near(0xe8, 'td_slot'); a.short(0x72, 'tna_end'); a.b(0xd1, 0xe3); a.near(0xe8, 'td_now'); a.b(0x2e, 0x89, 0x87); a.word('td_atk')   # call td_slot / jc / shl bx,1 / call td_now / mov cs:[bx+td_atk], ax
    a.b(0x51, 0x8a, 0x4d, 0x28, 0x8a, 0xeb, 0xd0, 0xed, 0xb0, ILOG_ATTACK); a.near(0xe8, 'log_knight'); a.b(0x59)   # log: its move, its record's slot
    a.label('tna_end')
    a.b(0x5b, 0x58, 0xc3)                                    # pop bx ax / ret
    # td_quiet (from hit_pair, a blow landed): CF = 1 if its victim is a human knight that defends in time: no hit marker or extra blood
    a.label('td_quiet')
    a.b(0x50, 0x51, 0x56, 0x57, 0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tq_no')   # push ax cx si di / timed_defence off
    a.b(0x8b, 0x76, 0x00, 0x8b, 0x74, 0x16, 0x8b, 0x7e, 0xfe, 0x8b, 0x7d, 0x16)   # mov si,[bp] / mov si,[si+16h] / mov di,[bp-2] / mov di,[di+16h]
    a.b(0x8a, 0x44, 0x35, 0x3c, 0x06); a.short(0x74, 'tq_k'); a.b(0x3c, COMPUTER_TYPE); a.short(0x75, 'tq_no')   # the striker is a knight
    a.label('tq_k')
    a.near(0xe8, 'td_kind')                                  # cl = the blow's kind
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x75, 'tq_cpu')     # cmp byte [di+35h], 6 / jne
    a.near(0xe8, 'td_judge'); a.b(0x3c, 0x01); a.short(0x74, 'tq_yes'); a.b(0x3c, 0x03); a.short(0x74, 'tq_yes'); a.short(0xeb, 'tq_no')   # a human
    a.label('tq_cpu')
    a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, 'tq_no')   # cmp byte [di+35h], 8 / jne
    a.b(0x2e, 0x80, 0x3e); a.word('dummy'); a.b(0x00); a.short(0x75, 'tq_roll')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_BK_AI); a.b(0x00); a.short(0x74, 'tq_no')   # classic: the game's block
    a.label('tq_roll')
    a.near(0xe8, 'td_cpu'); a.b(0x3c, 0x01); a.short(0x74, 'tq_yes')   # call td_cpu / cmp al, 1 / je
    a.label('tq_no')
    a.b(0x5f, 0x5e, 0x59, 0x58, 0xf8, 0xc3)                  # pop di si cx ax / clc / ret
    a.label('tq_yes')
    a.b(0x5f, 0x5e, 0x59, 0x58, 0xf9, 0xc3)                  # pop di si cx ax / stc / ret
    a.label('td_window_trogg')                               # bx = knight * 2: CF = 1 within 6 ticks of the block's start (troggs have no attack start here)
    a.b(0x50); a.near(0xe8, 'td_now'); a.b(0x2e, 0x2b, 0x87); a.word('td_start'); a.b(0x3d, 0x07, 0x00, 0x58, 0xc3)   # push ax / call td_now / sub ax, cs:[bx+td_start] / cmp ax, 7 / pop ax / ret

    # td_monster (1000:42D8 axe troggs, 432A spear troggs: the same cmp): a block the game would allow counts only in the window. Out of it: the
    # axe's hit is a fifth, the spear's in full. A block in time also gives the fast swing; troggs do not stagger
    a.label('rules_td_monster')
    a.b(0x50, 0x53, 0x52)                                    # push ax bx dx
    a.b(0x2e, 0xc6, 0x06); a.word('td_mist'); a.b(0x00)
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tmo_end')
    a.b(0x83, 0x3e, 0xfc, 0x77, 0x00); a.short(0x74, 'tmo_end')   # cmp word [77FCh], 0 / je
    a.b(0x80, 0x7d, 0x35, 0x06); a.short(0x75, 'tmo_end')    # cmp byte [di+35h], 6 / jne
    a.near(0xe8, 'knight_no'); a.short(0x72, 'tmo_end')      # call knight_no / jc
    a.b(0xd1, 0xe3); a.near(0xe8, 'td_window_trogg'); a.short(0x72, 'tmo_time')   # shl bx,1 / call td_window / jc
    a.b(0xc7, 0x06, 0xfc, 0x77, 0x00, 0x00, 0x81, 0x7e, 0x02, 0xda, 0x42); a.short(0x75, 'tmo_end')   # mov word [77FCh], 0 / cmp word [bp+2], 42DAh / jne
    a.b(0x2e, 0xc6, 0x06); a.word('td_mist'); a.b(0x01); a.short(0xeb, 'tmo_end')
    a.label('tmo_time')
    a.near(0xe8, 'td_now'); a.b(0x33, 0xd2, 0x2e, 0x8a, 0x16); a.word('rules_table', G_TD_FAST); a.b(0x03, 0xc2, 0x2e, 0x89, 0x87); a.word('td_fast')
    a.label('tmo_end')
    a.b(0x5a, 0x5b, 0x58, 0x83, 0x3e, 0xfc, 0x77, 0x00); a.near(0xe9, 'rules_flags')   # pop dx bx ax / cmp word [77FCh], 0  (replaced)

    a.label('rules_td_trogg')                                # 1000:4302, sub [di+38h],ax: an axe trogg's hit
    a.near(0xe8, 'td_adjust'); a.b(0x29, 0x45, 0x38, 0x2e, 0xc6, 0x06); a.word('td_after'); a.b(0x00); a.near(0xe9, 'rules_done')
    a.label('rules_td_cdmg')                                 # 1000:4DA1, sub [di+38h],ax: a computer knight's damage
    a.near(0xe8, 'td_adjust'); a.b(0x29, 0x45, 0x38, 0xb8, 0x73, 0x4d)   # (replaced) / mov ax, 4D73h   the blocked reaction if mistimed
    a.label('td_after_hit')                                  # ax = where a mistimed block's reaction is (the knight still stands)
    a.b(0x2e, 0x80, 0x3e); a.word('td_after'); a.b(0x00); a.short(0x74, 'tah_end')
    a.b(0x2e, 0xc6, 0x06); a.word('td_after'); a.b(0x00, 0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'tah_end')   # the flag off / cmp word [di+38h], 0 / jle
    a.b(0x89, 0x46, 0x02)                                    # mov [bp+2], ax
    a.label('tah_end')
    a.near(0xe9, 'rules_done')
    a.label('td_adjust')                                     # ax = a hit's damage, di = its victim: a fifth (at least 1) after a block too early (the ordinary hit reaction follows)
    a.near(0xe8, 'saber_knight')                             # D51: a lightsaber's blow that lands kills
    a.b(0x2e, 0x80, 0x3e); a.word('td_mist'); a.b(0x00); a.short(0x74, 'tad_ctr')
    a.b(0x2e, 0xc6, 0x06); a.word('td_mist'); a.b(0x00)
    a.b(0x51, 0x52, 0x33, 0xd2, 0xb9, 0x05, 0x00, 0xf7, 0xf1, 0x5a, 0x59, 0x0b, 0xc0); a.short(0x75, 'tad_end'); a.b(0x40)   # push cx dx / xor dx,dx / mov cx, 5 / div cx / pop dx cx / or ax,ax / jnz / inc ax
    a.label('tad_end')
    a.b(0xc3)
    a.label('tad_ctr')
    a.b(0xc3)

    # td_bk_block (1000:4C93, mov word [si+28h],8 in BKBlock): with timed defence a smart knight defends by the roll at the hit, not this stance
    a.label('rules_td_bk_block')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_TD); a.b(0x00); a.short(0x74, 'tbb_game')
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_BK_AI); a.b(0x00); a.short(0x74, 'tbb_game')
    a.b(0xc7, 0x46, 0x02, 0xcf, 0x4c); a.near(0xe9, 'rules_done')   # mov word [bp+2], 4CCFh   BKAttack
    a.label('tbb_game')
    a.b(0xc7, 0x44, 0x28, 0x08, 0x00); a.near(0xe9, 'rules_done')   # (replaced)


    a.label('rules_troll_target')
    a.b(0xbe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)            # mov si, 6C9Eh   (replaced)
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'mt_cmp')                                  # je mt_cmp
    a.b(0x8b, 0x36, 0x78, 0x09)                              # mov si, [0978h]
    a.label('mt_cmp')
    a.b(0x83, 0x7c, 0x38, 0x00)                              # cmp word [si+38h], 0   (replaced)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # troll_depth (K26; 1000:570E, call 3C97h in the troll's step 56E5h; si = the troll, di = its knight): the troll
    # counted as level with its knight within 5 in depth either way (+56h), but its swing hits only when its depth
    # is 0-4 more than the knight's. 1-5 nearer, it stood and swung at the air for as long as the knight stood
    # still, e.g. a knight at the screen's edge with the troll off the screen. Level now means 0-4: else it steps
    # (5 at a time, 1000:5629 and 563E), so it always gets there
    # The step 56E5h is shared: the mudman (1000:5363) and the computer knight (4BCA) use it too, so for them it
    # does what 3C97h does: level within +56h either way
    a.label('rules_troll_depth')
    a.b(0x80, 0x7c, 0x35, TROLL_TYPE)                        # cmp byte [si+35h], 20h
    a.short(0x74, 'td_troll')                                # je td_troll
    a.b(0x8b, 0x44, 0x06, 0x2b, 0x45, 0x06)                  # mov ax, [si+6] / sub ax, [di+6]
    a.short(0x79, 'td_abs'); a.b(0xf7, 0xd8)                 # jns td_abs / neg ax
    a.label('td_abs')
    a.b(0x3b, 0x44, 0x56, 0xb8, 0x00, 0x00)                  # cmp ax, [si+56h] / mov ax, 0
    a.short(0x7f, 'td_end')                                  # jg td_end
    a.b(0x40)                                                # inc ax
    a.short(0xeb, 'td_end')                                  # jmp td_end
    a.label('td_troll')
    a.b(0x8b, 0x44, 0x06, 0x2b, 0x45, 0x06)                  # mov ax, [si+6] / sub ax, [di+6]
    a.b(0x3d, 0x04, 0x00, 0xb8, 0x00, 0x00)                  # cmp ax, 4 / mov ax, 0
    a.short(0x77, 'td_end')                                  # ja td_end      below 0 or above 4: not level
    a.b(0x40)                                                # inc ax
    a.label('td_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done (the game tests ax)

    # troll_back (K26; 1000:573B, mov bp,[si+54h] in the troll's step: it steps back from its knight within this, 90):
    # its swing hits a standing knight only from about 100 on, but the troll swung from 91 on (1000:568B, below 100),
    # past the knight's body. It steps back within 104 now, so it swings only where it can hit
    a.label('rules_troll_back')
    a.b(0x8b, 0x5c, 0x54)                                    # mov bx, [si+54h]
    a.b(0x80, 0x7c, 0x35, TROLL_TYPE)                        # cmp byte [si+35h], 20h   only the troll
    a.short(0x75, 'tb_set')                                  # jne tb_set
    a.b(0x81, 0xfb, TROLL_BACK & 0xff, TROLL_BACK >> 8)      # cmp bx, 104
    a.short(0x7d, 'tb_set')                                  # jge tb_set
    a.b(0xbb, TROLL_BACK & 0xff, TROLL_BACK >> 8)            # mov bx, 104
    a.label('tb_set')
    a.b(0x89, 0x5e, 0x00)                                    # mov [bp+0], bx     the game's bp (pop bp)
    a.near(0xe9, 'hard_step')                                # jmp hard_step      TOOEASY (then rules_done)

    # fight_end (D17; 1000:0ABE, replaces mov word [0942h],0 at the end of every fight): the map's CPU speed again
    a.label('rules_fight_end')
    a.near(0xe8, 'cheat_fight_end')                          # call cheat_fight_end
    a.b(0xfb, 0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x55, 0x06, 0x1e)   # sti / push ax bx cx dx si di bp es ds
    a.b(0x0e, 0x1f, 0x80, 0x3e); a.word('sped'); a.b(0x00)   # push cs / pop ds / cmp byte [sped], 0
    a.short(0x74, 'fe_same')                                 # je fe_same           the speed did not change
    a.b(0xbe); a.word('map_tail')                            # mov si, map_tail
    a.near(0xe8, 'speed')                                    # call speed
    a.b(0xc6, 0x06); a.word('sped'); a.b(0x00)               # mov byte [sped], 0
    a.label('fe_same')
    a.near(0xe8, 'ilog_dump')                                # call ilog_dump   input_log
    a.b(0x1f, 0x07, 0x5d, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58)   # pop ds es bp di si dx cx bx ax
    a.b(0xc7, 0x06, 0x42, 0x09, 0x00, 0x00)                  # mov word [0942h], 0   (replaced)
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # moon_picture (K20; 1000:9053, replaces mov ax,[8989h] before the map's moon is drawn): the phase values 2Eh
    # and 2Fh are drawn as each other's picture. The cycle DS:05A9 showed full, half, three-quarters, crescent, new;
    # the half-moon Moonstones work at 2Eh (1000:1065, 2DBF), which now shows the half moon
    a.label('rules_moon_picture')
    a.b(0xa1, 0x89, 0x89)                                    # mov ax, [8989h]
    a.b(0x3d, MOON_HALF, 0x00); a.short(0x74, 'mp_swap')     # cmp ax, 2Eh / je mp_swap
    a.b(0x3d, MOON_THREE_QUARTER, 0x00); a.short(0x75, 'mp_end')   # cmp ax, 2Fh / jne mp_end
    a.label('mp_swap')
    a.b(0x35, MOON_HALF ^ MOON_THREE_QUARTER, 0x00)          # xor ax, 1    2Eh <-> 2Fh
    a.label('mp_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # pause (1000:025C, replaces mov ax,6F08h): the routine toggles every monster's pause flag; the fight start and
    # each knight's walk-in script (command 1000:9DB3) run it, so with an even number of knights the monsters stay
    # paused. In co-op only knight 1's walk-in toggles; the others return at once (to the routine's ret)
    a.label('rules_pause')
    a.b(0xb8, 0x08, 0x6f)                                    # mov ax, 6F08h          as the game
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'pause_done')                              # je pause_done
    a.b(0x81, 0x7e, 0x08, WALK_IN_RET & 0xff, WALK_IN_RET >> 8)   # cmp word [bp+8], 9DCAh   called by a script?
    a.short(0x75, 'pause_done')                              # jne pause_done
    a.b(0x81, 0xff, 0x9e, 0x6c)                              # cmp di, 6C9Eh          knight 1
    a.short(0x74, 'pause_done')                              # je pause_done
    a.b(0xc7, 0x46, 0x02, PAUSE_RET & 0xff, PAUSE_RET >> 8)  # mov word [bp+2], 0278h   skip the toggles
    a.label('pause_done')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # practice_frame (1000:0371, the fight loop; replaces cmp byte [897Dh],0): while both teams have a knight
    # standing the fight goes on; when one has none, the game's own end (as 1000:0238) starts once
    # In practice Esc ends the fight (the game has no key for it): the same end, and then nothing restarts it
    a.label('rules_practice_frame')
    # D49 DAGGERFALL: a new dagger (df_due): its record, then 1000:981F gives it its animation; this site again
    a.b(0x2e, 0x80, 0x3e); a.word('df_due'); a.b(0x00); a.short(0x74, 'pfd_none')
    a.b(0x2e, 0xc6, 0x06); a.word('df_due'); a.b(0x00)
    a.near(0xe8, 'df_spawn'); a.short(0x72, 'pfd_none')      # call df_spawn / jc   no room
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(0x1f, 0x98)   # mov word cs:[call_target], 981Fh
    a.b(0x53, 0x8b, 0x5e, 0x02, 0x4b, 0x4b, 0x2e, 0x89, 0x1e); a.word('call_ret'); a.b(0x5b)   # this site again
    a.near(0xe9, 'call_game')
    a.label('pfd_none')
    # MINEFIELD: its mines into the background, one blit per pass of this site, then the page and es back
    a.b(0x2e, 0x80, 0x3e); a.word('mine_todo'); a.b(0x00); a.short(0x75, 'pfm_draw')
    a.b(0x2e, 0x80, 0x3e); a.word('mine_busy'); a.b(0x00); a.short(0x74, 'pfm_none')
    a.b(0x2e, 0xc6, 0x06); a.word('mine_busy'); a.b(0x00)
    a.near(0xe8, 'mine_shown')                               # D50: shown from now
    a.b(0x2e, 0xa1); a.word('mine_page'); a.b(0xa3, 0xb9, 0x80)   # [80B9h] back
    a.b(0x2e, 0x8e, 0x06); a.word('mine_es'); a.short(0xeb, 'pfm_none')
    a.label('pfm_draw')
    a.b(0x2e, 0x80, 0x3e); a.word('mine_busy'); a.b(0x00); a.short(0x75, 'pfm_blit')
    a.b(0x2e, 0xc6, 0x06); a.word('mine_busy'); a.b(0x01)
    a.b(0xa1, 0xb9, 0x80, 0x2e, 0xa3); a.word('mine_page')   # mov ax, [80B9h] / mov cs:[mine_page], ax
    a.b(0x2e, 0x8c, 0x06); a.word('mine_es')                 # mov cs:[mine_es], es
    a.b(0xc7, 0x06, 0xb9, 0x80, 0x00, 0xac)                  # mov word [80B9h], 0AC00h   the background
    a.label('pfm_blit')
    a.b(0x2e, 0xfe, 0x0e); a.word('mine_todo')               # dec byte cs:[mine_todo]
    a.b(0x33, 0xdb, 0x2e, 0x8a, 0x1e); a.word('mine_todo'); a.b(0xd1, 0xe3)   # xor bx, bx / mov bl, cs:[mine_todo] / shl bx, 1
    a.b(0x2e, 0xc6, 0x06); a.word('mine_mode'); a.b(0x00); a.near(0xe8, 'mine_rect')   # D50: the background under it kept
    a.b(0x2e, 0x8b, 0x87); a.word('mine_x'); a.b(0x05, MINE_DRAW_X & 0xff, (MINE_DRAW_X >> 8) & 0xff, 0x89, 0x46, 0xfe)   # x, as bx
    a.b(0x2e, 0x8b, 0x8f); a.word('mine_z'); a.b(0x83, 0xc1, MINE_DRAW_Y)   # mov cx, cs:[bx+mine_z] / add cx, y
    a.b(0xc4, 0x36, MINE_BANK & 0xff, MINE_BANK >> 8, 0xb8, MINE_FRAME, 0x00)   # les si, [bank] / mov ax, frame
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(BLITTER & 0xff, BLITTER >> 8)
    a.b(0x53, 0x8b, 0x5e, 0x02, 0x4b, 0x4b, 0x2e, 0x89, 0x1e); a.word('call_ret'); a.b(0x5b)   # this site again
    a.near(0xe9, 'call_game')
    a.label('pfm_none')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_wait'); a.b(0x00); a.short(0x74, 'sxpf_nw')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x00, 0x2e, 0xa1); a.word('snd_ax')   # back from the sound: ax again
    a.short(0xeb, 'sxpf_go')
    a.label('sxpf_nw')
    a.b(0x2e, 0x80, 0x3e); a.word('snd_req'); a.b(0x00); a.short(0x74, 'sxpf_go')
    a.b(0x2e, 0xc6, 0x06); a.word('snd_req'); a.b(0x00, 0x2e, 0xc6, 0x06); a.word('snd_wait'); a.b(0x01)
    a.b(0x2e, 0xa3); a.word('snd_ax'); a.b(0x8b, 0x46, 0x02, 0x2d, 0x02, 0x00)   # mov cs:[snd_ax], ax / mov ax, [bp+2] / sub ax, 2
    a.b(0x2e, 0xa3); a.word('call_ret')                      # this site's int 63h again
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(SOUND & 0xff, SOUND >> 8)
    a.b(0x2e, 0xa1); a.word('snd_id')                        # mov ax, cs:[snd_id]   sound id
    a.b(0x2e, 0xc7, 0x06); a.word('snd_id'); a.b(CHEAT_SOUND, 0x00)   # (the next is the code's own)
    a.near(0xe9, 'call_game')                                # 1000:5970
    a.label('sxpf_go')
    a.near(0xe8, 'cheat_fight')                              # call cheat_fight   cheat codes
    a.near(0xe8, 'knight_flash')                             # call knight_flash  knights 3 and 4 at low HP
    a.b(0x83, 0x3e, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION)   # cmp word [0704h], 2
    a.short(0x75, 'pf_play')                                 # jne pf_play          not a practice
    a.b(0x2e, 0x80, 0x3e); a.word('quitting'); a.b(0x00)     # cmp byte cs:[quitting], 0
    a.short(0x75, 'pf_quit_cmp')                             # jne pf_quit_cmp      ending: leave it to the game
    a.b(0x06, 0x8e, 0x46, 0x04)                              # push es / mov es, [bp+4]   MAIN's code segment
    a.b(0x26, 0x80, 0x3e, (KEY_TABLE + ESC) & 0xff, (KEY_TABLE + ESC) >> 8, 0xff)   # cmp byte es:[81E4h], 0FFh
    a.b(0x07)                                                # pop es
    a.short(0x74, 'pf_play')                                 # je pf_play           Esc not pressed
    a.b(0x2e, 0xc6, 0x06); a.word('quitting'); a.b(0x01)     # mov byte cs:[quitting], 1
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'pf_quit_end')                             # je pf_quit_end
    a.b(0x50); a.near(0xe8, 'first_standing')                # push ax / call first_standing
    a.b(0xa3, 0x79, 0x89, 0x58)                              # mov [8979h], ax / pop ax   (as a won co-op fight)
    a.label('pf_quit_end')
    a.b(0x80, 0x3e, 0x7d, 0x89, 0x00)                        # cmp byte [897Dh], 0
    a.short(0x74, 'pf_quit_cmp')                             # je pf_quit_cmp       already ending
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x00, 0xc6, 0x06, 0x87, 0x89, 0x23)   # mov byte [897Dh], 0 / mov byte [8987h], 23h
    a.label('pf_quit_cmp')
    a.near(0xe9, 'pf_cmp')                                   # jmp pf_cmp
    a.label('pf_play')
    a.b(0x2e, 0x83, 0x3e); a.word('team_t0'); a.b(0x00)      # cmp word cs:[team_t0], 0
    a.short(0x75, 'pf_started')                              # jne pf_started
    a.b(0x50, 0x1e, 0x33, 0xc0, 0x8e, 0xd8)                  # push ax / push ds / xor ax, ax / mov ds, ax
    a.b(0xa1, 0x6c, 0x04, 0x1f, 0x0c, 0x01)                  # mov ax, [046Ch] / pop ds / or al, 1   (never 0)
    a.b(0x2e, 0xa3); a.word('team_t0'); a.b(0x58)            # mov cs:[team_t0], ax / pop ax   the first frame
    a.label('pf_started')
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'pf_coop')                                 # jne pf_coop
    a.near(0xe9, 'pf_not_coop')                              # jmp pf_not_coop
    a.label('pf_coop')
    # co-op: [0978h] = a knight standing; while one stands and monsters are left the fight goes on; with none
    # standing the end starts (when the monsters are all down the game ends it itself)
    a.b(0x50, 0x53, 0x56, 0x51)                              # push ax bx si cx
    a.b(0x33, 0xf6, 0x33, 0xc9)                              # xor si, si / xor cx, cx
    a.label('pfc_loop')
    a.b(0x8b, 0xd9, 0xd1, 0xe3)                              # mov bx, cx / shl bx, 1
    a.b(0x2e, 0x8b, 0x9f); a.word('knight_list')             # mov bx, cs:[bx+knight_list]
    a.b(0x83, 0x7f, 0x38, 0x00)                              # cmp word [bx+38h], 0
    a.short(0x7e, 'pfc_next')                                # jle pfc_next
    a.b(0x8b, 0xf3)                                          # mov si, bx
    a.short(0xeb, 'pfc_found')                               # jmp pfc_found
    a.label('pfc_next')
    a.b(0x41)                                                # inc cx
    a.b(0x2e, 0x3a, 0x0e); a.word('coop')                    # cmp cl, cs:[coop]
    a.short(0x72, 'pfc_loop')                                # jb pfc_loop
    a.label('pfc_found')
    a.b(0x0b, 0xf6)                                          # or si, si
    a.short(0x75, 'pfc_alive')                               # jnz pfc_alive
    a.b(0x80, 0x3e, 0x7d, 0x89, 0x00)                        # cmp byte [897Dh], 0
    a.short(0x74, 'pfc_none_pop')                            # je pfc_none_pop      already ending
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x00, 0xc6, 0x06, 0x87, 0x89, 0x23)   # mov byte [897Dh], 0 / mov byte [8987h], 23h
    a.label('pfc_none_pop')
    a.near(0xe9, 'pfc_pop')                                  # jmp pfc_pop
    a.label('pfc_alive')
    a.b(0x89, 0x36, 0x78, 0x09)                              # mov [0978h], si      the first knight standing
    # D19: a Black Knight falls as a knight does, not through the monsters' death (1000:0213), so the counts never
    # fall: the fight is won when all of them have come and none stands
    a.b(0x2e, 0x80, 0x3e); a.word('bk'); a.b(0x00)           # cmp byte cs:[bk], 0
    a.short(0x74, 'pfc_monsters')                            # je pfc_monsters
    # not all have come (the set-up made fewer): the game's top-up brings them
    a.b(0x2e, 0xa0); a.word('coop'); a.b(0x32, 0xe4)         # mov al, cs:[coop] / xor ah, ah
    a.b(0x2e, 0x3a, 0x06); a.word('bk_count')                # cmp al, cs:[bk_count]
    a.short(0x76, 'pfc_bk_all')                              # jbe pfc_bk_all
    a.b(0xa3, 0x6c, 0x09)                                    # mov [096Ch], ax      at once: all
    a.b(0x39, 0x06, 0x6e, 0x09); a.short(0x73, 'pfc_bk_all') # cmp [096Eh], ax / jae   (on screen >= all: none)
    a.label('pfc_bk_more')
    a.b(0x83, 0x3e, 0x6a, 0x09, 0x00); a.short(0x7e, 'pfc_bk_all')   # cmp word [096Ah], 0 / jle
    a.b(0x59, 0x5e, 0x5b, 0x58)                              # pop cx si bx ax
    a.near(0xe9, 'pf_topup')                                 # jmp pf_topup
    a.label('pfc_bk_all')
    a.b(0x57, 0x33, 0xc9, 0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb8, MONSTER_COUNT, 0x00)
    #                                                          push di / xor cx, cx / mov di, 6F08h / mov ax, 20
    a.label('pfc_bk')
    a.b(0x83, 0x3d, 0x00); a.short(0x74, 'pfc_bk_next')      # cmp word [di], 0 / je
    a.b(0x80, 0x7d, 0x35, COMPUTER_TYPE); a.short(0x75, 'pfc_bk_next')   # cmp byte [di+35h], 8 / jne
    a.b(0x83, 0x7d, 0x38, 0x00); a.short(0x7e, 'pfc_bk_next')   # cmp word [di+38h], 0 / jle   down
    a.b(0x41)                                                # inc cx
    a.label('pfc_bk_next')
    a.b(0x83, 0xc7, SLOT_SIZE, 0x48); a.short(0x75, 'pfc_bk')   # add di, 62h / dec ax / jnz pfc_bk
    a.b(0x5f, 0x0b, 0xc9)                                    # pop di / or cx, cx
    a.short(0x74, 'pfc_bk_none')                             # jz pfc_bk_none
    a.near(0xe9, 'pfc_go')                                   # jmp pfc_go           one stands
    a.label('pfc_bk_none')
    a.b(0x2e, 0xa0); a.word('bk_count')                      # mov al, cs:[bk_count]
    a.b(0x2e, 0x3a, 0x06); a.word('coop')                    # cmp al, cs:[coop]
    a.short(0x73, 'pfc_bk_won')                              # jae pfc_bk_won
    a.near(0xe9, 'pfc_go')                                   # jmp pfc_go           not all came yet
    a.label('pfc_bk_won')
    a.b(0xc7, 0x06, 0x6a, 0x09, 0x00, 0x00, 0xc7, 0x06, 0x6e, 0x09, 0x00, 0x00)   # [096Ah] = [096Eh] = 0
    a.b(0x80, 0x3e, 0x7d, 0x89, 0x00)                        # cmp byte [897Dh], 0
    a.short(0x74, 'pfc_bk_hero')                             # je pfc_bk_hero      already ending
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x00, 0xc6, 0x06, 0x87, 0x89, 0x23)   # mov byte [897Dh], 0 / mov byte [8987h], 23h
    a.label('pfc_bk_hero')
    a.b(0x89, 0x36, 0x79, 0x89)                              # mov [8979h], si      a knight standing
    a.near(0xe9, 'pfc_pop')                                  # jmp pfc_pop
    a.label('pfc_monsters')
    # the dragon's practice (D): the dragon is no monster of the counts ([096Ah] stays 1), so the fight went on after
    # its death script had ended it (0231): won when the dragon has no HP left (its script ends the fight)
    a.b(0x2e, 0x80, 0x3e); a.word('monster'); a.b(DRAGON_CHOICE)   # cmp byte cs:[monster], 10
    a.short(0x75, 'pfc_not_dragon')                          # jne pfc_not_dragon
    a.b(0x83, 0x3e, (DRAGON_RECORD + 0x38) & 0xff, (DRAGON_RECORD + 0x38) >> 8, 0x00)   # cmp word [6E5Eh], 0
    a.short(0x7e, 'pfc_dragon_dead')                         # jle pfc_dragon_dead
    a.near(0xe9, 'pfc_go')                                   # jmp pfc_go
    a.label('pfc_dragon_dead')
    # its death script ends the fight; once it is over (the dragon's object gone) the end starts if it has not
    a.b(0x83, 0x3e, DRAGON_RECORD & 0xff, DRAGON_RECORD >> 8, 0x00)   # cmp word [6E26h], 0
    a.short(0x75, 'pfc_won')                                 # jne pfc_won          still dying
    a.b(0x80, 0x3e, 0x7d, 0x89, 0x00)                        # cmp byte [897Dh], 0
    a.short(0x74, 'pfc_won')                                 # je pfc_won           ending
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x00, 0xc6, 0x06, 0x87, 0x89, 0x23)   # mov byte [897Dh], 0 / mov byte [8987h], 23h
    a.short(0xeb, 'pfc_won')                                 # jmp pfc_won
    a.label('pfc_not_dragon')
    # K25: a monster that left the fight without dying (a mudman that pulled a knight under) still counted as on the
    # screen ([096Eh]), so no other came: in the one-to-one game the fight was over. With fewer monster objects
    # active than counted, the count follows and the game's own top-up (1000:0243) runs, which brings the next
    a.b(0x57, 0x33, 0xc9, 0xbf, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8, 0xb8, MONSTER_COUNT, 0x00)
    #                                                          push di / xor cx, cx / mov di, 6F08h / mov ax, 20
    a.label('pfc_count')
    a.b(0x83, 0x3d, 0x00); a.short(0x74, 'pfc_count_next')   # cmp word [di], 0 / je              not active
    a.b(0x41)                                                # inc cx
    a.label('pfc_count_next')
    a.b(0x83, 0xc7, SLOT_SIZE, 0x48); a.short(0x75, 'pfc_count')   # add di, 62h / dec ax / jnz pfc_count
    a.b(0x5f)                                                # pop di
    a.b(0x3b, 0x0e, 0x6e, 0x09); a.short(0x73, 'pfc_counted')   # cmp cx, [096Eh] / jae pfc_counted
    a.b(0x39, 0x0e, 0x6a, 0x09); a.short(0x7e, 'pfc_counted')   # cmp [096Ah], cx / jle: none left to come
    a.b(0x89, 0x0e, 0x6e, 0x09)                              # mov [096Eh], cx
    a.b(0x59, 0x5e, 0x5b, 0x58)                              # pop cx si bx ax
    a.near(0xe9, 'pf_topup')                                 # jmp pf_topup
    a.label('pfc_counted')
    a.b(0x83, 0x3e, 0x6a, 0x09, 0x00)                        # cmp word [096Ah], 0  monsters still to come
    a.short(0x7f, 'pfc_go')                                  # jg pfc_go
    a.b(0x83, 0x3e, 0x6e, 0x09, 0x00)                        # cmp word [096Eh], 0  monsters on screen
    a.short(0x7f, 'pfc_go')                                  # jg pfc_go
    # won: the end looks at the knight in [8979h] (1000:0ABE gives a fallen one its HP back, and it stood up again)
    a.label('pfc_won')
    a.b(0x89, 0x36, 0x79, 0x89)                              # mov [8979h], si      a knight standing
    a.short(0xeb, 'pfc_pop')                                 # jmp pfc_pop
    a.label('pfc_go')
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x01)                        # mov byte [897Dh], 1
    a.label('pfc_pop')
    a.b(0x59, 0x5e, 0x5b, 0x58)                              # pop cx si bx ax
    a.near(0xe9, 'pf_cmp')                                   # jmp pf_cmp
    a.label('pf_not_coop')
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x75, 'pf_active')                               # jne pf_active
    a.near(0xe9, 'pf_cmp')                                   # jmp pf_cmp
    a.label('pf_active')
    a.b(0x50, 0x33, 0xc0)                                    # push ax / xor ax, ax
    a.b(0x2e, 0x80, 0x3e); a.word('teams'); a.b(0x00)        # cmp byte cs:[teams], 0
    a.short(0x75, 'pf_team_mode')                            # jne pf_team_mode
    for n, rec in enumerate((TEAM1[0], TEAM2[0], TEAM1[1], TEAM2[1])):   # free-for-all: knights standing
        if n == 3:
            a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x04)   # cmp byte cs:[multi], 4
            a.short(0x75, 'pf_count')                        # jne pf_count
        hp = rec + 0x38
        a.b(0x83, 0x3e, hp & 0xff, hp >> 8, 0x00)            # cmp word [record+38h], 0
        a.short(0x7e, f'pf_ffa{n}')                          # jle next
        a.b(0xfe, 0xc0)                                      # inc al
        a.label(f'pf_ffa{n}')
    a.label('pf_count')
    a.b(0x3c, 0x02)                                          # cmp al, 2
    a.short(0x72, 'pf_over')                                 # jb pf_over      one knight (or none) left
    a.short(0xeb, 'pf_go')                                   # jmp pf_go
    a.label('pf_team_mode')                                  # teams: al = team 1, ah = team 2 standing
    for rec, reg, label in ((TEAM1[0], 0xb0, 'pf_a'), (TEAM1[1], 0xb0, 'pf_b'), (TEAM2[0], 0xb4, 'pf_c')):
        hp = rec + 0x38
        a.b(0x83, 0x3e, hp & 0xff, hp >> 8, 0x00)            # cmp word [record+38h], 0
        a.short(0x7e, label)                                 # jle next
        a.b(reg, 0x01)                                       # mov al/ah, 1
        a.label(label)
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x04)        # cmp byte cs:[multi], 4
    a.short(0x75, 'pf_teams')                                # jne pf_teams
    hp = TEAM2[1] + 0x38
    a.b(0x83, 0x3e, hp & 0xff, hp >> 8, 0x00)                # cmp word [6DC4h+38h], 0
    a.short(0x7e, 'pf_teams')                                # jle pf_teams
    a.b(0xb4, 0x01)                                          # mov ah, 1
    a.label('pf_teams')
    a.b(0x22, 0xc4)                                          # and al, ah
    a.short(0x74, 'pf_over')                                 # jz pf_over
    a.label('pf_go')
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x01)                        # mov byte [897Dh], 1     the fight goes on
    a.short(0xeb, 'pf_pop')                                  # jmp pf_pop
    a.label('pf_over')
    a.b(0x80, 0x3e, 0x7d, 0x89, 0x00)                        # cmp byte [897Dh], 0
    a.short(0x74, 'pf_pop')                                  # je pf_pop               already ending
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x00)                        # mov byte [897Dh], 0
    a.b(0xc6, 0x06, 0x87, 0x89, 0x23)                        # mov byte [8987h], 23h   as 1000:0238
    a.label('pf_pop')
    a.b(0x58)                                                # pop ax
    a.label('pf_cmp')
    a.near(0xe8, 'score_settled')                            # D57: the practice score, as its end begins
    a.b(0x80, 0x3e, 0x7d, 0x89, 0x00)                        # cmp byte [897Dh], 0     (replaced instruction)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags
    # pf_topup (K25): return into the game's top-up 1000:0243 with its ret pointing at this int 63h again (the
    # frame check then runs as usual). The interrupt frame moves down a word: IP 0243h, CS, flags, the site
    a.label('pf_topup')
    a.b(0x5b, 0x5d, 0x50, 0x50, 0x55, 0x8b, 0xec)            # pop bx / pop bp / push ax / push ax / push bp / mov bp, sp
    a.b(0x8b, 0x46, 0x06, 0x2d, 0x02, 0x00)                  # mov ax, [bp+6] / sub ax, 2    the site
    a.b(0x87, 0x46, 0x0a, 0x87, 0x46, 0x08, 0x89, 0x46, 0x06)   # xchg ax, [bp+10] / xchg ax, [bp+8] / mov [bp+6], ax
    a.b(0xc7, 0x46, 0x04, 0x43, 0x02)                        # mov word [bp+4], 0243h
    a.b(0x5d, 0x58, 0xcf)                                    # pop bp / pop ax / iret

    # practice_hit (1000:4275, a knight was hit; replaces mov si,[di+0Eh] / xor ax,ax): a hit by a teammate is
    # dropped and the knight's control goes on as if not hit (1000:3F05)
    a.label('rules_practice_hit')
    a.b(0x8b, 0x75, 0x0e, 0x33, 0xc0)                        # mov si, [di+0Eh] / xor ax, ax   (replaced)
    # against monsters a knight's dagger does not hit knights (unless coop_dagger_hits)
    a.b(0x2e, 0x80, 0x3e); a.word('vs_monsters'); a.b(0x00)  # cmp byte cs:[vs_monsters], 0
    a.short(0x74, 'ph_knights')                              # je ph_knights
    a.b(0x80, 0x7c, 0x35, DAGGER)                            # cmp byte [si+35h], 1Ah
    a.short(0x75, 'ph_knights')                              # jne ph_knights
    a.b(0x81, 0x7c, DAGGER_OWNER, MONSTER_SLOTS & 0xff, MONSTER_SLOTS >> 8)   # cmp word [si+5Ch], 6F08h
    a.short(0x73, 'ph_knights')                              # jae ph_knights   D19: a Black Knight's: a hit
    a.b(0x2e, 0xf6, 0x06); a.word('rules_table', G_PRACTICE_FLAGS); a.b(COOP_DAGGER_HITS)   # test flags, dagger
    a.short(0x74, 'ph_drop')                                 # jz ph_drop
    a.label('ph_knights')
    a.b(0x2e, 0x83, 0x3e); a.word('coop_partner'); a.b(0x00); a.short(0x74, 'ph_sides')   # D33: a co-op lair:
    a.near(0xe9, 'ph_end')                                   # every hit as the game's (friendly fire)
    a.label('ph_sides')
    a.near(0xe8, 'colours_active')                           # call colours_active   (3-4 players or co-op)
    a.short(0x74, 'ph_end')                                  # jz ph_end
    a.b(0x8b, 0xdf); a.near(0xe8, 'team')                    # mov bx, di / call team
    a.b(0x8a, 0xe0)                                          # mov ah, al
    a.b(0x8b, 0xde)                                          # mov bx, si
    a.b(0x80, 0x7f, 0x35, DAGGER); a.short(0x75, 'ph_team')  # cmp byte [bx+35h], 1Ah / jne ph_team
    a.b(0x8b, 0x5f, DAGGER_OWNER)                            # mov bx, [bx+5Ch]   D19: a dagger is on its thrower's side
    a.label('ph_team')
    a.near(0xe8, 'team')                                     # call team
    a.b(0x0a, 0xc0)                                          # or al, al
    a.short(0x74, 'ph_clear')                                # jz ph_clear     not a knight (a dagger): a hit
    a.b(0x3a, 0xc4)                                          # cmp al, ah
    a.short(0x75, 'ph_clear')                                # jne ph_clear
    a.b(0xb0, COOP_KNIGHT_HITS)                              # mov al, co-op flag    same side: allowed?
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'ph_flag')                                 # jne ph_flag
    a.b(0xb0, TEAM_KNIGHT_HITS)                              # mov al, team flag
    a.label('ph_flag')
    a.b(0x2e, 0x84, 0x06); a.word('rules_table', G_PRACTICE_FLAGS)   # test cs:[flags], al
    a.short(0x75, 'ph_clear')                                # jnz ph_clear     allowed: a hit
    a.label('ph_drop')
    a.b(0xc7, 0x45, 0x0e, 0x00, 0x00)                        # mov word [di+0Eh], 0
    a.b(0x39, 0x7c, 0x0c)                                    # cmp [si+0Ch], di
    a.short(0x75, 'ph_skip')                                 # jne ph_skip
    a.b(0xc7, 0x44, 0x0c, 0x00, 0x00)                        # mov word [si+0Ch], 0
    a.label('ph_skip')
    a.b(0x8b, 0xf7)                                          # mov si, di
    a.b(0xc7, 0x46, 0x02, 0x05, 0x3f)                        # mov word [bp+2], 3F05h   not hit
    a.label('ph_clear')
    a.b(0x33, 0xc0)                                          # xor ax, ax
    a.label('ph_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    a.label('team')                                          # bx = record -> al = its team, 0 = not a knight
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'team_split')                              # je team_split
    for rec in KNIGHTS:                                      # co-op: every knight on one side
        a.b(0x81, 0xfb, rec & 0xff, rec >> 8)                # cmp bx, record
        a.short(0x74, 'team_1')                              # je team_1
    a.b(0x32, 0xc0, 0xc3)                                    # xor al, al / ret
    a.label('team_split')
    a.b(0x2e, 0x80, 0x3e); a.word('teams'); a.b(0x00)        # cmp byte cs:[teams], 0
    a.short(0x74, 'team_ffa')                                # je team_ffa      free-for-all: each knight alone
    for n, recs in ((1, TEAM1), (2, TEAM2)):
        for rec in recs:
            a.b(0x81, 0xfb, rec & 0xff, rec >> 8)            # cmp bx, record
            a.short(0x74, f'team_{n}')                       # je team_n
    a.b(0x32, 0xc0, 0xc3)                                    # xor al, al / ret
    a.label('team_ffa')
    for n, rec in enumerate((TEAM1[0], TEAM2[0], TEAM1[1], TEAM2[1]), 1):
        a.b(0x81, 0xfb, rec & 0xff, rec >> 8)                # cmp bx, record
        a.short(0x74, f'team_{n}')                           # je team_n
    a.b(0x32, 0xc0, 0xc3)                                    # xor al, al / ret
    for n in (1, 2, 3, 4):
        a.label(f'team_{n}')
        a.b(0xb0, n, 0xc3)                                   # mov al, n / ret

    # joy_a (1000:83F0; replaces pop bx / or bx,ax): ax = joystick A, the pushed word = player 1's keys
    # sep_inputs: ZF = 0 when the joysticks are inputs of their own (3-4 practice, a monster code's fight, a co-op
    # lair's knight on a joystick)
    a.label('sep_inputs')
    a.b(0x2e, 0x83, 0x3e); a.word('multi'); a.b(0x00); a.short(0x75, 'sep_end')   # (a word with mon_mode)
    a.b(0x2e, 0x80, 0x3e); a.word('joy_own'); a.b(0x00)
    a.label('sep_end')
    a.b(0xc3)
    a.label('rules_joy_a')
    a.b(0x2e, 0xa3); a.word('joy_a')                         # mov cs:[joy_a], ax
    a.b(0x8b, 0x5e, 0x08)                                    # mov bx, [bp+8]          the pushed bx
    a.near(0xe8, 'sep_inputs'); a.short(0x75, 'ja_keys')     # separate inputs: keys alone
    a.b(0x0b, 0xd8)                                          # or bx, ax
    a.label('ja_keys')
    a.b(0x89, 0x5e, 0xfe)                                    # mov [bp-2], bx          returned as bx
    a.b(0x5b, 0x5d, 0x50, 0x55, 0x8b, 0xec)                  # pop bx / pop bp / push ax / push bp / mov bp, sp
    for src, dst in ((8, 10), (6, 8), (4, 6)):               # the frame up over the popped word
        a.b(0x8b, 0x46, src, 0x89, 0x46, dst)                # mov ax, [bp+src] / mov [bp+dst], ax
    a.b(0x5d, 0x58, 0x83, 0xc4, 0x02, 0xcf)                  # pop bp / pop ax / add sp, 2 / iret

    # joy_b (1000:8422; replaces pop dx / pop bx / or ax,dx): ax = joystick B, pushed dx = player 2's keys, bx
    a.label('rules_joy_b')
    a.b(0x2e, 0xa3); a.word('joy_b')                         # mov cs:[joy_b], ax
    a.b(0x8b, 0x56, 0x08, 0x8b, 0x5e, 0x0a, 0x89, 0x5e, 0xfe)   # mov dx, [bp+8] / mov bx, [bp+10] / mov [bp-2], bx
    a.near(0xe8, 'sep_inputs')                               # separate inputs (multi, mon_mode, joy_own)
    a.short(0x75, 'jb_keys')                                 # jne jb_keys
    a.b(0x0b, 0xc2)                                          # or ax, dx
    a.short(0xeb, 'jb_drop')                                 # jmp jb_drop
    a.label('jb_keys')
    a.b(0x8b, 0xc2)                                          # mov ax, dx              keys alone
    a.label('jb_drop')
    a.b(0x5b, 0x5d, 0x50, 0x55, 0x8b, 0xec)                  # pop bx / pop bp / push ax / push bp / mov bp, sp
    for src, dst in ((8, 12), (6, 10), (4, 8)):              # the frame up over the two popped words
        a.b(0x8b, 0x46, src, 0x89, 0x46, dst)                # mov ax, [bp+src] / mov [bp+dst], ax
    a.b(0x5d, 0x58, 0x83, 0xc4, 0x04, 0xcf)                  # pop bp / pop ax / add sp, 4 / iret

    # input_pick (1000:0A91; replaces cmp byte [di+9],1 / je / mov ax,bx): ax = this knight's input by +9:
    # 1 player 2's (ax), 5 joystick A, 6 joystick B, else player 1's (bx)
    a.label('rules_input_pick')
    a.b(0x8a, 0x5d, 0x09)                                    # mov bl, [di+9]
    a.b(0x80, 0xfb, 0x01); a.short(0x74, 'ip_end')           # cmp bl, 1 / je ip_end
    a.b(0x80, 0xfb, JOY_A_CONTROL); a.short(0x75, 'ip_b')    # cmp bl, 5 / jne ip_b
    a.b(0x2e, 0xa1); a.word('joy_a'); a.short(0xeb, 'ip_end')   # mov ax, cs:[joy_a] / jmp ip_end
    a.label('ip_b')
    a.b(0x80, 0xfb, JOY_B_CONTROL); a.short(0x75, 'ip_k3')    # cmp bl, 6 / jne ip_k3
    a.b(0x2e, 0xa1); a.word('joy_b'); a.short(0xeb, 'ip_end')   # mov ax, cs:[joy_b] / jmp ip_end
    a.label('ip_k3')                                         # 7: the third key set (I K J L, B), as 83C0 makes bits
    a.b(0x80, 0xfb, KEYS3_CONTROL); a.short(0x75, 'ip_keys')
    a.near(0xe8, 'keys3_bits'); a.short(0xeb, 'ip_end')
    a.label('ip_keys')
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]          the caller's bx
    a.label('ip_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # practice_end (1000:014D; replaces mov dx,[0940h]): practice is over
    a.label('rules_practice_end')
    a.near(0xe8, 'bk_colours_off')                           # call bk_colours_off   D19
    a.b(0x2e, 0xc6, 0x06); a.word('bk'); a.b(0x00)           # mov byte cs:[bk], 0
    a.b(0x2e, 0xc6, 0x06); a.word('dummy'); a.b(0x00)        # D46
    a.b(0x2e, 0xc6, 0x06); a.word('multi'); a.b(0x00)        # mov byte cs:[multi], 0
    a.b(0x2e, 0xc6, 0x06); a.word('monster'); a.b(0x00)      # mov byte cs:[monster], 0
    a.b(0x2e, 0x80, 0x3e); a.word('mon_mode'); a.b(0x00); a.short(0x74, 'pe_no_mon')
    a.b(0x2e, 0x80, 0x3e); a.word('k1_out'); a.b(0x00); a.short(0x75, 'pe_k1')
    a.b(0x50, 0x2e, 0xa0); a.word('k1_ctl'); a.b(0xa2, (KNIGHTS[0] + 9) & 0xff, (KNIGHTS[0] + 9) >> 8, 0x58)   # knight 1's +9 back
    a.label('pe_k1')
    a.b(0x2e, 0xc7, 0x06); a.word('mon_mode'); a.b(0x00, 0x00)   # mon_mode, mon_req = 0
    a.b(0x2e, 0xc6, 0x06); a.word('k1_out'); a.b(0x00)
    a.label('pe_no_mon')
    a.b(0x2e, 0xc6, 0x06); a.word('init_state'); a.b(0x00)   # mov byte cs:[init_state], 0
    a.b(0x2e, 0xc6, 0x06); a.word('coop'); a.b(0x00)         # mov byte cs:[coop], 0
    a.b(0x2e, 0xc6, 0x06); a.word('vs_monsters'); a.b(0x00)  # mov byte cs:[vs_monsters], 0
    a.b(0x2e, 0xc6, 0x06); a.word('quitting'); a.b(0x00)     # mov byte cs:[quitting], 0
    a.b(0x8b, 0x16, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8)   # mov dx, [0940h]
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # village (1000:1130): the home village druids, si = record
    a.label('rules_village')
    a.b(0x50, 0x2e, 0xa0); a.word('rules_table', G_MAX_LIVES)       # push ax / mov al, cs:[max_lives]
    a.b(0x2e, 0x8a, 0x26); a.word('rules_table', G_VILLAGE)         # mov ah, cs:[village]
    a.b(0x80, 0xfc, VILLAGE_FULL)                            # cmp ah, 2
    a.short(0x74, 'village_full')                            # je village_full
    a.b(0x0a, 0xe4)                                          # or ah, ah
    a.short(0x75, 'village_add')                             # jnz village_add
    a.b(0xb0, 0x03)                                          # mov al, 3       below 3 (the original)
    a.label('village_add')
    a.b(0x38, 0x44, 0x31)                                    # cmp [si+31h], al
    a.short(0x7d, 'village_hp')                              # jge village_hp
    a.b(0xfe, 0x44, 0x31)                                    # inc byte [si+31h]
    a.short(0xeb, 'village_hp')                              # jmp village_hp
    a.label('village_full')
    a.b(0x38, 0x44, 0x31)                                    # cmp [si+31h], al
    a.short(0x7d, 'village_hp')                              # jge village_hp
    a.b(0x88, 0x44, 0x31)                                    # mov [si+31h], al
    a.label('village_hp')                                    # full HP whatever the lives (the manual); speedrun: as the game
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_EXPLOIT_FIXES); a.b(0x00); a.short(0x74, 'village_end')
    a.b(0x8b, 0x44, 0x3c, 0x89, 0x44, 0x38)                  # mov ax, [si+3Ch] / mov [si+38h], ax
    a.label('village_end')
    a.b(0x58)                                                # pop ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

def rules_data(a, table):
    """The int 63h tables: the sites (return address, job) and the settings from rules.py."""
    base, per = struct.unpack_from('<HH', table or rules_default_table(), G_CYCLES)
    fights = struct.unpack_from('<4H', table or rules_default_table(), G_FIGHT_CYCLES)
    on = any(f != base for f in fights)                      # else the map's speed in every fight: no change
    a.label('fight_tails')                                   # D17: CONFIG -set cycles=... for 1-4 knights, the map
    for n in range(4):
        a.word(f'fight_tail{n}')
    for n in range(4):                                       # fight_cycles of 1-4 knights
        a.label(f'fight_tail{n}'); a.b(cycles_tail(fights[n] if on else 0))
    a.label('map_tail'); a.b(cycles_tail(base if on else 0))
    a.label('sped'); a.b(0)                                  # 1 after a fight's speed was set
    a.label('down'); a.b(bytes(4))                           # K25: 1 = the knight's fall has been started
    a.label('held'); a.b(bytes(8))                           # D60: the frame a dead knight's slot repeats (3-4 knight practice), 0 = none
    a.label('mud_victim'); a.b(0, 0)                         # K25: the knight the mudman holds
    a.label('dragon_victim'); a.b(0, 0)                      # K25: the knight the dragon has eaten
    a.label('moves_left'); a.b(0, 0)                         # rest heal: the turn's movement left (turn_moves)
    a.label('turned'); a.b(0)                                # D25: 1 = a knight turned this frame (no step)
    a.label('turn_from'); a.b(bytes(4))                      # D25: each knight's facing before its last turn, 0 = none
    a.label('turn_tick'); a.b(bytes(8))                      # D25: ... and when it turned (BIOS tick)
    a.label('rel_bits'); a.b(bytes(3))                       # D24: each player's directions let go lately
    a.label('coop_partner'); a.b(0, 0)                       # D33: the first partner in a lair's fight, 0 = none
    a.label('coop_partners'); a.b(bytes(2 * COOP_PARTNERS))  # D33: the partners in it
    a.label('coop_pn'); a.b(0)                               # D33: ... how many
    a.label('lair_partners'); a.b(bytes(2 * COOP_PARTNERS))  # D33: the partners the list offers
    a.label('lair_pn'); a.b(0)                               # D33: ... how many
    a.label('lair_list'); a.b(bytes(2 * 4))                  # D33: the fight's knights (the visit's first)
    a.label('lair_xs')
    for x in LAIR_XS:
        a.b(struct.pack('<H', x))
    a.label('battle_list'); a.b(bytes(CHOICE_SIZE * CHOICE_COUNT))   # D33: the knights to fight ("Battle with ...")
    a.label('battle_n'); a.b(0)                              # D33: ... how many
    a.label('cl_used'); a.b(0)                               # D33: the list's entries
    a.label('cl_max'); a.b(0)                                # D33: the partners the inputs allow
    a.label('joy_seen'); a.b(0)                              # D33: the joysticks that answered (4 A, 8 B)
    a.label('joy_own'); a.b(0)                               # D33: a lair's knight on a joystick (not merged)
    a.label('coop_count'); a.b(0)                            # D33: the chests (knights standing)
    a.label('coop_start'); a.b(0)                            # D33: the order's first drawn place
    a.label('coop_state'); a.b(0)                            # D33: the set-up's step
    a.label('coop_lstate'); a.b(0)                           # D33: the chests' step
    a.label('coop_alive'); a.b(0)                            # D33: bit 0 the visit's knight stands, 1 + p partner p
    a.label('coop_order'); a.b(bytes(4))                     # D33: the chests' order (the knights' places)
    a.label('coop_saved'); a.b(bytes(2 * len(COOP_SAVE) * COOP_PARTNERS))   # D33: the partners' own fields
    a.label('coop_gold'); a.b(0, 0)                          # D33: the lair's gold and items before the first chest
    a.label('coop_items'); a.b(bytes(LAIR_ITEMS))
    a.label('combined'); a.b(0, 0)                           # D15: the record combine changed
    a.label('coop_share'); a.b(0)                            # D33: 1 = a shared chest is open
    a.label('coop_last'); a.b(0)                             # D33: 1 = the last knight's turn at it
    a.label('coop_n'); a.b(0, 0)                             # D33: the knights standing
    a.label('coop_pct'); a.b(0, 0)                           # D33: the chest's extra, percent
    a.label('loot_base'); a.b(0, 0)                          # the lair's own gold before catchup's extra
    a.label('loot_capped'); a.b(0)                            # 1 = catchup added to this chest: the gold capped
    a.label('loot_potion'); a.b(0)                           # 1 = a healing potion was added to this chest
    a.label('coop_gold_share'); a.b(0, 0)                    # D33: what a click on the gold takes
    a.label('coop_gold_left'); a.b(0, 0)                     # D33: ... left of it in this click
    a.label('slot_shifts'); a.b(bytes(SLOT_SHIFTS))          # D33: the recolour's shift by colour slot
    a.label('ptr_back'); a.b(0)                              # D36: 1 = back from the game's input call
    a.label('ptr_bits'); a.b(0)                              # D36: the directions held
    a.label('ptr_t0'); a.b(0, 0)                             # D36: the tick they were pressed
    a.label('ptr_t'); a.b(0, 0)                              # D36: the tick of the last move
    a.label('ench_k'); a.b(bytes(4))                         # D35: each knight's sword's enchantment (0 none)
    a.label('ench_w'); a.b(bytes(4))                         # D35: ... the sword (+40h) it is on
    a.label('lair_ench'); a.b(bytes(LAIR_COUNT))             # D35: each lair's chest: 0 not decided, 1 none, 1 + one
    a.label('hoard_ench'); a.b(0)                            # D35: the dragon's hoard (right after lair_ench)
    a.label('arm_lair'); a.b(bytes(LAIR_COUNT + 1))          # D37: the same for armour enchantments (25 bytes after lair_ench, hoard last)
    a.label('arm_k'); a.b(bytes(4))                          # D37: each knight's armour's enchantment (0 none)
    a.label('arm_w'); a.b(bytes(4))                          # D37: ... the armour (+42h) it is on
    a.label('arm_tp'); a.b(0, 0)                             # D37: the text arm_desc points to
    a.label('horse_x'); a.b(bytes(2))                        # D38: where the knight on the move last was
    a.label('horse_y'); a.b(bytes(2))
    a.label('horse_tick'); a.b(bytes(2))                     # D38: the BIOS tick of its last step
    a.label('horse_ride'); a.b(0)                            # D38: 1 = the horse shows
    a.label('horse_k'); a.b(bytes(4))                        # D38: each knight's horse (0 none, 1-5)
    a.label('horse_s'); a.b(0)                               # D38: slot 4 this stay in town (0 not rolled, 1 empty, 4 or 5 a horse)
    a.label('gv_flag'); a.b(0)                               # D43: 1 during a visit to the tavern or merchant
    a.label('gv_start'); a.b(0, 0)                           # D43: the knight's gold as it began
    a.label('hp_back'); a.b(0)                               # D40: 1 while PlaceIcons draws the panel's horse
    a.label('hi_state'); a.b(0)                              # D38: the next shop slot to place
    a.label('ai_back'); a.b(0)                               # D37: arm_icon: back from PlaceIcons
    a.label('sp_tries'); a.b(0)                              # D37: arm_target: knights passed
    a.label('arm_names')
    for n, name in enumerate(ARM_NAMES):
        a.word(f'arm_name{n}')
    for n, name in enumerate(ARM_NAMES):
        a.label(f'arm_name{n}'); a.b(name.encode() + b'\0')
    for value, name in ARMOUR_NAMES:
        a.label(f'aname_{value:x}'); a.b(name + b'\0')
    a.label('ench_names')
    for n in range(len(ENCH_NAMES)):
        a.word(f'ench_name{n}')
    for n, name in enumerate(ENCH_NAMES):
        a.label(f'ench_name{n}'); a.b(name.encode() + b'\0')
    for value, name in WEAPON_NAMES:
        a.label(f'wname_{value:x}'); a.b(name + b'\0')
    a.label('ench_of_text'); a.b(b' of \0')
    a.label('ench_text'); a.b(ENCH_TEXT + b'\0')
    a.label('coop_text'); a.b(COOP_TEXT + b'\0')
    a.label('battle_text'); a.b(BATTLE_TEXT + b'\0')
    a.label('together_text'); a.b(TOGETHER_TEXT + b'\0')
    a.label('choice_tmp'); a.b(bytes(CHOICE_SIZE * CHOICE_COUNT))   # D33: the map's choices while they are ordered
    a.label('rel_tick'); a.b(bytes(6))                       # D24: ... when the last was
    a.label('chord_on'); a.b(bytes(4))                       # D24: input_chord, per knight: 1 waiting, 2 waited
    a.label('chord_tick'); a.b(bytes(8))                     # D24: ... since when
    a.label('last_read'); a.b(bytes(8))                      # D24: input_log: each knight's last bits (as read, as used)
    a.label('ilog_path'); a.b(ILOG_PATH)
    a.label('ilog_hdr'); a.b(b'IL')                          # D24: input_log: the header written before a fight's entries
    a.label('ilog_n'); a.b(0, 0)
    a.label('ilog_lost'); a.b(0, 0)
    a.label('ilog'); a.b(bytes(6 * ILOG_MAX))
    a.label('cheat_tab')                                     # cheat codes: length, context, id, scan codes
    for name, ctx, cid, scans in CHEATS:
        a.b(len(scans), ctx, cid, *scans)
    a.b(0)
    a.label('cheat_prog'); a.b(bytes(len(CHEATS)))
    a.label('cheat_ctx'); a.b(0)
    a.label('cheat_pending'); a.b(0)
    a.label('cheat_last'); a.b(0, 0)
    a.label('code_t'); a.b(0x00, 0x80)                       # D55: the tick of the last key a code went on with
    a.label('cheat_flags'); a.b(0)
    a.label('cheat_flags2'); a.b(0)                          # D48: F2_DARTS, F2_SABER, F2_GUNSHOT (this fight)
    a.label('gun_src'); a.b(GUN_SRC)                         # D64: GUNSHOT's scripts and hit points (GUN_AREA)
    a.label('df_on'); a.b(0)                                 # D49: DAGGERFALL in this fight
    a.label('df_due'); a.b(0)                                # D49: a dagger to drop in the next pass
    a.label('df_last'); a.b(0, 0)                            # D49: the tick of the last one
    a.label('df_rng'); a.b(0, 0)                             # DAGGERFALL's random state
    a.label('df_src')                                        # D49: the falling dagger's script (DF_SCRIPT)
    a.b(0x90, 0x01, 0, 0, 0, 0, 0, 0)                        # no movement in the script; one frame
    a.b(DF_BANK, DF_PIC, 0x00, 0x02, 0xfe, 0xff, 0xff, 0xff)   # D58: the dagger turned, point down, centred; D59: flag 2 hits
    a.label('darts_lent'); a.b(bytes(25))                    # D48: DARTS lent this object a dagger (obj_index / 2)
    a.label('saber_piece'); a.b(0)                           # D51: the frame being drawn is a lightsaber's piece
    a.label('sab_g'); a.b(0)                                 # D51: its glow's colour
    a.label('saber_frame'); a.b(0)                           # D57: its KN4.OB frame
    a.label('sab_k'); a.b(0, 0)                              # D59: -1 the frame as it is, 0-15 mirrored with that padding
    a.label('saber_ltab')                                    # D57: each frame's centre line (0: none)
    for n in range(SABER_FRAMES_TAB):
        if n in SABER_LINES: a.word(f'saber_l{n}')
        else: a.b(0, 0)
    for n, pts in SABER_LINES.items():
        a.label(f'saber_l{n}')
        a.b(len(pts))                                        # D59: the count, then (x, y)s
        for x, y in pts: a.b(x, y)
        a.b(0xff)
    a.label('sab_kind'); a.b(bytes(25))                      # D51: a lightsaber's deadly blow on this object: its death (SABER_KINDS)
    a.label('sab_last'); a.b(0)                              # D51: saber_finish: the kind
    a.label('bars_on'); a.b(0)                               # D54: BEATEMUP in this fight
    a.label('score_won'); a.b(0)                             # D56: this fight's winner counted
    a.label('score_live'); a.b(0)                            # D56: [897Dh] seen set in this fight (it went on)
    a.label('bars_keep'); a.b(0)                             # D57: BEATEMUP typed in the first menu: every practice fight
    a.label('score_saved'); a.b(0)                           # D56: the score's box kept
    a.label('box_mode'); a.b(0)                              # D56: score_box: 0 keep, 1 put back
    a.label('pal_mode'); a.b(0)                              # D56: pal_pick: 0 red, 1 turquoise
    a.label('score_ord'); a.b(b'\xff' * 4)                   # D56: the knight records from the left at the start
    a.label('ord_bits'); a.b(1, 2, 4, 8)
    a.label('score_bg'); a.b(bytes(SCORE_BOX_W * SCORE_BOX_H))   # D56: the background under the score
    a.label('bars_n'); a.b(0)                                # ... the bars (0: not laid out yet)
    a.label('bars_who'); a.b(bytes(BARS_MAX))                # ... each one's side (BARS_COMP_SIDE, BARS_TEAM + n, record n)
    a.label('bars_x'); a.b(bytes(2 * BARS_MAX))              # ... their left edges
    a.label('bars_len'); a.b(bytes(2 * BARS_MAX))            # ... their filled lengths drawn
    a.label('bars_col'); a.b(bytes(BARS_MAX))                # ... their colours drawn
    a.label('bars_w'); a.b(0, 0)                             # ... a bar's width
    a.label('bars_y'); a.b(0, 0)                             # ... their top
    a.label('bars_hum'); a.b(0)                              # ... the human knight records in the fight (bits)
    a.label('bars_crec'); a.b(0)                             # ... the computer's knight records in it
    a.label('bars_drag'); a.b(0)                             # ... 1: the dragon in it
    a.label('bars_full'); a.b(0, 0)                          # ... the computer side's most HP seen
    a.label('bars_top'); a.b(0, 0)                           # ... one monster's most HP seen
    a.label('bars_recs')
    for rec in KNIGHTS:
        a.b(rec & 0xff, rec >> 8)
    a.label('score_sig'); a.b(bytes(SCORE_SIG))              # D52: this practice fight's kind
    a.label('score_prev'); a.b(b'\xff' * SCORE_SIG)          # D52: the previous one's
    a.label('score_tab'); a.b(bytes(SCORE_KINDS * SCORE_ENTRY))   # D52: the kinds' wins
    a.label('score_used'); a.b(0)                            # ... a bit for each entry in use
    a.label('score_next'); a.b(0)                            # ... the next to take when none is free
    a.label('score_cur'); a.b(0xff)                          # ... this fight's entry, FFh none
    a.label('score_pend'); a.b(0)                            # ... 1: to show in this fight
    a.label('score_t0'); a.b(0, 0)                           # ... the fight's first tick
    a.label('score_col'); a.b(b'\xff' * 4)                   # ... the knights' colours seen
    a.label('score_txt'); a.b(bytes(2 * 16 + 1))             # ... the text: (glyph, colour) pairs, FFh
    a.label('score_font')
    for rows in SCORE_FONT:
        a.b(*rows)
    a.label('sab_striker'); a.b(0, 0)                        # ... and who struck
    a.label('knight_haste'); a.b(0)
    a.label('one_more'); a.b(0)
    a.label('one_more_used'); a.b(0, 0)
    a.label('fore_saved'); a.b(bytes(2 * len(KNIGHT_STRIKES)))
    a.label('prev_hp'); a.b(b'\x00\x80' * 25)
    a.label('cheat_killed'); a.b(bytes(25))
    a.label('hotstuff'); a.b(0)                              # HOTSTUFF typed in the first menu
    a.label('dragon_ctl'); a.b(0)                            # HOTSTUFF: player 1 is the dragon in this practice
    a.label('dragon_bits'); a.b(0)                           # its input bits at its last move
    a.label('cu_level'); a.b(0)                              # catchup: this chest's level
    a.label('cu_seed'); a.b(0x35, 0x4a)                      # catchup: the random numbers
    a.label('cu_items'); a.b(bytes(CU_ITEMS))
    a.label('air_on'); a.b(bytes(25))                        # LUNAR: by object number, 1 = flying
    a.label('air_vx'); a.b(bytes(25))                        # ... its speeds (signed)
    a.label('air_vy'); a.b(bytes(25))
    a.label('air_tick'); a.b(0)
    a.label('p3_ctl'); a.b(JOY_A_CONTROL)                    # D12: knight 3's input (+9), practice_mode
    a.label('p4_ctl'); a.b(JOY_B_CONTROL, 0)                 # knight 4's, a spare byte
    a.label('fight_begun'); a.b(0)                           # this fight's first frame has been
    a.label('q_codes'); a.b(0, 0)                            # fight codes queued (bit n: CHEAT_FIGHT_CODES[n])
    a.label('q_where'); a.b(0)                               # ... for 1 the next practice fight, 2 the game's
    a.label('q_added'); a.b(0)                               # cheat_flags the queue turned on in this fight
    a.label('q_bit')
    for i, name in enumerate(CHEAT_FIGHT_CODES):
        a.b(struct.pack('<H', 1 << i))
    a.label('q_clear')
    for i, name in enumerate(CHEAT_FIGHT_CODES):
        m = sum(1 << CHEAT_FIGHT_CODES.index(n) for n in FIGHT_CLASH.get(name, ()))
        a.b(struct.pack('<H', 0xffff ^ m))
    a.label('hard_eff'); a.b(0)                              # the TOOEASY rules in this fight (hard_flags)
    a.label('cheese_eff'); a.b(0)                            # the anti-cheese rules in this fight
    a.label('bd_on'); a.b(0)                                 # BLACKDEATH was typed
    a.label('hard_ai'); a.b(0)                               # TOOEASY 1 = the harder fights, TOOHARD 2 = the easier, 0
    a.label('easy_eff'); a.b(0)                              # TOOHARD's rules in this fight (hard_flags)
    a.label('mon_ctl'); a.b(0)                               # DIRTYRAT...: the type player 1 is (0 = none)
    a.label('mon_obj'); a.b(0, 0)                            # ... its object
    a.label('mon_dive'); a.b(0)                              # SWAMPTHING: 1 = its own dive, the grab may follow
    a.label('mr_dist'); a.b(0, 0)                            # nearest_knight: a knight's distance in x
    a.label('nk_rx'); a.b(0, 0)                              # ... how far in x
    a.label('nk_rz'); a.b(0, 0)                              # ... and in depth
    a.label('rat_victim'); a.b(0, 0)                         # rat_hang, rat_ride: the knight a ratman holds
    a.label('paw_set'); a.b(0)                               # HOTSTUFF: the paw's reaction set (paw_saved kept)
    a.label('paw_saved'); a.b(0, 0)
    a.label('mh_have'); a.b(0)                               # mud_escape: 1 = the keys read
    a.label('mon_jump'); a.b(0)                              # JUMPSCARE: 1 = this jump crushes a knight below
    a.label('mon_crush'); a.b(0)                             # ... 1 = this grab crushes the knight held
    a.label('mon_have'); a.b(0)                              # ... 1 = the keys read, this decision
    a.label('hard_hit'); a.b(bytes(2 * 25))                  # TOOEASY: each object's last counted hit (BIOS tick)
    a.label('day_left'); a.b(bytes(8))                       # rest heal: each knight's movement left at its last turn's end
    a.label('day_budget'); a.b(bytes(8))                     # rest heal: and that turn's budget
    a.label('mud_puller'); a.b(0, 0)                         # K25: the mudman that pulled a knight under
    a.label('balok_victim'); a.b(0, 0)                       # K28: the knight the Balok holds (or held last)
    a.label('impaled'); a.b(bytes(2 * MONSTER_COUNT))        # K28: by monster slot, the knight a trogg speared
    a.label('gore_pass'); a.b(0)                             # D22: what gore_clean does to the frame being drawn
    a.label('conv_jump'); a.b(0, 0)                          # D23: the routine for this frame's mask
    a.label('conv_routines')                                 # D23: by mask, the routine (0 = the game's converter)
    for mask in range(32):
        if mask in CONVERT_MASKS:
            a.word(f'conv_{mask:02x}')
        else:
            a.b(0, 0)
    a.label('conv_t')                                        # D23: a byte's bits, the highest first, as 8 bytes
    for v in range(256):
        a.b(*[(v >> (7 - j)) & 1 for j in range(8)])
    a.label('rc_xlat'); a.b(bytes(range(256)))               # D23: the recolour's table (identity between frames)
    a.label('marker_tick'); a.b(0, 0)                        # D22: the BIOS tick of the last hit marker
    a.label('eff_script'); a.b(0, 0)                         # spawn_marker / spawn_effect: the effect's script
    a.label('eff_bank'); a.b(0, 0)                           # and its bank table
    a.label('key_tick'); a.b(bytes(256))                     # D24: each key's last press (BIOS tick)
    a.label('key_pending'); a.b(bytes(128))                  # D24: 1 = its release is kept back
    a.label('key_pending_any'); a.b(0)
    a.label('buf_bits'); a.b(0, 0, 0)                           # D24: each player's fire noted (bits as 83C0), 0 = none
    a.label('buf_tick'); a.b(0, 0, 0, 0, 0, 0)                     # D24: when
    a.label('last_hitter'); a.b(bytes(48))                   # D20: by knight or monster slot (victim_slot), what hit it last
    a.label('last_strike'); a.b(bytes(48))                   # D20: ... that object's +28h (low) and type (high)
    a.label('team_t0'); a.b(0, 0)
    a.label('bk'); a.b(0)                                    # D19: 1 = a Black Knight practice, 2 = the B key's
    a.label('bk_count'); a.b(0)                              # D19: Black Knights made in this fight
    a.label('bk_saved'); a.b(0)                              # D19: 1 = bk_old holds MAIN's words
    a.label('bk_old'); a.b(bytes(6))
    a.label('bk_face'); a.b(bytes(BK_FACE))
    a.label('bk_x'); a.b(struct.pack('<4h', *BK_X))
    a.label('thrower'); a.b(0, 0)                            # D19: the object throwing a dagger now
                            # D14: the BIOS tick of the fight's first frame
    # the table is searched from its start at every int 63h: the hooks that run for every piece drawn, every object
    # and every hit test in a fight come first (in the order HOT), the rest after them in their own order
    a.label('hooks')
    entries = [(hook_bytes(where, old, kind)[1], kind) for where, old, kind in
               HOOKS + [(where, old, 'fate') for where, old, _ in FATE_HOOKS]] + list(PRACTICE_HOOKS)
    if len({ret for ret, _ in entries}) != len(entries):
        raise ValueError('two hooks return to the same address')
    entries.sort(key=lambda e: HOT.index(e[1]) if e[1] in HOT else len(HOT))
    for ret, kind in entries:
        a.b(ret & 0xff, ret >> 8); a.word('rules_' + kind)
    a.b(0, 0)
    a.label('fate_sites')                                    # return address, routine, stream * 2
    for where, old, stream in FATE_HOOKS:
        target = (where + 3 + struct.unpack('<h', bytes.fromhex(old)[1:])[0]) & 0xffff
        a.b(struct.pack('<HHH', where + 2, target, 2 * stream))
    a.label('fate_state'); a.b(bytes(2 * FATE_STREAMS))
    a.label('fate_target'); a.b(0, 0)
    a.label('multi'); a.b(0)                                 # (a word with mon_mode: separate inputs)
    a.label('mon_mode'); a.b(0)                              # 1 = a monster code's fight (player 1 a monster)
    a.label('mon_req'); a.b(0)                               # the monster type a menu code asked for
    a.label('k1_out'); a.b(0)                                # 1 = knight 1 is out of that fight (1-3 knights)
    a.label('k1_ctl'); a.b(0)                                # knight 1's +9 before the third key set took it
    a.label('held_scan'); a.b(0)                             # first menu: a key held back for a code (D, J)
    a.label('snd_req'); a.b(0)                               # a code typed whole: its sound to play
    a.label('snd_wait'); a.b(0)                              # the sound is playing (back to the hook's site)
    a.label('snd_ax'); a.b(0, 0)
    a.label('multi_x'); a.b(0)                                 # D12: 0, or 3-4 knights in this practice
    a.label('teams'); a.b(0)                                 # D14: 1 = the 3-4 player practice in teams
    a.label('monster'); a.b(0)                               # D14: the practice choice (PRACTICE_KEYS), 0 = knight
    a.label('init_state'); a.b(0)                            # D14: the monster set-up's calls so far
    a.label('practice_keys')                                 # D14: (scan code, choice) pairs, 0 = the end
    for scan, choice in PRACTICE_KEYS:
        a.b(scan, choice)
    a.b(0, 0)
    a.label('practice_lairs'); a.b(bytes(PRACTICE_LAIRS))
    a.label('knight_list')                                   # D15: the four knight records in order
    for rec in KNIGHTS:
        a.b(rec & 0xff, rec >> 8)
    a.label('add_state'); a.b(0)                             # D12: InitPractice's added calls so far
    a.label('joy_a'); a.b(0, 0)                              # D12: joystick bits last read
    a.label('joy_b'); a.b(0, 0)
    for name, size in (('td_start', 8), ('td_seen', 8), ('td_fast', 8), ('td_stag', 48), ('td_atk', 48), ('td_pause', 24), ('td_roll', 24), ('td_rolled', 48), ('dummy', 1), ('dm_seen', 48), ('dm_next', 48), ('dm_seq', 48), ('td_fk', 24), ('dg_hp', 8), ('dg_n', 8), ('dg_tick', 8), ('dd_lo', 2), ('dd_hi', 2), ('dd_on', 1), ('td_mist', 1), ('td_after', 1)):
        a.label(name); a.b(*bytes(size))                     # D46
    a.label('call_target'); a.b(0, 0)                        # D12: call_game
    a.label('call_ret'); a.b(0, 0)
    a.label('recolour'); a.b(0)                              # D13: first pixel value to move in this frame, 0 = none
    a.label('level'); a.b(16)                                # D13: fade level of entries 32-37, 0-16
    a.label('words_left'); a.b(NEW_WORDS)
    a.label('colour_sites')                                  # D13/D15/D19: where MAIN keeps the colour words: 32-43
    for sites in [sites for _, _, sites in RECOLOUR] + [GREEN_SITES, BLACK_SITES, BLUE_SITES]:
        for site in sites:
            a.b(site & 0xff, site >> 8)
    a.label('rc_shift'); a.b(RECOLOUR_SHIFT)                 # D15: the shift of the frame being recoloured
    a.label('sw_shift'); a.b(0)                              # D31: the sword's shift in this frame (pixels 1-4), 0 = none
    a.label('sword_rgb')                                     # D31: entries 48-59
    for _, colours in SWORD_TINTS + ARMOUR_TINTS:
        for rgb in colours:
            a.b(bytes(rgb))
    a.label('coop'); a.b(0)                                  # D15: knights in a co-op practice, 0 = none
    a.label('vs_monsters'); a.b(0)                           # D15: 1 = a practice against monsters
    a.label('quitting'); a.b(0)                              # D15: 1 = Esc has ended this practice fight
    a.label('last_hit'); a.b(bytes(4))                       # K6: BIOS ticks of the last counted hit (0 = none)
    a.label('own_strength'); a.b(0)                          # D15: knight 1's own strength and max HP during combine
    a.label('own_max_hp'); a.b(0, 0)
    a.label('last_target'); a.b(bytes(2 * 21))               # D15: each monster's knight (20 slots, the dragon)
    a.label('target_hold'); a.b(bytes(2 * 21))               # ... updates it keeps a new one whatever the distances
    a.label('coop_knights')                                  # D15: record, control, colour slot, x
    for rec, control, colour, x in COOP_KNIGHTS:
        a.b(struct.pack('<HBBH', rec, control, colour, x))
    a.label('spawns')
    for x, y in SPAWNS:
        a.b(struct.pack('<HH', x, y))
    a.label('section_ptrs')
    for n in range(len(SECTIONS)):
        a.word('rules_table', n * SECTION_SIZE)
    a.label('rules_table'); a.b(table or rules_default_table())
    a.label('rec4'); a.b(0, 0)
    a.label('start_pos'); a.b(bytes(16))                     # x, y of each knight record when the game started

def make_savehook(rules_table=None):
    a = Asm(0x100)
    a.near(0xe9, 'install')                                  # jmp install
    a.b(SIGNATURE)
    # --- int 66h: fight starts (resident) ---
    a.label('fight_handler')
    a.b(0xc7, 0x06, 0x41, 0x78, 0x00, 0x00)                  # mov word [7841h], 0   (replaced MAIN instruction)
    a.b(0x2e, 0xc7, 0x06); a.word('name_ptr'); a.word('fight_name')   # mov word cs:[name_ptr], fight_name
    a.label('save_state')                                    # shared: save under the name at cs:[name_ptr]
    a.b(0xfb)                                                # sti
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x55, 0x1e, 0x06)   # push ax bx cx dx si di bp ds es
    a.b(0x0e, 0x1f)                                          # push cs / pop ds
    a.b(0x81, 0x3e); a.word('name_ptr'); a.word('fight_name')   # cmp word [name_ptr], fight_name
    a.short(0x75, 'save_check')                              # jne save_check
    # D17: the fight's CPU speed by its knights: a co-op practice's count, D12's 3-4, 2 in a two-player practice,
    # else 1 (MAIN's DS is the one pushed last but one)
    a.b(0x8b, 0xec, 0x8e, 0x46, 0x02, 0x33, 0xdb)            # mov bp, sp / mov es, [bp+2] / xor bx, bx
    a.b(0x8a, 0x1e); a.word('coop'); a.b(0x0a, 0xdb)         # mov bl, [coop] / or bl, bl
    a.short(0x75, 'fs_count')                                # jnz fs_count
    a.b(0x8a, 0x1e); a.word('multi'); a.b(0x0a, 0xdb)        # mov bl, [multi] / or bl, bl
    a.short(0x75, 'fs_count')                                # jnz fs_count
    a.b(0xb3, 0x01)                                          # mov bl, 1
    a.b(0x26, 0x83, 0x3e, MENU_OPTION & 0xff, MENU_OPTION >> 8, PRACTICE_OPTION)   # cmp word es:[0704h], 2
    a.short(0x75, 'fs_count')                                # jne fs_count
    a.b(0x26, 0x83, 0x3e, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8, 0x02)   # cmp word es:[0940h], 2
    a.short(0x72, 'fs_count')                                # jb fs_count
    a.b(0xb3, 0x02)                                          # mov bl, 2
    a.label('fs_count')
    a.b(0x4b, 0x83, 0xe3, 0x03, 0xd1, 0xe3)                  # dec bx / and bx, 3 / shl bx, 1
    a.b(0x8b, 0xb7); a.word('fight_tails')                   # mov si, [bx+fight_tails]
    a.near(0xe8, 'speed')                                    # call speed
    a.label('save_check')
    a.near(0xe8, 'checkpoint')                               # call checkpoint   save modes
    a.b(0x80, 0x3e); a.word('rules_table', G_SAVE_MODE); a.b(MANUAL_ONLY)   # cmp byte [save_mode], 2
    a.short(0x73, 'save_skip')                               # jae save_skip     no automatic saves
    a.near(0xe8, 'mcb')                                      # call mcb          es = MAIN's memory block
    a.b(0xbe, 0x08, 0x00)                                    # mov si, 8
    a.b(0xbf); a.word('old_name')                            # mov di, old_name
    a.b(0xb9, 0x08, 0x00)                                    # mov cx, 8
    a.label('save_name')
    a.b(0x26, 0x8a, 0x04, 0x88, 0x05, 0x46, 0x47)            # mov al, es:[si] / mov [di], al / inc si / inc di
    a.short(0xe2, 'save_name')                               # loop save_name
    a.b(0x8b, 0x36); a.word('name_ptr')                      # mov si, [name_ptr]
    a.near(0xe8, 'number_name')                              # call number_name  FIGHT1-5 or TURN1-4, in turn
    a.near(0xe8, 'set_name')                                 # call set_name
    a.near(0xe8, 'refresh')                                  # call refresh      DOSBox-X now sees the new name
    a.near(0xe8, 'save_wait')                                # call save_wait    autosave happens here
    a.near(0xe8, 'accept')                                   # call accept       (a loaded autosave resumes here)
    a.near(0xe8, 'mcb')                                      # call mcb
    a.b(0xbe); a.word('old_name')                            # mov si, old_name
    a.near(0xe8, 'set_name')                                 # call set_name
    a.near(0xe8, 'refresh')                                  # call refresh      back to MAIN
    a.label('save_skip')
    a.b(0x07, 0x1f, 0x5d, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58)   # pop es ds bp di si dx cx bx ax
    a.b(0xcf)                                                # iret

    # --- int 65h: a knight's turn starts on the map (resident) ---
    # A human's turn is saved first (save_state). Then every turn, the computer's too, plays the game's menu sound
    # (TURN_SOUND, as 1000:D6E1): the return goes to 1000:5970 with ax = the sound, and 5970 returns to the int 65h
    # again (TURN_SITE), whose second pass puts the game's ax back and goes on
    a.label('turn_handler')
    a.b(0x2e, 0x80, 0x3e); a.word('turn_pass'); a.b(0x00); a.short(0x74, 'turn_first')   # cmp byte cs:[turn_pass], 0
    a.b(0x2e, 0xc6, 0x06); a.word('turn_pass'); a.b(0x00)   # the second pass: after the sound
    a.b(0x2e, 0xa1); a.word('turn_ax'); a.b(0xcf)            # mov ax, cs:[turn_ax] / iret
    a.label('turn_first')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77e8h]       (replaced MAIN instruction)
    a.b(0x83, 0x7c, 0x20, COMPUTER)                          # cmp word [si+20h], 4  computer knight?
    a.short(0x74, 'turn_sound')                              # je turn_sound         no save for computer turns
    a.b(0x2e, 0xc6, 0x06); a.word('map_hold'); a.b(0x01)     # mov byte cs:[map_hold], 1   D26: keys let go first
    a.b(0x2e, 0xc7, 0x06); a.word('name_ptr'); a.word('turn_name')    # mov word cs:[name_ptr], turn_name
    a.b(0x9c, 0x0e); a.near(0xe8, 'save_state')              # pushf / push cs / call save_state   (it irets)
    a.label('turn_sound')
    a.b(0x2e, 0xa3); a.word('turn_ax')                       # mov cs:[turn_ax], ax
    a.b(0x2e, 0xc6, 0x06); a.word('turn_pass'); a.b(0x01)    # mov byte cs:[turn_pass], 1
    a.b(0x83, 0xec, 0x02, 0x55, 0x8b, 0xec, 0x50)            # sub sp, 2 / push bp / mov bp, sp / push ax
    a.b(0x8b, 0x46, 0x06, 0x89, 0x46, 0x04)                  # mov ax, [bp+6] / mov [bp+4], ax   the CS, a word lower
    a.b(0x8b, 0x46, 0x08, 0x89, 0x46, 0x06)                  # mov ax, [bp+8] / mov [bp+6], ax   the flags
    a.b(0xc7, 0x46, 0x08, TURN_SITE & 0xff, TURN_SITE >> 8)  # mov word [bp+8], A63Fh   5970's return: here again
    a.b(0xc7, 0x46, 0x02, SOUND & 0xff, SOUND >> 8)          # mov word [bp+2], 5970h
    a.b(0x58, 0x5d, 0xb8, TURN_SOUND, 0x00, 0xcf)            # pop ax / pop bp / mov ax, sound / iret

    # --- int 62h: weapon pick on the duel loot screen (resident); si = winner, di = loser, bp = loser's weapon ---
    a.label('loot_handler')
    a.b(0x83, 0xfd, SHARPNESS)                               # cmp bp, 19h
    a.short(0x75, 'loot_weapon')                             # jne loot_weapon
    a.b(0x53)                                                # push bx
    a.b(0x8b, 0x5c, 0x44, 0xc7, 0x47, 0x04, 0x01, 0x00)      # mov bx, [si+44h] / mov word [bx+4], 1   winner's item
    a.b(0x8b, 0x5d, 0x44, 0xc7, 0x47, 0x04, 0x00, 0x00)      # mov bx, [di+44h] / mov word [bx+4], 0   loser's item
    a.b(0x5b)                                                # pop bx
    a.label('loot_weapon')
    a.b(0x3b, 0x6c, 0x40)                                    # cmp bp, [si+40h]      (replaced MAIN instructions)
    a.short(0x7c, 'loot_done')                               # jl loot_done
    a.b(0x89, 0x6c, 0x40)                                    # mov [si+40h], bp
    a.label('loot_done')
    a.b(0xcf)                                                # iret

    rules_code(a)

    a.label('mcb')                                           # es = memory block of the current PSP
    a.b(0xb4, 0x62, 0xcd, 0x21)                              # mov ah, 62h / int 21h
    a.b(0x4b, 0x8e, 0xc3, 0xc3)                              # dec bx / mov es, bx / ret

    # number_name: DS = CS, si = fight_name or turn_name: puts the next number into the name and counts on. Each
    # numbered name has one autosave slot, so a wait that spans two of DOSBox-X's checks saves twice into the same
    # slot instead of filling the next one. The counters live in SAVEHOOK.SLT (a missing file keeps the ones here)
    a.label('number_name')
    a.b(0x50, 0x53, 0x51, 0x52, 0x57)                        # push ax bx cx dx di
    a.near(0xe8, 'amiga_check')                              # call amiga_check   (D65)
    a.b(0xb8, 0x00, 0x3d, 0xba); a.word('slot_path')         # mov ax, 3D00h / mov dx, slot_path
    a.b(0xcd, 0x21)                                          # int 21h     open
    a.short(0x72, 'nn_pick')                                 # jc nn_pick
    a.b(0x8b, 0xd8, 0xb4, 0x3f, 0xb9, 0x02, 0x00, 0xba); a.word('slot_next')   # mov bx, ax / mov ah, 3Fh / mov cx, 2 / mov dx, slot_next
    a.b(0xcd, 0x21, 0xb4, 0x3e, 0xcd, 0x21)                  # int 21h (read) / mov ah, 3Eh / int 21h (close)
    a.label('nn_pick')
    a.b(0x81, 0xfe); a.word('fight_name')                    # cmp si, fight_name
    a.short(0x75, 'nn_turn')                                 # jne nn_turn
    a.b(0xbb, 0x01, 0x00, 0xb1, FIGHT_SLOTS)                 # mov bx, 1 / mov cl, 5
    a.b(0xbf); a.word('fight_name', len(FIGHT_NAME))         # mov di, fight_name + 5   the digit
    a.short(0xeb, 'nn_have')                                 # jmp nn_have
    a.label('nn_turn')
    a.b(0x33, 0xdb, 0xb1, TURN_SLOTS)                        # xor bx, bx / mov cl, 4
    a.b(0xbf); a.word('turn_name', len(TURN_NAME))           # mov di, turn_name + 4
    a.label('nn_have')
    a.b(0x8a, 0x87); a.word('slot_next')                     # mov al, [bx+slot_next]
    a.b(0x3a, 0xc1); a.short(0x72, 'nn_in')                  # cmp al, cl / jb nn_in
    a.b(0x32, 0xc0)                                          # xor al, al          (a damaged file)
    a.label('nn_in')
    a.b(0x8a, 0xe0, 0x80, 0xc4, 0x31, 0x88, 0x25)            # mov ah, al / add ah, '1' / mov [di], ah
    a.b(0xfe, 0xc0, 0x3a, 0xc1); a.short(0x72, 'nn_next')    # inc al / cmp al, cl / jb nn_next
    a.b(0x32, 0xc0)                                          # xor al, al          round again
    a.label('nn_next')
    a.b(0x88, 0x87); a.word('slot_next')                     # mov [bx+slot_next], al
    a.b(0xb4, 0x3c, 0x33, 0xc9, 0xba); a.word('slot_path')   # mov ah, 3Ch / xor cx, cx / mov dx, slot_path
    a.b(0xcd, 0x21)                                          # int 21h     create
    a.short(0x72, 'nn_end')                                  # jc nn_end
    a.b(0x8b, 0xd8, 0xb4, 0x40, 0xb9, 0x02, 0x00, 0xba); a.word('slot_next')   # mov bx, ax / mov ah, 40h / mov cx, 2 / mov dx, slot_next
    a.b(0xcd, 0x21, 0xb4, 0x3e, 0xcd, 0x21)                  # int 21h (write) / mov ah, 3Eh / int 21h (close)
    a.label('nn_end')
    a.b(0x5f, 0x5a, 0x59, 0x5b, 0x58, 0xc3)                  # pop di dx cx bx ax / ret

    a.label('set_name')                                      # copy 8 bytes ds:si -> es:0008
    a.b(0xbf, 0x08, 0x00, 0xb9, 0x08, 0x00)                  # mov di, 8 / mov cx, 8
    a.label('set_loop')
    a.b(0x8a, 0x04, 0x26, 0x88, 0x05, 0x46, 0x47)            # mov al, [si] / mov es:[di], al / inc si / inc di
    a.short(0xe2, 'set_loop')                                # loop set_loop
    a.b(0xc3)                                                # ret

    # speed (D17): DS = CS, si = a command line (fight_tail, map_tail): DOSBox-X's CONFIG -set cycles=... through its
    # shell, run as a child like the name refresh; an empty line changes nothing. All registers but si may change
    a.label('speed')
    a.b(0x80, 0x3c, 0x00); a.short(0x74, 'speed_end')        # cmp byte [si], 0 / je speed_end
    a.b(0xc6, 0x06); a.word('sped'); a.b(0x01)               # mov byte [sped], 1
    a.b(0x89, 0x36); a.word('param_block', 2)                # mov [param_block+2], si   the command line
    a.b(0xba); a.word('cmd_path')                            # mov dx, cmd_path
    a.b(0x56); a.near(0xe8, 'exec')                          # push si / call exec
    a.b(0x5e, 0xc7, 0x06); a.word('param_block', 2); a.word('tail')   # pop si / mov word [param_block+2], tail
    a.label('speed_end')
    a.b(0xc3)                                                # ret

    a.label('refresh')                                       # run the child so that DOSBox-X re-reads the name
    a.b(0xba); a.word('child_path')                          # mov dx, child_path
    a.label('exec')                                          # dx = the program to run (all registers may change)
    a.b(0xa1); a.word('reserve')                             # mov ax, [reserve]
    a.b(0x0b, 0xc0)                                          # or ax, ax
    a.short(0x74, 'no_free')                                 # jz no_free
    a.b(0x8e, 0xc0, 0xb4, 0x49, 0xcd, 0x21)                  # mov es, ax / mov ah, 49h / int 21h   free it
    a.label('no_free')
    a.b(0x2e, 0x8c, 0x16); a.word('save_ss')                 # mov cs:[save_ss], ss
    a.b(0x2e, 0x89, 0x26); a.word('save_sp')                 # mov cs:[save_sp], sp
    a.b(0x0e, 0x07)                                          # push cs / pop es
    a.b(0xbb); a.word('param_block')                         # mov bx, param_block
    a.b(0xb8, 0x00, 0x4b, 0xcd, 0x21)                        # mov ax, 4B00h / int 21h          exec
    a.b(0xfa)                                                # cli
    a.b(0x2e, 0x8e, 0x16); a.word('save_ss')                 # mov ss, cs:[save_ss]
    a.b(0x2e, 0x8b, 0x26); a.word('save_sp')                 # mov sp, cs:[save_sp]
    a.b(0xfb, 0x0e, 0x1f)                                    # sti / push cs / pop ds
    a.b(0xc7, 0x06); a.word('reserve'); a.b(0x00, 0x00)      # mov word [reserve], 0
    a.b(0xb4, 0x48, 0xbb, RESERVE_PARAS & 0xff, RESERVE_PARAS >> 8, 0xcd, 0x21)   # mov ah,48h / mov bx,n / int 21h
    a.short(0x72, 'no_alloc')                                # jc no_alloc
    a.b(0xa3); a.word('reserve')                             # mov [reserve], ax
    a.label('no_alloc')
    a.b(0xc3)                                                # ret

    # save_wait (DS = CS, the name numbered): as wait, but ends as soon as the name's save file has a new date or
    # time (DOSBox-X's autosave has written it; a loaded save resumes here and ends at once)
    a.label('save_wait')
    a.b(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x06)            # push ax bx cx dx si di es
    a.b(0xa0); a.word('turn_name', len(TURN_NAME))           # mov al, [turn_name + 4]   the digit
    a.b(0x81, 0x3e); a.word('name_ptr'); a.word('fight_name')   # cmp word [name_ptr], fight_name
    a.short(0x75, 'sw_turn')
    a.b(0xa0); a.word('fight_name', len(FIGHT_NAME)); a.b(0x04, TURN_SLOTS)   # mov al, [fight_name + 5] / add al, 4
    a.label('sw_turn')
    a.b(0x2c, ord('1'), 0x32, 0xe4, 0xb1, 0x04, 0xd3, 0xe0)  # sub al, '1' / xor ah, ah / mov cl, 4 / shl ax, cl
    a.b(0x05); a.word('save_paths'); a.b(0x8b, 0xf0)         # add ax, save_paths / mov si, ax   its file
    a.near(0xe8, 'file_stamp')                               # call file_stamp   dx:cx = its date and time now
    a.b(0x89, 0x16); a.word('sw_stamp', 2); a.b(0x89, 0x0e); a.word('sw_stamp')   # mov [sw_stamp+2], dx / mov [sw_stamp], cx
    a.b(0xb8, 0x40, 0x00, 0x8e, 0xc0)                        # mov ax, 40h / mov es, ax
    a.b(0x26, 0x8b, 0x1e, 0x6c, 0x00, 0x8b, 0xfb)            # mov bx, es:[6Ch] / mov di, bx   the last tick seen
    a.b(0x83, 0xc3, WAIT_TICKS)                              # add bx, WAIT_TICKS
    a.b(0xc6, 0x06); a.word('sw_spin'); a.b(WAIT_LIMIT_HI)   # mov byte [sw_spin], WAIT_LIMIT_HI
    a.b(0x33, 0xc9)                                          # xor cx, cx
    a.label('sw_loop')
    a.b(0x26, 0xa1, 0x6c, 0x00)                              # mov ax, es:[6Ch]
    a.b(0x50, 0x2b, 0xc3, 0x58); a.short(0x79, 'sw_done')    # push ax / sub ax, bx / pop ax / jns sw_done   time is up
    a.b(0x3b, 0xc7); a.short(0x74, 'sw_spin_on')             # cmp ax, di / je sw_spin_on   the same tick
    a.b(0x8b, 0xf8, 0x51)                                    # mov di, ax / push cx
    a.near(0xe8, 'file_stamp')                               # call file_stamp
    a.b(0x3b, 0x0e); a.word('sw_stamp'); a.b(0x59); a.short(0x75, 'sw_done')    # cmp cx, [sw_stamp] / pop cx / jne
    a.b(0x3b, 0x16); a.word('sw_stamp', 2); a.short(0x75, 'sw_done')            # cmp dx, [sw_stamp+2] / jne   saved
    a.label('sw_spin_on')
    a.short(0xe2, 'sw_loop')                                 # loop sw_loop
    a.b(0xfe, 0x0e); a.word('sw_spin'); a.short(0x75, 'sw_loop')   # dec byte [sw_spin] / jnz   (ticks stopped)
    a.label('sw_done')
    a.b(0x07, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58, 0xc3)      # pop es di si dx cx bx ax / ret
    # file_stamp: si = a file name -> dx = its date, cx = its time (FFFFh both if it cannot be opened); keeps bx, si
    a.label('file_stamp')
    a.b(0x53, 0xb8, 0x00, 0x3d, 0x8b, 0xd6, 0xcd, 0x21)      # push bx / mov ax, 3D00h / mov dx, si / int 21h   open
    a.short(0x72, 'fs_none')
    a.b(0x8b, 0xd8, 0xb8, 0x00, 0x57, 0xcd, 0x21)            # mov bx, ax / mov ax, 5700h / int 21h   its date, time
    a.b(0x9c, 0x51, 0x52, 0xb4, 0x3e, 0xcd, 0x21, 0x5a, 0x59, 0x9d)   # pushf / push cx dx / close / pop dx cx / popf
    a.short(0x73, 'fs_end')
    a.label('fs_none')
    a.b(0xb9, 0xff, 0xff, 0x8b, 0xd1)                        # mov cx, FFFFh / mov dx, cx
    a.label('fs_end')
    a.b(0x5b, 0xc3)                                          # pop bx / ret

    a.label('wait')                                          # wait WAIT_TICKS BIOS ticks
    a.b(0xb8, 0x40, 0x00, 0x8e, 0xc0)                        # mov ax, 40h / mov es, ax
    a.b(0x26, 0x8b, 0x1e, 0x6c, 0x00)                        # mov bx, es:[6Ch]
    a.b(0x83, 0xc3, WAIT_TICKS)                              # add bx, WAIT_TICKS
    a.b(0x33, 0xc9, 0xba, WAIT_LIMIT_HI, 0x00)               # xor cx, cx / mov dx, WAIT_LIMIT_HI
    a.label('wait_loop')
    a.b(0x26, 0xa1, 0x6c, 0x00, 0x2b, 0xc3)                  # mov ax, es:[6Ch] / sub ax, bx
    a.short(0x79, 'wait_done')                               # jns wait_done
    a.short(0xe2, 'wait_loop')                               # loop wait_loop
    a.b(0x4a)                                                # dec dx
    a.short(0x75, 'wait_loop')                               # jnz wait_loop
    a.label('wait_done')
    a.b(0xc3)                                                # ret

    # --- resident data ---
    a.label('old_name'); a.b(bytes(8))
    a.label('save_paths')                                    # save_wait: the save files of TURN1-4, FIGHT1-5 (16 bytes each)
    for slot in SAVE_SLOTS:
        a.b(f'C:\\SAVE\\{slot}.SAV'.encode().ljust(16, b'\0'))
    a.label('turn_pass'); a.b(0)                             # int 65h: 1 while the turn sound plays
    a.label('mine_req'); a.b(0)                              # MINEFIELD: 1 = place them in the next frame
    a.label('mine_live'); a.b(0, 0)                          # ... a bit for each mine not yet set off
    a.label('mine_todo'); a.b(0)                             # ... mines still to draw
    a.label('mine_busy'); a.b(0)                             # ... 1 while they are drawn
    a.label('mine_page'); a.b(0, 0)
    a.label('mine_es'); a.b(0, 0)
    a.label('mine_x'); a.b(bytes(2 * MINE_COUNT))
    a.label('mine_vis'); a.b(0)                              # D50: 1 while the mines show
    a.label('mine_t'); a.b(0, 0)                             # ... the tick they were drawn
    a.label('mine_mode'); a.b(0)                             # ... mine_rect: 0 keep the background, 1 put it back
    a.label('mine_bg'); a.b(bytes(MINE_W * MINE_H * MINE_COUNT))   # ... the background under each
    a.label('mine_z'); a.b(bytes(2 * MINE_COUNT))
    a.label('snd_id'); a.b(CHEAT_SOUND, 0)                   # the next sound of a fight's frame
    a.label('map_flags'); a.b(0)                             # SIRWALKSALOT, SIRPICKSALOT (on until typed again)
    a.label('key_show'); a.b(0)                              # IDROPPEDMYKEY: the screen's stage, 0 = none
    a.label('keys_shown'); a.b(0)                            # ... 1 = the lairs with keys glow
    for n, (bit, name) in enumerate(KEY_REGIONS):
        a.label(f'kxt_{n}'); a.b(name.encode() + bytes(1))
    a.label('kxt_dragon'); a.b(b'the Dragon' + bytes(1))
    a.label('kxt_temple'); a.b(b'the High Temple' + bytes(1))
    a.label('kxt_lair'); a.b(b'a glowing lair' + bytes(1))
    a.label('kxt_none'); a.b(b'nowhere' + bytes(1))
    a.label('heal_given'); a.b(0, 0)                         # healer: the donation made
    a.label('ds_have'); a.b(0)                               # dragon_scroll: 1 = the offer has been made
    a.label('ds_old'); a.b(bytes(4))                         # ... [8979h], [897Bh] as they were
    a.label('hawk_ok'); a.b(0)                               # hawk_guard: 1 = hawk_pos is a place outside the Valley
    a.label('hawk_pos'); a.b(bytes(4))
    a.label('slot_group'); a.b(bytes(SLOT_GROUP))            # D61: a colour slot's glow group
    for name in ('glow_cur', 'glow_base', 'glow_tgt', 'glow_cnt'):   # D61: 15 words each, in colour_sites' order
        a.label(name); a.b(b'\xff' * 2 * NEW_WORDS if name == 'glow_cur' else bytes(2 * NEW_WORDS))
    a.label('glow_old'); a.b(bytes(12))                      # D61: knights 1 and 2's words (6-11) before the glow
    a.label('glow_sites')                                    # D61: where MAIN keeps the glow targets (09A5)
    for slot in GLOW_GROUP_SLOTS:
        for site in GLOW_SITES[slot]:
            a.b(site & 0xff, site >> 8)
    a.label('map_hold'); a.b(0)                              # D26: 1 = a human's new turn, keys not yet let go
    a.label('turn_ax'); a.b(0, 0)                            # ... the game's ax
    a.label('sw_stamp'); a.b(bytes(4))                       # the file's time and date when the wait began
    a.label('sw_spin'); a.b(0)
    a.label('fight_name'); a.b((FIGHT_NAME + b'1').ljust(8, b'\0'))   # the digit is number_name's
    a.label('turn_name'); a.b((TURN_NAME + b'1').ljust(8, b'\0'))
    a.label('slot_next'); a.b(0, 0)                          # next turn and fight number - 1 (SAVEHOOK.SLT)
    a.label('name_ptr'); a.b(0, 0)
    a.label('reserve'); a.b(0, 0)
    a.label('save_ss'); a.b(0, 0)
    a.label('save_sp'); a.b(0, 0)
    a.label('child_path'); a.b(CHILD_PATH)
    a.label('cmd_path'); a.b(CMD_PATH)
    a.label('chk_path'); a.b(CHK_PATH)
    a.label('slot_path'); a.b(SLOT_PATH)
    a.label('amiga_path'); a.b(AMIGA_PATH)                   # D65
    a.label('amiga_on'); a.b(0)                              # 1 = the effects go to the SoundFont
    a.label('amiga_slot'); a.b(0)                            # the channel (0-3) of the last sound
    a.label('amiga_prog'); a.b(bytes(amiga_program(i) for i in range(180)))   # sound id -> Amiga program, 0 = none
    a.label('auto_name'); a.b(AUTO_NAME.ljust(8, b'\0'))
    a.label('none_name'); a.b(NONE_NAME.ljust(8, b'\0'))
    a.label('token'); a.b(bytes(4))
    a.label('file_token'); a.b(bytes(4))
    rules_data(a, rules_table)
    a.label('tail'); a.b(0x00, 0x0d)                         # empty command line
    a.label('fcb'); a.b(bytes(16))
    a.label('param_block')
    a.b(0, 0)                                                # environment: copy of the parent's
    a.word('tail'); a.label('tail_seg'); a.b(0, 0)
    a.word('fcb'); a.label('fcb1_seg'); a.b(0, 0)
    a.word('fcb'); a.label('fcb2_seg'); a.b(0, 0)
    a.label('resident_end')

    # --- installer (discarded when resident) ---
    a.label('install')
    a.b(0xb8, FIGHT_INT, 0x35, 0xcd, 0x21)                   # mov ax, 3566h / int 21h   es:bx = vector
    a.b(0x26, 0x81, 0x7f, 0xfe, SIGNATURE)                   # cmp word es:[bx-2], 'SV'
    a.short(0x75, 'inst_new')                                # jne inst_new
    a.near(0xe9, 'quit')                                     # jmp quit     already installed: run by hand again
    a.label('inst_new')
    # The vectors are taken over without checking them: DOSBox-X points int 66h at a BIOS IRET stub by default
    # (bios.cpp, "war2d"), so a non-zero vector does not mean another program uses it. Nothing else in this
    # setup uses 62h, 63h, 65h or 66h, and the patched MAIN.EXE must always reach these handlers.
    a.b(0xba); a.word('fight_handler')                       # mov dx, fight_handler
    a.b(0xb8, FIGHT_INT, 0x25, 0xcd, 0x21)                   # mov ax, 2566h / int 21h
    a.b(0xba); a.word('turn_handler')                        # mov dx, turn_handler
    a.b(0xb8, TURN_INT, 0x25, 0xcd, 0x21)                    # mov ax, 2565h / int 21h
    a.b(0xba); a.word('loot_handler')                        # mov dx, loot_handler
    a.b(0xb8, LOOT_INT, 0x25, 0xcd, 0x21)                    # mov ax, 2562h / int 21h
    a.b(0xba); a.word('rules_handler')                       # mov dx, rules_handler
    a.b(0xb8, RULES_INT, 0x25, 0xcd, 0x21)                   # mov ax, 2563h / int 21h
    a.b(0xba); a.word('key_handler')                         # mov dx, key_handler   D24
    a.b(0xb8, KEY_INT, 0x25, 0xcd, 0x21)                     # mov ax, 2564h / int 21h
    for seg in ('tail_seg', 'fcb1_seg', 'fcb2_seg'):
        a.b(0x8c, 0x0e); a.word(seg)                         # mov [seg], cs
    a.near(0xe8, 'amiga_check')                              # call amiga_check   (D65)
    # the child program (a failure leaves an older one, or no automatic saves)
    a.b(0xb4, 0x3c, 0x33, 0xc9, 0xba); a.word('child_path')   # mov ah, 3Ch / xor cx, cx / mov dx, child_path
    a.b(0xcd, 0x21); a.short(0x72, 'no_child')               # int 21h   create / jc
    a.b(0x8b, 0xd8, 0xb4, 0x40, 0xb9, len(CHILD_CODE), 0x00, 0xba); a.word('child_code')   # mov bx, ax / mov ah, 40h / mov cx, 5 / mov dx, child_code
    a.b(0xcd, 0x21, 0xb4, 0x3e, 0xcd, 0x21)                  # int 21h (write) / mov ah, 3Eh / int 21h (close)
    a.label('no_child')
    a.b(0x8e, 0x06, 0x2c, 0x00, 0xb4, 0x49, 0xcd, 0x21)      # mov es, [2Ch] / mov ah, 49h / int 21h   free env
    a.b(0x0e, 0x07)                                          # push cs / pop es
    a.label('resident_paras_1')
    a.b(0xbb, 0, 0, 0xb4, 0x4a, 0xcd, 0x21)                  # mov bx, paras / mov ah, 4Ah / int 21h   shrink
    a.b(0xb4, 0x48, 0xbb, RESERVE_PARAS & 0xff, RESERVE_PARAS >> 8, 0xcd, 0x21)   # mov ah,48h / mov bx,n / int 21h
    a.short(0x72, 'no_reserve')                              # jc no_reserve
    a.b(0xa3); a.word('reserve')                             # mov [reserve], ax
    a.label('no_reserve')
    for mode in (AUTO_ONLY, NO_SAVES):                       # save check: a fresh token in memory and the file
        a.b(0x80, 0x3e); a.word('rules_table', G_SAVE_MODE); a.b(mode)   # cmp byte [save_mode], mode
        a.short(0x74, 'inst_token')                          # je inst_token
    a.short(0xeb, 'inst_msg')                                # jmp inst_msg
    a.label('inst_token')
    a.near(0xe8, 'new_token')                                # call new_token
    a.near(0xe8, 'write_token')                              # call write_token
    a.label('inst_msg')
    a.b(0xba); a.word('msg_ok')                              # mov dx, msg_ok
    a.b(0xb4, 0x09, 0xcd, 0x21)                              # mov ah, 9 / int 21h
    a.label('resident_paras_2')
    a.b(0xba, 0, 0, 0xb8, 0x00, 0x31, 0xcd, 0x21)            # mov dx, paras / mov ax, 3100h / int 21h   stay resident
    a.label('quit')
    a.b(0xb8, 0x00, 0x4c, 0xcd, 0x21)                        # mov ax, 4C00h / int 21h
    a.label('msg_ok'); a.b(b'SAVEHOOK: save state before every fight and turn is on.\r\n$')
    a.label('child_code'); a.b(CHILD_CODE)

    code = bytearray(a.build())
    paras = (a.labels['resident_end'] + 15) // 16           # offsets count from the PSP, so this includes it
    for name in ('resident_paras_1', 'resident_paras_2'):
        struct.pack_into('<H', code, a.labels[name] - 0x100 + 1, paras)
    return bytes(code)

if __name__ == '__main__':
    com = make_savehook()
    open(sys.argv[1], 'wb').write(com)
    print(f'{len(com)} bytes -> {sys.argv[1]}')
