"""Render the Amiga Moonstone sound programs to WAV files, from the user's own Amiga disk images (never distributed).

The Amiga game's sound driver (in `mog` on disk 1) has four channels. Each runs a "sound program", a byte stream of
notes and commands, one step per frame (50 Hz), and plays samples from the `.a` bank files on disks 2 and 3 through the
Amiga's sound chip (Paula). This tool reads the driver's tables and the banks, steps the programs as the driver does
and plays the result through a small model of a Paula channel, so every program becomes the sound the Amiga makes.
See docs/amiga-audio-plan-2026-11-11.md and research/amiga_sound.py (the tables and commands).

Only addresses, signatures and checksums are in this file: the programs, period tables and samples all come from the
disks. The results are for the user's own machine.

Without the disks the effects are built from the DOS game's own samples (48 of the Amiga's samples are in it, the
same data), substitute sounds of our own for the others (sounds/, see sounds/SOURCES.md) and sound_programs.json:
for each effect program, what the driver plays frame by frame (which sample, at what rate and volume, for how long),
written by export_sound_programs.py. No sample, period table or program code of the Amiga game is in that table.

Usage: python -I tools/make_amiga_audio.py <folder with the three .adf files> <output folder>
       writes <output folder>/sNNN.wav for every program, mix_*.wav for the sounds played on several channels at
       once, and index.html, a page to listen to them all.
       python -I tools/make_amiga_audio.py <folder with the three .adf files> <file.sf2> soundfont
       writes the SoundFont the game plays its effects from (D65): one key per program, see FONT_PROGRAMS.
       python -I tools/make_amiga_audio.py <installation folder> <file.sf2> install
       the same for an installation: from the disk images in its amiga folder if all three are there, else from its
       SAMPLES folder, its sounds folder and sound_programs.json."""
import sys, os, glob, json, struct, wave, hashlib, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_python'))   # AmigaSound_Setup.bat puts numpy there if Python has none
import numpy as np
from adf import Adf
import soundfont

# --- the driver's data in `mog`, as addresses in the image made by load_hunks ------------------------------------------
BASE = 0x10000
PERIODS, MODS, SEQ_TABLE, WAVES, INSTR, INSTR_END = 0x3edc4, 0x3f326, 0x401c4, 0x40470, 0x40518, 0x40c50
PROGRAMS = 167
# Where the tables are is checked by signature, so another dump of the same program is found too
PERIOD_SIGN = struct.pack('>4H', 27364, 26972, 26585, 26204)              # the first periods, at PERIODS
WAVE_SIGN = bytes.fromhex('0040804000c080c000081008 00f8f0f8'.replace(' ', ''))   # the second synth wave, at WAVES + 10h
KNOWN_MOG = {'6355df0579232ca5e2cd8b5412584689e16d5fa86704b03eaccb2f7d1f94ffac'}  # SHA-256 of `mog` this was made with
# Which bank file each sample instrument's offset refers to (found by matching offsets and lengths with the files)
BANK_OF = [(9, 16, 'kn'), (17, 38, 'dr'), (39, 40, 'kn'), (41, 57, 'ba'), (58, 60, 'kn'), (61, 70, 'tr'), (71, 71, 'wn'),
           (72, 78, 'gu'), (79, 87, 'mu'), (88, 95, 'ra'), (96, 99, 'mu'), (100, 102, 'gu'), (103, 112, 're'),
           (113, 114, 'wz'), (115, 122, 'to'), (123, 127, 'be'), (128, 129, 're'), (130, 130, 'he')]
