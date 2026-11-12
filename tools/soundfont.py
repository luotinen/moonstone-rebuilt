"""Write a SoundFont 2 file (.sf2) with one sound per key, for the FluidSynth inside DOSBox-X.

A note-on for a key plays that key's sample at its own rate (the key is the sample's root key), at full volume for
velocity 127. A one-shot plays to its end whatever happens to the key; a looping sound repeats between its loop
points until the note-off.

sounds: [(preset number, key, name, samples as numpy floats -1..1, rate in Hz, loop)], loop = None for a one-shot or
(first sample of the loop, sample after its end). write(path, sounds, name) makes one preset per preset number
(bank 0) and returns nothing. With cut=True every sound is in one exclusive class: a new note on a MIDI channel
stops the sound that channel was playing, as a new sound does on an Amiga channel."""
import struct
import numpy as np

# generator numbers (SoundFont 2.01, section 8.1.2)
PAN, ATTACK, RELEASE, INSTRUMENT, KEY_RANGE, VEL_RANGE = 17, 34, 38, 41, 43, 44
ATTENUATION, SAMPLE_ID, SAMPLE_MODES, EXCLUSIVE_CLASS, ROOT_KEY, FILTER_FC = 48, 53, 54, 57, 58, 8

def _chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'')

def _list(kind, *chunks):
    return _chunk(b'LIST', kind + b''.join(chunks))

def _name(s):
    return s.encode('ascii', 'replace')[:19].ljust(20, b'\0')

def write(path, sounds, name='Moonstone', cut=False):
    presets = sorted({s[0] for s in sounds})
    smpl, shdr = bytearray(), bytearray()
    inst, ibag, igen = bytearray(), bytearray(), bytearray()
    phdr, pbag, pgen = bytearray(), bytearray(), bytearray()
    sample_no = 0
    for inst_no, preset in enumerate(presets):
        phdr += _name(f'{name} {preset}') + struct.pack('<HHHIII', preset, 0, len(pbag) // 4, 0, 0, 0)
        pbag += struct.pack('<HH', len(pgen) // 4, 0)
        pgen += struct.pack('<HH', INSTRUMENT, inst_no)
        inst += _name(f'{name} {preset}') + struct.pack('<H', len(ibag) // 4)
        for _, key, sname, x, rate, loop in (s for s in sounds if s[0] == preset):
            pcm = np.clip(np.asarray(x, dtype=np.float64) * 32767, -32768, 32767).astype('<i2')
            start = len(smpl) // 2
            smpl += pcm.tobytes() + bytes(2 * 46)                  # 46 zero samples after each, as the format asks
            lo, hi = (start + loop[0], start + loop[1]) if loop else (start, start + len(pcm))
            shdr += _name(sname) + struct.pack('<IIIIIBbHH', start, start + len(pcm), lo, hi, int(round(rate)), key, 0, 0, 1)
            ibag += struct.pack('<HH', len(igen) // 4, 0)
            igen += struct.pack('<HBB', KEY_RANGE, key, key)
            igen += struct.pack('<Hh', FILTER_FC, 13500)           # the filter fully open, whatever the velocity
            igen += struct.pack('<Hh', ROOT_KEY, key)
            igen += struct.pack('<Hh', RELEASE, 8000 if not loop else -7000)   # one-shot: let it finish; loop: 17 ms
            igen += struct.pack('<Hh', SAMPLE_MODES, 1 if loop else 0)
            if cut: igen += struct.pack('<Hh', EXCLUSIVE_CLASS, 1)
            igen += struct.pack('<HH', SAMPLE_ID, sample_no)
            sample_no += 1
    # the terminal records every list ends with
    phdr += _name('EOP') + struct.pack('<HHHIII', 0, 0, len(pbag) // 4, 0, 0, 0)
    pbag += struct.pack('<HH', len(pgen) // 4, 0); pgen += bytes(4)
    inst += _name('EOI') + struct.pack('<H', len(ibag) // 4)
    ibag += struct.pack('<HH', len(igen) // 4, 0); igen += bytes(4)
    shdr += _name('EOS') + bytes(26)
    info = _list(b'INFO', _chunk(b'ifil', struct.pack('<HH', 2, 1)), _chunk(b'isng', b'EMU8000\0'),
                 _chunk(b'INAM', name.encode('ascii', 'replace') + b'\0'))
    sdta = _list(b'sdta', _chunk(b'smpl', bytes(smpl)))
    pdta = _list(b'pdta', _chunk(b'phdr', bytes(phdr)), _chunk(b'pbag', bytes(pbag)), _chunk(b'pmod', bytes(10)),
                 _chunk(b'pgen', bytes(pgen)), _chunk(b'inst', bytes(inst)), _chunk(b'ibag', bytes(ibag)),
                 _chunk(b'imod', bytes(10)), _chunk(b'igen', bytes(igen)), _chunk(b'shdr', bytes(shdr)))
    body = b'sfbk' + info + sdta + pdta
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', len(body)) + body)
