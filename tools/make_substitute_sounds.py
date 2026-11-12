"""Synthesize substitute sounds for samples the Amiga version of Moonstone has and the DOS version lacks.

Every sound here is made by this code from a description of what the sound is (a hoof thud, a whip of air, wind),
its length and the rate the game plays it at. Nothing is taken from, or modelled on, the Amiga samples, so the results
can be distributed with Moonstone Rebuilt. See docs/amiga-audio-plan-2026-11-11.md, section 5.2.

Each sound gets a few candidates (a, b, c) to choose from by ear:
  <out>/NAME_x.wav            the sound itself: mono, 8 bits, as many samples as the sample it stands in for, at the
                              rate the game plays that sample
  <out>/preview/NAME_x.wav    how the game would play it (44.1 kHz, stepped as an Amiga plays samples, at the
                              program's volume; loops played twice)
  <out>/index.html            a page to listen to the previews

Usage: python -I tools/make_substitute_sounds.py <output folder>            the candidates
       python -I tools/make_substitute_sounds.py <output folder> chosen     only the chosen ones, as NAME.wav"""
import sys, os, wave, html
import numpy as np

PREVIEW_RATE = 44100

# name: (stands in for, samples, rate the game plays it at (Hz), volume of that program (0-63), loops, what it is)
SOUNDS = {
    'beast_gallop': ('BEASTGALLOP.SND', 672, 2934, 24, False, 'one hoof beat of the war beast: a low, soft thud'),
    'dragon_thud': ('dragthud1c', 4008, 4655, 63, False, 'the dragon hits the ground: a heavy, deep thud'),
    'trogg_bang': ('bang2', 1832, 4395, 63, False, 'a dull bang'),
    'troll_bash': ('bash', 6670, 11084, 60, False, 'the troll\'s club lands: a thump with a crunch'),
    'balok_swish': ('BALSWISH2b', 1872, 9852, 53, False, 'a big paw cuts the air: a short, heavy swish'),
    'guardian_sparks': ('sparx2b', 8770, 9309, 35, True, 'sparks crackling, as a steady texture (the game shuffles four parts of it)'),
    'wind': ('wind2', 20108, 6581, 30, True, 'wind over open ground, looping'),
    'menu_click': ('clik2', 318, 6982, 30, False, 'a short click'),
    'dice': ('dice2c', 2226, 5533, 60, False, 'dice rattle on a table'),
}

# The candidate chosen by ear for each sound (the user, 12 Nov 2026)
CHOSEN = {'beast_gallop': 'a', 'dragon_thud': 'a', 'trogg_bang': 'b', 'troll_bash': 'b', 'balok_swish': 'b',
          'guardian_sparks': 'c', 'wind': 'a', 'menu_click': 'b', 'dice': 'b'}

def t_axis(n, rate): return np.arange(n) / rate
def decay(n, rate, tau): return np.exp(-t_axis(n, rate) / tau)
def noise(n, rng): return rng.standard_normal(n)

def band(x, rate, lo=None, hi=None, order=2):
    """Keep lo..hi Hz (smooth edges; the sound is treated as one period, which suits the looping ones)."""
    f = np.fft.rfftfreq(len(x), 1.0 / rate)
    h = np.ones_like(f)
    if hi: h /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo: h /= np.sqrt(1 + (lo / np.maximum(f, 1e-6)) ** (2 * order))
    return np.fft.irfft(np.fft.rfft(x) * h, len(x))

def sweep(n, rate, f0, f1, tau):
    """A sine falling from f0 to f1 Hz with time constant tau."""
    f = f1 + (f0 - f1) * np.exp(-t_axis(n, rate) / tau)
    return np.sin(2 * np.pi * np.cumsum(f) / rate)

def at(n, rate, when, piece):
    """piece placed at `when` seconds in n samples of silence."""
    out, i = np.zeros(n), int(when * rate)
    m = max(0, min(len(piece), n - i))
    out[i:i + m] = piece[:m]
    return out

