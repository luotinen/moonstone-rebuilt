"""D20: new deaths for a knight hit again while it falls (its slumped pose, script 1000:130E): split in two, a
dagger where it hit (face, back of the head, belly, back), a long thrust through the middle of the body, a back
strike down through the helmet. The new pieces are made from the knight's own pieces in the user's KN3.OB (and
HE3.OB, the other look) and appended to those banks; the scripts that draw them go into MAIN.EXE's data segment
(D20 in make_savehook.py, which picks one when a slumped knight is hit). Pure Python: no numpy.
Usage: python -I tools/death_frames.py <game dir> [preview.png]   (the preview needs Pillow and msfmt.py)"""
import os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_savehook import D20, D20_BASE, D20_END, D20_NAMES, D20_SIZE

BANK = 8                                  # KN3.OB in the knights' bank table (DS:8933, loaded at 1000:8B10)
FIRST = 64                                # KN3.OB's own frames are 0-63; the new ones follow
DS_IN_IMAGE = 0x123b * 16                 # MAIN.EXE's data segment from the start of the load image
GORE_OFF_SCRIPT = 0x1328                  # the plain fall the game plays when [0700h] is set
# with EMS the game copies files into a cache at start, each at a fixed place (DS:828A, 6 bytes a file: page group,
# offset, size); D20 moves the files after KN3.OB and HE3.OB on by 800h, which leaves them this much room
EMS_ROOM = {'KN3.OB': 0x3369, 'HE3.OB': 0x3399}
# the knights' bank area (1000:86A7): 1988h paragraphs for KN1-5.OB, D20 makes it this big
BANK_AREA, BANK_USED = 0x1ac0, 0x1988
THRUST_NEAR = 6                           # the thrust brings the knight this much nearer (anim +8h), in front of the sword
# blood is 15 only, as the game's own blood in KN3.OB: colours 9-14 come from each scene's palette (the knights
# never use them; 14 showed as coloured grains)
BLOOD, BLOOD_LIGHT, OUTLINE, STEEL, STEEL_DARK, STEEL_EDGE = 15, 15, 5, 1, 2, 4
# the slumped pose (script 1000:130E): head 21, body 22, legs and sword 23, as (frame, dx, dy)
HEAD, BODY, LEGS = (21, -28, 7), (22, -28, 21), (23, -59, 40)
LYING = [(25, -52, 42), (24, -80, 44), (26, -62, 51), (27, -98, 56)]   # the game's lying knight (1000:1328)


# --- the bank format (msfmt.read_cel; LZSS of INTR.EXE 0000:36B6) ---
def lz_decode(src, start, length):
    out = bytearray(); i = start; end = start + length
    while i < end:
        ctl = src[i]; i += 1
        for _ in range(8):
            if i >= end: break
            if ctl & 0x80:
                w = src[i] << 8 | src[i + 1]; i += 2
                p = len(out) - (w & 0x7ff)
                for k in range(34 - (w >> 11)): out.append(out[p + k])
            else:
                out.append(src[i]); i += 1
            ctl = (ctl << 1) & 0xff
    return out


def lz_encode(data):
    """Control byte MSB first, 1 = BE word (length 34 - (w >> 11), 3-34; distance w & 7FFh), 0 = a literal."""
    out, i, n = bytearray(), 0, len(data)
    heads = {}
    while i < n:
        ctl_pos = len(out); out.append(0); ctl = 0
        for bit in range(8):
            if i >= n: break
            best_len, best_dist = 0, 0
            for j in reversed(heads.get(bytes(data[i:i + 3]), [])):
                dist = i - j
                if dist > 0x7ff: break
                k = 0
                while k < 34 and i + k < n and data[j + k] == data[i + k]: k += 1
                if k > best_len: best_len, best_dist = k, dist
                if k == 34: break
            step = best_len if best_len >= 3 else 1
            if best_len >= 3:
                w = ((34 - best_len) << 11) | best_dist
                out += bytes((w >> 8, w & 0xff)); ctl |= 0x80 >> bit
            else:
                out.append(data[i])
            for k in range(i, i + step): heads.setdefault(bytes(data[k:k + 3]), []).append(k)
            i += step
        out[ctl_pos] = ctl
    return bytes(out)


