"""D146-D148: the in-between poses of the knight's attacks (docs/smooth-animation-plan-2026-11-19.md, sections 15-17).

D146: the swing, the overhead chop and the lunge, with the fast swing and the riposte that share their pictures, and
the hit endings (a striking frame back to the ready pose 0C92); D147: the backward thrust (with its hit endings), the
fast backward thrust, the upward thrust, the dagger throw (and the throw again while its key is held), the block and
the dodge; D148: the moves begun straight from a held block, dodge or thrown pose: the pose changes of
make_savehook.ATK_CHANGES. For each change this makes five pictures of the whole knight (body, sword and motion
arcs), at the sixths of the tick, for both knight looks (KN1/KN2.OB, HE1/HE2.OB) and both facings, from the user's
own files, by the layered recipe the user approved on 20 Nov 2026 (the sample
research/smooth-animation-2026-11-19/attack_poses.py) with the fixes the user approved on 21 Nov 2026 after
reviewing every picture (plan 16.4; the sample research/smooth-animation-2026-11-19/attack_frames_v2.py with
rigid=True, whose pictures these equal pixel for pixel):

  * the body pieces of a frame are composed into one picture and cut at the hip row (the belt) into the upper body
    and the two legs (split where the feet's columns have a gap); a body pixel of a piece drawn after the sword
    piece is drawn over the sword; the upper body takes OVERLAP rows of the legs too (no break at the waist) and the
    hands below the hip row near the sword's grip (fixes 6, 7);
  * the upper body is turned about the pivot (the middle of the waist on the hip row) and moved: the turn and the
    step were found by matching in the sample and are shipped here as numbers (RECIPE); the moved pivot is put on a
    whole pixel and a half always rounds up (fix 1: a layer that only moves is copied pixel for pixel);
  * the legs are one continuous warp, every pixel fetched from its source: at the hip row each point goes where the
    turned upper body takes it, at the feet where its foot goes, evenly in between (fix 7);
  * in-betweens before the switch show the old pose's layers turned and moved forward, from it on the new pose's
    turned and moved back;
  * the lunge's and the riposte's changes (LUNGE) do not turn the upper body: it moves by the grip's own rows, so the
    blade goes straight from the old pose's row to the new one's; the riposte's own change (RIPOSTE) goes as a
    faster lunge, the blade level by the time the arm reaches out, then up from the lunge's stance row (fixes 2, 2b);
  * the sword is never part of the body: the game's own sword picture nearest the angle, hung in the hands; the
    angle turns with the upper body (the arm's extension), never back against the sword's way nor past the new
    pose's angle; a sweep past half a turn, and the lunge's, goes evenly (fix 5a);
  * the new pose's motion arc only over the angle the sword has swept so far, hung from the sword's grip in the
    picture; the old one's shrinks away by mid-tick; no trail pixel ahead of the sword's way or beyond where its
    blade has reached (fix 4).

D147 (the sample research/smooth-animation-2026-11-19/attack_frames_d147.py, approved by the user on 21 Nov 2026 with
its proposals P1 and P2; plan section 17), whose pictures these equal pixel for pixel:
  * the upward thrust keeps the sword on its line (UP_LINE, P1): no turn of the upper body, only the recipe's step;
  * the fast backward thrust goes the backward thrust's way round, down in front and back (RECIPE, P2);
  * the dagger in the hand (KN4.OB frame 9) moves with the body's layers but is the sword's part (WPN: the game draws
    every KN4 piece of a knight in the weapon's colour state); a no-spin throw: the knight holds it by its hilt, the
    point away from him (dagger_by_hilt, which Setup also writes into KN4.OB: held_dagger), and keeps it in the fist
    through the throw until the game's thrown frame (KEEP_DAGGER, dagger_picture);
  * a pose without a sword (the thrown pose): the other pose's sword turns with its upper body; a change into a pose
    with no KN4 piece is all the body's part (the pictures of a tick take their colour states from its pieces).

D148 (the sample research/smooth-animation-2026-11-19/attack_frames_d148.py, approved by the user on 21 Nov 2026 with
its proposals P3 and P4; plan section 18), whose pictures these equal pixel for pixel:
  * the game goes from the block (pose 19), the dodge (26) and the thrown pose (25) straight into the next move when
    the keys change: 21 changes from each of the three into the swing's wind-up, the lunge's stance, the riposte's
    reach, the ready pose, the fast backward thrust's thrust back, the throw's raised pose and the other defence;
  * each follows the rule of the same move's start from standing (LUNGE, RIPOSTE: into the lunge's stance and the
    riposte's reach the upper body only moves);
  * from the dodge into the swing (P3) and into the fast backward thrust (P4) the sword goes over the head forward,
    down in front and back (RECIPE -228 and -275), as from standing.

Each picture is stored as two parts: the pixels drawn in the body's colour state and those drawn in the sword's (the
game tints a knight's body by its armour and its sword by its weapon, D31, and moves an HE knight's sword colours,
he_shared): SAVEHOOK.COM draws each part with the colour state of the piece it comes from. A part is cut into
strips of whole rows, each a frame of its own with its place; the strips are packed into slots of WK_SLOT bytes,
each a bank of frames (ATK_* in make_savehook.py), so that one slot at a time goes through BUF_WALK.

Pure Python: no numpy (the arithmetic is kept in the sample's order, in floats, so the rounding is the same).
Nothing made here is distributed: Setup runs this on the user's files (through walk_frames.build).
Usage: python -I tools/attack_frames.py <game dir>     (the sizes; the file is made by walk_frames.py)"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_savehook import ATK_POSES, ATK_CHANGES, ATK_SWORDS, ATK_REC, ATK_RECS, ATK_BANK, ATK_LAST, ATK_MORE, WK_SLOT, BUF_WALK
from death_frames import read_bank, frame_pixels, frame_planes

LOOKS = (('KN1.OB', 'KN2.OB'), ('HE1.OB', 'HE2.OB'))  # look 0, look 1 (in DISKB); KN4.OB is both looks' sword
SWORDS = ATK_SWORDS                             # KN4.OB: the sword at its angles
ARCS = tuple(range(11, 24))                     # KN4.OB: the motion arcs
SHADOW = 5
OVER = 0x20                                     # a body pixel drawn over the sword (a piece after the sword piece)
WPN = 0x40                                      # D147: a pixel of a KN4 piece in the body's layers (the dagger in hand):
                                                # moved with the body, drawn in the sword's colour state
PAD = 90                                        # the work canvas' margin
J = (1, 2, 3, 4, 5)                             # the in-betweens at the sixths of the tick
# The recipe of each change of ATK_CHANGES, in its order: the upper body's turn (degrees, counter-clockwise on the
# screen, facing right) and step (pixels) found by matching the old pose's upper body onto the new one's; the switch
# (the first in-between that shows the new pose's layers); the sword's way round in degrees where it is not the
# short one (None: the short way)
RECIPE = [
    (-2, (-1, 0), 3, -198), (-14, (5, 2), 3, None), (-9, (-1, 6), 3, None), (-3, (4, -1), 3, None),
    (76, (3, -4), 3, None), (0, (0, 0), 3, None), (-29, (0, 0), 3, None), (4, (-7, -1), 3, None),
    (-6, (6, 2), 3, 198), (-3, (-3, 1), 3, None), (26, (2, -5), 3, None), (28, (0, -1), 3, None),
    (-29, (0, 0), 3, None),
    (-12, (5, 2), 3, 255),                      # (the long way: pose 2's own trail shows the sword from behind, fix 4)
    (-17, (1, 2), 3, None), (-26, (-5, 4), 3, None), (0, (13, -2), 3, None), (-2, (-1, 0), 3, None),
    (0, (0, 0), 3, None), (71, (3, 3), 2, None), (18, (-2, -1), 3, None), (11, (3, 0), 3, None),
    (26, (2, -5), 3, None), (43, (-4, 3), 3, None), (84, (4, 6), 3, None), (83, (6, 3), 3, None),
    (-106, (-4, -4), 3, None),
    (-8, (5, 2), 3, None), (11, (-2, 1), 3, None), (-19, (-1, 0), 3, None), (-21, (-2, 3), 3, None),
    (-30, (4, -2), 3, None), (-1, (0, 0), 3, None), (-1, (0, 0), 3, None), (82, (2, 0), 3, None),
    (-6, (4, -1), 3, None), (8, (3, 0), 3, None), (14, (-1, -3), 3, None), (46, (-2, 2), 3, None),
    (46, (-2, 2), 3, None), (52, (-2, 1), 3, None),
    (7, (2, 0), 3, None),
    # D147 (42-58): the backward thrust, its hit endings, the fast backward thrust, the upward thrust, the dagger
    # throw, the block, the dodge, the throw again
    (-2, (2, -1), 3, None), (-10, (-6, -1), 3, None), (0, (0, 0), 3, None), (13, (3, 0), 3, None),
    (7, (0, 1), 3, None), (13, (3, 0), 3, None),
    (-44, (-4, 0), 3, -246),                    # (P2: the backward thrust's way, down in front and back)
    (-36, (-6, -1), 3, None), (34, (5, -2), 3, None),
    (11, (4, 3), 3, None), (-58, (-3, -2), 3, None), (43, (-1, -2), 3, None),
    (-21, (4, 2), 3, None), (22, (-4, -1), 3, None),
    (-10, (2, 1), 3, None), (14, (-1, -1), 3, None),
    (62, (4, -2), 3, None),
    # D148: from the block (59-65), from the dodge (66-72), from the thrown pose (73-79)
    (17, (-5, 0), 3, None), (-3, (-5, 0), 3, None), (-37, (-8, -1), 3, None), (7, (0, 1), 3, None),
    (-10, (-6, -1), 3, None), (46, (4, 0), 3, None), (1, (-5, 0), 3, None),
    (-2, (-7, 0), 3, -228),                     # (P3: into the swing down in front, as from standing)
    (-2, (0, 0), 3, None), (-36, (-5, 0), 3, None), (-6, (0, 0), 3, None),
    (-5, (0, 0), 3, -275),                      # (P4: into the fast backward thrust down in front and back, as P2)
    (-10, (-9, 3), 3, None), (-2, (5, 0), 3, None),
    (53, (3, -4), 3, None), (20, (0, 0), 3, None), (-7, (-5, 4), 3, None), (26, (2, 0), 3, None),
    (25, (2, 1), 3, None), (14, (1, 0), 3, None), (22, (-1, 0), 3, None)]
UP_LINE = {49, 50}                              # the upward thrust (P1): no turn, so the sword stays on its line
KEEP_DAGGER = {52: ((58, 8.5), 0)}               # the throw (24 -> 25): the dagger stays in the hand in the pictures of
                                                # the thrown pose's layers (the game frame has it gone: the flying one
                                                # comes the tick after): its hilt at this point of pose 25 (the fist),
                                                # its point away along the arm (degrees), turned with the upper body
DAGGERS = (9, 10)                               # KN4.OB: the dagger held (diagonal) and flying (level)
HELD_DAGGER = 9                                 # KN4.OB: the held dagger, turned to be held by its hilt (dagger_by_hilt)
LUNGE = {14, 15, 16, 17, 18, 19, 20, 26, 60, 61, 67, 68, 74, 75}   # the lunge's and the riposte's changes (D148: and
                                                # the starts into them from a held pose): the upper body only moves
RIPOSTE = {26: 8, 61: 8, 68: 8, 75: 8}          # the riposte's starts: as the lunge's, through this pose's grip row
OVERLAP = 2                                     # rows of the legs also in the upper body
HAND_R = 9                                      # pixels below the hip this near the sword's grip are the hands
ROOM = WK_SLOT - ATK_BANK - 10                  # a slot: ATK_RECS records, the bank's header, then its frames
FRAME_HEAD = 10                                 # a frame: its entry in the bank, then its planes


class AttackError(Exception):
    """The files are not the game's knight pieces (the attacks are then drawn in place)."""