def thud(n, rate, rng, f0, f1, tau, click=0.4, click_hi=900, rumble=0.0):
    x = sweep(n, rate, f0, f1, tau * 0.6) * decay(n, rate, tau)
    x += click * band(noise(n, rng), rate, hi=click_hi) * decay(n, rate, tau * 0.25)
    if rumble: x += rumble * band(noise(n, rng), rate, hi=220) * decay(n, rate, tau * 1.6)
    return x

def swish(n, rate, rng, bands, rise=0.45):
    """Noise whose colour moves through `bands` [(lo, hi)] while its loudness rises and falls."""
    t = np.linspace(0, 1, n)
    x = np.zeros(n)
    for k, (lo, hi) in enumerate(bands):
        centre = (k + 0.5) / len(bands)
        x += band(noise(n, rng), rate, lo, hi) * np.exp(-((t - centre) / 0.22) ** 2)
    hump = np.where(t < rise, np.sin(0.5 * np.pi * t / rise) ** 2, np.cos(0.5 * np.pi * (t - rise) / (1 - rise)) ** 2)
    return x * hump

def crackle(n, rate, rng, per_second, f_lo, f_hi, ring, hiss=0.0, gate=None):
    """Random small cracks (damped sines) on a bed of hiss; the same all the way through, so any part of it loops."""
    x = np.zeros(n)
    for _ in range(int(per_second * n / rate)):
        m = int(ring * 6 * rate)
        crack = np.sin(2 * np.pi * rng.uniform(f_lo, f_hi) * t_axis(m, rate)) * decay(m, rate, ring * rng.uniform(0.5, 1.5))
        i = rng.integers(0, n)
        x += np.roll(at(n, rate, 0, crack * rng.uniform(0.3, 1.0) ** 2), i)
    if hiss:
        bed = band(noise(n, rng), rate, lo=1500)
        if gate: bed *= (np.sin(2 * np.pi * gate * t_axis(n, rate)) > 0.2)
        x += hiss * bed
    return x

