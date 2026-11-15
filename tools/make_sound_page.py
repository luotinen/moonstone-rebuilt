"""Write SOUNDS.html: every sound of the DOS game to listen to, named as the game and its code name them.

The page is made from your own copy of the game (the installed, fixed MAIN.EXE and the SAMPLES files), so it holds
the game's own sounds and is for your own use: do not share the page. Share this tool instead. The page lists
* the sound ids (what 1000:5970 is asked for in al, and what script command 92 names), each with a plain name for
  people (SOUND_NAMES, D93: what the player hears and where, marked "inferred" where not confirmed) beside its code
  names: each id's sample from the
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
N_IDS = 173                                          # the game's 0-170 (the Amiga's programs 1-167), then Rebuilt's own

# D93: a plain name for every sound id: what the player hears and where. Each entry is (name, what the name rests on,
# sure). Sure = a game routine (research/main_syms.json) or an animation script of that creature asks for the id
# (tools/sound_table.py's sound_users), or the Amiga audio plan names it; not sure (shown as "inferred") = the name
# comes from the sample's file name or the Amiga program's sample alone, or nobody was found asking for the id.
# "Amiga only" = the DOS game never asks for the id; with the Amiga sound effects (D65) the program is there anyway.
def _names():
    n = {}
    def put(ids, name, how, sure=True):
        for k, i in enumerate(ids):
            n[i] = (name.format(k=k + 1, n=len(ids)), how, sure)
    put([0], 'No sound (id 0 is never asked for; its entry is BALAND, the Balok\'s landing, which ids 45-47 play)',
        'nothing asks for 0', False)
    put([1, 2, 3], 'Knight\'s footstep ({k} of {n} pitches)', 'sample KSTEP; the knight\'s scripts ask for 3', False)
    put([4, 5, 6, 7, 8], 'Knight grunts when struck ({k} of {n})',
        '1000:3D66 KnightStruckSound picks 4-8 (switched off in DOS, K38); also in scripts')
    put([9], 'A head is chopped off', 'sample HEADCHOP; the ratmen\'s scripts', False)
    put([10, 14], 'Knight lands on the ground (Amiga only)', 'Amiga program plays NITLAND (NITELAND2d); DOS never asks',
        False)
    put([11], 'Sword swishes through the air (knight)', 'the knight\'s scripts; sample SWISH')
    put([12, 13], 'Weapon swishes through the air ({k} of {n})', 'scripts of the mudmen, troggs, ratmen and troll; SWISH')
    put([15], 'Menu click (and the turn sound, D7)', '1000:D6E1 AddClickSound; the Amiga plays program 156')
    put([16], 'A head hits the ground; DOS also plays it when the dice are shaken',
        'sample HEDLAND; the ratmen\'s scripts; 1000:B508 ShakeDiceSnd asks for 16 (153-155 with the Amiga '
        'effects, D95)')
    put([17], 'Swords clash (a blocked blow; also the cheat sound)', '1000:4254, the block (K38); sample SWORDCL')
    put([18], 'A blow lands (hit)', 'scripts of the knight, Balok, beast, troggs; 1000:3E1F after the thrash')
    put([19], 'Knight grunts, after a short pause', 'the knight\'s scripts (Amiga: 6 with a pause)')
    put([20, 21, 22, 23], 'Dragon grunts ({k} of {n})', '1000:3DEA DragonChewSound, after a chew; parts of DRAGRU (K37)')
    put([24, 25, 26], 'Dragon chews a knight (bite {k} of {n})', '1000:3DEA DragonChewSound; parts of CHOMPS (K37)')
    put([27], 'Dragon\'s fire roars (loop)', '1000:3E07 DrFireSnd')
    put([28], 'Dragon\'s low grunt', 'Amiga sample chimpgruntloB; a script asks for 28', False)
    put([29], 'Dragon\'s breath (loop)', '1000:3E2C DrBreathSnd')
    put([30, 31, 32], 'Knight\'s muffled cry in the dragon\'s mouth ({k} of {n})',
        '1000:3DA4 DragonKnightSound / KnightCrySound')
    put([33], 'Dragon hits the ground (thud)', 'Amiga sample dragthud1c; a script asks for 33', False)
    put([34], 'Lions\' den ambience (Amiga only)', 'Amiga program: lionatmos1; the den follows a Balok\'s roar')
    put([35, 36, 37, 38, 39, 40, 41, 42], 'Balok roars ({k} of {n}, lower each time)',
        '1000:3E0D BalokRoarSound goes through 35-42')
    put([43], 'A head pops off', 'sample POPHED12; the Balok\'s scripts', False)
    put([44], 'Balok\'s paw swishes through the air', 'the Balok\'s scripts; Amiga sample BALSWISH2b')
    put([45], 'Balok lands after a long jump', '1000:375D BigLandAudio in BalokJumping; sample BALAND')
    put([46], 'Balok lands: the second thud', 'Amiga 016D52 plays 45 then 46 (D72); scripts at DS:2E54, DS:3048')
    put([47], 'Balok lands after a short jump', '1000:3764 LittleLandAudio in BalokJumping')
    put([48], 'Balok shakes a knight (thrash)', '1000:3E1F BalokThrashSound (48, then the hit 18); sample BALSHAKE')
    put([49, 50, 51], 'Balok bites (chomp {k} of {n})', 'the Balok\'s scripts; parts of CHOMPS (K37)')
    put([52], 'Blood spurts', 'the troggs\' scripts; sample BLOODSP')
    put([53], 'A spear strikes', 'the troggs\' scripts; sample SPEAR1')
    put([54], 'A blade slices', 'the troggs\' scripts; sample SLICE3')
    put([55], 'A dull bang (trogg)', 'the troggs\' scripts; Amiga sample bang2')
    put([56, 57, 58, 59, 60, 61], 'Trogg roars ({k} of {n})', '1000:3D82 TroggRoarSound goes through 56-61')
    put([62], 'Wind over open ground (never played: neither game asks for it)',
        'Amiga program on wind2, but nothing loads Wn.a (02A5F4 has no caller) or asks for 62; the DOS entry is '
        'WIPCRAK, as 63 (GUNSHOT had used it)')
    put([63], 'Whip crack (Guardian)', 'the Guardian\'s scripts; sample WIPCRAK')
    put([64], 'Guardian\'s death scream', '1000:581C GuardianDiesSnd; the Amiga picks 64, 66 or 68')
    put([65, 67, 69], 'Guardian\'s death scream: the second voice ({k} of {n})',
        'Amiga 03D24E plays 64+65, 66+67 or 68+69 (D72)')
    put([66, 68], 'Guardian\'s death scream ({k} of {n} other takes)', 'Amiga 03D24E (D72); DOS asks for 64 only')
    put([70, 71, 72, 73], 'Guardian screams ({k} of {n})', 'the Guardian\'s scripts; sample FEMSCR')
    put([74], 'Guardian\'s long yell', '1000:5816 GuardianYellSnd; Amiga sample rolandscreamB')
    put([75, 76, 77], 'Guardian\'s long yell: echo {k} of {n}', 'Amiga 03D224 plays 74-77 together (D72)')
    put([78], 'Guardian\'s sparks crackle (loop)', 'the Guardian\'s scripts; Amiga sample sparx2b')
    put([79], 'A low swish that repeats (never played: only a developer\'s test key asks for it)',
        'Amiga 011284: the key G of a fight-test key handler (01113C) that nothing enters, after the Guardian '
        'fight\'s set-up; the DOS program has no such handler')
    put([80], 'Mud bubbles (mudmen\'s loop)', '1000:57FA AddMudSound; sample MUD2')
    put([81], 'A mudman falls into the mud', 'the mudmen\'s scripts; sample MUDFAL', False)
    put([82], 'A mudman is hit', 'the mudmen\'s scripts; sample MUDHIT')
    put([83, 84, 85], 'Mudman\'s voice ({k} of {n})', '1000:57E5 AddMudVoice, table DS:7B84')
    put([86], 'A mudman stretches', 'the mudmen\'s scripts; sample STRETCH')
    put([87, 88, 89], 'Mudmen\'s scare voice ({k} of 4)', '1000:57D8 PlayScareMusic (K35 table 152, 87, 88, 89)')
    put([90], 'A crunch: the mudmen crush a knight', '1000:5822 AddCrushSnd; sample NEWKRUSH')
    put([91, 92], 'Ratman screams ({k} of {n})', '1000:3DDE RatScreamSound')
    put([93, 94], 'Ratman bites ({k} of {n})', 'the ratmen\'s scripts; Amiga sample ratbite1')
    put([95, 96], 'Ratman gouges ({k} of {n})', 'the ratmen\'s scripts; sample RATGOUG', False)
    put([97, 98, 99, 100], 'Ratman leaps ({k} of {n})', '1000:3DB5 RatLeapSound')
    put([101, 102], 'Rat on the skull squeals ({k} of {n})', '1000:3DC1 SkullRatSound (K35: 101-102)')
    put([103, 104, 105], 'Ratman impales a knight ({k} of {n})', '1000:3DCD RatImpaleSound')
    put([106, 107], 'Ratman hangs on, straining ({k} of {n})', '1000:3E13 RatHangSound; Amiga sample Strain1d')
    put([108], 'A scrape (ratmen)', 'the ratmen\'s scripts; sample SCRAPE', False)
    put([109], 'A swish (ratmen)', 'the ratmen\'s scripts; sample SWISH')
    put([110, 111, 112, 113], 'War drums of the gods\' message screen (music part {k} of {n})',
        'D74: Amiga 012F20; DOS has no sample for it')
    put([114, 120, 132, 133], 'No use found (an Amiga program between the music pieces)',
        'Amiga program not among the effects or the five pieces', False)
    put([115], 'The resident bank\'s ten samples in a row (never played; a test program by the look of it)',
        'Amiga program on instruments 103-112 (Re.a); no asker found in either game', False)
    put([157], 'Thunder at the offering at Stonehenge (with the Amiga effects, D95)',
        'Amiga script 03DD52 and 01AAA8; the DOS script calls 1000:B50A (was the empty HengeThunderSnd, B5F2); '
        'Amiga sample he.a, substitute thunder.wav')
    put([116, 117, 118, 119], 'Healer\'s music (part {k} of {n})', 'D73: Amiga 019BE6')
    put([121, 122, 123, 124], 'Mythral\'s music (part {k} of {n})', 'D73: Amiga 019E4A')
    put([125, 126, 127], 'Tavern music (part {k} of {n})', 'D73: Amiga 01A4EC')
    put([128, 129, 130, 131], 'Wizard\'s music (part {k} of {n})', 'D73: Amiga 019630')
    put([134], 'A chomp repeating and rising in pitch (never played; perhaps a planned eating loop)',
        'Amiga program on the first part of CHOMPS, as 24, about once a second, a step higher each time; nothing '
        'refers to it in either game', False)
    put([135], 'Troll\'s club lands (Amiga only)', 'Amiga sample bash; no DOS asker found', False)
    put([136, 137, 138, 139, 140, 141, 142], 'Troll grunts ({k} of {n})', '1000:5801 AddTrollSND (K35 table)')
    put([143, 144, 145], 'War beast roars ({k} of {n})', 'the beast\'s scripts ask for 143; Amiga beast roars 1-3')
    put([146], 'War beast gallops (a hoof beat)', 'a script; Amiga sample BEASTGALLOP')
    put([147], 'War beast impales a knight', 'the beast\'s scripts; Amiga sample impale1 (part of RATMPAL)')
    put([148, 149, 150, 151], 'Mudmen\'s scare voice: the second voice ({k} of {n})',
        'Amiga 03CBC8 plays 87+148, 88+149, 89+150, 151+152 (D72)')
    put([152], 'Mudmen\'s scare voice (4 of 4)', '1000:57D8 PlayScareMusic (K35); sample CHEAP1B')
    put([153, 154, 155], 'Dice rattle in the tavern ({k} of {n}; with the Amiga effects, D95)',
        'Amiga 01A8C2 picks from its table 01A8E0, on channel 3; DOS shakes the dice with 16 (1000:B508)')
    put([156], 'Menu click (the Amiga\'s; DOS asks for id 15)', 'AMIGA_PROGRAM_OF = {15: 156}; Amiga sample clik2')
    put([158, 159, 160], 'Druids\' henge music (part {k} of {n})', 'D73: Amiga 01AA3A, "The druids prepare for the ritual"')
    put([161, 162, 163, 164, 165, 166], 'A synth effect ({k} of {n}, use not found, Amiga only)',
        'Amiga 01CE8A plays 161+162, 01CEB0 163-166; DOS side not found', False)
    put([167], 'Silence (frees an Amiga channel)', 'the Amiga driver\'s release plays the silent program 167')
    put([168, 169, 170], 'No sound (past the Amiga\'s 167 programs)', 'nothing asks for it')
    put([171], 'The mines of MINEFIELD (Moonstone Rebuilt)', 'MINE_SOUND in make_savehook.py; sample BONFIRE2')
    put([172], 'GUNSHOT\'s bang (Moonstone Rebuilt)', 'D65; sample WIPCRAK')
    if sorted(n) != list(range(N_IDS)):
        raise ValueError('every sound id needs a name')
    return n
SOUND_NAMES = _names()

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
        plain, how, sure = SOUND_NAMES[sid]
        ids.append({'id': sid, 'sample': name, 'rate': rate, 'part': slices.get(sid), 'fm': ds[P.FM_TABLE + sid],
                    'amiga': P.amiga_program(sid) if fixed else 0, 'default': ds[P.SB_TABLE + sid] == P.UNUSED_SAMPLE,
                    'name': plain, 'how': how, 'sure': sure})
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
td.how { font-size: 13px; color: var(--muted); min-width: 260px; }
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
<div class="bar"><input type="search" id="q" placeholder="Filter: a word (troll, scream), an id, a sample name, a program number&hellip;" aria-label="Filter">
<label><input type="checkbox" id="hide"> hide the ids with HIT3 (the table's default: most are never asked for)</label></div>
<h2 id="ids">Sound ids</h2>
<p>Each id has two names. <b>Sound</b> says in plain words what the player hears and where; <b>Id</b>,
<b>Sample</b> and <b>Amiga</b> are its code names, for programming. Each button plays what the game plays for the
id: its sample at the id's rate, only its part where it has one. FM is the AdLib effect the id plays without a
Sound Blaster; Amiga is the Amiga program it is (with the Amiga sound effects on, that program plays instead).
<b>Found from</b> says what the plain name rests on: a game routine (<code>1000:xxxx</code> and its name), a
creature's animation scripts, or the Amiga program. Names marked <span class="tag">inferred</span> come from a file
name alone or have nobody found asking for them. &ldquo;Amiga only&rdquo;: the DOS game never asks for the id.</p>
<div class="wrap"><table id="tid"><thead><tr><th></th><th>Sound</th><th>Id</th><th>Sample</th><th>Amiga</th>
<th>Rate (Hz)</th><th>Part (samples)</th><th>Length (s)</th><th>FM</th><th>Found from</th></tr></thead><tbody></tbody></table></div>
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
  tr.id = 'id' + s.id;
  tr.dataset.text = [s.id, s.sample, s.amiga || '', s.name, s.how, s.sure ? '' : 'inferred'].join(' ').toLowerCase();
  tr.dataset.default = s.default ? '1' : '';
  if (s.default) tr.classList.add('dim');
  const n = s.part ? s.part[1] : sm.len;
  const sample = link(s.sample, '#s-' + s.sample);
  const name = document.createElement('span');
  name.textContent = s.name;
  if (!s.sure) name.append(' ', Object.assign(document.createElement('span'), {className: 'tag', textContent: 'inferred'}));
  const how = s.how + (s.default ? '. Plays HIT3, the table’s default' : '');
  cells(tr, [b, name, s.id, sample, s.amiga || '', s.rate, s.part ? s.part[0] + '–' + (s.part[0] + s.part[1] - 1) : '',
             sec(n, s.rate), s.fm, how]);
  tr.children[1].className = 'wide'; tr.lastChild.className = 'wide how';
  b.onclick = () => play(tr, s.sample, sm.wav, sm.rate, s.rate, s.part);
  tid.appendChild(tr);
}
const tsm = document.querySelector('#tsm tbody');
for (const [name, sm] of Object.entries(DATA.samples).sort((a, b) => a[1].n - b[1].n)) {
  const tr = document.createElement('tr'), b = button(name), ids = document.createElement('span');
  tr.id = 's-' + name; tr.dataset.text = (name + ' ' + sm.ids.join(' ')).toLowerCase(); ids.className = 'ids';
  for (const i of sm.ids) ids.appendChild(Object.assign(link(String(i), '#id' + i), {title: DATA.ids[i].name}));
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
