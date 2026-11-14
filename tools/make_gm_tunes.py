"""Make General MIDI music modules for the DOS game: copies of the Roland modules (RTUNEn.BIN) whose embedded
MIDI programs are remapped from MT-32 patches to General MIDI (same table as extract_music.py). Installed as
ATUNEn.BIN they play through the MPU-401 in Sound Blaster mode, e.g. on DOSBox-X's FluidSynth with a SoundFont.
The Roland player sends file channel n on channel n+1 and keeps drums on channel 10, which suits GM as well.

The UART set (D82, for GM music with the Amiga effects): the player sends every MIDI message as an MPU-401
intelligent-mode "want to send data" (D0h + channel to 331h) and waits for the acknowledge with no time-out. The Amiga
effects (SAVEHOOK.COM) switch the MPU to UART mode before every note; in UART mode the MPU ignores commands, so the
player would wait for ever inside the timer interrupt and the game would freeze. In this set the player's command
routine becomes "3Fh (UART mode) to 331h, read 330h, ret": in intelligent mode that gets the acknowledge, in UART
mode it is ignored, and every message then goes out as raw bytes. The start's controller loop ("reset all
controllers" and volume 127) covers channels 0-9 instead of 0-15, so the effects' channels 12-15 keep their state.
The routine is found by its bytes, so the build shifted by 16h (ATUNE5) is covered too.
Usage: python -I tools/make_gm_tunes.py <game dir> <output dir> [<UART output dir>]
       (writes <output dir>/DISKA|DISKB/ATUNEn.BIN, and the UART set the same way)"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_music import find_smf, to_general_midi

# the command routine: push ax, cx, dx / wait until the MPU takes input / out dx (331h), al / then the acknowledge
COMMAND = bytes.fromhex('50 51 52 ba3103 8ae0 ec 02c0 78fb 8ac4 ba3103 ee')
UART_COMMAND = bytes.fromhex('50 52 ba3103 b03f ee 4a ec 5a 58 c3')   # push ax, dx / mov dx, 331h / mov al, 3Fh / out /
                                                                      # dec dx / in al, dx / pop dx, ax / ret
START_LOOP = bytes.fromhex('fec1 fec5 80fd10')                        # inc cl / inc ch / cmp ch, 10h

def uart_patch(module):
    """The module with its player in UART mode (see the module's docstring)."""
    smf = find_smf(module)
    code = module[:module.find(smf)]
    at, loop = code.find(COMMAND), code.find(START_LOOP)
    if at < 0 or code.find(COMMAND, at + 1) >= 0 or loop < 0 or code.find(START_LOOP, loop + 1) >= 0:
        raise ValueError('the tune has another player than the one this tool knows (command routine or start loop)')
    m = bytearray(module)
    m[at:at + len(UART_COMMAND)] = UART_COMMAND
    m[loop + 6] = 0x0a                                                # cmp ch, 0Ah
    return bytes(m)

def main(game, out, uart_out=None):
    for path in sorted(glob.glob(f'{game}/DISK?/RTUNE*.BIN')):
        module = open(path, 'rb').read()
        smf = find_smf(module)
        start = module.find(smf)
        gm = to_general_midi(smf)
        if len(gm) != len(smf):
            raise ValueError(f'{path}: the General MIDI version changed the length of the music')
        disk, name = os.path.basename(os.path.dirname(path)), os.path.basename(path)
        os.makedirs(f'{out}/{disk}', exist_ok=True)
        target = f'{out}/{disk}/A{name[1:]}'
        tune = module[:start] + gm + module[start + len(smf):]
        open(target, 'wb').write(tune)
        changed = sum(a != b for a, b in zip(smf, gm))
        print(f'{disk}/{name} -> {target}: {changed} program bytes remapped')
        if uart_out:
            os.makedirs(f'{uart_out}/{disk}', exist_ok=True)
            open(f'{uart_out}/{disk}/A{name[1:]}', 'wb').write(uart_patch(tune))

if __name__ == '__main__':
    main(*sys.argv[1:4])
