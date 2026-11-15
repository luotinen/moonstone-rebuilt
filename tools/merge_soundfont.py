"""Merge two SoundFont 2 files into one: a General MIDI font and the Amiga font (or any second font).

DOSBox-X's `synth` MIDI device (FluidSynth 1.1.6) loads one SoundFont. With GM music and the Amiga effects on
together it needs the GM font's presets and the Amiga ones in one file. The Amiga presets are in their own bank
(soundfont.AMIGA_BANK, 100), so they do not collide with the GM programs of bank 0.

How the merge works:
* The second font's sample data goes after the first font's, with 46 zero samples between them (the SoundFont
  2.01 spec asks for at least 46 after every sample). Every sample header of the second font moves by that offset,
  and its stereo link index by the first font's sample count.
* The presets, instruments, bags, generators and modulators are decoded into lists and written again, so every index
  is rebased: a second-font instrument generator `sampleID` and preset generator `instrument` move by the first
  font's counts. A first-font preset with the same bank and program as a second-font one is dropped, with its
  bags (its instrument stays, unused). Each list ends with one terminal record.
* Every first-font preset gets `attenuation` centibels more (GM_ATTENUATION by default), in its global zone (one is
  added if it has none), so that the GM music and the effects share one mixer level.
* The INFO chunk is the first font's, so its name, engineer and copyright fields are kept; a comment on the merge is
  added (ICMT, appended to the first font's comment).
* SF3 (compressed samples) and 24-bit (sm24) fonts are refused, and so is a result over the 16-bit index limits.

An installation's merged font, _music/amiga/amiga_gm.sf2 (update_install, --install): from soundfonts/default.sf2
(the user's own) or soundfonts/GeneralUser-GS.sf2 (shipped) and _music/amiga/amiga.sf2, made again only when one of
them changed (amiga_gm.sf2.inputs). It holds the user's own data (the DOS game's samples, the Amiga disks' with the
disk build): it is made on the user's machine and never distributed.
Usage: python -I tools/merge_soundfont.py <gm.sf2> <second.sf2> <out.sf2>
       python -I tools/merge_soundfont.py --install <installation folder>"""
import os, struct, sys

INSTRUMENT, SAMPLE_ID = 41, 53                   # generators that hold an index (SoundFont 2.01, 8.1.2)
ATTENUATION = 48                                 # initialAttenuation, in centibels; a preset's value adds to the instrument's
# D82: every first-font (GM) preset is attenuated by this much, in centibels: at the SYNTH mixer level of the Amiga
# effects (600) GeneralUser's music clipped (research/sf2_spike/make_spike11.py: tune 1 peaked at 1.77 of full
# scale). 6 dB is what the user chose by ear (14 Nov 2026) from tune 1 with the menu clicks and blows. FluidSynth
# (1.1.6 in DOSBox-X, as the EMU cards) takes 0.4 of a generator's attenuation, so 6 dB is 150 "centibels" here:
# tune 1 measured 2.40 dB quieter with 60 and 6.00 dB with 150 (research/sf2_spike/att_probe.py).
GM_ATTENUATION = 150
PAD = 46                                         # zero samples after each sample's data
LIMIT = 0xffff                                   # bag, generator and modulator indices are WORDs

