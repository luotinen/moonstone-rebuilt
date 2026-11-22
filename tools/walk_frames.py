"""D143: the in-between poses of the knight's walk (docs/smooth-animation-plan-2026-11-19.md, sections 13 and 14).

The walk is four poses in a loop (KN1.OB legs / torso 5/4 -> 7/6 -> 9/8 -> 3/2 -> 5/4; HE1.OB is the second knight
look, the same pieces in other colours). For each of the four pose changes this makes five body pictures, at the
sixths of the tick, from the user's own files, by the layered recipe the user approved on 19 Nov 2026 (the sample
research/smooth-animation-2026-11-19/walk_poses.py, whose pictures these equal pixel for pixel):

  * the body (legs piece + torso piece) is composed as one picture and cut into layers: the upper body (above the
    hip row), the two legs with their halves of the robe (a split line per pose) and the shadow under each foot;
  * the upper body only travels (UPPER_STEP: found by matching in the sample, shipped here as numbers);
  * each leg is leaned about the hip: its rows keep their pixels and are moved as whole rows, the top row with the
    upper body, the foot rows with the foot, the rows between in proportion;
  * the standing foot is the picture's origin; the swinging foot goes in a straight line to its place in the new pose;
  * up to SWITCH the old pose's layers are shown leaned forward, after it the new pose's leaned back;
  * pixels are only moved, never mixed; the sword is not in the picture (the game's own piece is drawn).

The pictures go into SAVEHOOK.INB (the layout: WK_SLOT in make_savehook.py), which SAVEHOOK.COM reads into XMS.
Nothing made here is distributed: Setup runs this on the user's files. Pure Python: no numpy (the arithmetic is kept
in the sample's order, in floats, so the rounding is the same).
Usage: python -I tools/walk_frames.py <game dir> [<folder for SAVEHOOK.INB>]"""
import os, struct, sys
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_savehook import WK_SLOT, WK_SLOTS, WK_MAGIC, WK_SUM, WK_BIAS, WK_WHOLE, WK_BANK, WK_LOOP, WK_TORSO, WK_FAR, ATK_K, INB_SLOTS
from death_frames import read_bank, frame_pixels, frame_planes

BANKS = ('KN1.OB', 'HE1.OB')               # look 0, look 1 (in DISKB)
INB_NAME = 'SAVEHOOK.INB'
SHADOW = 5                                 # the colour of the shadow dither under the feet
FOOT_ROWS = 3                              # a foot's own rows are not leaned: they move with the foot
PAD = 40                                   # the work canvas' margin
FRACTIONS = [1 / 6, 1 / 3, 1 / 2, 2 / 3, 5 / 6]

# The recipe, one entry a pose, keyed by the legs frame. Coordinates: the composed body's own box, facing left
# (column 0 = the leftmost column of the two pieces' word-wide arrays, row 0 = the plume's top row).
#   hip     the first row of the legs layers (the upper body is everything above)
#   shadow  the first row whose pixels of colour 5 are the shadow
#   split   the line between the left and the right leg: (row, column) points, a pixel left of it is the left leg's
#   left    which leg the left one is: 'far' or 'near' (the near leg is drawn over the far one)
#   foot    optional (x, y) of a leg's lowest point where the picture's own lowest rows are not it
RECIPE = {
    5: dict(hip=32, shadow=56, left='far', split=[(32, 27), (42, 27), (43, 28), (70, 28)]),
    7: dict(hip=32, shadow=54, left='near', split=[(32, 21.5), (45, 21.5), (46, 18.5), (70, 18.5)], foot={'near': (15, 54)}),
    9: dict(hip=32, shadow=54, left='near', split=[(32, 29.5), (38, 29.5), (39, 28.5), (70, 28.5)]),
    3: dict(hip=32, shadow=56, left='far',
            split=[(32, 22.5), (37, 22.5), (38, 20.5), (47, 20.5), (48, 21.5), (50, 21.5), (51, 22.5), (56, 22.5),
                   (57, 19.5), (70, 19.5)]),
}
PLANTED = {5: 'far', 7: 'far', 9: 'near', 3: 'near'}   # the leg on the ground during the change that starts from this pose
SWITCH = {5: 4 / 6, 7: 3 / 6, 9: 4 / 6, 3: 3 / 6}      # from this fraction on the new pose's layers are shown
# how far the upper body of this pose travels to lie on the next pose's (the sample's upper_step, by matching)
UPPER_STEP = {5: (-7, 0), 7: (7, 1), 9: (-5, -1), 3: (5, 0)}