def nonzero(a):
    """(ys, xs) of a picture's nonzero pixels in row-major order (numpy.nonzero's order)."""
    ys, xs = [], []
    for y, row in enumerate(a):
        for x, v in enumerate(row):
            if v: ys.append(y); xs.append(x)
    return ys, xs


def wrap(d): return (d + math.pi) % (2 * math.pi) - math.pi


def R(v):
    """Rounded, a half always up (Python's round takes a half to the even number: rows doubled and left out)."""
    return int(math.floor(v + 0.5))


def dagger_by_hilt(a):
    """D147 (the user, 21 Nov 2026: a no-spin throw, the knight holds the dagger by its hilt, the point away from him):
    KN4.OB's held dagger (frame 9) turned half round in its own box, so that at the same place its hilt is in the
    raised fist and its point up and back; a picture already turned (its hilt's dark pixels in the lower right half)
    is returned as it is, so that making it twice changes nothing. The game draws this frame only in the dagger
    throw's raised pose (scripts 0DF8-0E40)."""
    dk = [(y, x) for y, r in enumerate(a) for x, v in enumerate(r) if v in (4, 5)]
    if not dk: return a
    h, w = len(a), len(a[0])
    if sum(y for y, x in dk) / len(dk) > (h - 1) / 2 and sum(x for y, x in dk) / len(dk) > (w - 1) / 2: return a
    return [r[::-1] for r in a[::-1]]