BANKS = sorted({b for _, _, b in BANK_OF})
PAULA_CLOCK, FRAME_HZ = 3546895, 50                # PAL: sample rate = clock / period; the driver steps once a frame
RATE = 44100                                       # of the WAV files
LEFT = (0, 3)                                      # Paula channels 0 and 3 are the left speaker, 1 and 2 the right
# Sounds the game starts on several channels at once: name -> [(program, channel)], with what they are
MIXES = {
    'dragon_fire': ('The dragon breathes fire: breath and fire loops', [(29, 0), (27, 1)]),
    'guardian_scream': ('The Guardian\'s long scream with three echoes', [(74, 0), (75, 1), (76, 2), (77, 3)]),
    'guardian_cry_1': ('A scream and its echo', [(64, 0), (65, 1)]),
    'guardian_cry_2': ('A scream and its echo', [(66, 0), (67, 1)]),
    'guardian_cry_3': ('A scream and its echo', [(68, 0), (69, 1)]),
    'mud_voice_1': ('The mudmen\'s scare voice, two voices', [(151, 0), (152, 1)]),
    'mud_voice_2': ('The mudmen\'s scare voice, two voices', [(87, 0), (148, 1)]),
    'mud_voice_3': ('The mudmen\'s scare voice, two voices', [(88, 0), (149, 1)]),
    'mud_voice_4': ('The mudmen\'s scare voice, two voices', [(89, 0), (150, 1)]),
    'drums': ('War drums (programs 110-113)', [(110, 0), (111, 1), (112, 2), (113, 3)]),
    'healer': ('The healer (116-119)', [(116, 0), (117, 1), (118, 2), (119, 3)]),
    'mythral': ('Mythral (121-124)', [(121, 0), (122, 1), (123, 2), (124, 3)]),
    'tavern': ('The tavern (125-127)', [(125, 0), (126, 1), (127, 2)]),
    'wizard': ('The wizard (128-131)', [(128, 0), (129, 1), (130, 2), (131, 3)]),
    'piece_158': ('Programs 158-160 (place not yet identified)', [(158, 0), (159, 1), (160, 2)]),
}

# The effect programs in the SoundFont and their keys are set in patches.py, which SAVEHOOK.COM's sound handler
# follows too. (Keys below 15 are not used: the FluidSynth in DOSBox-X plays them too low; a footstep on key 3 came
# out an octave down in the spike.)
from patches import AMIGA_PROGRAMS as FONT_PROGRAMS, AMIGA_FIRST_KEY as FIRST_KEY, AMIGA_PER_PRESET as PER_PRESET

def font_key(program):
    """-> (preset, key) of a program in the SoundFont."""
    return (program - 1) // PER_PRESET, FIRST_KEY + (program - 1) % PER_PRESET

class AudioError(Exception):
    pass

def load_hunks(d):
    """An Amiga hunk program as one image with relocations applied: hunk k at BASE + the earlier hunks' sizes (each
    rounded up to 16)."""
    pos = 0
    def L():
        nonlocal pos
        v = struct.unpack('>I', d[pos:pos+4])[0]; pos += 4; return v
    if L() != 0x3f3: raise AudioError('mog is not an Amiga program')
    L(); n = L(); L(); L()
    sizes = [(L() & 0x3fffffff) * 4 for _ in range(n)]
    bases, a = [], BASE
    for s in sizes:
        bases.append(a); a += (s + 15) & ~15
    img, h = bytearray(a - BASE), 0
    while pos < len(d) and h < n:
        t = L() & 0x3fffffff
        if t in (0x3e9, 0x3ea):
            s = L() * 4
            img[bases[h]-BASE:bases[h]-BASE+s] = d[pos:pos+s]; pos += s
        elif t == 0x3eb: L()
        elif t == 0x3ec:
            while (k := L()):
                tgt = L()
                for _ in range(k):
                    p = bases[h] - BASE + L()
                    img[p:p+4] = struct.pack('>I', (struct.unpack('>I', img[p:p+4])[0] + bases[tgt]) & 0xffffffff)
        elif t == 0x3f2: h += 1
        else: raise AudioError(f'mog: unknown hunk type {t:x}')
    return bytes(img)

def read_disks(folder):
    """-> {lower-case file name: bytes} of `mog` and the bank files, from the .adf files in the folder."""
    want, found = {'mog'} | {b + '.a' for b in BANKS}, {}
    paths = sorted(glob.glob(os.path.join(folder, '*.adf')) + glob.glob(os.path.join(folder, '*.ADF')))
    for path in dict.fromkeys(paths):
        try:
            adf = Adf(path)
            for p, h in adf.walk():
                name = p.split('/')[-1].lower()
                if name in want and name not in found:
                    found[name] = adf.read(h)
        except ValueError as e:
            print(f'  {os.path.basename(path)}: {e}')
    missing = sorted(want - set(found))
    if missing:
        raise AudioError(f'not found on the disk images in {folder}: {", ".join(missing)} (all three disks are needed)')
    return found

