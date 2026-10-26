"""Moonstone Rebuilt setup: builds the playable game folder from the user's own GOG copy of Moonstone (DOS).

Only files from the user's installation are used; nothing of the original game is part of this release.
1. Finds the GOG installation (argument, GOG Galaxy registry entry or common folders) and checks every game file
   against setup/gog-dos-1.json (SHA-256).
2. Copies the game files here: DISKA, DISKB, DISKC, SAMPLES, MS.EXE.
3. Builds the original programs, only unpacked (the packed ones fail in DOSBox-X's lowest 64 KB, and LOADFIX would
   leave too little memory), and keeps the original sound files, in _fixes/original; builds the fixed ones in
   _fixes/fixed (MAIN.EXE: K1 K2 K4 K5 K11 K17 D6 D7 D9, INTR.EXE: K9, sound files: K10).
4. Builds the music sets in _music (adlib: the original modules, mt32: the Roland modules, gm: General MIDI ones),
   SAVEHOOK.COM, MOON.CFG (Sound Blaster) and music.conf: on the first setup the best music available (MT-32 if
   the ROMs are in mt32-roms, else General MIDI if soundfonts/default.sf2 exists, else AdLib); later runs keep the choice.
5. Installs the fixed set, or the original one if ORIGINAL.FLG exists (Fixes_Off.bat).
6. If amiga/Moonstone_Disk1.adf exists, sets up the Amiga intro and ending music (needs VLC once).
It can be run again at any time; saves (save/) and the MT-32 ROMs and SoundFont are left alone.
Usage: python -I setup/setup.py [GOG Moonstone folder]"""
import sys, os, json, hashlib, shutil, glob

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'tools'))

MANIFEST = os.path.join(HERE, 'setup', 'gog-dos-1.json')
GOG_GAME_ID = '1854348302'
COMMON_FOLDERS = [r'C:\GOG Games\Moonstone', r'C:\Program Files (x86)\GOG Galaxy\Games\Moonstone',
                  r'C:\Program Files\GOG Galaxy\Games\Moonstone', r'D:\GOG Games\Moonstone']
MAIN_FIXES = ['K1', 'K2', 'K4', 'K5', 'K11', 'K17', 'D6', 'D7', 'D9']
INTR_FIXES = ['K9']
SAMPLE_FILES = None                      # set from make_voc_rates.FILES

def say(text):
    print(text, flush=True)

def gog_from_registry():
    try:
        import winreg
    except ImportError:
        return None
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf'SOFTWARE\GOG.com\Games\{GOG_GAME_ID}', 0,
                                winreg.KEY_READ | view) as key:
                return winreg.QueryValueEx(key, 'path')[0]
        except OSError:
            continue
    return None

def find_gog(arg):
    candidates = [arg] if arg else [gog_from_registry()] + COMMON_FOLDERS
    for folder in candidates:
        if folder and os.path.exists(os.path.join(folder, 'MAIN.EXE')) and os.path.isdir(os.path.join(folder, 'DISKA')):
            return folder
    return None

def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def check_gog(folder):
    files = json.load(open(MANIFEST))['files']
    bad = [f['path'] for f in files if not os.path.exists(os.path.join(folder, f['path']))
           or sha256(os.path.join(folder, f['path'])) != f['sha256']]
    if bad:
        raise SystemExit(f'{len(bad)} game files are missing or different from the GOG release, e.g. {bad[:5]}.\n'
                         'Moonstone Rebuilt needs the unchanged GOG DOS version (reinstall or verify it in GOG Galaxy).')
    return files

def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)

def write(dst, data):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'wb') as f:
        f.write(data)

