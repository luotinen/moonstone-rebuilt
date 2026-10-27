"""Byte patches for the uncompressed MAIN.EXE (see make_main_exe.py). Each patch names its address in the
running program (segment:offset in the load-segment-1000h image, or DS:offset with DS = 223Bh), the original bytes
it expects and the new bytes, so a patch can never be applied to the wrong file. Fix ids match FIXES.md (K1...)."""
import struct

LOAD_SEG, DS_SEG = 0x1000, 0x223b

PATCHES = {
    'K1': {
        'title': 'CHEAP1B sample: the sample name table lists "cheap2b" twice (DS:8721, entries 8 and 9); '
                 'entry 8 is meant to be cheap1b (the list is alphabetical), so CHEAP1B was never played',
        'bytes': [(('DS', 0x87c1), b'cheap2b\0', b'cheap1b\0')],
    },
    'K2': {
        'title': 'Ratmen grow stronger as the moon waxes (manual). The ratmen setup at 1000:23fe used its strong '
                 'stats (7 HP, bite 6, claw 3) at full moon (2Dh) and its strongest (12 HP, bite 8, claw 5) at new moon '
                 '(31h). Now: strongest at full moon, strong at three-quarter moon (2Fh), normal otherwise',
        'bytes': [((0x1000, 0x240c), b'\x83\x3e\x89\x89\x2d', b'\x83\x3e\x89\x89\x2f'),   # strong:    full -> 3/4
                  ((0x1000, 0x2427), b'\x83\x3e\x89\x89\x31', b'\x83\x3e\x89\x89\x2d')],  # strongest: new  -> full
    },
    'K4': {
        'title': 'Object slot leak in fights (a safeguard: in play a fight uses about 8-9 of the 10 animation slots). '
                 'New fight objects (fire, hit effects, daggers) are made at 1000:3E89: a game object slot (20 at DS:6F08) and '
                 'an animation slot (10 at DS:947E, call 981F). When the animation slots are full, 981F returns AX=1, which '
                 'was ignored: the game slot stayed taken for the rest of the fight, and with all 20 gone the next object '
                 'was written past the table (DS:76B0). Now the routine ends with [di] = AX xor 1, which frees the game slot '
                 'when the animation slot could not be had (2A1E has already set [di] to 1, so the old mov word [di],1 '
                 'was redundant)',
        'bytes': [((0x1000, 0x3ea5), bytes.fromhex('c7050100885535e87059c3'),      # mov word [di],1 / mov [di+35h],dl /
                                                                                    # call 981F / ret
                                     bytes.fromhex('885535e874593401' '8805c3'))],  # mov [di+35h],dl / call 981F /
    },                                                                              # xor al,1 / mov [di],al / ret
    'K5': {
        'title': 'Quit key moved from Q to Esc. On the map the turn loop (1000:A594) checks Q (scan code 10h) with the '
                 'key check at 8288 and goes straight to GAME OVER, without asking, during any knight\'s turn. Q is '
                 'next to W and A, the second player\'s movement keys, so the game could end by accident (the '
                 '"unexpected Game Over" reports). Esc (01h) is far from the movement keys; MAIN uses it only in the '
                 'menu before a game',
        'bytes': [((0x1000, 0xa594), b'\xb8\x10\x00', b'\xb8\x01\x00')],   # mov ax,10h (Q) -> mov ax,01h (Esc)
    },
    'K11': {
        'title': 'Math and Mythral read their stat tables wrongly (confirmed in play for Math: only strength ever rose, '
                 'and twice Math printed a long list of game data). Math (1000:B9C2, also used when the Guardian wins at '
                 '0FF8) steps through the 4-byte table at DS:E33B (stat field, message) 8 bytes per index, and the caller '
                 'reads the message at [si+ax+4]: strength 5/16, constitution 3/16, endurance never, 8/16 a field that is '
                 'not a stat, and never the right message. Mythral (1000:BBD5) searches only 2 of the 3 entries of '
                 'DS:DE04 / DE1C (stat field, message record) and takes [si+4] instead of [si+2]. Now Math gives strength '
                 '5/16, endurance 5/16, constitution 6/16 with the matching line, and Mythral the right message for every '
                 'stat, gain and loss',
        'bytes': [((0x1000, 0xb9e2), b'\xd1\xe0', b'\x90\x90'),                         # shl ax,1 -> nop nop (index *4)
                  ((0x1000, 0xb972), b'\x03\xf0\xff\x74\x04', b'\x90\x90\xff\x74\x02'),  # add si,ax / push [si+4]
                                                                                    #   -> nop nop / push [si+2]
                  ((0x1000, 0xbbd5), b'\xb9\x02\x00', b'\xb9\x03\x00'),               # mov cx,2 -> mov cx,3
                  ((0x1000, 0xbbe7), b'\x8b\x74\x04', b'\x8b\x74\x02')],              # mov si,[si+4] -> [si+2]
    },
    'K16': {
        'title': 'Duel looting. (1) The weapon pick on the loot screen (1000:ce91) moved only the weapon number, so a '
                 'knight who took the Sword of Sharpness got it without the sword item, and the loser kept the item '
                 'and was re-armed with it: two swords. The compare and store after the long-sword check become '
                 'int 62h, which SAVEHOOK.COM handles: it also moves the item when the weapon is 19h (needs '
                 'SAVEHOOK.COM resident, like D6). (2) The automatic loot of a computer winner (1000:0b8e) moved the '
                 'hit points of the old armour of the winner instead of the armour taken; push/pop ax go. (3) When '
                 'the loser has no lives left, the sword is now set as the weapon of the winner (1000:0c4b), not of '
                 'the loser. (4) The stat raise of a computer knight after a duel win (1000:04bd) had no cap; it now '
                 'stops at 5 like the human level-up (1000:d58b) and keeps the XP when the stat is already 5',
        'bytes': [((0x1000, 0xce99), b'\x3b\x6c\x40\x7c\x03', b'\xcd\x62\xeb\x04\x90'),   # int 62h / jmp cea1
                  ((0x1000, 0x0b96), b'\x50', b'\x90'),                                     # push ax -> nop
                  ((0x1000, 0x0b9d), b'\x58', b'\x90'),                                     # pop ax -> nop
                  ((0x1000, 0x0c4b), b'\xc7\x45\x40', b'\xc7\x44\x40'),                     # [di+40h] -> [si+40h]
                  ((0x1000, 0x04bd), bytes.fromhex('2503003d02007e03b802008bd8fe402e83fb0175048344380a'),
                                     bytes.fromhex('2503003c0314ff8bd880782e057d18fe402e4b75048344380a'))],
        # and ax,3 / cmp al,3 / adc al,-1 (3 -> 2) / mov bx,ax / cmp byte [bx+si+2Eh],5 / jge 04e6 (no raise, no XP
        # spent) / inc byte [bx+si+2Eh] / dec bx / jnz 04d6 / add word [si+38h],10 (CON: +10 HP)
    },
    'K17': {
        'title': 'Ratmen disease removed (user decision; widely taken for a bug). A ratman\'s bite set the disease '
                 '(knight +60h, 1000:42AD), and at every periodic update (each moon phase, four days; 1000:1229) a '
                 'diseased knight lost a life point, without any message. Now the bite does not infect, and the '
                 'update skips the loss also for a knight infected in an older save',
        'bytes': [((0x1000, 0x42ad), b'\xc6\x45\x60\x01', b'\xc6\x45\x60\x00'),   # mov byte [di+60h],1 -> 0
                  ((0x1000, 0x122d), b'\x74\x04', b'\xeb\x04')],                     # je -> jmp: no life lost
    },
    'D6': {
        'title': 'Save state before every fight (Moonstone Rebuilt only). Every fight (lairs, dragon, Guardian, knights) '
                 'starts in the routine at 1000:0307; its first instruction (mov word [7841h],0) becomes int 66h, '
                 'which SAVEHOOK.COM (make_savehook.py) handles: it does that instruction and has DOSBox-X autosave '
                 'the state. Needs SAVEHOOK.COM resident, otherwise the game crashes at the first fight',
        'bytes': [((0x1000, 0x0307), b'\xc7\x06\x41\x78\x00\x00', b'\xcd\x66\x90\x90\x90\x90')],
    },
    'D7': {
        'title': 'Save state at the start of every human turn on the map (Moonstone Rebuilt only). The turn change at '
                 '1000:a610 sets up the next knight (call 1000:a697) and then loads its record (1000:a63f, '
                 'mov si,[77e8h]); that instruction becomes int 65h, which SAVEHOOK.COM handles: it does the '
                 'instruction and, unless the knight is computer-controlled, has DOSBox-X autosave the state. '
                 'Needs SAVEHOOK.COM resident',
        'bytes': [((0x1000, 0xa63f), b'\x8b\x36\xe8\x77', b'\xcd\x65\x90\x90')],
    },
    'D9': {
        'title': 'Player 2 moves with W, A, S, D (Moonstone Rebuilt; user request). The keyboard routine at 1000:83C0 '
                 'reads player 2 as Tab (fire), W (up), X (down), A (left) and D (right); down becomes S (scan code '
                 '1Fh), which the game does not use for anything else',
        'bytes': [((0x1000, 0x8403), b'\xb8\x2d\x00', b'\xb8\x1f\x00')],   # mov ax,2Dh (X) -> mov ax,1Fh (S)
    },
}

