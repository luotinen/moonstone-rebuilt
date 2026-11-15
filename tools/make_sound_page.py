"""Write SOUNDS.html: every sound of the DOS game to listen to, named as the game and its code name them.

The page is made from your own copy of the game (the installed, fixed MAIN.EXE and the SAMPLES files), so it holds
the game's own sounds and is for your own use: do not share the page. Share this tool instead. The page lists
* the sound ids (what 1000:5970 is asked for in al, and what script command 92 names): each id's sample from the
  table DS:7E6E (sample k = the k-th name in DS:8721), its own rate (K36, the table after DS:7E6E + 180), the part of
  the sample it plays (K37, DS:7D02 + 192), its FM effect (DS:7D02) and the Amiga program it is (D65);
* the samples, by their file names in SAMPLES, at the rate their file gives (K10);
* Moonstone Rebuilt's substitute sounds (sounds/, CC0 or as SOURCES.md says), which stand in for the Amiga samples the
  DOS game lacks.
Each play button plays exactly what the game plays for that id: the sample at the id's rate, the id's part only.

Usage: python -I tools/make_sound_page.py [install folder] [output file]
       (defaults: the folder above tools, <folder>/SOUNDS.html)"""
import sys, os, struct, base64, html, json, io, wave, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patches as P

NAME_TABLE, N_SAMPLES = 0x8721, 49
OWN_IDS = {171: 'Moonstone Rebuilt: the mines of MINEFIELD', 172: 'Moonstone Rebuilt: GUNSHOT\'s bang'}
N_IDS = 173                                          # the game's 0-170 (the Amiga's programs 1-167), then Rebuilt's own

def main_exe(folder):
    """The installed fixed MAIN.EXE (unpacked) and whether it is the fixed one; else the original, unpacked."""
    fixed = os.path.join(folder, '_fixes', 'fixed', 'MAIN.EXE')
    if os.path.exists(fixed):
        return open(fixed, 'rb').read(), True
    from make_main_exe import make_main_exe
    return make_main_exe(folder), False

def data_segment(exe):
    header = struct.unpack('<H', exe[8:10])[0] * 16
    start = header + P.image_offset(('DS', 0))
    return exe[start:start + 0x10000]

def voc(data):
    """A Creative VOC file -> (8-bit unsigned PCM, rate)."""
    i, pcm, rate = struct.unpack('<H', data[20:22])[0], bytearray(), 11025
    while i < len(data) and data[i] != 0:
        kind, n = data[i], data[i + 1] | data[i + 2] << 8 | data[i + 3] << 16
        block = data[i + 4:i + 4 + n]
        if kind == 1:
            rate = 1000000 // (256 - block[0]); pcm += block[2:]
        elif kind == 2:
            pcm += block
        i += 4 + n
    return bytes(pcm), rate

def wav(pcm, rate):
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(1); w.setframerate(rate); w.writeframes(pcm)
    return out.getvalue()

def tc_rate(tc):
    return round(1000000 / (256 - tc))

def read_game(folder):
    exe, fixed = main_exe(folder)
    ds = data_segment(exe)
    cstr = lambda o: ds[o:ds.index(b'\0', o)].decode('ascii')
    names = [cstr(struct.unpack('<H', ds[NAME_TABLE + 2 * k:NAME_TABLE + 2 * k + 2])[0]).upper() for k in range(N_SAMPLES)]
    slices, i = {}, P.SOUND_SLICES
    while fixed and ds[i]:
        sid, start, length = struct.unpack('<BHH', ds[i:i + 5]); slices[sid] = (start, length); i += 5
    sample_dir = os.path.join(folder, '_fixes', 'fixed', 'SAMPLES')
    if not os.path.isdir(sample_dir):
        sample_dir = os.path.join(folder, 'SAMPLES')
    samples = {}
    for k, name in enumerate(names):
        if name not in samples:
            pcm, rate = voc(open(os.path.join(sample_dir, name), 'rb').read())
            samples[name] = {'n': k, 'rate': rate, 'len': len(pcm), 'wav': wav(pcm, rate), 'ids': []}
    ids = []
    for sid in range(N_IDS):
        name = names[ds[P.SB_TABLE + sid]]
        tc = ds[P.SOUND_RATES + sid] if fixed and sid < 180 else 0
        rate = tc_rate(tc) if tc else samples[name]['rate']
        ids.append({'id': sid, 'sample': name, 'rate': rate, 'part': slices.get(sid), 'fm': ds[P.FM_TABLE + sid],
                    'amiga': P.amiga_program(sid) if fixed else 0, 'default': ds[P.SB_TABLE + sid] == P.UNUSED_SAMPLE,
                    'note': OWN_IDS.get(sid, '')})
        samples[name]['ids'].append(sid)
    return fixed, ids, samples