class Driver:
    """The driver's tables and the banks."""
    def __init__(self, files):
        self.verified = hashlib.sha256(files['mog']).hexdigest() in KNOWN_MOG
        self.img = img = load_hunks(files['mog'])
        code, data = img.find(PERIOD_SIGN), img.find(WAVE_SIGN)
        if code < 0 or data < 0 or img.find(PERIOD_SIGN, code + 1) >= 0:
            raise AudioError('the sound driver was not found in mog: not the Moonstone main program this tool knows')
        self.dc, self.dd = code + BASE - PERIODS, data + BASE - (WAVES + 0x10)   # how far code and data are from the known places
        self.banks = {}
        for b in BANKS:                             # a bank is the file without its 32-byte hunk header (wn.a has none)
            d = files[b + '.a']
            self.banks[b] = d[0x20:] if d[:4] == b'\0\0\x03\xf3' else d
        self.ins = []
        for k in range((INSTR_END - INSTR) // 14):
            a = INSTR + self.dd + 14 * k
            flag, loop, lenw, ptr, ptab = struct.unpack('>HHHII', self.mem(a, 14))
            bank = next((b for lo, hi, b in BANK_OF if lo <= k <= hi), None)
            if bank: pcm = self.banks[bank][ptr:ptr + lenw * 2]
            elif BASE <= ptr < BASE + len(img): pcm = self.mem(ptr, lenw * 2)       # a synth wave in the driver
            else: pcm = b''
            self.ins.append(dict(looped=flag == 0xffff, loop=loop, ptab=ptab, bank=bank or 'wave', ptr=ptr,
                                 pcm=np.frombuffer(pcm, dtype=np.int8).astype(np.float32) / 128.0))
        self.name = self._names()

    def mem(self, a, n): return self.img[a - BASE:a - BASE + n]
    def byte(self, a): return self.img[a - BASE]
    def word(self, a): return struct.unpack('>H', self.mem(a, 2))[0]
    def start(self, prog): return struct.unpack('>I', self.mem(SEQ_TABLE + self.dc + 4 * prog, 4))[0]

    def _names(self):
        """Instrument number -> the sample's name in its bank (and where a slice starts)."""
        out = {}
        for k, x in enumerate(self.ins):
            if x['bank'] == 'wave': out[k] = 'synth wave'; continue
            if x['bank'] == 'he': out[k] = 'he.a'; continue
            d, i, best = self.banks[x['bank']], 0, None
            while (i := d.find(b'NAME', i)) >= 0:
                b = d.find(b'BODY', i)
                if b < 0 or b + 8 > x['ptr']: break
                best = (d[i+8:i+8+struct.unpack('>I', d[i+4:i+8])[0]].split(b'\0')[0].decode('latin1'), x['ptr'] - (b + 8)); i += 4
            out[k] = (best[0] + (f' +{best[1]}' if best[1] else '')) if best else '?'
        return out

SKIP1 = (0x84, 0xa0, 0xa4)

class Channel:
    """One driver channel running one program: step() is the driver's work for one frame."""
    def __init__(self, drv, prog, tempo):
        self.d, self.tempo = drv, tempo             # tempo: a one-item list, shared by the channels as in the driver
        self.start = self.pc = drv.start(prog)
        self.stack = []
        self.dur = self.reload = 0
        self.vol = self.cur_vol = 0
        self.period = self.out_period = 0x100
        self.transpose = self.flags = 0
        self.mod = [0] * 15
        self.vdelay, self.vcount, self.pdelay, self.pcount = [0, 0], [0, 0], [0, 0, 0], [0, 0, 0]
        self.vsum = self.psum = 0
        self.ins = drv.ins[0]
        self.trigger = self.stop = False
        self.restarts = 0                           # times the program began again
        self.used = []                              # instruments played
        if not BASE <= self.pc < BASE + len(drv.img): self.pc = None

    def _restart_vol(self):
        self.vdelay, self.vcount = self.mod[10:12], self.mod[0:2]
    def _restart_pitch(self):
        self.pdelay, self.pcount = self.mod[12:15], self.mod[2:5]

    def step(self):
        d = self.d
        self.trigger = self.stop = False
        if self.pc is None: return
        if self.dur == 0:
            if self.ins['loop'] == 0: self.stop = True          # the note is over (a sample with a loop point plays on)
            while True:
                c = d.byte(self.pc); self.pc += 1
                arg = d.byte(self.pc)
                if c < 0x80:                                    # a note
                    self.stop = True
                    self.period = d.word(self.ins['ptab'] + 2 * (c * 4 + self.transpose))
                    self.trigger = True
                    self.used.append(d.ins.index(self.ins))
                    self._restart_vol(); self._restart_pitch(); self.vsum = self.psum = 0
                    break
                if c == 0x90: break                             # a rest
                if c == 0xac:                                   # the end
                    self.pc = None; self.stop = True; return
                if c == 0x80: self.vol = arg; self.pc += 1
                elif c in SKIP1: self.pc += 1
                elif c == 0x88: self.pc = self.start; self.restarts += 1
                elif c == 0x8c: self.reload = arg * self.tempo[0]; self.pc += 1
                elif c == 0x94: self.tempo[0] = 750 // arg; self.pc += 1
                elif c == 0x98:
                    self.reload = sum(d.mem(self.pc + 1, arg)) * self.tempo[0]; self.pc += 1 + arg
                elif c == 0x9c:
                    self.flags &= 0xfc
                    self.mod = [b - 256 if b > 127 else b for b in d.mem(MODS + d.dc + 15 * arg, 15)]
                    self.vdelay, self.vcount, self.pdelay, self.pcount = [0, 0], [0, 0], [0, 0, 0], [0, 0, 0]
                    self.vsum = self.psum = 0; self.pc += 1
                elif c == 0xa8: self.flags |= arg; self.pc += 1
                elif c == 0xb0: self.stack.append(self.pc + 1); self.pc = d.start(arg)
                elif c == 0xb4: self.pc = self.stack.pop()
                elif c == 0xb8: self.transpose = 0 if arg == 0 else self.transpose + (arg - 256 if arg > 127 else arg); self.pc += 1
                elif c == 0xbc: self.transpose = arg - 256 if arg > 127 else arg; self.pc += 1
                elif c == 0xc0: self.pc += 1; self.stack.append([self.pc if arg else 0, arg])
                elif c == 0xc4:
                    top = self.stack[-1]
                    if top[0]:
                        self.pc = top[0]; top[1] -= 1
                        if top[1] == 0: top[0] = 0
                    else: self.stack.pop()
                elif c == 0xd0: self.ins = d.ins[arg]; self.pc += 1
                elif c == 0xd4:
                    self.pc = d.start(arg)
                else:
                    raise AudioError(f'sound program: command {c:02x} at {self.pc - 1:06x} is not one this tool knows')
            self.dur = self.reload
        self.dur = (self.dur - 1) & 0xffff
        # modulation presets: two volume stages and three pitch stages, each (delay, count, change)
        for i in range(2):
            if self.vdelay[i]: self.vdelay[i] = (self.vdelay[i] - 1) & 0xffff; break
            if self.vcount[i]:
                self.vcount[i] = (self.vcount[i] - 1) & 0xffff; self.vsum += self.mod[5 + i]; self.vdelay[i] = self.mod[10 + i] & 0xffff; break
        else:
            self.vsum = 0
            if self.flags & 1: self._restart_vol()
        for i in range(3):
            if self.pdelay[i]: self.pdelay[i] = (self.pdelay[i] - 1) & 0xffff; break
            if self.pcount[i]:
                self.pcount[i] = (self.pcount[i] - 1) & 0xffff; self.psum += self.mod[7 + i]; self.pdelay[i] = self.mod[12 + i] & 0xffff; break
        else:
            if self.flags & 2: self._restart_pitch()
        self.cur_vol = (self.vol + self.vsum) & 0x3f
        self.out_period = (self.period + self.psum) & 0xffff

    @property
    def rate(self):
        """The sample rate Paula plays at now, in Hz."""
        return PAULA_CLOCK / max(self.out_period, 1)

def record(drv, program, loops=1, max_seconds=30.0):
    """A program as the driver plays it on one channel -> (steps, loops). A step is [frames, volume 0-63, sample rate
    in Hz, start]: start is an instrument's number where a note begins, -1 where the sound is cut, None otherwise.
    loops: the program begins again by itself (then the steps are `loops` times round)."""
    ch, steps, frame = Channel(drv, program, [0]), [], 0
    while frame < max_seconds * FRAME_HZ:
        ch.step(); frame += 1
        start = ch.used[-1] if ch.trigger else -1 if ch.stop else None
        if steps and start is None and steps[-1][1] == ch.cur_vol and steps[-1][2] == ch.rate: steps[-1][0] += 1
        else: steps.append([1, ch.cur_vol, ch.rate, start])
        if ch.pc is None or ch.restarts >= loops: break
    return steps, ch.pc is not None

class Replay:
    """Plays recorded steps (from record, or from the table in sound_programs.json) as a Channel plays its program.
    instruments: number -> dict(pcm, looped, loop)."""
    def __init__(self, steps, loops, instruments):
        self.steps, self.loops, self.instruments = steps, loops, instruments
        self.k = self.left = 0
        self.pc, self.restarts, self.used = 0, 0, []
        self.trigger = self.stop = False
        self.cur_vol, self.rate, self.ins = 0, 1.0, None

    def step(self):
        self.trigger = self.stop = False
        if self.k >= len(self.steps): return
        frames, vol, rate, start = self.steps[self.k]
        if self.left == 0:                              # the first frame of this step
            self.left, self.cur_vol, self.rate = frames, vol, rate
            if start is None: pass
            elif start < 0: self.stop = True
            else:
                self.trigger, self.ins = True, self.instruments[start]
                self.used.append(start)
        self.left -= 1
        if self.left == 0:
            self.k += 1
            if self.k == len(self.steps):
                if self.loops: self.restarts += 1
                else: self.pc = None

class Paula:
    """One Paula channel: plays 8-bit samples at clock / period, without smoothing between samples."""
    def __init__(self):
        self.pcm, self.pos, self.loop_from = None, 0.0, None

    def frame(self, ch, n):
        if ch.stop: self.pcm = None
        if ch.trigger:
            x = ch.ins
            self.pcm, self.pos = x['pcm'], 0.0
            self.loop_from = None if not x['looped'] else x['loop']     # the whole sample, or from the loop point
        out = np.zeros(n, dtype=np.float32)
        if self.pcm is None or len(self.pcm) == 0: return out
        step = ch.rate / RATE
        pos = self.pos + step * np.arange(n)
        size = len(self.pcm)
        if self.loop_from is None:
            live = pos < size
            out[live] = self.pcm[pos[live].astype(np.int64)]
            self.pos += step * n
            if self.pos >= size: self.pcm = None
        else:
            span = max(size - self.loop_from, 2)
            wrapped = np.where(pos < size, pos, self.loop_from + (pos - size) % span)
            out[:] = self.pcm[np.minimum(wrapped.astype(np.int64), size - 1)]
            end = self.pos + step * n
            self.pos = end if end < size else self.loop_from + (end - size) % span
        return out * (ch.cur_vol / 64.0)

def amiga_filter(x):
    """The Amiga 500's fixed output filter: one pole at about 4.9 kHz (applied to the whole sound at once)."""
    spectrum = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / RATE)
    return np.fft.irfft(spectrum / (1 + 1j * f / 4900.0), len(x)).astype(np.float32)

