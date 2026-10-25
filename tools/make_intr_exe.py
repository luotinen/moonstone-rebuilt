"""Build an uncompressed INTR.EXE (EXEPACK removed, so it starts in DOSBox-X), optionally with fixes from patches.py.
Usage: python -I tools/make_intr_exe.py <game dir> <output INTR.EXE> [K9]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unexepack import unexepack
from patches import patch_intr_skip

INTR_PATCHES = {'K9': patch_intr_skip}

def make_intr_exe(game, patch_ids=()):
    exe = unexepack(open(os.path.join(game, 'INTR.EXE'), 'rb').read())
    for pid in patch_ids:
        exe = INTR_PATCHES[pid](exe)
    return exe

if __name__ == '__main__':
    game, out, *ids = sys.argv[1:]
    exe = make_intr_exe(game, ids)
    open(out, 'wb').write(exe)
    print(f'{len(exe)} bytes -> {out}' + (f' (patches: {", ".join(ids)})' if ids else ''))
