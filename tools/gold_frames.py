"""D91: five-digit money. TV5.PIV is the game's TAV.PIV with the gold sack (top right) 10 pixels wider, MY5.CEL is the
game's MYS.CEL with its frames 0 and 1 (Mythral's and the healer's gold sack, on the donation screen) 10 pixels wider,
so that their dark boxes hold five digits. The fixed MAIN.EXE loads them (patches.py D91); the original files stay as
they are, for the original program.
Usage: python -I tools/gold_frames.py <game dir>"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from death_frames import lz_encode, lz_decode, read_bank, frame_pixels, frame_planes

WIDER = 10                                   # pixels added in the middle of each sack
# the tavern's sack: its box (inside) x 279-296, y 14-19; the rows 11-27 (shoulders down) are widened around SPLIT
TAV_SPLIT, TAV_ROWS, TAV_X = 288, range(11, 28), range(268, 308)
TAV_PAPER = {16, 18, 2}                      # the parchment's colours around it
# MYS.CEL frames 0 (Mythral, 46 wide) and 1 (healer, 47 wide): box inside x 13-30 / 14-31; rows 11 on are the body
CEL_SPLIT, CEL_BODY = {0: 22, 1: 23}, 11
TARGETS = {'TV5.PIV': 'TAV.PIV', 'MY5.CEL': 'MYS.CEL'}


def piv_pixels(data):
    planes, csize = struct.unpack('>HI', data[:6])
    head = 6 + 2 * (16 if planes == 4 else 32)
    raw = lz_decode(data, head, csize)
    img = [[0] * 320 for _ in range(200)]
    for p in range(planes):
        for y in range(200):
            row = raw[(p * 200 + y) * 40:(p * 200 + y + 1) * 40]
            for x in range(320):
                if row[x >> 3] & (0x80 >> (x & 7)): img[y][x] |= 1 << p
    return planes, data[6:head], img


def piv_bytes(planes, palette, img):
    raw = bytearray(planes * 200 * 40)
    for p in range(planes):
        for y in range(200):
            base = (p * 200 + y) * 40
            for x, v in enumerate(img[y]):
                if v & (1 << p): raw[base + (x >> 3)] |= 0x80 >> (x & 7)
    packed = lz_encode(bytes(raw))
    return struct.pack('>HI', planes, len(packed)) + palette + packed


def wider_tavern(img):
    """The sack's pixels left of TAV_SPLIT move WIDER/2 left, those right of it WIDER/2 right; the middle keeps the
    old pixels (the box and the sack's bands go on); the parchment left bare by the move is its plain colour 16."""
    half = WIDER // 2
    img = [row[:] for row in img]
    for y in TAV_ROWS:
        old = img[y][:]
        sack = {x: old[x] for x in TAV_X if old[x] not in TAV_PAPER}
        for x in sack: img[y][x] = 16
        for x, v in sack.items():
            if x < TAV_SPLIT: img[y][x - half] = v
            if TAV_SPLIT - half <= x < TAV_SPLIT + half: img[y][x] = v
            if x >= TAV_SPLIT: img[y][x + half] = v
    return img


def wider_sack(img, split):
    """The body rows get WIDER columns copied from the middle; the neck above moves WIDER/2 right."""
    half = WIDER // 2
    out = []
    for y, row in enumerate(img):
        if y < CEL_BODY: out.append([0] * half + row + [0] * half)
        else: out.append(row[:split] + row[split - half:split + half] + row[split:])
    return out


def wider_bank(data):
    frames, raw = read_bank(data)
    new_raw, new_frames = bytearray(), []
    for i, (off, w, h, mask) in enumerate(frames):
        if i in CEL_SPLIT:
            img = wider_sack(frame_pixels(raw, off, w, h, mask), CEL_SPLIT[i])
            mask, planes = frame_planes(img)
            w = len(img[0])
        else:
            nplanes = bin(mask & 0xff).count('1')
            planes = raw[off:off + ((w + 15) // 16) * 2 * h * nplanes]
        new_frames.append((len(new_raw), w, h, mask))
        new_raw += planes
    packed = lz_encode(bytes(new_raw))
    return (struct.pack('>HII', len(new_frames), len(packed), len(new_raw) * 8) +
            b''.join(struct.pack('>IHHH', *f) for f in new_frames) + packed)


def make(name, data):
    if name == 'TV5.PIV':
        planes, palette, img = piv_pixels(data)
        return piv_bytes(planes, palette, wider_tavern(img))
    return wider_bank(data)


def install(game):
    """Writes DISKC/TV5.PIV and DISKC/MY5.CEL from the game's own files."""
    disk = os.path.join(game, 'DISKC')
    for target, source in TARGETS.items():
        with open(os.path.join(disk, source), 'rb') as f: data = f.read()
        with open(os.path.join(disk, target), 'wb') as f: f.write(make(target, data))


if __name__ == '__main__':
    install(sys.argv[1])