def held_dagger(game):
    """D147: Setup turns the held dagger (KN4.OB frame 9) in the game folder's DISKB/KN4.OB to be held by its hilt
    (dagger_by_hilt; the user chose to change it in place, so the original game shows it so too). The bank is packed
    again and filled with zeros to its own length (the game's EMS file cache has KN4.OB's place just this big: the
    files after it are not moved). Returns True when the file was written, False when it already holds the turned
    frame; raises AttackError when it is not the game's KN4.OB."""
    import death_frames
    path = os.path.join(game, 'DISKB', 'KN4.OB')
    with open(path, 'rb') as fh: data = fh.read()
    frames, raw = read_bank(data)
    if len(frames) < 25: raise AttackError('KN4.OB: fewer than 25 frames')
    off, w, h, mask = frames[HELD_DAGGER]
    img = frame_pixels(raw, off, w, h, mask)
    new = dagger_by_hilt(img)
    if new is img: return False
    m2, planes = frame_planes(new)
    if m2 != mask or len(planes) != len(frame_planes(img)[1]): raise AttackError('KN4.OB: frame 9 is not the dagger')
    raw = bytearray(raw); raw[off:off + len(planes)] = planes
    packed = death_frames.lz_encode(bytes(raw))
    out = (struct.pack('>HII', len(frames), len(packed), len(raw) * 8) +
           b''.join(struct.pack('>IHHH', *f) for f in frames) + packed)
    if len(out) > len(data): raise AttackError(f'KN4.OB: {len(out)} bytes packed again, its place holds {len(data)}')
    with open(path, 'wb') as fh: fh.write(out.ljust(len(data), b'\0'))
    return True


class Banks:
    """One look's pieces: {0: KN1/HE1 frames, 1: KN2/HE2 frames, 3: KN4 frames}, each a list of rows."""
    def __init__(self, game, look):
        self.f = {}
        for idx, name in ((0, LOOKS[look][0]), (1, LOOKS[look][1]), (3, 'KN4.OB')):
            with open(os.path.join(game, 'DISKB', name), 'rb') as fh: frames, raw = read_bank(fh.read())
            self.f[idx] = [frame_pixels(raw, *fr) for fr in frames]
        if len(self.f[3]) > HELD_DAGGER: self.f[3][HELD_DAGGER] = dagger_by_hilt(self.f[3][HELD_DAGGER])


def sword_geometry(kn4):
    """KN4 sword frames: {frame: (grip u, grip v, angle in radians (u right, v up), length)}. The grip is the middle
    of the dark grip and guard pixels (colours 3 and 4); the angle points from it to the farthest blade pixel."""
    out = {}
    for n in SWORDS:
        a = kn4[n]
        ys, xs = nonzero(a)
        dk = [i for i in range(len(ys)) if a[ys[i]][xs[i]] in (3, 4)]
        gx = sum(xs[i] for i in dk) / len(dk); gy = sum(ys[i] for i in dk) / len(dk)
        d = [math.hypot(x - gx, y - gy) for x, y in zip(xs, ys)]
        k = d.index(max(d))
        out[n] = (gx, gy, math.atan2(-(ys[k] - gy), xs[k] - gx), float(d[k]))
    return out


