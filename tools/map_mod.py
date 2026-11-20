"""Map mod formats for the terrain editor (docs/terrain-80x50-plan-2026-11-19.md, T1b and T1c; findings in
docs/map-mod-study-2026-11-19.md). Pure Python 3 with Pillow (no numpy): the game's LZSS, Amiga bit planes, MAP.CMP,
the sprite banks (.C), the palette reduction, the places and lairs, the project ZIP, and applying a map to a game
folder with the original kept as MAP.CMP.orig.

Nothing here ships game art: every picture and sprite is read from the player's own game folder."""
import io
import os
import shutil
import struct
import zipfile
from collections import Counter

MAP_W, MAP_H = 320, 200
MAP_LIMIT = 35840               # the map stash [88FD] (0x8C0 paragraphs, 1000:867A): the longest MAP.CMP the game takes
MAP_GAME_LEN = 35331            # the game's own MAP.CMP; the copies at 8A88 and 914B move this many bytes (immediates,
                                # set to a longer file's length by the rules build, D135)
FREE_COLOURS = (15, 20, 21, 22, 23, 27)   # palette entries no map sprite uses: the player's to change
REACH_X, REACH_Y = 310, 190     # a knight's top-left position stays within x 0-310, y 0-190 (AB98, ABAB)
KNIGHT_W, KNIGHT_H = 8, 10      # a knight's map icon (MI.C frame 0)
DS_IMG = 0x123b * 16            # MAIN.EXE's data segment in its load image
PLACES_DS, LAIRS_DS, TERRAIN_DS = 0x0498, 0x0aca, 0xc42a


# ---- LZSS (control byte MSB first; 1 = big-endian word: length 34 - (w >> 11), distance w & 7FFh; 0 = literal) ----

def lz_decode(src, start, length):
    out = bytearray()
    i, end = start, start + length
    while i < end:
        ctl = src[i]
        i += 1
        for _ in range(8):
            if i >= end:
                break
            if ctl & 0x80:
                w = src[i] << 8 | src[i + 1]
                i += 2
                p = len(out) - (w & 0x7ff)
                for k in range(34 - (w >> 11)):
                    out.append(out[p + k])
            else:
                out.append(src[i])
                i += 1
            ctl = (ctl << 1) & 0xff
    return bytes(out)


def lz_encode(raw, window=2047, minlen=3, maxlen=34, chain=512):
    """LZSS in the game's format with an optimal parse (lz_decode gives raw back exactly): the longest match at each
    position (searched through the last `chain` places with the same 3 bytes), then the cheapest way through in bits
    (a literal 9, a match 17). The game's own map: 34,996-35,070 bytes, its file 35,261."""
    raw = bytes(raw)
    n = len(raw)
    heads, best = {}, [(0, 0)] * n
    for i in range(n - 2):
        key = raw[i:i + 3]
        bl = bd = 0
        for p in reversed(heads.get(key, ())[-chain:]):
            d = i - p
            if d > window:
                break
            ln = 3
            while ln < maxlen and i + ln < n and raw[p + ln] == raw[i + ln]:
                ln += 1
            if ln > bl:
                bl, bd = ln, d
                if ln == maxlen:
                    break
        heads.setdefault(key, []).append(i)
        best[i] = (bl, bd)
    cost, choice = [0] * (n + 1), [1] * n
    for i in range(n - 1, -1, -1):
        c, ch = cost[i + 1] + 9, 1
        for ln in range(minlen, best[i][0] + 1):
            if cost[i + ln] + 17 < c:
                c, ch = cost[i + ln] + 17, ln
        cost[i], choice[i] = c, ch
    items, i = [], 0
    while i < n:
        if choice[i] == 1:
            items.append(raw[i])
        else:
            items.append((choice[i], best[i][1]))
        i += choice[i]
    out = bytearray()
    for g in range(0, len(items), 8):
        ctl, body = 0, bytearray()
        for k, it in enumerate(items[g:g + 8]):
            if isinstance(it, tuple):
                ctl |= 0x80 >> k
                body += struct.pack('>H', ((maxlen - it[0]) << 11) | it[1])
            else:
                body.append(it)
        out.append(ctl)
        out += body
    return bytes(out)


# ---- bit planes ------------------------------------------------------------------------------------------------------

_BIT = [[bytes(((b >> (7 - k)) & 1) << p for b in range(256)) for k in range(8)] for p in range(8)]
_UNBIT = [[bytes(((b >> p) & 1) << (7 - k) for b in range(256)) for k in range(8)] for p in range(8)]


