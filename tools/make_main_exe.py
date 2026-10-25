"""Build a runnable, uncompressed MAIN.EXE (for patching and for DOSBox). MAIN.EXE is PKLITE around EXEPACK:
1. run the PKLITE stub in the emulator until it jumps to the EXEPACK entry (CS:0012 with the 'RB' header at CS:0010),
2. rebuild that intermediate EXEPACK executable from memory and registers,
3. unpack EXEPACK with unexepack.py, which gives a normal MZ file with a relocation table.
Optionally applies the patches in patches.py. Needs: pip install unicorn
Usage: python -I tools/make_main_exe.py <game dir> <output MAIN.EXE> [patch id ...]"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unpack_main import PSP_SEG, LOAD_SEG
from unexepack import unexepack, build_mz

def pklite_to_exepack(exe):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
    from unicorn.x86_const import (UC_X86_REG_AH, UC_X86_REG_AX, UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_SS,
                                   UC_X86_REG_SP, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_EFLAGS)
    d = open(exe, 'rb').read()
    h = struct.unpack('<14H', d[:28])
    image = d[h[4] * 16:(h[2] - 1) * 512 + (h[1] or 512)]
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x110000)
    mu.mem_write(LOAD_SEG * 16, image)
    psp = bytearray(256); psp[0:2] = b'\xcd\x20'; struct.pack_into('<H', psp, 2, 0x9fff)
    mu.mem_write(PSP_SEG * 16, bytes(psp))
    for i in range(h[3]):
        off, seg = struct.unpack('<HH', d[h[12] + 4*i:h[12] + 4*i + 4])
        a = (LOAD_SEG + seg) * 16 + off
        v = struct.unpack('<H', mu.mem_read(a, 2))[0]
        mu.mem_write(a, struct.pack('<H', (v + LOAD_SEG) & 0xffff))
    for reg, val in ((UC_X86_REG_CS, (LOAD_SEG + h[11]) & 0xffff), (UC_X86_REG_IP, h[10]),
                     (UC_X86_REG_SS, (LOAD_SEG + h[7]) & 0xffff), (UC_X86_REG_SP, h[8]),
                     (UC_X86_REG_DS, PSP_SEG), (UC_X86_REG_ES, PSP_SEG)):
        mu.reg_write(reg, val)

    def on_int(uc, number, _):
        ah = uc.reg_read(UC_X86_REG_AH)
        if number == 0x21 and ah == 0x4a: uc.reg_write(UC_X86_REG_EFLAGS, uc.reg_read(UC_X86_REG_EFLAGS) & ~1)
        elif number == 0x21 and ah == 0x30: uc.reg_write(UC_X86_REG_AX, 0x0005)
        else: raise RuntimeError(f'unexpected int {number:02x}h ah={ah:02x}h in PKLITE stub')
    state = {}
    def on_code(uc, address, size, _):
        cs, ip = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
        if LOAD_SEG <= cs < 0xa000 and uc.mem_read(cs * 16 + 0x10, 2) == b'RB' and ip == 0x12:
            state.update(cs=cs, ss=uc.reg_read(UC_X86_REG_SS), sp=uc.reg_read(UC_X86_REG_SP))
            uc.emu_stop()
    mu.hook_add(UC_HOOK_INTR, on_int)
    mu.hook_add(UC_HOOK_CODE, on_code)
    mu.emu_start(((LOAD_SEG + h[11]) & 0xffff) * 16 + h[10], 0xfffff, count=20_000_000)
    if not state:
        raise RuntimeError('did not reach the EXEPACK entry')
    stub = state['cs'] * 16
    exepack_size = struct.unpack('<H', mu.mem_read(stub + 6, 2))[0]
    dest_paras = struct.unpack('<H', mu.mem_read(stub + 12, 2))[0]
    end = stub + exepack_size
    inner = bytes(mu.mem_read(LOAD_SEG * 16, end - LOAD_SEG * 16))
    image_paras = (len(inner) + 15) // 16
    min_paras = max(0, dest_paras + (exepack_size + 15) // 16 + 16 - image_paras)
    return build_mz(inner, [], state['cs'] - LOAD_SEG, 0x12, state['ss'] - LOAD_SEG, state['sp'], min_paras)

def make_main_exe(game, patch_ids=()):
    exe = unexepack(pklite_to_exepack(os.path.join(game, 'MAIN.EXE')))
    if patch_ids:
        from patches import apply_patches
        exe = apply_patches(exe, patch_ids)
    return exe

if __name__ == '__main__':
    game, out, *ids = sys.argv[1:]
    exe = make_main_exe(game, ids)
    open(out, 'wb').write(exe)
    print(f'{len(exe)} bytes -> {out}' + (f' (patches: {", ".join(ids)})' if ids else ''))
