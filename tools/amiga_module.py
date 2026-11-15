"""Play the Amiga intro and ending tunes of Moonstone as the Amiga game itself does (phase 5 of the Amiga audio work).

The two tunes are 4-channel modules (music.cmp and vmusic.cmp on Amiga disk 1, tag FLT4). The Amiga's intro and
ending program (`program` on disk 1) plays them with a NoiseTracker-type routine, called once a frame (50 a second).
This file reads a module and steps it exactly as that routine does, tick by tick, and gives what each of the four
Paula channels plays in each tick. make_amiga_audio.py turns that into sound (its Paula class) for the SoundFont.

How the routine differs from the players of today (all of it followed here):
 * commands 0 (arpeggio), 1, 2 (slide up, down), 3 (slide to a note), 4 (vibrato), A (volume slide), B (jump),
   C (volume), D (break) and F (speed); E and the others do nothing;
 * D ignores its parameter: the next pattern always starts at its first row. B and D toggle one flag, so two of
   them on one row cancel each other;
 * F is the speed only (parameter and 1Fh, 0 ignored): there is no tempo, a tick is always a 50th of a second;
 * C writes the volume register only: a volume slide after it goes on from the sample's volume (or from where the
   last slide left it), not from C's value;
 * a looped sample plays from its start to its loop's end and then the loop; the part after the loop is never heard.
   A sample without a loop plays whole, then its first two bytes for ever, which the routine clears at the start
   (the first four bytes of every sample are cleared);
 * the first row is played on the sixth tick; at the end of the order list the tune goes back to its first order.

Nothing of the Amiga game is in this file: the modules and the routine's table of periods (used by the arpeggio
only) are read from the user's own disk image. A table of the same kind can be made with equal_periods() for tests.
The checksum below only recognises the table."""
import os, glob, math, struct, hashlib

TICK_HZ = 50
PAULA_CLOCK = 3546895                              # PAL: a channel plays clock / period samples a second
MODULES = {'music.cmp': 'intro', 'vmusic.cmp': 'ending'}
PROGRAM = 'program'                                # the Amiga's intro and ending program, with the player
PERIOD_WORDS = 37                                  # 36 periods and a 0 that ends the arpeggio's search
PERIODS_SHA = 'd8044d03c906e574d5c18d058e4936297af0cc8be3b26a470b27958b3914fea9'    # SHA-256 of the table's 74 bytes
PREFERRED = 'Moonstone_Disk1.adf'                  # the name the Moonstone Rebuilt instructions ask for
# In the SoundFont: each tune is a left and a right sample (Paula channels 0+3 and 1+2), keys of preset 3 in the
# Amiga bank, played on two MIDI channels nobody else uses (the GM tunes 0-9, the location music 4-7, effects 12-15)
TUNE_PRESET = 3
TUNE_KEYS = {'intro': (40, 41), 'ending': (42, 43)}            # (left, right)
TUNE_CHANNELS = (10, 11)
# The level. An effect is one Paula channel at 0.95 of full scale in the font, played at MIDI volume 100. A tune's
# side is two channels summed (peaks of 1.29 channels were measured), so each is 0.75 in the font and the tune
# module sets MIDI volume 113 on its two channels: 2.1 dB up in FluidSynth (40 log10(113 / 100)), 0.96 in all.
TUNE_LEVEL, TUNE_VOLUME = 0.75, 113
# The pans: three quarters of the full width (0 and 127 are hard left and right, 64 the middle)
TUNE_PANS = (16, 111)
VIBRATO = [int(255 * math.sin(math.pi * i / 32)) for i in range(32)]     # the vibrato's half wave

class ModuleError(Exception):
    pass

def equal_periods(top=856):
    """A table of periods in equal temperament (36 notes down from `top`, then 0), for tests: the shape of the
    routine's own table, made from a formula."""
    return [int(round(top / 2 ** (n / 12))) for n in range(PERIOD_WORDS - 1)] + [0]

