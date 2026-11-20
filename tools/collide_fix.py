"""D131: the troll's blow from above hits where its club is drawn. COLLFIX.HIT is the game's COLLIDE.HIT (DISKB) with
more points on the club pieces of the troll's blow frame (script 5C7C: TROLL2.CEL frame 2, TROLL1.CEL frames 24h and
2Fh, the pieces with flag 2), so the club no longer passes through gaps in the knight's picture between the game's
thin line of points. The fixed MAIN.EXE loads it (patches.py D131, the name at DS:9D82); the original file stays as
it is, for the original program.
The file cannot grow: MAIN.EXE copies it whole to DS:A1DE and keeps it there for the whole game (each fight's banks
are parsed from it, 8851), and the bank table follows at DS:C282, 8356 bytes on: the game's file fills that room to
the byte. The new points take the room of TROLL2.CEL frame 0Dh's 14 points, which no script draws as a weapon piece
(only pieces with flag 2 go to the weapon list, 9A94, and only weapon pieces are tested by their points, A1A6), so
the file keeps its size. The game's own points stay; every added point is a drawn pixel of its piece, within the
game's points' reach (119-160 pixels in front of the troll at the blow), so the chop's reach ends stay.
Usage: python -I tools/collide_fix.py <game dir>"""
import os, sys

TARGET, SOURCE = 'COLLFIX.HIT', 'COLLIDE.HIT'
ROOM = 0xc282 - 0xa1de                       # DS:A1DE up to the bank table at C282: 8356 bytes, the game's file size
FREED = ('troll2.cel', 0x0d)                 # 14 points never read: frame 0Dh is no weapon piece in any script
# the added points per (bank, frame), after the game's own (the first point that hits gives the hit's place,
# [di+58h]: where the game's points hit, nothing changes); x, y in the frame's own pixels. Chosen in MAIN's fight loop
# (research/fight_saves/chop_pick.py, dev folder): with the knight standing 90-180 pixels from the troll, either side,
# depth -8 to 8, the blow lands at every distance from the side's nearest game hit at depth 0-4 (right of the knight
# 110, left 111) to the depth's own farthest one, and nowhere the game did not; the club itself (frame 2): its
# handle end and its head, the rows the game's line (y 8-14) left out; the streak 24h: its near edge.
ADDED = {
    ('troll2.cel', 2): [(18, 11), (15, 6), (18, 15), (19, 16), (44, 10), (28, 11), (14, 6), (43, 15), (16, 7), (45, 10)],
    ('troll1.cel', 0x24): [(7, 16), (6, 15), (4, 13), (7, 12)],
}


def read_banks(text):
    """-> [(name line, [(count line, flag line, points line), ...])], keeping the file's own spelling."""
    lines, banks, i = text.split('\n'), [], 0
    while i < len(lines) and lines[i] not in ('', '99'):
        name, frames = lines[i], []; i += 1
        while lines[i] != '99':
            n = int(lines[i])
            if n: frames.append((lines[i], lines[i + 1], lines[i + 2])); i += 3
            else: frames.append((lines[i], None, None)); i += 1
        banks.append((name, frames)); i += 1
    return banks, '\n'.join(lines[i:])


def write_banks(banks, tail):
    out = []
    for name, frames in banks:
        out.append(name)
        for count, flag, points in frames:
            out.append(count)
            if flag is not None: out += [flag, points]
        out.append('99')
    return '\n'.join(out) + '\n' + tail


def points(line):
    return [(int(line[k:k + 3]), int(line[k + 3:k + 6])) for k in range(0, len(line), 6)]


def make(data):
    text = data.decode('latin1')
    banks, tail = read_banks(text)
    if write_banks(banks, tail) != text:
        raise ValueError(f"{SOURCE}: not the game's file (it does not read back the same)")
    for name, frames in banks:
        for (bank, frame), extra in ADDED.items():
            if name.lower() == bank:
                count, flag, line = frames[frame]
                pts = points(line) + list(extra)
                if len(pts) >= 99 or len(set(pts)) != len(pts):          # '99' ends a bank
                    raise ValueError(f'{bank} frame {frame:X}h: {len(pts)} points, or a point twice')
                frames[frame] = ('%02d' % len(pts), flag, ''.join('%03d%03d' % p for p in pts))
        if name.lower() == FREED[0]:
            frames[FREED[1]] = ('00', None, None)
    out = write_banks(banks, tail).encode('latin1')
    if len(out) > ROOM:
        raise ValueError(f'{TARGET}: {len(out)} bytes, more than the {ROOM} MAIN.EXE keeps room for (DS:A1DE-C282)')
    return out


def install(game):
    """Writes DISKB/COLLFIX.HIT from the game's own DISKB/COLLIDE.HIT."""
    disk = os.path.join(game, 'DISKB')
    with open(os.path.join(disk, SOURCE), 'rb') as f: data = f.read()
    with open(os.path.join(disk, TARGET), 'wb') as f: f.write(make(data))


if __name__ == '__main__':
    install(sys.argv[1])