def substitutes(folder):
    """sounds/*.wav with what each stands in for (SOURCES.md's tables)."""
    d = os.path.join(folder, 'sounds')
    if not os.path.isdir(d):
        return []
    rows = {}
    src = os.path.join(d, 'SOURCES.md')
    for line in open(src, encoding='utf-8').read().splitlines() if os.path.exists(src) else ():
        m = re.match(r'\|\s*`([^`]+\.wav)`\s*\|\s*`?([^|`]+)`?\s*\|\s*([^|]*)\|', line)
        if m:
            rows[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    out = []
    for f in sorted(os.listdir(d)):
        if f.lower().endswith('.wav'):
            data = open(os.path.join(d, f), 'rb').read()
            with wave.open(io.BytesIO(data)) as w:
                rate, n = w.getframerate(), w.getnframes()
            stands, what = rows.get(f, ('', ''))
            out.append({'file': f, 'for': stands, 'what': what, 'rate': rate, 'len': n, 'wav': data})
    return out

PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moonstone Sounds</title>
<style>
:root { --bg: #f6f4ef; --panel: #ffffff; --text: #22201c; --muted: #6b665c; --line: #e2ddd2; --accent: #7a4fb5;
        --accent-text: #ffffff; --soft: #efe9f7; --warn: #9a5b00; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #16151a; --panel: #1f1e24; --text: #ecebf0;
        --muted: #a29fae; --line: #34323c; --accent: #b993ee; --accent-text: #16151a; --soft: #2a2535; --warn: #e0a64a; } }
:root[data-theme="dark"] { --bg: #16151a; --panel: #1f1e24; --text: #ecebf0; --muted: #a29fae; --line: #34323c;
        --accent: #b993ee; --accent-text: #16151a; --soft: #2a2535; --warn: #e0a64a; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; } h2 { font-size: 19px; margin: 32px 0 8px; }
p { margin: 6px 0; color: var(--muted); max-width: 75ch; }
.bar { position: sticky; top: 0; z-index: 2; background: var(--bg); padding: 10px 0; display: flex; gap: 10px; flex-wrap: wrap;
       align-items: center; border-bottom: 1px solid var(--line); }
input[type=search] { flex: 1 1 220px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px;
       background: var(--panel); color: var(--text); font: inherit; }
label { color: var(--muted); font-size: 14px; display: flex; gap: 6px; align-items: center; }
.wrap { overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: 13px; color: var(--muted); font-weight: 600; background: var(--panel); }
tr:last-child td { border-bottom: 0; }
td.wide { white-space: normal; min-width: 180px; }
tr.playing td { background: var(--soft); }
tr.dim td { color: var(--muted); }
button.play { width: 34px; height: 28px; border: 0; border-radius: 6px; background: var(--accent); color: var(--accent-text);
       cursor: pointer; font-size: 13px; }
button.play:focus-visible { outline: 2px solid var(--text); outline-offset: 2px; }
code, .name { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: 13.5px; }
a { color: var(--accent); }
.tag { font-size: 12px; color: var(--warn); }
.ids a { margin-right: 6px; }
</style></head><body><main>
<h1>Moonstone sounds</h1>
<p>Every sound effect of the DOS game, made by <code>tools/make_sound_page.py</code> from __SOURCE__. Names are the
game's: a <b>sound id</b> is the number the code asks <code>1000:5970</code> for (<code>mov al, id</code>, or script
command 92); a <b>sample</b> is a file in <code>SAMPLES</code>. This page holds the game's own sounds: keep it for
your own use.</p>
<div class="bar"><input type="search" id="q" placeholder="Filter: an id, a sample name, a program number&hellip;" aria-label="Filter">
<label><input type="checkbox" id="hide"> hide the ids with HIT3 (the table's default: most are never asked for)</label></div>
<h2 id="ids">Sound ids</h2>
<p>Each button plays what the game plays for the id: its sample at the id's rate, only its part where it has one.
FM is the AdLib effect the id plays without a Sound Blaster; Amiga is the Amiga program it is (with the Amiga
sound effects on, that program plays instead).</p>
<div class="wrap"><table id="tid"><thead><tr><th></th><th>Id</th><th>Sample</th><th>Rate (Hz)</th><th>Part (samples)</th>
<th>Length (s)</th><th>FM</th><th>Amiga</th><th>Note</th></tr></thead><tbody></tbody></table></div>
<h2 id="samples">Samples</h2>
<p>The files at the rate their VOC header gives (K10: the Amiga's rate of the sample).</p>
<div class="wrap"><table id="tsm"><thead><tr><th></th><th>#</th><th>File</th><th>Rate (Hz)</th><th>Length (s)</th>
<th>Played by the ids</th></tr></thead><tbody></tbody></table></div>
<h2 id="subs">Substitute sounds</h2>
<p>Moonstone Rebuilt's own files in <code>sounds/</code> (see <code>sounds/SOURCES.md</code>), for Amiga samples the DOS
game lacks; the Amiga sound effects without the Amiga disks play them.</p>
<div class="wrap"><table id="tsu"><thead><tr><th></th><th>File</th><th>Stands in for</th><th>Rate (Hz)</th>
<th>Length (s)</th><th class="wide">What it is</th></tr></thead><tbody></tbody></table></div>
</main>
<script>
const DATA = __DATA__;
let ctx = null, current = null, currentRow = null;
const buffers = {};
function audio() { if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)(); return ctx; }
async function buffer(key, b64) {
  if (!buffers[key]) {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    buffers[key] = await audio().decodeAudioData(bytes.buffer);
  }
  return buffers[key];
}
function stop() {
  if (current) { try { current.stop(); } catch (e) {} current = null; }
  if (currentRow) { currentRow.classList.remove('playing'); currentRow = null; }
}
async function play(row, key, b64, fileRate, rate, part) {
  const same = currentRow === row; stop(); if (same) return;
  const buf = await buffer(key, b64), src = audio().createBufferSource();
  src.buffer = buf; src.playbackRate.value = rate / fileRate; src.connect(audio().destination);
  const start = part ? part[0] / fileRate : 0, dur = part ? part[1] / fileRate : buf.duration;
  src.onended = () => { if (current === src) stop(); };
  src.start(0, start, dur); current = src; currentRow = row; row.classList.add('playing');
}
const sec = (n, r) => (n / r).toFixed(2);
function button(label) { const b = document.createElement('button'); b.className = 'play'; b.textContent = '▶';
  b.setAttribute('aria-label', 'Play ' + label); return b; }
function cells(tr, values) { for (const v of values) { const td = document.createElement('td');
  if (v instanceof Node) td.appendChild(v); else td.textContent = v; tr.appendChild(td); } }
function link(text, href) { const a = document.createElement('a'); a.href = href; a.textContent = text; a.className = 'name'; return a; }
const tid = document.querySelector('#tid tbody');
for (const s of DATA.ids) {
  const sm = DATA.samples[s.sample], tr = document.createElement('tr'), b = button('id ' + s.id);
  tr.id = 'id' + s.id; tr.dataset.text = [s.id, s.sample, s.amiga || '', s.note].join(' ').toLowerCase();
  tr.dataset.default = s.default ? '1' : '';
  if (s.default) tr.classList.add('dim');
  const n = s.part ? s.part[1] : sm.len;
  const sample = link(s.sample, '#s-' + s.sample);
  const note = s.note || (s.default ? 'HIT3, the table’s default (most of these ids are never asked for)' : '');
  cells(tr, [b, s.id, sample, s.rate, s.part ? s.part[0] + '–' + (s.part[0] + s.part[1] - 1) : '', sec(n, s.rate),
             s.fm, s.amiga || '', note]);
  b.onclick = () => play(tr, s.sample, sm.wav, sm.rate, s.rate, s.part);
  tid.appendChild(tr);
}
const tsm = document.querySelector('#tsm tbody');
for (const [name, sm] of Object.entries(DATA.samples).sort((a, b) => a[1].n - b[1].n)) {
  const tr = document.createElement('tr'), b = button(name), ids = document.createElement('span');
  tr.id = 's-' + name; tr.dataset.text = (name + ' ' + sm.ids.join(' ')).toLowerCase(); ids.className = 'ids';
  for (const i of sm.ids) ids.appendChild(link(String(i), '#id' + i));
  cells(tr, [b, sm.n, Object.assign(document.createElement('span'), {className: 'name', textContent: name}), sm.rate,
             sec(sm.len, sm.rate), ids]);
  b.onclick = () => play(tr, name, sm.wav, sm.rate, sm.rate, null);
  tsm.appendChild(tr);
}
const tsu = document.querySelector('#tsu tbody');
for (const s of DATA.subs) {
  const tr = document.createElement('tr'), b = button(s.file);
  tr.dataset.text = (s.file + ' ' + s.for + ' ' + s.what).toLowerCase();
  cells(tr, [b, Object.assign(document.createElement('span'), {className: 'name', textContent: s.file}), s.for, s.rate,
             sec(s.len, s.rate), s.what]);
  tr.lastChild.className = 'wide';
  b.onclick = () => play(tr, 'sub:' + s.file, s.wav, s.rate, s.rate, null);
  tsu.appendChild(tr);
}
if (!DATA.subs.length) document.querySelector('#tsu').closest('.wrap').outerHTML = '<p>No sounds/ folder found.</p>';
function filter() {
  const q = document.getElementById('q').value.trim().toLowerCase(), hide = document.getElementById('hide').checked;
  for (const tr of document.querySelectorAll('tbody tr')) {
    const show = (!q || tr.dataset.text.split(' ').some(w => w === q) || tr.dataset.text.includes(q)) && !(hide && tr.dataset.default);
    tr.style.display = show ? '' : 'none';
  }
}
document.getElementById('q').addEventListener('input', filter);
document.getElementById('hide').addEventListener('change', filter);
document.addEventListener('keydown', e => { if (e.key === 'Escape') stop(); });
</script></body></html>
'''

def page(folder):
    fixed, ids, samples = read_game(folder)
    data = {'ids': ids,
            'samples': {k: {'n': v['n'], 'rate': v['rate'], 'len': v['len'], 'ids': v['ids'],
                            'wav': base64.b64encode(v['wav']).decode()} for k, v in samples.items()},
            'subs': [{'file': s['file'], 'for': s['for'], 'what': s['what'], 'rate': s['rate'], 'len': s['len'],
                      'wav': base64.b64encode(s['wav']).decode()} for s in substitutes(folder)]}
    source = ('the installed, fixed game (<code>_fixes/fixed</code>: the ids with their K35 samples, K36 rates and K37 '
              'parts)' if fixed else 'the original game (no fixes: the ids as the original table has them)')
    text = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    return PAGE.replace('__SOURCE__', source).replace('__DATA__', text), len(ids), len(samples), len(data['subs'])

def main(folder=None, out=None):
    folder = folder or os.path.dirname(HERE)
    out = out or os.path.join(folder, 'SOUNDS.html')
    text, n_ids, n_samples, n_subs = page(folder)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print(f'{out}: {n_ids} sound ids, {n_samples} samples, {n_subs} substitute sounds')

if __name__ == '__main__':
    main(*sys.argv[1:])