def planes_to_pixels(raw, w, h, plane_bits, off=0):
    """Amiga bit planes (one after the other, rows padded to 16 pixels) -> w * h colour indices (bytes)."""
    bpr = (w + 15) // 16 * 2
    size = bpr * h
    acc = [0] * 8
    for i, bit in enumerate(plane_bits):
        plane = bytes(raw[off + i * size: off + (i + 1) * size])
        for k in range(8):
            acc[k] |= int.from_bytes(plane.translate(_BIT[bit][k]), 'big')
    wide = bytearray(size * 8)
    for k in range(8):
        wide[k::8] = acc[k].to_bytes(size, 'big')
    if bpr * 8 == w:
        return bytes(wide)
    return b''.join(wide[y * bpr * 8: y * bpr * 8 + w] for y in range(h))


def pixels_to_planes(pix, w, h, planes):
    """w * h colour indices -> bit planes (the reverse of planes_to_pixels, plane i = bit i)."""
    bpr = (w + 15) // 16 * 2
    if bpr * 8 != w:
        pix = b''.join(bytes(pix[y * w:(y + 1) * w]) + bytes(bpr * 8 - w) for y in range(h))
    pix = bytes(pix)
    size = bpr * h
    out = bytearray()
    for p in range(planes):
        acc = 0
        for k in range(8):
            acc |= int.from_bytes(pix[k::8].translate(_UNBIT[p][k]), 'big')
        out += acc.to_bytes(size, 'big')
    return bytes(out)


# ---- palette ----------------------------------------------------------------------------------------------------------

def word_rgb(w):
    return ((w >> 8) & 15) * 17, ((w >> 4) & 15) * 17, (w & 15) * 17


def rgb_word(rgb):
    r, g, b = (min(15, max(0, round(c / 17))) for c in rgb[:3])
    return r << 8 | g << 4 | b


def set_colour(word, rgb12):
    """A palette word with its colour replaced, the top 4 bits kept (the game's words carry 8000h)."""
    return (word & 0xf000) | (rgb12 & 0xfff)


def palette_bytes(words):
    return bytes(c for w in words for c in word_rgb(w))


def _d2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _q(rgb):
    """A colour in the Amiga's 12-bit space (0-15 a channel, not rounded: the nearest is measured there)."""
    return rgb[0] / 17, rgb[1] / 17, rgb[2] / 17


def nearest(rgb, words, free=FREE_COLOURS):
    """The palette index nearest to rgb in the 12-bit RGB space. A tie (the game's palette has the same colour in more
    than one entry, e.g. 22, 23 and 26) goes to a fixed entry before a free one, so changing a free colour later never
    recolours pixels painted with a fixed colour; then to the lower index."""
    q = _q(rgb)
    return min(range(len(words)), key=lambda i: (_d2(q, ((words[i] >> 8) & 15, (words[i] >> 4) & 15, words[i] & 15)),
                                                 i in free, i))


def reduce_image(img, words):
    """A 320 x 200 picture -> (pixels as palette indices, how many pixels changed colour). No dithering. A paletted
    picture whose palette starts with the map's colours keeps its indices."""
    if img.size != (MAP_W, MAP_H):
        raise ValueError(f'the picture is {img.size[0]} x {img.size[1]}; the map must be {MAP_W} x {MAP_H}')
    if img.mode == 'P' and bytes(img.getpalette()[:3 * len(words)]) == palette_bytes(words) \
            and max(img.tobytes()) < len(words):
        return img.tobytes(), 0
    rgb = img.convert('RGB')
    lut, changed = {}, 0
    for count, c in rgb.getcolors(MAP_W * MAP_H):
        i = nearest(c, words)
        lut[c] = i
        if word_rgb(words[i]) != c:
            changed += count
    b = rgb.tobytes()
    return bytes(lut[c] for c in zip(b[0::3], b[1::3], b[2::3])), changed


def suggest_free(img, words, free=FREE_COLOURS, candidates=300, sample=1500):
    """The palette with its free entries set to the picture's colours the other entries show worst (greedy: each pick
    the 12-bit colour that cuts the most squared error, weighted by the pixel count)."""
    cols = Counter()
    for count, c in img.convert('RGB').getcolors(MAP_W * MAP_H):
        cols[rgb_word(c)] += count
    common = cols.most_common(sample)
    q = [(((w >> 8) & 15, (w >> 4) & 15, w & 15), n) for w, n in common]
    fixed = [((w >> 8) & 15, (w >> 4) & 15, w & 15) for i, w in enumerate(words) if i not in free]
    err = [min(_d2(c, f) for f in fixed) for c, _ in q]
    cands = [c for c, _ in q[:candidates]]
    out = list(words)
    for slot in free:
        gains = [sum(n * max(0, e - _d2(c, cand)) for (c, n), e in zip(q, err)) for cand in cands]
        if not gains or max(gains) <= 0:
            break
        pick = cands[gains.index(max(gains))]
        out[slot] = set_colour(out[slot], pick[0] << 8 | pick[1] << 4 | pick[2])
        err = [min(e, _d2(c, pick)) for (c, _), e in zip(q, err)]
    return out


