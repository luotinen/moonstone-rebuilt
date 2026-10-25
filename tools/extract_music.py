"""Extract the music of Moonstone. Every ?TUNEn.BIN is an int-handler player module
(ah=0 start, 1 tick, 2 stop) followed by a Standard MIDI File, which the player finds by
scanning for 'MThd'/'MTrk' (ATUNE1.BIN 00EA). A = AdLib and R = Roland MT-32 modules carry
the same MIDI data; B modules (PC speaker, ports 42h/61h) carry reduced arrangements.
Tempo: the player ignores tempo meta events. The game's timer interrupt (1000:5934) calls
it at 1193182/0x5555 = 54.62 Hz and each call steps every track N ticks ('mov cx, N' patched
over 'mov cx, 8'), so the real tempo is 54.62 * N * 60 / 192 BPM. *_game.mid has that tempo.
The Roland player sends channel n as n+1 (MT-32 parts 2..), drums stay on 10, and program
numbers are MT-32 patches; *_gm.mid (game tempo) remaps them for General MIDI synths.
Usage: python -I tools/extract_music.py <game dir> <output dir>"""
import sys, os, glob, struct, hashlib, re

TIMER_HZ = 1193182 / 0x5555

def ticks_per_call(module):
    return re.search(rb'\xb9\x08\x00\xb9(.)\x00', module, re.S).group(1)[0]

# MT-32 preset -> nearest General MIDI program; ScummVM's MidiDriver::_mt32ToGm
# (audio/mididrv.cpp). Valid because the tunes send no sysex, so only stock MT-32 timbres play.
MT32_TO_GM = [
      0,   1,   0,   2,   4,   4,   5,   3,  16,  17,  18,  16,  16,  19,  20,  21,
      6,   6,   6,   7,   7,   7,   8, 112,  62,  62,  63,  63,  38,  38,  39,  39,
     88,  95,  52,  98,  97,  99,  14,  54, 102,  96,  53, 102,  81, 100,  14,  80,
     48,  48,  49,  45,  41,  40,  42,  42,  43,  46,  45,  24,  25,  28,  27, 104,
     32,  32,  34,  33,  36,  37,  35,  35,  79,  73,  72,  72,  74,  75,  64,  65,
     66,  67,  71,  71,  68,  69,  70,  22,  56,  59,  57,  57,  60,  60,  58,  61,
     61,  11,  11,  98,  14,   9,  14,  13,  12, 107, 107,  77,  78,  78,  76,  76,
     47, 117, 127, 118, 118, 116, 115, 119, 115, 112,  55, 124, 123,   0,  14, 117]
MT32_TO_GM[12] = 19     # Pipe Org 1: the tracks are named 'Church Org', so Church Organ, not Drawbar

def walk(smf):
    """Yield (offset of status-or-data, status, kind) for every event; handles running status.
    kind is the meta type for FF events, else the channel status byte."""
    _, ntracks, _ = struct.unpack('>HHH', smf[8:14])
    j = 14
    for _ in range(ntracks):
        end = j + 8 + struct.unpack('>I', smf[j+4:j+8])[0]; k, run = j + 8, 0
        while k < end:
            while smf[k] & 0x80: k += 1
            k += 1
            st = smf[k]
            if st == 0xff:
                yield k, 0xff, smf[k+1]; k += 3 + smf[k+2]; continue
            if st in (0xf0, 0xf7):
                k += 1; ln = 0
                while True:
                    b = smf[k]; k += 1; ln = ln << 7 | b & 0x7f
                    if b < 0x80: break
                k += ln; continue
            if st & 0x80: run = st; k += 1
            yield k, run, run
            k += 1 if run & 0xf0 in (0xc0, 0xd0) else 2
        j = end

def to_general_midi(smf):
    out = bytearray(smf)
    for k, status, _ in walk(smf):
        if status & 0xf0 == 0xc0 and status & 15 != 9:
            out[k] = MT32_TO_GM[smf[k]]
    return bytes(out)

