"""Unpack MAIN.EXE (PKLITE around Microsoft EXEPACK) by running its own unpacker stubs in a
16-bit x86 emulator (Unicorn) until execution reaches the real program at the load segment.
The result is the memory image from the load segment up to 640 KB: code at 1000:0000 and the
data segment at DS = 223Bh (image offset DS_START). Needs: pip install unicorn
Usage: python -I tools/unpack_main.py <game dir> [<output file>]"""
import sys, os, struct

PSP_SEG = 0x0ff0
LOAD_SEG = PSP_SEG + 0x10                       # 1000h, the segment all addresses in FIXES.md use
DS_START = (0x223b - LOAD_SEG) * 16             # data segment inside the image
CACHE = '_extracted/MAIN_unpacked.bin'

def unpack(exe):
    from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
    from unicorn.x86_const import (UC_X86_REG_AH, UC_X86_REG_AX, UC_X86_REG_CS, UC_X86_REG_IP,
                                   UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_DS, UC_X86_REG_ES,
                                   UC_X86_REG_EFLAGS)
    d = open(exe, 'rb').read()
    h = struct.unpack('<14H', d[:28])
    image = d[h[4] * 16:(h[2] - 1) * 512 + (h[1] or 512)]
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x110000)
    mu.mem_write(LOAD_SEG * 16, image)
    psp = bytearray(256); psp[0:2] = b'\xcd\x20'; struct.pack_into('<H', psp, 2, 0x9fff)
    mu.mem_write(PSP_SEG * 16, bytes(psp))
    for i in range(h[3]):                       # relocations of the outer (PKLITE) layer
        off, seg = struct.unpack('<HH', d[h[12] + 4*i:h[12] + 4*i + 4])
        a = (LOAD_SEG + seg) * 16 + off
        v = struct.unpack('<H', mu.mem_read(a, 2))[0]
        mu.mem_write(a, struct.pack('<H', (v + LOAD_SEG) & 0xffff))
    for reg, val in ((UC_X86_REG_CS, LOAD_SEG + h[11]), (UC_X86_REG_IP, h[10]), (UC_X86_REG_SS, LOAD_SEG + h[7]),
                     (UC_X86_REG_SP, h[8]), (UC_X86_REG_DS, PSP_SEG), (UC_X86_REG_ES, PSP_SEG)):
        mu.reg_write(reg, val)

    def on_int(uc, number, _):                  # the stubs only ask DOS for its version and to resize memory
        ah = uc.reg_read(UC_X86_REG_AH)
        if number == 0x21 and ah == 0x4a: uc.reg_write(UC_X86_REG_EFLAGS, uc.reg_read(UC_X86_REG_EFLAGS) & ~1)
        elif number == 0x21 and ah == 0x30: uc.reg_write(UC_X86_REG_AX, 0x0005)
        else: raise RuntimeError(f'unexpected int {number:02x}h ah={ah:02x}h while unpacking')
    reached = []
    def on_code(uc, address, size, _):
        if uc.reg_read(UC_X86_REG_CS) == LOAD_SEG:  # the unpacked program starts at 1000:0000
            reached.append(uc.reg_read(UC_X86_REG_IP)); uc.emu_stop()
    mu.hook_add(UC_HOOK_INTR, on_int)
    mu.hook_add(UC_HOOK_CODE, on_code)
    mu.emu_start((LOAD_SEG + h[11]) * 16 + h[10], 0xfffff, count=50_000_000)
    if not reached:
        raise RuntimeError('unpacker did not reach the program entry')
    mem = bytes(mu.mem_read(LOAD_SEG * 16, 0xa0000 - LOAD_SEG * 16))
    if b'KN1.OB' not in mem[DS_START:DS_START + 0x10000]:
        raise RuntimeError('unpacked image does not look like Moonstone MAIN.EXE')
    return mem

def main_image(game):
    """Unpacked MAIN.EXE memory image; unpacked once and cached in <game>/_extracted/."""
    path = os.path.join(game, CACHE)
    if not os.path.exists(path):
        mem = unpack(os.path.join(game, 'MAIN.EXE'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(mem)
    return open(path, 'rb').read()

def main_ds(game):
    """MAIN.EXE's 64 KB data segment (DS = 223Bh)."""
    return main_image(game)[DS_START:DS_START + 0x10000]

if __name__ == '__main__':
    game = sys.argv[1]
    mem = unpack(os.path.join(game, 'MAIN.EXE'))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(game, CACHE)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'wb').write(mem)
    print(f'{len(mem)} bytes -> {out}')
