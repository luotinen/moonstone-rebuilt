"""Make General MIDI music modules for the DOS game: copies of the Roland modules (RTUNEn.BIN) whose embedded
MIDI programs are remapped from MT-32 patches to General MIDI (same table as extract_music.py). Installed as
ATUNEn.BIN they play through the MPU-401 in Sound Blaster mode, e.g. on DOSBox-X's FluidSynth with a SoundFont.
The Roland player sends file channel n on channel n+1 and keeps drums on channel 10, which suits GM as well.
Usage: python -I tools/make_gm_tunes.py <game dir> <output dir>   (writes <output dir>/DISKA|DISKB/ATUNEn.BIN)"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_music import find_smf, to_general_midi

def main(game, out):
    for path in sorted(glob.glob(f'{game}/DISK?/RTUNE*.BIN')):
        module = open(path, 'rb').read()
        smf = find_smf(module)
        start = module.find(smf)
        gm = to_general_midi(smf)
        assert len(gm) == len(smf)
        disk, name = os.path.basename(os.path.dirname(path)), os.path.basename(path)
        os.makedirs(f'{out}/{disk}', exist_ok=True)
        target = f'{out}/{disk}/A{name[1:]}'
        open(target, 'wb').write(module[:start] + gm + module[start + len(smf):])
        changed = sum(a != b for a, b in zip(smf, gm))
        print(f'{disk}/{name} -> {target}: {changed} program bytes remapped')

if __name__ == '__main__':
    main(*sys.argv[1:3])