class Pose:
    """One frame of a knight's script (a key of ATK_POSES), composed in the banks' orientation (facing right)."""
    def __init__(self, key, B, SW):
        F = B.f
        body = [(b, n, dy, dx, i) for i, (b, n, dy, dx) in enumerate(key)
                if b in (0, 1) or (b == 3 and n not in SWORDS and n not in ARCS)]
        sw = [(i, n, dy, dx) for i, (b, n, dy, dx) in enumerate(key) if b == 3 and n in SWORDS]
        self.arcs = [(n, dy, dx) for (b, n, dy, dx) in key if b == 3 and n in ARCS]
        self.sword, si = None, 99
        if sw:
            si, n, dy, dx = sw[0]
            gx, gy, ang, ln = SW[n]
            self.sword = dict(n=n, grip=(dx + gx, dy + gy), ang=ang, len=ln)
        u0 = min(dx for b, n, dy, dx, i in body); v0 = min(dy for b, n, dy, dx, i in body)
        u1 = max(dx + len(F[b][n][0]) for b, n, dy, dx, i in body); v1 = max(dy + len(F[b][n]) for b, n, dy, dx, i in body)
        h, w = v1 - v0, u1 - u0
        pic = [[0] * w for _ in range(h)]
        for b, n, dy, dx, i in body:                          # the game's order
            over = (OVER if i > si else 0) | (WPN if b == 3 else 0)   # D147: the dagger in hand: the sword's part
            for y, row in enumerate(F[b][n]):
                prow = pic[y + dy - v0]
                for x, v in enumerate(row):
                    if v: prow[x + dx - u0] = v | over
        self.pic, self.u0, self.v0, self.h, self.w = pic, u0, v0, h, w
        self._layers()

    def _layers(self):
        h, w, P = self.h, self.w, self.pic
        pic = [[v & 0x1F for v in row] for row in P]
        red = [[6 <= v <= 11 for v in row] for row in pic]
        # the hip: the belt, the row with the most black pixels that have the robe's red right above and below
        belt = []
        for y in range(h):
            n = 0
            for x in range(w):
                if pic[y][x] == SHADOW and ((y >= 1 and red[y - 1][x]) or (y >= 2 and red[y - 2][x])) and \
                        ((y + 1 < h and red[y + 1][x]) or (y + 2 < h and red[y + 2][x])):
                    n += 1
            belt.append(n)
        lo, hi = int(h * 0.2), int(h * 0.8)
        seg = belt[lo:hi]
        self.hip = hip = lo + seg.index(max(seg)) + 1 if max(seg) >= 3 else int(h * 0.5)
        self.upper = [[v if v and y < hip else 0 for v in row] for y, row in enumerate(P)]   # the masked pixels
        # the feet: columns of the lowest non-shadow rows, split where they have a gap, else in the middle
        ys, xs = [], []
        for y in range(hip, h):
            for x in range(w):
                if pic[y][x] and pic[y][x] != SHADOW: ys.append(y); xs.append(x)
        if not ys:
            self.leg = []; self.pivot = (w / 2, float(hip)); return
        ymax = max(ys)
        cols = sorted({x for y, x in zip(ys, xs) if y >= ymax - 3})
        gaps = [i for i in range(len(cols) - 1) if cols[i + 1] - cols[i] > 2]
        split = (cols[gaps[0]] + cols[gaps[0] + 1]) / 2 if gaps else (min(xs) + max(xs)) / 2
        self.leg = []
        for left in (True, False):
            rows = {}
            for y in range(hip, h):
                c = [x for x in range(w) if pic[y][x] and ((x < split) if left else (x >= split))]
                if c: rows[y] = c
            if not rows: continue
            yy = [y for y in rows for x in rows[y] if pic[y][x] != SHADOW]
            xx = [x for y in rows for x in rows[y] if pic[y][x] != SHADOW]
            if not yy:
                yy = [y for y in rows for x in rows[y]]; xx = [x for y in rows for x in rows[y]]
            top = max(yy)
            sole = [x for y, x in zip(yy, xx) if y >= top - 1]
            self.leg.append(dict(rows=rows, foot=(sum(sole) / len(sole), float(top))))
        r = [x for x in range(w) if (6 <= pic[hip - 1][x] <= 11) or pic[hip - 1][x] == SHADOW] if hip > 0 else []
        if not r: r = [x for x in range(w) if pic[min(hip, h - 1)][x]]
        # the middle of the longest run on the hip row: the waist, not an arm beside it
        runs, start = [], None
        for c in r + [None]:
            if start is None: start = prev = c
            elif c is not None and c == prev + 1: prev = c
            else: runs.append((prev - start, start, prev)); start = prev = c
        _, c0, c1 = max(runs)
        self.pivot = ((c0 + c1) / 2, float(hip))
        # the first OVERLAP rows of the legs also in the upper body (drawn over the legs' own; the belt is colour 5)
        for y in range(hip, min(h, hip + OVERLAP)):
            for x in range(w):
                if P[y][x]: self.upper[y][x] = P[y][x]
        # the hands: below the hip, near the sword's grip, not the robe's red nor the shadow: with the upper body
        if self.sword is not None:
            gx, gy = self.sword['grip'][0] - self.u0, self.sword['grip'][1] - self.v0
            for y in range(hip, h):
                for x in range(w):
                    v = P[y][x]
                    if v and not (6 <= (v & 0x1F) <= 11) and (v & 0x1F) != SHADOW and math.hypot(x - gx, y - gy) <= HAND_R:
                        self.upper[y][x] = v
                        for leg in self.leg:
                            if y in leg['rows'] and x in leg['rows'][y]:
                                leg['rows'][y] = [c for c in leg['rows'][y] if c != x]
            for leg in self.leg:
                leg['rows'] = {y: c for y, c in leg['rows'].items() if c}

    def at(self, p):
        """A point of the pose's own picture in the root's coordinates."""
        return (p[0] + self.u0, p[1] + self.v0)


def rotate(src, pivot, ang, H, W, at):
    """src's nonzero pixels turned by ang (radians, counter-clockwise on the screen) about pivot (src coordinates),
    the pivot landing at `at` (out coordinates): {(y, x): value}. Nearest pixel, inverse mapping (no holes), only
    over the box the turned pixels can reach (the out pixels beyond it map to none of them); a half rounds up."""
    c, s = math.cos(ang), math.sin(ang)
    h, w = len(src), len(src[0])
    ys, xs = nonzero(src)
    if not ys: return {}
    fx, fy = [], []
    for y, x in zip(ys, xs):
        dx, dy = x - pivot[0], y - pivot[1]
        fx.append(at[0] + c * dx + s * dy); fy.append(at[1] - s * dx + c * dy)
    x0, x1 = max(0, int(math.floor(min(fx))) - 2), min(W - 1, int(math.ceil(max(fx))) + 2)
    y0, y1 = max(0, int(math.floor(min(fy))) - 2), min(H - 1, int(math.ceil(max(fy))) + 2)
    out = {}
    for yy in range(y0, y1 + 1):
        dy = yy - at[1]
        for xx in range(x0, x1 + 1):
            dx = xx - at[0]
            sx = R(pivot[0] + c * dx - s * dy + 1e-9)        # inverse of turning by ang with v down
            sy = R(pivot[1] + s * dx + c * dy + 1e-9)
            if 0 <= sx < w and 0 <= sy < h:
                v = src[sy][sx]
                if v: out[(yy, xx)] = v
    return out