def render(drv, programs, max_seconds=30.0, loops=1):
    """Play programs [(program, channel)] together -> (left, right, facts). A program that ends stops by itself; one
    that begins again is played `loops` times round (or max_seconds; some music parts start with a long silence)."""
    tempo = [0]
    return mix([(Channel(drv, p, tempo), Paula(), c) for p, c in programs], max_seconds, loops)

def play(steps, loops, instruments, max_seconds=30.0):
    """Recorded steps (record) played on one channel -> (left, right, facts), as render gives for the program."""
    return mix([(Replay(steps, loops, instruments), Paula(), 0)], max_seconds, 1)

def mix(chans, max_seconds, loops):
    """chans: [(Channel or Replay, Paula, Paula channel number)], stepped and played together."""
    left, right, frame, acc = [], [], 0, 0.0
    while frame < max_seconds * FRAME_HZ:
        acc += RATE / FRAME_HZ; n = int(acc); acc -= n
        l, r = np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)
        for ch, voice, c in chans:
            ch.step()
            y = voice.frame(ch, n)
            if c in LEFT: l += y
            else: r += y
        left.append(l); right.append(r); frame += 1
        if all(ch.pc is None and v.pcm is None for ch, v, _ in chans): break
        running = [ch for ch, _, _ in chans if ch.pc is not None]
        if running and all(ch.restarts >= loops for ch in running): break
    facts = dict(seconds=frame / FRAME_HZ, loops=any(ch.pc is not None for ch, _, _ in chans),
                 instruments=sorted({i for ch, _, _ in chans for i in ch.used}))
    return np.concatenate(left), np.concatenate(right), facts