def find_periods(program):
    """The player's table of periods in the Amiga `program` file (found by its checksum, so no table is kept here)
    -> list of words, or None."""
    for at in range(0, len(program) - 2 * PERIOD_WORDS, 2):
        if program[at + 2 * PERIOD_WORDS - 2:at + 2 * PERIOD_WORDS] == b'\0\0' and \
                hashlib.sha256(program[at:at + 2 * PERIOD_WORDS]).hexdigest() == PERIODS_SHA:
            return list(struct.unpack(f'>{PERIOD_WORDS}H', program[at:at + 2 * PERIOD_WORDS]))
    return None

def read_disk(folder):
    """The tunes on the Amiga disk 1 among the .adf files of a folder -> (image path, {'intro': module, 'ending':
    module}, table of periods), or None if no image has the three files. The table is None if `program` is not the
    known one."""
    from adf import Adf
    from rnc import unrnc
    paths = sorted(set(glob.glob(os.path.join(folder, '*.adf')) + glob.glob(os.path.join(folder, '*.ADF'))))
    paths.sort(key=lambda p: os.path.basename(p).lower() != PREFERRED.lower())
    for path in paths:
        try:
            adf = Adf(path)
            files = {p.lower(): h for p, h in adf.walk()}
            if all(name in files for name in MODULES):
                modules = {MODULES[name]: unrnc(adf.read(files[name])) for name in MODULES}
                periods = find_periods(adf.read(files[PROGRAM])) if PROGRAM in files else None
                return path, modules, periods
        except ValueError as e:                             # not a disk, or a damaged one: try the next image
            print(f'  {os.path.basename(path)}: {e}')
    return None

class Module:
    """A module's header, patterns and sample memory as the routine sees them after its start."""
    def __init__(self, data):
        if len(data) < 1084 + 1024:
            raise ModuleError('not a module (too short)')
        self.title = data[:20].split(b'\0')[0].decode('latin-1')
        self.tag = data[1080:1084]
        self.songlen = data[950]
        self.orders = data[952:952 + 128]
        patterns = max(self.orders[:127]) + 1               # the routine looks at 127 entries of the table
        self.patterns = data[1084:1084 + 1024 * patterns]
        mem = bytearray(data[1084 + 1024 * patterns:])
        self.samples, at = [], 0
        for i in range(31):
            words, fine_vol, loop, replen = struct.unpack('>HHHH', data[42 + 30 * i:50 + 30 * i])
            self.samples.append(dict(start=at, words=words, vol=fine_vol, loop=loop, replen=replen))
            mem[at:at + 4] = bytes(min(4, max(0, len(mem) - at)))       # the routine clears each sample's first long
            at += 2 * words
        self.size = at                                      # the samples' bytes, by the header
        self.mem = bytes(mem)

class Voice:
    """One of the routine's four channels and the Paula registers it writes. After each tick: `trigger` (a note
    starts: the channel plays `ins` from its start), `period` and `volume` (the registers; see rate and level)."""
    def __init__(self):
        self.note = bytearray(4)
        self.start = self.words = self.loop_at = self.replen = 0       # the sample: offsets in bytes, lengths in words
        self.per = self.vol = 0                             # the routine's own period and volume words
        self.down = self.slide = self.wanted = 0            # slide to a note: direction, speed, target
        self.vib = self.vib_pos = 0
        self.period = self.volume = 0                       # the registers
        self.trigger, self.ins = False, None
        self.sounding = None                                # (loop offset, loop words) the channel was started with

    @property
    def rate(self):
        """Samples a second (0 = period register 0, never written by the two tunes)."""
        return PAULA_CLOCK / self.period if self.period else 0.0

    @property
    def level(self):
        """The volume as Paula takes it: bits 0-6 of the register, 64 at most."""
        return min(self.volume & 0x7f, 64)

def _signed(word):
    return word - 0x10000 if word & 0x8000 else word