def main(arg=None):
    gog = find_gog(arg)
    if not gog:
        raise SystemExit('The GOG installation of Moonstone was not found. Run Setup.bat again and give its folder,\n'
                         'for example:  Setup.bat "C:\\GOG Games\\Moonstone"')
    say(f'GOG installation: {gog}')
    files = check_gog(gog)
    say(f'  {len(files)} game files checked')

    for f in files:                                           # 2. game files
        if f['path'] not in ('MAIN.EXE', 'INTR.EXE'):
            copy(os.path.join(gog, f['path']), os.path.join(HERE, f['path']))
    say('  game files copied')

    original, fixed = os.path.join(HERE, '_fixes', 'original'), os.path.join(HERE, '_fixes', 'fixed')
    from make_voc_rates import FILES as samples, fix_rate
    for name in samples:                                         # 3. originals and fixes
        copy(os.path.join(gog, name), os.path.join(original, name))
    from make_main_exe import make_main_exe
    from make_intr_exe import make_intr_exe
    write(os.path.join(original, 'MAIN.EXE'), make_main_exe(gog))
    write(os.path.join(original, 'INTR.EXE'), make_intr_exe(gog))
    say('  building MAIN.EXE (unpacking takes a moment) ...')
    write(os.path.join(fixed, 'MAIN.EXE'), make_main_exe(gog, MAIN_FIXES))
    write(os.path.join(fixed, 'INTR.EXE'), make_intr_exe(gog, INTR_FIXES))
    for name in samples:
        write(os.path.join(fixed, name), fix_rate(open(os.path.join(gog, name), 'rb').read(), os.path.basename(name)))
    say(f'  fixes built: MAIN.EXE {" ".join(MAIN_FIXES)}, INTR.EXE {" ".join(INTR_FIXES)}, sound files K10')

    music = os.path.join(HERE, '_music')                       # 4. music sets and helpers
    for path in glob.glob(os.path.join(gog, 'DISK?', 'ATUNE*.BIN')):
        disk = os.path.basename(os.path.dirname(path))
        copy(path, os.path.join(music, 'adlib', disk, os.path.basename(path)))
    for path in glob.glob(os.path.join(gog, 'DISK?', 'RTUNE*.BIN')):
        disk = os.path.basename(os.path.dirname(path))
        copy(path, os.path.join(music, 'mt32', disk, 'A' + os.path.basename(path)[1:]))
    import make_gm_tunes
    make_gm_tunes.main(gog, os.path.join(music, 'gm'))
    from make_savehook import make_savehook
    write(os.path.join(HERE, 'SAVEHOOK.COM'), make_savehook())
    if not os.path.exists(os.path.join(HERE, 'MOON.CFG')):
        write(os.path.join(HERE, 'MOON.CFG'), b'SOUND=SOUNDBLASTER\r\nYGUARD=11234\r\n')
    music_conf = os.path.join(HERE, 'music.conf')
    if not os.path.exists(music_conf):                         # first setup: the best music available
        if glob.glob(os.path.join(HERE, 'mt32-roms', '*CONTROL.ROM')):
            chosen = 'mt32'                                    # the device the music was written for
        elif os.path.exists(os.path.join(HERE, 'soundfonts', 'default.sf2')):
            chosen = 'gm'
        else:
            chosen = 'adlib'
        copy(os.path.join(music, 'profiles', f'{chosen}.conf'), music_conf)
    conf = open(music_conf).read()                             # music in use, also if a Music_*.bat chose it
    chosen = 'mt32' if '= mt32' in conf else 'gm' if '= fluidsynth' in conf else 'adlib'
    for disk in ('DISKA', 'DISKB'):
        for path in glob.glob(os.path.join(music, chosen, disk, '*.BIN')):
            copy(path, os.path.join(HERE, disk, os.path.basename(path)))
    say(f'  music: {dict(gm="General MIDI", mt32="MT-32", adlib="AdLib")[chosen]}')
    os.makedirs(os.path.join(HERE, 'save'), exist_ok=True)
    say('  music sets, SAVEHOOK.COM and settings ready')

    use = original if os.path.exists(os.path.join(HERE, 'ORIGINAL.FLG')) else fixed   # 5. install a set
    for name in ['MAIN.EXE', 'INTR.EXE'] + samples:
        copy(os.path.join(use, name), os.path.join(HERE, name))
    say('  installed: ' + ('original programs (Fixes_Off.bat)' if use == original else 'fixed programs'))

    disk1 = os.path.join(HERE, 'amiga', 'Moonstone_Disk1.adf')  # 6. optional Amiga music
    if os.path.exists(disk1):
        import make_amiga_music
        try:
            make_amiga_music.main(os.path.join(HERE, 'amiga'), HERE)
            write(os.path.join(HERE, 'AMIGA.FLG'), b'amiga\r\n')
            say('  Amiga intro and ending music: on')
        except SystemExit as e:
            say(f'  Amiga music not set up: {e}')
    else:
        say('  Amiga music: not set up (optional; put your Amiga disk 1 as amiga\\Moonstone_Disk1.adf)')
    say('Done. Start the game with Start.bat.')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