def texts(smf):
    return [smf[k+3:k+3+smf[k+2]].decode('latin1') for k, st, kind in walk(smf) if st == 0xff and kind in (1, 3)]

def with_tempo(smf, us_per_quarter):
    """Copy of smf with every Set Tempo meta event replaced (all are 3-byte FF 51 03)."""
    out = bytearray(smf)
    for m in re.finditer(rb'\xff\x51\x03', smf):
        out[m.end():m.end() + 3] = us_per_quarter.to_bytes(3, 'big')
    return bytes(out)

def find_smf(data):
    i = data.find(b'MThd')
    _, ntracks, _ = struct.unpack('>HHH', data[i+8:i+14])
    j = i + 14
    for _ in range(ntracks):
        assert data[j:j+4] == b'MTrk'
        j += 8 + struct.unpack('>I', data[j+4:j+8])[0]
    return data[i:j]

def summary(smf):
    """Length in seconds, channels and program changes, by walking all tracks."""
    _, ntracks, div = struct.unpack('>HHH', smf[8:14])
    events, j = [], 14
    for _ in range(ntracks):
        n = struct.unpack('>I', smf[j+4:j+8])[0]; t, k, end, run = 0, j + 8, j + 8 + n, 0
        while k < end:
            dt = 0
            while True:
                b = smf[k]; k += 1; dt = dt << 7 | b & 0x7f
                if b < 0x80: break
            t += dt
            st = smf[k]
            if st == 0xff:
                kind, ln = smf[k+1], smf[k+2]
                if kind == 0x51: events.append((t, 'tempo', int.from_bytes(smf[k+3:k+6], 'big')))
                k += 3 + ln; continue
            if st in (0xf0, 0xf7):
                ln = 0; k += 1
                while True:
                    b = smf[k]; k += 1; ln = ln << 7 | b & 0x7f
                    if b < 0x80: break
                k += ln; continue
            if st & 0x80: run = st; k += 1
            ch, hi = run & 15, run & 0xf0
            if hi == 0xc0: events.append((t, 'prog', (ch, smf[k])))
            if hi == 0x90 and smf[k+1]: events.append((t, 'note', ch))
            k += 1 if hi in (0xc0, 0xd0) else 2
        j = end
    events.sort(key=lambda e: e[0])
    sec, last, tempo = 0.0, 0, 500000
    for t, kind, v in events:
        sec += (t - last) * tempo / div / 1e6; last = t
        if kind == 'tempo': tempo = v
    chans = sorted({v for _, k, v in events if k == 'note'})
    progs = sorted({v for _, k, v in events if k == 'prog'})
    return sec, chans, progs

def main(game, out):
    os.makedirs(out, exist_ok=True)
    seen = {}
    for f in sorted(glob.glob(f'{game}/DISK?/?TUNE*.BIN')):
        name = os.path.basename(f)[:-4].lower()
        module = open(f, 'rb').read()
        smf, n = find_smf(module), ticks_per_call(module)
        h = hashlib.md5(smf + bytes([n])).hexdigest()
        if h in seen:
            print(f'{name}: same MIDI as {seen[h]}'); continue
        seen[h] = name
        div = struct.unpack('>H', smf[12:14])[0]
        game = with_tempo(smf, round(div * 1e6 / (TIMER_HZ * n)))
        open(f'{out}/{name}.mid', 'wb').write(smf)
        open(f'{out}/{name}_game.mid', 'wb').write(game)
        open(f'{out}/{name}_gm.mid', 'wb').write(to_general_midi(game))
        sec, chans, progs = summary(smf)
        gsec = summary(game)[0]
        print(f'{name}: file {sec:5.1f} s, in game {gsec:5.1f} s ({TIMER_HZ * n * 60 / div:5.1f} BPM), '
              f'channels {[c + 1 for c in chans]}, programs MT-32 -> GM {[(c + 1, p, MT32_TO_GM[p]) for c, p in progs]}, '
              f'texts {texts(smf)}')

if __name__ == '__main__':
    main(*sys.argv[1:])