# --- INTR.EXE (intro and ending) -----------------------------------------------------------------------------------
# K9: skip the intro (and ending) with Enter, Space or Esc. Every intro scene waits for vertical retrace in the routine
# at 0000:0F9E; it is replaced by a far jump to new code in the unused tail of the music-module buffer (segment 0492h,
# offset 2300h; the largest intro module is 8274 bytes). When the module is loaded (first byte 1Eh = push ds) and one of
# the keys is pressed, the new code resets the stack and jumps to the intro's own shutdown path at 0000:00D1 (stop music,
# restore video and timer, exit). Otherwise it does the original retrace wait and returns through a RET at 0000:0FA3.
INTR_CAVE_SEG, INTR_CAVE_OFF = 0x0492, 0x2300
INTR_DATA_SEG, INTR_STACK_TOP = 0x06d2, 0x0800

KEY_STATE_TABLE = 0x46f3                                # INTR's own int 9 handler (0000:4774): byte per scan code,
SKIP_SCANCODES = (0x1c, 0x39, 0x01)                     # 00 = held, FF = released. Enter, Space, Esc.

def _intr_skip_code():
    """Machine code for the cave, plus offsets (within it) of words that need relocation. INTR replaces the keyboard
    interrupt and never passes keys to the BIOS, so the code reads INTR's key state table instead of int 16h."""
    c, relocs, fix = bytearray(), [], {}
    def emit(*b): c.extend(b)
    def jcc(op, label): emit(op, 0); fix[len(c) - 1] = label
    emit(0x2e, 0x80, 0x3e); flag_ref = len(c); emit(0, 0, 0x00)   # cmp byte cs:[flag], 0     already skipping?
    jcc(0x75, 'wait')                                  # jne wait
    emit(0x2e, 0x80, 0x3e, 0x00, 0x00, 0x1e)          # cmp byte cs:[0000], 1Eh   music module loaded?
    jcc(0x75, 'wait')                                  # jne wait
    emit(0x50, 0x06)                                   # push ax / push es
    emit(0xb8); relocs.append(len(c)); emit(0x00, 0x00)   # mov ax, segment 0 (INTR code)
    emit(0x8e, 0xc0)                                   # mov es, ax
    for code in SKIP_SCANCODES:
        addr = KEY_STATE_TABLE + code
        emit(0x26, 0x80, 0x3e, addr & 0xff, addr >> 8, 0x00)   # cmp byte es:[table+code], 0   held?
        jcc(0x74, 'skip')
    emit(0x07, 0x58)                                   # pop es / pop ax
    labels = {'wait': len(c)}
    emit(0xba, 0xda, 0x03)                             # mov dx, 3DAh  (original retrace wait)
    emit(0xec, 0xa8, 0x08, 0x75, 0xfb)                 # in al,dx / test al,8 / jnz -5
    emit(0xec, 0xa8, 0x08, 0x74, 0xfb)                 # in al,dx / test al,8 / jz -5
    emit(0xea, 0xa3, 0x0f); relocs.append(len(c)); emit(0x00, 0x00)   # jmp far 0000:0FA3 (ret)
    labels['skip'] = len(c)
    emit(0x07, 0x58)                                   # pop es / pop ax
    emit(0x2e, 0xc6, 0x06); flag_set = len(c); emit(0, 0, 0x01)      # mov byte cs:[flag], 1
    emit(0xb8); relocs.append(len(c)); emit(INTR_DATA_SEG & 0xff, INTR_DATA_SEG >> 8)   # mov ax, data segment
    emit(0x8e, 0xd8)                                   # mov ds, ax
    emit(0xbc, INTR_STACK_TOP & 0xff, INTR_STACK_TOP >> 8)                         # mov sp, 0800h
    emit(0xea, 0xd1, 0x00); relocs.append(len(c)); emit(0x00, 0x00)   # jmp far 0000:00D1 (shutdown)
    flag = INTR_CAVE_OFF + len(c); emit(0x00)          # flag byte
    for pos in (flag_ref, flag_set):
        c[pos:pos + 2] = bytes([flag & 0xff, flag >> 8])
    for pos, label in fix.items():
        rel = labels[label] - (pos + 1)
        assert -128 <= rel < 128
        c[pos] = rel & 0xff
    return bytes(c), relocs