class Maker:
    """The pictures of one look: Maker(game, look).inbetween(change, j) -> (rows, tags, u0, v0)."""
    def __init__(self, game, look, sword=None):
        self.B = Banks(game, look)
        self.kn4 = self.B.f[3]
        self.SW = sword or sword_geometry(self.kn4)
        self.poses, self.made = {}, {}
        self.info = {}                                   # (c, j): where the picture's sword is (its grip, angle)
        if len(self.kn4) < 25: raise AttackError('KN4.OB: fewer than 25 frames')

    def pose(self, i):
        if i not in self.poses: self.poses[i] = Pose(ATK_POSES[i], self.B, self.SW)
        return self.poses[i]

    def dagger_picture(self, ang):
        """D147: a dagger picture at the angle (from its hilt, held in the fist, to its point): the game's two dagger
        frames (the held one by its hilt) and their half turns, the nearest turned by what is left about the hilt:
        ({(y, x): value}, hilt). The hilt: the middle of its dark pixels (4, 5); the angle: to the farthest pixel."""
        if not hasattr(self, '_dg'):
            self._dg = []
            for n in DAGGERS:
                for half in (0, 1):
                    a = self.kn4[n]
                    if half: a = [r[::-1] for r in a[::-1]]
                    px = [(y, x) for y, r in enumerate(a) for x, v in enumerate(r) if v]
                    dk = [(y, x) for y, r in enumerate(a) for x, v in enumerate(r) if v in (4, 5)]
                    gy, gx = sum(y for y, x in dk) / len(dk), sum(x for y, x in dk) / len(dk)
                    fy, fx = max(px, key=lambda q: math.hypot(q[0] - gy, q[1] - gx))
                    self._dg.append((a, (gx, gy), math.atan2(-(fy - gy), fx - gx)))
        a, (gx, gy), ak = min(self._dg, key=lambda d: abs(wrap(d[2] - ang)))
        left = wrap(ang - ak)
        if abs(left) < math.radians(2):
            return {(y, x): v for y, row in enumerate(a) for x, v in enumerate(row) if v}, (gx, gy)
        S = 48
        return rotate(a, (gx, gy), left, S, S, (S / 2, S / 2)), (S / 2, S / 2)

    def sword_picture(self, ang):
        """The game's sword frame nearest to the angle, turned by what is left about its grip: (picture, grip in
        it): a picture as rows (not turned) or as {(y, x): value} with its size."""
        SW = self.SW
        k = min(SWORDS, key=lambda n: abs((SW[n][2] - ang + math.pi) % (2 * math.pi) - math.pi))
        a = self.kn4[k]
        gx, gy, ak, ln = SW[k]
        left = (ang - ak + math.pi) % (2 * math.pi) - math.pi
        if abs(left) < math.radians(2):
            return {(y, x): v for y, row in enumerate(a) for x, v in enumerate(row) if v}, (gx, gy)
        S = int(2 * ln + 8)
        return rotate(a, (gx, gy), left, S, S, (S / 2, S / 2)), (S / 2, S / 2)

    def arc_pixels(self, pose, grip, from_ang):
        """The arcs of a pose as (u, v, colour, p): p from 0 at the end nearer the angle from_ang (seen from grip)
        to 1."""
        out = []
        for n, dy, dx in pose.arcs:
            a = self.kn4[n]; ys, xs = nonzero(a)
            u = [x + dx for x in xs]; v = [y + dy for y in ys]
            rel = [wrap(math.atan2(-(vv - grip[1]), uu - grip[0]) - from_ang) for uu, vv in zip(u, v)]
            if max(rel) - min(rel) < math.radians(15):          # nearly straight seen from the grip: along the chord
                um, vm = sum(u) / len(u), sum(v) / len(v)
                cf, sf = math.cos(from_ang), math.sin(from_ang)
                rel = [-((uu - um) * cf - (vv - vm) * sf) for uu, vv in zip(u, v)]
            ab = [abs(r) for r in rel]
            lo, span = min(ab), max(1e-6, max(ab) - min(ab))
            out += [(uu, vv, a[y][x], (r - lo) / span) for uu, vv, y, x, r in zip(u, v, ys, xs, ab)]
        return out

    def inbetween(self, c, j):
        if (c, j) not in self.made: self.made[(c, j)] = self._inbetween(c, j)
        return self.made[(c, j)]

    def sword_ang(self, c, j):
        """The sword's angle in in-between j of change c (j = 0: the old pose's, 6: the new one's). 5a: the upper body's
        turn, but never back against the way the sword goes nor past the new pose's angle (the arm's extension where
        it can be); a sweep past half a turn and the lunge's evenly from the old pose's angle to the new one's."""
        ia, ib = ATK_CHANGES[c]
        deg, step, switch, turn = RECIPE[c]
        a, b = self.pose(ia), self.pose(ib)
        if not (a.sword and b.sword):                        # D147: one pose without a sword: the other's turns with
            src, f = (b, j / 6 - 1) if j >= switch else (a, j / 6)   # its upper body
            return src.sword['ang'] + math.radians(deg) * f if src.sword else None
        dang = wrap(b.sword['ang'] - a.sword['ang']) if turn is None else math.radians(turn)
        if j <= 0: return a.sword['ang']
        if j >= 6: return a.sword['ang'] + dang
        if c in RIPOSTE:                                     # 2b: level by the time the arm reaches out
            return a.sword['ang'] + min(1.0, j / switch) * dang
        if c in LUNGE or c in UP_LINE or abs(dang) > math.pi:   # (a sweep past half a turn: evenly)
            return a.sword['ang'] + j / 6 * dang
        sign = 1 if dang >= 0 else -1
        done = 0.0                                           # how far along the way it has gone (radians)
        for k in range(1, j + 1):
            t = k / 6
            src, f = (b, t - 1) if k >= switch else (a, t)
            rigid = src.sword['ang'] + math.radians(deg) * f
            p = (rigid - a.sword['ang']) * sign
            p = (p + math.pi) % (2 * math.pi) - math.pi      # the nearer way round from the old angle ...
            if p < -math.pi / 2: p += 2 * math.pi            # ... unless it is far behind: then the long way
            done = max(done, min(p, abs(dang)))
        return a.sword['ang'] + sign * done

    def _inbetween(self, c, j):
        """In-between j (1-5) of change c (an index of ATK_CHANGES): (rows, tags, u0, v0) in the root's coordinates
        (facing right); tags: 0 = a body pixel, 1 = a sword or arc pixel, per pixel of rows."""
        for k in range(1, j): self.inbetween(c, k)           # the earlier pictures' grips (the trail's reach)
        ia, ib = ATK_CHANGES[c]
        deg, step, switch, turn = RECIPE[c]
        lunge = c in LUNGE or c in UP_LINE
        if lunge: deg = 0
        a, b = self.pose(ia), self.pose(ib)
        dang = None
        if a.sword and b.sword:
            dang = wrap(b.sword['ang'] - a.sword['ang']) if turn is None else math.radians(turn)
        t = j / 6
        new = j >= switch
        src, f = (b, t - 1) if new else (a, t)
        th = math.radians(deg) * f
        pa, pb = a.at(a.pivot), b.at(b.pivot)
        D = ((pb[0] + float(step[0])) - pa[0], (pb[1] + float(step[1])) - pa[1])
        if c in LUNGE and a.sword and b.sword:               # 2: the rows the grip goes: a straight line
            D = (D[0], b.sword['grip'][1] - a.sword['grip'][1])
            if c in RIPOSTE and new:                         # 2b: the reach comes up from the lunge's stance row
                D = (D[0], b.sword['grip'][1] - self.pose(RIPOSTE[c]).sword['grip'][1])
        H, W = src.h + 2 * PAD, src.w + 2 * PAD
        org = (src.u0 - PAD, src.v0 - PAD)
        out = {}
        la = sorted(a.leg, key=lambda l: l['foot'][0]); lb = sorted(b.leg, key=lambda l: l['foot'][0])
        pair = {}
        if len(la) == len(lb):
            for x, y in zip(la, lb): pair[id(x)] = y; pair[id(y)] = x
        elif len(la) == 1 or len(lb) == 1:
            one, many = (la, lb) if len(la) == 1 else (lb, la)
            for y in many: pair[id(y)] = one[0]
            pair[id(one[0])] = None
        fD = (f * D[0], f * D[1])
        # 1: the pivot on a whole pixel, then the turn
        piv_out = (R((src.pivot[0] + PAD) + fD[0]), R((src.pivot[1] + PAD) + fD[1]))
        piv_out = (piv_out[0] + (src.pivot[0] % 1), piv_out[1] + (src.pivot[1] % 1))   # the pivot's own fraction kept
        # 7 (second round): the legs layer as one continuous warp, every out pixel fetched from its source (no gaps):
        # at the hip row each point goes where the turned upper body takes it, at the feet where its foot goes
        # (across the legs from the one foot's move to the other's), and in between evenly
        feet = []
        for leg in src.leg:
            other = pair.get(id(leg))
            if other is None: Ef = fD
            else:
                fa = src.at(leg['foot']); fb = (b if src is a else a).at(other['foot'])
                df = (fb[0] - fa[0], fb[1] - fa[1])
                Ef = (f * df[0], f * df[1]) if src is a else (-f * df[0], -f * df[1])
            feet.append((leg['foot'], Ef))
        feet.sort(key=lambda fe: fe[0][0])
        if feet:
            mask = {}
            for leg in src.leg:
                for y, xs in leg['rows'].items():
                    for x in xs: mask[(y, x)] = src.pic[y][x]
            cth, sth = math.cos(th), math.sin(th)
            hip = src.hip
            ankle = sum(fe[0][1] for fe in feet) / len(feet) - 3
            (fl, El), (fr, Er) = feet[0], feet[-1]
            def disp(x, y):
                dx, dy = x - src.pivot[0], hip - src.pivot[1]
                hx = piv_out[0] + cth * dx + sth * dy - (x + PAD)
                hy = piv_out[1] - sth * dx + cth * dy - (hip + PAD)
                u = 0.0 if fr[0] - fl[0] < 1 else min(1.0, max(0.0, (x - fl[0]) / (fr[0] - fl[0])))
                ex, ey = El[0] * (1 - u) + Er[0] * u, El[1] * (1 - u) + Er[1] * u
                w = min(1.0, max(0.0, (y - hip) / max(1.0, ankle - hip)))
                return hx * (1 - w) + ex * w, hy * (1 - w) + ey * w
            fwd = [(x + PAD + disp(x, y)[0], y + PAD + disp(x, y)[1]) for (y, x) in mask]
            X0, X1 = int(min(p[0] for p in fwd)) - 2, int(max(p[0] for p in fwd)) + 3
            Y0, Y1 = int(min(p[1] for p in fwd)) - 2, int(max(p[1] for p in fwd)) + 3
            for Y in range(max(0, Y0), min(H, Y1 + 1)):
                for X in range(max(0, X0), min(W, X1 + 1)):
                    x, y = X - PAD, Y - PAD
                    for _ in range(4):                       # the source of (X, Y): x = X - disp(x)
                        ddx, ddy = disp(x, y)
                        x, y = X - PAD - ddx, Y - PAD - ddy
                    q = (R(y + 1e-9), R(x + 1e-9))
                    if q in mask: out[(Y, X)] = mask[q]
        out.update(rotate(src.upper, src.pivot, th, H, W, piv_out))
        # 7: a gap of 1-2 rows left between the layers around the hip row: filled from the pixel above
        hip_out = int(src.hip + PAD + fD[1])
        for y in range(hip_out - 4, hip_out + 5):
            for x in {xx for (yy, xx) in out if hip_out - 6 <= yy <= hip_out + 7}:
                if (y, x) in out: continue
                above = next(((y - k, x) for k in (1, 2) if (y - k, x) in out), None)
                below = next(((y + k, x) for k in (1, 2) if (y + k, x) in out), None)
                if above and below: out[(y, x)] = out[above]
        sw = None; grip_root = ang = None
        if src.sword is not None:
            g = ((src.sword['grip'][0] - src.u0) - src.pivot[0], (src.sword['grip'][1] - src.v0) - src.pivot[1])
            c_, s_ = math.cos(th), math.sin(th)
            grip = (piv_out[0] + (c_ * g[0] + s_ * g[1]), piv_out[1] + (-s_ * g[0] + c_ * g[1]))
            ang = self.sword_ang(c, j)
            spic, (gx, gy) = self.sword_picture(ang)
            sw = (spic, R(grip[0] - gx), R(grip[1] - gy))
            grip_root = (grip[0] + org[0], grip[1] + org[1])
        final, tag = {}, {}
        for p, v in out.items():
            if not v & OVER: final[p] = v & 0x1F; tag[p] = 1 if v & WPN else 0
        sword_px = set()
        if sw:
            spic, x, y = sw
            for (yy, xx), v in spic.items():
                yy += y; xx += x
                if 0 <= yy < H and 0 <= xx < W: final[(yy, xx)] = v; tag[(yy, xx)] = 1; sword_px.add((xx + org[0], yy + org[1]))
        for p, v in out.items():
            if v & OVER: final[p] = v & 0x1F; tag[p] = 1 if v & WPN else 0; sword_px.discard((p[1] + org[0], p[0] + org[1]))
        for p, v in out.items():                             # D147: the dagger in hand is the sword's (not a trail)
            if v & WPN and tag.get(p) == 1: sword_px.add((p[1] + org[0], p[0] + org[1]))
        if c in KEEP_DAGGER and src is b:                    # D147: the dagger kept in the thrown pose's fist
            (hx, hy), hdeg = KEEP_DAGGER[c]
            g = ((hx - src.u0) - src.pivot[0], (hy - src.v0) - src.pivot[1])
            c_, s_ = math.cos(th), math.sin(th)
            hp = (piv_out[0] + (c_ * g[0] + s_ * g[1]), piv_out[1] + (-s_ * g[0] + c_ * g[1]))
            dpic, (tx, ty) = self.dagger_picture(math.radians(hdeg) + th)   # (tx, ty): its hilt
            ox, oy = R(hp[0] - tx), R(hp[1] - ty)
            for (yy, xx), v in dpic.items():
                yy += oy; xx += ox
                if 0 <= yy < H and 0 <= xx < W: final[(yy, xx)] = v; tag[(yy, xx)] = 1; sword_px.add((xx + org[0], yy + org[1]))
        # 4: the new pose's trail over the angle swept so far, hung from the sword's grip; the old one's fades
        ga = a.sword['grip'] if a.sword else a.at(a.pivot)
        if b.arcs and a.sword and b.sword and grip_root is not None:
            sign = 1 if dang >= 0 else -1
            swept = ang - a.sword['ang']
            if swept * sign < 0: swept += 2 * math.pi * sign
            swept = abs(swept)
            gb = b.sword['grip']
            sh = (grip_root[0] - gb[0], grip_root[1] - gb[1])
            for n, dy, dx in b.arcs:
                arc = self.kn4[n]
                for yy, row in enumerate(arc):
                    for xx, col in enumerate(row):
                        if not col: continue
                        u, v = xx + dx, yy + dy
                        d = wrap(math.atan2(-(v - gb[1]), u - gb[0]) - a.sword['ang']) * sign
                        if -math.radians(3) <= d <= swept + math.radians(2):
                            px, py = R(u + sh[0] - org[0]), R(v + sh[1] - org[1])
                            if 0 <= px < W and 0 <= py < H and (py, px) not in final:
                                final[(py, px)] = col; tag[(py, px)] = 1
        if a.arcs:
            start = a.sword['ang'] if a.sword else 0.0
            for u, v, col, p in self.arc_pixels(a, ga, start):
                if p <= 1 - 2 * t:
                    x, y = int(u - org[0]), int(v - org[1])
                    if 0 <= x < W and 0 <= y < H and (y, x) not in final: final[(y, x)] = col; tag[(y, x)] = 1
        if grip_root is not None:
            prev = self.sword_ang(c, j - 1)
            if prev is None: prev = ang                      # (D147: no sword in the picture before)
            move = ang - prev                               # (the angles go the sword's own way round)
            sign = (1 if move > 0 else -1) if abs(move) > math.radians(1) else (1 if (dang or 0) >= 0 else -1)
            gxo, gyo = grip_root[0] - org[0], grip_root[1] - org[1]
            grips = [a.sword['grip'] if a.sword else None] + [self.info[(c, k)]['grip'] for k in range(1, j)] + [grip_root]
            reach = max(p.sword['len'] for p in (a, b) if p.sword) + 3
            for (y, x) in [p for p in final if tag.get(p) == 1 and (p[1] + org[0], p[0] + org[1]) not in sword_px]:
                ahead = wrap(math.atan2(-(y - gyo), x - gxo) - ang) * sign
                far = min(math.hypot(x + org[0] - g[0], y + org[1] - g[1]) for g in grips if g) > reach
                if ahead > math.radians(2) or far: del final[(y, x)]
        final = {p: v for p, v in final.items() if v}
        if not any(k[0] == 3 for k in ATK_POSES[ib]):        # D147: no KN4 piece this tick: all the body's part
            tag = {p: 0 for p in tag}
        if not final: raise AttackError(f'change {c}, {j}: an empty picture')
        y0 = min(y for y, x in final); y1 = max(y for y, x in final)
        x0 = min(x for y, x in final); x1 = max(x for y, x in final)
        rows = [[0] * (x1 - x0 + 1) for _ in range(y1 - y0 + 1)]
        tags = [[0] * (x1 - x0 + 1) for _ in range(y1 - y0 + 1)]
        for (y, x), v in final.items(): rows[y - y0][x - x0] = v; tags[y - y0][x - x0] = tag[(y, x)]
        self.info[(c, j)] = dict(grip=grip_root, ang=ang, dang=dang, sword=sword_px, prev=self.sword_ang(c, j - 1),
                                 arm=(src.sword['ang'] + th) if src.sword else None)
        return rows, tags, int(org[0] + x0), int(org[1] + y0)


