"""Switches the game's programs as one change: Fixes_On.bat (fixed), Fixes_Off.bat (original) and Custom_rules_off.bat
(default rules). Usage: python -I tools/mode.py fixed|original|default [game folder]

Every replacement, the flags ORIGINAL.FLG and CUSTOM_RULES.FLG included, goes through rules.swap_files under the
installation's lock: a failure puts the previous mode back, or leaves INSTALLING.FLG (Start.bat refuses) if even that
fails. In original mode a CUSTOM_RULES.FLG stays, so that Fixes_On.bat installs the custom rules' pair again."""
import glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules

class Refused(Exception):
    """A reason to change nothing, with the message for the player."""

AGE_REFUSALS = {
    'original': 'the original game, with its own blood option, is not used.',
    'default': 'the custom rules stay on.',
}

def plan(game, mode):
    """The (name, data or None) list for the mode; raises Refused."""
    here = lambda *parts: os.path.join(game, *parts)
    if mode in AGE_REFUSALS and rules.age_limit(game) < 18:
        raise Refused('This installation is locked to an age rating for good (PARENTAL.LCK, or no PARENTAL.LCK): '
                      f'{AGE_REFUSALS[mode]}\nOnly a new installation of Moonstone Rebuilt removes the lock. '
                      'Nothing was changed.')
    read = lambda *parts: open(here(*parts), 'rb').read()
    if mode == 'default':
        if not all(os.path.exists(here('_fixes', 'fixed', n)) for n in ('MAIN.EXE', 'SAVEHOOK.COM')):
            raise Refused('The fixed files are missing (_fixes\\fixed). Run Setup.bat first. Nothing was changed.')
        files = [] if os.path.exists(here('ORIGINAL.FLG')) else [('MAIN.EXE', read('_fixes', 'fixed', 'MAIN.EXE'))]
        # the save mode lives in SAVEHOOK.COM: the normal one back (rules.install keeps a copy in _fixes/fixed)
        return files + [('SAVEHOOK.COM', read('_fixes', 'fixed', 'SAVEHOOK.COM')), ('CUSTOM_RULES.FLG', None)]
    if mode == 'fixed':
        if os.path.exists(here(rules.SETUP_FLAG)):
            raise Refused('The setup did not finish. Run Setup.bat. Nothing was changed.')
        if os.path.exists(here(rules.INSTALLING)):
            raise Refused('A change of the game\'s programs did not finish. Close DOSBox-X and run Custom_rules_on.bat '
                          'or Setup.bat. Nothing was changed.')
    src = 'fixed' if mode == 'fixed' else 'original'
    samples = sorted(glob.glob(here('_fixes', src, 'SAMPLES', '*')))
    if not samples or not all(os.path.exists(here('_fixes', src, *n)) for n in
                              (['MAIN.EXE'], ['INTR.EXE'], ['DISKA', 'CAMEL4'])):
        raise Refused(f'The {src} programs are missing (_fixes\\{src}). Run Setup.bat first. Nothing was changed.')
    main = read('_fixes', src, 'MAIN.EXE')
    files = []
    if mode == 'fixed' and os.path.exists(here('CUSTOM_RULES.FLG')):     # D10: the custom rules' own pair
        if not all(os.path.exists(here('_fixes', 'rules', n)) for n in ('MAIN.EXE', 'SAVEHOOK.COM')):
            raise Refused('The custom rules are on, but their programs are missing (_fixes\\rules). Run '
                          'Custom_rules_on.bat. Nothing was changed.')
        main = read('_fixes', 'rules', 'MAIN.EXE')
        files.append(('SAVEHOOK.COM', read('_fixes', 'rules', 'SAVEHOOK.COM')))
    files += [('MAIN.EXE', main), ('INTR.EXE', read('_fixes', src, 'INTR.EXE'))]
    files += [(os.path.join('SAMPLES', os.path.basename(p)), open(p, 'rb').read()) for p in samples]   # K10
    files.append((os.path.join('DISKA', 'CAMEL4'), read('_fixes', src, 'DISKA', 'CAMEL4')))
    files.append(('ORIGINAL.FLG', b'original\r\n' if mode == 'original' else None))
    return files

DONE = {
    'fixed': 'Game: fixed (unpacked programs and the fixes in FIXES.md)',
    'original': 'Game: original (unpacked but unchanged programs, original sound files)',
    'default': 'Default rules (the normal game). Restart DOSBox-X for this to take effect.',
}

def switch(game, mode):
    """Returns the message; raises Refused, rules.Busy or OSError (see the module's doc)."""
    with rules.install_lock(game):                     # the flags are read under the lock that the change holds
        files = plan(game, mode)
        rules.swap_files(game, files)
        rules_on = mode == 'fixed' and dict(files).get('SAVEHOOK.COM') is not None
    return ('Custom rules from custom_rules.ini: on\n' if rules_on else '') + DONE[mode]

def main(argv):
    if len(argv) < 2 or argv[1] not in DONE:
        raise SystemExit('Usage: mode.py fixed|original|default [game folder]')
    game = os.path.abspath(argv[2]) if len(argv) > 2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        print(switch(game, argv[1]))
    except Refused as e:
        raise SystemExit(str(e))
    except rules.Busy as e:
        raise SystemExit(f'{e}. Nothing was changed.')
    except OSError as e:
        raise SystemExit(f'Could not write the game\'s files ({e}). Close DOSBox-X and run this again. ' +
                         ('The change did not finish, so Start.bat will not start the game until it does.'
                          if os.path.exists(os.path.join(game, rules.INSTALLING)) else
                          'The previous mode was put back; nothing was changed.'))

if __name__ == '__main__':
    main(sys.argv)