# ---- MAP.CMP and the sprite banks ------------------------------------------------------------------------------------

def read_map(data):
    """MAP.CMP -> (planes, the palette's words, 320 * 200 pixels)."""
    planes, csize = struct.unpack('>HI', data[:6])
    if planes not in (4, 5) or 6 + csize > len(data) + 64:
        raise ValueError('not a map picture (MAP.CMP)')
    ncol = 16 if planes == 4 else 32
    words = list(struct.unpack('>%dH' % ncol, data[6:6 + 2 * ncol]))
    raw = lz_decode(data, 6 + 2 * ncol, csize)
    if len(raw) < planes * MAP_W * MAP_H // 8:
        raise ValueError('the map picture is cut short')
    return planes, words, planes_to_pixels(raw, MAP_W, MAP_H, list(range(planes)))


def write_map(pixels, words, planes=5):
    """320 * 200 pixels and the palette -> the MAP.CMP file's bytes."""
    if len(pixels) != MAP_W * MAP_H or max(pixels) >= 1 << planes:
        raise ValueError(f'the pixels must be {MAP_W} x {MAP_H} indices below {1 << planes}')
    ncol = 16 if planes == 4 else 32
    data = lz_encode(pixels_to_planes(pixels, MAP_W, MAP_H, planes))
    return struct.pack('>HI', planes, len(data)) + struct.pack('>%dH' % ncol, *words[:ncol]) + data


def read_cel(data):
    """A sprite bank (.C, .CEL) -> [(w, h, pixels)], index 0 transparent."""
    n, csize, _ = struct.unpack('>HII', data[:10])
    heads = [struct.unpack('>IHHH', data[10 + i * 10:20 + i * 10]) for i in range(n)]
    raw = lz_decode(data, 10 + n * 10, csize)
    return [(w, h, planes_to_pixels(raw, w, h, [b for b in range(8) if mask & (1 << b)], off))
            for off, w, h, mask in heads]


def pixels_image(pixels, words, w=MAP_W, h=MAP_H):
    from PIL import Image
    img = Image.frombytes('P', (w, h), bytes(pixels))
    img.putpalette(palette_bytes(words) + bytes(768 - 3 * len(words)))
    return img


def sprite_image(frame, words):
    """A sprite frame as RGBA (index 0 transparent)."""
    w, h, pix = frame
    from PIL import Image
    img = pixels_image(pix, words, w, h).convert('RGBA')
    img.putalpha(Image.frombytes('L', (w, h), bytes(255 if v else 0 for v in pix)))
    return img


# ---- places, starts, lairs (T1b) -------------------------------------------------------------------------------------

# key: (the game's id, MI.C frame, w, h, name, x, y as the game has it). The table DS:0498 lists them in this order.
PLACES = {
    'V1': (0x15, 21, 24, 19, 'Home village 1', 18, 11),
    'V2': (0x16, 22, 24, 14, 'Home village 2', 286, 11),
    'V3': (0x17, 23, 23, 11, 'Home village 3', 0, 187),
    'V4': (0x18, 24, 15, 8, 'Home village 4', 303, 192),
    'HW': (0x19, 25, 25, 32, 'High Wood (town)', 82, 28),
    'WD': (0x1a, 26, 32, 28, 'Water Deep (town)', 277, 143),
    'VY': (0x1c, 28, 13, 10, 'The Valley (the Guardian)', 152, 97),
    'SH': (0x1b, 27, 18, 12, 'Stonehenge', 88, 155),
    'MW': (0x1e, 30, 7, 20, 'Math the Wizard\'s tower', 217, 11),
}
VILLAGES = ('V1', 'V2', 'V3', 'V4')
# a knight's start: (village, x, y); the game sets them by colour slot 0-3 in InitNewGame (immediates, see IMM)
STARTS = {'S1': ('V1', 10, 10), 'S2': ('V2', 300, 5), 'S3': ('V3', 26, 180), 'S4': ('V4', 300, 185)}
BLACK_KNIGHTS = {'B1': (15, 100), 'B2': (300, 100), 'B3': (160, 20), 'B4': (160, 180)}
LAIRS = [(24, 112), (104, 120), (120, 144), (80, 184), (24, 160), (48, 136), (296, 32), (232, 16), (176, 48),
         (240, 48), (216, 72), (272, 80), (208, 104), (248, 120), (168, 136), (152, 176), (232, 176), (288, 176),
         (24, 24), (96, 16), (136, 40), (32, 64), (80, 64), (96, 88)]