class Player:
    """The routine's state. tick() is one call of it (one frame). `unmodelled` collects what this model does not
    play as an Amiga would (none of it happens in the two tunes)."""
    def __init__(self, module, periods):
        self.mod = module if isinstance(module, Module) else Module(module)
        self.periods = list(periods) + [0] * 16             # the arpeggio can read 15 words past the table
        self.speed, self.order, self.row16, self.counter, self.brk = 6, 0, 0, 0, 0
        self.voices = [Voice() for _ in range(4)]
        self.new_row = False                                # this tick read a row
        self.row_at = None                                  # (order, row) of the row this tick read
        self.unmodelled = []

    def tick(self):
        for v in self.voices: v.trigger = False
        self.new_row, self.row_at = False, None
        self.counter = (self.counter + 1) & 0xff
        if self.counter < self.speed:
            for v in self.voices: self._effect(v)
        else:
            self.counter = 0
            self._row()
        while self.brk: self._next_order()

    def _next_order(self):
        self.row16 = self.brk = 0
        self.order = (self.order + 1) & 0x7f
        if self.order == self.mod.songlen: self.order = 0

    def _row(self):
        mod = self.mod
        self.new_row, self.row_at = True, (self.order, self.row16 // 16)
        at = mod.orders[self.order] * 1024 + self.row16
        if at + 16 > len(mod.patterns): raise ModuleError(f'order {self.order} is past the patterns')
        for k, v in enumerate(self.voices):
            v.note[:] = mod.patterns[at + 4 * k:at + 4 * k + 4]
            number = (v.note[2] >> 4) | (v.note[0] & 0xf0)
            if number:
                if number > 31: raise ModuleError(f'sample {number} at order {self.order}')
                s = mod.samples[number - 1]
                v.start, v.words, v.vol = s['start'], s['words'], s['vol']
                if s['loop']:
                    v.loop_at = v.start + ((2 * s['loop']) & 0xffff)
                    v.words = (s['loop'] + s['replen']) & 0xffff
                else:
                    v.loop_at = v.start
                v.replen = s['replen']
                v.volume = v.vol
            started = False
            if (v.note[0] << 8 | v.note[1]) & 0xfff:
                if v.note[2] & 0xf == 3:
                    v.wanted = (v.note[0] << 8 | v.note[1]) & 0xfff
                    v.down = 0
                    if v.wanted == v.per: v.wanted = 0
                    elif _signed(v.wanted) < _signed(v.per): v.down = 1
                else:
                    v.per = v.period = (v.note[0] << 8 | v.note[1]) & 0xfff
                    v.vib_pos = 0
                    v.trigger = started = True
            command, par = v.note[2] & 0xf, v.note[3]
            if command == 0xd:
                self.brk ^= 0xff
            elif command == 0xb:
                self.order = (par - 1) & 0xff
                self.brk ^= 0xff
            elif command == 0xc:
                if 0x40 < par < 0x80: par = v.note[3] = 0x40
                v.volume = par << 8 | par                   # a byte write: both halves of the register get it
            elif command == 0xf and par & 0x1f:
                self.counter, self.speed = 0, par & 0x1f
            # after the four channels the routine writes each one's loop to Paula, which takes it when the sample
            # it is playing ends
            loop = (v.loop_at, v.replen)
            if started:
                v.ins, v.sounding = (v.start, v.words, v.loop_at, v.replen), loop
            elif v.sounding is not None and loop != v.sounding:
                self.unmodelled.append(f'order {self.order} row {self.row16 // 16} channel {k}: another sample\'s '
                                       'loop is set while a sample plays')
                v.sounding = loop
        self.row16 += 16
        if self.row16 == 0x400: self._next_order()

    def _effect(self, v):
        command, par = v.note[2] & 0xf, v.note[3]
        if command == 0 and par == 0:
            v.period = v.per
        elif command == 0:
            step = self.counter % 3
            if step == 0:
                v.period = v.per
            else:
                offset = par >> 4 if step == 1 else par & 0xf
                for i in range(PERIOD_WORDS):
                    if _signed(v.per) >= _signed(self.periods[i]):
                        if i + offset >= PERIOD_WORDS - 1:
                            self.unmodelled.append(f'arpeggio past the table of periods (period {v.per}, +{offset})')
                        v.period = self.periods[i + offset]
                        break
        elif command == 1:
            v.per = (v.per - par) & 0xffff
            if v.per & 0xfff < 0x71: v.per = (v.per & 0xf000) | 0x71
            v.period = v.per & 0xfff
        elif command == 2:
            v.per = (v.per + par) & 0xffff
            if v.per & 0xfff >= 0x358: v.per = (v.per & 0xf000) | 0x358
            v.period = v.per & 0xfff
        elif command == 3:
            if par:
                v.slide, v.note[3] = par, 0
            if v.wanted:
                if v.down:
                    v.per = (v.per - v.slide) & 0xffff
                    if not _signed(v.wanted) < _signed(v.per): v.per, v.wanted = v.wanted, 0
                else:
                    v.per = (v.per + v.slide) & 0xffff
                    if not _signed(v.wanted) > _signed(v.per): v.per, v.wanted = v.wanted, 0
                v.period = v.per
        elif command == 4:
            if par: v.vib = par
            swing = (VIBRATO[(v.vib_pos >> 2) & 0x1f] * (v.vib & 0xf)) >> 6
            v.period = (v.per - swing if v.vib_pos & 0x80 else v.per + swing) & 0xffff
            v.vib_pos = (v.vib_pos + ((v.vib >> 2) & 0x3c)) & 0xff
        else:
            v.period = v.per
            if command == 0xa:
                if par >> 4:
                    v.vol = (v.vol + (par >> 4)) & 0xffff
                    if _signed((v.vol - 0x40) & 0xffff) >= 0: v.vol = 0x40
                else:
                    v.vol = (v.vol - (par & 0xf)) & 0xffff
                    if v.vol & 0x8000: v.vol = 0
                v.volume = v.vol

def play_through(module, periods, max_seconds=3600):
    """Step the tune from its first row until a row comes again -> (ticks: one list per tick of four (trigger,
    instrument, period register, volume 0-64), loop tick, rows: [(tick, order, row)], player). Tick 0 is the tick
    of the first row (the routine's sixth call). The tune plays ticks[0:], then ticks[loop tick:] for ever. An
    instrument is (start byte, words, loop's start byte, loop's words) in the module's sample memory."""
    p = Player(module, periods)
    ticks, rows, seen = [], [], {}
    for _ in range(5): p.tick()                             # the five ticks before the first row: nothing sounds
    while len(ticks) < max_seconds * TICK_HZ:
        key = (p.order, p.row16, p.speed) if p.counter + 1 >= p.speed else None     # the next tick reads a row
        if key is not None:
            if key in seen: return ticks, seen[key], rows, p
            seen[key] = len(ticks)
        p.tick()
        if p.new_row: rows.append((len(ticks),) + p.row_at)
        ticks.append([(v.trigger, v.ins, v.period, v.level) for v in p.voices])
    raise ModuleError(f'the tune does not come round in {max_seconds} s')

def _period_sha():
    """python -I tools/amiga_module.py <folder with the .adf files>: say what is on disk 1 (numbers only)."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    found = read_disk(sys.argv[1])
    if not found: raise SystemExit('no disk 1 there')
    path, modules, periods = found
    print(f'{os.path.basename(path)}: table of periods ' + ('found' if periods else 'NOT found'))
    for name, data in modules.items():
        ticks, loop, rows, p = play_through(data, periods or equal_periods())
        print(f'  {name}: {len(data)} bytes, {len(rows)} rows, {len(ticks)} ticks = {len(ticks) / TICK_HZ:.2f} s, '
              f'comes round to tick {loop}; not modelled: {sorted(set(p.unmodelled)) or "nothing"}')

if __name__ == '__main__':
    _period_sha()
