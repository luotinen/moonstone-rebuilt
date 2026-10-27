"""Build SAVEHOOK.COM, the resident helper for D6 and D7 (DOSBox-X save state right before every fight and at the
start of every human player's turn on the map) and for K16 (code that does not fit in MAIN.EXE).

DOSBox-X has no way for a DOS program to ask for a save state, but its autosave can use a separate slot range per
running program ("autosave = 1 -1 PRETURN:91-95 PREFIGHT:96-100": check every second, never save for other
programs, save into slots 91-95 while the program is PRETURN and 96-100 while it is PREFIGHT). DOSBox-X takes the
program name from the memory block of the current PSP, and only re-reads it when a program starts or ends. The two
names need slot ranges of their own, because DOSBox-X keeps one rotation counter per name: two names in the same
slots would overwrite each other's newest saves.

SAVEHOOK.COM installs four interrupt handlers and stays resident. The patches in patches.py replace an instruction in
MAIN.EXE with an interrupt:
* D6, int 66h: the first instruction of the fight routine (1000:0307, mov word [7841h],0); every fight starts there.
* D7, int 65h: the instruction after the turn set-up (1000:a63f, mov si,[77e8h], the record of the knight whose turn
  begins); only for knights not controlled by the computer (record +20h <> 4), so computer turns do not pause.
The handler:
1. does the replaced instruction,
2. renames MAIN's memory block to PREFIGHT or PRETURN and runs SAVEHOOK.COM again as a child, so DOSBox-X re-reads the name
   (the child sees the handlers are installed and exits at once),
3. waits WAIT_TICKS BIOS ticks (about 1.1 s), during which DOSBox-X's once-a-second autosave check saves the state.
   Emulation stops while DOSBox-X writes a save, so the wait lasts longer in real time and often covers a second
   check: one fight or turn then fills two slots with the same moment. The game cannot see the pause (its clocks,
   the CMOS clock included, follow emulated time), so this is not avoided,
4. restores the old name and runs the child again, so the name is MAIN again.
K16, int 62h: the weapon pick on the duel loot screen (1000:ce99) moved only the weapon number. Taking the Sword of
Sharpness (weapon 19h) left the sword item with the loser, so both knights had the sword. The handler also moves the
item (item table +4) when the weapon is 19h, then does the replaced compare and store (the better weapon is kept).
Rules, int 63h: the custom game rules from custom_rules.ini (rules.py; only when they are on, CUSTOM_RULES.FLG).
rules.py writes the settings table into SAVEHOOK.COM and patches MAIN.EXE; see rules_code below. Without custom
rules the table holds the normal game's values and the normal MAIN.EXE never calls int 63h.

MAIN.EXE may use all free memory, so SAVEHOOK keeps a small block of its own and frees it for the child.
Usage: python -I tools/make_savehook.py <output SAVEHOOK.COM>   (the normal game; rules.py builds it with rules)"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rules import (HOOKS, SECTIONS, SECTION_SIZE, MODES, VILLAGE, G_ARMOUR_HP, G_SWORD, G_REST,
                   G_VILLAGE, G_MAX_LIVES, G_RING, G_COLOURS, MAX_HP, hook_bytes, table as rules_default_table)

FIGHT_INT, TURN_INT, LOOT_INT, RULES_INT = 0x66, 0x65, 0x62, 0x63   # MAIN.EXE uses none of these
SHARPNESS = 0x19                         # weapon number of the Sword of Sharpness
FIGHT_NAME = b'PREFIGHT'                 # program names that the autosave setting matches (8 characters at most)
TURN_NAME = b'PRETURN'
MODE_REINCARNATION, MODE_RESPAWN, MODE_INVULNERABLE = MODES['reincarnation'], MODES['respawn'], MODES['invulnerable']
VILLAGE_FULL = VILLAGE['full']
COMPUTER = 4                             # knight record +20h: control type 4 = computer
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

    # init (1000:1FEF): knight set-up, di = record, si = item table
    a.label('rules_init')
    a.b(0x50, 0x51, 0x56, 0x57, 0x87, 0xf7)                  # push ax cx si di / xchg si, di
    a.near(0xe8, 'section')                                  # call section
    a.near(0xe8, 'start_knight')                             # call start_knight
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
    for where, old, kind in HOOKS:
        _, ret = hook_bytes(where, old, kind)
        a.b(ret & 0xff, ret >> 8); a.word('rules_' + kind)
    a.b(0, 0)
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
    a.near(0xe8, 'mcb')                                      # call mcb          es = MAIN's memory block
    a.b(0xbe, 0x08, 0x00)                                    # mov si, 8
    a.b(0xbf); a.word('old_name')                            # mov di, old_name
    a.b(0xb9, 0x08, 0x00)                                    # mov cx, 8
    a.label('save_name')
    a.b(0x26, 0x8a, 0x04, 0x88, 0x05, 0x46, 0x47)            # mov al, es:[si] / mov [di], al / inc si / inc di
    a.short(0xe2, 'save_name')                               # loop save_name
    a.b(0x8b, 0x36); a.word('name_ptr')                      # mov si, [name_ptr]
    a.near(0xe8, 'set_name')                                 # call set_name
    a.near(0xe8, 'refresh')                                  # call refresh      DOSBox-X now sees the new name
    a.near(0xe8, 'wait')                                     # call wait         autosave happens here
    a.near(0xe8, 'mcb')                                      # call mcb
    a.b(0xbe); a.word('old_name')                            # mov si, old_name
    a.near(0xe8, 'set_name')                                 # call set_name
    a.near(0xe8, 'refresh')                                  # call refresh      back to MAIN
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
    a.label('fight_name'); a.b(FIGHT_NAME.ljust(8, b'\0'))
    a.label('turn_name'); a.b(TURN_NAME.ljust(8, b'\0'))
    a.label('name_ptr'); a.b(0, 0)
    a.label('reserve'); a.b(0, 0)
    a.label('save_ss'); a.b(0, 0)
    a.label('save_sp'); a.b(0, 0)
    a.label('child_path'); a.b(CHILD_PATH)
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
