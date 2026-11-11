"""D38: the horses' pictures. KH.CEL is the game's KI.CEL with the five 16x18 shop pictures after its 50 frames (one frame
per horse: the buyer's colour comes from palette entries 28 and 29), MH.C is the game's MI.C with the 9x11 map icons after its
47 frames (five colours per horse). The original files stay as they are, for the original program.
Usage: python -I tools/horse_frames.py <game dir>"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from death_frames import lz_encode, read_bank

FIRST_SHOP, FIRST_MAP = 50, 47
# with EMS the game copies files into a cache at start, each at a fixed place (DS:828A): the room each has there
EMS_ROOM = {'KH.CEL': 0x8000 - 0x4199, 'MH.C': 0x8000 - 0x4960}
SHOP = (
    ('.....##.........', '....#bb#........', '....#bbb###.....', '...#bbbbbCC##...', '...#bbbbCCCCC#..', '..#bbEEbbCCCCC#.',
     '..#bbEEbbCCDCC#.', '.#bbbbbbtCCDCCC#', '.#bbbbbbb#CDCCC#', '#bbbbbbbt#CCDCC#', '#bbNbbbt#bCCDCC#', '#bbbb###bbCCDCC#',
     '#t#t#..#bbCCDCC#', '.###...#bbCCDC#.', '.......#bbCCDC#.', '......#bbtCCCC#.', '......#bttCCCC#.', '......#########.'),
    ('.....##.........', '....#ww#........', '....#www###.....', '...#wwwwwCC##...', '...#wwwwCCCCC#..', '..#wwEEwwCCCCC#.',
     '..#wwEEwwCCDCC#.', '.#wwwwwwgCCDCC#.', '.#wwwwwwg#CDC#..', '#wwwwwwwg#CCwg#.', '#wwNwwwg#wwCwwg#', '#wwww###wwwwwgg#',
     '#g#g#..#wwwwwgg#', '.###...#wwwwwg#.', '.......#wwwwgg#.', '......#wwwwggg#.', '......#wwgggg#..', '......########..'),
    ('....#CCC#.......', '....#CCDC#......', '....#g#CC###....', '...#gwggwCC##...', '...#gwggCCCCC#..', '..#gwEEEgCCCCC#.',
     '..#gwggggCCDCC#.', '.#ggwgggkCCDCCC#', '.#ggwgggk#CDCCC#', '#bggwggk##CCDCC#', '#bbbggk#CCCCDCC#', '#bNbb###CCCCDCC#',
     '#t#t#..#CCCCDCC#', '.###...#gCCCDC#.', '.......#gCCCDC#.', '......#ggCCCCC#.', '......#gCCCCCC#.', '......#########.'),
    ('....#...#.......', '...#d#.#d#......', '...#dd#dd###....', '...#wdddddCC##..', '...#wwddCCCCCC#.', '..#wwdWWdCCCCC#.',
     '..#wwddddCCDCC#.', '.#wwddddkCCDCCC#', '.#wdddddd#CDCCC#', '#wwdddddk#CCDCC#', '#wwNddk#ddCCDCC#', '#wddd###ddCCDCC#',
     '#W#W#..#ddCCDCC#', '.###...#ddCCDC#.', '.......#ddCCDC#.', '......#ddkCCCC#.', '......#dkkCCCCC#', '......##########'),
    ('.....##.........', '....#wg#........', '....#wwg###.....', '...#wwgwwCC##...', '...#wgwwCCCCC#..', '..#wwEEwgCCCDC#.',
     '..#gwEEwwCDCC#..', '.#wwgwwgwCCDCC#.', '.#wgwwwww#CDCCC#', '#wwwgwwgw#CCDC#.', '#wwNwggw#wgCDCC#', '#wwww###gwCCDC#.',
     '#g#g#..#wgCDCC#.', '.###...#wwgCCD#.', '.......#gwwCDC#.', '......#wwgwCCC#.', '......#gwwgCCC#.', '......#########.'),
)
SHOP_COLOURS = {'.': 0, '#': 5, 'E': 5, 'N': 5, 'b': 11, 't': 12, 'w': 1, 'W': 9, 'g': 3, 'k': 6, 'd': 4, 'C': 28, 'D': 29}
MAP = (
    ('...##....', '..#b###..', '..#bbCC#.', '.#b#bCCC#', '.#bbtCCC#', '#bbb#CCC#', '#t#t#CCC#', '.###bCC#.', '...#bCC#.', '..#btCC#.', '..######.'),
    ('...##....', '..#w###..', '..#wwCC#.', '.#w#wCCC#', '.#wwgCCC#', '#www#CC#.', '#g#g#Cw#.', '.###wwC#.', '...#wwg#.', '..#wgg#..', '..#####..'),
    ('...#CC#..', '..#g#C#..', '..#gwCC#.', '.#g##CCC#', '.#ggwCCC#', '#bgg#CCC#', '#t#b#CCC#', '.###gCC#.', '...#gCC#.', '..#ggCC#.', '..######.'),
    ('..#..#...', '..#d#C#..', '..#wdCC#.', '.#wdWCCC#', '.#wddCCC#', '#wdd#CC#.', '#W#d#C#..', '.###dC#..', '...#dCC#.', '..#ddCCC#', '..#######'),
    ('...##....', '..#w###..', '..#wgCC#.', '.#w#wCCC#', '.#gwgCCC#', '#wwg#CC#.', '#g#w#CCC#', '.###gCCC#', '...#wCg#.', '..#gwC#..', '..#####..'),
)
MAP_COLOURS = {'.': 0, '#': 19, 'w': 1, 'g': 3, 'b': 5, 't': 6, 'd': 16, 'W': 1}
MAP_KNIGHT = (30, 29, 8, 28, 24)                 # blue, orange, green, red, computer (the helmets' MI.C frames 5-9 in this order)


def shop_frame(rows):
    return [[SHOP_COLOURS[ch] for ch in row] for row in rows]


def map_frame(rows, colour):
    """The active look: the outside edge of the outline in 31, the map's active outline."""
    h, w = len(rows), len(rows[0])
    out = [[colour if ch == 'C' else MAP_COLOURS[ch] for ch in row] for row in rows]
    for y in range(h):
        for x in range(w):
            if rows[y][x] == '#' and any(not (0 <= x + a < w and 0 <= y + b < h) or rows[y + b][x + a] == '.'
                                         for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[y][x] = 31
    return out


def frame_planes(img):
    """(frame mask, data): five bit planes, as the game's own MI.C frames and KI.CEL's frame 17."""
    bpr = ((len(img[0]) + 15) // 16) * 2
    out = bytearray()
    for b in range(5):
        for row in img:
            line = bytearray(bpr)
            for x, v in enumerate(row):
                if v & (1 << b): line[x >> 3] |= 0x80 >> (x & 7)
            out += line
    return 0x11f, bytes(out)


def with_frames(data, new, first):
    frames, raw = read_bank(data)
    if len(frames) != first: raise ValueError(f'{len(frames)} frames, expected {first}')
    raw = bytearray(raw)
    for img in new:
        mask, planes = frame_planes(img)
        frames.append((len(raw), len(img[0]), len(img), mask))
        raw += planes
    packed = lz_encode(bytes(raw))
    return (struct.pack('>HII', len(frames), len(packed), len(raw) * 8) +
            b''.join(struct.pack('>IHHH', *f) for f in frames) + packed)


def install(game):
    """Writes DISKB/KH.CEL and DISKB/MH.C from the game's own banks."""
    disk = os.path.join(game, 'DISKB')
    pairs = (('KI.CEL', 'KH.CEL', [shop_frame(r) for r in SHOP], FIRST_SHOP),
             ('MI.C', 'MH.C', [map_frame(r, c) for r in MAP for c in MAP_KNIGHT], FIRST_MAP))
    for source, target, new, first in pairs:
        with open(os.path.join(disk, source), 'rb') as f: data = f.read()
        data = with_frames(data, new, first)
        if len(data) > EMS_ROOM[target]:
            raise ValueError(f'{target}: {len(data)} bytes, its place in the EMS file cache holds {EMS_ROOM[target]}')
        with open(os.path.join(disk, target), 'wb') as f: f.write(data)


if __name__ == '__main__':
    install(sys.argv[1])
