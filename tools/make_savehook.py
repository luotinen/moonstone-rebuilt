"""Build SAVEHOOK.COM, the resident helper for D6 and D7 (DOSBox-X save state right before every fight and at the
start of every human player's turn on the map) and for K16 (code that does not fit in MAIN.EXE).

DOSBox-X has no way for a DOS program to ask for a save state, but its autosave can use a separate slot range per
running program ("autosave = 1 -1 PRETURN:91-95 PREFIGHT:96-100": check every second, never save for other
programs, save into slots 91-95 while the program is PRETURN and 96-100 while it is PREFIGHT). DOSBox-X takes the
program name from the memory block of the current PSP, and only re-reads it when a program starts or ends. The two
names need slot ranges of their own, because DOSBox-X keeps one rotation counter per name: two names in the same
slots would overwrite each other's newest saves.

SAVEHOOK.COM installs three interrupt handlers and stays resident. The patches in patches.py replace an instruction in
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

MAIN.EXE may use all free memory, so SAVEHOOK keeps a small block of its own and frees it for the child.
Usage: python -I tools/make_savehook.py <output SAVEHOOK.COM>"""
import sys, struct

FIGHT_INT, TURN_INT, LOOT_INT = 0x66, 0x65, 0x62   # MAIN.EXE uses none of these
SHARPNESS = 0x19                         # weapon number of the Sword of Sharpness
FIGHT_NAME = b'PREFIGHT'                 # program names that the autosave setting matches (8 characters at most)
TURN_NAME = b'PRETURN'
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
    def word(self, label):                      # 16-bit address of a label
        self.fixups.append(('abs', len(self.code), label)); self.code += b'\0\0'
    def short(self, opcode, label):             # jcc / jmp short / loop
        self.code.append(opcode); self.fixups.append(('rel8', len(self.code), label)); self.code.append(0)
    def near(self, opcode, label):              # call / jmp near
        self.code.append(opcode); self.fixups.append(('rel16', len(self.code), label)); self.code += b'\0\0'
    def here(self):
        return self.org + len(self.code)
    def build(self):
        for kind, pos, label in self.fixups:
            target = self.labels[label]
            if kind == 'abs':
                struct.pack_into('<H', self.code, pos, target)
            elif kind == 'rel8':
                rel = target - (self.org + pos + 1)
                assert -128 <= rel < 128, label
                self.code[pos] = rel & 0xff
            else:
                struct.pack_into('<h', self.code, pos, target - (self.org + pos + 2))
        return bytes(self.code)

def make_savehook():
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
    # setup uses 62h, 65h or 66h, and the patched MAIN.EXE must always reach these handlers.
    a.b(0xba); a.word('fight_handler')                       # mov dx, fight_handler
    a.b(0xb8, FIGHT_INT, 0x25, 0xcd, 0x21)                   # mov ax, 2566h / int 21h
    a.b(0xba); a.word('turn_handler')                        # mov dx, turn_handler
    a.b(0xb8, TURN_INT, 0x25, 0xcd, 0x21)                    # mov ax, 2565h / int 21h
    a.b(0xba); a.word('loot_handler')                        # mov dx, loot_handler
    a.b(0xb8, LOOT_INT, 0x25, 0xcd, 0x21)                    # mov ax, 2562h / int 21h
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
