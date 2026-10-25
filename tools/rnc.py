"""Decompression of the Amiga version's .cmp files (music.cmp, vmusic.cmp). They start with 'RNC', 1 like Rob Northen
ProPack method 1, but use an older Rob Northen format: a 12-byte header (signature, unpacked size, packed size) and a
stream that is decoded from the end backwards, bit by bit, writing the output from its end towards its start.
This is a translation of the unpacker in the Amiga 'program' file (file offset 65D6). Usage: python -I tools/rnc.py <in> <out>"""
import sys, struct

LIT_BITS, LIT_ADD = (10, 3, 2, 2), (14, 7, 4, 1)          # program 6686 / 668A, indexed by d1 = 3..0
LEN_BITS, LEN_ADD = (10, 2, 1, 0, 0), (10, 6, 4, 3, 2)     # 66C2 / 66C7
OFF_BITS, OFF_ADD = (11, 4, 7), (0x120, 0, 0x20)           # 670E / 6712

class _Stream:
    def __init__(self, data, end):
        self.d, self.p = data, end - 1
        self.buf, self.x = data[self.p], 0                 # the first byte read is a whole byte (with its end marker)
    def byte(self):
        self.p -= 1
        return self.d[self.p]
    def bit(self):                                         # lsl.b #1,d3 / bne / move.b -(a6),d3 / roxl.b #1,d3
        c = self.buf >> 7
        self.buf = (self.buf << 1) & 0xff
        self.x = c
        if self.buf:
            return c
        nb = self.byte()
        c = nb >> 7
        self.buf = ((nb << 1) | self.x) & 0xff
        self.x = c
        return c
    def bits(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

def unrnc(data):
    if data[:4] != b'RNC\x01':
        raise ValueError('not an RNC file')
    size, packed = struct.unpack('>LL', data[4:12])
    if packed + 12 != len(data):
        raise ValueError('not the old 12-byte-header RNC format (standard ProPack files are not supported here)')
    s = _Stream(data, 12 + packed)
    out = bytearray(size + 0x100)
    top = a3 = len(out)
    while True:
        if s.bit():                                        # literal run
            n = 0
            if s.bit():
                for d1 in (3, 2, 1, 0):
                    n = s.bits(LIT_BITS[d1])
                    if d1 == 0 or n != (1 << LIT_BITS[d1]) - 1:
                        n += LIT_ADD[d1]
                        break
            for _ in range(n + 1):
                a3 -= 1; out[a3] = s.byte()
        if s.p <= 12:
            break
        d0 = 3                                             # match length
        while d0 >= 0 and s.bit():
            d0 -= 1
        d0 += 1
        length = s.bits(LEN_BITS[d0]) + LEN_ADD[d0]
        if length == 2:                                    # match offset
            offset = s.bits(9) + 0x40 if s.bit() else s.bits(6)
        else:
            d0 = 1
            while d0 >= 0 and s.bit():
                d0 -= 1
            d0 += 1
            offset = s.bits(OFF_BITS[d0] + 1) + OFF_ADD[d0]
        src = a3 + offset + length - 1 if offset else a3 + 1
        for _ in range(length):
            src -= 1; a3 -= 1; out[a3] = out[src]
    result = bytes(out[a3:top])
    if len(result) != size:
        raise ValueError(f'unpacked {len(result)} bytes, header says {size}')
    return result

if __name__ == '__main__':
    out = unrnc(open(sys.argv[1], 'rb').read())
    open(sys.argv[2], 'wb').write(out)
    print(f'{len(out)} bytes -> {sys.argv[2]}')
