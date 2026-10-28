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
2. renames MAIN's memory block to the next of FIGHT1-FIGHT5 or TURN1-TURN4 and runs SAVEHOOK.COM again as a child, so
   DOSBox-X re-reads the name (the child sees the handlers are installed and exits at once),
3. waits WAIT_TICKS BIOS ticks (about 1.1 s), during which DOSBox-X's once-a-second autosave check saves the state.
   Emulation stops while DOSBox-X writes a save, so the wait lasts longer in real time and often covers a second
   check. The game cannot see the pause (its clocks, the CMOS clock included, follow emulated time), so the second
   save goes into the same slot (one slot per name),
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

MAIN.EXE may use all free memory, so SAVEHOOK keeps a small block of its own and frees it for the child.
Usage: python -I tools/make_savehook.py <output SAVEHOOK.COM>   (the normal game; rules.py builds it with rules)"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import (HOOKS, FATE_HOOKS, FATE_STREAMS, SECTIONS, SECTION_SIZE, MODES, VILLAGE, SAVE_MODES, SPAWNS,
                   G_ARMOUR_HP, G_SWORD, G_REST, G_VILLAGE, G_MAX_LIVES, G_RING, G_COLOURS, G_HOMES, G_VILLAGE_ANY,
                   G_SAVE_MODE, G_FATE, G_SELLING, G_MAX_GOLD, G_SELL, G_HOARD, HOARD_MODES, MAX_HP, hook_bytes,
                   G_PRACTICE, G_PRACTICE_FLAGS, G_TARGET_MARGIN, COOP_KNIGHT_HITS, TEAM_KNIGHT_HITS,
                   COOP_DAGGER_HITS, TARGET_FIRST, G_HIT_REST, G_EXPLOIT_FIXES, KEEP_DRAGON_TARGET,
                   NO_EXTRA_TURN, POTION_LIFE,
                   table as rules_default_table)

FIGHT_INT, TURN_INT, LOOT_INT, RULES_INT = 0x66, 0x65, 0x62, 0x63   # MAIN.EXE uses none of these
SHARPNESS = 0x19                         # weapon number of the Sword of Sharpness
FIGHT_NAME, FIGHT_SLOTS = b'FIGHT', 5     # program names FIGHT1-FIGHT5 and TURN1-TURN4, one autosave slot each
TURN_NAME, TURN_SLOTS = b'TURN', 4       # (moonstone-dosbox-x.conf: FIGHT1:96 ... FIGHT5:100, TURN1:91 ... TURN4:94)
MODE_REINCARNATION, MODE_RESPAWN, MODE_INVULNERABLE = MODES['reincarnation'], MODES['respawn'], MODES['invulnerable']
VILLAGE_FULL = VILLAGE['full']
COMPUTER = 4                             # knight record +20h: control type 4 = computer
AUTO_ONLY, MANUAL_ONLY, NO_SAVES = SAVE_MODES['autosave_only'], SAVE_MODES['manual_only'], SAVE_MODES['none']
CHK_PATH = b'C:\\SAVEHOOK.CHK\0'        # the save check's token file (save states do not restore files)
SLOT_PATH = b'C:\\SAVEHOOK.SLT\0'       # the next autosave number of each kind (a file, so loading a state keeps it)
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
                  # K23: the healing potion's life
                  (0xccb8, 'potion_life')]
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
                 (0x0b, 12), (0x20, 10), (0x22, 11)]