class WalkError(Exception):
    """The files are not the game's walk pieces (the frames file is then not made: the walk is drawn in place)."""


def padded(w): return (w + 15) // 16 * 16


class Pose:
    """One walk pose, facing left, composed and cut into its layers."""
    def __init__(self, frame, legs, torso):
        r = RECIPE[frame]
        self.frame, self.hip = frame, r['hip']
        wl, wt = len(legs[0]), len(torso[0])
        self.legs_pad, self.legs_aw = padded(wl) - wl, padded(wl)
        tdx, tdy = WK_TORSO[frame][1]
        # the pieces' word-wide arrays as the game holds them turned to the left: the padding first, then the
        # frame mirrored; the legs piece is drawn at (0, 0), the torso piece at (tdx, tdy)
        ol, ot = (-self.legs_pad, 0), (tdx - (padded(wt) - wt), tdy)
        x0, y0 = min(ol[0], ot[0]), min(ol[1], ot[1])
        self.w = w = max(ol[0] + padded(wl), ot[0] + padded(wt)) - x0
        self.h = h = max(ol[1] + len(legs), ot[1] + len(torso)) - y0
        self.legs_at = (ol[0] - x0, ol[1] - y0)
        pic = self.pic = [[0] * w for _ in range(h)]
        for a, o in ((legs, ol), (torso, ot)):               # the game's order: legs, then torso
            pad = padded(len(a[0])) - len(a[0])
            for y, row in enumerate(a):
                for x, v in enumerate(row[::-1]):
                    if v: pic[y + o[1] - y0][x + pad + o[0] - x0] = v
        pts = r['split']
        for (r0, c0), (r1, c1) in zip(pts, pts[1:]):         # exact at every row: a span is flat or one row long
            if c0 != c1 and r1 - r0 != 1: raise WalkError(f'recipe {frame}: a slanted split span')
        def split(y):
            if y <= pts[0][0]: return pts[0][1]
            for (r0, c0), (r1, c1) in zip(pts, pts[1:]):
                if y <= r1: return c0 if y < r1 else c1
            return pts[-1][1]
        other = 'near' if r['left'] == 'far' else 'far'
        self.upper, self.leg, self.shade = set(), {'far': set(), 'near': set()}, {'far': set(), 'near': set()}
        for y in range(h):
            s = split(y)
            for x in range(w):
                v = pic[y][x]
                if not v: continue
                side = r['left'] if x < s else other
                if v == SHADOW and y >= r['shadow']: self.shade[side].add((y, x))
                elif y >= r['hip']: self.leg[side].add((y, x))
                else: self.upper.add((y, x))
        self.foot, self.foot_exact = {}, {}
        for k, m in self.leg.items():
            if not m: raise WalkError(f'pose {frame}: no {k} leg')
            if k in r.get('foot', {}):
                self.foot_exact[k] = tuple(Fraction(v) for v in r['foot'][k])
                self.foot[k] = tuple(float(v) for v in r['foot'][k]); continue
            low = max(y for y, x in m)
            xs = [x for y, x in m if y >= low - 1]           # the lowest two rows: the sole
            self.foot_exact[k] = (Fraction(sum(xs), len(xs)), Fraction(low))
            self.foot[k] = (sum(xs) / len(xs), float(low))


def _put_rows(out, pic, mask, shift):
    """Move a layer's rows: shift(row) -> (dx, dy). Rows keep their pixels; a stretched layer repeats a row, a
    squeezed one lets the lower row win."""
    rows = {}
    for y, x in mask: rows.setdefault(y, []).append(x)
    prev = None
    for y in sorted(rows):
        dx, dy = shift(y)
        d = int(round(y + dy)); x = int(round(dx))
        lo = d if prev is None or d <= prev + 1 else prev + 1
        for r in range(lo, d + 1):
            for c in rows[y]: out[r + PAD][c + x + PAD] = pic[y][c]
        prev = d if prev is None else max(prev, d)


