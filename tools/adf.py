"""Read files from Amiga disk images (.ADF, 880 KB, OFS or FFS). Only for the user's own Amiga Moonstone disks.
Usage: python -I tools/adf.py <disk.adf> [output folder]   (lists the files; with a folder, extracts them)"""
import sys, os, struct

BLOCK, ROOT = 512, 880
T_HEADER, T_DATA, T_LIST = 2, 8, 16
ST_ROOT, ST_DIR, ST_FILE = 1, 2, -3 & 0xffffffff

class Adf:
    """A damaged image raises ValueError: block numbers outside the disk, wrong block types and chains that loop."""
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        if self.d[:3] != b'DOS':
            raise ValueError(f'{path}: not an AmigaDOS disk (no DOS boot block)')
        if len(self.d) % BLOCK or len(self.d) // BLOCK <= ROOT:
            raise ValueError(f'{path}: not a whole AmigaDOS disk image ({len(self.d)} bytes)')
        self.ffs = bool(self.d[3] & 1)

    def block(self, n):
        if not 2 <= n < len(self.d) // BLOCK:                # 0-1 are the boot block
            raise ValueError(f'block {n} is outside the disk')
        return self.d[n * BLOCK:(n + 1) * BLOCK]

    def header(self, n, seen):
        """Block n as a header block (type 2), once per walk."""
        if n in seen:
            raise ValueError(f'block {n} is reached twice (a damaged directory)')
        seen.add(n)
        b = self.block(n)
        if struct.unpack('>L', b[:4])[0] != T_HEADER:
            raise ValueError(f'block {n} is not a header block')
        return b

    def longs(self, n):
        return struct.unpack('>128L', self.block(n))

    @staticmethod
    def name(b):
        return b[0x1b1:0x1b1 + b[0x1b0]].decode('latin-1')

    def walk(self, n=ROOT, path='', seen=None):
        """Yield (path, header block) for every file under the directory block n."""
        seen = {n} if seen is None else seen
        for h in self.longs(n)[6:6 + 72]:
            while h:
                b = self.header(h, seen)
                sec = struct.unpack('>L', b[-4:])[0]
                p = path + self.name(b)
                if sec == ST_DIR:
                    yield from self.walk(h, p + '/', seen)
                elif sec == ST_FILE:
                    yield p, h
                h = struct.unpack('>L', b[-16:-12])[0]       # next in the hash chain

    def read(self, h):
        b = self.block(h)
        size = struct.unpack('>L', b[-188:-184])[0]
        if size > len(self.d):
            raise ValueError(f'block {h}: file size {size} is larger than the disk')
        seen = set()
        if self.ffs:                                         # data block table, newest first; extension blocks
            out, hdr = bytearray(), h
            while hdr and len(out) < size:
                if hdr in seen:
                    raise ValueError(f'block {hdr}: the extension blocks loop')
                seen.add(hdr)
                table = self.longs(hdr)[6:6 + 72][::-1]
                for blk in table:
                    if blk:
                        out += self.block(blk)
                hdr = self.longs(hdr)[126]
            return bytes(out[:size])
        out, blk = bytearray(), self.longs(h)[4]               # OFS: first data block, then a chain
        while blk and len(out) < size:
            if blk in seen:
                raise ValueError(f'block {blk}: the data blocks loop')
            seen.add(blk)
            l = self.longs(blk)
            if l[0] != T_DATA:
                raise ValueError(f'block {blk} is not a data block')
            n = l[3]
            out += self.block(blk)[24:24 + n]
            blk = l[4]
        return bytes(out[:size])

if __name__ == '__main__':
    adf = Adf(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else None
    print('FFS' if adf.ffs else 'OFS', 'volume', adf.name(adf.block(ROOT)))
    for p, h in adf.walk():
        data = adf.read(h)
        print(f'{len(data):8}  {p}')
        if out:
            dest = os.path.join(out, *p.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, 'wb').write(data)