LAIR_W, LAIR_H, LAIR_FRAME = 9, 5, 20
REGIONS = ('Forest', 'Wasteland', 'Swamp', 'Moors')      # lairs 1-6, 7-12, 13-18, 19-24 (T0: the region is the number)
SHOP_OFFSETS = {'HW': (12, 19), 'WD': (20, 14)}         # the computer knights' shopping targets: town + offset
SHOP_CELL_OFFSETS = {'HW': (17, 31), 'WD': (22, 20)}    # their cells (to pick the nearer town): (town + offset) // 8
# Where T2 writes the positions into MAIN.EXE's code (the immediate word's address in 1000:xxxx), for the record.
IMM = {
    'S4': (0x0178, 0x017d), 'S1': (0x0191, 0x0196), 'S2': (0x01aa, 0x01af), 'S3': (0x01c3, 0x01c8),
    'B1': (0x1c85, 0x1c8a), 'B2': (0x1ca4, 0x1ca9), 'B3': (0x1cc3, 0x1cc8), 'B4': (0x1ce2, 0x1ce7),
    'shop_cells': (0xaf64, 0xaf67, 0xaf77, 0xaf7a), 'shop_hw': (0xaf8d, 0xaf93), 'shop_wd': (0xaf9a, 0xafa0),
    'map_len': (0x8a89, 0x914c),
}


def lair_key(n):
    return f'L{n + 1}'