# --- the file's attack part ---------------------------------------------------------------------------------------
def parts(rows, tags):
    """The picture's two parts: [(part, rows, column, row)] for the body's pixels (0) and the sword's (1), each cropped
    to its own box (the places relative to the picture's)."""
    out = []
    for part in (0, 1):
        pts = [(y, x) for y, row in enumerate(rows) for x, v in enumerate(row) if v and tags[y][x] == part]
        if not pts: continue
        y0 = min(y for y, x in pts); y1 = max(y for y, x in pts)
        x0 = min(x for y, x in pts); x1 = max(x for y, x in pts)
        pr = [[(rows[y][x] if tags[y][x] == part else 0) for x in range(x0, x1 + 1)] for y in range(y0, y1 + 1)]
        out.append((part, pr, x0, y0))
    return out


def pack(frames_in):
    """The picture's parts as strips of whole rows packed into slots: [[(part, rows, dx, dy), ...] a slot]. A part
    goes on in the room left in the slot, the rows that do not fit in the next one."""
    slots, cur, room = [], [], ROOM
    for part, rows, dx, dy in frames_in:
        bpr = (len(rows[0]) + 15) // 16 * 2
        used = []
        for row in rows:
            u = 0
            for v in row: u |= v
            used.append(u)
        y = 0
        while y < len(rows):
            n, u = 0, 0
            while y + n < len(rows):                         # a strip's bytes: frame_planes' planes (at least one)
                u2 = u | used[y + n]
                if FRAME_HEAD + max(1, bin(u2 & 15).count('1')) * (n + 1) * bpr > room: break
                n, u = n + 1, u2
            if n == 0 or len(cur) == ATK_RECS:
                if not cur: raise AttackError('a row longer than a slot')
                slots.append(cur); cur, room = [], ROOM; continue
            strip = rows[y:y + n]
            cur.append((part, strip, dx, dy + y)); room -= FRAME_HEAD + len(frame_planes(strip)[1]); y += n
    if cur: slots.append(cur)
    return slots


