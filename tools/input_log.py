"""Read INPUT.LOG, written by SAVEHOOK.COM after every fight when custom_rules.ini has input_log = on (D24).

Each fight appends a 6-byte header ('IL', entries, entries lost when the fight had more than SAVEHOOK keeps) and its
entries, 6 bytes each: the BIOS tick (18.2 a second), the kind, a knight number (0-3) or a scan code, and two values.
  1 key down / 2 key up: the scan code
  3 input read: a knight's direction and fire bits as the game read them, and as SAVEHOOK passed them on (input_buffer,
    the directions let go just before fire, input_chord's wait: 0)
  4 attack: the bits the attack was picked from, and the facing (1 right, 3 left)
For every attack the tool shows how long after the last fire key it started (the latency players feel; with two
players pressing at once, the nearer press counts).
Usage: python -I tools/input_log.py [INPUT.LOG]"""
import struct, sys

KINDS = {1: 'key down', 2: 'key up', 3: 'input', 4: 'attack'}
KEYS = {0x1c: 'Enter (P1 fire)', 0x48: 'Up', 0x50: 'Down', 0x4b: 'Left', 0x4d: 'Right',
        0x0f: 'Tab (P2 fire)', 0x11: 'W', 0x1f: 'S', 0x1e: 'A', 0x20: 'D',
        0x30: 'B (P3 fire)', 0x17: 'I', 0x25: 'K', 0x24: 'J', 0x26: 'L'}
FIRE_KEYS = (0x1c, 0x0f, 0x30)
TICK_MS = 1000 / 18.2065
# the attack each set of bits gives, facing right (1000:0C32); facing left, left and right change places
MOVES = {0x10: 'overhead chop', 0x11: 'swing', 0x12: 'backward thrust', 0x14: 'sidestep', 0x15: 'lunge',
         0x16: 'block', 0x18: 'overhead chop', 0x19: 'upward thrust', 0x1a: 'dagger throw'}


def bits_text(b):
    if not b:
        return '-'
    names = [n for bit, n in ((0x10, 'fire'), (8, 'up'), (4, 'down'), (2, 'left'), (1, 'right')) if b & bit]
    return '+'.join(names)


def attack(bits, facing):
    b = (bits | 0x10) & 0x1f
    if facing == 3 and b & 3 in (1, 2):
        b ^= 3                                     # facing left: the table with left and right swapped
    if b == 0x10:
        return 'overhead chop' if bits & 8 or not bits & 0x0f else MOVES.get(b, '?')
    return MOVES.get(b, '?')


def fights(data):
    i = 0
    while i + 6 <= len(data):
        tag, n, lost = struct.unpack_from('<2sHH', data, i)
        if tag != b'IL':
            raise ValueError(f'offset {i}: not a fight header')
        entries = [struct.unpack_from('<HBBBB', data, i + 6 + 6 * k) for k in range(n)]
        yield entries, lost
        i += 6 + 6 * n


def report(data, out=print):
    for number, (entries, lost) in enumerate(fights(data), 1):
        out(f'Fight {number}: {len(entries)} entries' + (f', {lost} lost (the log was full)' if lost else ''))
        if not entries:
            continue
        start, last_fire, latencies = entries[0][0], None, []
        for tick, kind, who, a, b in entries:
            t = (tick - start) & 0xffff
            if kind in (1, 2):
                if kind == 1 and who in FIRE_KEYS:
                    last_fire = tick
                out(f'  {t:5}  {KINDS[kind]:8}  {KEYS.get(who, hex(who))}')
            elif kind == 3:
                note = '' if a == b else ('   held back (input_chord)' if not b else '   changed')
                out(f'  {t:5}  input     knight {who}: {bits_text(a)} -> {bits_text(b)}{note}')
            elif kind == 4:
                delay = ((tick - last_fire) & 0xffff) if last_fire is not None else None
                last_fire = None
                if delay is not None:
                    latencies.append(delay)
                lat = f', {delay * TICK_MS:.0f} ms after fire' if delay is not None else ''
                out(f'  {t:5}  attack    knight {who}: {bits_text(a)} facing {"right" if b == 1 else "left"}'
                    f' = {attack(a, b)}{lat}')
            else:
                out(f'  {t:5}  kind {kind}: {who} {a} {b}')
        if latencies:
            out(f'  attacks {len(latencies)}: from fire to attack {min(latencies) * TICK_MS:.0f}-'
                f'{max(latencies) * TICK_MS:.0f} ms, mean {sum(latencies) / len(latencies) * TICK_MS:.0f} ms')


if __name__ == '__main__':
    report(open(sys.argv[1] if len(sys.argv) > 1 else 'INPUT.LOG', 'rb').read())