def region_of(key):
    return REGIONS[(int(key[1:]) - 1) // 6]


def original_layout():
    """Every marker's (x, y) as the game has it."""
    lay = {k: (v[5], v[6]) for k, v in PLACES.items()}
    lay.update({k: (v[1], v[2]) for k, v in STARTS.items()})
    lay.update(BLACK_KNIGHTS)
    lay.update({lair_key(i): p for i, p in enumerate(LAIRS)})
    return lay


def kind_of(key):
    """'village', 'place', 'start', 'black', 'lair'."""
    if key in PLACES:
        return 'village' if key in VILLAGES else 'place'
    return {'S': 'start', 'B': 'black', 'L': 'lair'}[key[0]]


def box(key, pos):
    """The marker's box (x0, y0, x1, y1), inclusive: a place's frame, a lair's sprite, a knight's icon."""
    x, y = pos
    k = kind_of(key)
    w, h = PLACES[key][2:4] if k in ('village', 'place') else (LAIR_W, LAIR_H) if k == 'lair' else (KNIGHT_W, KNIGHT_H)
    return x, y, x + w - 1, y + h - 1


def overlap(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def check_move(layout, key, pos):
    """'' if the marker may stand at pos, else why not. A knight's start is a position: x 0-310, y 0-190. A place or
    a lair: its box inside the 320 x 200 map (the game tests a knight's icon against the box, 0653), and not over
    another place's box (a place) or another lair's (a lair): the game takes the first it finds."""
    x, y = pos
    k = kind_of(key)
    if k in ('start', 'black'):
        return '' if 0 <= x <= REACH_X and 0 <= y <= REACH_Y else f'a knight stands at x 0-{REACH_X}, y 0-{REACH_Y}'
    b = box(key, pos)
    if b[0] < 0 or b[1] < 0 or b[2] >= MAP_W or b[3] >= MAP_H:
        return 'the box must stay inside the map (320 x 200)'
    same = ('village', 'place') if k in ('village', 'place') else ('lair',)
    for other, p in layout.items():
        if other != key and kind_of(other) in same and overlap(b, box(other, p)):
            return f'over {other}'
    return ''


def move(layout, key, pos):
    """A new layout with the marker moved (a home village takes its knight's start along), or a reason (str)."""
    why = check_move(layout, key, pos)
    if why:
        return why
    out = dict(layout)
    dx, dy = pos[0] - layout[key][0], pos[1] - layout[key][1]
    out[key] = tuple(pos)
    if kind_of(key) == 'village':
        s = 'S' + key[1]
        sx, sy = layout[s][0] + dx, layout[s][1] + dy
        out[s] = (min(max(sx, 0), REACH_X), min(max(sy, 0), REACH_Y))
    return out


def shop_targets(layout):
    """The computer knights' shopping targets (pixels) and the cells they choose the nearer town by (the game's own:
    (94, 47) and (297, 157), cells (12, 7) and (37, 20))."""
    t = {k: (layout[k][0] + dx, layout[k][1] + dy) for k, (dx, dy) in SHOP_OFFSETS.items()}
    return t, {k: ((layout[k][0] + dx) // 8, (layout[k][1] + dy) // 8) for k, (dx, dy) in SHOP_CELL_OFFSETS.items()}


def places_text(layout):
    lines = ['key,id,x,y']
    for k in list(PLACES) + list(STARTS) + list(BLACK_KNIGHTS):
        pid = f'{PLACES[k][0]:02X}h' if k in PLACES else ''
        lines.append(f'{k},{pid},{layout[k][0]},{layout[k][1]}')
    return '\n'.join(lines) + '\n'


def lairs_text(layout):
    lines = ['lair,x,y,region']
    for i in range(len(LAIRS)):
        k = lair_key(i)
        lines.append(f'{i + 1},{layout[k][0]},{layout[k][1]},{region_of(k)}')
    return '\n'.join(lines) + '\n'


def _rows(text, name, header):
    rows = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not rows or rows[0].replace(' ', '').lower() != header:
        raise ValueError(f'{name}: the first line must be "{header}"')
    return [r.split(',') for r in rows[1:]]


def _num(v, name):
    try:
        return int(v)
    except ValueError:
        raise ValueError(f'{name}: "{v}" is not a whole number') from None


def parse_layout(places, lairs, name='places'):
    """A layout from places.csv's and lairs.csv's text; every marker present once and allowed where it stands."""
    lay = {}
    for r in _rows(places, name, 'key,id,x,y'):
        if len(r) != 4 or (r[0] not in PLACES and r[0] not in STARTS and r[0] not in BLACK_KNIGHTS):
            raise ValueError(f'{name}: unknown row {",".join(r)}')
        if r[0] in lay:
            raise ValueError(f'{name}: {r[0]} twice')
        lay[r[0]] = (_num(r[2], name), _num(r[3], name))
    for r in _rows(lairs, 'lairs', 'lair,x,y,region'):
        n = _num(r[0], 'lairs') if r else 0
        if len(r) != 4 or not 1 <= n <= len(LAIRS) or lair_key(n - 1) in lay:
            raise ValueError(f'lairs: bad row {",".join(r)}')
        lay[lair_key(n - 1)] = (_num(r[1], 'lairs'), _num(r[2], 'lairs'))
    missing = [k for k in original_layout() if k not in lay]
    if missing:
        raise ValueError(f'{name}: missing {", ".join(missing[:5])}')
    for k, p in lay.items():
        why = check_move(lay, k, p)
        if why:
            raise ValueError(f'{name}: {k} at {p}: {why}')
    return lay


# ---- the player's game folder ------------------------------------------------------------------------------------------

def map_files(game):
    return [os.path.join(game, d, 'MAP.CMP') for d in ('DISKB', 'DISKC')]


def exe_image(path):
    """MAIN.EXE's load image if it is the unpacked game (its places table where it should be), else None."""
    try:
        d = open(path, 'rb').read()
    except OSError:
        return None
    img = d[struct.unpack('<H', d[8:10])[0] * 16:] if d[:2] == b'MZ' else d
    head = struct.unpack('<3H', img[DS_IMG + PLACES_DS:DS_IMG + PLACES_DS + 6]) if len(img) > DS_IMG + 0xd000 else ()
    return img if head == (0x15, 18, 11) else None


def original_exe(game):
    """The game's own MAIN.EXE image: the fixed copy Setup keeps (the installed one holds the custom rules' tables)."""
    for p in (os.path.join(game, '_fixes', 'fixed', 'MAIN.EXE'), os.path.join(game, 'MAIN.EXE')):
        img = exe_image(p)
        if img is not None:
            return img
    return None


def layout_from_exe(img):
    """The markers' positions as a MAIN.EXE image has them (tables and code immediates)."""
    w = lambda a: struct.unpack('<H', img[a:a + 2])[0]
    lay = {}
    t = DS_IMG + PLACES_DS
    ids = {v[0]: k for k, v in PLACES.items()}
    while w(t) != 0xffff:
        lay[ids[w(t)]] = (w(t + 2), w(t + 4))
        t += 6
    for i in range(len(LAIRS)):
        a = DS_IMG + LAIRS_DS + 4 * i
        lay[lair_key(i)] = (w(a), w(a + 2))
    for k in list(STARTS) + list(BLACK_KNIGHTS):
        lay[k] = (w(IMM[k][0]), w(IMM[k][1]))
    return lay


def original_zones(game, rocks_rows=14, shift_cells=0):
    """The game's own grid as 80 x 50 kinds (value 2 in rows 0-13 is rocks, kind 4), or None. shift_cells moves it up
    (the plan: 1 for the probe at the icon's middle, so a border stays under the same feet)."""
    img = original_exe(game)
    if img is None:
        return None
    g = img[DS_IMG + TERRAIN_DS:DS_IMG + TERRAIN_DS + 1000]
    rows = [[4 if (v & 3) == 2 and (v & 4 or y < rocks_rows) else v & 3 for v in g[y * 40:(y + 1) * 40]] for y in range(25)]
    big = []
    for r in rows:
        wide = [v for v in r for _ in (0, 1)]
        big += [wide, wide[:]]
    return big[shift_cells:] + [big[-1][:] for _ in range(shift_cells)]


def game_map(game):
    """(planes, words, pixels) of the game's original map: MAP.CMP.orig if the tool made one, else MAP.CMP."""
    for p in map_files(game)[:1]:
        for q in (p + '.orig', p):
            if os.path.exists(q):
                return read_map(open(q, 'rb').read())
    return None


SWATCH_SIDE, SWATCH_GAP, SWATCH_LABEL, SWATCH_TOP, SWATCH_COLS = 56, 10, 16, 46, 8
SWATCH_BG, SWATCH_TEXT, SWATCH_FIXED, SWATCH_FREE = (24, 22, 20), (240, 236, 220), (118, 118, 118), (250, 220, 40)
# (the frame and text colours are no 12-bit colour expanded: no channel a multiple of 17, so a dropper that misses a
# square never picks a palette colour)


def swatch_boxes(n=32):
    """The palette swatch's squares (x0, y0, x1, y1), inclusive, in palette order: 8 a row."""
    out = []
    for i in range(n):
        x = SWATCH_GAP + (i % SWATCH_COLS) * (SWATCH_SIDE + SWATCH_GAP)
        y = SWATCH_TOP + (i // SWATCH_COLS) * (SWATCH_SIDE + SWATCH_LABEL + SWATCH_GAP)
        out.append((x, y, x + SWATCH_SIDE - 1, y + SWATCH_SIDE - 1))
    return out


def palette_swatch(words, free=FREE_COLOURS):
    """The map's 32 colours as flat squares for a colour dropper (RGB PNG): each square exactly the colour the game shows
    (the 12-bit colour expanded, as the import's nearest-colour match expects, so a picture painted with them imports
    unchanged), its palette index below it; the free entries framed yellow ("free: yours to change"), the others grey
    (used by the game's map sprites). Not game art: 32 colour values."""
    from PIL import Image, ImageDraw, ImageFont
    boxes = swatch_boxes(len(words))
    w = SWATCH_GAP + SWATCH_COLS * (SWATCH_SIDE + SWATCH_GAP)
    h = boxes[-1][3] + SWATCH_LABEL + 44
    img = Image.new('RGB', (w, h), SWATCH_BG)
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((SWATCH_GAP, 8), 'Moonstone map palette: 32 colours. Paint your map with these exact colours', fill=SWATCH_TEXT, font=font)
    d.text((SWATCH_GAP, 24), '(pick them with a colour dropper from the squares).', fill=SWATCH_TEXT, font=font)
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        frame = SWATCH_FREE if i in free else SWATCH_FIXED
        d.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), outline=frame, width=2)
        d.rectangle((x0, y0, x1, y1), fill=word_rgb(words[i]))
        d.text((x0, y1 + 5), f'{i}' + (' free' if i in free else ''), fill=SWATCH_FREE if i in free else SWATCH_TEXT, font=font)
    d.text((SWATCH_GAP, h - 34), 'Yellow frame: free, yours to change (Map > Free colours of the palette).',
           fill=SWATCH_FREE, font=font)
    d.text((SWATCH_GAP, h - 18), "Grey frame: fixed, used by the game's map sprites (knights, lairs, places' outlines).",
           fill=SWATCH_TEXT, font=font)
    return img


SPRITES = [(f'knight_{i}', i) for i in range(10)] + [('lair', LAIR_FRAME)] + \
          [(f'place_{k}', v[1]) for k, v in PLACES.items()]


def export_sprites(game, out_dir, words):
    """The game's map sprites from the player's own DISKB/MI.C as PNG files with transparency; returns the names."""
    frames = read_cel(open(os.path.join(game, 'DISKB', 'MI.C'), 'rb').read())
    os.makedirs(out_dir, exist_ok=True)
    names = []
    for name, f in SPRITES:
        sprite_image(frames[f], words).save(os.path.join(out_dir, name + '.png'))
        names.append(name + '.png')
    return names


# ---- the project (one ZIP) -------------------------------------------------------------------------------------------

PROJECT_FORMAT = 1


class Project:
    """A map mod: zones (80 x 50 rows), the layout, and the picture (None = the game's own map) with its palette."""
    def __init__(self, zones, layout, pixels=None, words=None, name='original', cells='4x4'):
        self.zones, self.layout, self.pixels, self.words, self.name, self.cells = zones, layout, pixels, words, name, cells

    def own_map(self):
        return self.pixels is not None


def save_project(path, p, zones_text):
    """Write the project ZIP: project.txt, zones.csv, places.csv, lairs.csv and, for the player's own picture only,
    map.png (paletted) and palette.txt (its 32 palette words in hex, as MAP.CMP holds them). The game's own map is never put in."""
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.txt', f'format={PROJECT_FORMAT}\nname={p.name}\ncells={p.cells}\n'
                                  f'map={"own" if p.own_map() else "game"}\n')
        z.writestr('zones.csv', zones_text(p.zones))
        z.writestr('places.csv', places_text(p.layout))
        z.writestr('lairs.csv', lairs_text(p.layout))
        if p.own_map():
            b = io.BytesIO()
            pixels_image(p.pixels, p.words).save(b, 'PNG')
            z.writestr('map.png', b.getvalue())
            z.writestr('palette.txt', ' '.join(f'{w:04X}' for w in p.words) + '\n')
    os.replace(tmp, path)


def load_project(path, parse_zones):
    """Read a project ZIP; parse_zones(text) gives the 80 x 50 rows. Everything is checked before it is used."""
    from PIL import Image
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        need = {'project.txt', 'zones.csv', 'places.csv', 'lairs.csv'}
        if not need <= names:
            raise ValueError(f'{os.path.basename(path)}: not a map project (missing {", ".join(sorted(need - names))})')
        meta = dict(ln.split('=', 1) for ln in z.read('project.txt').decode().splitlines() if '=' in ln)
        if int(meta.get('format', 0)) > PROJECT_FORMAT:
            raise ValueError(f'{os.path.basename(path)}: made by a newer tool (format {meta["format"]})')
        zones = parse_zones(z.read('zones.csv').decode())
        layout = parse_layout(z.read('places.csv').decode(), z.read('lairs.csv').decode())
        pixels = words = None
        if meta.get('map') == 'own':
            img = Image.open(io.BytesIO(z.read('map.png')))
            img.load()
            if img.mode != 'P' or img.size != (MAP_W, MAP_H):
                raise ValueError('map.png: must be a paletted 320 x 200 picture')
            if 'palette.txt' in names:
                words = [int(v, 16) for v in z.read('palette.txt').decode().split()]
                if len(words) != 32 or any(not 0 <= v <= 0xffff for v in words):
                    raise ValueError('palette.txt: must be 32 palette words (hex)')
            else:
                pal = list(img.getpalette() or []) + [0] * 96
                words = [rgb_word(pal[i:i + 3]) for i in range(0, 96, 3)]
            pixels = img.tobytes()
            if max(pixels) > 31:
                raise ValueError('map.png: more than 32 colours')
    cells = meta.get('cells', '4x4')
    return Project(zones, layout, pixels, words, meta.get('name', os.path.basename(path)), cells if cells in ('4x4', '2x2') else '4x4')


# ---- apply and restore (the plan's last decisions) -------------------------------------------------------------------

def apply_plan(game, data, limit=MAP_GAME_LEN):
    """What apply_map would do, as lines for the player to confirm; raises ValueError if it cannot be done."""
    if len(data) > limit:
        raise ValueError(f'the map file would be {len(data):,} bytes; the game takes at most {limit:,}. '
                         'Use fewer colours or larger flat areas.')
    lines = []
    for p in map_files(game):
        if not os.path.exists(p) and not os.path.exists(p + '.orig'):
            raise ValueError(f'{p}: not found (is this the game folder?)')
        if not os.path.exists(p + '.orig'):
            lines.append(f'copy {p} to {os.path.basename(p)}.orig (the original, kept for Restore)')
        lines.append(f'write {p} ({len(data):,} bytes)')
    return lines


def ensure_backup(game):
    """Copy each MAP.CMP to MAP.CMP.orig once (never overwritten), checked by size and bytes; raises OSError."""
    for p in map_files(game):
        o = p + '.orig'
        if os.path.exists(o):
            continue
        shutil.copyfile(p, o)
        if os.path.getsize(o) != os.path.getsize(p) or open(o, 'rb').read() != open(p, 'rb').read():
            os.remove(o)
            raise OSError(f'{o}: the backup does not match {p}; nothing was changed')


def _write_all(files):
    """Write {path: bytes} all or nothing: each to a .new file first, then into place; on a failure the files
    already replaced get their old bytes back."""
    old = {p: open(p, 'rb').read() if os.path.exists(p) else None for p in files}
    for p, d in files.items():
        with open(p + '.new', 'wb') as f:
            f.write(d)
    done = []
    try:
        for p in files:
            os.replace(p + '.new', p)
            done.append(p)
    except OSError:
        for p in done:
            if old[p] is None:
                os.remove(p)
            else:
                with open(p, 'wb') as f:
                    f.write(old[p])
        for p in files:
            if os.path.exists(p + '.new'):
                os.remove(p + '.new')
        raise


def apply_map(game, data, limit=MAP_GAME_LEN):
    """Write a new MAP.CMP to DISKB and DISKC: the backup first, then both files or none. limit: the game's own length
    until the rules build patches the copy length (IMM['map_len']), MAP_LIMIT after."""
    apply_plan(game, data, limit)
    ensure_backup(game)
    _write_all({p: data for p in map_files(game)})


def set_ini(path, section, values):
    """Set keys of one section of an ini file in place (the rest of the file, its comments and line ends kept); a
    missing key is added at the section's end, a missing section at the file's end."""
    raw = open(path, 'rb').read().decode('utf-8')
    nl = '\r\n' if '\r\n' in raw else '\n'
    lines = raw.split(nl)
    start = next((i for i, ln in enumerate(lines) if ln.strip().lower() == f'[{section.lower()}]'), None)
    if start is None:
        lines += [f'[{section}]'] + [f'{k} = {v}' for k, v in values.items()] + ['']
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith('[')), len(lines))
        todo = dict(values)
        for i in range(start + 1, end):
            key = lines[i].split('=', 1)[0].strip().lower() if '=' in lines[i] and not lines[i].lstrip().startswith(';') else None
            if key in todo:
                rest = lines[i].split('=', 1)[1]
                comment = rest[rest.index(';'):] if ';' in rest else ''
                lines[i] = f'{lines[i].split("=", 1)[0].rstrip()} = {todo.pop(key)}'
                lines[i] = (lines[i].ljust(36) + comment) if comment else lines[i]
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = [f'{k} = {v}' for k, v in todo.items()]
    with open(path + '.tmp', 'wb') as f:
        f.write(nl.join(lines).encode('utf-8'))
    os.replace(path + '.tmp', path)