def wind(n, rate, rng, lo, hi, gusts, whistle=0.0):
    """Looping wind: coloured noise whose loudness and colour swell and fade a whole number of times in the loop."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    low, high = band(noise(n, rng), rate, lo, (lo * hi) ** 0.5), band(noise(n, rng), rate, (lo * hi) ** 0.5, hi)
    swell = lambda k: 0.6 + 0.4 * np.sin(k * t + rng.uniform(0, 2 * np.pi))
    x = low * swell(gusts) + 0.8 * high * swell(gusts + 1) * swell(1)
    if whistle:
        x += whistle * band(noise(n, rng), rate, 620, 760, order=6) * (0.5 + 0.5 * np.sin(2 * t + rng.uniform(0, 6))) ** 2
    return x

def rattle(n, rate, rng, hits, f_lo, f_hi, ring, spread):
    """Several small knocks, most of them early, each quieter than the one before."""
    x = np.zeros(n)
    times = np.sort(rng.beta(1.2, 2.2, hits)) * spread
    for k, when in enumerate(times):
        m = int(ring * 8 * rate)
        knock = np.sin(2 * np.pi * rng.uniform(f_lo, f_hi) * t_axis(m, rate)) * decay(m, rate, ring)
        knock += 0.5 * band(noise(m, rng), rate, lo=800) * decay(m, rate, ring * 0.5)
        x += at(n, rate, when, knock * (0.95 ** k) * rng.uniform(0.6, 1.0))
    return x

def candidates(name, n, rate):
    """-> [(letter, what makes this one different, samples as floats)]"""
    r = lambda k: np.random.default_rng(1000 * sorted(SOUNDS).index(name) + k)
    if name == 'beast_gallop':
        return [('a', 'one soft beat', thud(n, rate, r(1), 110, 45, 0.05, click=0.5)),
                ('b', 'duller and longer', thud(n, rate, r(2), 90, 40, 0.07, click=0.3)),
                ('c', 'two quick beats', thud(n, rate, r(3), 130, 55, 0.03, click=0.7)
                                         + 0.7 * at(n, rate, 0.085, thud(n, rate, r(4), 115, 50, 0.035, click=0.6)))]
    if name == 'dragon_thud':
        return [('a', 'one deep thud', thud(n, rate, r(1), 70, 30, 0.25, click=0.5, click_hi=1200, rumble=0.6)),
                ('b', 'deeper, long rumble', thud(n, rate, r(2), 55, 26, 0.35, click=0.35, click_hi=900, rumble=1.0)),
                ('c', 'a thud and a bounce', thud(n, rate, r(3), 75, 32, 0.18, click=0.6, click_hi=1300, rumble=0.5)
                                             + 0.5 * at(n, rate, 0.33, thud(n, rate, r(4), 65, 30, 0.14, click=0.3, rumble=0.4)))]
    if name == 'trogg_bang':
        body = lambda rng, tau, lp: band(noise(n, rng), rate, hi=lp) * decay(n, rate, tau) + 0.7 * sweep(n, rate, 95, 50, 0.06) * decay(n, rate, tau * 1.2)
        return [('a', 'a short dull bang', body(r(1), 0.08, 1800)),
                ('b', 'boomier', body(r(2), 0.14, 1200)),
                ('c', 'sharp, with a slap back', body(r(3), 0.05, 2000) + 0.35 * at(n, rate, 0.12, body(r(4), 0.05, 1400)))]
    if name == 'troll_bash':
        def bash(rng, f0, crunch, debris):
            x = sweep(n, rate, f0, 55, 0.05) * decay(n, rate, 0.09)
            x += crunch * band(noise(n, rng), rate, 300, 2500) * decay(n, rate, 0.06)
            if debris: x += debris * crackle(n, rate, rng, 45, 500, 1800, 0.004) * decay(n, rate, 0.2)
            return x
        return [('a', 'a thump with a crunch', bash(r(1), 160, 0.8, 0)),
                ('b', 'heavier, less crunch', bash(r(2), 120, 0.45, 0)),
                ('c', 'with bits falling after it', bash(r(3), 170, 0.8, 0.5))]
    if name == 'balok_swish':
        return [('a', 'low to high and back', swish(n, rate, r(1), [(400, 900), (900, 1800), (1800, 3500), (900, 1800)])),
                ('b', 'heavier and lower', swish(n, rate, r(2), [(250, 600), (500, 1200), (900, 2200), (500, 1200)])),
                ('c', 'a quick rising whip', swish(n, rate, r(3), [(500, 1000), (1000, 2000), (2000, 4000)], rise=0.7))]
    if name == 'guardian_sparks':
        return [('a', 'crackle with a little hiss', crackle(n, rate, r(1), 70, 1800, 4200, 0.003, hiss=0.15)),
                ('b', 'fewer, sharper cracks', crackle(n, rate, r(2), 28, 2200, 4400, 0.002, hiss=0.05)),
                ('c', 'electric: buzzing hiss', crackle(n, rate, r(3), 45, 1500, 4000, 0.003, hiss=0.5, gate=64))]
    if name == 'wind':
        return [('a', 'steady moor wind', wind(n, rate, r(1), 150, 1500, 1)),
                ('b', 'low and gusty', wind(n, rate, r(2), 90, 900, 2)),
                ('c', 'with a whistle in it', wind(n, rate, r(3), 180, 1600, 1, whistle=1.5))]
    if name == 'menu_click':
        tick = lambda f, tau, hiss, rng: np.sin(2 * np.pi * f * t_axis(n, rate)) * decay(n, rate, tau) + hiss * noise(n, rng) * decay(n, rate, tau * 0.4)
        return [('a', 'a bright tick', tick(1800, 0.006, 0.3, r(1))),
                ('b', 'a lower tock', tick(900, 0.009, 0.15, r(2))),
                ('c', 'a double tick', tick(1500, 0.004, 0.3, r(3)) + 0.7 * at(n, rate, 0.018, tick(2000, 0.004, 0.3, r(4))))]
    if name == 'dice':
        return [('a', 'six knocks, bone on wood', rattle(n, rate, r(1), 6, 1200, 2200, 0.004, 0.33)),
                ('b', 'wooden, fewer knocks', rattle(n, rate, r(2), 4, 600, 1000, 0.006, 0.3)),
                ('c', 'a long busy rattle', rattle(n, rate, r(3), 9, 1400, 2400, 0.003, 0.36))]
    raise KeyError(name)

def to_8bit(x):
    """Full scale, as the game's samples are, with the last few samples faded so a one-shot does not click."""
    return np.round(x / max(np.abs(x).max(), 1e-9) * 127).astype(np.int8)