def inbetween(a, b, j):
    """The in-between picture of poses a -> b, j sixths of the way (1-5), facing left: (rows, the standing foot's
    (x, y) in it as exact fractions)."""
    t = FRACTIONS[j - 1]
    planted = PLANTED[a.frame]; swing = 'near' if planted == 'far' else 'far'
    us = UPPER_STEP[a.frame]
    D = tuple(us[i] - b.foot[planted][i] + a.foot[planted][i] for i in (0, 1))   # the upper body's step, the foot standing
    E = {planted: (0.0, 0.0),
         swing: tuple((b.foot[swing][i] - b.foot[planted][i]) - (a.foot[swing][i] - a.foot[planted][i]) for i in (0, 1))}
    src, f = (a, t) if t < SWITCH[a.frame] - 1e-9 else (b, t - 1.0)
    out = [[0] * (src.w + 2 * PAD) for _ in range(src.h + 2 * PAD)]
    for k in ('far', 'near'):                                # shadows first: under everything
        if src.shade[k]: _put_rows(out, src.pic, src.shade[k], lambda y, k=k: (f * E[k][0], 0.0))
    for k in ('far', 'near'):                                # the near leg over the far one
        ankle = src.foot[k][1] - FOOT_ROWS
        def shift(y, k=k, ankle=ankle):
            w = min(1.0, max(0.0, (y - src.hip) / max(1.0, ankle - src.hip)))
            return tuple(f * (D[i] * (1 - w) + E[k][i] * w) for i in (0, 1))
        _put_rows(out, src.pic, src.leg[k], shift)
    _put_rows(out, src.pic, src.upper, lambda y: (f * D[0], f * D[1]))
    ys = [y for y, row in enumerate(out) if any(row)]
    xs = [x for row in out for x, v in enumerate(row) if v]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    foot = src.foot_exact[planted]
    return [row[x0:x1 + 1] for row in out[y0:y1 + 1]], (foot[0] + PAD - x0, foot[1] + PAD - y0)


def poses(bank):
    """The four walk poses of a bank file's bytes, facing left: {legs frame: Pose}."""
    frames, raw = read_bank(bank)
    if len(frames) < 10: raise WalkError('fewer than 10 frames')
    out = {}
    for f in WK_LOOP:
        legs, torso = frame_pixels(raw, *frames[f]), frame_pixels(raw, *frames[f - 1])
        out[f] = Pose(f, legs, torso)
    return out


def look_frames(bank):
    """One look's pictures and places: {(facing, legs frame of the old pose, j): (rows, cx, cy)}; facing 0 = right,
    1 = left; (cx, cy) as WK_SLOT says (place())."""
    P = poses(bank)
    out = {}
    for i, fa in enumerate(WK_LOOP):
        a, b = P[fa], P[WK_LOOP[(i + 1) % 4]]
        planted = PLANTED[fa]
        for j in range(1, 6):
            pic, foot = inbetween(a, b, j)
            w = len(pic[0])
            # the standing foot on the screen from a tick's legs piece drawn at x (left: the piece's visible columns
            # begin at x, its array's padding left of it; right: the body mirrored)
            left = [-p.legs_pad - p.legs_at[0] + p.foot_exact[planted][0] for p in (a, b)]
            right = [p.legs_at[0] + p.legs_aw - 1 - p.foot_exact[planted][0] for p in (a, b)]
            up = [-p.legs_at[1] + p.foot_exact[planted][1] for p in (a, b)]
            def c(pair, own):                                # six times the constant part of the place, + 3 to round
                v = (6 - j) * pair[0] + j * pair[1] - 6 * own + 3
                n = v.numerator // v.denominator + 6 * WK_BIAS
                if not 5 * WK_FAR <= n < 0x8000: raise WalkError('a place constant out of range')
                return n | (WK_WHOLE if v.denominator == 1 else 0)
            cy = c(up, foot[1])
            out[(1, fa, j)] = (pic, c(left, foot[0]), cy)
            out[(0, fa, j)] = ([row[::-1] for row in pic], c(right, w - 1 - foot[0]), cy)
    return out


