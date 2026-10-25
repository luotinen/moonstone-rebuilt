"""Set up the Amiga intro and ending music for Moonstone Rebuilt (D8), from the user's own Amiga disk images.

1. Finds the disk with music.cmp and vmusic.cmp among the .adf files in a folder (tools/adf.py) and unpacks the two
   StarTrekker modules (tools/rnc.py).
2. Renders them to WAV with VLC (only needed here; the game plays the WAV files with Windows' own sound player).
3. Makes muted copies of the DOS intro and ending tunes (DISKA/ATUNE1.BIN and ATUNE6.BIN) for every music set:
   every note-on gets velocity 0, so the tune keeps its timing (and the intro skip, K9, still sees a loaded module),
   but plays nothing.
The results go to <rebuilt>/_music/amiga/. amiga_music.ps1 plays the WAV files while INTR.EXE runs.
Usage: python -I tools/make_amiga_music.py <folder with .adf files> <rebuilt folder> [vlc.exe]"""
import sys, os, glob, subprocess, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adf import Adf
from rnc import unrnc
from extract_music import find_smf, walk

MODULES = {'music.cmp': 'intro', 'vmusic.cmp': 'ending'}
# SHA-256 of the unpacked modules from the disks this was made with; other dumps of the same disks should match
KNOWN = {'intro': '26b78aeda0ac1dbdaa68e3be0706159121557db224370227489e63298fcd4faa',
         'ending': '606e033e6c436ad6e347c47a8fae57f58a2c7464deedbc5eab533ac7e77b8358'}
MUSIC_SETS = ('adlib', 'gm', 'mt32')
VLC_PATHS = (r'C:\Program Files\VideoLAN\VLC\vlc.exe', r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe')

PREFERRED = 'Moonstone_Disk1.adf'          # the name the Moonstone Rebuilt instructions ask for

def find_modules(folder):
    paths = sorted(set(glob.glob(os.path.join(folder, '*.adf')) + glob.glob(os.path.join(folder, '*.ADF'))))
    paths.sort(key=lambda p: os.path.basename(p).lower() != PREFERRED.lower())
    for path in paths:
        try:
            adf = Adf(path)
        except ValueError:
            continue
        files = {p.lower(): h for p, h in adf.walk()}
        if all(name in files for name in MODULES):
            return path, {MODULES[name]: unrnc(adf.read(files[name])) for name in MODULES}
    raise SystemExit(f'No Amiga Moonstone disk 1 (with music.cmp and vmusic.cmp) found in {folder}; expected {PREFERRED}')

def render(vlc, mod_path, wav_path):
    sout = '#transcode{acodec=s16l,channels=2,samplerate=44100}:std{access=file,mux=wav,dst=' + wav_path.replace('\\', '/') + '}'
    subprocess.run([vlc, '-I', 'dummy', '--dummy-quiet', '--no-repeat', '--no-loop', mod_path, '--sout', sout,
                    'vlc://quit'], check=True, timeout=600)
    if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100000:
        raise SystemExit(f'VLC did not render {wav_path}')

def mute(module):
    smf = find_smf(module)
    start = module.find(smf)
    out = bytearray(smf)
    for k, status, _ in walk(smf):
        if status & 0xf0 == 0x90:
            out[k + 1] = 0                                   # note-on with velocity 0 = note-off
    return module[:start] + bytes(out) + module[start + len(smf):]

def main(adf_folder, rebuilt, vlc=None):
    vlc = vlc or next((p for p in VLC_PATHS if os.path.exists(p)), None)
    if not vlc:
        raise SystemExit('VLC is needed to render the modules (https://www.videolan.org/)')
    disk, modules = find_modules(adf_folder)
    print(f'Modules found on {os.path.basename(disk)}')
    out = os.path.join(rebuilt, '_music', 'amiga')
    os.makedirs(out, exist_ok=True)
    for name, data in modules.items():
        digest = hashlib.sha256(data).hexdigest()
        if KNOWN[name] and KNOWN[name] != digest:
            print(f'  note: {name} module differs from the known disk version ({digest[:12]})')
        mod = os.path.join(out, f'{name}.mod')
        open(mod, 'wb').write(data)
        render(vlc, mod, os.path.join(out, f'{name}.wav'))
        print(f'  {name}: {len(data)} bytes, title {data[:20].split(bytes(1))[0].decode("latin-1")!r} -> {name}.wav')
    for music_set in MUSIC_SETS:
        for tune in ('ATUNE1.BIN', 'ATUNE6.BIN'):
            src = os.path.join(rebuilt, '_music', music_set, 'DISKA', tune)
            dst = os.path.join(out, music_set, tune)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(mute(open(src, 'rb').read()))
    print(f'Muted DOS intro and ending tunes for {", ".join(MUSIC_SETS)} -> {out}')

if __name__ == '__main__':
    main(*sys.argv[1:4])