KEY_0_CHOICE = 12                                    # the 0 key: the tenth practice entry (custom rules can set it)
# key 1 ratmen x10, 2 ratmen x14, 3 wasteland troggs x10, 4 axe troggs x10, 5 war beasts x9, 6 spear troggs x5,
# 7 Baloks x3, 8 mudmen x5, 9 trolls x6
PRACTICE_LAIRS = [0, 3, 9, 1, 21, 19, 7, 12, 17]
SET_UPS = {10: 0x2444, 11: 0x2749}                   # as 1000:0D15 and 0FE7
LAIR_RECORDS, LAIR_SIZE = 0x0002, 0x12               # lair records built at 1000:1E95
# D15 co-op: the knights after the first: (record, control, colour slot +20h, x); all face left like the first
COOP_KNIGHTS = [(0x6d00, 1, 2, 220), (0x6d62, 5, 1, 280), (0x6dc4, 6, 3, 190)]   # controls as D12's
KNIGHTS = (0x6c9e, 0x6d00, 0x6d62, 0x6dc4)
ADD_STATE = 10                                       # practice_init states from here: adding the co-op knights
TARGET_KEEP = 20                                     # a monster keeps its knight unless another is this much nearer
MONSTER_SLOTS, SLOT_SIZE, MONSTER_COUNT, DRAGON_RECORD = 0x6f08, 0x62, 20, 0x6e26   # fight objects (1000:2A1E), dragon
DRAGON_HOARD, DRAGON_GOLD = 0x6ee8, 0x6e26 + 0x32   # K18: the dragon's 24-byte item table and its gold
# D13: the knights drawn in the new colours: (record, its first knight-colour pixel, the game's fight palette words
# for +20h = 1 and 3, which custom rules recolour); their pixels move up by 26: 6-8 -> 32-34, 9-11 -> 35-37
RECOLOUR = [(0x6d62, 6, (0x4838, 0x483d, 0x4842)), (0x6dc4, 9, (0x484e, 0x4853, 0x4858))]
RECOLOUR_SHIFT, NEW_ENTRIES = 26, 32
# D15: in a lair fight bank 8949h holds the monsters, so every co-op knight is drawn from KN*.OB (6-8): knight 2
# moves to 38-40 (+32, the words of +20h = 2), 3 to 32-34 (+26), 4 to 35-37 (+29)
COOP_RECOLOUR = [(0x6d00, 6, 32), (0x6d62, 6, 26), (0x6dc4, 6, 29)]
PRACTICE_RECOLOUR = [(rec, first, RECOLOUR_SHIFT) for rec, first, _ in RECOLOUR]
GREEN_SITES = (0x4864, 0x4869, 0x486e)               # fight palette words of +20h = 2, for entries 38-40
BLITTER, BLIT_COUNT = 0x5dd4, 0x637b          # the blitter, and its converter's output count (a word in MAIN's code)
TEAM1, TEAM2 = (0x6c9e, 0x6d62), (0x6d00, 0x6dc4)   # D12: player 1 + joystick A, player 2 + joystick B
JOY_A_CONTROL, JOY_B_CONTROL = 5, 6                  # D12: knight +9 for the two joysticks (4 is the computer)
JOY_PORT_LIMIT = 0x2000                              # no joystick: its port bits never fall within this many reads
CHILD_PATH = b'C:\\SAVEHOOK.COM\0'      # the game folder is drive C: in moonstone-dosbox-x.conf
WAIT_TICKS = 20                          # 20 / 18.2 Hz = 1.1 s; the autosave check runs about every 1.0 s
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
        assert name not in self.labels, f'label {name} defined twice'
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
                assert -128 <= rel < 128, label
                self.code[pos] = rel & 0xff
            else:
                struct.pack_into('<h', self.code, pos, target - (self.org + pos + 2))
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
    a.b(0x50, 0x51, 0x56, 0x57, 0x87, 0xf7)                  # push ax cx si di / xchg si, di
    a.near(0xe8, 'section')                                  # call section
    a.near(0xe8, 'start_knight')                             # call start_knight
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
    a.b(0x01, 0x46, 0xfe, 0x58)                              # add [bp-2], ax (the saved bx) / pop ax
    a.b(0x81, 0x7e, 0xfe, MAX_HP & 0xff, MAX_HP >> 8)        # cmp word [bp-2], 999
    a.short(0x7e, 'max_hp_done')                             # jle max_hp_done
    a.b(0xc7, 0x46, 0xfe, MAX_HP & 0xff, MAX_HP >> 8)        # mov word [bp-2], 999
    a.label('max_hp_done')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # damage (1000:2D86): replaces mov cl,[si+2Eh] / add ax,cx; si = attacker, ax = base damage
    a.label('rules_damage')
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

    # rest (1000:A590): the E key ends the turn; replaces mov ax,[0CCACh]
    a.label('rules_rest')
    a.b(0xa1, 0xac, 0xcc)                                    # mov ax, [0CCACh]
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_REST); a.b(0x00)   # cmp byte cs:[rest_heal], 0
    a.short(0x74, 'rest_end')                                # je rest_end
    a.b(0x8b, 0x1e, 0xe8, 0x77, 0x50)                        # mov bx, [77E8h] / push ax
    a.b(0x8b, 0x47, 0x3c, 0x89, 0x47, 0x38, 0x58)            # mov ax, [bx+3Ch] / mov [bx+38h], ax / pop ax
    a.label('rest_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # colour (1000:08D6, A419, A3CF): replaces mov ax,[si+20h] / mov ax,[di+20h] where the map icon is chosen:
    # ax = the colour picked for that knight (the icon sprite number is ax + an offset)
    a.label('rules_colour_di')
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
    a.near(0xe8, 'checkpoint')                               # call checkpoint
    a.b(0x2e, 0x80, 0x3e); a.word('rules_table', G_FATE); a.b(0x00)   # cmp byte cs:[fate], 0
    a.short(0x74, 'fate_call')                               # je fate_call
    a.b(0x2e, 0x8b, 0x87); a.word('fate_state')              # mov ax, cs:[bx+fate_state]
    a.b(0x0b, 0xc0)                                          # or ax, ax
    a.short(0x75, 'fate_next')                               # jnz fate_next
    a.b(0xa1, RANDOM_STATE & 0xff, RANDOM_STATE >> 8)        # mov ax, [0E22Fh]        first use: the game's state
    a.label('fate_next')
    a.b(0xb9, 0x55, 0x62, 0xf7, 0xe1)                        # mov cx, 25173 / mul cx
    a.b(0x05, 0x19, 0x36)                                    # add ax, 13849
    a.b(0x2e, 0x89, 0x87); a.word('fate_state')              # mov cs:[bx+fate_state], ax
    a.b(0x0b, 0xc0)                                          # or ax, ax
    a.short(0x75, 'fate_seed')                               # jnz fate_seed
    a.b(0x40)                                                # inc ax                  never 0 (the LFSR stays 0)
    a.label('fate_seed')
    a.b(0xa3, RANDOM_STATE & 0xff, RANDOM_STATE >> 8)        # mov [0E22Fh], ax
    a.label('fate_call')
    a.b(0x5e, 0x5a, 0x59, 0x58, 0x5b, 0x5d)                  # pop si dx cx ax / pop bx / pop bp
    a.b(0x50, 0x55, 0x8b, 0xec, 0x50)                        # push ax (room) / push bp / mov bp, sp / push ax
    a.b(0x8b, 0x46, 0x04, 0x40)                              # mov ax, [bp+4] / inc ax          site + 3
    a.b(0x87, 0x46, 0x08, 0x87, 0x46, 0x06)                  # xchg ax, [bp+8] / xchg ax, [bp+6]   flags, CS up
    a.b(0x89, 0x46, 0x04)                                    # mov [bp+4], ax
    a.b(0x2e, 0xa1); a.word('fate_target')                   # mov ax, cs:[fate_target]
    a.b(0x89, 0x46, 0x02)                                    # mov [bp+2], ax
    a.b(0x58, 0x5d, 0xcf)                                    # pop ax / pop bp / iret   -> the routine

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
    for add in (0, 2):                                       # a missing or short file counts as a match
        a.b(0xa1); a.word('token', add); a.b(0xa3); a.word('file_token', add)   # mov ax, [token] / mov [file_token], ax
    a.b(0xb8, 0x00, 0x3d, 0xba); a.word('chk_path')          # mov ax, 3D00h / mov dx, chk_path
    a.b(0xcd, 0x21)                                          # int 21h     open
    a.short(0x72, 'chk_new')                                 # jc chk_new
    a.b(0x8b, 0xd8, 0xb4, 0x3f, 0xb9, 0x04, 0x00, 0xba); a.word('file_token')   # mov bx, ax / mov ah, 3Fh / mov cx, 4 / mov dx, file_token
    a.b(0xcd, 0x21, 0xb4, 0x3e, 0xcd, 0x21)                  # int 21h (read) / mov ah, 3Eh / int 21h (close)
    for add in (0, 2):
        a.b(0xa1); a.word('file_token', add); a.b(0x3b, 0x06); a.word('token', add)   # mov ax, [file_token] / cmp ax, [token]
        a.short(0x75, 'chk_refuse')                          # jne chk_refuse
    a.label('chk_new')
    a.near(0xe8, 'new_token')                                # call new_token
    a.near(0xe8, 'write_token')                              # call write_token
    a.b(0x07, 0x1f, 0x5a, 0x59, 0x5b, 0x58, 0xc3)            # pop es ds dx cx bx ax / ret
    a.label('chk_refuse')
    a.near(0xe9, 'refuse')                                   # jmp refuse

    a.label('new_token')                                     # DS = CS: token = BIOS ticks, counter + 1
    a.b(0x06, 0xb8, 0x40, 0x00, 0x8e, 0xc0, 0x26, 0xa1, 0x6c, 0x00, 0x07)   # push es / mov ax, 40h / mov es, ax / mov ax, es:[6Ch] / pop es
    a.b(0xa3); a.word('token')                               # mov [token], ax
    a.b(0xff, 0x06); a.word('token', 2)                      # inc word [token+2]
    a.b(0xc3)                                                # ret

    a.label('write_token')                                   # DS = CS: SAVEHOOK.CHK = token (clobbers ax bx cx dx)
    a.b(0xb4, 0x3c, 0x33, 0xc9, 0xba); a.word('chk_path')    # mov ah, 3Ch / xor cx, cx / mov dx, chk_path
    a.b(0xcd, 0x21)                                          # int 21h     create
    a.short(0x72, 'write_end')                               # jc write_end
    a.b(0x8b, 0xd8, 0xb4, 0x40, 0xb9, 0x04, 0x00, 0xba); a.word('token')   # mov bx, ax / mov ah, 40h / mov cx, 4 / mov dx, token
    a.b(0xcd, 0x21, 0xb4, 0x3e, 0xcd, 0x21)                  # int 21h (write) / mov ah, 3Eh / int 21h (close)
    a.label('write_end')
    a.b(0xc3)                                                # ret

    a.label('accept')                                        # DS = CS, after an automatic save's wait: its token
    a.b(0x80, 0x3e); a.word('rules_table', G_SAVE_MODE); a.b(AUTO_ONLY)   # cmp byte [save_mode], 1
    a.short(0x75, 'accept_end')                              # jne accept_end
    a.near(0xe9, 'write_token')                              # jmp write_token
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
    a.short(0x75, 'sell_no')                                 # jne sell_no
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
    a.b(0x2e, 0xa1); a.word('rules_table', G_MAX_GOLD)       # mov ax, cs:[max_gold]
    a.b(0x39, 0x44, 0x32)                                    # cmp [si+32h], ax
    a.short(0x7e, 'sell_yes')                                # jle sell_yes
    a.b(0x89, 0x44, 0x32)                                    # mov [si+32h], ax
    a.label('sell_yes')
    a.b(0x5e, 0x58, 0x3b, 0xe4)                              # pop si / pop ax / cmp sp, sp    ZF = 1
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

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
    # practice_mode: cs:[multi] = 3 or 4 when that many players were chosen and their joysticks answer, else 0
    a.label('practice_mode')
    a.b(0x50, 0x53, 0x51, 0x52)                              # push ax bx cx dx
    a.b(0x2e, 0xc6, 0x06); a.word('multi'); a.b(0x00)        # mov byte cs:[multi], 0
    a.b(0x2e, 0xc6, 0x06); a.word('add_state'); a.b(0x00)    # mov byte cs:[add_state], 0
    a.b(0x8b, 0x1e, CHOSEN_PLAYERS & 0xff, CHOSEN_PLAYERS >> 8)   # mov bx, [0940h]
    a.b(0x83, 0xfb, 0x03)                                    # cmp bx, 3
    a.short(0x72, 'pm_end')                                  # jb pm_end
    a.b(0xb4, 0x01)                                          # mov ah, 1         joystick A, x axis
    a.near(0xe8, 'joy_present')                              # call joy_present
    a.short(0x72, 'pm_end')                                  # jc pm_end
    a.b(0x83, 0xfb, 0x04)                                    # cmp bx, 4
    a.short(0x72, 'pm_three')                                # jb pm_three
    a.b(0xb4, 0x04)                                          # mov ah, 4         joystick B, x axis
    a.near(0xe8, 'joy_present')                              # call joy_present
    a.short(0x72, 'pm_end')                                  # jc pm_end         (two players, as before)
    a.b(0x2e, 0xc6, 0x06); a.word('multi'); a.b(0x04)        # mov byte cs:[multi], 4
    a.short(0xeb, 'pm_end')                                  # jmp pm_end
    a.label('pm_three')
    a.b(0x2e, 0xc6, 0x06); a.word('multi'); a.b(0x03)        # mov byte cs:[multi], 3
    a.label('pm_end')
    a.b(0x5a, 0x59, 0x5b, 0x58, 0xc3)                        # pop dx cx bx ax / ret

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
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x74, 'pa_done')                                 # je pa_done
    a.b(0x2e, 0xa0); a.word('add_state')                     # mov al, cs:[add_state]
    a.b(0x2e, 0xfe, 0x06); a.word('add_state')               # inc byte cs:[add_state]
    a.b(0x3c, 0x00); a.short(0x74, 'pa_p3')                  # cmp al, 0 / je pa_p3
    a.b(0x3c, 0x01); a.short(0x74, 'pa_p3_run')              # cmp al, 1 / je pa_p3_run
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x04)        # cmp byte cs:[multi], 4
    a.short(0x75, 'pa_done')                                 # jne pa_done
    a.b(0x3c, 0x02); a.short(0x74, 'pa_p4')                  # cmp al, 2 / je pa_p4
    a.b(0x3c, 0x03); a.short(0x74, 'pa_p4_run')              # cmp al, 3 / je pa_p4_run
    a.label('pa_done')
    a.b(0x2e, 0xc6, 0x06); a.word('add_state'); a.b(0x00)    # mov byte cs:[add_state], 0
    a.b(0xc7, 0x06, 0x1c, 0x09, 0x06, 0x00)                  # mov word [91Ch], 6     (replaced instruction)
    a.near(0xe9, 'rules_done')                               # jmp rules_done
    for knight, control, colour, x, facing, bank in (('p3', JOY_A_CONTROL, 1, 0xfa, 3, 0x8933),
                                                     ('p4', JOY_B_CONTROL, 3, 0x1e, 1, 0x8949)):
        rec = TEAM1[1] if knight == 'p3' else TEAM2[1]
        a.label('pa_' + knight)                              # as InitPractice's knights (1000:296E, 200F)
        a.b(0xbf, rec & 0xff, rec >> 8)                      # mov di, record
        a.b(0xc6, 0x45, 0x35, 0x06, 0xc6, 0x45, 0x09, control)   # mov byte [di+35h], 6 / mov byte [di+9], control
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
    a.b(0x8b, 0x5d, 0x16)                                    # mov bx, [di+16h]   the object
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x75, 'draw_coop')                               # jne draw_coop
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x74, 'draw_call')                               # je draw_call
    a.b(0x2e, 0x80, 0x3e); a.word('teams'); a.b(0x00)        # cmp byte cs:[teams], 0
    a.short(0x75, 'draw_call')                               # jne draw_call     teams wear their team's colour
    for table, name in ((PRACTICE_RECOLOUR, 'p'), (COOP_RECOLOUR, 'c')):
        if name == 'c':
            a.short(0xeb, 'draw_call')                       # jmp draw_call
            a.label('draw_coop')
        for rec, first, shift in table:
            a.b(0x81, 0xfb, rec & 0xff, rec >> 8)            # cmp bx, record
            a.short(0x75, f'draw_{name}{rec:x}')             # jne next
            a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(first)    # mov byte cs:[recolour], first pixel value
            a.b(0x2e, 0xc6, 0x06); a.word('rc_shift'); a.b(shift)    # mov byte cs:[rc_shift], shift
            a.label(f'draw_{name}{rec:x}')
    a.label('draw_call')
    a.b(0x50, 0x8b, 0x46, 0x02, 0x40)                        # push ax / mov ax, [bp+2] / inc ax   site + 3
    a.b(0x2e, 0xa3); a.word('call_ret')                      # mov cs:[call_ret], ax
    a.b(0x58)                                                # pop ax
    a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(BLITTER & 0xff, BLITTER >> 8)   # mov word cs:[call_target], 5DD4h
    a.near(0xe9, 'call_game')                                # jmp call_game

    # recolour (1000:5EDF; replaces pop di / pop si / pop ds, the frame now converted into es:0): moves this
    # frame's knight colours up, then does the three pops
    a.label('rules_recolour')
    a.b(0x2e, 0x8a, 0x1e); a.word('recolour')                # mov bl, cs:[recolour]
    a.b(0x0a, 0xdb)                                          # or bl, bl
    a.short(0x74, 'rc_pop')                                  # jz rc_pop
    a.b(0x2e, 0x8a, 0x3e); a.word('rc_shift')                # mov bh, cs:[rc_shift]
    a.b(0x2e, 0xc6, 0x06); a.word('recolour'); a.b(0x00)     # mov byte cs:[recolour], 0
    a.b(0x50, 0x51, 0x57, 0x1e)                              # push ax cx di ds
    a.b(0x8e, 0x5e, 0x04)                                    # mov ds, [bp+4]     MAIN's code segment
    a.b(0x8b, 0x0e, BLIT_COUNT & 0xff, BLIT_COUNT >> 8)      # mov cx, [637Bh]    bytes the converter wrote
    a.b(0x33, 0xff)                                          # xor di, di
    a.b(0xe3); a.b(0x00); rc_jcxz = len(a.code) - 1          # jcxz rc_end (patched below)
    a.label('rc_loop')
    a.b(0x26, 0x8a, 0x05)                                    # mov al, es:[di]
    a.b(0x2a, 0xc3)                                          # sub al, bl
    a.b(0x3c, 0x02)                                          # cmp al, 2
    a.short(0x77, 'rc_next')                                 # ja rc_next         not one of the three
    a.b(0x26, 0x00, 0x3d)                                    # add es:[di], bh   the shift
    a.label('rc_next')
    a.b(0x47)                                                # inc di
    a.short(0xe2, 'rc_loop')                                 # loop rc_loop
    a.label('rc_end')
    a.code[rc_jcxz] = (a.labels['rc_end'] - (a.org + rc_jcxz + 1)) & 0xff
    a.b(0x1f, 0x5f, 0x59, 0x58)                              # pop ds di cx ax
    a.label('rc_pop')
    a.b(0x8b, 0x7e, 0x08, 0x8b, 0x76, 0x0a, 0x8e, 0x5e, 0x0c)   # mov di, [bp+8] / mov si, [bp+10] / mov ds, [bp+12]
    a.b(0x5b, 0x5d, 0x50, 0x55, 0x8b, 0xec)                  # pop bx / pop bp / push ax / push bp / mov bp, sp
    for src, dst in ((8, 14), (6, 12), (4, 10)):             # the frame up over the three popped words
        a.b(0x8b, 0x46, src, 0x89, 0x46, dst)                # mov ax, [bp+src] / mov [bp+dst], ax
    a.b(0x5d, 0x58, 0x83, 0xc4, 0x06, 0xcf)                  # pop bp / pop ax / add sp, 6 / iret

    # new_entries: write DAC entries 32-37 (the index is already there) at cl/16 of their colours; ds = MAIN's code
    a.label('new_entries')
    a.b(0x50, 0x53, 0x52, 0x56)                              # push ax bx dx si
    a.b(0xba, 0xc9, 0x03)                                    # mov dx, 3C9h
    a.b(0xbe); a.word('colour_sites')                        # mov si, colour_sites
    a.label('ne_word')
    a.b(0x2e, 0x8b, 0x1c, 0x8b, 0x1f)                        # mov bx, cs:[si] / mov bx, [bx]   the word 0RGB
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
    a.short(0x75, 'ne_word')                                 # jnz ne_word
    a.b(0x2e, 0xc6, 0x06); a.word('words_left'); a.b(0x09)   # mov byte cs:[words_left], 9
    a.b(0x5e, 0x5a, 0x5b, 0x58, 0xc3)                        # pop si dx bx ax / ret

    # dac_write (1000:5B40; replaces mov dx,3C8h of the palette write 5B3E): writes the 32 entries from ds:si as the
    # game does, then 32-37, and returns to its ret (5B4E)
    a.label('rules_dac_write')
    a.b(0xba, 0xc8, 0x03, 0x32, 0xc0, 0xee, 0x42)            # mov dx, 3C8h / xor al, al / out dx, al / inc dx
    a.b(0xb9, 0x60, 0x00)                                    # mov cx, 60h
    a.label('dw_loop')
    a.b(0xac, 0xee)                                          # lodsb / out dx, al
    a.short(0xe2, 'dw_loop')                                 # loop dw_loop
    a.near(0xe8, 'colours_active')                           # call colours_active
    a.short(0x74, 'dw_ret')                                  # jz dw_ret
    a.b(0x2e, 0xc6, 0x06); a.word('level'); a.b(0x10)        # mov byte cs:[level], 16
    a.near(0xe8, 'dac_new')                                  # call dac_new
    a.label('dw_ret')
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
        a.near(0xe8, 'colours_active')                       # call colours_active
        a.short(0x74, name + '_bp')                          # jz bp
        a.b(0x50, 0x8b, 0x46, 0x08)                          # push ax / mov ax, [bp+8]   the pushed cx
        if fade_in:
            a.b(0xf7, 0xd8, 0x05, 0x11, 0x00)                # neg ax / add ax, 17
        else:
            a.b(0x48)                                        # dec ax
        a.b(0x2e, 0xa2); a.word('level')                     # mov cs:[level], al
        a.b(0x58)                                            # pop ax
        a.near(0xe8, 'dac_new')                              # call dac_new
        a.label(name + '_bp')
        a.b(0x81, 0x46, 0x00, 0xc0, 0x00)                    # add word [bp], 0C0h    (the game's bp, replaced)
        a.near(0xe9, 'rules_done')                           # jmp rules_done

    # menu_keys (D14, 1000:129B; replaces mov [77E2h],bx, the first menu's input): anywhere in the first menu Space
    # starts the practice in teams (with 1-2 players the normal practice: the Black Knight, or knight against knight)
    # and the keys of PRACTICE_KEYS a practice against that fight (0: the Black Knight); Enter (fire) clears both
    # choices. The key states are MAIN's table in its code segment
    a.label('rules_menu_keys')
    a.b(0x50, 0x56, 0x06)                                    # push ax si es
    a.b(0x8e, 0x46, 0x04)                                    # mov es, [bp+4]    MAIN's code segment
    a.b(0x8b, 0x5e, 0xfe)                                    # mov bx, [bp-2]    the input bits
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
    a.b(0x2e, 0x80, 0x3e); a.word('init_state'); a.b(0x00)   # cmp byte cs:[init_state], 0
    a.short(0x75, 'pi_kept')                                 # jne pi_kept        (the second call of a lair)
    a.b(0x51, 0x57, 0x06, 0x0e, 0x07)                        # push cx di es / push cs / pop es
    a.b(0xbf); a.word('last_target')                         # mov di, last_target
    a.b(0x33, 0xc0, 0xb9, 0x15, 0x00, 0xfc, 0xf3, 0xab)      # xor ax, ax / mov cx, 21 / cld / rep stosw
    a.b(0x07, 0x5f, 0x59)                                    # pop es di cx
    a.label('pi_kept')
    for choice, target in SET_UPS.items():                   # fights with their own set-up
        a.b(0x80, 0xfb, choice)                              # cmp bl, choice
        a.short(0x75, f'pi_not_{choice}')                    # jne next
        a.b(0xc7, 0x06, 0x78, 0x09, 0x9e, 0x6c)              # mov word [0978h], 6C9Eh   (as 1000:0CF6)
        a.b(0x2e, 0xc6, 0x06); a.word('vs_monsters'); a.b(0x01)   # mov byte cs:[vs_monsters], 1
        a.b(0x2e, 0xc7, 0x06); a.word('call_target'); a.b(target & 0xff, target >> 8)   # cs:[call_target] = set-up
        a.near(0xe9, 'pi_after')                             # jmp pi_after
        a.label(f'pi_not_{choice}')
    # the key's entry (G_PRACTICE): its lair, or FFh the Black Knight
    a.b(0x8a, 0xc3, 0x3c, KEY_0_CHOICE)                      # mov al, bl / cmp al, 12   the 0 key?
    a.short(0x75, 'pk_entry')                                # jne pk_entry
    a.b(0xb0, 0x0a)                                          # mov al, 10
    a.label('pk_entry')
    a.b(0xfe, 0xc8, 0x32, 0xe4, 0x8b, 0xf0)                  # dec al / xor ah, ah / mov si, ax
    a.b(0x2e, 0x8a, 0x84); a.word('rules_table', G_PRACTICE) # mov al, cs:[si+entry]
    a.b(0x3c, 0xff)                                          # cmp al, 0FFh             the Black Knight
    a.short(0x75, 'pk_lair')                                 # jne pk_lair
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
    a.b(0xbe, KNIGHTS[0] & 0xff, KNIGHTS[0] >> 8)            # mov si, 6C9Eh
    a.b(0x8a, 0x44, STRENGTH, 0x2e, 0xa2); a.word('own_strength')   # mov al, [si+2Eh] / mov cs:[own_strength], al
    a.b(0x8b, 0x44, MAX_HP_FIELD, 0x2e, 0xa3); a.word('own_max_hp')  # mov ax, [si+3Ch] / mov cs:[own_max_hp], ax
    a.b(0x33, 0xd2, 0x33, 0xc0, 0x33, 0xc9)                  # xor dx, dx (strength) / xor ax, ax (HP) / xor cx, cx
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
    a.b(0x50, 0x2e, 0xa0); a.word('own_strength')            # push ax / mov al, cs:[own_strength]
    a.b(0xa2, (KNIGHTS[0] + STRENGTH) & 0xff, (KNIGHTS[0] + STRENGTH) >> 8)   # mov [6CCCh], al
    a.b(0x2e, 0xa1); a.word('own_max_hp')                    # mov ax, cs:[own_max_hp]
    a.b(0xa3, (KNIGHTS[0] + MAX_HP_FIELD) & 0xff, (KNIGHTS[0] + MAX_HP_FIELD) >> 8)   # mov [6CDAh], ax
    a.b(0x58, 0xc3)                                          # pop ax / ret

    # update (D15, 1000:98FD, replaces mov bx,[di+1Ah] before the fight's update pass calls an object's handler,
    # si = the object): the monsters' moves read the knight they fight from [0978h] all over (1000:30EE, 310D, 32CE,
    # ...), so in co-op [0978h] is set for each object: a monster gets the knight it goes for (pick_target), anything
    # else the first knight standing (knight 1 while it stands)
    a.label('rules_update')
    a.b(0x8b, 0x5d, 0x1a, 0x89, 0x5e, 0xfe)                  # mov bx, [di+1Ah] / mov [bp-2], bx   as the game
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'up_done')                                 # je up_done
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
    # than the target margin nearer; ax unchanged when no knight stands
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
    a.b(0xd1, 0xe0, 0x8b, 0xf0)                              # shl ax, 1 / mov si, ax
    a.b(0x2e, 0x8b, 0x84); a.word('last_target')             # mov ax, cs:[si+last_target]
    a.b(0x2e, 0x89, 0x8c); a.word('last_target')             # mov cs:[si+last_target], cx   (the best, for now)
    a.b(0x0b, 0xc0)                                          # or ax, ax
    a.short(0x74, 'tg_pick')                                 # jz tg_pick
    a.b(0x3b, 0xc1)                                          # cmp ax, cx
    a.short(0x74, 'tg_pick')                                 # je tg_pick
    a.b(0x56, 0x8b, 0xf0)                                    # push si / mov si, ax   the last knight
    a.b(0x83, 0x7c, 0x38, 0x00)                              # cmp word [si+38h], 0
    a.short(0x7e, 'tg_last_down')                            # jle tg_last_down
    a.near(0xe8, 'distance')                                 # call distance
    a.b(0x52, 0x2e, 0x8a, 0x16); a.word('rules_table', G_TARGET_MARGIN)   # push dx / mov dl, cs:[margin]
    a.b(0x32, 0xf6, 0x03, 0xda, 0x5a)                        # xor dh, dh / add bx, dx / pop dx
    a.b(0x3b, 0xc3)                                          # cmp ax, bx
    a.short(0x77, 'tg_last_down')                            # ja tg_last_down     clearly farther: switch
    a.b(0x8b, 0xce, 0x5e)                                    # mov cx, si / pop si
    a.b(0x2e, 0x89, 0x8c); a.word('last_target')             # mov cs:[si+last_target], cx   keep it
    a.short(0xeb, 'tg_pick')                                 # jmp tg_pick
    a.label('tg_last_down')
    a.b(0x5e)                                                # pop si
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
    a.b(0x03, 0xc2, 0x5a, 0xc3)                              # add ax, dx / pop dx / ret

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
    a.b(0x2e, 0x80, 0x3e); a.word('coop'); a.b(0x00)         # cmp byte cs:[coop], 0
    a.short(0x74, 'pf_not_coop')                             # je pf_not_coop
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
    a.short(0x74, 'pfc_pop')                                 # je pfc_pop           already ending
    a.b(0xc6, 0x06, 0x7d, 0x89, 0x00, 0xc6, 0x06, 0x87, 0x89, 0x23)   # mov byte [897Dh], 0 / mov byte [8987h], 23h
    a.short(0xeb, 'pfc_pop')                                 # jmp pfc_pop
    a.label('pfc_alive')
    a.b(0x89, 0x36, 0x78, 0x09)                              # mov [0978h], si      the first knight standing
    a.b(0x83, 0x3e, 0x6a, 0x09, 0x00)                        # cmp word [096Ah], 0  monsters still to come
    a.short(0x7f, 'pfc_go')                                  # jg pfc_go
    a.b(0x83, 0x3e, 0x6e, 0x09, 0x00)                        # cmp word [096Eh], 0  monsters on screen
    a.short(0x7f, 'pfc_go')                                  # jg pfc_go
    # won: the end looks at the knight in [8979h] (1000:0ABE gives a fallen one its HP back, and it stood up again)
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
    a.b(0x80, 0x3e, 0x7d, 0x89, 0x00)                        # cmp byte [897Dh], 0     (replaced instruction)
    a.near(0xe9, 'rules_flags')                              # jmp rules_flags

    # practice_hit (1000:4275, a knight was hit; replaces mov si,[di+0Eh] / xor ax,ax): a hit by a teammate is
    # dropped and the knight's control goes on as if not hit (1000:3F05)
    a.label('rules_practice_hit')
    a.b(0x8b, 0x75, 0x0e, 0x33, 0xc0)                        # mov si, [di+0Eh] / xor ax, ax   (replaced)
    # against monsters a knight's dagger does not hit knights (unless coop_dagger_hits)
    a.b(0x2e, 0x80, 0x3e); a.word('vs_monsters'); a.b(0x00)  # cmp byte cs:[vs_monsters], 0
    a.short(0x74, 'ph_knights')                              # je ph_knights
    a.b(0x80, 0x7c, 0x35, DAGGER)                            # cmp byte [si+35h], 1Ah
    a.short(0x75, 'ph_knights')                              # jne ph_knights
    a.b(0x2e, 0xf6, 0x06); a.word('rules_table', G_PRACTICE_FLAGS); a.b(COOP_DAGGER_HITS)   # test flags, dagger
    a.short(0x74, 'ph_drop')                                 # jz ph_drop
    a.label('ph_knights')
    a.near(0xe8, 'colours_active')                           # call colours_active   (3-4 players or co-op)
    a.short(0x74, 'ph_end')                                  # jz ph_end
    a.b(0x8b, 0xdf); a.near(0xe8, 'team')                    # mov bx, di / call team
    a.b(0x8a, 0xe0)                                          # mov ah, al
    a.b(0x8b, 0xde); a.near(0xe8, 'team')                    # mov bx, si / call team
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
    a.label('rules_joy_a')
    a.b(0x2e, 0xa3); a.word('joy_a')                         # mov cs:[joy_a], ax
    a.b(0x8b, 0x5e, 0x08)                                    # mov bx, [bp+8]          the pushed bx
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
    a.short(0x75, 'ja_keys')                                 # jne ja_keys             keys alone
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
    a.b(0x2e, 0x80, 0x3e); a.word('multi'); a.b(0x00)        # cmp byte cs:[multi], 0
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
    a.b(0x80, 0xfb, JOY_B_CONTROL); a.short(0x75, 'ip_keys')  # cmp bl, 6 / jne ip_keys
    a.b(0x2e, 0xa1); a.word('joy_b'); a.short(0xeb, 'ip_end')   # mov ax, cs:[joy_b] / jmp ip_end
    a.label('ip_keys')
    a.b(0x8b, 0x46, 0xfe)                                    # mov ax, [bp-2]          the caller's bx
    a.label('ip_end')
    a.near(0xe9, 'rules_done')                               # jmp rules_done

    # practice_end (1000:014D; replaces mov dx,[0940h]): practice is over
    a.label('rules_practice_end')
    a.b(0x2e, 0xc6, 0x06); a.word('multi'); a.b(0x00)        # mov byte cs:[multi], 0
    a.b(0x2e, 0xc6, 0x06); a.word('monster'); a.b(0x00)      # mov byte cs:[monster], 0
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
    a.short(0x7d, 'village_end')                             # jge village_end
    a.b(0xfe, 0x44, 0x31)                                    # inc byte [si+31h]
    a.short(0xeb, 'village_end')                             # jmp village_end
    a.label('village_full')
    a.b(0x38, 0x44, 0x31)                                    # cmp [si+31h], al
    a.short(0x7d, 'village_hp')                              # jge village_hp
    a.b(0x88, 0x44, 0x31)                                    # mov [si+31h], al
    a.label('village_hp')
    a.b(0x8b, 0x44, 0x3c, 0x89, 0x44, 0x38)                  # mov ax, [si+3Ch] / mov [si+38h], ax
    a.label('village_end')
    a.b(0x58)                                                # pop ax
    a.near(0xe9, 'rules_done')                               # jmp rules_done