def read_bank(data):
    n, csize, _ = struct.unpack('>HII', data[:10])
    frames = [struct.unpack('>IHHH', data[10 + i * 10:20 + i * 10]) for i in range(n)]
    return frames, lz_decode(data, 10 + n * 10, csize)


def frame_pixels(raw, off, w, h, mask):
    """Rows of colour indices from the Amiga bit planes (one plane per mask bit 0-7)."""
    bpr = ((w + 15) // 16) * 2
    bits = [b for b in range(8) if mask & (1 << b)]
    img = [[0] * w for _ in range(h)]
    for p, b in enumerate(bits):
        base = off + p * h * bpr
        for y in range(h):
            row = raw[base + y * bpr:base + (y + 1) * bpr]
            for x in range(w):
                if row[x >> 3] & (0x80 >> (x & 7)): img[y][x] |= 1 << b
    return img


def frame_planes(img):
    """(plane mask, data): only the bit planes the frame's colours use, as the game's own frames (10Xh)."""
    bpr = ((len(img[0]) + 15) // 16) * 2
    used = 0
    for row in img:
        for v in row: used |= v
    used = used or 1
    out = bytearray()
    for b in range(4):
        if not used & (1 << b): continue
        for row in img:
            line = bytearray(bpr)
            for x, v in enumerate(row):
                if v & (1 << b): line[x >> 3] |= 0x80 >> (x & 7)
            out += line
    return 0x100 | used, bytes(out)


def bank_with(data, new):
    """The bank with the frames `new` after its own."""
    frames, raw = read_bank(data)
    raw = bytearray(raw)
    for img in new:
        mask, planes = frame_planes(img)
        frames.append((len(raw), len(img[0]), len(img), mask))
        raw += planes
    packed = lz_encode(bytes(raw))
    return (struct.pack('>HII', len(frames), len(packed), len(raw) * 8) +
            b''.join(struct.pack('>IHHH', *f) for f in frames) + packed)


def bank_frames(data):
    frames, raw = read_bank(data)
    return [frame_pixels(raw, *f) for f in frames]


# --- pictures as lists of rows ---
def blank(w, h): return [[0] * w for _ in range(h)]
def flip_h(a): return [row[::-1] for row in a]
def flip_v(a): return [row[:] for row in a[::-1]]
def rot_cw(a): return [list(col)[::-1] for col in zip(*a)]


def paste(canvas, a, x, y):
    for j, row in enumerate(a):
        for i, v in enumerate(row):
            if v and 0 <= y + j < len(canvas) and 0 <= x + i < len(canvas[0]): canvas[y + j][x + i] = v


def squash(a, k):
    h = len(a); nh = max(1, int(round(h * k)))
    return [a[min(h - 1, int(y * h / nh))][:] for y in range(nh)]


def spray(w, h, seed, density):
    """Drops of blood, heavier towards the bottom centre."""
    rng = random.Random(seed)
    a = blank(w, h)
    for y in range(h):
        for x in range(w):
            centre = 1 - abs(x - (w - 1) / 2) / (w / 2 + 0.5)
            if rng.random() < density * (0.4 + 0.6 * centre) * (0.5 + 0.5 * y / max(h - 1, 1)):
                a[y][x] = BLOOD_LIGHT if rng.random() < 0.3 else BLOOD
    return a


def pool(w, h, seed):
    rng = random.Random(seed)
    a = blank(w, h)
    for x in range(w):
        edge = min(x, w - 1 - x)
        for y in range(h - (h if edge > 2 else max(1, edge)), h):
            a[y][x] = BLOOD if rng.random() > 0.15 else BLOOD_LIGHT
    return a


def blade(length, diagonal=False, bloody=0):
    """A blade out of a head: steel with a dark edge, the last `bloody` pixels of the tip red. Straight: tip at the
    left; diagonal: tip at the bottom right."""
    if not diagonal:
        a = blank(length, 3)
        for x in range(length):
            a[0][x] = STEEL if x else 0; a[1][x] = STEEL_DARK if x else STEEL_EDGE; a[2][x] = OUTLINE if x >= 2 else 0
        for x in range(bloody):
            a[0][x] = BLOOD if x else 0; a[1][x] = BLOOD_LIGHT if x % 2 else BLOOD
        return a
    a = blank(length + 2, length + 2)
    for k in range(length):
        tip = k >= length - bloody
        a[k][k] = BLOOD if tip else STEEL; a[k][k + 1] = BLOOD_LIGHT if tip else STEEL_DARK; a[k + 1][k + 1] = OUTLINE
    return a


def clean_blade(length):
    a = blade(length)
    a[0] = [STEEL] * length; a[1] = [STEEL_DARK] * length
    return a


def dagger(hilt_right):
    """The thrown dagger's (KN4.OB frame 10) hilt and a little of its blade, the blade's end bloody."""
    a = blank(11, 4)
    for x in range(6): a[1][x] = 4; a[2][x] = 5
    a[0][6] = 1; a[3][6] = 2
    for x in range(7, 11): a[1][x] = 1; a[2][x] = 2
    a[1][9], a[1][10], a[2][9], a[2][10] = BLOOD, BLOOD_LIGHT, BLOOD, BLOOD
    return flip_h(a) if hilt_right else a


def dagger_slant():
    """The dagger slanting down to the right into the back of a head: hilt at the top left, a little blade, its end
    bloody (as dagger(), at 45 degrees)."""
    a = blank(9, 9)
    for k in range(5): a[k][k] = 4; a[k + 1][k] = 5           # grip
    a[4][6] = 1; a[6][4] = 2                                  # guard
    for k in (5, 6): a[k][k] = 1; a[k + 1][k] = 2              # blade
    a[7][7] = BLOOD; a[8][7] = BLOOD; a[8][8] = BLOOD
    return a


def make(k3):
    """The new frames (FIRST on) and each death's frames: [(repeat, [(bank, frame, dy, flags, dx), ...]), ...]."""
    new = []
    def add(a):
        new.append(a); return FIRST + len(new) - 1
    head, body = k3[HEAD[0]], k3[BODY[0]]
    ux, uy = HEAD[1], HEAD[2]
    upper = blank(max(len(head[0]), len(body[0])), BODY[2] + len(body) - uy)
    paste(upper, body, BODY[1] - ux, BODY[2] - uy); paste(upper, head, 0, 0)
    uh, uw = len(upper), len(upper[0])
    # the split (the user's approved draft, 1 Nov 2026), along the body and parallel to the screen: the far half
    # tips away (up the screen) and the near half towards the player (down), both showing the blood-red cut face
    # with the armour's rim round it (but at the far half's foot, which stays on the ground); the legs and robe on
    # the ground part, the far ones (without the sword) a little back, a red cut between
    m = [[1 if v else 0 for v in row] for row in upper]
    def rim(y, x): return any(not (0 <= y + j < uh and 0 <= x + i < uw and m[y + j][x + i]) for j, i in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    cut_face = [[(upper[y][x] if rim(y, x) else BLOOD) if m[y][x] else 0 for x in range(uw)] for y in range(uh)]
    def far_half(k, up):
        a = squash(cut_face, k)
        foot = [BLOOD if v else 0 for v in a[-1]]
        return a[:-2] + [foot[:], foot[:]] + [foot[:] for _ in range(up)]
    legs_pic = k3[LEGS[0]]
    LEGS_FAR = add([[v if v not in (STEEL, STEEL_DARK) else 0 for v in row] for row in legs_pic])
    strip = [BLOOD if v else 0 for v in new[-1][0]]
    LEGS_CUT = {n: add([strip[:] for _ in range(n)]) for n in (1, 2, 3)}
    SPLIT = [  # (far: scale, up; 0 = hidden), (near: scale, down, upside down), legs apart
        ((0, 1), (1.0, 0, False), 1), ((0.8, 2), (0.75, 1, False), 2), ((0.6, 3), (0.45, 2, False), 2),
        ((0.45, 4), (0.2, 2, True), 3), ((0.4, 5), (0.4, 3, True), 3)]
    FAR = {up: add(far_half(k, up)) for (k, up), _, _ in SPLIT if k}
    NEAR = {k: add(flip_v(squash(cut_face, k)) if f else squash(upper, k)) for _, (k, _, f), _ in SPLIT if k < 1}
    SPRAY_S, SPRAY_M, SPRAY_L = add(spray(7, 8, 1, 0.35)), add(spray(11, 14, 2, 0.3)), add(spray(15, 20, 3, 0.28))
    POOL_S, POOL_L = add(pool(16, 2, 4)), add(pool(34, 3, 5))
    DRIP = add([[BLOOD], [BLOOD_LIGHT], [BLOOD]])
    DIAG_S, DIAG_L = add(blade(5, True, 2)), add(blade(9, True, 3))
    DAGGER_FRONT, DAGGER_BACK = add(dagger(True)), add(dagger(False))
    DAGGER_UP = add(rot_cw(dagger(False)))
    DAGGER_SLANT = add(dagger_slant())

    # positions as the pose's pieces (dx, dy of a piece's top left): piece 21's helmet spans x 4-16, y 1-9 of it,
    # its face at the right (the front), the plume at the left
    hx, hy = HEAD[1], HEAD[2]
    bottom, ground, cx = uy + uh, 58, ux + uw // 2
    P = lambda n, x, y: (BANK, n, y, 0, x)
    legs = lambda dy=0: P(LEGS[0], LEGS[1], LEGS[2] + dy)
    body_p = lambda dx=0, dy=0: P(BODY[0], BODY[1] + dx, BODY[2] + dy)
    head_p = lambda dx=0, dy=0: P(HEAD[0], HEAD[1] + dx, HEAD[2] + dy)
    lying = [P(n, dx, dy) for n, dx, dy in LYING]
    def split_frame(i):
        (kf, up), (kn, down, flip), apart = SPLIT[i]
        out = [P(LEGS_FAR, LEGS[1], LEGS[2] - apart)]
        if kf:
            far = new[FAR[up] - FIRST]
            out.append(P(FAR[up], ux, bottom - len(far)))
        out += [P(LEGS_CUT[apart], LEGS[1], LEGS[2] - apart + 1), legs(apart // 2)]
        if kn == 1: out += [body_p(0, down), head_p(0, down)]
        else:
            near = new[NEAR[kn] - FIRST]
            out.append(P(NEAR[kn], ux, bottom + down if flip else bottom + down - len(near)))
        return out
    deaths = {}
    deaths['split'] = [
        (2, [legs(), body_p(), head_p(), P(SPRAY_S, cx - 3, uy - 5)]),
        (2, [legs(), body_p(), head_p(), P(SPRAY_M, cx - 5, uy - 8)]),
        (2, split_frame(0) + [P(SPRAY_M, cx - 5, uy - 10)]),
        (2, split_frame(1) + [P(SPRAY_M, cx - 5, bottom - round(uh * 0.8) - 12)]),
        (2, split_frame(2) + [P(POOL_S, ux + 2, bottom + 3)]),
        (2, split_frame(3) + [P(POOL_S, ux + 2, bottom + 3)]),
        (0, split_frame(4) + [P(POOL_L, ux - 8, bottom + 3 + round(uh * 0.4))]),
    ]
    # a dagger at the head's height: from the front it stays in the helmet's face, hilt out; from behind slanting in
    # the back of the head, hilt up and back. At the waist's height: level in the belly or the back, hilt out on
    # the side it came from (the user's mock-ups)
    waist = BODY[2] + 6
    for name, d, x, y, lie in (
            ('dagger_front', DAGGER_FRONT, hx + 11, hy + 3, P(DAGGER_UP, -62, 37)),
            ('dagger_back', DAGGER_SLANT, hx - 4, hy - 4, P(DAGGER_UP, -62, 37)),
            ('dagger_waist_front', DAGGER_FRONT, BODY[1] + 15, waist, P(DAGGER_UP, -44, 38)),
            ('dagger_waist_back', DAGGER_BACK, BODY[1] - 7, waist, P(DAGGER_UP, -44, 38))):
        front = 'front' in name
        jolt = -1 if front else 1
        drip = x + (7 if front else 3)
        deaths[name] = [
            (2, [legs(), body_p(jolt), head_p(jolt), P(d, x + jolt, y), P(DRIP, drip, y + 4)]),
            (3, [legs(), body_p(), head_p(), P(d, x, y), P(DRIP, drip, y + 6)]),
            (4, [legs(), body_p(0, 1), head_p(0, 1), P(d, x, y + 1), P(SPRAY_S, drip - 3, y + 5)]),
        ]
        # the game's lying pose is the fall forward (the user's play test): from the front the knight falls
        # backward, drawn mirrored (80h FFh); the dagger stands up from its forehead, chest, back of the head or back
        if front: deaths[name].append((None, b'\x80\xff'))
        deaths[name].append((0, lying + [lie, P(POOL_S, -72, ground)]))
    # the long thrust goes through the middle of the body: the knight is brought 6 nearer (drawn after, so in front
    # of the striker's own sword, which shows again past it; its pieces 6 higher so it stays put), and blood bursts
    # out on its other side, at the back for a thrust from the front, at the front for one from behind
    near_in = struct.pack('<BBhhh', 0x90, 0x00, 0, 0, THRUST_NEAR)       # z += 6 (move flag 20h clear)
    near_out = struct.pack('<BBhhh', 0x90, 0x20, 0, 0, THRUST_NEAR)      # z -= 6
    up = -THRUST_NEAR
    slumped_up = lambda dy=0: [legs(up), body_p(0, up + dy), head_p(0, up + dy)]
    waist = BODY[2] + 6 + up
    for name, front in (('thrust_front', True), ('thrust_back', False)):
        # x of the sprays' near edge: the body's left edge at the back, its right edge at the front
        out = (lambda w: BODY[1] + 2 - w) if front else (lambda w: BODY[1] + 18)
        deaths[name] = [
            (None, near_in),
            (2, slumped_up() + [P(SPRAY_S, out(7), waist - 3)]),
            (2, slumped_up() + [P(SPRAY_M, out(11), waist - 6), P(SPRAY_S, out(7) + (-6 if front else 6), waist - 2)]),
            (3, slumped_up() + [P(SPRAY_L, out(15), waist - 8), P(DRIP, BODY[1] + 9, waist + 2)]),
            (2, slumped_up(1) + [P(SPRAY_M, out(11), waist - 2), P(DRIP, BODY[1] + 9, waist + 5),
                                 P(POOL_S, out(16), ground + up)]),
            (None, near_out),
            (0, lying + [P(POOL_L, -80, ground)]),
        ]
    # the back strike comes down through the top of the helmet and out under the chin
    deaths['back'] = [
        (2, [legs(), body_p(), head_p(), P(DIAG_S, hx + 13, hy + 8), P(SPRAY_S, hx + 15, hy + 9)]),
        (3, [legs(), body_p(), head_p(), P(DIAG_L, hx + 13, hy + 8), P(SPRAY_M, hx + 16, hy + 10)]),
        (2, [legs(), body_p(), head_p(0, 1), P(SPRAY_M, hx + 6, hy - 6), P(DRIP, hx + 16, hy + 11)]),
        (3, [legs(), body_p(), head_p(0, 2), P(SPRAY_S, hx + 7, hy - 3), P(DRIP, hx + 16, hy + 13)]),
        (0, lying + [P(POOL_S, -72, ground)]),
    ]
    return new, deaths


def script(frames, sound=0x09):
    """A death script as the game's beheading (1000:1386, ending 1000:154A): the finish flag (native 3E82), loop
    counters reset, the plain fall when blood is off ([0700h], 8Ch), a sound; the frames; a thud and the last frame,
    then held and drawn into the background (piece flag 10h) and the end of the fight (native 0231). The knight's
    object stays (removing it, 9Eh as the beheading, stopped the 3-4 knight practice's round end); SAVEHOOK.COM keeps
    it lying (knight_down)."""
    s = bytearray(b'\x98\x00' + struct.pack('<H', 0x3e82) + b'\xa8\x00\x8c\xff' + struct.pack('<H', GORE_OFF_SCRIPT))
    s += bytes((0x92, sound))
    def frame(pieces, flag=0):
        return b''.join(struct.pack('<BBbBh', b, n, dy, fl | flag, dx) for b, n, dy, fl, dx in pieces) + b'\xff\x00'
    for repeat, pieces in frames[:-1]:
        if repeat is None:                 # a command (bytes) between frames
            s += pieces; continue
        if repeat: s += bytes((0x84, repeat))
        s += frame(pieces)
    last = frames[-1][1]
    s += b'\x92\x10' + frame(last) + b'\x84\x02' + frame(last, 0x10)
    s += b'\x98\x00' + struct.pack('<H', 0x0231) + b'\xff\xff'
    return bytes(s)


def added_bytes(game):
    """How much KN3.OB grows in memory (frames' headers and planes): the knights' bank area must hold it."""
    data = open(os.path.join(game, 'DISKB', 'KN3.OB'), 'rb').read()
    new, _ = make(bank_frames(data)[:FIRST])
    return sum(10 + len(frame_planes(a)[1]) for a in new)


def install(game, exe):
    """KN3.OB and HE3.OB (the other look, a duel's second knight) with the new pieces, each made from its own
    pieces (written into game/DISKB unless it has them), and MAIN.EXE (bytes) with the scripts at D20_BASE; returns
    the new MAIN.EXE."""
    for name in ('KN3.OB', 'HE3.OB'):
        path = os.path.join(game, 'DISKB', name)
        data = open(path, 'rb').read()
        frames, _ = read_bank(data)
        new, made = make(bank_frames(data)[:FIRST])
        if name == 'KN3.OB': deaths = made
        if len(frames) == FIRST:
            data = bank_with(data, new)
            with open(path, 'wb') as f: f.write(data)
        elif len(frames) != FIRST + len(new):
            raise ValueError(f'{path}: {len(frames)} frames, expected {FIRST} or {FIRST + len(new)}')
        if len(data) > EMS_ROOM[name]:
            raise ValueError(f'{path}: {len(data)} bytes, its place in the EMS file cache holds {EMS_ROOM[name]}')
    if BANK_USED + (added_bytes(game) + 15) // 16 > BANK_AREA:
        raise ValueError(f"the new pieces need {added_bytes(game)} bytes, the knights' bank area has room for "
                         f'{(BANK_AREA - BANK_USED) * 16}')
    exe = bytearray(exe)
    image = struct.unpack('<H', exe[8:10])[0] * 16 + DS_IN_IMAGE
    for name in D20_NAMES:
        if name not in deaths: continue                   # a reserved slot (up_forward): left empty
        code = script(deaths[name])
        assert len(code) <= D20_SIZE[name], (name, len(code))
        at = image + D20[name]
        if any(exe[at:at + D20_SIZE[name]]) and exe[at:at + len(code)] != code:
            raise ValueError(f'MAIN.EXE: DS:{D20[name]:04X} is not free')
        exe[at:at + D20_SIZE[name]] = code + bytes(D20_SIZE[name] - len(code))
    return bytes(exe)


def preview(game, out):
    from PIL import Image, ImageDraw
    from msfmt import read_piv
    _, pal, _ = read_piv(open(os.path.join(game, 'DISKB/FO1.CMP'), 'rb').read()); pal += [0] * (768 - len(pal))
    pal[0:3] = [40, 40, 60]
    k3 = bank_frames(open(os.path.join(game, 'DISKB', 'KN3.OB'), 'rb').read())[:FIRST]
    new, deaths = make(k3)
    allf = k3 + new
    W, H, OX, OY = 170, 96, 110, 18
    rows = []
    slump = [(BANK, n, dy, 1, dx) for n, dx, dy in (HEAD, BODY, LEGS)]
    for name in D20_NAMES:
        cells = [slump] + [p for r, p in deaths[name] if r is not None]
        row = Image.new('P', (W * len(cells), H), 0); row.putpalette(pal)
        for i, pieces in enumerate(cells):
            c = blank(W, H)
            for b, n, dy, fl, dx in pieces: paste(c, allf[n], OX + dx, OY + dy)
            im = Image.new('P', (W, H)); im.putdata([v for r in c for v in r]); row.paste(im, (i * W, 0))
        rows.append((name, row.convert('RGB')))
    img = Image.new('RGB', (max(r.width for _, r in rows), sum(H + 12 for _ in rows)), (20, 20, 30))
    d = ImageDraw.Draw(img); y = 0
    for name, r in rows:
        d.text((2, y), name, fill=(255, 255, 0)); img.paste(r, (0, y + 12)); y += H + 12
    img.resize((img.width * 3, img.height * 3), Image.NEAREST).save(out)


if __name__ == '__main__':
    preview(sys.argv[1], sys.argv[2])
