"""Make the substitute sounds that come from open-licence recordings (sounds/SOURCES.md): the five sounds of the Amiga
version that the DOS version lacks and that synthesis does badly (a grunt, a den of lions, a scream, a rat, a strain).

Each is a piece of a recording under CC0 or CC BY, cut, slowed or sped up, filtered and reduced to what the game
plays: mono, 8 bits, as many samples as the sample it stands in for, at the rate the game plays that sample. Nothing
is taken from, or modelled on, the Amiga samples; only their length and rate are used.

The source recordings are not in the repo: sounds/sources/manifest.json lists where each came from (and
sounds/SOURCES.md says so for the chosen ones). VLC decodes them to WAV once (sounds/sources/_wav).

Usage: python -I tools/make_recorded_sounds.py <sounds folder> analyse       where the loud parts of each source are
       python -I tools/make_recorded_sounds.py <sounds folder> candidates    <sounds folder>/candidates/NAME_x.wav,
                                                                             previews and recordings.html
       python -I tools/make_recorded_sounds.py <sounds folder> chosen        <sounds folder>/NAME.wav"""
import sys, os, json, wave, html, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from make_substitute_sounds import write_sound, write_preview, to_8bit

VLC_PATHS = (r'C:\Program Files\VideoLAN\VLC\vlc.exe', r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe')
# name: (stands in for, samples, rate the game plays it at (Hz), volume of that program (0-63), steady, what it is)
# steady: an even texture that the game cuts into parts (no fades; the evenest loud part of the source is taken)
SOUNDS = {
    'dragon_grunt': ('chimpgruntloB', 8332, 6581, 63, False, 'the dragon\'s low grunt'),
    'lion_den': ('lionatmos1', 8273, 7830, 20, True, 'the low rumble of lions in their den (the game plays eight parts of it in turn)'),
    'long_scream': ('rolandscreamB', 13924, 12445, 60, False, 'the Guardian\'s long scream'),
    'rat_bite': ('ratbite1', 8396, 13982, 60, False, 'a ratman bites: a sharp squeal'),
    'strain': ('Strain1d', 5132, 12855, 60, False, 'a short grunt of effort'),
}
# name: [(letter, source file under sounds/sources, start in seconds or None for the loudest part, speed, how)]
# speed: how fast the source is played (0.5 = half speed, an octave down)
PICKS = {
    'dragon_grunt': [('a', 'dragon_grunt/233170_4056007-hq.ogg', None, 0.6, 'the grunt of a pig at 0.6 speed'),
                     ('b', 'dragon_grunt/842313_15895934-hq.ogg', None, 0.7, 'the growling grunt of a pig at 0.7 speed'),
                     ('c', 'dragon_grunt/Alligatorbellow1.ogg', None, 1.0, 'the bellow of an alligator')],
    'lion_den': [('a', 'lion_den/223978_639300-hq.ogg', None, 1.0, 'a lion moaning low'),
                 ('b', 'lion_den/439280_954919-hq.ogg', None, 0.8, 'a tiger growling, at 0.8 speed'),
                 ('c', 'lion_den/503755_6911631-hq.ogg', None, 0.5, 'the purr of a tom cat at half speed')],
    'long_scream': [('a', 'long_scream/682177_10938187-hq.ogg', None, 1.0, 'an airy scream of pain, whole'),
                    ('b', 'long_scream/243382_3229685-hq.ogg', None, 1.0, 'the start of a longer dry scream'),
                    ('c', 'long_scream/542128_318949-hq.ogg', None, 1.0, 'the loudest part of a rising scream')],
    'rat_bite': [('a', 'rat_bite/143125_2580450-hq.ogg', None, 1.0, 'the squeaks of a pet rat'),
                 ('b', 'rat_bite/217767_950925-hq.ogg', None, 1.0, 'a rat protesting'),
                 ('c', 'rat_bite/815837_15895934-hq.ogg', None, 1.0, 'the squeal of a guinea pig')],
    'strain': [('a', 'strain/841313_18316981-hq.ogg', None, 1.0, 'a grunt of exertion'),
               ('b', 'strain/803168_17274093-hq.ogg', (4.0, 7.0), 1.0, 'a soft short effort'),
               ('c', 'strain/464677_7358035-hq.ogg', None, 1.0, 'one deep grunt')],
}
# The candidate chosen by ear for each sound (the user, 12 Nov 2026)
CHOSEN = {'dragon_grunt': 'c', 'lion_den': 'a', 'long_scream': 'b', 'rat_bite': 'b', 'strain': 'a'}

def decode(vlc, src, dst):
    """Any audio file -> 16-bit WAV, 44.1 kHz mono, with VLC."""
    sout = '#transcode{acodec=s16l,channels=1,samplerate=44100}:std{access=file,mux=wav,dst=' + dst.replace('\\', '/') + '}'
    subprocess.run([vlc, '-I', 'dummy', '--dummy-quiet', '--no-repeat', '--no-loop', src, '--sout', sout, 'vlc://quit'],
                   check=True, timeout=300)

def load(sounds, rel):
    """A source recording as mono samples in -1..1 and its rate."""
    src = os.path.join(sounds, 'sources', rel)
    dst = os.path.join(sounds, 'sources', '_wav', rel.replace('/', '_').replace('\\', '_') + '.wav')
    if not os.path.exists(dst) or os.path.getsize(dst) < 1000:
        vlc = next((p for p in VLC_PATHS if os.path.exists(p)), None)
        if not vlc: raise SystemExit('VLC is needed to decode the source recordings')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        decode(vlc, os.path.abspath(src), os.path.abspath(dst))
    with wave.open(dst, 'rb') as w:
        ch, rate, width = w.getnchannels(), w.getframerate(), w.getsampwidth()
        d = w.readframes(w.getnframes())
    if width != 2: raise SystemExit(f'{dst}: not 16-bit')
    x = np.frombuffer(d[:len(d) // (2 * ch) * 2 * ch], dtype='<i2').reshape(-1, ch).astype(np.float64).mean(axis=1) / 32768.0
    return x - x.mean(), rate

def envelope(x, rate, ms=10):
    k = max(1, int(rate * ms / 1000))
    n = len(x) // k
    return np.sqrt((x[:n * k].reshape(n, k) ** 2).mean(axis=1)), k

def loudest(x, rate, seconds, steady=False):
    """Start (in samples) of the part of that length to take: the one with the most energy, begun a little before
    its sound starts; for a steady texture the evenest of the loud parts."""
    e, k = envelope(x, rate)
    w = max(1, int(seconds * rate / k))
    if len(e) <= w: return 0
    power = np.convolve(e ** 2, np.ones(w), 'valid')
    if steady:
        loud = np.flatnonzero(power >= 0.5 * power.max())
        spread = [e[i:i + w].std() / (e[i:i + w].mean() + 1e-9) for i in loud]
        return int(loud[int(np.argmin(spread))]) * k
    i = int(np.argmax(power))
    loud = np.flatnonzero(e[i:i + w] > 0.2 * e[i:i + w].max())        # begin just before the sound does
    return max(0, i + int(loud[0]) - 1) * k

def resample(x, n):
    """x as n samples (the band above the new rate is cut; x is treated as one period, so fade it first)."""
    spectrum = np.fft.rfft(x)
    m = n // 2 + 1
    out = np.zeros(m, dtype=complex)
    out[:min(m, len(spectrum))] = spectrum[:min(m, len(spectrum))]
    return np.fft.irfft(out, n) * n / len(x)

def make(sounds, name, rel, start, speed):
    stands_for, n, rate, volume, steady, what = SOUNDS[name]
    x, src_rate = load(sounds, rel)
    seconds = n / rate * speed                                       # of the source
    if start is None: start = loudest(x, src_rate, seconds, steady) / src_rate
    elif isinstance(start, tuple):                                   # the loudest part between two times
        lo = int(start[0] * src_rate)
        start = (lo + loudest(x[lo:int(start[1] * src_rate)], src_rate, seconds, steady)) / src_rate
    piece = x[int(start * src_rate):int((start + seconds) * src_rate)].copy()
    if len(piece) < 0.9 * seconds * src_rate: raise SystemExit(f'{rel}: too short for {name} at speed {speed}')
    edge = int(0.004 * src_rate)
    piece[:edge] *= np.linspace(0, 1, edge)
    tail = edge if steady else int(0.04 * src_rate)
    piece[-tail:] *= np.linspace(1, 0, tail)
    y = resample(piece, n)
    y -= y.mean()
    return to_8bit(y), start

def main(sounds, which='candidates'):
    manifest = {m['file'].replace('\\', '/'): m for m in json.load(open(os.path.join(sounds, 'sources', 'manifest.json'), encoding='utf-8'))}
    if which == 'analyse':
        for rel, m in manifest.items():
            x, rate = load(sounds, rel)
            e, k = envelope(x, rate, 50)
            name = m['sound']
            seconds = SOUNDS[name][1] / SOUNDS[name][2]
            at = loudest(x, rate, seconds, SOUNDS[name][4]) / rate
            marks = ''.join(' .:-=+*#%@'[min(9, int(10 * v / (e.max() + 1e-9)))] for v in e[:160])
            print(f'{name:13s} {rel[:46]:46s} {len(x) / rate:6.1f} s  peak {np.abs(x).max():.2f}  loudest {seconds:.2f} s at {at:6.2f} s\n    |{marks}|')
        return
    out = os.path.join(sounds, 'candidates')
    if which == 'chosen':
        for name, letter in CHOSEN.items():
            _, rel, start, speed, how = next(p for p in PICKS[name] if p[0] == letter)
            pcm, _ = make(sounds, name, rel, start, speed)
            write_sound(os.path.join(sounds, f'{name}.wav'), pcm, SOUNDS[name][2])
        print(f'{len(CHOSEN)} chosen recordings written to {sounds}')
        return
    os.makedirs(os.path.join(out, 'preview'), exist_ok=True)
    page = ['<!doctype html><meta charset="utf-8"><title>Substitute sounds from recordings: candidates</title>',
            '<style>body{font:14px sans-serif;margin:16px;max-width:1100px}td,th{padding:4px 8px;text-align:left;'
            'border-bottom:1px solid #8884}audio{height:28px;width:240px}</style>',
            '<h1>Substitute sounds from recordings: candidates</h1><p>Made by tools/make_recorded_sounds.py from '
            'open-licence recordings. Each is heard as the game would play it. Pick one letter per sound, or say what '
            'should change.</p><table>']
    for name, picks in PICKS.items():
        stands_for, n, rate, volume, steady, what = SOUNDS[name]
        page.append(f'<tr><th colspan="4">{html.escape(name)}: {html.escape(what)} ({n / rate:.2f} s; stands in for '
                    f'{html.escape(stands_for)})</th></tr>')
        for letter, rel, start, speed, how in picks:
            pcm, start = make(sounds, name, rel, start, speed)
            write_sound(os.path.join(out, f'{name}_{letter}.wav'), pcm, rate)
            write_preview(os.path.join(out, 'preview', f'{name}_{letter}.wav'), pcm, rate, volume, steady)
            m = manifest[rel]
            mark = ' (chosen)' if CHOSEN.get(name) == letter else ''
            page.append(f'<tr><td>{letter}{mark}</td><td>{html.escape(how)}</td>'
                        f'<td>{html.escape(m["title"])}, {html.escape(m["author"])}, {html.escape(m["licence"])}</td>'
                        f'<td><audio controls preload="none" src="preview/{name}_{letter}.wav"></audio></td></tr>')
    page.append('</table>')
    with open(os.path.join(out, 'recordings.html'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(page))
    print(f'{sum(len(p) for p in PICKS.values())} candidates for {len(PICKS)} sounds written to {out}')

if __name__ == '__main__':
    main(*sys.argv[1:3])
