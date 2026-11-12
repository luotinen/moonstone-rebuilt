"""Write tools/sound_programs.json: the Amiga game's effect programs as what the sound driver plays frame by frame,
so that the effects can be built from the DOS game's samples for users without the Amiga disks (D66).

Needs the three Amiga disk images and a DOS installation (for its SAMPLES folder); run it when the list of effect
programs or the substitutes change. The table holds, for each effect program, steps of [frames (1/50 s), volume
(0-63), sample rate in Hz, start]: start is the number of the instrument a note begins with, -1 where the sound is
cut, null otherwise. And for each instrument where its samples come from: a part of a DOS sample that holds the same
data ("dos", "at", "n"), a part of a substitute sound in sounds/ ("file"), or nothing (silent: the instruments of
the location music, which has no substitute). "stand_in" marks a DOS sample that is another take of the sound, not
the same data. The table has no samples, no period table and no program code of the Amiga game.

Usage: python -I tools/export_sound_programs.py <folder with the three .adf files> <DOS installation folder>"""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import make_amiga_audio as audio

HERE = os.path.dirname(os.path.abspath(__file__))
# Substitute sounds (sounds/, see sounds/SOURCES.md): the Amiga sample's name in its bank -> our file. A substitute has
# as many samples as the sample it stands in for, so the instruments that are parts of the sample are the same parts
# of the substitute.
SUBSTITUTES = {'dragthud1c': 'dragon_thud.wav', 'BALSWISH2b': 'balok_swish.wav', 'bang2': 'trogg_bang.wav',
               'wind2': 'wind.wav', 'sparx2b': 'guardian_sparks.wav', 'bash': 'troll_bash.wav',
               'BEASTGALLOP.SND': 'beast_gallop.wav', 'dice2c': 'dice.wav', 'clik2': 'menu_click.wav',
               'chimpgruntloB': 'dragon_grunt.wav', 'lionatmos1': 'lion_den.wav', 'rolandscreamB': 'long_scream.wav',
               'ratbite1': 'rat_bite.wav', 'Strain1d': 'strain.wav'}
# Another take of the same sound that the DOS game has: the Amiga sample's name -> the DOS sample (played whole)
STAND_INS = {'BEAST2.SND': 'BEAST1', 'BEAST3.SND': 'BEAST1', 'dragmufl1B': 'DAGMUF3', 'dragmufl3B': 'DAGMUF3',
             'femsrm5b': 'FEMSCR', 'femsrm6b': 'FEMSCR', 'femscrm2': 'FEMSCR', 'grnt1b': 'GRNT1', 'cheap3': 'CHEAP2B'}
# Used when a substitute file is not there yet: a DOS sample of the same kind
FALLBACKS = {'dragon_grunt.wav': 'DRAGRU', 'lion_den.wav': 'LION2C1', 'long_scream.wav': 'FEMSCR',
             'rat_bite.wav': 'RATSCR', 'strain.wav': 'GRNT3'}

def main(adf_folder, install):
    drv = audio.Driver(audio.read_disks(adf_folder))
    if not drv.verified: raise SystemExit('mog is not the known file: the table must be made from the known disks')
    samples = os.path.join(install, 'SAMPLES')
    dos = {os.path.basename(p).upper(): audio.read_voc(p) for p in sorted(glob.glob(os.path.join(samples, '*')))}
    dos_bytes = {n: (x * 128).astype(np.int8).tobytes() for n, x in dos.items()}
    sounds = os.path.join(HERE, '..', 'sounds')
    programs, used = {}, set()
    for p in audio.FONT_PROGRAMS:
        steps, loops = audio.record(drv, p)
        programs[p] = dict(loops=loops, steps=[[n, vol, rate, start] for n, vol, rate, start in steps])
        used |= {s[3] for s in steps if s[3] is not None and s[3] >= 0}
    instruments, counts = {}, dict(same=0, substitute=0, stand_in=0, fallback=0, silent=0)
    for k in sorted(used):
        x = drv.ins[k]
        raw = (x['pcm'] * 128).astype(np.int8).tobytes()
        name, _, offset = drv.name[k].partition(' +')
        offset = int(offset or 0)
        loop = dict(loop=x['loop']) if x['looped'] else {}
        hit = next(((n, d.find(raw)) for n, d in sorted(dos_bytes.items()) if len(raw) >= 64 and d.find(raw) >= 0), None)
        if hit:
            instruments[k] = dict(dos=hit[0], at=hit[1], n=len(raw), **loop); counts['same'] += 1
        elif name in SUBSTITUTES and os.path.exists(os.path.join(sounds, SUBSTITUTES[name])):
            have = len(audio.read_wav8(os.path.join(sounds, SUBSTITUTES[name])))
            if offset + len(raw) > have: raise SystemExit(f'{SUBSTITUTES[name]} is too short for instrument {k}')
            instruments[k] = dict(file=SUBSTITUTES[name], at=offset, n=len(raw), **loop); counts['substitute'] += 1
        elif name in SUBSTITUTES:
            d = FALLBACKS[SUBSTITUTES[name]]
            instruments[k] = dict(dos=d, at=0, n=len(dos[d]), stand_in=True); counts['fallback'] += 1
            print(f'  no {SUBSTITUTES[name]} yet: instrument {k} ({name}) plays {d}')
        elif name in STAND_INS:
            d = STAND_INS[name]
            instruments[k] = dict(dos=d, at=0, n=len(dos[d]), stand_in=True, **loop); counts['stand_in'] += 1
        else:
            instruments[k] = {}; counts['silent'] += 1
    lines = ['{', '"about": "Moonstone Rebuilt: the effect programs frame by frame, see tools/export_sound_programs.py",',
             '"frame_hz": %d,' % audio.FRAME_HZ, '"instruments": {']
    lines += ['  "%d": %s%s' % (k, json.dumps(x), ',' if k != max(instruments) else '') for k, x in sorted(instruments.items())]
    lines += ['},', '"programs": {']
    last = max(programs)
    lines += ['  "%d": %s%s' % (p, json.dumps(x, separators=(',', ':')), ',' if p != last else '') for p, x in sorted(programs.items())]
    lines += ['}', '}']
    out = os.path.join(HERE, 'sound_programs.json')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    json.load(open(out, encoding='utf-8'))
    print(f'{out}: {len(programs)} programs, {len(instruments)} instruments {counts}, {os.path.getsize(out)} bytes')

if __name__ == '__main__':
    main(*sys.argv[1:3])