def slot_bytes(slot, more):
    """A slot of SAVEHOOK.INB's attack part: ATK_RECS records of ATK_REC bytes, one a frame (its place from the
    knight's first piece as the game draws it: dx, dy; its part: 0 = drawn in the body's colour state, 1 = in the
    sword's; its frame number, with ATK_LAST on the slot's last frame and ATK_MORE there when the picture goes on in
    the next slot); a bank of the frames at ATK_BANK (the game's layout; its data offset BUF_WALK, the frames' offsets
    from the slot's start, its segment written when the slot is fetched); the planes."""
    n = len(slot)
    recs = b''
    for i, (part, rows, dx, dy) in enumerate(slot):
        flags = i | (ATK_LAST | (ATK_MORE if more else 0) if i == n - 1 else 0)
        recs += struct.pack('<hhBB', dx, dy, part, flags)
    at = ATK_BANK + 10 + 10 * n
    entries, data = b'', b''
    for part, rows, dx, dy in slot:
        mask, planes = frame_planes(rows)
        entries += struct.pack('>IHHH', at + len(data), len(rows[0]), len(rows), mask)
        data += planes
    s = recs.ljust(ATK_BANK, b'\0') + struct.pack('>H', n) + struct.pack('<HH', BUF_WALK, 0) + bytes(4) + entries + data
    if len(s) > WK_SLOT: raise AttackError(f'a slot of {len(s)} bytes')
    return s + bytes(WK_SLOT - len(s))