class Font:
    def __init__(self, path):
        data = open(path, 'rb').read()
        if data[:4] != b'RIFF' or data[8:12] != b'sfbk':
            raise ValueError(f'{path}: not a SoundFont 2 file')
        self.path, self.chunks = path, {}
        self._walk(data, 12, 8 + struct.unpack_from('<I', data, 4)[0])
        self.info = self.chunks.pop('INFO')
        ifil = dict(self.info).get(b'ifil', b'')
        if len(ifil) < 4 or struct.unpack_from('<H', ifil)[0] != 2:
            raise ValueError(f'{path}: version {struct.unpack_from("<H", ifil)[0] if len(ifil) >= 2 else "?"} '
                             f'(SF3 or unknown); only SoundFont 2 can be merged')
        if 'sm24' in self.chunks:
            raise ValueError(f'{path}: 24-bit samples (sm24) are not supported')
        self.smpl = self.chunks.get('smpl', b'')
        self.samples = [list(struct.unpack_from('<20sIIIIIBbHH', self.chunks['shdr'], o))
                        for o in range(0, len(self.chunks['shdr']) - 46, 46)]
        if any(s[9] & 0x10 for s in self.samples):
            raise ValueError(f'{path}: compressed samples (SF3); only SoundFont 2 can be merged')
        self.presets = self._zones('phdr', 38, '<20sHHHIII', 3, 'pbag', 'pgen', 'pmod')
        self.instruments = self._zones('inst', 22, '<20sH', 1, 'ibag', 'igen', 'imod')

    def _walk(self, data, o, end, in_info=False):
        while o + 8 <= end:
            tag, n = data[o:o + 4], struct.unpack_from('<I', data, o + 4)[0]
            if tag == b'LIST':
                kind = data[o + 8:o + 12]
                if kind == b'INFO':
                    self.chunks['INFO'] = []
                    self._walk(data, o + 12, o + 8 + n, True)
                else:
                    self._walk(data, o + 12, o + 8 + n)
            elif in_info:
                self.chunks['INFO'].append((tag, data[o + 8:o + 8 + n]))
            else:
                self.chunks[tag.decode('latin-1')] = data[o + 8:o + 8 + n]
            o += 8 + n + (n & 1)

    def _zones(self, hdr, size, fmt, bag_field, bag, gen, mod):
        """[(header fields, [(generators [(oper, amount)], modulators [10-byte records])])], terminal dropped."""
        h, b, g, m = (self.chunks[k] for k in (hdr, bag, gen, mod))
        heads = [list(struct.unpack_from(fmt, h, o)) for o in range(0, len(h) - size + 1, size)]
        bags = [struct.unpack_from('<HH', b, o) for o in range(0, len(b) - 3, 4)]
        gens = [struct.unpack_from('<HH', g, o) for o in range(0, len(g) - 3, 4)]
        mods = [m[o:o + 10] for o in range(0, len(m) - 9, 10)]
        out = []
        for i in range(len(heads) - 1):
            zones = []
            for z in range(heads[i][bag_field], heads[i + 1][bag_field]):
                (g0, m0), (g1, m1) = bags[z], bags[z + 1]
                zones.append((list(gens[g0:g1]), list(mods[m0:m1])))
            out.append((heads[i], zones))
        return out

def _chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'')

def _list(kind, *chunks):
    return _chunk(b'LIST', kind + b''.join(chunks))

def _even_text(text):
    """A zero-terminated string (bytes) padded to an even length (FluidSynth 1.1.6 refuses odd INFO chunk sizes)."""
    b = text.rstrip(b'\0') + b'\0'
    return b + (b'\0' if len(b) % 2 else b'')

def _encode(items, fmt, bag_field, name):
    """Header, bag, generator and modulator chunks of presets or instruments (each list with its terminal)."""
    heads, bags, gens, mods = bytearray(), bytearray(), bytearray(), bytearray()
    nbag = ngen = nmod = 0
    for fields, zones in items:
        fields = list(fields); fields[bag_field] = nbag
        heads += struct.pack(fmt, *fields)
        for g, m in zones:
            bags += struct.pack('<HH', ngen, nmod)
            for oper, amount in g:
                gens += struct.pack('<HH', oper, amount)
            for rec in m:
                mods += rec
            nbag, ngen, nmod = nbag + 1, ngen + len(g), nmod + len(m)
    for count, what in ((nbag, 'bags'), (ngen, 'generators'), (nmod, 'modulators')):
        if count > LIMIT:
            raise ValueError(f'the merged font has {count} {name} {what}; the limit is {LIMIT}')
    terminal = [b'EOP' if name == 'preset' else b'EOI'] + [0] * (len(fmt) - 4)   # '<20s' + one letter a field
    terminal[bag_field] = nbag
    heads += struct.pack(fmt, *terminal)
    bags += struct.pack('<HH', ngen, nmod)
    gens += bytes(4); mods += bytes(10)
    return bytes(heads), bytes(bags), bytes(mods), bytes(gens)