def write_wav(path, left, right=None, filtered=True):
    chans = [left] if right is None else [left, right]
    if filtered: chans = [amiga_filter(c) for c in chans]
    pcm = np.clip(np.stack(chans, axis=1) * 32767 * 0.9, -32768, 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(len(chans)); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm.tobytes())

def font_sound(steps, loops, instruments):
    """One program as its sound in the SoundFont (mono, RATE), or None if it is silent."""
    left, right, _ = play(steps, loops, instruments)
    x = amiga_filter(left + right)
    live = np.flatnonzero(np.abs(x) > 1e-4)
    if not len(live): return None
    x = x[:min(len(x), live[-1] + RATE // 20)]                  # no long silent tail
    x[-64:] *= np.linspace(1, 0, 64)
    return x * 0.95

def write_soundfont(instruments, programs, path):
    """Every effect program as one sound. programs: number -> (steps, loops), from record or from the table.
    A program that begins again by itself (fire, wind, a Balok's roar with the den after it) is played once round:
    nothing in the game stops such a loop yet, so it must end by itself. -> (sounds, seconds, programs left out as
    silent)."""
    sounds, total, silent = [], 0, []
    for p in FONT_PROGRAMS:
        x = font_sound(*programs[p], instruments) if p in programs else None
        if x is None:
            silent.append(p); continue
        preset, key = font_key(p)
        sounds.append((preset, key, f'program {p}', x, RATE, None)); total += len(x)
    soundfont.write(path, sounds, 'Moonstone', cut=True)
    return len(sounds), total / RATE, silent

# --- without the Amiga disks: the same programs with the DOS game's samples -------------------------------------------
TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sound_programs.json')

def read_voc(path):
    """The sound of a Creative Voice file as signed 8-bit samples."""
    d = open(path, 'rb').read()
    if d[:19] != b'Creative Voice File': raise AudioError(f'{path} is not a Creative Voice file')
    i, pcm = struct.unpack('<H', d[20:22])[0], bytearray()
    while i < len(d) and d[i] != 0:
        kind, n = d[i], d[i + 1] | d[i + 2] << 8 | d[i + 3] << 16
        if kind == 1: pcm += d[i + 6:i + 4 + n]
        elif kind == 2: pcm += d[i + 4:i + 4 + n]
        i += 4 + n
    return (np.frombuffer(bytes(pcm), dtype=np.uint8).astype(np.int16) - 128).astype(np.float32) / 128.0

def read_wav8(path):
    """A mono WAV file (8 or 16 bits) as samples in -1..1."""
    with wave.open(path, 'rb') as w:
        if w.getnchannels() != 1: raise AudioError(f'{path} is not mono')
        d, width = w.readframes(w.getnframes()), w.getsampwidth()
    if width == 1: return (np.frombuffer(d, dtype=np.uint8).astype(np.int16) - 128).astype(np.float32) / 128.0
    if width == 2: return np.frombuffer(d, dtype='<i2').astype(np.float32) / 32768.0
    raise AudioError(f'{path}: {8 * width}-bit samples are not supported')

def read_table(path=TABLE):
    """sound_programs.json -> (instruments' sources, programs: number -> (steps, loops))."""
    t = json.load(open(path, encoding='utf-8'))
    return t['instruments'], {int(p): (x['steps'], x['loops']) for p, x in t['programs'].items()}

def dos_instruments(sources, samples, sounds):
    """The instruments of the table from the DOS game's SAMPLES folder and the substitute sounds: number -> dict(pcm,
    looped, loop). An instrument is a part (at, n) of a DOS sample ('dos') or of a substitute file ('file'); one with
    neither is silent."""
    out, files = {}, {}
    for k, x in sources.items():
        where = os.path.join(samples, x['dos']) if 'dos' in x else os.path.join(sounds, x['file']) if 'file' in x else None
        if where is None:
            pcm = np.zeros(0, dtype=np.float32)
        else:
            if where not in files:
                if not os.path.exists(where): raise AudioError(f'{where} is missing')
                files[where] = read_voc(where) if 'dos' in x else read_wav8(where)
            pcm = files[where][x['at']:x['at'] + x['n']]
            if len(pcm) != x['n']:
                raise AudioError(f'{where} is not the file this tool knows (it has {len(files[where])} samples)')
        out[int(k)] = dict(pcm=pcm, looped='loop' in x, loop=x.get('loop', 0))
    return out

def build_soundfont(install, font):
    """The effects' SoundFont for an installation: from the user's three Amiga disk images in <install>/amiga if they
    are there, else from the DOS game's samples (<install>/SAMPLES), the substitute sounds (<install>/sounds) and
    the table of programs. -> a line saying what was built."""
    amiga = os.path.join(install, 'amiga')
    os.makedirs(os.path.dirname(os.path.abspath(font)), exist_ok=True)
    if len(glob.glob(os.path.join(amiga, '*.[aA][dD][fF]'))) >= 3:
        drv = Driver(read_disks(amiga))
        n, seconds, silent = write_soundfont(drv.ins, {p: record(drv, p) for p in FONT_PROGRAMS}, font)
        source = 'from your Amiga disks' + ('' if drv.verified else ' (mog is not the known file)')
    else:
        sources, programs = read_table()
        instruments = dos_instruments(sources, os.path.join(install, 'SAMPLES'), os.path.join(install, 'sounds'))
        n, seconds, silent = write_soundfont(instruments, programs, font)
        source = 'from the DOS samples and the substitute sounds (no Amiga disks in the amiga folder)'
    return f'{n} sounds, {seconds:.0f} s, {os.path.getsize(font) / 1e6:.1f} MB, {source}'

def main(folder, out, what='wav'):
    if what == 'soundfont':                                     # folder: the three .adf files
        drv = Driver(read_disks(folder))
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        n, seconds, _ = write_soundfont(drv.ins, {p: record(drv, p) for p in FONT_PROGRAMS}, out)
        print(f'{out}: {n} sounds, {seconds:.0f} s, {os.path.getsize(out) / 1e6:.1f} MB' + ('' if drv.verified else ' (mog is not the known file)'))
        return
    if what == 'install':                                       # folder: the installation
        print(f'{out}: ' + build_soundfont(folder, out))
        return
    drv = Driver(read_disks(folder))
    print('mog: ' + ('the known file' if drv.verified else 'another dump (the driver was found by its signature; not verified)'))
    os.makedirs(out, exist_ok=True)
    rows, silent = [], []
    for p in range(1, PROGRAMS + 1):
        left, right, facts = render(drv, [(p, 0)])
        mono = left + right
        if not facts['instruments'] or not np.any(mono):
            silent.append(p)
        write_wav(os.path.join(out, f's{p:03d}.wav'), mono)
        what = ', '.join(dict.fromkeys(f'{drv.ins[i]["bank"]}.a {drv.name[i]}' for i in facts['instruments'])) or 'silence'
        rows.append((f's{p:03d}.wav', f'{p}', what, facts))
    for name, (what, progs) in MIXES.items():
        left, right, facts = render(drv, progs, loops=2)
        # each channel mostly on its own side with a little on the other: full left and right is tiring on headphones
        write_wav(os.path.join(out, f'mix_{name}.wav'), 0.75 * left + 0.25 * right, 0.25 * left + 0.75 * right)
        rows.append((f'mix_{name}.wav', '+'.join(str(p) for p, _ in progs), what, facts))
    page = ['<!doctype html><meta charset="utf-8"><title>Amiga Moonstone sound programs</title>',
            '<style>body{font:14px sans-serif;margin:16px;max-width:1100px}td,th{padding:3px 8px;text-align:left;'
            'border-bottom:1px solid #8884}audio{height:28px;width:260px}</style>',
            '<h1>Amiga Moonstone sound programs</h1><p>Rendered from your own Amiga disk images. For this machine only: '
            'do not share these files.</p><table><tr><th>Program</th><th>Samples</th><th>Length</th><th></th></tr>']
    for fname, prog, what, facts in rows:
        length = f'{facts["seconds"]:.2f} s' + (' (loops)' if facts['loops'] else '')
        page.append(f'<tr><td>{html.escape(prog)}</td><td>{html.escape(what)}</td><td>{length}</td>'
                    f'<td><audio controls preload="none" src="{fname}"></audio></td></tr>')
    page.append('</table>')
    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(page))
    print(f'{PROGRAMS} programs and {len(MIXES)} mixes written to {out}; silent programs: {silent}')

if __name__ == '__main__':
    try:
        main(*sys.argv[1:4])
    except AudioError as e:
        raise SystemExit(f'make_amiga_audio: {e}')