def placed(mk, c, j, facing):
    """One picture's slots' contents for a facing (0 right, 1 left): the parts and strips with their places from
    the new pose's first piece as the game draws it."""
    rows, tags, u0, v0 = mk.inbetween(c, j)
    ib = ATK_CHANGES[c][1]
    b0, n0, dy0, dx0 = ATK_POSES[ib][0]
    W = len(rows[0])
    if facing:
        rows = [r[::-1] for r in rows]; tags = [t[::-1] for t in tags]
        w0 = len(mk.B.f[b0][n0][0])
        cx = dx0 + w0 - u0 - W                               # x = root - u0 - W, the first piece at root - dx0 - w0
    else:
        cx = u0 - dx0
    cy = v0 - dy0
    return pack([(part, pr, cx + x, cy + y) for part, pr, x, y in parts(rows, tags)])


def sizes(game):
    """{(c, look, facing, j): slots} and the bytes used."""
    out, used = {}, 0
    for look in (0, 1):
        mk = Maker(game, look)
        for c in range(len(ATK_CHANGES)):
            for facing in (0, 1):
                for j in J:
                    s = placed(mk, c, j, facing)
                    out[(c, look, facing, j)] = len(s)
                    used += sum(len(slot_bytes(x, False).rstrip(b'\0')) for x in s)
    return out, used


def build(game, K):
    """The attack part's slots (bytes), after the walk's: for each change, each facing and look (facing * 2 + look:
    as atk_match works it out), each sixth j: K[c] slots, the picture's own and zeros after them."""
    out = []
    makers = [Maker(game, look) for look in (0, 1)]
    for c in range(len(ATK_CHANGES)):
        for combo in range(4):
            facing, look = combo >> 1, combo & 1
            for j in J:
                s = placed(makers[look], c, j, facing)
                if len(s) > K[c]: raise AttackError(f'change {c}: a picture of {len(s)} slots, more than {K[c]}')
                for i, slot in enumerate(s): out.append(slot_bytes(slot, i + 1 < len(s)))
                out += [bytes(WK_SLOT)] * (K[c] - len(s))
    return out


if __name__ == '__main__':
    import time
    t0 = time.time()
    s, used = sizes(sys.argv[1])
    K = [max(v for (c, l, f, j), v in s.items() if c == cc) for cc in range(len(ATK_CHANGES))]
    print('K =', K)
    print(f'{len(s)} pictures, {sum(s.values())} slots used, {used} bytes used; with K: {20 * sum(K)} slots, '
          f'{20 * sum(K) * WK_SLOT} bytes; {time.time() - t0:.1f} s')