def _raised(gens, cb):
    """Generators with their attenuation (a signed amount) raised by cb, at most 1440 cB."""
    def up(v):
        v = v - 0x10000 if v >= 0x8000 else v
        return min(1440, v + cb) & 0xffff
    return [(o, up(v) if o == ATTENUATION else v) for o, v in gens]

def attenuate(zones, cb):
    """A preset's zones with `cb` centibels more attenuation. A preset zone's own attenuation replaces the global
    zone's (SoundFont 2.01, 9.6; FluidSynth does so), so it goes up in both: in the global zone (the first zone,
    when it has no instrument; one is added if there is none) and in every zone that has its own."""
    if not cb:
        return zones
    if zones and all(o != INSTRUMENT for o, _ in zones[0][0]):
        (g, m), local = zones[0], zones[1:]
    else:
        (g, m), local = ([], []), zones
    g = _raised(g, cb) if any(o == ATTENUATION for o, _ in g) else g + [(ATTENUATION, cb)]
    return [(g, m)] + [(_raised(lg, cb), lm) for lg, lm in local]

def merge(first, second, out, attenuation=GM_ATTENUATION):
    a, b = Font(first), Font(second)
    shift = len(a.smpl) // 2 + PAD                 # where the second font's samples begin, in samples
    nsamples, ninst = len(a.samples), len(a.instruments)
    samples = [list(s) for s in a.samples]
    for s in b.samples:
        s = list(s)
        s[1:5] = [v + shift for v in s[1:5]]       # start, end, loop start, loop end
        if s[9] & 0x0e:                            # right, left or linked: the link is a sample index
            s[8] += nsamples
        samples.append(s)
    def rebase(zones, oper_of_index, by):
        return [([(o, v + by if o == oper_of_index else v) for o, v in g], m) for g, m in zones]
    instruments = a.instruments + [(h, rebase(z, SAMPLE_ID, nsamples)) for h, z in b.instruments]
    taken = {(h[2], h[1]) for h, _ in b.presets}   # (bank, program)
    dropped = [h for h, _ in a.presets if (h[2], h[1]) in taken]
    presets = [(h, attenuate(z, attenuation)) for h, z in a.presets if (h[2], h[1]) not in taken]
    presets += [(h, rebase(z, INSTRUMENT, ninst)) for h, z in b.presets]
    phdr, pbag, pmod, pgen = _encode(presets, '<20sHHHIII', 3, 'preset')
    inst, ibag, imod, igen = _encode(instruments, '<20sH', 1, 'instrument')
    if len(samples) > LIMIT:
        raise ValueError(f'the merged font has {len(samples)} samples; the limit is {LIMIT}')
    shdr = b''.join(struct.pack('<20sIIIIIBbHH', *s) for s in samples) + b'EOS'.ljust(20, b'\0') + bytes(26)
    note = (f'Merged on this machine by Moonstone Rebuilt (tools/merge_soundfont.py) from '
            f'{os.path.basename(first)} and {os.path.basename(second)}: the second font\'s presets added '
            f'(banks {", ".join(str(v) for v in sorted({h[2] for h, _ in b.presets}))}), the first font\'s '
            f'attenuated by {attenuation / 10:g} dB. Not for distribution.')
    info = []
    for tag, data in a.info:
        if tag == b'ICMT':
            data = _even_text(data.rstrip(b'\0') + b'\n\n' + note.encode('ascii'))
            note = None
        elif tag not in (b'ifil', b'iver'):           # the text fields, padded to an even size
            data = _even_text(data)
        info.append((tag, data))
    if note:
        info.append((b'ICMT', _even_text(note.encode('ascii'))))
    smpl = a.smpl + bytes(2 * PAD) + b.smpl
    body = (b'sfbk' + _list(b'INFO', *(_chunk(t, d) for t, d in info)) + _list(b'sdta', _chunk(b'smpl', smpl))
            + _list(b'pdta', _chunk(b'phdr', phdr), _chunk(b'pbag', pbag), _chunk(b'pmod', pmod),
                    _chunk(b'pgen', pgen), _chunk(b'inst', inst), _chunk(b'ibag', ibag), _chunk(b'imod', imod),
                    _chunk(b'igen', igen), _chunk(b'shdr', shdr)))
    tmp = out + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', len(body)) + body)
    os.replace(tmp, out)
    return {'presets': len(presets), 'dropped': len(dropped), 'instruments': len(instruments),
            'samples': len(samples), 'bytes': 8 + len(body)}