def is_install(game):
    """A Moonstone Rebuilt installation the map tool may apply to: Setup's fixed MAIN.EXE and the map files there."""
    return os.path.exists(os.path.join(game, '_fixes', 'fixed', 'MAIN.EXE')) and \
        all(os.path.exists(p) or os.path.exists(p + '.orig') for p in map_files(game))


def _snapshot(paths):
    return {p: open(p, 'rb').read() if os.path.exists(p) else None for p in paths}


def _put_back(snap):
    for p, d in snap.items():
        if d is None:
            if os.path.exists(p):
                os.remove(p)
        else:
            with open(p, 'wb') as f:
                f.write(d)


def apply_project(game, data, save, rebuild, keep=()):
    """Apply a project to the game folder, all or nothing: the map picture (data, MAP.CMP bytes, or None for the game's
    own map, the original put back if the tool had changed it), then save() (the zones' and places' files), [Map]
    custom_terrain and custom_places on in custom_rules.ini, then rebuild() (the rules build). On any failure the map
    files, the files in keep and custom_rules.ini are put back as they were and the error raised."""
    if data is not None:
        apply_plan(game, data, MAP_LIMIT)
    ini = os.path.join(game, 'custom_rules.ini')
    snap = _snapshot(list(map_files(game)) + list(keep) + [ini])
    try:
        if data is not None:
            ensure_backup(game)
            _write_all({p: data for p in map_files(game)})
        elif all(os.path.exists(p + '.orig') for p in map_files(game)):
            restore_original(game)
        save()
        if not os.path.exists(ini):
            shutil.copyfile(os.path.join(game, 'custom_rules-default.ini'), ini)
        set_ini(ini, 'Map', {'custom_terrain': 'on', 'custom_places': 'on'})
        rebuild()
    except Exception:
        _put_back(snap)
        raise


def restore_all(game, rebuild):
    """Restore original: both MAP.CMP from .orig (if the tool ever changed them), custom_places and custom_terrain off,
    the rules rebuilt. Needs no project file. On a failure of the rebuild the ini is put back (the map stays original)."""
    restored = restore_original(game) if all(os.path.exists(p + '.orig') for p in map_files(game)) else []
    ini = os.path.join(game, 'custom_rules.ini')
    snap = _snapshot([ini])
    try:
        if os.path.exists(ini):
            set_ini(ini, 'Map', {'custom_terrain': 'off', 'custom_places': 'off'})
        rebuild()
    except Exception:
        _put_back(snap)
        raise
    return restored


def restore_original(game):
    """Put both MAP.CMP files back from MAP.CMP.orig (works without any project file). Returns the files restored."""
    files = {}
    for p in map_files(game):
        if not os.path.exists(p + '.orig'):
            raise ValueError(f'{p}.orig not found: the map was never changed by the tool')
        files[p] = open(p + '.orig', 'rb').read()
    _write_all(files)
    return list(files)
