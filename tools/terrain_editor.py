"""Moonstone map tool: the 80 x 50 terrain zones (cells of 4 x 4 pixels), the places and lairs, and the map picture.

Start with Terrain_editor.bat (or: python tools/terrain_editor.py). Needs Python 3 with tkinter and Pillow.
Plan: docs/terrain-80x50-plan-2026-11-19.md (T1a zones, T1b places and lairs, T1c the map picture and projects).
Formats: docs/terrain-zones.md; the map file, sprites, projects and apply: tools/map_mod.py.

Files (read by the rules build: Custom_rules_on.bat or Setup.bat after a change):
  tools/terrain_zones.csv        the zones: 50 lines of 80 kinds. An older 40 x 25 file is converted at the start,
                                 each 8 x 8 cell to 2 x 2 new cells (exact), after a copy of it is kept as
                                 tools/terrain_zones_40x25.csv (once, never overwritten).
  tools/places.csv, lairs.csv    the markers' positions (written by Save).
  a project (.zip)               zones, places, lairs and the player's own map picture (File menu).
  tools/map_palette.png          the map's 32 colours as squares for a colour dropper (ships; map_mod.palette_swatch).

Cells: 4x4 paints single 4 x 4 pixel cells; 2x2 paints the game's own 8 x 8 blocks (2 x 2 cells each). In 2x2 mode,
blocks that hold more than one kind are outlined in magenta.
Keys: 0-4 kind, B brush, F fill, V move markers, + and - brush size 1-4, M switch 4x4 / 2x2, P markers on/off,
T tint, G grid, Z zoom 2x/3x/4x, arrows nudge the chosen marker, Ctrl+Z undo, Ctrl+S save.
Mouse: left button paints, fills or drags a marker; right button picks up the kind under it.

The map picture and the sprites are the player's own: read from their game folder, never shipped with the tool."""
import csv
import io
import os
import shutil
import sys
from collections import Counter, deque

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_mod as MM  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ZONES = os.path.join(HERE, 'terrain_zones.csv')              # the zones (the rules build reads them, D133)
ZONES_OLD = os.path.join(HERE, 'terrain_zones_40x25.csv')    # an older 40 x 25 file, kept when converted
SAVE_PATH = ZONES
PLACES_CSV = os.path.join(HERE, 'places.csv')
LAIRS_CSV = os.path.join(HERE, 'lairs.csv')
GAME = ROOT                                                   # the game folder (DISKB, MAIN.EXE): tools/..
APPLY_READY = True              # D133-D135: the rules build reads the tool's files and takes a longer map file
PALETTE_PNG = os.path.join(HERE, 'map_palette.png')                # the game's map palette as squares (ships)
GAME_GRID = os.path.join(ROOT, '_extracted', 'map_terrain.csv')
MAP_PNG = os.path.join(ROOT, '_extracted', 'backgrounds', 'MAP_CMP.png')
EXPORT = os.path.join(ROOT, 'mockups', 'terrain-zones.png')

W, H, CELL = 80, 50, 4          # the zone grid: 80 x 50 cells of 4 x 4 pixels
OLD_W, OLD_H = 40, 25           # the game's grid: 8 x 8 pixel cells, 2 x 2 of ours
MAP_W, MAP_H = W * CELL, H * CELL
ROCK_ROWS = 14                  # the game's grid: value 2 in rows 0-13 is rocks
UNDO_LIMIT = 100
MAX_X, MAX_Y = 310, 190         # a knight's position stays within x 0-310, y 0-190
BRUSH_MAX = 4
MODES = {'4x4': 1, '2x2': 2}    # the mode: the block size in cells
ZOOMS = (2, 3, 4)

# kind: (name, game value, slowing, tint RGBA, hex colour for the legend)
KINDS = {
    0: ('Open ground', 0, 'full speed', (0, 0, 0, 0), '#cccccc'),
    1: ('Forest', 1, '1/2 speed', (40, 200, 60, 105), '#28c83c'),
    2: ('Swamp and water', 2, '1/2 speed (own rhythm)', (40, 120, 255, 125), '#2878ff'),
    3: ('Mountains and map edges', 3, '1/4 speed', (230, 40, 40, 115), '#e62828'),
    4: ('Rocks (game value 2)', 2, '1/2 speed (own rhythm)', (240, 160, 0, 125), '#f0a000'),
}


# ---- the zone files -------------------------------------------------------------------------------------------------

def parse_rows(text, name='zones'):
    """Rows of kind numbers from CSV text (comma-separated, or one digit a cell); checked: 0-4 only."""
    rows = []
    for n, r in enumerate(csv.reader(io.StringIO(text))):
        if not r:
            continue
        cells = r if len(r) > 1 else list(r[0].strip())
        try:
            row = [int(v) for v in cells]
        except ValueError:
            raise ValueError(f'{name}: line {n + 1} holds something other than kind numbers 0-4') from None
        if any(v not in KINDS for v in row):
            raise ValueError(f'{name}: line {n + 1} holds a kind outside 0-4')
        rows.append(row)
    return rows


def grid_size(rows):
    """(width, height) of rectangular rows, or None if the rows differ in length."""
    return (len(rows[0]), len(rows)) if rows and all(len(r) == len(rows[0]) for r in rows) else None


def to_grid80(rows, name='zones'):
    """An 80 x 50 grid from 80 x 50 rows (copied) or 40 x 25 rows (expanded 2 x 2); else ValueError naming the size."""
    size = grid_size(rows)
    if size == (W, H):
        return [r[:] for r in rows]
    if size == (OLD_W, OLD_H):
        return expand2(rows)
    got = f'{size[0]} x {size[1]}' if size else f'{len(rows)} rows of unequal length'
    raise ValueError(f'{name}: {got} cells; must be {W} x {H} (50 lines of 80 kinds) or {OLD_W} x {OLD_H} (the old size)')


def read_zones(path):
    """(the 80 x 50 grid, the file's size (w, h)) from a zone file of either size."""
    with open(path, newline='') as f:
        rows = parse_rows(f.read(), path)
    return to_grid80(rows, path), grid_size(rows)


def zones_text(grid):
    """The file text: one line a row, the kinds comma-separated, LF line ends."""
    return ''.join(','.join(str(v) for v in row) + '\n' for row in grid)


def save_zones(path, grid):
    if grid_size(grid) != (W, H):
        raise ValueError(f'save_zones: the grid must be {W} x {H}')
    tmp = path + '.tmp'
    with open(tmp, 'w', newline='') as f:
        f.write(zones_text(grid))
    os.replace(tmp, path)


def expand2(rows):
    """Each cell of a grid becomes 2 x 2 cells (40 x 25 -> 80 x 50)."""
    out = []
    for r in rows:
        wide = [v for v in r for _ in (0, 1)]
        out += [wide, wide[:]]
    return out


def block(grid, bx, by):
    """The four kinds of block (bx, by) in the order top-left, top-right, bottom-left, bottom-right."""
    x, y = 2 * bx, 2 * by
    return grid[y][x], grid[y][x + 1], grid[y + 1][x], grid[y + 1][x + 1]