# D82: an installation's merged font. The GM font is the user's own soundfonts/default.sf2 if it is there, else the
# GeneralUser GS 2.0.3 that the release ships; the second font is the Amiga effects' _music/amiga/amiga.sf2.
GM_FONTS = (os.path.join('soundfonts', 'default.sf2'), os.path.join('soundfonts', 'GeneralUser-GS.sf2'))
AMIGA_FONT = os.path.join('_music', 'amiga', 'amiga.sf2')
MERGED = os.path.join('_music', 'amiga', 'amiga_gm.sf2')     # not "amiga.sf2" in its name: Start.bat looks for that
INPUTS = '.inputs'                                           # beside the merged font: what it was made from

def gm_font(install):
    """The GM font an installation uses (a path), or None."""
    return next((os.path.join(install, f) for f in GM_FONTS if os.path.exists(os.path.join(install, f))), None)

def update(first, second, out, attenuation=GM_ATTENUATION):
    """Merge again only if <out> is missing or was made from other files (names, sizes, times) or another
    attenuation. -> True if it was made now."""
    stamp = ''.join(line + '\n' for line in [f'attenuation {attenuation}'] +
                    [f'{os.path.basename(f)} {os.path.getsize(f)} {int(os.path.getmtime(f))}' for f in (first, second)])
    try:
        if os.path.exists(out) and open(out + INPUTS).read() == stamp:
            return False
    except OSError:
        pass
    merge(first, second, out, attenuation)
    with open(out + INPUTS, 'w') as f:
        f.write(stamp)
    return True

def update_install(install):
    """The installation's _music/amiga/amiga_gm.sf2, made or brought up to date. -> a line saying what was done."""
    gm, amiga = gm_font(install), os.path.join(install, AMIGA_FONT)
    if not gm or not os.path.exists(amiga):
        return 'not made: ' + ('no GM SoundFont in soundfonts' if not gm else 'the Amiga effects are not built')
    out = os.path.join(install, MERGED)
    made = update(gm, amiga, out)
    # D87: amiga_gm.tunes says the merged font has the intro and ending tunes, as amiga.tunes says of amiga.sf2
    marker, has = os.path.splitext(out)[0] + '.tunes', os.path.exists(os.path.splitext(amiga)[0] + '.tunes')
    if has:
        with open(marker, 'w', newline='\r\n') as f:
            f.write('amiga_gm.sf2 has the Amiga intro and ending tunes (built from your own Amiga disk images)\n')
    elif os.path.exists(marker):
        os.remove(marker)
    return (f'{"made" if made else "up to date"} from {os.path.basename(gm)} and amiga.sf2, '
            f'{os.path.getsize(out) / 1e6:.1f} MB')

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--install':
        print(f'{MERGED}: ' + update_install(sys.argv[2]))
        sys.exit()
    if len(sys.argv) != 4:
        sys.exit(__doc__.rsplit('Usage: ', 1)[1])
    r = merge(*sys.argv[1:4])
    print(f'{sys.argv[3]}: {r["presets"]} presets ({r["dropped"]} of the first font replaced), '
          f'{r["instruments"]} instruments, {r["samples"]} samples, {r["bytes"] / 1e6:.1f} MB')