def write_sound(path, pcm, rate):
    with wave.open(path, 'wb') as w:                              # 8-bit WAV files are unsigned
        w.setnchannels(1); w.setsampwidth(1); w.setframerate(rate); w.writeframes((pcm.astype(np.int16) + 128).astype(np.uint8).tobytes())

def write_preview(path, pcm, rate, volume, loops):
    data = np.tile(pcm, 2) if loops else pcm
    n = int(len(data) * PREVIEW_RATE / rate)
    x = data[np.minimum((np.arange(n) * rate / PREVIEW_RATE).astype(np.int64), len(data) - 1)] / 128.0 * volume / 64.0
    spectrum, f = np.fft.rfft(x), np.fft.rfftfreq(n, 1.0 / PREVIEW_RATE)   # the Amiga 500's output filter
    x = np.fft.irfft(spectrum / (1 + 1j * f / 4900.0), n)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(PREVIEW_RATE)
        w.writeframes(np.clip(x * 32767 * 0.9, -32768, 32767).astype('<i2').tobytes())

def finished(name, x, loops):
    pcm = to_8bit(x)
    if not loops: pcm[-8:] = (pcm[-8:] * np.linspace(1, 0, 8)).astype(np.int8)
    return pcm

def main(out, which='candidates'):
    if which == 'chosen':
        os.makedirs(out, exist_ok=True)
        for name, (stands_for, n, rate, volume, loops, what) in SOUNDS.items():
            x = next(x for letter, how, x in candidates(name, n, rate) if letter == CHOSEN[name])
            write_sound(os.path.join(out, f'{name}.wav'), finished(name, x, loops), rate)
        print(f'{len(SOUNDS)} chosen sounds written to {out}')
        return
    os.makedirs(os.path.join(out, 'preview'), exist_ok=True)
    page = ['<!doctype html><meta charset="utf-8"><title>Substitute sounds: candidates</title>',
            '<style>body{font:14px sans-serif;margin:16px;max-width:1000px}td,th{padding:4px 8px;text-align:left;'
            'border-bottom:1px solid #8884}audio{height:28px;width:240px}</style>',
            '<h1>Substitute sounds: candidates</h1><p>Synthesized by tools/make_substitute_sounds.py. Each is heard as '
            'the game would play it. Pick one letter per sound, or say what should change.</p><table>']
    for name, (stands_for, n, rate, volume, loops, what) in SOUNDS.items():
        page.append(f'<tr><th colspan="3">{html.escape(name)}: {html.escape(what)} ({n / rate:.2f} s'
                    f'{", loops" if loops else ""}; stands in for {html.escape(stands_for)})</th></tr>')
        for letter, how, x in candidates(name, n, rate):
            pcm = finished(name, x, loops)
            write_sound(os.path.join(out, f'{name}_{letter}.wav'), pcm, rate)
            write_preview(os.path.join(out, 'preview', f'{name}_{letter}.wav'), pcm, rate, volume, loops)
            mark = ' (chosen)' if CHOSEN.get(name) == letter else ''
            page.append(f'<tr><td>{letter}{mark}</td><td>{html.escape(how)}</td>'
                        f'<td><audio controls preload="none" src="preview/{name}_{letter}.wav"></audio></td></tr>')
    page.append('</table>')
    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(page))
    print(f'{len(SOUNDS)} sounds, three candidates each, written to {out}')

if __name__ == '__main__':
    main(*sys.argv[1:3])
