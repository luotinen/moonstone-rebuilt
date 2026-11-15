"""Set up the Amiga intro and ending music for Moonstone Rebuilt (D87), from the user's own Amiga disk images.

1. Finds the disk with music.cmp and vmusic.cmp among the .adf files in a folder (tools/adf.py) and checks the two
   modules (tools/rnc.py unpacks them).
2. Writes the tune modules that play them from the SoundFont (_music/amiga/font/ATUNE1.BIN and ATUNE6.BIN).
   INTR.EXE loads a tune module to 0492:0000 and calls it through int 60h: ah = 0 starts the tune, 1 is the timer's
   tick, 2 stops it. Ours is a few bytes of machine code written here: the start sends the two notes of the tune's
   left and right sample (make_amiga_audio.py puts them in the SoundFont, preset 3 of the Amiga bank) to the MIDI
   port, the stop sends their note-offs. Its head also holds the pace of the pictures while the tune plays (the
   Amiga's pictures are slower): the intro's retrace wait reads it (patches.py, K9's cave), and the tick slows the
   BIOS clock, which times the scenes' frame loops, by holding back some of the ticks INTR.EXE passes to the BIOS.
   The intro starts our tune in its first sequence, as the Amiga does (K9's cave); a start while it plays does
   nothing, so the game's own start later changes nothing.
   tools/set_sound.bat and Start.bat use these modules whenever DOSBox-X can load a SoundFont that has the tunes:
   with AdLib or General MIDI music, with the DOS or the Amiga sound effects; MT-32 music keeps its Roland tunes.
3. Removes what the older way (D8, retired in phase 5 step 7) left in the folder: the modules, VLC's WAV files and
   the muted DOS tunes.
The results go to <rebuilt>/_music/amiga/.
Usage: python -I tools/make_amiga_music.py <folder with .adf files> <rebuilt folder>"""
import sys, os, struct, hashlib, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amiga_module import read_disk, PREFERRED, TUNE_PRESET, TUNE_KEYS, TUNE_CHANNELS, TUNE_VOLUME, TUNE_PANS
from patches import (AMIGA_BANK, INTR_TUNE_SIGN, INTR_TUNE_N, INTR_TUNE_M, INTR_TUNE_SKIP, INTR_TUNE_OF,
                     INTR_TUNE_ACC, INTR_TUNE_TICKS, INTR_TUNE_ON, INTR_TUNE_LEFT, INTR_TUNE_SWITCH, INTR_TUNE_FIRST,
                     INTR_TUNE_SECOND, INTR_TUNE_CODE, INTR_TIMER_DIVIDER)

# SHA-256 of the unpacked modules from the disks this was made with; other dumps of the same disks should match
KNOWN = {'intro': '26b78aeda0ac1dbdaa68e3be0706159121557db224370227489e63298fcd4faa',
         'ending': '606e033e6c436ad6e347c47a8fae57f58a2c7464deedbc5eab533ac7e77b8358'}
# What D8 (the host player, retired) wrote into _music/amiga: removed when the music is set up again
D8_FILES = ('intro.mod', 'ending.mod', 'intro.wav', 'ending.wav', 'amiga_music.log')
D8_SETS = ('adlib', 'gm', 'gm_amiga', 'mt32')      # the muted DOS tunes, one folder per music set

# --- D87: the tune modules that play from the SoundFont -----------------------------------------------------------
FONT_SET = 'font'                                  # _music/amiga/font
TUNE_FILES = {'intro': 'ATUNE1.BIN', 'ending': 'ATUNE6.BIN'}
# The pace of the pictures while a tune plays: (n, m, skip, of). INTR.EXE times its pictures in two ways:
#  * by vertical retraces (70 a second): of every m calls of its retrace wait, n wait for one more retrace.
#    2 of 5 is the Amiga's 50 frames a second, for the waits that count frames;
#  * by the BIOS clock (the scenes' frame loops wait for two of its ticks, 110 ms): of every `of` ticks of INTR.EXE's
#    timer (54.6 Hz; a third of them go on to the BIOS clock), `skip` are kept from the BIOS clock, which then runs
#    of / (of - skip) times slower.
# A pace may have a second part: (n, m, skip, of, ticks, n2, m2, skip2, of2): `ticks` of INTR.EXE's timer after the
# start the second pace takes the first one's place.
# Set by measurement (docs/amiga-audio-plan-2026-11-11.md, 5.13 and 5.14): the first bright flash of each lightning
# scene of the intro is to come 0.3 s before its thunder in the tune (at 58.7 s and 81.4 s). Since the intro starts
# its tune where the Amiga does (in the first sequence, 20 s earlier than the DOS game), the DOS pace brings the
# first flash there by itself (58.67 s), but the second scene 5.1 s early: so no pace until just after the first
# flash (3223 ticks, 59.0 s), then 2 of 5 retraces (the Amiga's 50 frames a second) and 18 of 47 ticks kept from
# the BIOS clock (1.62 times slower): 58.67 s and 81.33 s.
# The ending has no such mark; it starts its tune where the Amiga does. With 2 of 5 and 41 of 91 its pictures last
# 98.0 s, a little longer than its tune (97.92 s), whose start then comes round for a quarter of a second; with
# 7 of 16 they last 96.6 s.
PACE = {'intro': (0, 1, 0, 1, 3223, 2, 5, 18, 47), 'ending': (2, 5, 7, 16)}