def block_kind(cells):
    """The kind a 2 x 2 block stands for in the game's 8 x 8 grid: the most common, a tie going to the earlier cell."""
    c = Counter(cells)
    best = max(c.values())
    return next(v for v in cells if c[v] == best)


def reduce2(grid):
    """The 40 x 25 grid of the game's 8 x 8 cells (the reverse of expand2 for a grid of whole blocks)."""
    return [[block_kind(block(grid, bx, by)) for bx in range(len(grid[0]) // 2)] for by in range(len(grid) // 2)]


def mixed_blocks(grid):
    """The 8 x 8 blocks (bx, by) that hold more than one kind."""
    return [(bx, by) for by in range(len(grid) // 2) for bx in range(len(grid[0]) // 2)
            if len(set(block(grid, bx, by))) > 1]


def game_grid(path=GAME_GRID):
    """The game's own grid (40 x 25) with the value 2 cells of rows 0-13 turned into rocks (kind 4), expanded."""
    with open(path, newline='') as f:
        rows = parse_rows(f.read(), path)
    if grid_size(rows) != (OLD_W, OLD_H):
        raise ValueError(f'{path}: expected {OLD_H} rows of {OLD_W} values')
    return expand2([[4 if (v == 2 and y < ROCK_ROWS) else v for v in row] for y, row in enumerate(rows)])


def migrate(zones=None, old=None):
    """An older 40 x 25 zones file becomes 80 x 50 in place, each cell 2 x 2 (exact: reduce2 gives it back), after it
    is copied to `old` (once, never overwritten, checked). Returns a line for the status bar, or '' if nothing was done."""
    zones = zones or ZONES
    old = old or os.path.join(os.path.dirname(zones), 'terrain_zones_40x25.csv')
    if not os.path.exists(zones):
        return ''
    grid, size = read_zones(zones)
    if size != (OLD_W, OLD_H):
        return ''
    if not os.path.exists(old):
        shutil.copyfile(zones, old)
        with open(old, 'rb') as a, open(zones, 'rb') as b:
            if a.read() != b.read():
                raise OSError(f'{old}: the copy of {zones} does not match it')
    save_zones(zones, grid)
    return f'{os.path.basename(zones)} converted to 80 x 50 (the 40 x 25 file kept as {os.path.basename(old)})'


def probe_shift(game=None):
    """Rows to move the game's own zones up for Restore original zones: 1 with [Map] terrain_probe = centre (the default:
    a border stays under the same feet, 5 pixels being about one 4-pixel cell), 0 with feet."""
    game = game or GAME
    import configparser
    cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    try:
        cp.read(os.path.join(game, 'custom_rules.ini'), encoding='utf-8')
        probe = cp.get('Map', 'terrain_probe', fallback='centre').strip().lower()
    except (configparser.Error, UnicodeDecodeError):
        probe = 'centre'
    return 0 if probe == 'feet' else 1


# ---- painting (pure: a grid is a list of rows, changed in place) ----------------------------------------------------

def span(c, size, limit):
    """The range of size cells (or blocks) round c, the extra one going right/down, clipped to 0..limit-1."""
    lo = c - (size - 1) // 2
    return range(max(lo, 0), min(lo + size, limit))


def brush_cells(x, y, size, blk=1):
    """The cells a brush of size x size cells (blk = 1) or 8 x 8 blocks (blk = 2) covers round cell (x, y)."""
    bx, by = x // blk, y // blk
    return [(cx, cy) for by2 in span(by, size, H // blk) for bx2 in span(bx, size, W // blk)
            for cy in range(by2 * blk, by2 * blk + blk) for cx in range(bx2 * blk, bx2 * blk + blk)]


def paint(grid, cells, kind):
    """Set the cells to kind; returns how many changed."""
    n = 0
    for x, y in cells:
        if grid[y][x] != kind:
            grid[y][x] = kind
            n += 1
    return n


def flood_cells(grid, x, y, blk=1):
    """The cells a fill at (x, y) changes: every cell of the clicked kind connected to it by its sides (blk = 1). In
    blocks (blk = 2): the clicked 8 x 8 block and every whole block of the clicked kind connected to it by sides."""
    target = grid[y][x]
    if blk == 1:
        seen, todo = {(x, y)}, deque([(x, y)])
        while todo:
            cx, cy = todo.popleft()
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen and grid[ny][nx] == target:
                    seen.add((nx, ny))
                    todo.append((nx, ny))
        return sorted(seen, key=lambda c: (c[1], c[0]))
    bw, bh = W // 2, H // 2
    start = (x // 2, y // 2)
    seen, todo = {start}, deque([start])
    while todo:
        cx, cy = todo.popleft()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < bw and 0 <= ny < bh and (nx, ny) not in seen and set(block(grid, nx, ny)) == {target}:
                seen.add((nx, ny))
                todo.append((nx, ny))
    return [(2 * bx + i, 2 * by + j) for bx, by in sorted(seen, key=lambda c: (c[1], c[0])) for j in (0, 1) for i in (0, 1)]


def fill(grid, x, y, kind, blk=1):
    """Fill from cell (x, y) with kind; returns how many cells changed."""
    if blk == 1 and grid[y][x] == kind:
        return 0
    return paint(grid, flood_cells(grid, x, y, blk), kind)


def cell_bounds(x, y):
    """'in', 'partly' or 'outside': where cell (x, y) lies against a knight's reach (x 0-310, y 0-190)."""
    x0, y0, x1, y1 = x * CELL, y * CELL, x * CELL + CELL - 1, y * CELL + CELL - 1
    if x0 > MAX_X or y0 > MAX_Y:
        return 'outside'
    return 'partly' if x1 > MAX_X or y1 > MAX_Y else 'in'


def counts(grid):
    c = dict.fromkeys(KINDS, 0)
    for row in grid:
        for v in row:
            c[v] += 1
    return c


# ---- drawing ---------------------------------------------------------------------------------------------------------

def load_map_picture(path=MAP_PNG):
    """The map picture (320 x 200 RGB) from the player's own files, or None. (T1c: decode DISKB/MAP.CMP here.)"""
    try:
        img = Image.open(path).convert('RGB')
    except OSError:
        return None
    return img if img.size == (MAP_W, MAP_H) else img.resize((MAP_W, MAP_H), Image.NEAREST)


def game_picture(game=None):
    """(the game's map as RGB, its palette words) from the player's MAP.CMP (.orig if the tool made one); else the
    extracted PNG of the dev folder with no palette; else (None, None)."""
    game = game or GAME
    try:
        m = MM.game_map(game)
    except (OSError, ValueError):
        m = None
    if m:
        return MM.pixels_image(m[2], m[1]).convert('RGB'), m[1]
    return load_map_picture(), None


def blank_map():
    return Image.new('RGB', (MAP_W, MAP_H), (60, 56, 50))


class View:
    """What the drawing shows: zoom, tint, grid lines, the mode (block size)."""
    def __init__(self, scale=3, tint=True, lines=True, mode='4x4'):
        self.scale, self.tint, self.lines, self.mode = scale, tint, lines, mode

    @property
    def blk(self):
        return MODES[self.mode]


def layer_lines(d, grid, v):
    """The grid lines: 4 x 4 cells faint (4x4 mode, 3x zoom or more), 8 x 8 blocks, every 40 pixels white."""
    s, n = v.scale, MAP_W * v.scale
    for step, col, show in ((CELL, (96, 96, 96), v.blk == 1 and s >= 3), (2 * CELL, (150, 150, 150), True),
                            (10 * CELL, (255, 255, 255), True)):
        if not show:
            continue
        for x in range(0, MAP_W + 1, step):
            d.line((x * s, 0, x * s, MAP_H * s), fill=col)
        for y in range(0, MAP_H + 1, step):
            d.line((0, y * s, n, y * s), fill=col)


def layer_mixed(d, grid, v):
    """2x2 mode: the 8 x 8 blocks holding more than one kind, outlined in magenta."""
    if v.blk != 2:
        return
    c = 2 * CELL * v.scale
    for bx, by in mixed_blocks(grid):
        d.rectangle((bx * c + 1, by * c + 1, bx * c + c - 2, by * c + c - 2), outline=(255, 0, 255))


def layer_bounds(d, grid, v):
    """The knights' reach: cells wholly outside x 0-310, y 0-190 (columns 78-79, rows 48-49) hatched yellow; a yellow
    line at the exact edge, through the partly outside column 77 and row 47."""
    s = v.scale
    ex, ey = (MAX_X + 1) * s, (MAX_Y + 1) * s
    ox, oy = ((MAX_X // CELL) + 1) * CELL * s, ((MAX_Y // CELL) + 1) * CELL * s
    w, h = MAP_W * s, MAP_H * s
    for x0, y0, x1, y1 in ((ox, 0, w, h), (0, oy, w, h)):
        for k in range(-(y1 - y0), x1 - x0, 8):
            d.line((x0 + max(k, 0), y0 + max(-k, 0), x0 + min(k + (y1 - y0), x1 - x0 - 1),
                    y0 + min(y1 - y0 - 1, (x1 - x0 - 1) - k)), fill=(255, 255, 0))
    d.line((ex, 0, ex, h), fill=(255, 255, 0), width=2)
    d.line((0, ey, w, ey), fill=(255, 255, 0), width=2)


LAYERS = [layer_lines, layer_mixed, layer_bounds]   # drawn in order over the tinted map (markers: layer_markers)


def render(base, grid, view, layers=None):
    """The map with the zones, enlarged: PIL RGB image."""
    img = (base or blank_map()).convert('RGBA')
    if view.tint:
        t = Image.new('RGBA', (W, H))
        t.putdata([KINDS[v][3] for row in grid for v in row])
        img = Image.alpha_composite(img, t.resize(img.size, Image.NEAREST))
    s = view.scale
    img = img.convert('RGB').resize((MAP_W * s, MAP_H * s), Image.NEAREST)
    d = ImageDraw.Draw(img)
    for layer in (LAYERS if layers is None else layers):
        if layer is not layer_lines or view.lines:
            layer(d, grid, view)
    return img


def export_png(base, grid, path, view=None):
    """The map with the zones at 4x, a legend with the cell counts below it."""
    view = view or View(scale=4)
    img = render(base, grid, view)
    legend = Image.new('RGB', (img.width, 24 + 18 * (len(KINDS) + 1)), (24, 22, 20))
    d = ImageDraw.Draw(legend)
    cn = counts(grid)
    for k, (name, val, slow, _, col) in KINDS.items():
        y = 8 + 18 * k
        d.rectangle((8, y, 22, y + 12), fill=col)
        d.text((30, y), f'{k}  {name}: {slow}, game value {val}, {cn[k]} cells of 4 x 4', fill=(240, 236, 220))
    d.text((30, 8 + 18 * len(KINDS)), 'Yellow: the knights\' reach ends at x 310, y 190; hatched cells are outside it',
           fill=(255, 255, 0))
    out = Image.new('RGB', (img.width, img.height + legend.height))
    out.paste(img, (0, 0))
    out.paste(legend, (0, img.height))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)


# ---- the markers (T1b) -----------------------------------------------------------------------------------------------

KNIGHT_COLOURS = ('#3070ff', '#ff9020', '#30c040', '#ff3030')   # knights 1-4: blue, orange, green, red (approved)
PLACE_COLOUR = '#40e0ff'        # towns and the other places
LAIR_COLOUR = '#c070ff'         # the lairs
BAD_COLOUR = '#ff2020'          # a refused position while dragging
LAIR_R = 7                      # the lair marker's radius in map pixels (the sprite is only 9 x 5)
MARKER_ORDER = ('place', 'village', 'start', 'lair', 'black')


def marker_label(key):
    k = MM.kind_of(key)
    return key[1] if k == 'village' else key[1:] if k == 'lair' else key


def marker_colour(key):
    k = MM.kind_of(key)
    if k in ('village', 'start'):
        return KNIGHT_COLOURS[int(key[1]) - 1]
    return {'place': PLACE_COLOUR, 'lair': LAIR_COLOUR, 'black': '#ffffff'}[k]


def marker_shapes(layout, s, hot=None, bad=False):
    """The markers as shapes in canvas pixels (s = zoom): (shape, key, coords, colour, extra). Shapes: 'box' (outline,
    extra = width), 'dash' (dashed outline), 'fill' (filled box, extra = outline colour), 'ring' (circle), 'link' (a
    thin line), 'text' (extra = the text). hot: the chosen or dragged marker, drawn last (red if bad)."""
    out = []
    keys = sorted(layout, key=lambda k: (k == hot, MARKER_ORDER.index(MM.kind_of(k))))
    for key in keys:
        kind = MM.kind_of(key)
        x0, y0, x1, y1 = MM.box(key, layout[key])
        bx = (x0 * s, y0 * s, (x1 + 1) * s - 1, (y1 + 1) * s - 1)
        col = BAD_COLOUR if key == hot and bad else marker_colour(key)
        if kind in ('village', 'place'):
            out.append(('box', key, bx, col, 2 if key != hot else 3))
            out.append(('text', key, (bx[0] + 3, bx[1] + 1), col, marker_label(key)))
        elif kind == 'start':
            v = MM.box('V' + key[1], layout['V' + key[1]])
            out.append(('link', key, ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2, (v[0] + v[2] + 1) * s / 2,
                                      (v[1] + v[3] + 1) * s / 2), col, None))
            out.append(('dash', key, bx, col, None))
            out.append(('text', key, (bx[0], bx[1] - 12), col, key))
        elif kind == 'black':
            out.append(('fill', key, bx, '#101010', BAD_COLOUR if key == hot and bad else '#ffffff'))
            out.append(('text', key, (bx[2] + 2, bx[1]), col, key))
        else:
            cx, cy, r = (x0 + x1 + 1) * s / 2, (y0 + y1 + 1) * s / 2, LAIR_R * s
            out.append(('ring', key, (cx - r, cy - r, cx + r, cy + r), col, 2 if key != hot else 3))
            out.append(('box', key, bx, col, 1))
            out.append(('text', key, (cx - 3 * len(marker_label(key)) - 1, cy - r - 13), col, marker_label(key)))
    return out


def marker_at(layout, mx, my):
    """The marker under map pixel (mx, my): knights' starts, the Black Knights and the lairs first, then the places."""
    for kinds in (('start', 'black'), ('lair',), ('village', 'place')):
        for key, pos in layout.items():
            if MM.kind_of(key) not in kinds:
                continue
            x0, y0, x1, y1 = MM.box(key, pos)
            if kinds == ('lair',):
                cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2
                if (mx - cx) ** 2 + (my - cy) ** 2 <= LAIR_R ** 2:
                    return key
            elif x0 - 1 <= mx <= x1 + 1 and y0 - 1 <= my <= y1 + 1:
                return key
    return None


def layer_markers(layout):
    """A layer (for render) drawing the markers with Pillow: the exports and the template."""
    def draw(d, grid, v):
        font = ImageFont.load_default()
        for shape, key, c, col, extra in marker_shapes(layout, v.scale):
            if shape in ('box', 'ring'):
                (d.rectangle if shape == 'box' else d.ellipse)(c, outline=col, width=extra or 2)
            elif shape == 'dash':
                d.rectangle(c, outline=col)
            elif shape == 'fill':
                d.rectangle(c, fill=col, outline=extra)
            elif shape == 'link':
                d.line(c, fill=col)
            else:
                d.text((c[0] + 1, c[1] + 1), extra, fill='black', font=font)
                d.text(c, extra, fill=col, font=font)
    return draw


def marker_info(key, pos, grid):
    """The status line for a marker: name, position, box, and the zone under it."""
    kind = MM.kind_of(key)
    x0, y0, x1, y1 = MM.box(key, pos)
    if kind in ('start', 'black'):
        px, py = pos[0] + 4, pos[1] + 10                       # the game's probe: the icon's feet (T2 may move it)
        cx, cy = min(max(px, 0) // CELL, W - 1), min(max(py, 0) // CELL, H - 1)
        name = f'Knight {key[1]}\'s start' if kind == 'start' else f'Black Knight {key[1]}\'s start'
        return f'{key} {name}  x {pos[0]} y {pos[1]}  zone at its feet: {KINDS[grid[cy][cx]][0]}'
    name = f'Lair {key[1:]} ({MM.region_of(key)})' if kind == 'lair' else MM.PLACES[key][4]
    kinds = Counter(grid[y][x] for y in range(max(y0, 0) // CELL, min(max(y1, 0) // CELL, H - 1) + 1)
                    for x in range(max(x0, 0) // CELL, min(max(x1, 0) // CELL, W - 1) + 1))
    zone = ', '.join(KINDS[k][0] for k, _ in kinds.most_common(2))
    return f'{key} {name}  x {pos[0]} y {pos[1]}  box {x0}-{x1} x {y0}-{y1}  zones: {zone}'


def original_layout(game=None):
    """The markers where the game has them: its MAIN.EXE if found, else the known table."""
    game = game or GAME
    img = MM.original_exe(game)
    return MM.layout_from_exe(img) if img is not None else MM.original_layout()


def load_layout(places=None, lairs=None, game=None):
    """The markers from places.csv and lairs.csv; without them the game's own."""
    places, lairs, game = places or PLACES_CSV, lairs or LAIRS_CSV, game or GAME
    if os.path.exists(places) and os.path.exists(lairs):
        with open(places) as a, open(lairs) as b:
            return MM.parse_layout(a.read(), b.read(), places)
    return original_layout(game)


def save_layout(layout, places=None, lairs=None):
    places, lairs = places or PLACES_CSV, lairs or LAIRS_CSV
    for path, text in ((places, MM.places_text(layout)), (lairs, MM.lairs_text(layout))):
        with open(path + '.tmp', 'w', newline='') as f:
            f.write(text)
        os.replace(path + '.tmp', path)


def export_template(base, grid, layout, folder, game=None, words=None):
    """For a map painter: template_4x.png (the map, the 8 x 8 grid, the bounds and the markers) and overlay_1x.png
    (transparent, 320 x 200: the places' outline sprites and the lairs' sprites where the game draws them, from the
    player's own MI.C; without it, the boxes) and, with the palette, palette.png: the project's 32 colours as squares
    for a colour dropper, its own six free colours included (map_mod.palette_swatch). Returns the files written."""
    game = game or GAME
    os.makedirs(folder, exist_ok=True)
    out = [os.path.join(folder, 'template_4x.png'), os.path.join(folder, 'overlay_1x.png')]
    render(base, grid, View(scale=4, tint=False), LAYERS + [layer_markers(layout)]).save(out[0])
    ov = Image.new('RGBA', (MAP_W, MAP_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    try:
        frames = MM.read_cel(open(os.path.join(game, 'DISKB', 'MI.C'), 'rb').read()) if words else None
    except (OSError, ValueError):
        frames = None
    for key, pos in layout.items():
        if MM.kind_of(key) in ('start', 'black'):
            continue
        if frames:
            spr = MM.sprite_image(frames[MM.PLACES[key][1] if key in MM.PLACES else MM.LAIR_FRAME], words)
            layer = Image.new('RGBA', (MAP_W, MAP_H), (0, 0, 0, 0))
            layer.paste(spr, pos)
            ov = Image.alpha_composite(ov, layer)
            d = ImageDraw.Draw(ov)
        else:
            d.rectangle(MM.box(key, pos), outline=marker_colour(key))
    ov.save(out[1])
    if words:
        out.append(os.path.join(folder, 'palette.png'))
        MM.palette_swatch(words).save(out[2])
    return out


# ---- the window ------------------------------------------------------------------------------------------------------

BG, FG, DIM = '#181614', '#f0ecdc', '#b8b4a0'
FILETYPES_PIC = [('Pictures', '*.png *.bmp *.gif *.pcx *.tif *.tiff'), ('All files', '*.*')]


class Editor:
    def __init__(self, tk_root):
        import tkinter as tk
        from tkinter import messagebox, filedialog
        from PIL import ImageTk
        self.tk, self.mb, self.fd, self.ImageTk = tk, messagebox, filedialog, ImageTk
        self.root = tk_root
        self.game_base, self.game_words = game_picture()
        self.pixels = self.words = self.src = None      # the player's own picture (None: the game's map)
        self.map_len = 0
        self.project_path = None
        self.view = View(scale=self.fit_scale())
        self.kind, self.tool, self.size = 1, 'brush', 1
        self.markers = True
        self.chosen = self.drag_key = self.drag_pos = None
        self.undo = []
        self.stroke = False
        self.note = ''
        self.load()
        self.root.configure(bg=BG)
        self.build_menu()
        self.build_side()
        main = tk.Frame(self.root, bg=BG)
        main.pack(side='left', padx=6, pady=6, anchor='n')
        self.canvas = tk.Canvas(main, highlightthickness=0, bg='black', cursor='crosshair')
        self.canvas.pack()
        self.status = tk.Label(main, anchor='w', fg=FG, bg=BG, font=('Consolas', 10), width=1)  # the canvas sets the width
        self.status.pack(fill='x')
        self.bind_keys()
        self.redraw()

    def fit_scale(self):
        """3x unless the screen is too small for it (the map, the side panel and the window's frame)."""
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        for s in (3, 2):
            if MAP_W * s + 260 <= sw and MAP_H * s + 140 <= sh:
                return s
        return 2

    def load(self):
        try:
            self.note = migrate()
            if os.path.exists(SAVE_PATH):
                self.grid, _ = read_zones(SAVE_PATH)
                self.saved = [r[:] for r in self.grid]
            else:
                self.grid, self.saved = game_grid(), None
            self.layout = load_layout()
            self.saved_layout = dict(self.layout) if os.path.exists(PLACES_CSV) else original_layout()
        except (OSError, ValueError) as e:
            self.mb.showerror('Map tool', str(e))
            raise SystemExit(1)
        if self.game_base is None:
            self.note = (self.note + '; ' if self.note else '') + 'map picture not found in ' + GAME

    # ---- panels
    def build_menu(self):
        tk = self.tk
        bar = tk.Menu(self.root)
        f = tk.Menu(bar, tearoff=0)
        f.add_command(label='Save zones and places', accelerator='Ctrl+S', command=self.save)
        f.add_separator()
        f.add_command(label='Load project...', command=self.load_project)
        f.add_command(label='Save project as...', command=self.save_project)
        f.add_separator()
        f.add_command(label='Export zones picture', command=self.export)
        f.add_separator()
        f.add_command(label='Close', command=self.close)
        bar.add_cascade(label='File', menu=f)
        m = tk.Menu(bar, tearoff=0)
        m.add_command(label='Import map picture (320 x 200)...', command=self.import_picture)
        m.add_command(label='Export map picture...', command=self.export_picture)
        m.add_command(label='Free colours of the palette...', command=self.palette_dialog)
        m.add_command(label="Use the game's map", command=self.use_game_map)
        m.add_separator()
        m.add_command(label='Export sprites (from your game files)...', command=self.export_sprites)
        m.add_command(label='Export template for painting...', command=self.export_template)
        m.add_separator()
        ready = APPLY_READY and MM.is_install(GAME)
        later = '' if ready else ' (needs an installed game)'
        state = 'normal' if ready else 'disabled'
        m.add_command(label='Apply to the game...' + later, command=self.apply, state=state)
        m.add_command(label='Restore original map' + later, command=self.restore, state=state)
        bar.add_cascade(label='Map', menu=m)
        p = tk.Menu(bar, tearoff=0)
        p.add_command(label='Markers on/off', accelerator='P', command=self.toggle_markers)
        p.add_command(label='Restore original positions', command=self.restore_positions)
        p.add_command(label='Restore original zones', command=self.reset)
        bar.add_cascade(label='Places', menu=p)
        self.root.config(menu=bar)

    def build_side(self):
        tk = self.tk
        side = tk.Frame(self.root, bg=BG)
        side.pack(side='left', fill='y', padx=6, pady=6)
        self.kindvar = tk.IntVar(value=self.kind)
        self.count_lbl = {}
        for k, (name, val, slow, _, col) in KINDS.items():
            f = tk.Frame(side, bg=BG)
            f.pack(anchor='w', pady=2)
            tk.Radiobutton(f, variable=self.kindvar, value=k, command=lambda: self.set_kind(self.kindvar.get()),
                           indicatoron=0, width=2, bg=col, selectcolor=col, text=str(k), relief='raised',
                           bd=3).pack(side='left')
            txt = tk.Frame(f, bg=BG)
            txt.pack(side='left', padx=4)
            tk.Label(txt, text=name, fg=FG, bg=BG, anchor='w').pack(anchor='w')
            self.count_lbl[k] = tk.Label(txt, fg=DIM, bg=BG, anchor='w')
            self.count_lbl[k].pack(anchor='w')
            self.count_lbl[k].base = f'{slow}, game value {val}'

        def row(label, var, values, cmd):
            f = tk.Frame(side, bg=BG)
            f.pack(anchor='w', pady=(6, 0))
            tk.Label(f, text=label, fg=FG, bg=BG, width=6, anchor='w').pack(side='left')
            for val, text in values:
                tk.Radiobutton(f, variable=var, value=val, text=text, command=cmd, indicatoron=0, width=5,
                               bg='#3a3630', fg=FG, selectcolor='#6a5a30').pack(side='left')
        self.modevar = tk.StringVar(value=self.view.mode)
        self.toolvar = tk.StringVar(value=self.tool)
        self.sizevar = tk.IntVar(value=self.size)
        row('Cells', self.modevar, (('4x4', '4x4'), ('2x2', '2x2')), lambda: self.set_mode(self.modevar.get()))
        row('Tool', self.toolvar, (('brush', 'Brush'), ('fill', 'Fill'), ('move', 'Move')),
            lambda: self.set_tool(self.toolvar.get()))
        row('Brush', self.sizevar, [(n, str(n)) for n in range(1, BRUSH_MAX + 1)],
            lambda: self.set_size(self.sizevar.get()))
        legend = tk.Frame(side, bg=BG)
        legend.pack(anchor='w', pady=(8, 0))
        for text, col in (('1-4 home villages, S1-S4 starts', KNIGHT_COLOURS[0]), ('HW WD SH VY MW places', PLACE_COLOUR),
                          ('1-24 lairs', LAIR_COLOUR), ('B1-B4 Black Knights', '#ffffff')):
            tk.Label(legend, text='■ ' + text, fg=col, bg=BG, anchor='w').pack(anchor='w')
        tk.Label(side, text='2x2: the game\'s own 8 x 8 blocks;\nmixed blocks are outlined magenta.\n'
                 'Yellow: the knights\' reach ends at\nx 310, y 190; hatched = outside.',
                 fg='#ffe000', bg=BG, justify='left').pack(anchor='w', pady=6)
        for text, cmd in (('Save (Ctrl+S)', self.save), ('Undo (Ctrl+Z)', self.undo_step),
                          ('Tint on/off (T)', self.toggle_tint), ('Grid on/off (G)', self.toggle_grid),
                          ('Markers on/off (P)', self.toggle_markers), ('Zoom 2x/3x/4x (Z)', self.toggle_zoom)):
            tk.Button(side, text=text, command=cmd).pack(fill='x', pady=1)
        self.map_lbl = tk.Label(side, fg=DIM, bg=BG, justify='left', anchor='w')
        self.map_lbl.pack(anchor='w', pady=(8, 0))
        tk.Label(side, text=f'Save writes {os.path.basename(SAVE_PATH)},\nplaces.csv and lairs.csv; then run\n'
                 'Custom_rules_on.bat (the game\nreads them at the rules build).',
                 fg=DIM, bg=BG, justify='left').pack(anchor='w', pady=6)

    def bind_keys(self):
        c, r = self.canvas, self.root
        c.bind('<Button-1>', self.press)
        c.bind('<B1-Motion>', self.drag)
        c.bind('<ButtonRelease-1>', self.release)
        c.bind('<Button-3>', self.rpick)
        c.bind('<Motion>', self.motion)
        c.bind('<Leave>', lambda e: (c.delete('cursor'), self.info()))
        r.bind('<Control-z>', lambda e: self.undo_step())
        r.bind('<Control-s>', lambda e: self.save())
        for k in KINDS:
            r.bind(str(k), lambda e, k=k: self.set_kind(k))
        for key in ('plus', 'equal', 'KP_Add'):
            r.bind(f'<{key}>', lambda e: self.set_size(self.size + 1))
        for key in ('minus', 'KP_Subtract'):
            r.bind(f'<{key}>', lambda e: self.set_size(self.size - 1))
        for key, fn in (('t', self.toggle_tint), ('g', self.toggle_grid), ('z', self.toggle_zoom),
                        ('p', self.toggle_markers), ('b', lambda: self.set_tool('brush')),
                        ('f', lambda: self.set_tool('fill')), ('v', lambda: self.set_tool('move')),
                        ('m', lambda: self.set_mode('2x2' if self.view.mode == '4x4' else '4x4'))):
            r.bind(key, lambda e, fn=fn: fn())
        for key, d in (('Left', (-1, 0)), ('Right', (1, 0)), ('Up', (0, -1)), ('Down', (0, 1))):
            r.bind(f'<{key}>', lambda e, d=d: self.nudge(*d))
        r.protocol('WM_DELETE_WINDOW', self.close)

    # ---- state
    def dirty(self):
        return self.saved is None or self.grid != self.saved or self.layout != self.saved_layout

    def set_kind(self, k):
        self.kind = k
        self.kindvar.set(k)
        self.info()

    def set_tool(self, t):
        self.tool = t
        self.toolvar.set(t)
        if t == 'move' and not self.markers:
            self.toggle_markers()
        self.canvas.config(cursor='fleur' if t == 'move' else 'crosshair')
        self.canvas.delete('cursor')
        self.info()

    def set_size(self, n):
        self.size = max(1, min(BRUSH_MAX, n))
        self.sizevar.set(self.size)
        self.info()

    def set_mode(self, m):
        self.view.mode = m
        self.modevar.set(m)
        self.redraw()

    def cell(self, e):
        x, y = e.x // (CELL * self.view.scale), e.y // (CELL * self.view.scale)
        return (x, y) if 0 <= x < W and 0 <= y < H else None

    def snapshot(self):
        return [r[:] for r in self.grid], dict(self.layout)

    def push_undo(self, snap=None):
        self.undo.append(snap or self.snapshot())
        del self.undo[:-UNDO_LIMIT]

    # ---- painting and moving
    def press(self, e):
        s = self.view.scale
        if self.tool == 'move':
            self.drag_key = marker_at(self.layout, e.x / s, e.y / s) if self.markers else None
            self.chosen = self.drag_key
            if self.drag_key:
                x, y = self.layout[self.drag_key]
                self.drag_off = (e.x // s - x, e.y // s - y)
                self.drag_pos = (x, y)
            self.draw_markers()
            self.motion(e)
            return
        c = self.cell(e)
        if not c:
            return
        if self.tool == 'fill':
            snap = self.snapshot()
            if fill(self.grid, c[0], c[1], self.kind, self.view.blk):
                self.push_undo(snap)
                self.redraw()
        else:
            self.stroke = False
            self.brush(c)
        self.motion(e)

    def drag(self, e):
        if self.tool == 'move':
            if self.drag_key:
                s = self.view.scale
                self.drag_pos = (e.x // s - self.drag_off[0], e.y // s - self.drag_off[1])
                self.draw_markers()
                why = MM.check_move(self.layout, self.drag_key, self.drag_pos)
                self.info(marker_info(self.drag_key, self.drag_pos, self.grid) + (f'  REFUSED: {why}' if why else ''))
            return
        c = self.cell(e)
        if c and self.tool == 'brush':
            self.brush(c)
        self.motion(e)

    def release(self, e):
        self.stroke = False
        if self.tool == 'move' and self.drag_key:
            key, pos = self.drag_key, self.drag_pos
            self.drag_key = self.drag_pos = None
            self.put_marker(key, pos)

    def put_marker(self, key, pos):
        if pos == self.layout[key]:
            self.draw_markers()
            return
        new = MM.move(self.layout, key, pos)
        if isinstance(new, str):
            self.note = f'{key} not moved: {new}'
        else:
            self.push_undo()
            self.layout, self.note = new, ''
        self.draw_markers()
        self.info(self.note or marker_info(key, self.layout[key], self.grid))

    def nudge(self, dx, dy):
        if self.chosen and self.markers and self.tool == 'move':
            x, y = self.layout[self.chosen]
            self.put_marker(self.chosen, (x + dx, y + dy))

    def brush(self, c):
        cells = brush_cells(c[0], c[1], self.size, self.view.blk)
        if any(self.grid[y][x] != self.kind for x, y in cells):
            if not self.stroke:
                self.push_undo()
                self.stroke = True
            paint(self.grid, cells, self.kind)
            self.redraw()

    def rpick(self, e):
        c = self.cell(e)
        if c:
            self.set_kind(self.grid[c[1]][c[0]])

    def undo_step(self):
        if self.undo:
            self.grid, self.layout = self.undo.pop()
            self.redraw()

    def motion(self, e):
        self.canvas.delete('cursor')
        s = self.view.scale
        if self.tool == 'move':
            if self.drag_key:
                return
            key = marker_at(self.layout, e.x / s, e.y / s) if self.markers else None
            if key:
                self.info(marker_info(key, self.layout[key], self.grid))
                return
        c = self.cell(e)
        if not c:
            self.info()
            return
        x, y = c
        if self.tool != 'move':
            cells = brush_cells(x, y, 1 if self.tool == 'fill' else self.size, self.view.blk)
            xs, ys = [p[0] for p in cells], [p[1] for p in cells]
            k4 = CELL * s
            self.canvas.create_rectangle(min(xs) * k4, min(ys) * k4, (max(xs) + 1) * k4 - 1, (max(ys) + 1) * k4 - 1,
                                         outline='white', tags='cursor')
        k = self.grid[y][x]
        b = block(self.grid, x // 2, y // 2)
        where = {'in': '', 'partly': '  (partly outside the reach)', 'outside': '  (outside the reach)'}[cell_bounds(x, y)]
        mixed = f'  block mixed: the game uses {block_kind(b)}' if len(set(b)) > 1 else ''
        self.info(f'pixel {e.x // s},{e.y // s}  cell {x},{y} (x {x * CELL}-{x * CELL + 3}, y {y * CELL}-{y * CELL + 3})'
                  f'  8x8 {x // 2},{y // 2}  kind {k} {KINDS[k][0]}{mixed}{where}')

    def info(self, text=''):
        tool = {'fill': 'fill', 'move': 'move'}.get(self.tool, f'brush {self.size}')
        self.status.config(text=(text or self.note or f'{KINDS[self.kind][0]}')
                           + f'   [{self.view.mode} {tool} kind {self.kind}]' + ('  [unsaved]' if self.dirty() else ''))

    # ---- views
    def toggle_tint(self):
        self.view.tint = not self.view.tint
        self.redraw()

    def toggle_grid(self):
        self.view.lines = not self.view.lines
        self.redraw()

    def toggle_markers(self):
        self.markers = not self.markers
        self.draw_markers()

    def toggle_zoom(self):
        self.view.scale = ZOOMS[(ZOOMS.index(self.view.scale) + 1) % len(ZOOMS)]
        self.redraw()

    def base(self):
        if self.pixels is not None:
            return MM.pixels_image(self.pixels, self.words).convert('RGB')
        return self.game_base

    def redraw(self):
        img = render(self.base(), self.grid, self.view)
        self.photo = self.ImageTk.PhotoImage(img)
        self.canvas.config(width=img.width, height=img.height)
        self.canvas.delete('map')
        self.canvas.create_image(0, 0, anchor='nw', image=self.photo, tags='map')
        self.canvas.tag_lower('map')
        self.draw_markers()
        cn = counts(self.grid)
        for k, lbl in self.count_lbl.items():
            lbl.config(text=f'{lbl.base}: {cn[k]} cells')
        own = self.pixels is not None
        self.map_lbl.config(text=('Map: your picture' + (f', {self.map_len:,} bytes' if self.map_len else '')
                                  if own else "Map: the game's own")
                            + (f'\nProject: {os.path.basename(self.project_path)}' if self.project_path else ''))
        self.root.title('Moonstone map tool' + (f' - {os.path.basename(self.project_path)}' if self.project_path else ''))
        self.info()

    def draw_markers(self):
        c = self.canvas
        c.delete('marker')
        if not self.markers:
            return
        lay = dict(self.layout)
        bad = False
        if self.drag_key and self.drag_pos:
            lay[self.drag_key] = self.drag_pos
            bad = bool(MM.check_move(self.layout, self.drag_key, self.drag_pos))
            if not bad and MM.kind_of(self.drag_key) == 'village':
                lay = MM.move(self.layout, self.drag_key, self.drag_pos)
        hot = self.drag_key or self.chosen
        font = ('Arial', 6 + self.view.scale, 'bold')
        for shape, key, xy, col, extra in marker_shapes(lay, self.view.scale, hot, bad):
            if shape == 'box':
                c.create_rectangle(*xy, outline=col, width=extra, tags='marker')
            elif shape == 'dash':
                c.create_rectangle(*xy, outline=col, width=2, dash=(3, 2), tags='marker')
            elif shape == 'fill':
                c.create_rectangle(*xy, fill=col, outline=extra, width=2, tags='marker')
            elif shape == 'ring':
                c.create_oval(*xy, outline=col, width=extra, tags='marker')
            elif shape == 'link':
                c.create_line(*xy, fill=col, dash=(2, 3), tags='marker')
            else:
                c.create_text(xy[0] + 1, xy[1] + 1, text=extra, anchor='nw', fill='black', font=font, tags='marker')
                c.create_text(*xy, text=extra, anchor='nw', fill=col, font=font, tags='marker')
        c.tag_raise('cursor')

    # ---- files
    def save(self):
        try:
            save_zones(SAVE_PATH, self.grid)
            save_layout(self.layout)
        except OSError as e:
            self.mb.showerror('Save', str(e))
            return False
        self.saved, self.saved_layout = [r[:] for r in self.grid], dict(self.layout)
        self.note = f'saved {os.path.basename(SAVE_PATH)}, places.csv, lairs.csv'
        self.info()
        return True

    def reset(self):
        if self.mb.askyesno('Restore original zones', "Replace the zones with the game's own (rocks in rows 0-13)?"):
            try:
                g = MM.original_zones(GAME, shift_cells=probe_shift()) or game_grid()
            except (OSError, ValueError) as e:
                self.mb.showerror('Restore original zones', str(e))
                return
            self.push_undo()
            self.grid = g
            self.redraw()

    def restore_positions(self):
        if self.mb.askyesno('Restore original positions', 'Put every place, start and lair back where the game has it?'):
            self.push_undo()
            self.layout = original_layout()
            self.redraw()

    def export(self):
        export_png(self.base(), self.grid, EXPORT)
        self.mb.showinfo('Export', f'Wrote {EXPORT}')

    def project(self):
        name = os.path.splitext(os.path.basename(self.project_path or 'map'))[0]
        return MM.Project(self.grid, self.layout, self.pixels, self.words, name, self.view.mode)

    def save_project(self):
        path = self.fd.asksaveasfilename(title='Save project', defaultextension='.zip',
                                         filetypes=[('Map project', '*.zip')], initialdir=GAME)
        if not path:
            return
        try:
            MM.save_project(path, self.project(), zones_text)
        except OSError as e:
            self.mb.showerror('Save project', str(e))
            return
        self.project_path = path
        self.redraw()

    def load_project(self):
        if self.dirty() and not self.mb.askyesno('Load project', 'Unsaved changes will be lost. Go on?'):
            return
        path = self.fd.askopenfilename(title='Load project', filetypes=[('Map project', '*.zip')], initialdir=GAME)
        if not path:
            return
        try:
            p = MM.load_project(path, lambda t: to_grid80(parse_rows(t, 'zones.csv'), 'zones.csv'))
        except (OSError, ValueError, KeyError) as e:
            self.mb.showerror('Load project', str(e))
            return
        self.push_undo()
        self.grid, self.layout, self.pixels, self.words = p.zones, p.layout, p.pixels, p.words
        self.src = None
        self.project_path = path
        self.view.mode = p.cells
        self.modevar.set(p.cells)
        self.measure_map()

    # ---- the map picture (T1c)
    def palette(self):
        return self.words or self.game_words

    def measure_map(self):
        self.map_len = 0
        if self.pixels is not None:
            self.root.config(cursor='watch')
            self.root.update()
            self.map_len = len(MM.write_map(self.pixels, self.words))
            self.root.config(cursor='')
        self.redraw()

    def import_picture(self):
        if not self.game_words:
            self.mb.showerror('Import', f"The game's map (DISKB/MAP.CMP) was not found in {GAME}: its palette is needed.")
            return
        path = self.fd.askopenfilename(title='Import map picture (320 x 200)', filetypes=FILETYPES_PIC)
        if not path:
            return
        try:
            img = Image.open(path)
            img.load()
            words = list(self.words or self.game_words)
            pixels, changed = MM.reduce_image(img, words)
        except (OSError, ValueError) as e:
            self.mb.showerror('Import', str(e))
            return
        self.src, self.pixels, self.words = img, pixels, words
        self.measure_map()
        self.report_map(changed)

    def report_map(self, changed):
        limit = MM.MAP_LIMIT if APPLY_READY else MM.MAP_GAME_LEN
        msg = (f'{changed:,} of {MAP_W * MAP_H:,} pixels took the nearest of the map\'s colours.\n' if changed else
               'Every pixel has a colour of the map\'s palette.\n')
        msg += f'As MAP.CMP: {self.map_len:,} bytes (the game takes {limit:,}).'
        if self.map_len > limit:
            msg += '\nToo big: use fewer colours or larger flat areas.'
        if changed:
            msg += '\nMap > Free colours of the palette can fit six colours to the picture.'
        self.mb.showinfo('Map picture', msg)

    def export_picture(self):
        path = self.fd.asksaveasfilename(title='Export map picture', defaultextension='.png',
                                         filetypes=[('PNG', '*.png')])
        if not path:
            return
        m = (None, self.words, self.pixels) if self.pixels is not None else MM.game_map(GAME)
        if not m:
            self.mb.showerror('Export', "The game's map was not found.")
            return
        MM.pixels_image(m[2], m[1]).save(path)
        self.note = f'wrote {path} (paletted: it imports back unchanged)'
        self.info()

    def use_game_map(self):
        self.pixels = self.words = self.src = None
        self.measure_map()

    def palette_dialog(self):
        if self.pixels is None:
            self.mb.showinfo('Palette', 'Import a map picture first: the free colours belong to your own picture.')
            return
        tk = self.tk
        from tkinter import colorchooser
        top = tk.Toplevel(self.root, bg=BG)
        top.title('Map palette')
        top.transient(self.root)
        top.geometry(f'+{self.canvas.winfo_rootx() + self.canvas.winfo_width() - 420}+{self.canvas.winfo_rooty() + 20}')
        tk.Label(top, text='The 32 colours of the map. The 26 that the map\'s sprites use stay fixed;\n'
                 f'the six free ones ({", ".join(map(str, MM.FREE_COLOURS))}) are yours to set.',
                 fg=FG, bg=BG, justify='left').grid(row=0, column=0, columnspan=8, padx=6, pady=6, sticky='w')
        cells = []

        def hexc(w):
            return '#%02x%02x%02x' % MM.word_rgb(w)

        def show():
            for i, b in enumerate(cells):
                b.config(bg=hexc(self.words[i]), activebackground=hexc(self.words[i]))

        def changed():
            if self.src is not None:
                self.pixels, _ = MM.reduce_image(self.src, self.words)
            self.measure_map()
            show()

        def pick(i):
            rgb, _ = colorchooser.askcolor(hexc(self.words[i]), parent=top, title=f'Colour {i}')
            if rgb:
                self.words[i] = MM.set_colour(self.words[i], MM.rgb_word(tuple(int(c) for c in rgb)))
                changed()

        for i in range(32):
            free = i in MM.FREE_COLOURS
            b = tk.Button(top, text=str(i) if free else '', width=4, height=2, relief='raised' if free else 'flat',
                          state='normal' if free else 'disabled', command=lambda i=i: pick(i))
            b.grid(row=1 + i // 8, column=i % 8, padx=2, pady=2)
            cells.append(b)
        show()

        def suggest():
            src = self.src if self.src is not None else MM.pixels_image(self.pixels, self.words)
            self.words = MM.suggest_free(src, self.words)
            changed()

        def game():
            for i in MM.FREE_COLOURS:
                self.words[i] = self.game_words[i]
            changed()
        f = tk.Frame(top, bg=BG)
        f.grid(row=6, column=0, columnspan=8, pady=6)
        tk.Button(f, text='Fit the free colours to the picture', command=suggest).pack(side='left', padx=3)
        tk.Button(f, text="The game's colours", command=game).pack(side='left', padx=3)
        tk.Button(f, text='Close', command=top.destroy).pack(side='left', padx=3)

    def export_sprites(self):
        folder = self.fd.askdirectory(title='Folder for the sprites', initialdir=GAME)
        if not folder or not self.palette():
            return
        try:
            names = MM.export_sprites(GAME, folder, self.palette())
        except (OSError, ValueError, IndexError) as e:
            self.mb.showerror('Export sprites', str(e))
            return
        self.mb.showinfo('Export sprites', f'Wrote {len(names)} sprites from your game files to {folder}.')

    def export_template(self):
        folder = self.fd.askdirectory(title='Folder for the template', initialdir=GAME)
        if not folder:
            return
        try:
            out = export_template(self.base(), self.grid, self.layout, folder, GAME, self.palette())
        except OSError as e:
            self.mb.showerror('Export template', str(e))
            return
        self.mb.showinfo('Export template', 'Wrote\n' + '\n'.join(out))

    def rebuild(self):
        """The rules build (Custom_rules_on.bat's work), so the game reads the files at once."""
        import rules
        rules.install(GAME)

    def write_files(self):
        save_zones(SAVE_PATH, self.grid)
        save_layout(self.layout)

    def apply(self):
        """Apply the project to the game, all or nothing (D135): the map picture as MAP.CMP on both disks (the originals
        kept as MAP.CMP.orig first), the zones and places saved, custom_terrain and custom_places on, the rules built."""
        data = lines = None
        try:
            if self.pixels is not None:
                data = MM.write_map(self.pixels, self.words)
                lines = MM.apply_plan(GAME, data, MM.MAP_LIMIT)
        except (OSError, ValueError) as e:
            self.mb.showerror('Apply', str(e))
            return
        lines = (lines or (["the game's own map (the original put back if the tool had changed it)"]))
        lines += [f'save {os.path.basename(SAVE_PATH)}, places.csv and lairs.csv',
                  'set [Map] custom_terrain and custom_places on in custom_rules.ini', 'build the rules (Custom_rules_on)']
        if not self.mb.askyesno('Apply to the game', 'This will:\n- ' + '\n- '.join(lines) + '\n\nGo on?'):
            return
        self.root.config(cursor='watch')
        self.root.update()
        try:
            MM.apply_project(GAME, data, self.write_files, self.rebuild,
                             keep=(SAVE_PATH, PLACES_CSV, LAIRS_CSV))
        except Exception as e:                       # rules.RulesError, Busy, OSError, ValueError: all put back
            self.mb.showerror('Apply', f'{e}\n\nThe game was left as it was.')
            return
        finally:
            self.root.config(cursor='')
        self.saved, self.saved_layout = [r[:] for r in self.grid], dict(self.layout)
        self.note = 'applied: restart DOSBox-X to play it'
        self.info()
        self.mb.showinfo('Apply', 'Done. Restart DOSBox-X to play the new map.')

    def restore(self):
        """Restore original (D135): both MAP.CMP from MAP.CMP.orig, custom_places and custom_terrain off, the rules built.
        The tool's files stay as they are (load or paint them again later)."""
        if not self.mb.askyesno('Restore original map', 'Put the original map back on both disks, switch the custom '
                                'places and terrain off and build the rules?'):
            return
        try:
            MM.restore_all(GAME, self.rebuild)
        except Exception as e:
            self.mb.showerror('Restore original map', str(e))
            return
        self.use_game_map()
        self.mb.showinfo('Restore original map', "The game's original map, places and terrain are back. Restart DOSBox-X.")

    def close(self):
        if self.dirty():
            a = self.mb.askyesnocancel('Unsaved changes', 'Save the zones and places before closing?')
            if a is None:
                return
            if a and not self.save():
                return
        self.root.destroy()


def main():
    import tkinter as tk
    root = tk.Tk()
    Editor(root)
    root.mainloop()


if __name__ == '__main__':
    sys.exit(main())