def patch_intr_skip(exe):
    """Apply K9 to an uncompressed INTR.EXE; returns the new EXE (relocation table extended)."""
    from unexepack import build_mz
    h = struct.unpack('<14H', exe[:28])
    image = bytearray(exe[h[4] * 16:])
    relocs = [struct.unpack('<HH', exe[h[12] + 4*i:h[12] + 4*i + 4]) for i in range(h[3])]
    hook = 0x0f9e
    expected = bytes.fromhex('bada0390eca80875fb90eca80874fbc3')
    if image[hook:hook + 16] != expected:
        raise ValueError('K9: unexpected bytes at 0000:0F9E (not the GOG INTR.EXE?)')
    cave = INTR_CAVE_SEG * 16 + INTR_CAVE_OFF
    code, code_relocs = _intr_skip_code()
    if any(image[cave:cave + len(code)]):
        raise ValueError('K9: cave area is not empty')
    image[cave:cave + len(code)] = code
    image[hook:hook + 5] = bytes([0xea, INTR_CAVE_OFF & 0xff, INTR_CAVE_OFF >> 8,
                                  INTR_CAVE_SEG & 0xff, INTR_CAVE_SEG >> 8])           # jmp far 0492:2300
    image[hook + 5] = 0xc3                                                               # ret (target of the jump back)
    new = [hook + 3] + [cave + r for r in code_relocs]
    relocs += [(lin & 0xf, lin >> 4) for lin in new]                                     # (offset, segment) pairs
    return build_mz(bytes(image), relocs, h[11], h[10], h[7], h[8], h[5])

def image_offset(where):
    seg, off = where
    seg = DS_SEG if seg == 'DS' else seg
    return (seg - LOAD_SEG) * 16 + off

def apply_patches(exe, ids):
    out = bytearray(exe)
    header = struct.unpack('<H', exe[8:10])[0] * 16
    for pid in ids:
        for where, old, new in PATCHES[pid]['bytes']:
            pos = header + image_offset(where)
            if out[pos:pos + len(old)] != old:
                raise ValueError(f'{pid}: expected {old!r} at {where}, found {bytes(out[pos:pos + len(old)])!r}')
            out[pos:pos + len(new)] = new
    return bytes(out)