def paces(pace):
    """(first pace, ticks from the start to the second, second pace) from (n, m, skip, of) or
    (n, m, skip, of, ticks, n2, m2, skip2, of2); ticks = 0: the first pace all the time."""
    pace = tuple(pace)
    if len(pace) == 4:
        pace += (0,) + pace
    if len(pace) != 9 or not 0 <= pace[4] <= 0xffff:
        raise ValueError(f'pace {pace}: four numbers, or four, the ticks to the second pace (0-65535) and four more')
    for n, m, skip, of in (pace[:4], pace[5:]):
        if not (0 <= n <= m <= 255 and m > 0 and 0 <= skip < of <= 127):
            raise ValueError(f'pace {n} of {m}, {skip} of {of}: n must be at most m and skip less than of')
    return pace[:4], pace[4], pace[5:]

def tune_module(name, pace=None):
    """The machine code of a tune module: an int 60h handler loaded at 0492:0000."""
    first, switch, second = paces(pace or PACE[name])
    h = bytes.fromhex
    def send(values): return b''.join(bytes([0xb0, v, 0xee]) for v in values)        # mov al,v / out dx,al
    def clear(at, word): return bytes([0x2e, 0xc7 if word else 0xc6, 0x06, at, 0]) + bytes(2 if word else 1)
    def cs(*op, at): return bytes([0x2e, *op, at, 0x00])     # an instruction on a byte of the head
    def use(pace):                                           # the pace in use = the 4 bytes at `pace`
        return (cs(0xa1, at=pace) + cs(0xa3, at=INTR_TUNE_N)            # mov ax, cs:[pace] / mov cs:[n], ax
                + cs(0xa1, at=pace + 2) + cs(0xa3, at=INTR_TUNE_SKIP))  # mov ax, cs:[pace+2] / mov cs:[skip], ax
    keys = TUNE_KEYS[name]
    setup = [v for c, pan in zip(TUNE_CHANNELS, TUNE_PANS)
             for v in (0xb0 | c, 0, AMIGA_BANK, 0xc0 | c, TUNE_PRESET, 0xb0 | c, 7, TUNE_VOLUME, 0xb0 | c, 10, pan)]
    notes = [v for c, key in zip(TUNE_CHANNELS, keys) for v in (0x90 | c, key, 0x7f)]
    offs = [v for c, key in zip(TUNE_CHANNELS, keys) for v in (0x80 | c, key, 0)]
    leave = h('5a 58 1f cf')                                 # pop dx / pop ax / pop ds / iret
    # the start: INTR.EXE starts our tune in the first sequence (patches.py) and again at its own place later; a
    # start while the tune plays does nothing
    start = (cs(0x80, 0x3e, at=INTR_TUNE_ON) + b'\x00' + bytes([0x74, len(leave)]) + leave   # cmp byte cs:[on],0 / je
             + use(INTR_TUNE_FIRST) + cs(0xa1, at=INTR_TUNE_SWITCH) + cs(0xa3, at=INTR_TUNE_LEFT)   # left = switch
             + clear(INTR_TUNE_ACC, False) + clear(INTR_TUNE_TICKS, False)
             + cs(0xc6, 0x06, at=INTR_TUNE_ON) + b'\x01'     # mov byte cs:[on], 1
             + h('ba3103 b03f ee 4a ec')                     # mov dx,331h / mov al,3Fh / out dx,al: UART mode / dec dx / in al,dx
             + send(setup + notes) + leave)
    stop = clear(INTR_TUNE_ON, False) + h('ba3003') + send(offs) + leave      # mov byte cs:[on],0 / mov dx,330h
    # the tick (ds = INTR.EXE's data): on `skip` of every `of` ticks the count to the BIOS's next tick goes back up
    divider = INTR_TIMER_DIVIDER.to_bytes(2, 'little')
    held = h('833e') + divider + h('03 7704') + h('ff06') + divider      # cmp word [divider],3 / ja +4 / inc word [divider]
    late = cs(0x2a, 0x06, at=INTR_TUNE_OF) + held            # sub al, cs:[of] / hold this tick back
    count = (cs(0xa0, at=INTR_TUNE_TICKS) + cs(0x02, 0x06, at=INTR_TUNE_SKIP)      # mov al, cs:[ticks] / add al, cs:[skip]
             + cs(0x3a, 0x06, at=INTR_TUNE_OF) + bytes([0x72, len(late)]) + late   # cmp al, cs:[of] / jb +
             + cs(0xa2, at=INTR_TUNE_TICKS))                 # mov cs:[ticks], al
    # the second pace: `switch` ticks after the start it takes the first one's place (never with switch = 0)
    later = use(INTR_TUNE_SECOND)
    turn = (cs(0x83, 0x3e, at=INTR_TUNE_LEFT) + b'\x00' + bytes([0x74, 5 + 2 + len(later)])    # cmp word cs:[left],0 / je
            + cs(0xff, 0x0e, at=INTR_TUNE_LEFT) + bytes([0x75, len(later)]) + later)       # dec word cs:[left] / jne
    count = turn + count
    tick = cs(0x80, 0x3e, at=INTR_TUNE_ON) + b'\x00' + bytes([0x74, len(count)]) + count + leave   # cmp byte cs:[on],0 / je
    head = bytearray(INTR_TUNE_CODE)
    head[0] = 0x1e                                           # push ds: what K9's skip knows a loaded module by
    head[1:3] = struct.pack('<H', INTR_TUNE_SIGN)            # jmp short over the numbers
    head[INTR_TUNE_N:INTR_TUNE_OF + 1] = bytes(first)        # in use until the start sets it again
    head[INTR_TUNE_SWITCH:INTR_TUNE_SWITCH + 2] = struct.pack('<H', switch)
    head[INTR_TUNE_FIRST:INTR_TUNE_FIRST + 4] = bytes(first)
    head[INTR_TUNE_SECOND:INTR_TUNE_SECOND + 4] = bytes(second)
    if head[1] != 0xeb or head[2] != INTR_TUNE_CODE - 3:      # the short jump over the numbers
        raise ValueError('the head of the tune module does not match patches.py')
    # push ax, dx / cmp ah,1 / je tick / cmp ah,0 / je start / cmp ah,2 / je stop / leave
    if max(len(count), 5 + len(leave) + len(tick) + len(stop)) > 127:
        raise ValueError('the tune module\'s short jumps are out of range')
    code = (h('50 52') + h('80fc01 74') + bytes([10 + len(leave)]) + h('80fc00 74') + bytes([5 + len(leave) + len(tick) + len(stop)])
            + h('80fc02 74') + bytes([len(leave) + len(tick)]) + leave)
    return bytes(head) + code + tick + stop + start