def rules_data(a, table):
    """The int 63h tables: the sites (return address, job) and the settings from rules.py."""
    a.label('hooks')
    for where, old, kind in HOOKS + [(where, old, 'fate') for where, old, _ in FATE_HOOKS]:
        _, ret = hook_bytes(where, old, kind)
        a.b(ret & 0xff, ret >> 8); a.word('rules_' + kind)
    for ret, kind in PRACTICE_HOOKS:
        a.b(ret & 0xff, ret >> 8); a.word('rules_' + kind)
    a.b(0, 0)
    a.label('fate_sites')                                    # return address, routine, stream * 2
    for where, old, stream in FATE_HOOKS:
        target = (where + 3 + struct.unpack('<h', bytes.fromhex(old)[1:])[0]) & 0xffff
        a.b(struct.pack('<HHH', where + 2, target, 2 * stream))
    a.label('fate_state'); a.b(bytes(2 * FATE_STREAMS))
    a.label('fate_target'); a.b(0, 0)
    a.label('multi'); a.b(0)                                 # D12: 0, or 3-4 knights in this practice
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
    a.label('call_target'); a.b(0, 0)                        # D12: call_game
    a.label('call_ret'); a.b(0, 0)
    a.label('recolour'); a.b(0)                              # D13: first pixel value to move in this frame, 0 = none
    a.label('level'); a.b(16)                                # D13: fade level of entries 32-37, 0-16
    a.label('words_left'); a.b(9)
    a.label('colour_sites')                                  # D13/D15: where MAIN keeps the colour words: 32-40
    for sites in [sites for _, _, sites in RECOLOUR] + [GREEN_SITES]:
        for site in sites:
            a.b(site & 0xff, site >> 8)
    a.label('rc_shift'); a.b(RECOLOUR_SHIFT)                 # D15: the shift of the frame being recoloured
    a.label('coop'); a.b(0)                                  # D15: knights in a co-op practice, 0 = none
    a.label('vs_monsters'); a.b(0)                           # D15: 1 = a practice against monsters
    a.label('quitting'); a.b(0)                              # D15: 1 = Esc has ended this practice fight
    a.label('last_hit'); a.b(bytes(4))                       # K6: BIOS ticks of the last counted hit (0 = none)
    a.label('own_strength'); a.b(0)                          # D15: knight 1's own strength and max HP during combine
    a.label('own_max_hp'); a.b(0, 0)
    a.label('last_target'); a.b(bytes(2 * 21))               # D15: each monster's knight (20 slots, the dragon)
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
    a.near(0xe8, 'wait')                                     # call wait         autosave happens here
    a.near(0xe8, 'accept')                                   # call accept       (a loaded autosave resumes here)
    a.near(0xe8, 'mcb')                                      # call mcb
    a.b(0xbe); a.word('old_name')                            # mov si, old_name
    a.near(0xe8, 'set_name')                                 # call set_name
    a.near(0xe8, 'refresh')                                  # call refresh      back to MAIN
    a.label('save_skip')
    a.b(0x07, 0x1f, 0x5d, 0x5f, 0x5e, 0x5a, 0x59, 0x5b, 0x58)   # pop es ds bp di si dx cx bx ax
    a.b(0xcf)                                                # iret

    # --- int 65h: a knight's turn starts on the map (resident) ---
    a.label('turn_handler')
    a.b(0x8b, 0x36, 0xe8, 0x77)                              # mov si, [77e8h]       (replaced MAIN instruction)
    a.b(0x83, 0x7c, 0x20, COMPUTER)                          # cmp word [si+20h], 4  computer knight?
    a.short(0x75, 'turn_save')                               # jne turn_save
    a.b(0xcf)                                                # iret                  no save for computer turns
    a.label('turn_save')
    a.b(0x2e, 0xc7, 0x06); a.word('name_ptr'); a.word('turn_name')    # mov word cs:[name_ptr], turn_name
    a.near(0xe9, 'save_state')                               # jmp save_state

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

    a.label('refresh')                                       # run the child so that DOSBox-X re-reads the name
    a.b(0xa1); a.word('reserve')                             # mov ax, [reserve]
    a.b(0x0b, 0xc0)                                          # or ax, ax
    a.short(0x74, 'no_free')                                 # jz no_free
    a.b(0x8e, 0xc0, 0xb4, 0x49, 0xcd, 0x21)                  # mov es, ax / mov ah, 49h / int 21h   free it
    a.label('no_free')
    a.b(0x2e, 0x8c, 0x16); a.word('save_ss')                 # mov cs:[save_ss], ss
    a.b(0x2e, 0x89, 0x26); a.word('save_sp')                 # mov cs:[save_sp], sp
    a.b(0x0e, 0x07)                                          # push cs / pop es
    a.b(0xbb); a.word('param_block')                         # mov bx, param_block
    a.b(0xba); a.word('child_path')                          # mov dx, child_path
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
    a.label('fight_name'); a.b((FIGHT_NAME + b'1').ljust(8, b'\0'))   # the digit is number_name's
    a.label('turn_name'); a.b((TURN_NAME + b'1').ljust(8, b'\0'))
    a.label('slot_next'); a.b(0, 0)                          # next turn and fight number - 1 (SAVEHOOK.SLT)
    a.label('name_ptr'); a.b(0, 0)
    a.label('reserve'); a.b(0, 0)
    a.label('save_ss'); a.b(0, 0)
    a.label('save_sp'); a.b(0, 0)
    a.label('child_path'); a.b(CHILD_PATH)
    a.label('chk_path'); a.b(CHK_PATH)
    a.label('slot_path'); a.b(SLOT_PATH)
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
    a.short(0x74, 'quit')                                    # je quit     already installed: run as the child
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
    for seg in ('tail_seg', 'fcb1_seg', 'fcb2_seg'):
        a.b(0x8c, 0x0e); a.word(seg)                         # mov [seg], cs
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

    code = bytearray(a.build())
    paras = (a.labels['resident_end'] + 15) // 16           # offsets count from the PSP, so this includes it
    for name in ('resident_paras_1', 'resident_paras_2'):
        struct.pack_into('<H', code, a.labels[name] - 0x100 + 1, paras)
    return bytes(code)

if __name__ == '__main__':
    com = make_savehook()
    open(sys.argv[1], 'wb').write(com)
    print(f'{len(com)} bytes -> {sys.argv[1]}')
