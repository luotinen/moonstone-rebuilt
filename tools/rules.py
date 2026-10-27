"""Game rules from an INI file (Moonstone Rebuilt, D10; user request): starting values per knight, a death mode per
knight, the computer knights' extras and global rules.
Usage: python -I tools/rules.py [game folder]   applies custom_rules.ini (Custom_rules_on.bat).
Custom_rules_off.bat puts the fixed MAIN.EXE back and removes CUSTOM_RULES.FLG; Custom_rules_reset.bat copies
custom_rules-default.ini (the normal game's values) to custom_rules.ini.

How it works. Values that the game keeps as a constant in its code (prices of the rules, caps, tables) are byte patches
on top of the fixed MAIN.EXE (_fixes/fixed/MAIN.EXE). Things that need new code use int 61h, which SAVEHOOK.COM handles
(make_savehook.py, rules_handler); it finds the job by the return address and reads its settings from a table that
this tool writes into SAVEHOOK.COM. The int 61h sites are in HOOKS below. Without CUSTOM_RULES.FLG the game is the
normal fixed one: SAVEHOOK.COM always carries the rules code, but the normal MAIN.EXE never calls it.

The knights. Record +20h is the knight: 0-3 for a human player's knight (the order on the selection screen; it also
gives the start corner and home village), 4 for a computer knight. The INI sections [Knight1]-[Knight4] are 0-3 and
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

# Settings table in SAVEHOOK.COM: one SECTION_SIZE block per INI section in SECTIONS order, then the globals.
# Block: +0 STR, +1 CON, +2 END, +3 lives, +4 gold (word), +6 daggers (= knight record +2Eh..+34h, copied as is),
# +7 death mode, +8 XP, +0Ah weapon, +0Ch armour, +0Eh HP bonus (words), +10h the 24-byte item table.
SECTION_SIZE = 0x28
G_ARMOUR_HP = len(SECTIONS) * SECTION_SIZE    # 4 words: max HP bonus of padded, chain, plate, battle
G_SWORD = G_ARMOUR_HP + 8                     # word: damage bonus of the long sword (the others are in MAIN.EXE)
G_REST, G_VILLAGE, G_MAX_LIVES = G_SWORD + 2, G_SWORD + 3, G_SWORD + 4    # bytes
TABLE_SIZE = G_SWORD + 6

# int 61h sites: (address, original bytes, kind). The kind names the handler in make_savehook.py.
# The lives kinds keep the instruction's 8-bit operand after the int (cd 61 nn 90): the handler reads it
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
]

def hook_bytes(where, old, kind):
    """The replacement for a hook site and the return address that the handler sees."""
    old = bytes.fromhex(old)
    if kind == 'init':                                  # mov si,[di+44h] / int 61h / jmp 1FF7
        new = old[:3] + b'\xcd\x61\xeb\x06'
        return new.ljust(len(old), b'\x90'), where + 5
    if kind == 'village':                               # int 61h / jmp 1138
        return b'\xcd\x61\xeb\x06'.ljust(len(old), b'\x90'), where + 2
    if kind.startswith('lives'):
        return b'\xcd\x61' + old[3:4] + b'\x90', where + 2    # handler reads the operand at the return address
    return b'\xcd\x61'.ljust(len(old), b'\x90'), where + 2

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
        raise RulesError(f'[{sec}] {key} = {raw}: not a valid value')
    if lo is not None and not lo <= val <= hi:
        raise RulesError(f'[{sec}] {key} = {raw}: must be {lo}-{hi}')
    return val

def _choice(table):
    def conv(raw):
        return table[raw.lower()]
    return conv

def _onoff(raw):
    return {'on': 1, 'off': 0, 'yes': 1, 'no': 0, '1': 1, '0': 0}[raw.lower()]

def read_ini(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    cp.optionxform = str.lower
    if not cp.read(path, encoding='utf-8'):
        raise RulesError(f'{path} not found')
    r = {'knights': []}
    for sec in SECTIONS:
        if not cp.has_section(sec):
            raise RulesError(f'section [{sec}] is missing')
        k = {}
        for key in ('strength', 'constitution', 'endurance'):
            k[key] = _get(cp, sec, key, int, 1, 99)
        k['lives'] = _get(cp, sec, 'lives', int, 1, 99)
        k['gold'] = _get(cp, sec, 'gold', int, 0, 32767)
        k['experience'] = _get(cp, sec, 'experience', int, 0, 32767)
        k['daggers'] = _get(cp, sec, 'daggers', int, 0, 99)
        k['hp_bonus'] = _get(cp, sec, 'hp_bonus', int, -1000, 1000)
        k['weapon'] = _get(cp, sec, 'weapon', _choice(WEAPONS))
        k['armour'] = _get(cp, sec, 'armour', _choice(ARMOURS))
        for name, _ in ITEMS:
            k[name] = _get(cp, sec, name, int, 0, 99)
        k['keys'] = _get(cp, sec, 'keys', int, 0, 4)
        k['moonstones'] = _get(cp, sec, 'moonstones', int, 0, 4)
        k['mode'] = _get(cp, sec, 'mode', _choice(MODES))
        r['knights'].append(k)
    b = 'Black'
    r['ai_xp_per_moon_phase'] = _get(cp, b, 'xp_per_moon_phase', int, -128, 127)
    r['ai_math_per_moon_phase'] = _get(cp, b, 'math_visit_per_moon_phase', _onoff)
    r['ai_duel_win_xp'] = _get(cp, b, 'duel_win_xp', int, -128, 127)
    g = 'Rules'
    r['ratmen_disease'] = _get(cp, g, 'ratmen_disease', _onoff)
    r['hawk_curse'] = _get(cp, g, 'hawk_curse_chance', float, 0, 100)
    r['protection_curse'] = _get(cp, g, 'protection_curse_chance', float, 0, 100)
    r['max_gold'] = _get(cp, g, 'max_gold', int, 0, 32767)
    r['max_lives'] = _get(cp, g, 'max_lives', int, 1, 99)
    r['village_heal'] = _get(cp, g, 'village_heal', _choice(VILLAGE))
    r['village_any'] = _get(cp, g, 'village_heal_where', _choice({'home': 0, 'any': 1}))
    r['rest_heal'] = _get(cp, g, 'rest_heal', _choice({'none': 0, 'full': 1}))
    r['moon_days'] = _get(cp, g, 'moon_days', int, 1, 100)
    r['xp_per_stat'] = [_get(cp, g, f'xp_per_stat_{n}_player{"s" if n > 1 else ""}', int, 0, 32767)
                        for n in (1, 2, 3, 4)]
    w = 'Weapons'
    r['weapon_damage'] = [_get(cp, w, name, int, -100, 100) for name in WEAPONS]
    a = 'Armour'
    r['armour_hp'] = [_get(cp, a, f'{name}_hp', int, -100, 100) for name in ARMOURS]
    return r

# --- the SAVEHOOK.COM table -------------------------------------------------------------------------------------------
DEFAULT_KNIGHT = dict(strength=1, constitution=1, endurance=1, lives=5, gold=10, experience=0, daggers=10, hp_bonus=0,
                      weapon=0x16, armour=0x1b, keys=0, moonstones=0, mode=0,
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
    return bytes(t)

# --- MAIN.EXE patches -------------------------------------------------------------------------------------------------
def roll_threshold(percent):
    """The game's 0-100 roll (1000:BF82: 7 random bits, 100-127 minus 27) is compared with 'roll <= limit'.
    Returns the limit whose chance is nearest to percent; -1 (never) for 0."""
    if percent <= 0:
        return -1
    rolls = [x - 27 if x >= 100 else x for x in range(128)]
    return min(range(101), key=lambda t: abs(sum(v <= t for v in rolls) / 1.28 - percent))

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
    if r['village_any']:                                 # villages 15h-18h react only to their own knight (+20h)
        for site in (0x073b, 0x0746, 0x0751, 0x075c):    # jne (skip the place) -> nop nop
            out.append((site, bytes(img[site:site + 2]), b'\x90\x90'))
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
    if r['ratmen_disease']:                              # undo K17
        for where, old, new in PATCHES['K17']['bytes']:
            out.append((image_offset(where), new, old))
    return out

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
    os.makedirs(os.path.join(game, '_fixes', 'rules'), exist_ok=True)
    for name, data in ((os.path.join('_fixes', 'rules', 'MAIN.EXE'), exe), ('SAVEHOOK.COM', hook),
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