def write_font_modules(out):
    folder = os.path.join(out, FONT_SET)
    os.makedirs(folder, exist_ok=True)
    for name, file in TUNE_FILES.items():
        open(os.path.join(folder, file), 'wb').write(tune_module(name))

def find_modules(folder):
    found = read_disk(folder)
    if not found:
        raise SystemExit(f'No Amiga Moonstone disk 1 (with music.cmp and vmusic.cmp) found in {folder}; expected {PREFERRED}')
    return found[0], found[1]

def remove_d8(out):
    """The older player's files (D8): nothing reads them any more."""
    gone = []
    for name in D8_FILES:
        if os.path.isfile(os.path.join(out, name)):
            os.remove(os.path.join(out, name)); gone.append(name)
    for music_set in D8_SETS:
        if os.path.isdir(os.path.join(out, music_set)):
            shutil.rmtree(os.path.join(out, music_set)); gone.append(music_set + '/')
    return gone

def main(adf_folder, rebuilt):
    disk, modules = find_modules(adf_folder)
    print(f'Modules found on {os.path.basename(disk)}')
    out = os.path.join(rebuilt, '_music', 'amiga')
    os.makedirs(out, exist_ok=True)
    for name, data in modules.items():
        digest = hashlib.sha256(data).hexdigest()
        if KNOWN[name] and KNOWN[name] != digest:
            print(f'  note: {name} module differs from the known disk version ({digest[:12]})')
        print(f'  {name}: {len(data)} bytes, title {data[:20].split(bytes(1))[0].decode("latin-1")!r}')
    write_font_modules(out)
    print(f'Tune modules that play the tunes from the SoundFont -> {os.path.join(out, FONT_SET)}')
    gone = remove_d8(out)
    if gone:
        print(f'  removed the files of the older player (D8): {", ".join(gone)}')

if __name__ == '__main__':
    main(*sys.argv[1:3])