def place(entry, j, xa, ya, xb, yb):
    """Where in-between picture j of an entry of look_frames() is drawn when the legs piece was drawn at (xa, ya)
    the tick before and is drawn at (xb, yb) now (as SAVEHOOK.COM works it out)."""
    def part(a, b, c):                                       # rounded to the nearest pixel, an exact half to the even one
        q, r = divmod(j * (b - a) + (c & ~WK_WHOLE), 6)
        v = a + q - WK_BIAS
        return v - 1 if c & WK_WHOLE and r == 0 and v & 1 else v
    _, cx, cy = entry
    return part(xa, xb, cx), part(ya, yb, cy)


def slot_number(look, facing, fa, j):
    return 1 + ((look * 2 + facing) * 4 + (fa - 3) // 2) * 5 + (j - 1)


def slot_bytes(entry):
    pic, cx, cy = entry
    mask, planes = frame_planes(pic)
    s = (struct.pack('<HH', cx, cy) + b'\x00\x01' + bytes(8) + struct.pack('>IHHH', 0, len(pic[0]), len(pic), mask) + planes)
    if len(s) > WK_SLOT: raise WalkError(f'a picture of {len(s)} bytes: more than a slot ({WK_SLOT})')
    return s + bytes(WK_SLOT - len(s))


def build(game, attacks=True):
    """SAVEHOOK.INB's bytes from the game folder's DISKB/KN1.OB and HE1.OB; D146: then the attack part
    (attack_frames.py, from KN1/KN2.OB, HE1/HE2.OB and KN4.OB), or the walk's slots alone when those files are not
    the game's pieces (the attacks are then drawn in place; SAVEHOOK.COM tells the two by the file's length)."""
    slots = [None] * WK_SLOTS
    for look, name in enumerate(BANKS):
        with open(os.path.join(game, 'DISKB', name), 'rb') as fh: bank = fh.read()
        for (facing, fa, j), entry in look_frames(bank).items():
            slots[slot_number(look, facing, fa, j)] = slot_bytes(entry)
    if attacks:
        import attack_frames
        try:
            more = attack_frames.build(game, ATK_K)
            if WK_SLOTS + len(more) == INB_SLOTS: slots += more
        except (attack_frames.AttackError, OSError, ValueError, IndexError, KeyError, ZeroDivisionError, struct.error):
            pass
    slots[0] = (WK_MAGIC + struct.pack('<HH', WK_SLOT, len(slots))).ljust(WK_SLOT, b'\0')
    data = bytearray(b''.join(slots))
    # the header's fifth word makes the file's words add up to WK_SUM: SAVEHOOK.COM's check of the file and its layout
    total = sum(struct.unpack(f'<{len(data) // 2}H', data)) & 0xffff
    struct.pack_into('<H', data, 8, (WK_SUM - total) & 0xffff)
    return bytes(data)


def install(game, folder=None):
    """Writes SAVEHOOK.INB (into the game folder, or folder). Returns its path, or None when the files are not the
    game's walk pieces (an old file is removed: the walk is then drawn in place). D147: first turns the held dagger
    in the game folder's KN4.OB to be held by its hilt (attack_frames.held_dagger)."""
    path = os.path.join(folder or game, INB_NAME)
    try:                                                     # D147: the no-spin throw's dagger, held by its hilt
        import attack_frames
        attack_frames.held_dagger(game)
    except Exception:                                        # (not the game's KN4.OB: left as it is)
        pass
    try:
        data = build(game)
    except (WalkError, OSError, ValueError, IndexError, struct.error):
        if os.path.exists(path): os.remove(path)
        return None
    with open(path, 'wb') as fh: fh.write(data)
    return path


if __name__ == '__main__':
    out = install(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(out or 'not made: the walk pieces are not the game\'s')
