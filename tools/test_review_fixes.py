"""Focused regressions. Run: python -I tools/test_review_fixes.py

Set DOSBOX_X to dosbox-x.exe to also execute generated 16-bit routines in a
standalone DOS harness. This does not run Moonstone or test gameplay.
"""
import ast
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules
import make_savehook as hook

ROOT = Path(__file__).resolve().parent.parent


def names(game):
    """The folder's files, without the lock (_fixes/UPDATE.LCK) and the record BUILD.TXT."""
    return sorted(p.name for p in game.iterdir() if p.name not in ('_fixes', rules.BUILD_STAMP))


def labelled_hook():
    labels = {}
    original_build = hook.Asm.build

    def capture(assembler):
        labels.update(assembler.labels)
        return original_build(assembler)

    with patch.object(hook.Asm, 'build', capture):
        code = hook.make_savehook()
    return code, labels


class Dos:
    """The int 21h file calls of the save check, with chosen failures."""
    def __init__(self, open_error=0, content=b'', read_error=0, create_error=0, write_error=0, written=4, close_error=0,
                 close_errors=()):
        self.__dict__.update(locals())
        self.file = None
        self.calls = 0
        self.closes = 0


class Routines:
    """Runs one generated routine in a 16-bit emulator (the COM file in its own segment, game data in another)."""
    CS, DS, STOP = 0x1000, 0x3000, 0xfff0

    def __init__(self):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
        self.code, self.labels = labelled_hook()
        self.uc = Uc(UC_ARCH_X86, UC_MODE_16)
        self.uc.mem_map(0, 0x100000)
        self.uc.mem_write(self.CS * 16 + 0x100, self.code)
        self.uc.mem_write(self.CS * 16 + self.STOP, b'\xf4')
        self.uc.hook_add(UC_HOOK_INTR, self.interrupt)
        self.uc.hook_add(UC_HOOK_CODE, self.step, begin=self.CS * 16 + self.labels['refuse'],
                         end=self.CS * 16 + self.labels['refuse'])
        self.dos, self.refused = None, False

    def poke(self, label, value, add=0, size=2):
        self.uc.mem_write(self.CS * 16 + self.labels[label] + add, value.to_bytes(size, 'little'))

    def peek(self, label, add=0, size=2):
        return int.from_bytes(self.uc.mem_read(self.CS * 16 + self.labels[label] + add, size), 'little')

    def game(self, addr, value=None):
        if value is None:
            return int.from_bytes(self.uc.mem_read(self.DS * 16 + addr, 2), 'little')
        self.uc.mem_write(self.DS * 16 + addr, value.to_bytes(2, 'little'))

    def step(self, uc, *_):
        self.refused = True
        uc.emu_stop()

    def interrupt(self, uc, number, _):
        from unicorn.x86_const import UC_X86_REG_AH, UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_DX, UC_X86_REG_DS, UC_X86_REG_EFLAGS
        d, ah = self.dos, uc.reg_read(UC_X86_REG_AH)
        d.calls += 1
        error = {0x3d: d.open_error, 0x3f: d.read_error, 0x3c: d.create_error, 0x40: d.write_error, 0x3e: d.close_error}[ah]
        if ah == 0x3e:                                   # close_errors: one result for each close in turn
            if d.closes < len(d.close_errors):
                error = d.close_errors[d.closes]
            d.closes += 1
        flags = uc.reg_read(UC_X86_REG_EFLAGS) & ~1
        if error:
            uc.reg_write(UC_X86_REG_AX, error)
            uc.reg_write(UC_X86_REG_EFLAGS, flags | 1)
            return
        result = 5                                       # a handle
        at = uc.reg_read(UC_X86_REG_DS) * 16 + uc.reg_read(UC_X86_REG_DX)
        if ah == 0x3f:
            uc.mem_write(at, d.content)
            result = len(d.content)
        elif ah == 0x40:
            d.file = bytes(uc.mem_read(at, d.written))
            result = d.written
        uc.reg_write(UC_X86_REG_AX, result)
        uc.reg_write(UC_X86_REG_EFLAGS, flags)

    def call(self, label, dos=None, ds=None, bx=0):
        from unicorn.x86_const import (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP,
                                       UC_X86_REG_BX)
        self.dos, self.refused = dos or Dos(), False
        u = self.uc
        u.reg_write(UC_X86_REG_SS, 0x5000)
        u.reg_write(UC_X86_REG_SP, 0xff00 - 2)
        u.mem_write(0x5000 * 16 + 0xff00 - 2, self.STOP.to_bytes(2, 'little'))
        u.reg_write(UC_X86_REG_DS, self.DS if ds is None else ds)
        u.reg_write(UC_X86_REG_ES, self.DS)
        u.reg_write(UC_X86_REG_BX, bx)
        u.reg_write(UC_X86_REG_CS, self.CS)
        u.emu_start(self.CS * 16 + self.labels[label], self.CS * 16 + self.STOP, count=20000)


def has_unicorn():
    try:
        import unicorn  # noqa: F401
        return True
    except ImportError:
        return False


class StagedInstall(unittest.TestCase):
    """rules.swap_files and rules.install: all files or none."""
    FILES = [('SAVEHOOK.COM', b'NEW_HOOK'), ('MAIN.EXE', b'NEW_MAIN'), ('CUSTOM_RULES.FLG', b'NEW_FLAG')]

    def folder(self):
        game = Path(tempfile.mkdtemp(dir=ROOT))
        self.addCleanup(shutil.rmtree, game, True)
        (game / 'SAVEHOOK.COM').write_bytes(b'OLD_HOOK')
        (game / 'MAIN.EXE').write_bytes(b'OLD_MAIN')
        return game

    def test_success(self):
        game = self.folder()
        rules.swap_files(game, self.FILES)
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'NEW_MAIN')
        self.assertEqual((game / 'CUSTOM_RULES.FLG').read_bytes(), b'NEW_FLAG')
        self.assertEqual(names(game), ['CUSTOM_RULES.FLG', 'MAIN.EXE', 'SAVEHOOK.COM'])

    def test_each_failed_replacement_is_undone(self):
        real = os.replace
        for failing in range(3):
            with self.subTest(failing=failing):
                game = self.folder()
                seen = []

                def replace(src, dst):
                    if str(src).endswith('.new'):
                        seen.append(src)
                        if len(seen) == failing + 1:
                            raise PermissionError('held open')
                    real(src, dst)

                with patch('rules.os.replace', replace), self.assertRaises(PermissionError):
                    rules.swap_files(game, self.FILES)
                self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'OLD_MAIN')
                self.assertEqual((game / 'SAVEHOOK.COM').read_bytes(), b'OLD_HOOK')
                self.assertEqual(names(game), ['MAIN.EXE', 'SAVEHOOK.COM'])

    def test_failed_undo_leaves_the_marker(self):
        game = self.folder()
        real = os.replace

        def replace(src, dst):
            if (Path(dst).name == 'MAIN.EXE' and str(src).endswith('.new')) or str(src).endswith('.old'):
                raise PermissionError('held open')
            real(src, dst)

        with patch('rules.os.replace', replace), self.assertRaises(PermissionError):
            rules.swap_files(game, self.FILES)
        self.assertTrue((game / rules.INSTALLING).exists())

    def test_an_earlier_marker_survives_an_undo(self):
        """The undo brings back the state before this change, which was already unfinished."""
        game = self.folder()
        (game / rules.INSTALLING).write_bytes(b'earlier')
        with patch('rules.os.replace', side_effect=PermissionError('held open')), self.assertRaises(PermissionError):
            rules.swap_files(game, self.FILES)
        self.assertTrue((game / rules.INSTALLING).exists())

    def test_a_finished_change_removes_an_earlier_marker(self):
        game = self.folder()
        (game / rules.INSTALLING).write_bytes(b'earlier')
        rules.swap_files(game, self.FILES)
        self.assertFalse((game / rules.INSTALLING).exists())

    def test_write_failure_changes_nothing(self):
        game = self.folder()
        (game / 'BLOCKED').write_bytes(b'')               # a file where a folder is needed: cannot be written
        with self.assertRaises(OSError):
            rules.swap_files(game, self.FILES + [(os.path.join('BLOCKED', 'X'), b'X')])
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'OLD_MAIN')
        self.assertFalse((game / rules.INSTALLING).exists())
        self.assertEqual(names(game), ['BLOCKED', 'MAIN.EXE', 'SAVEHOOK.COM'])

    def test_install_with_a_failing_main(self):
        """The audit's repro: old MAIN, new SAVEHOOK and an old flag must not remain together."""
        game = self.folder()
        shutil.copyfile(ROOT / 'custom_rules-default.ini', game / 'custom_rules-default.ini')
        (game / 'CUSTOM_RULES.FLG').write_bytes(b'OLD_FLAG')
        (game / 'PARENTAL.LCK').write_text('18 x\n')
        real = os.replace

        def replace(src, dst):
            if Path(dst) == game / 'MAIN.EXE':
                raise PermissionError('held open')
            real(src, dst)

        with patch('rules.build', lambda g, r: (b'NEW_MAIN', b'NEW_HOOK')), patch('rules.os.replace', replace), \
                self.assertRaises(PermissionError):
            rules.install(str(game))
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'OLD_MAIN')
        self.assertEqual((game / 'SAVEHOOK.COM').read_bytes(), b'OLD_HOOK')
        self.assertEqual((game / 'CUSTOM_RULES.FLG').read_bytes(), b'OLD_FLAG')
        self.assertFalse((game / rules.INSTALLING).exists())

    def test_age_check(self):
        game = self.folder()
        k18, k12 = {'age': 18}, {'age': 12}
        rules.age_check(game, k18, setup=True)           # a new installation: age_init will allow K18
        with self.assertRaises(rules.RulesError):
            rules.age_check(game, k18)                   # no lock, not the setup: K12
        (game / 'PARENTAL.LCK').write_text('12 x\n')
        for setup in (False, True):
            rules.age_check(game, k12, setup=setup)
            with self.assertRaisesRegex(rules.RulesError, 'at most K12'):
                rules.age_check(game, k18, setup=setup)

    def test_setup_refuses_before_any_write(self):
        sys.path.insert(0, str(ROOT / 'setup'))
        import setup as installer
        game = self.folder()
        shutil.copyfile(ROOT / 'custom_rules-default.ini', game / 'custom_rules-default.ini')
        shutil.copyfile(ROOT / 'custom_rules-default.ini', game / 'custom_rules.ini')
        (game / 'CUSTOM_RULES.FLG').write_bytes(b'OLD_FLAG')
        (game / 'PARENTAL.LCK').write_text('12 x\n')
        before = {p.name: p.read_bytes() for p in game.iterdir() if p.is_file()}
        with patch.object(installer, 'HERE', str(game)), patch.object(installer, 'check_gog', lambda g: []), \
                patch.object(installer, 'find_gog', lambda a: str(game)), self.assertRaisesRegex(SystemExit, 'at most K12'):
            installer.main(str(game))
        self.assertEqual({p.name: p.read_bytes() for p in game.iterdir() if p.is_file()}, before)

    def test_a_failed_removal_is_undone(self):
        """data None removes a file; a later failure puts the removed file back."""
        game = self.folder()
        (game / 'ORIGINAL.FLG').write_bytes(b'original')
        real = os.replace

        def replace(src, dst):
            if Path(dst).name == 'SAVEHOOK.COM' and str(src).endswith('.new'):
                raise PermissionError('held open')
            real(src, dst)

        with patch('rules.os.replace', replace), self.assertRaises(PermissionError):
            rules.swap_files(game, [('ORIGINAL.FLG', None), ('MAIN.EXE', b'NEW'), ('SAVEHOOK.COM', b'NEW')])
        self.assertEqual((game / 'ORIGINAL.FLG').read_bytes(), b'original')
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'OLD_MAIN')
        self.assertEqual(names(game), ['MAIN.EXE', 'ORIGINAL.FLG', 'SAVEHOOK.COM'])
        rules.swap_files(game, [('ORIGINAL.FLG', None), ('MAIN.EXE', b'NEW')])
        self.assertEqual(names(game), ['MAIN.EXE', 'SAVEHOOK.COM'])

    def test_overlapping_changes_are_serialized(self):
        """The review's interleaving: A pauses at its first replacement while B starts. Each change that reports success
        installs its own complete set, and the last one's set is the one left."""
        import threading
        game = self.folder()
        real, paused, go = os.replace, threading.Event(), threading.Event()
        a_thread = []

        def replace(src, dst):
            if threading.get_ident() in a_thread and not go.is_set():
                paused.set()
                go.wait(10)
            real(src, dst)

        results = {}

        def run(name, files):
            if name == 'A':
                a_thread.append(threading.get_ident())
            try:
                rules.swap_files(game, files)
                results[name] = 'ok'
            except Exception as e:                       # pragma: no cover - reported by the assertion
                results[name] = repr(e)

        a = [('MAIN.EXE', b'A_MAIN'), ('SAVEHOOK.COM', b'A_HOOK')]
        b = [('MAIN.EXE', b'B_MAIN'), ('SAVEHOOK.COM', b'B_HOOK')]
        with patch('rules.os.replace', replace):
            ta = threading.Thread(target=run, args=('A', a))
            ta.start()
            self.assertTrue(paused.wait(10))
            tb = threading.Thread(target=run, args=('B', b))
            tb.start()
            tb.join(0.5)
            self.assertTrue(tb.is_alive(), 'B must wait for A\'s lock')
            go.set()
            ta.join(15)
            tb.join(15)
        self.assertEqual(results, {'A': 'ok', 'B': 'ok'})
        self.assertEqual(((game / 'MAIN.EXE').read_bytes(), (game / 'SAVEHOOK.COM').read_bytes()), (b'B_MAIN', b'B_HOOK'))
        self.assertEqual(names(game), ['MAIN.EXE', 'SAVEHOOK.COM'])

    def test_a_held_lock_refuses_after_waiting(self):
        game = self.folder()
        import threading
        held, done = threading.Event(), threading.Event()

        def hold():
            with rules.install_lock(game):
                held.set()
                done.wait(10)

        t = threading.Thread(target=hold)
        t.start()
        self.assertTrue(held.wait(10))
        try:
            with self.assertRaises(rules.Busy):
                with rules.install_lock(game, wait=0.3):
                    pass
        finally:
            done.set()
            t.join(10)
        with rules.install_lock(game, wait=0.3):         # released with its holder
            pass


@unittest.skipUnless(has_unicorn(), 'the package unicorn (make_main_exe imports it)')
class SetupFlow(unittest.TestCase):
    """setup.main with the slow builds replaced: which flags and programs each ending leaves."""
    def game(self, rules_on=True):
        game = Path(tempfile.mkdtemp(dir=ROOT))
        self.addCleanup(shutil.rmtree, game, True)
        for name in ('custom_rules-default.ini', 'Start.bat'):
            shutil.copyfile(ROOT / name, game / name)
        shutil.copyfile(ROOT / 'custom_rules-default.ini', game / 'custom_rules.ini')
        (game / 'music.conf').write_text('mididevice = default\n')
        (game / 'dosbox-x.exe').write_bytes(b'')
        (game / 'PARENTAL.LCK').write_text('18 x\n')
        (game / 'MAIN.EXE').write_bytes(b'OLD_MAIN')
        (game / 'SAVEHOOK.COM').write_bytes(b'OLD_HOOK')
        if rules_on:
            (game / 'CUSTOM_RULES.FLG').write_bytes(b'flag')
        return game

    def run_setup(self, game, replace=os.replace, main_exe=lambda gog, fixes=None: b'FIXED_MAIN'):
        sys.path.insert(0, str(ROOT / 'setup'))
        self.addCleanup(sys.path.remove, str(ROOT / 'setup'))
        import setup as installer
        import collide_fix, death_frames, gold_frames, horse_frames, make_gm_tunes, make_intr_exe, make_main_exe, make_voc_rates
        with patch.object(installer, 'HERE', str(game)), patch.object(installer, 'check_gog', lambda g: []), \
                patch.object(installer, 'find_gog', lambda a: str(game)), patch.object(make_voc_rates, 'FILES', []), \
                patch.object(make_main_exe, 'make_main_exe', main_exe), \
                patch.object(make_intr_exe, 'make_intr_exe', lambda gog, fixes=None: b'FIXED_INTR'), \
                patch.object(death_frames, 'install', lambda here, exe: exe), \
                patch.object(horse_frames, 'install', lambda here: None), \
                patch.object(gold_frames, 'install', lambda here: None), \
                patch.object(collide_fix, 'install', lambda here: None), \
                patch.object(make_gm_tunes, 'main', lambda *args: None), \
                patch.object(hook, 'make_savehook', lambda table=None: b'DEFAULT_HOOK'), \
                patch('rules.build', lambda g, r: (b'RULES_MAIN', b'RULES_HOOK')), \
                patch('rules.os.replace', replace):
            installer.main(str(game))

    def start_refused(self, game):
        env = dict(os.environ, MOONSTONE_NOLAUNCH='1', PATH=os.environ.get('PATH', '') + os.pathsep + str(game))
        r = subprocess.run(['cmd', '/d', '/c', str(game / 'Start.bat')], input='\n', text=True, capture_output=True,
                           env=env, timeout=20, cwd=game)
        return r.returncode == 1 and 'setup did not finish' in r.stdout

    def test_a_finished_setup_removes_both_flags(self):
        for rules_on, main in ((True, b'RULES_MAIN'), (False, b'FIXED_MAIN')):
            with self.subTest(rules_on=rules_on):
                game = self.game(rules_on)
                (game / rules.SETUP_FLAG).write_bytes(b'earlier')
                (game / rules.INSTALLING).write_bytes(b'earlier')
                self.run_setup(game)
                self.assertFalse((game / rules.SETUP_FLAG).exists())
                self.assertFalse((game / rules.INSTALLING).exists())
                self.assertEqual((game / 'MAIN.EXE').read_bytes(), main)

    def test_a_setup_that_stops_blocks_custom_rules_and_the_start(self):
        game = self.game()
        def fails(gog, fixes=None):
            raise RuntimeError('stopped half way')
        with self.assertRaises(RuntimeError):
            self.run_setup(game, main_exe=fails)
        self.assertTrue((game / rules.SETUP_FLAG).exists())
        before = {p.name: p.read_bytes() for p in game.iterdir() if p.is_file()}
        with self.assertRaises(rules.SetupUnfinished):
            rules.install(str(game))
        self.assertEqual({p.name: p.read_bytes() for p in game.iterdir() if p.is_file()}, before)
        r = subprocess.run([sys.executable, '-I', str(ROOT / 'tools' / 'rules.py'), str(game)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('Run Setup.bat', r.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in game.iterdir() if p.is_file()}, before)
        if os.name == 'nt':
            self.assertTrue(self.start_refused(game))

    def test_a_failed_undo_keeps_the_block(self):
        """Codex's repro through the whole Setup: MAIN.EXE cannot be replaced, and SAVEHOOK.COM not put back."""
        game = self.game()
        real = os.replace

        def replace(src, dst):
            if Path(dst) == game / 'MAIN.EXE' and str(src).endswith('.new'):
                raise PermissionError('held open')
            if Path(dst) == game / 'SAVEHOOK.COM' and str(src).endswith('.old'):
                raise PermissionError('held open')
            real(src, dst)

        with self.assertRaises(SystemExit) as stop:
            self.run_setup(game, replace)
        self.assertIn('run Setup.bat again', str(stop.exception))
        self.assertNotIn('default rules', str(stop.exception))
        self.assertTrue((game / rules.SETUP_FLAG).exists())
        self.assertTrue((game / rules.INSTALLING).exists())
        self.assertTrue((game / 'CUSTOM_RULES.FLG').exists())
        if os.name == 'nt':
            self.assertTrue(self.start_refused(game))
        self.run_setup(game)                             # the way out
        self.assertFalse((game / rules.SETUP_FLAG).exists())
        self.assertFalse((game / rules.INSTALLING).exists())
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'RULES_MAIN')
        self.assertEqual((game / 'SAVEHOOK.COM').read_bytes(), b'RULES_HOOK')

    def test_an_undone_failure_is_the_default_set(self):
        game = self.game()
        real = os.replace

        def replace(src, dst):
            if Path(dst) == game / 'MAIN.EXE' and str(src).endswith('.new'):
                raise PermissionError('held open')
            real(src, dst)

        with self.assertRaises(SystemExit) as stop:
            self.run_setup(game, replace)
        self.assertIn('default rules', str(stop.exception))
        self.assertIn('Close DOSBox-X', str(stop.exception))
        self.assertNotIn('Correct custom_rules.ini', str(stop.exception))
        for name in (rules.SETUP_FLAG, rules.INSTALLING, 'CUSTOM_RULES.FLG'):
            self.assertFalse((game / name).exists(), name)
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'FIXED_MAIN')
        self.assertEqual((game / 'SAVEHOOK.COM').read_bytes(), b'DEFAULT_HOOK')


class BuildChecks(unittest.TestCase):
    def test_no_assert_guards_the_output(self):
        """python -O removes assert statements, so nothing the release runs may rely on one."""
        for path in [*(ROOT / 'tools').glob('*.py'), *(ROOT / 'setup').glob('*.py')]:
            if path.name.startswith('test_'):
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)], [], path.name)

    def test_checks_work_under_optimization(self):
        code = '''
import sys
sys.path.insert(0, sys.argv[1])
from make_savehook import Asm
assert False, 'not optimized'
a = Asm(0x100)
a.short(0x74, 'far'); a.b(bytes(300)); a.label('far')
for step in (a.build, lambda: a.label('far')):
    try:
        step()
    except ValueError as e:
        print('refused')
    else:
        print('accepted')
'''
        r = subprocess.run([sys.executable, '-O', '-c', code, str(ROOT / 'tools')], capture_output=True, text=True)
        self.assertEqual(r.stdout.split(), ['refused', 'refused'], r.stderr)

    def test_adf_names_stay_in_the_folder(self):
        import adf
        out = os.path.abspath('out')
        self.assertEqual(adf.extract_path(out, 'music/vmusic.cmp'), os.path.join(out, 'music', 'vmusic.cmp'))
        for name in ('../escaped.txt', 'a/../../b', '..', '.. ', '...', '', 'a//b', 'C:', 'C:\\x', 'a\\..\\..\\b', 'x:stream', 'a\nb'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                adf.extract_path(out, name)

    def test_adf_extraction_refuses_an_escaping_name(self):
        """The command line, with a disk image whose root holds one file named ../escaped.txt."""
        name = b'../escaped.txt'
        image = bytearray(1760 * 512)
        image[:4] = b'DOS\x01'
        struct.pack_into('>L', image, 880 * 512 + 6 * 4, 881)       # the root's hash table: the file's header
        header = 881 * 512
        struct.pack_into('>L', image, header, 2)                    # a header block
        image[header + 0x1b0] = len(name)
        image[header + 0x1b1:header + 0x1b1 + len(name)] = name
        struct.pack_into('>L', image, header + 508, 0xfffffffd)     # a file
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            disk, out = Path(folder) / 'disk.adf', Path(folder) / 'deep' / 'out'
            disk.write_bytes(image)
            r = subprocess.run([sys.executable, '-I', str(ROOT / 'tools' / 'adf.py'), str(disk), str(out)],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn('unsafe file name', r.stderr)
            self.assertFalse((Path(folder) / 'deep' / 'escaped.txt').exists())


@unittest.skipUnless(os.name == 'nt', 'Windows batch files')
class Launchers(unittest.TestCase):
    def game(self):
        game = Path(tempfile.mkdtemp(dir=ROOT))
        self.addCleanup(shutil.rmtree, game, True)
        for name in ('Start.bat', 'Fixes_On.bat', 'Fixes_Off.bat', 'Custom_rules_off.bat'):
            shutil.copyfile(ROOT / name, game / name)
        shutil.copytree(ROOT / 'tools', game / 'tools', ignore=shutil.ignore_patterns('__pycache__', 'test_*'))
        (game / 'dosbox-x.exe').write_bytes(b'')
        (game / 'PARENTAL.LCK').write_text('18 x\n')
        return game

    def run_bat(self, game, name):
        env = dict(os.environ, MOONSTONE_NOLAUNCH='1', PATH=os.environ.get('PATH', '') + os.pathsep + str(game))
        r = subprocess.run(['cmd', '/d', '/c', str(game / name)], input='\n', text=True, capture_output=True,
                           env=env, timeout=20, cwd=game)
        return r.returncode, r.stdout + r.stderr

    def rules_pair(self, game, main=b'RULES_MAIN', hook_bytes=b'RULES_HOOK'):
        folder = game / '_fixes' / 'rules'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'MAIN.EXE').write_bytes(main)
        (folder / 'SAVEHOOK.COM').write_bytes(hook_bytes)

    def fixed_set(self, game):
        folder = game / '_fixes' / 'fixed'
        (folder / 'DISKA').mkdir(parents=True)
        (folder / 'SAMPLES').mkdir()
        (game / 'DISKA').mkdir(exist_ok=True)
        (game / 'SAMPLES').mkdir()
        (folder / 'MAIN.EXE').write_bytes(b'FIXED_MAIN')
        (folder / 'SAVEHOOK.COM').write_bytes(b'FIXED_HOOK')
        (folder / 'INTR.EXE').write_bytes(b'I')
        (folder / 'DISKA' / 'CAMEL4').write_bytes(b'C')
        (folder / 'SAMPLES' / 'A').write_bytes(b'S')

    def original_set(self, game):
        folder = game / '_fixes' / 'original'
        (folder / 'DISKA').mkdir(parents=True)
        (folder / 'SAMPLES').mkdir()
        (folder / 'MAIN.EXE').write_bytes(b'ORIGINAL_MAIN')
        (folder / 'INTR.EXE').write_bytes(b'ORIGINAL_INTR')
        (folder / 'DISKA' / 'CAMEL4').write_bytes(b'ORIGINAL_C')
        (folder / 'SAMPLES' / 'A').write_bytes(b'ORIGINAL_S')

    def installed(self, game):
        """What the mode switches may change: the programs, the sound file and the flags."""
        out = {}
        for name in ('MAIN.EXE', 'INTR.EXE', 'SAVEHOOK.COM', 'SAMPLES/A', 'DISKA/CAMEL4', 'ORIGINAL.FLG',
                     'CUSTOM_RULES.FLG', 'INSTALLING.FLG', 'custom_rules.ini', 'PARENTAL.LCK'):
            out[name] = (game / name).read_bytes() if (game / name).exists() else None
        return out

    def fixed_install(self, game, rules_on=False):
        self.fixed_set(game)
        self.original_set(game)
        if rules_on:
            self.rules_pair(game)
            (game / 'CUSTOM_RULES.FLG').write_bytes(b'flag')
        (game / 'custom_rules.ini').write_text('[Rules]\n; the player\'s own\n')
        for name, data in (('MAIN.EXE', b'RULES_MAIN' if rules_on else b'FIXED_MAIN'), ('INTR.EXE', b'I'),
                           ('SAVEHOOK.COM', b'RULES_HOOK' if rules_on else b'FIXED_HOOK'), ('SAMPLES/A', b'S'),
                           ('DISKA/CAMEL4', b'C')):
            (game / name).write_bytes(data)

    def test_a_held_file_rolls_each_switch_back(self):
        """The review's repro and its extension: each destination and flag held open in turn (Windows then refuses to
        replace or remove it). The switch fails, and the previous mode is back complete, flags included."""
        cases = [('Fixes_Off.bat', False, ['MAIN.EXE', 'INTR.EXE', 'SAMPLES/A', 'DISKA/CAMEL4']),
                 ('Fixes_On.bat', True, ['SAVEHOOK.COM', 'MAIN.EXE', 'INTR.EXE', 'SAMPLES/A', 'DISKA/CAMEL4',
                                         'ORIGINAL.FLG']),
                 ('Custom_rules_off.bat', True, ['MAIN.EXE', 'SAVEHOOK.COM', 'CUSTOM_RULES.FLG'])]
        for bat, rules_on, held in cases:
            for name in held:
                with self.subTest(bat=bat, held=name):
                    game = self.game()
                    self.fixed_install(game, rules_on)
                    if bat == 'Fixes_On.bat':                      # from original mode
                        (game / 'ORIGINAL.FLG').write_bytes(b'original\r\n')
                    before = self.installed(game)
                    with open(game / name, 'rb'):
                        code, out = self.run_bat(game, bat)
                    self.assertEqual(code, 1, out)
                    self.assertIn('previous mode was put back', out)
                    self.assertEqual(self.installed(game), before)
                    (game / 'music.conf').write_text('mididevice = default\n')
                    self.assertEqual(self.run_bat(game, 'Start.bat')[0], 0)

    def test_mode_round_trip_keeps_the_settings(self):
        """fixed + custom rules -> original (rules remembered) -> fixed (the rules' pair again) -> default rules."""
        game = self.game()
        self.fixed_install(game, rules_on=True)
        ini, lock = (game / 'custom_rules.ini').read_bytes(), (game / 'PARENTAL.LCK').read_bytes()
        self.assertEqual(self.run_bat(game, 'Fixes_Off.bat')[0], 0)
        now = self.installed(game)
        self.assertEqual((now['MAIN.EXE'], now['INTR.EXE'], now['SAMPLES/A'], now['SAVEHOOK.COM']),
                         (b'ORIGINAL_MAIN', b'ORIGINAL_INTR', b'ORIGINAL_S', b'RULES_HOOK'))
        self.assertIsNotNone(now['ORIGINAL.FLG'])
        self.assertIsNotNone(now['CUSTOM_RULES.FLG'])
        code, out = self.run_bat(game, 'Fixes_On.bat')
        self.assertEqual(code, 0, out)
        self.assertIn('Custom rules from custom_rules.ini: on', out)
        now = self.installed(game)
        self.assertEqual((now['MAIN.EXE'], now['SAVEHOOK.COM'], now['INTR.EXE'], now['ORIGINAL.FLG']),
                         (b'RULES_MAIN', b'RULES_HOOK', b'I', None))
        self.assertEqual(self.run_bat(game, 'Custom_rules_off.bat')[0], 0)
        now = self.installed(game)
        self.assertEqual((now['MAIN.EXE'], now['SAVEHOOK.COM'], now['CUSTOM_RULES.FLG'], now['INSTALLING.FLG']),
                         (b'FIXED_MAIN', b'FIXED_HOOK', None, None))
        self.assertEqual((now['custom_rules.ini'], now['PARENTAL.LCK']), (ini, lock))
        self.assertIn('mode: fixed', (game / 'BUILD.TXT').read_text())

    def test_age_lock_refuses_the_switches(self):
        game = self.game()
        self.fixed_install(game, rules_on=True)
        (game / 'PARENTAL.LCK').write_text('12 x\n')
        before = self.installed(game)
        for bat in ('Fixes_Off.bat', 'Custom_rules_off.bat'):
            code, out = self.run_bat(game, bat)
            self.assertEqual(code, 1, bat + out)
            self.assertIn('locked to an age rating for good', out)
        self.assertEqual(self.installed(game), before)

    def adlib_set(self, game):
        for disk in ('DISKA', 'DISKB'):
            (game / '_music' / 'adlib' / disk).mkdir(parents=True)
            (game / '_music' / 'adlib' / disk / 'ATUNE.BIN').write_bytes(b'T')
            (game / disk).mkdir(exist_ok=True)
        (game / '_music' / 'profiles').mkdir(parents=True)
        (game / '_music' / 'profiles' / 'adlib.conf').write_text('mididevice = default\n')

    def test_fixes_on_refuses_without_the_rules_programs(self):
        game = self.game()
        self.fixed_set(game)
        (game / 'CUSTOM_RULES.FLG').write_bytes(b'flag')
        (game / 'MAIN.EXE').write_bytes(b'OLD')
        code, out = self.run_bat(game, 'Fixes_On.bat')
        self.assertEqual(code, 1, out)
        self.assertIn('Custom_rules_on.bat', out)
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'OLD')

    def test_fixes_on_installs_the_pair(self):
        game = self.game()
        self.fixed_set(game)
        self.rules_pair(game)
        (game / 'CUSTOM_RULES.FLG').write_bytes(b'flag')
        (game / 'SAVEHOOK.COM').write_bytes(b'OTHER')
        code, out = self.run_bat(game, 'Fixes_On.bat')
        self.assertEqual(code, 0, out)
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'RULES_MAIN')
        self.assertEqual((game / 'SAVEHOOK.COM').read_bytes(), b'RULES_HOOK')

    def test_fixes_on_without_rules_uses_the_fixed_main(self):
        game = self.game()
        self.fixed_set(game)
        code, out = self.run_bat(game, 'Fixes_On.bat')
        self.assertEqual(code, 0, out)
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'FIXED_MAIN')

    def test_unfinished_change_blocks_both(self):
        game = self.game()
        self.fixed_set(game)
        (game / 'music.conf').write_text('mididevice = default\n')
        (game / rules.INSTALLING).write_bytes(b'x')
        for name in ('Start.bat', 'Fixes_On.bat'):
            code, out = self.run_bat(game, name)
            self.assertEqual(code, 1, name + out)
            self.assertIn('did not finish', out)

    def test_unfinished_setup_blocks_both(self):
        game = self.game()
        self.fixed_set(game)
        (game / 'music.conf').write_text('mididevice = default\n')
        (game / 'MAIN.EXE').write_bytes(b'OLD')
        (game / rules.SETUP_FLAG).write_bytes(b'x')
        for name in ('Start.bat', 'Fixes_On.bat'):
            code, out = self.run_bat(game, name)
            self.assertEqual(code, 1, name + out)
            self.assertIn('The setup did not finish. Run Setup.bat.', out)
        self.assertEqual((game / 'MAIN.EXE').read_bytes(), b'OLD')

    def test_start_compares_the_pair(self):
        game = self.game()
        self.rules_pair(game)
        (game / 'music.conf').write_text('mididevice = default\n')
        (game / 'CUSTOM_RULES.FLG').write_bytes(b'flag')
        (game / 'MAIN.EXE').write_bytes(b'RULES_MAIN')
        (game / 'SAVEHOOK.COM').write_bytes(b'RULES_HOOK')
        self.assertEqual(self.run_bat(game, 'Start.bat')[0], 0)
        (game / 'MAIN.EXE').write_bytes(b'FIXED_MAIN')      # the review's repro: fixed MAIN with the flag on
        code, out = self.run_bat(game, 'Start.bat')
        self.assertEqual(code, 1, out)
        self.assertIn('not theirs', out)
        (game / 'MAIN.EXE').write_bytes(b'RULES_MAIN')
        (game / 'SAVEHOOK.COM').write_bytes(b'FIXED_HOOK')
        self.assertEqual(self.run_bat(game, 'Start.bat')[0], 1)
        (game / 'ORIGINAL.FLG').write_bytes(b'o')           # original mode: only SAVEHOOK.COM is the rules'
        (game / 'SAVEHOOK.COM').write_bytes(b'RULES_HOOK')
        (game / 'MAIN.EXE').write_bytes(b'ORIGINAL_MAIN')
        self.assertEqual(self.run_bat(game, 'Start.bat')[0], 0)

    def test_adlib_fallback_failure_stops_the_start(self):
        game = self.game()
        (game / 'mt32-roms').mkdir()
        (game / 'DISKA').mkdir()
        (game / 'DISKB').mkdir()
        (game / 'music.conf').write_text('mididevice = mt32\n')
        code, out = self.run_bat(game, 'Start.bat')
        self.assertEqual(code, 1, out)
        self.assertIn('was not started', out)

    def test_adlib_fallback_success(self):
        game = self.game()
        (game / 'mt32-roms').mkdir()
        self.adlib_set(game)
        (game / 'music.conf').write_text('mididevice = mt32\n')
        code, out = self.run_bat(game, 'Start.bat')
        self.assertEqual(code, 0, out)
        self.assertNotIn('mt32', (game / 'music.conf').read_text())
        self.assertTrue((game / 'DISKA' / 'ATUNE.BIN').exists())

    def test_missing_music_conf_without_sources(self):
        game = self.game()
        (game / 'DISKA').mkdir()
        (game / 'DISKB').mkdir()
        self.assertEqual(self.run_bat(game, 'Start.bat')[0], 1)


@unittest.skipUnless(os.name == 'nt', 'Windows batch files')
class SoundSwitches(unittest.TestCase):
    """D82: separate switches for the music and the sound effects (tools/set_sound.bat), with made-up files."""
    SETS = ('adlib', 'gm', 'gm_amiga', 'mt32')
    run_bat = Launchers.run_bat

    def game(self):
        game = Launchers.game(self)
        for name in ('Music_AdLib.bat', 'Music_GM.bat', 'Music_MT32.bat', 'AmigaSound_On.bat', 'AmigaSound_Off.bat'):
            shutil.copyfile(ROOT / name, game / name)
        shutil.copytree(ROOT / '_music' / 'profiles', game / '_music' / 'profiles')
        for music_set in self.SETS:
            for disk in ('DISKA', 'DISKB'):
                (game / '_music' / music_set / disk).mkdir(parents=True)
                (game / '_music' / music_set / disk / 'ATUNE1.BIN').write_text(music_set)
                (game / disk).mkdir(exist_ok=True)
        (game / 'soundfonts').mkdir()
        (game / 'soundfonts' / 'GeneralUser-GS.sf2').write_bytes(b'GU')
        (game / 'mt32-roms').mkdir()
        (game / 'mt32-roms' / 'MT32_CONTROL.ROM').write_bytes(b'R')
        (game / '_music' / 'amiga').mkdir()
        (game / '_music' / 'amiga' / 'amiga.sf2').write_bytes(b'A')
        (game / '_music' / 'amiga' / 'amiga_gm.sf2').write_bytes(b'M')   # not real fonts: the merge fails, the file stays
        return game

    def state(self, game):
        conf = (game / 'music.conf').read_text()
        return (conf, (game / 'effects.cfg').read_text().strip(), (game / 'DISKA' / 'ATUNE1.BIN').read_text())

    def profile(self, game, name):
        return (game / '_music' / 'profiles' / f'{name}.conf').read_text()

    def switch(self, game, name):
        code, out = self.run_bat(game, name)
        self.assertEqual(code, 0, out)
        return out

    def test_each_switch_keeps_the_other_choice(self):
        game = self.game()
        self.switch(game, 'Music_AdLib.bat')
        self.assertEqual(self.state(game), (self.profile(game, 'adlib'), 'dos', 'adlib'))
        self.assertIn('Music: AdLib (original). Sound effects: Amiga.', self.switch(game, 'AmigaSound_On.bat'))
        self.assertEqual(self.state(game), (self.profile(game, 'amiga'), 'amiga', 'adlib'))
        self.switch(game, 'Music_GM.bat')            # GM with the Amiga effects: the merged font, the UART tunes
        self.assertEqual(self.state(game), (self.profile(game, 'amiga_gm'), 'amiga', 'gm_amiga'))
        self.switch(game, 'AmigaSound_Off.bat')      # GM without them: the fluidsynth device, the shipped font
        conf, effects, tunes = self.state(game)
        self.assertEqual((effects, tunes), ('dos', 'gm'))
        self.assertTrue(conf.startswith(self.profile(game, 'gm')))
        self.assertIn('fluid.soundfont = soundfonts\\GeneralUser-GS.sf2', conf)
        (game / 'soundfonts' / 'default.sf2').write_bytes(b'OWN')
        self.switch(game, 'Music_GM.bat')            # the user's own font: the conf's default.sf2
        self.assertEqual(self.state(game), (self.profile(game, 'gm'), 'dos', 'gm'))

    def test_mt32_and_the_amiga_effects_exclude_each_other(self):
        game = self.game()
        self.switch(game, 'AmigaSound_On.bat')
        out = self.switch(game, 'Music_MT32.bat')
        self.assertIn('the effects are now the DOS game', out)
        self.assertEqual(self.state(game), (self.profile(game, 'mt32'), 'dos', 'mt32'))
        out = self.switch(game, 'AmigaSound_On.bat')
        self.assertIn('the music is now AdLib', out)
        self.assertEqual(self.state(game), (self.profile(game, 'amiga'), 'amiga', 'adlib'))

    def test_start_follows_effects_cfg(self):
        game = self.game()
        self.switch(game, 'Music_GM.bat')
        self.switch(game, 'AmigaSound_On.bat')
        (game / 'DISKA' / 'ATUNE1.BIN').write_text('as left')
        code, out = self.run_bat(game, 'Start.bat')
        self.assertEqual(code, 0, out)
        self.assertTrue((game / 'AMIGASND.FLG').exists())
        self.assertEqual(self.state(game), (self.profile(game, 'amiga_gm'), 'amiga', 'as left'))   # nothing to fix
        self.switch(game, 'AmigaSound_Off.bat')
        self.assertEqual(self.run_bat(game, 'Start.bat')[0], 0)
        self.assertFalse((game / 'AMIGASND.FLG').exists())

    def test_start_falls_back(self):
        game = self.game()
        self.switch(game, 'Music_GM.bat')
        self.switch(game, 'AmigaSound_On.bat')
        (game / '_music' / 'amiga' / 'amiga.sf2').unlink()      # the effects gone: DOS effects, GM music stays
        code, out = self.run_bat(game, 'Start.bat')
        self.assertEqual(code, 0, out)
        self.assertIn('not set up', out)
        conf, effects, tunes = self.state(game)
        self.assertEqual((effects, tunes, 'GeneralUser-GS.sf2' in conf), ('dos', 'gm', True))
        self.assertFalse((game / 'AMIGASND.FLG').exists())

    def test_old_install_without_effects_cfg(self):
        game = self.game()
        shutil.copyfile(game / '_music' / 'profiles' / 'amiga.conf', game / 'music.conf')   # AmigaSound_On.bat before D82
        self.assertEqual(self.run_bat(game, 'Start.bat')[0], 0)
        self.assertTrue((game / 'AMIGASND.FLG').exists())
        self.assertEqual((game / 'effects.cfg').read_text().strip(), 'amiga')


@unittest.skipUnless(has_unicorn(), 'the package unicorn')
class GeneratedRoutines(unittest.TestCase):
    def test_token_failures_refuse(self):
        token = (0x1234).to_bytes(2, 'little') + (7).to_bytes(2, 'little')
        fine = dict(open_error=0, content=token)
        cases = [('a match', Dos(**fine), False),
                 ('no file yet', Dos(open_error=2), False),
                 ('another token', Dos(content=b'\0\0\0\0'), True),
                 ('open: access denied', Dos(open_error=5), True),
                 ('open: too many files', Dos(open_error=4), True),
                 ('read fails', Dos(open_error=0, content=token, read_error=5), True),
                 ('a short file', Dos(content=token[:2]), True),
                 ('an empty file', Dos(content=b''), True),
                 ('create fails', Dos(open_error=2, create_error=5), True),
                 ('write fails', Dos(open_error=2, write_error=5), True),
                 ('a short write', Dos(open_error=2, written=2), True),
                 ('close fails', Dos(open_error=2, close_error=5), True),
                 ('only the read handle fails to close', Dos(content=token, close_errors=(6, 0)), True),
                 ('only the new token fails to close', Dos(content=token, close_errors=(0, 6)), True)]
        r = Routines()
        for mode in (hook.AUTO_ONLY, hook.NO_SAVES):
            r.poke('rules_table', mode, rules.G_SAVE_MODE, 1)
            for name, dos, refuse in cases:
                with self.subTest(mode=mode, case=name):
                    r.poke('token', 0x1234)
                    r.poke('token', 7, 2)
                    dos.file, dos.closes = None, 0
                    r.call('checkpoint', dos)
                    self.assertEqual(r.refused, refuse)
                    if name == 'only the read handle fails to close':
                        self.assertIsNone(dos.file)              # refused before a new token was written
                    if not refuse:
                        self.assertEqual(r.peek('token', 2), 8)
                        self.assertEqual(dos.file, bytes(r.uc.mem_read(r.CS * 16 + r.labels['token'], 4)))

    def test_other_save_modes_touch_no_file(self):
        r = Routines()
        r.poke('rules_table', 0, rules.G_SAVE_MODE, 1)
        dos = Dos(open_error=5)
        r.call('checkpoint', dos)
        self.assertFalse(r.refused)
        self.assertEqual(dos.calls, 0)

    def test_accept_refuses_a_failed_write(self):
        r = Routines()
        r.poke('rules_table', hook.AUTO_ONLY, rules.G_SAVE_MODE, 1)
        r.call('accept', Dos(create_error=5), ds=r.CS)
        self.assertTrue(r.refused)
        r.call('accept', Dos(), ds=r.CS)
        self.assertFalse(r.refused)

    def test_first_roll_does_not_read_the_shared_state(self):
        r = Routines()
        r.poke('rules_table', 1, rules.G_FATE, 1)
        results = set()
        for shared in (123, 45678):
            r.poke('fate_state', 0, 6)
            r.game(hook.RANDOM_STATE, shared)
            r.call('fate_prepare', bx=6)
            results.add((r.peek('fate_state', 6), r.game(hook.RANDOM_STATE)))
        self.assertEqual(len(results), 1, results)

    def test_a_zero_is_never_stored(self):
        r = Routines()
        r.poke('rules_table', 1, rules.G_FATE, 1)
        r.poke('fate_state', 3915, 6)
        r.call('fate_prepare', bx=6)
        self.assertEqual(r.peek('fate_state', 6), 1)
        self.assertEqual(r.game(hook.RANDOM_STATE), 1)

    def test_init_seeds_only_unused_streams(self):
        from unicorn.x86_const import UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX
        r = Routines()
        seeds = []
        for shared in (123, 45678):
            for stream in range(rules.FATE_STREAMS):
                r.poke('fate_state', 0, 2 * stream)
            r.poke('fate_state', 999, 2)                 # a stream in use stays as it is
            r.game(hook.RANDOM_STATE, shared)
            for reg, value in ((UC_X86_REG_AX, 1), (UC_X86_REG_CX, 2), (UC_X86_REG_DX, 3)):
                r.uc.reg_write(reg, value)
            r.call('fate_init', bx=4)
            self.assertEqual(r.game(hook.RANDOM_STATE), shared)
            self.assertEqual(r.peek('fate_state', 2), 999)
            states = [r.peek('fate_state', 2 * s) for s in range(rules.FATE_STREAMS)]
            self.assertNotIn(0, states)
            self.assertEqual(len(set(states)), rules.FATE_STREAMS)
            self.assertEqual([r.uc.reg_read(x) for x in (UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX)], [1, 4, 2, 3])
            seeds.append(states)
        self.assertNotEqual(seeds[0], seeds[1])


@unittest.skipUnless(has_unicorn(), 'the package unicorn')
class Minefield(unittest.TestCase):
    ANIM = hook.ANIM_SLOTS
    KNIGHT = hook.KNIGHTS[1]
    MINE_X, MINE_Z = 100, 100

    def stepped_on(self, x, depth, kind=6, mirrored=False):
        r = Routines()
        for offset in range(0, hook.ANIM_SIZE * hook.ANIM_COUNT, 2):
            r.game(self.ANIM + offset, 0)
        r.game(self.ANIM, 1)
        r.game(self.ANIM + 0x14, 2 if mirrored else 0)
        r.game(self.ANIM + 0x16, self.KNIGHT)
        r.game(self.KNIGHT + 2, x)
        r.game(self.KNIGHT + 4, 0)
        r.game(self.KNIGHT + 6, depth)
        r.game(self.KNIGHT + 0x34, kind << 8)
        r.game(self.KNIGHT + 0x38, 20)
        r.poke('mine_live', 1)
        r.poke('mine_x', self.MINE_X)
        r.poke('mine_z', self.MINE_Z)
        r.call('mine_frame')
        return r.peek('mine_live') == 0

    def test_only_the_feet_set_it_off(self):
        on = self.MINE_Z - hook.MINE_FOOT_Z
        for kind in (6, hook.COMPUTER_TYPE):
            with self.subTest(kind=kind):
                self.assertTrue(self.stepped_on(self.MINE_X, on, kind))
                # the body over the mark: where the old check, at the mine's own depth, set it off
                self.assertFalse(self.stepped_on(self.MINE_X, self.MINE_Z, kind))
                self.assertFalse(self.stepped_on(self.MINE_X, self.MINE_Z - 6, kind))
                for depth, hit in ((on - 3, False), (on - 2, True), (on + 2, True), (on + 3, False)):
                    self.assertEqual(self.stepped_on(self.MINE_X, depth, kind), hit, depth)

    def test_the_feet_follow_the_facing(self):
        on = self.MINE_Z - hook.MINE_FOOT_Z
        for mirrored, low, high in ((False, -19, 13), (True, -12, 20)):       # x - mine x
            with self.subTest(mirrored=mirrored):
                for x, hit in ((low - 1, False), (low, True), (high, True), (high + 1, False)):
                    self.assertEqual(self.stepped_on(self.MINE_X + x, on, mirrored=mirrored), hit, x)

    def test_monsters_are_as_before(self):
        self.assertTrue(self.stepped_on(self.MINE_X, self.MINE_Z, 0x20))
        self.assertFalse(self.stepped_on(self.MINE_X, self.MINE_Z - hook.MINE_FOOT_Z, 0x20))

    def shared_colours(self, recolour, shift, bank, table=hook.HE_BANK):
        from unicorn.x86_const import UC_X86_REG_DI, UC_X86_REG_SI
        r = Routines()
        r.poke('recolour', recolour, size=1)
        r.poke('rc_shift', shift, size=1)
        r.game(0x8941, 0x10), r.game(0x8943, r.DS), r.game(0x8945, 0x20), r.game(0x8947, r.DS)
        r.game(0x500 + 0x18, table)
        r.uc.reg_write(UC_X86_REG_DI, 0x500)
        r.uc.reg_write(UC_X86_REG_SI, bank)
        r.call('he_shared')
        return r.peek('recolour', size=1), r.peek('rc_shift', size=1)

    def test_the_crush_takes_the_knights_colour(self):
        for bank in (0x10, 0x20):                        # KN4.OB, KN5.OB
            self.assertEqual(self.shared_colours(0, 99, bank), (6, 3))    # the duel's second knight: 6-8 to 9-11
            self.assertEqual(self.shared_colours(9, 26, bank), (6, 29))   # the fourth: 6-8 to its 35-37
            self.assertEqual(self.shared_colours(6, 32, bank), (6, 32))   # already moved
        self.assertEqual(self.shared_colours(0, 99, 0x30), (0, 99))       # the knight's own HE frames
        self.assertEqual(self.shared_colours(0, 99, 0x20, hook.KNIGHT_BANK), (0, 99))   # the KN look


@unittest.skipUnless(has_unicorn(), 'the package unicorn')
class SwordTints(unittest.TestCase):
    def shift(self, weapon, kind=6, bank=0x10, armour=0x1b, body_file=True):
        from unicorn.x86_const import UC_X86_REG_DI, UC_X86_REG_SI, UC_X86_REG_ES
        r = Routines()
        record = 0x6d62
        r.game(0x8941, 0x10), r.game(0x8943, r.DS)
        r.game(0x8937, r.DS if body_file else 0x2222)   # KN1.OB's segment: the body pieces here come from it
        r.game(0x500 + 0x16, record), r.game(record + 0x34, kind << 8), r.game(record + 0x40, weapon)
        r.game(record + 0x42, armour)
        r.poke('sw_shift', 0, size=1)
        r.uc.reg_write(UC_X86_REG_DI, 0x500)
        r.uc.reg_write(UC_X86_REG_SI, bank)
        r.call('sword_tint')
        return r.peek('sw_shift', size=1)

    def test_each_sword_its_entries(self):
        first = {weapon: hook.SWORD_FIRST + 4 * k for k, (weapon, _) in enumerate(hook.SWORD_TINTS)}
        self.assertEqual(first, {0x16: 48, 0x17: 52, 0x19: 56})
        for weapon, entry in first.items():
            self.assertEqual(self.shift(weapon), entry - 1)                 # pixel 1 -> the first entry
            self.assertEqual(self.shift(weapon, hook.COMPUTER_TYPE), entry - 1)
        self.assertEqual(self.shift(0x18), 0)                               # the claymore: the game's steel
        self.assertEqual(self.shift(0x16, kind=0x1a), 0)                    # a thrown dagger's object
        self.assertEqual(self.shift(0x16, bank=0x30), 0)                    # not KN4.OB: padded armour, none

    def test_each_armour_its_entries(self):
        first = {armour: hook.ARMOUR_FIRST + 4 * k for k, (armour, _) in enumerate(hook.ARMOUR_TINTS)}
        self.assertEqual(first, {0x1c: 60, 0x1d: 64, 0x1e: 68})
        for armour, entry in first.items():
            self.assertEqual(self.shift(0x16, bank=0x30, armour=armour), entry - 1)   # a body piece
            self.assertEqual(self.shift(0x16, armour=armour), 47)                    # the sword: its weapon
        self.assertEqual(self.shift(0x16, kind=0x20, bank=0x30, armour=0x1e), 0)     # a troll: nothing
        self.assertEqual(self.shift(0x16, bank=0x30, armour=0x1e, body_file=False), 0)   # not a body file (the map's)

    def test_entries_fit(self):
        self.assertLessEqual(hook.SWORD_FIRST + hook.GEAR_ENTRIES, 256)
        self.assertGreater(hook.SWORD_FIRST, hook.NEW_ENTRIES + hook.NEW_WORDS - 1)   # after 32-43
        for _, colours in hook.SWORD_TINTS + hook.ARMOUR_TINTS:
            self.assertTrue(all(0 <= v <= 63 for rgb in colours for v in rgb))

    def test_item_violets_after_the_gear(self):
        # D119: the item screen's violets (D98) are DAC entries of their own after the gear's, written with them;
        # the item palette's 17-19 (the pointer's, MI.C) stay the game's, and no item-screen look uses them
        self.assertEqual(hook.VIOLET, tuple(range(hook.SWORD_FIRST + hook.GEAR_ENTRIES, hook.SWORD_FIRST + hook.GEAR_ENTRIES + 3)))
        self.assertLessEqual(max(hook.VIOLET), 255)
        self.assertEqual(hook.ITEM_PALETTE_GAME, (0x0fff, 0x0777, 0x0000))
        looks = [list(hook.ENCH_LOOK_MAP.values())] + [list(v) for t in (hook.POT_LOOKS, hook.RING_LOOKS, hook.GEM_LOOKS) for v in t.values()]
        self.assertFalse([v for look in looks for v in look if v in (17, 18, 19)])

    def test_stat_ring_number_shown(self):
        # D121: the item screen's ability number (_ablloop, C3EB) counts the stat rings; D108's gadget-count hooks
        # (C2BD, C2F3, C329) are gone
        sites = {site: name for site, old, name in rules.HOOKS}
        self.assertEqual(sites.get(0xc3eb), 'ring_abl')
        self.assertFalse([s for s in (0xc2bd, 0xc2f3, 0xc329) if s in sites])

    def test_math_mythral_ability_cap(self):
        # D123: the fixed game's pick test (B9EC) is int 63h, a PRACTICE_HOOKS job, and the patch is in setup.py's list
        from patches import PATCHES
        self.assertEqual(PATCHES['D123']['bytes'], [((0x1000, 0xb9ec), bytes.fromhex('80390574d1'), bytes.fromhex('cd63909090'))])
        self.assertIn((0xb9ee, 'ability_pick'), hook.PRACTICE_HOOKS)
        line = (ROOT / 'setup' / 'setup.py').read_text(encoding='utf-8').split('MAIN_FIXES = ')[1].split('\n')[0]
        self.assertIn("'D123'", line)

    def test_no_write_outside_the_abilities(self):
        # D126: with every ability at 5 or more the pick gives bx = 0: the Guardian's lowering (1003) skips it in
        # place, Mythral's loss (BBAC) is int 63h (mythral_loss); the patch is in setup.py's list
        from patches import PATCHES
        self.assertEqual(PATCHES['D126']['bytes'],
                         [((0x1000, 0x1003), bytes.fromhex('5603f3803c015e74075603f3802c015e'),
                           bytes.fromhex('85db740c803801740780280190909090')),
                          ((0x1000, 0xbbac), bytes.fromhex('8039017445'), bytes.fromhex('cd63909090'))])
        self.assertIn((0xbbae, 'mythral_loss'), hook.PRACTICE_HOOKS)
        line = (ROOT / 'setup' / 'setup.py').read_text(encoding='utf-8').split('MAIN_FIXES = ')[1].split('\n')[0]
        self.assertIn("'D126'", line)

    def test_guardian_lowers_any_ability(self):
        # D130: the Guardian's penalty draws its own ability (0FF8: call B9C2 -> int 63h + nop, guardian_pick)
        from patches import PATCHES
        self.assertEqual(PATCHES['D130']['bytes'], [((0x1000, 0x0ff8), bytes.fromhex('e8c7a9'), bytes.fromhex('cd6390'))])
        self.assertIn((0x0ffa, 'guardian_pick'), hook.PRACTICE_HOOKS)
        line = (ROOT / 'setup' / 'setup.py').read_text(encoding='utf-8').split('MAIN_FIXES = ')[1].split('\n')[0]
        self.assertIn("'D130'", line)

    def test_troll_club_points(self):
        # D131: the fixed MAIN.EXE loads COLLFIX.HIT (DS:9D82), the game's COLLIDE.HIT with more points on the troll
        # blow's club pieces in the room of TROLL2.CEL frame 0Dh's; the file keeps within MAIN.EXE's room (DS:A1DE-C282)
        import collide_fix
        from patches import PATCHES
        self.assertEqual(PATCHES['D131']['bytes'], [(('DS', 0x9d82), b'COLLIDE.HIT', b'COLLFIX.HIT')])
        text = (ROOT / 'setup' / 'setup.py').read_text(encoding='utf-8')
        self.assertIn("'D131'", text.split('MAIN_FIXES = ')[1].split('\n')[0])
        self.assertIn('install_collide(HERE)', text)
        self.assertEqual(collide_fix.ROOM, 8356)
        self.assertEqual(set(collide_fix.ADDED), {('troll2.cel', 2), ('troll1.cel', 0x24)})
        self.assertEqual(sum(len(v) for v in collide_fix.ADDED.values()), 14)
        game = ROOT / 'DISKB' / 'COLLIDE.HIT'
        if game.exists():                                 # a set-up checkout: the real file
            data = game.read_bytes()
            out = collide_fix.make(data)
            self.assertLessEqual(len(out), collide_fix.ROOM)
            self.assertEqual(out.count(b'\n'), data.count(b'\n') - 2)   # frame 0Dh's flag and points lines gone

    def test_skipcombat_code(self):
        # D122: SKIPCOMBAT is a map code (ids 60-79) with its own map_flags bit; its skips sit in the lair visit (0581),
        # LairWon's first-win mark (05B6) and the dragon's attack (0D15); its work is in group OVL_COLD, and group 1
        # (the map codes) still fits the window it had
        self.assertIn('SKIPCOMBAT', hook.CHEAT_MAP_CODES)
        self.assertTrue(60 <= hook.CHEAT_ID['SKIPCOMBAT'] < 80)
        self.assertEqual(hook.MAP_SKIP & (hook.MAP_WALK | hook.MAP_ANY_KEYS), 0)
        sites = {site: name for site, old, name in rules.HOOKS}
        self.assertEqual((sites.get(0x0581), sites.get(0x05b6), sites.get(0x0d15)), ('lair_hawk', 'lair_loot', 'dragon_scroll'))
        a, _ = hook._build_savehook(None, None)
        self.assertEqual({hook.OVL_COLD}, {a.entries[n][0] for n in ('skip_lair', 'skip_dragon', 'cm_bd')})
        self.assertLessEqual(len(a.groups[hook.OVL_CHEATS][0]), 1360)

    def test_dragon_aim(self):
        # D150: the dragon's walk (TrackKnight 3BF4, also run from its fires' scripts) reads its knight at 3C00; in
        # co-op dragon_aim (resident) gives it the dragon's own (last_target at the dragon's place, 20)
        self.assertIn((0x3c00, 'a17809', 'dragon_aim'), rules.HOOKS)
        self.assertEqual(hook.MONSTER_COUNT, 20)
        a, _ = hook._build_savehook(None, None)
        self.assertIn('rules_dragon_aim', a.labels)
        self.assertNotIn('rules_dragon_aim', {n for n in a.entries})

    def test_riposte_rules(self):
        # D151: a riposte does not stop the troll's or the hammer trogg's blow from above (TroggStruck 2F28, ControlTroll
        # 55E7, TrollStruck 56DC; gun_monster finishes the trogg's); D125's tie keeps only the axe trogg and takes a
        # knight's chop against a riposte; one riposte for each blow (rip_foe, cleared by td_note_attack): all resident
        sites = {site: (old, name) for site, old, name in rules.HOOKS}
        self.assertEqual(sites.get(0x2f28), ('c6454a00', 'trogg_struck'))
        self.assertEqual(sites.get(0x55e7), ('837d0c00', 'troll_tie'))
        self.assertEqual(sites.get(0x56dc), ('c7063a78945c', 'troll_flinch'))
        self.assertEqual((hook.TIE_MONSTERS, hook.RIPOSTE_MONSTERS, hook.TROLL_CHOP), ((0x0c,), (0x20, 0x0c, 0x0e), 0x5b9e))
        a, _ = hook._build_savehook(None, None)
        entries = {n for n in a.entries}
        for name in ('rules_trogg_struck', 'rules_troll_tie', 'rules_troll_flinch', 'rip_by', 'rip_clear', 'rip_foe', 'tie_rip'):
            self.assertIn(name, a.labels)
            self.assertNotIn(name, entries)

    def test_back_tap_turns(self):
        # D152: a back key let go during D24's chord wait still turns at its end (rules_input's ich_gone, resident; the
        # keyboard knights only; dropped after CHORD_STALE ticks, more than input_chord's largest value 6)
        a, _ = hook._build_savehook(None, None)
        entries = {n for n in a.entries}
        for name in ('ich_gone', 'ich_keys', 'ich_waited'):
            self.assertIn(name, a.labels)
            self.assertNotIn(name, entries)
        self.assertGreater(hook.CHORD_STALE, 6)
        self.assertEqual(hook.KEYS3_CONTROL, 7)

    def test_spear_trogg_pause_and_riposte_tie(self):
        # D124: the spear trogg's waits from [Monsters] spear_trogg_attack_pause (130 % in both ini files): TroggHit's
        # hook at 2F61 and the immediate at 2ED1; D125: td_tie, called from hit_pair (A14C), is in the resident code
        sites = {site: name for site, old, name in rules.HOOKS}
        self.assertEqual(sites.get(0x2f61), 'spear_pause')
        for name in ('custom_rules-default.ini', 'custom_rules.ini'):
            self.assertEqual(rules.read_ini(str(ROOT / name))['spear_pause'], 130)
        self.assertEqual((rules.spear_pause(10, 130), rules.spear_pause(20, 130), rules.spear_pause(20, 100)), (13, 26, 20))
        a, _ = hook._build_savehook(None, None)
        self.assertIn('td_tie', a.labels)
        self.assertNotIn('td_tie', {n for n in a.entries})

    def test_fight_safety_timer(self):
        # D127, D132: [Combat] fight_idle_exit (30 s in both ini files, as BIOS ticks in the table, off without custom
        # rules; D127's fight_safety_timer gone from the files); the frame test is resident (the fight loop's test),
        # the leaving's work, the knights watched and the hint in group OVL_MAP
        for name in ('custom_rules-default.ini', 'custom_rules.ini'):
            r = rules.read_ini(str(ROOT / name))
            self.assertEqual(r['safety'], 30)
            self.assertEqual(struct.unpack_from('<H', rules.table(r), rules.G_SAFETY)[0], 546)
            self.assertNotIn('fight_safety_timer', (ROOT / name).read_text(encoding='utf-8'))
        self.assertEqual(struct.unpack_from('<H', rules.table(None), rules.G_SAFETY)[0], 0)
        self.assertEqual(rules.safety_ticks(3600), 0xffff)
        a, _ = hook._build_savehook(None, None)
        self.assertIn('safety_frame', a.labels)
        self.assertNotIn('safety_frame', a.entries)
        self.assertEqual({hook.OVL_MAP}, {a.entries[n][0] for n in ('safety_leave', 'safety_end', 'safety_start', 'safety_hint')})
        self.assertLessEqual(len(a.groups[hook.OVL_MAP][0]), 1268)
        self.assertEqual(len(hook.hint_rows(hook.SH_TEXT)[0]), hook.SH_W)
        self.assertTrue(104 <= hook.SH_X and hook.SH_X + hook.SH_W + 1 <= 104 + 112 and 2 <= hook.SH_Y and hook.SH_Y + 6 <= 2 + 11)   # in score_box


class InputSettings(unittest.TestCase):
    def test_chord_and_log_settings(self):
        source = (ROOT / 'custom_rules-default.ini').read_text(encoding='utf-8')
        self.assertEqual(rules.table(rules.read_ini(ROOT / 'custom_rules-default.ini'))[rules.G_INPUT_CHORD], 2)
        self.assertEqual(rules.table(None)[rules.G_INPUT_CHORD], rules.INPUT_CHORD_DEFAULT)
        self.assertEqual(rules.table(None)[rules.G_INPUT_LOG], 0)
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            ini = Path(folder) / 'custom_rules.ini'
            for text, chord, log in (('input_chord = 0', 0, 0), ('input_chord = 6', 6, 0)):
                ini.write_text(source.replace('input_chord = 2', text), encoding='utf-8')
                t = rules.table(rules.read_ini(ini))
                self.assertEqual((t[rules.G_INPUT_CHORD], t[rules.G_INPUT_LOG]), (chord, log))
            ini.write_text(source.replace('input_log = off', 'input_log = on'), encoding='utf-8')
            self.assertEqual(rules.table(rules.read_ini(ini))[rules.G_INPUT_LOG], 1)
            ini.write_text(source.replace('input_chord = 2', 'input_chord = 7'), encoding='utf-8')
            with self.assertRaisesRegex(rules.RulesError, 'input_chord'):
                rules.read_ini(ini)
            old = source.replace('input_chord = 2', ';').replace('input_log = off', ';')
            ini.write_text(old, encoding='utf-8')          # an older custom_rules.ini: the defaults
            t = rules.table(rules.read_ini(ini))
            self.assertEqual((t[rules.G_INPUT_CHORD], t[rules.G_INPUT_LOG]), (2, 0))

    def test_coop_lairs_setting(self):
        source = (ROOT / 'custom_rules-default.ini').read_text(encoding='utf-8')
        t = rules.table(rules.read_ini(ROOT / 'custom_rules-default.ini'))
        self.assertEqual((t[rules.G_COOP_LAIRS], t[rules.G_COOP_EXTRA]), (1, 50))      # full, 50 %
        self.assertEqual(rules.table(None)[rules.G_COOP_LAIRS], 0)                     # no custom rules: none
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            ini = Path(folder) / 'custom_rules.ini'
            for text, mode in (('off', 0), ('full', 1), ('shared', 2), ('on', 1)):
                ini.write_text(source.replace('coop_lairs = full', 'coop_lairs = ' + text), encoding='utf-8')
                self.assertEqual(rules.table(rules.read_ini(ini))[rules.G_COOP_LAIRS], mode, text)
            ini.write_text(source.replace('coop_lairs = full', ';').replace('extra_loot_per_knight = 50', ';'), encoding='utf-8')
            t = rules.table(rules.read_ini(ini))                                       # an older custom_rules.ini
            self.assertEqual((t[rules.G_COOP_LAIRS], t[rules.G_COOP_EXTRA]), (1, 50))
            ini.write_text(source.replace('extra_loot_per_knight = 50', 'extra_loot_per_knight = 101'), encoding='utf-8')
            with self.assertRaisesRegex(rules.RulesError, 'extra_loot_per_knight'):
                rules.read_ini(ini)

    def test_log_report(self):
        import input_log
        fight = [(100, 1, 0x48, 0, 0), (101, 1, 0x1c, 0, 0), (103, 3, 0, 0x18, 0x18), (103, 4, 0, 0x18, 1),
                 (110, 3, 0, 0x02, 0x00), (111, 4, 1, 0x1a, 3)]
        data = struct.pack('<2sHH', b'IL', len(fight), 3) + b''.join(struct.pack('<HBBBB', *e) for e in fight)
        lines = []
        input_log.report(data + data, lines.append)
        text = chr(10).join(lines)
        self.assertEqual(text.count('Fight '), 2)
        self.assertIn('3 lost', text)
        self.assertIn('overhead chop, 110 ms after fire', text)
        self.assertIn('held back (input_chord)', text)
        self.assertIn('fire+up+left facing left = upward thrust', text)


class SpecialItems(unittest.TestCase):
    """D137: [Special_items] and its master switch; D139: the lairs way (special_items = lairs, the default file's;
    D140: special_item_lairs = 8 by default).
    The fixtures: the default ini of D136 (the keys still in [Rules] and [Treasure]), a copy of an older user's
    custom_rules.ini (all five chances 100), and their tables as built before D137 (the map tool's places left out,
    so the bytes do not depend on tools/places.csv). Those tables end before D139's bytes (G_SPEC_MODE on)."""
    FIX = Path(__file__).resolve().parent / 'fixtures'
    OLD = 'custom_rules-d136-default.ini'
    USER = 'custom_rules-older-user.ini'
    LAIRS = '\nspecial_items = lairs '                # the key's line (the comments name it too)
    CHANCES = ('G_ENCH_CHANCE', 'G_ARM_CHANCE', 'G_POT_CHANCE', 'G_RING_CHANCE', 'G_GEM_CHANCE')

    def setUp(self):
        import json
        self.want = json.loads((self.FIX / 'special_items_tables.json').read_text(encoding='utf-8'))
        p = patch.object(rules, 'places_layout', lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)
        self.source = (ROOT / 'custom_rules-default.ini').read_text(encoding='utf-8')
        # B9 (D161) turned ratmen_disease on in the default file; the fixtures' tables were built with it off
        self.assertEqual(self.source.count('\nratmen_disease = on '), 1)
        self.source = self.source.replace('\nratmen_disease = on ', '\nratmen_disease = off')
        self.chances = [getattr(rules, n) for n in self.CHANCES]

    def table(self, path):
        return rules.table(rules.read_ini(str(path)))

    def write(self, folder, text, name='custom_rules.ini'):
        ini = Path(folder) / name
        ini.write_text(text, encoding='utf-8')
        return ini

    def spec(self, t):                                  # D139's bytes: the mode, N, the five weights
        return t[rules.G_SPEC_MODE], t[rules.G_SPEC_LAIRS], list(t[rules.G_SPEC_W:rules.G_SPEC_W + 5])

    def test_old_and_new_files_give_the_same_bytes(self):
        n = rules.G_SPEC_MODE
        self.assertEqual(n * 2, len(self.want[self.OLD]))
        self.assertEqual(rules.G_DUCK, n + 7)                # D144's two bytes after D139's seven
        self.assertEqual(rules.TABLE_SIZE, n + 9)
        old, user = self.table(self.FIX / self.OLD), self.table(self.FIX / self.USER)
        self.assertEqual((old[rules.G_DUCK], old[rules.G_DUCK_WINDOW]), (1, 6))   # D144: an older ini: on, 6 ticks
        self.assertEqual(old[:n].hex(), self.want[self.OLD])
        self.assertEqual(user[:n].hex(), self.want[self.USER])
        self.assertEqual(self.spec(old), (rules.SPEC_CHANCE, 8, [10] * 5))       # no special_items: the chance way
        self.assertEqual(self.spec(user), (rules.SPEC_CHANCE, 8, [100] * 5))
        self.assertEqual([user[at] for at in self.chances], [100] * 5)
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:          # the new file set to chance: the old bytes
            t = self.table(self.write(folder, self.source.replace(self.LAIRS, '\nspecial_items = chance ')))
            self.assertEqual(t[:n].hex(), self.want[self.OLD])
        base = bytes.fromhex(self.want[self.OLD])
        for name in ('custom_rules-default.ini', 'custom_rules.ini'):   # the lairs way: the chance bytes 100
            t = self.table(ROOT / name)
            self.assertEqual(t[rules.G_DISEASE], 1, name)              # B9: ratmen_disease = on
            self.assertEqual({i for i in range(n) if t[i] != base[i]}, set(self.chances) | {rules.G_DISEASE}, name)
            self.assertEqual([t[at] for at in self.chances], [100] * 5)
            self.assertEqual(self.spec(t), (rules.SPEC_LAIRS, 8, [10] * 5))

    def test_the_section_is_after_treasure_with_every_key(self):
        import configparser
        cp = configparser.ConfigParser(inline_comment_prefixes=(';',))
        cp.read_string(self.source)
        names = cp.sections()
        self.assertEqual(names.index('Special_items'), names.index('Treasure') + 1)
        self.assertEqual(set(cp.options('Special_items')), {'special_items', 'special_item_lairs', *rules.SPECIAL_KEYS})
        self.assertEqual((cp.get('Special_items', 'special_items'), cp.get('Special_items', 'special_item_lairs')), ('lairs', '8'))
        for key, old in rules.SPECIAL_KEYS.items():
            self.assertFalse(cp.has_option(old, key), key)
        self.assertEqual((ROOT / 'custom_rules.ini').read_text(encoding='utf-8'), (ROOT / 'custom_rules-default.ini').read_text(encoding='utf-8'))

    def test_a_key_in_both_places_the_new_section_wins(self):
        text = self.source.replace('[Treasure]\n', '[Treasure]\nrare_gem_chance = 55\n').replace(
            '[Rules]\n', '[Rules]\nsword_enchantment_chance = 66\n')
        w = rules.G_SPEC_W
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            t = self.table(self.write(folder, text))
            self.assertEqual((t[w + 4], t[w]), (10, 10))
            t = self.table(self.write(folder, text.replace('rare_gem_chance = 10 ', 'rare_gem_chance = 20 ')))
            self.assertEqual(t[w + 4], 20)
            older = text.replace('rare_gem_chance = 10 ', ';').replace('sword_enchantment_chance = 10 ', ';')
            t = self.table(self.write(folder, older))     # only in the old place: read there
            self.assertEqual((t[w + 4], t[w]), (55, 66))
            t = self.table(self.write(folder, older.replace(self.LAIRS, '\nspecial_items = chance ')))
            self.assertEqual((t[rules.G_GEM_CHANCE], t[rules.G_ENCH_CHANCE]), (55, 66))

    def test_unknown_key_and_bad_value_are_errors(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            text = self.source.replace(self.LAIRS, '\nrare_horse_chance = 5' + self.LAIRS)
            with self.assertRaisesRegex(rules.RulesError, r'\[Special_items\] rare_horse_chance: unknown setting'):
                rules.read_ini(self.write(folder, text))
            for bad in ('yes', 'none', '1'):
                text = self.source.replace(self.LAIRS, '\nspecial_items = ' + bad + ' ')
                with self.assertRaisesRegex(rules.RulesError, 'special_items'):
                    rules.read_ini(self.write(folder, text))
            for bad in ('25', '-1', 'six'):                # D139
                text = self.source.replace('special_item_lairs = 8 ', 'special_item_lairs = ' + bad + ' ')
                with self.assertRaisesRegex(rules.RulesError, 'special_item_lairs'):
                    rules.read_ini(self.write(folder, text))
            text = self.source.replace('rare_ring_chance = 10 ', 'rare_ring_chance = 101 ')
            with self.assertRaisesRegex(rules.RulesError, r'\[Special_items\] rare_ring_chance'):
                rules.read_ini(self.write(folder, text))

    def test_off_clears_exactly_the_five_on_bytes(self):
        n = rules.G_SPEC_MODE
        base = bytes.fromhex(self.want[self.OLD])
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            t = self.table(self.write(folder, self.source.replace(self.LAIRS, '\nspecial_items = off ')))
            self.assertEqual({i for i in range(n) if t[i] != base[i]}, set(rules.G_SPECIAL_ON))
            self.assertEqual([t[at] for at in rules.G_SPECIAL_ON], [0] * 5)
            self.assertEqual(self.spec(t), (0, 8, [10] * 5))
            lairs = self.table(self.write(folder, self.source))
            for mode in ('on', 'LAIRS'):                   # D139: on is lairs
                t = self.table(self.write(folder, self.source.replace(self.LAIRS, '\nspecial_items = ' + mode + ' ')))
                self.assertEqual(t, lairs, mode)
            t = self.table(self.write(folder, self.source.replace(self.LAIRS, '\n; ').replace('special_item_lairs = 8 ', ';')))
            self.assertEqual((t[:n], self.spec(t)), (base, (rules.SPEC_CHANCE, 8, [10] * 5)))   # no keys: chance, N 8
            t = self.table(self.write(folder, self.source.replace('special_item_lairs = 8 ', 'special_item_lairs = 0 ')
                                      .replace('rare_ring_chance = 10 ', 'rare_ring_chance = 0 ')))
            self.assertEqual((self.spec(t), t[rules.G_RING_CHANCE]), ((rules.SPEC_LAIRS, 0, [10, 10, 10, 0, 10]), 100))

    def test_speedrun_mode_has_no_special_items(self):
        before = bytes.fromhex(self.want['speedrun'])
        n = rules.G_SPEC_MODE
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            self.write(folder, self.source, 'custom_rules-default.ini')
            text = self.source.replace('speedrun_mode = off', 'speedrun_mode = on')
            self.assertNotEqual(text, self.source)
            t = self.table(self.write(folder, text))
        self.assertEqual([t[at] for at in rules.G_SPECIAL_ON], [0] * 5)
        self.assertEqual(t[rules.G_SPEC_MODE], 0)           # off, whatever the default file says (lairs)
        self.assertEqual({i for i in range(n) if t[i] != before[i]}, set(rules.G_SPECIAL_ON))


class ReviewFixes(unittest.TestCase):
    def test_speed_validation_and_packing(self):
        source = (ROOT / 'custom_rules-default.ini').read_text(encoding='utf-8')
        cases = [('70000', 650, False), ('65500', 650, False),
                 ('65535', 0, True), ('63585', 650, True),
                 ('63586', 650, False), ('100,65535,100,65535', 650, True),
                 ('2600,3250,3500,3750', 650, True)]
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            ini = Path(folder) / 'custom_rules.ini'
            for speed, per, valid in cases:
                with self.subTest(speed=speed, per=per):
                    text = source.replace('fight_cycles = 2600, 3250, 3500, 3750', f'fight_cycles = {speed}')
                    text = text.replace('additional_cycles_per_knight = 650', f'additional_cycles_per_knight = {per}')
                    ini.write_text(text, encoding='utf-8')
                    if valid:
                        r = rules.read_ini(ini)
                        packed = rules.table(r)
                        self.assertEqual(struct.unpack_from('<4H', packed, rules.G_FIGHT_CYCLES), r['fight_cycles'])
                        hook.make_savehook(packed)
                    else:
                        with self.assertRaisesRegex(rules.RulesError, 'fight_cycles'):
                            rules.read_ini(ini)
            ini.write_text(source.replace('default_cycles = 4000', 'default_cycles = 70000'), encoding='utf-8')
            with self.assertRaisesRegex(rules.RulesError, 'default_cycles'):
                rules.read_ini(ini)

    @unittest.skipUnless(os.name == 'nt', 'Windows batch launcher')
    def test_start_requires_rebuild_after_lock_deletion(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            game = Path(folder)
            shutil.copyfile(ROOT / 'Start.bat', game / 'Start.bat')
            (game / 'tools').mkdir()                          # D82: Start.bat sets the sound with tools\set_sound.bat
            for name in ('set_sound.bat', 'find_python.bat'):
                shutil.copyfile(ROOT / 'tools' / name, game / 'tools' / name)
            (game / 'CUSTOM_RULES.FLG').write_text('custom rules\n')
            (game / 'music.conf').write_text('[midi]\nmididevice = default\n')
            # Only discovery is exercised: MOONSTONE_NOLAUNCH prevents executing this stub.
            (game / 'dosbox-x.exe').write_bytes(b'')
            env = dict(os.environ, MOONSTONE_NOLAUNCH='1', PATH=str(game) + os.pathsep + os.environ.get('PATH', ''))
            for rating in (18, 16):
                # Simulate flags and binaries left behind by a higher installed rating.
                (game / 'MAIN.EXE').write_bytes(bytes([rating]))
                (game / 'PARENTAL.LCK').write_text(f'{rating} highest rating\n')
                (game / 'PARENTAL.LCK').unlink()
                result = subprocess.run(['cmd', '/d', '/c', str(game / 'Start.bat')],
                                        input='\n', text=True, capture_output=True, env=env, timeout=10)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('no PARENTAL.LCK: K12', result.stdout)
                self.assertEqual(rules.age_limit(game), 12)
            # A successfully rebuilt K12 installation has a lock again.
            (game / 'PARENTAL.LCK').write_text('12 highest rating\n')
            (game / '_fixes' / 'rules').mkdir(parents=True)
            for name in ('MAIN.EXE', 'SAVEHOOK.COM'):
                (game / name).write_bytes(b'K12')
                (game / '_fixes' / 'rules' / name).write_bytes(b'K12')
            result = subprocess.run(['cmd', '/d', '/c', str(game / 'Start.bat')],
                                    input='\n', text=True, capture_output=True, env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_assembly(self):
        self.assertLess(len(hook.make_savehook()), 0xff00)

    @unittest.skipUnless(os.environ.get('DOSBOX_X'), 'set DOSBOX_X to run the DOS routine harness')
    def test_generated_routines_in_dosbox(self):
        labels = {}
        original_build = hook.Asm.build

        def capture(assembler):
            labels.update(assembler.labels)
            return original_build(assembler)

        with patch.object(hook.Asm, 'build', capture):
            code = hook.make_savehook()
        a = hook.Asm(0x100)
        a.b(code)
        a.labels.update(labels)
        a.label('test_entry')
        # Keep game data in a separate, cleared segment; leave CS and the stack intact.
        a.b(0x0e, 0x58, 0x05, 0x00, 0x10, 0x8e, 0xd8, 0x8e, 0xc0,
            0x33, 0xff, 0x33, 0xc0, 0xb9, 0x00, 0x80, 0xfc, 0xf3, 0xab)

        def set_word(addr, value, cs=False):
            if cs:
                a.b(0x2e)
            a.b(0xc7, 0x06, struct.pack('<HH', addr, value))

        def setting(offset, value):
            a.b(0x2e, 0xc6, 0x06, struct.pack('<H', labels['rules_table'] + offset), value)

        def expect_word(addr, value, cs=False):
            if cs:
                a.b(0x2e)
            a.b(0x81, 0x3e, struct.pack('<HH', addr, value), 0x74, 0x03)
            a.near(0xe9, 'test_fail')

        # Blood stays on at K16, but every death mode must replace a pending beheading.
        for rating in (12, 16, 18):
            setting(rules.G_AGE, rating)
            for mode in rules.DEATHS.values():
                setting(rules.G_DEATHS, mode)
                for pending in (hook.BEHEADING, hook.PLAIN_DEATH, 0, 0xffff):
                    set_word(hook.GORE, 0)
                    set_word(0x783a, pending)
                    a.near(0xe8, 'pick_death')
                    expected = (hook.PLAIN_DEATH if pending == hook.BEHEADING and
                                (rating < 18 or mode == rules.DEATHS['off']) else pending)
                    expect_word(0x783a, expected)
                    expect_word(hook.GORE, int(mode == rules.DEATHS['off']))

        # Replay a curse after changing the shared RNG: same roll and stream advancement.
        setting(rules.G_FATE, 1)
        stream = labels['fate_state'] + 6
        for shared in (123, 45678):
            set_word(stream, 1234, cs=True)
            set_word(hook.RANDOM_STATE, shared)
            a.near(0xe8, 'curse_roll')
            if shared == 123:
                a.b(0x2e, 0xa3); a.word('test_roll')
            else:
                a.b(0x2e, 0x3b, 0x06); a.word('test_roll')
                a.b(0x74, 0x03); a.near(0xe9, 'test_fail')
            expect_word(stream, (1234 * 25173 + 13849) & 0xffff, cs=True)
        for offset in (0, 2, 4):
            expect_word(labels['fate_state'] + offset, 0, cs=True)
        # With fate off, the wrapper must behave like game_roll and leave fate state alone.
        setting(rules.G_FATE, 0)
        set_word(hook.RANDOM_STATE, 4321)
        a.near(0xe8, 'game_roll')
        a.b(0x2e, 0xa3); a.word('test_roll')
        set_word(hook.RANDOM_STATE, 4321)
        a.near(0xe8, 'curse_roll')
        a.b(0x2e, 0x3b, 0x06); a.word('test_roll')
        a.b(0x74, 0x03); a.near(0xe9, 'test_fail')
        expect_word(stream, (1234 * 25173 + 13849) & 0xffff, cs=True)
        # Exercise both actual interrupt handlers, including their return frames.
        setting(rules.G_FATE, 1)
        state = 1234
        set_word(stream, state, cs=True)
        for limit in (100, 255):                         # always cursed, never cursed (signed -1)
            setting(rules.G_HASTE_CURSE, limit)
            setting(rules.G_WYRM_CURSE, limit)
            set_word(0x77e8, 0x6c9e)
            set_word(hook.DRAGON_RECORD + 0x46, 0x6d00)
            for name in ('haste', 'wyrm'):
                a.b(0x9c, 0x0e)                         # pushf / push cs
                a.near(0xe8, 'test_' + name + '_frame')
                state = (state * 25173 + 13849) & 0xffff
                expect_word(stream, state, cs=True)
            expect_word(0xcca2, 1 if limit == 100 else 0xffff)
            expect_word(hook.DRAGON_RECORD + 0x46, 0x6c9e if limit == 100 else 0x6d00)
        # Checked save modes must checkpoint even with fate disabled.
        setting(rules.G_FATE, 0)
        for mode in (hook.AUTO_ONLY, hook.NO_SAVES):
            setting(rules.G_SAVE_MODE, mode)
            a.near(0xe8, 'curse_roll')
        expect_word(labels['token'] + 2, 2, cs=True)
        a.b(0x0e, 0x1f, 0xba); a.word('test_pass_text')
        a.short(0xeb, 'test_print')
        a.label('test_fail')
        a.b(0x0e, 0x1f, 0xba); a.word('test_fail_text')
        a.label('test_print')
        a.b(0xb4, 0x09, 0xcd, 0x21, 0xb8, 0x00, 0x4c, 0xcd, 0x21)
        for name in ('haste', 'wyrm'):
            a.label('test_' + name + '_frame')
            a.b(0x55, 0x8b, 0xec, 0x53)                  # push bp / mov bp, sp / push bx
            a.near(0xe9, 'rules_' + name + '_curse')
        a.label('test_pass_text'); a.b(b'PASS$')
        a.label('test_fail_text'); a.b(b'FAIL$')
        a.label('test_roll'); a.b(0, 0)
        harness = bytearray(a.build())
        struct.pack_into('<H', harness, 1, (a.labels['test_entry'] - 0x103) & 0xffff)   # a near jump wraps in 64 KB
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            game = Path(folder)
            (game / 'REVIEW.COM').write_bytes(harness)
            (game / 'test.conf').write_text('[sdl]\nfullscreen=false\noutput=surface\n[cpu]\ncycles=fixed 20000\n')
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run([os.environ['DOSBOX_X'], '-fastlaunch', '-conf', str(game / 'test.conf'),
                            '-c', f'mount c "{game}"', '-c', 'c:',
                            '-c', 'review.com > result.txt', '-c', 'exit'],
                           cwd=game, startupinfo=startup, capture_output=True, timeout=40, check=True)
            self.assertEqual((game / 'RESULT.TXT').read_text().strip(), 'PASS')


class SoundPrograms(unittest.TestCase):
    """The table the effects are built from without the Amiga disks (D66), against the files of the release."""
    @classmethod
    def setUpClass(cls):
        import json
        cls.table = json.loads((ROOT / 'tools' / 'sound_programs.json').read_text(encoding='utf-8'))

    def test_every_effect_program_is_in_the_table(self):
        import patches
        self.assertEqual(sorted(int(p) for p in self.table['programs']), sorted(patches.AMIGA_PROGRAMS))

    def test_steps_are_well_formed(self):
        instruments = self.table['instruments']
        for p, program in self.table['programs'].items():
            self.assertIsInstance(program['loops'], bool, p)
            self.assertTrue(program['steps'], p)
            for frames, volume, rate, start in program['steps']:
                self.assertGreaterEqual(frames, 1, p)
                self.assertTrue(0 <= volume <= 63, p)
                self.assertGreater(rate, 0, p)
                self.assertTrue(start is None or start == -1 or str(start) in instruments, f'{p}: {start}')

    def test_loops_go_back_to_a_step_of_a_program_that_begins_again(self):
        # D67: "loop" is the step a program goes back to after its last one; the sounds the game plays on a
        # channel of their own are such loops
        import patches
        programs = self.table['programs']
        for p, program in programs.items():
            if 'loop' in program:
                self.assertTrue(program['loops'], p)
                self.assertIsInstance(program['loop'], int, p)
                self.assertTrue(0 <= program['loop'] < len(program['steps']), p)
                start = program['steps'][program['loop']][3]
                self.assertTrue(start is not None and start >= 0, f'{p}: the round that repeats starts a note')
        for sound, channel in patches.AMIGA_FIXED.items():
            self.assertIn('loop', programs[str(patches.amiga_program(sound))], sound)
            self.assertIn(channel, range(4), sound)
        self.assertEqual(sorted(int(p) for p, x in programs.items() if 'loop' in x),
                         [27, 29] + list(range(34, 43)) + [62, 78, 79, 80])

    def test_instruments_come_from_the_dos_game_or_the_sounds_folder(self):
        import wave
        game_files = (ROOT / 'setup' / 'gog-dos-1.json').read_text(encoding='utf-8')
        for k, x in self.table['instruments'].items():
            self.assertLessEqual(('dos' in x) + ('file' in x), 1, k)
            if 'dos' in x:
                self.assertIn(f'"SAMPLES/{x["dos"]}"', game_files, k)
            elif 'file' in x:
                with wave.open(str(ROOT / 'sounds' / x['file']), 'rb') as w:
                    self.assertEqual(w.getnchannels(), 1, x['file'])
                    self.assertGreaterEqual(w.getnframes(), x['at'] + x['n'], f'{x["file"]} is long enough for instrument {k}')
            if x:
                self.assertTrue(x['at'] >= 0 and x['n'] > 0, k)

    def test_the_henge_thunder_has_its_substitute(self):
        # D95: program 157 plays instrument 130 (the Amiga's he.a), which without the disks is sounds/thunder.wav
        import wave
        self.assertEqual(self.table['programs']['157']['steps'][0][3], 130)
        self.assertEqual(self.table['instruments']['130'], {'file': 'thunder.wav', 'at': 0, 'n': 12012})
        with wave.open(str(ROOT / 'sounds' / 'thunder.wav'), 'rb') as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()), (1, 1, 7830, 12012))

    def test_every_substitute_has_its_source_listed(self):
        sources = (ROOT / 'sounds' / 'SOURCES.md').read_text(encoding='utf-8')
        for path in (ROOT / 'sounds').glob('*.wav'):
            self.assertIn(f'`{path.name}`', sources, f'{path.name} is not in sounds/SOURCES.md')

def has_numpy():
    try:
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def tune_test_module():
    """A module of our own for the tune player (D87): three square-wave samples and two patterns that use every
    command of the Amiga's routine once. No Amiga data."""
    def sample(words, vol, loop=0, replen=1, fine=0):
        return struct.pack('>22sHBBHH', b'square', words, fine, vol, loop, replen)
    def square(words, half):
        return bytes((0x40 if (i // half) % 2 == 0 else 0xc0) for i in range(2 * words))
    heads = [sample(64, 64, 8, 16), sample(32, 40), sample(16, 48, fine=3)] + [sample(0, 0)] * 28
    data = [square(64, 4), square(32, 8), square(16, 2)]
    def note(smp=0, period=0, cmd=0, par=0):
        return bytes([(smp & 0xf0) | period >> 8, period & 0xff, (smp & 15) << 4 | cmd, par])
    def pattern(rows):
        out = bytearray(1024)
        for r, row in rows.items():
            for c, n in row.items():
                out[16 * r + 4 * c:16 * r + 4 * c + 4] = n
        return bytes(out)
    p0 = pattern({0: {0: note(1, 428, 0xf, 3), 1: note(2, 320, 0xc, 0x20)},       # speed 3; volume 20h
                  1: {0: note(cmd=0xa, par=0x04), 1: note(cmd=0xa, par=0x30)},     # volume slides down and up
                  2: {0: note(cmd=1, par=0x10), 1: note(cmd=2, par=0x08)},         # slides up and down
                  3: {0: note(0, 214, 3, 0x20), 1: note(cmd=4, par=0x41)},         # slide to a note; vibrato
                  4: {0: note(cmd=3), 1: note(cmd=0, par=0x37)},                   # the slide goes on; arpeggio
                  5: {0: note(cmd=0xd, par=0x05), 2: note(1, 428, 0xe, 1), 3: note(3, 214, 5, 0x11)}})   # break
    p1 = pattern({0: {2: note(2, 340, 0xc, 0x50), 3: note(cmd=0xf)},               # volume over 40h; speed 0
                  1: {1: note(cmd=0xb, par=1), 2: note(cmd=0xd)}})                 # a jump and a break on one row
    orders = bytes([0, 1]) + bytes(126)
    return b'test'.ljust(20, b'\0') + b''.join(heads) + bytes([2, 127]) + orders + b'M.K.' + p0 + p1 + b''.join(data)


class AmigaTunes(unittest.TestCase):
    """D87: the Amiga intro and ending tunes from the SoundFont. The player is checked with a module made here."""

    def test_player_steps_every_command_as_the_amiga_routine(self):
        import amiga_module
        ticks, loop, rows, player = amiga_module.play_through(tune_test_module(), amiga_module.equal_periods())
        self.assertEqual((len(ticks), loop, player.unmodelled), (24, 6, []))
        # the rows: three ticks each (F03); the break's parameter is ignored; the jump and the break on one row
        # cancel each other, and the jump's order is taken without a break: order 0 goes on from its row 2
        self.assertEqual(rows, [(0, 0, 0), (3, 0, 1), (6, 0, 2), (9, 0, 3), (12, 0, 4), (15, 0, 5), (18, 1, 0), (21, 1, 1)])
        periods = [[t[c][2] for t in ticks] for c in range(4)]
        volumes = [[t[c][3] for t in ticks] for c in range(4)]
        self.assertEqual(periods[0], [428] * 7 + [412, 396, 396, 364, 332, 332, 300, 268] + [268] * 9)
        # slide down; the vibrato's two ticks; the arpeggio from the table's 321 (+3 and +7 notes), whose last
        # period stays in the register on the next row's tick
        self.assertEqual(periods[1], [320] * 7 + [328, 336, 336, 336, 337, 337, 270, 214, 214] + [336] * 8)
        self.assertEqual(periods[2], [0] * 15 + [428] * 3 + [340] * 6)
        self.assertEqual(periods[3], [0] * 15 + [214] * 9)
        self.assertEqual(volumes[0], [64, 64, 64, 64, 60, 56] + [56] * 18)
        # C20 sets the register only: the slide goes up from the sample's own 40
        self.assertEqual(volumes[1], [32, 32, 32, 32, 43, 46] + [46] * 18)
        self.assertEqual(volumes[2], [0] * 15 + [64] * 9)               # C50 is taken as 40h
        self.assertEqual(volumes[3], [0] * 15 + [48] * 9)               # the finetune byte is not volume
        starts = {(i, c): t[c][1] for i, t in enumerate(ticks) for c in range(4) if t[c][0]}
        # (start byte, words, loop's start byte, loop's words): a looped sample ends at its loop's end
        self.assertEqual(starts, {(0, 0): (0, 24, 16, 16), (0, 1): (128, 32, 128, 1), (15, 2): (0, 24, 16, 16),
                                  (15, 3): (192, 16, 192, 1), (18, 2): (128, 32, 128, 1)})

    def test_player_clears_each_samples_first_long(self):
        import amiga_module
        mod = amiga_module.Module(tune_test_module())
        self.assertEqual([mod.mem[at:at + 5].hex() for at in (0, 128, 192)], ['00000000c0', '0000000040', '0000000040'])
        self.assertEqual((mod.size, mod.songlen, len(mod.patterns)), (224, 2, 2048))

    def test_player_says_what_it_does_not_model(self):
        import amiga_module
        data = bytearray(tune_test_module())
        data[1084 + 16 + 2] = 0x20                          # row 1, channel 0: sample 2 without a note
        ticks, loop, rows, player = amiga_module.play_through(bytes(data), amiga_module.equal_periods())
        self.assertTrue(any('another sample' in line for line in player.unmodelled))
        data = bytearray(tune_test_module())
        data[1084 + 4:1084 + 6] = b'\x00\x7f'              # channel 1 starts at period 127: its arpeggio's seventh
                                                            # note up is past the table's end
        ticks, loop, rows, player = amiga_module.play_through(bytes(data), amiga_module.equal_periods())
        self.assertTrue(any('past the table' in line for line in player.unmodelled))

    def test_no_table_of_periods_is_kept(self):
        import amiga_module
        self.assertEqual(len(amiga_module.equal_periods()), amiga_module.PERIOD_WORDS)
        self.assertIsNone(amiga_module.find_periods(bytes(4000)))
        table = struct.pack('>37H', *amiga_module.equal_periods())
        self.assertIsNone(amiga_module.find_periods(bytes(100) + table + bytes(100)))    # not the Amiga's own table

    # --- the tune module INTR.EXE loads -----------------------------------------------------------------------------
    S, MOD = 0x1000, 0x1000 + 0x0492                        # INTR's first segment as loaded; the tune module's segment
    REGS = dict(AX=0x1234, BX=0x2345, CX=0x3456, DX=0x4567, SI=0x5678, DI=0x6789, BP=0x789a, DS=0x4000, ES=0x5000)

    def machine(self, module):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INSN
        from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
        import patches
        uc = Uc(UC_ARCH_X86, UC_MODE_16)
        uc.mem_map(0, 0x100000)
        uc.mem_write(self.MOD * 16, module)
        code, relocs = patches._intr_skip_code()            # K9's cave, relocated as DOS would
        code = bytearray(code)
        for r in relocs:
            code[r:r + 2] = ((int.from_bytes(code[r:r + 2], 'little') + self.S) & 0xffff).to_bytes(2, 'little')
        self.assertLessEqual(len(code), 258)                # the room behind the largest tune module
        uc.mem_write(self.MOD * 16 + patches.INTR_CAVE_OFF, bytes(code))
        uc.mem_write(self.S * 16 + 0x0f9e, bytes([0xea, 0x00, 0x23]) + self.MOD.to_bytes(2, 'little') + b'\xc3')
        uc.mem_write(self.S * 16 + patches.KEY_STATE_TABLE, b'\xff' * 128)      # no key held
        self.outs, self.reads, self.press_at = [], [0], None
        def port_in(uc, port, size, user):
            if port == 0x3da:                               # each retrace: one read outside it, one inside
                self.reads[0] += 1
                if self.reads[0] == self.press_at:          # a key that skips goes down: the keyboard handler notes it
                    uc.mem_write(self.MOD * 16 + patches.INTR_CAVE_OFF + patches._intr_cave()[2]['latch'], b'\x01')
                return 8 if self.reads[0] % 2 == 0 else 0
            return 0xfe
        uc.hook_add(UC_HOOK_INSN, lambda uc, port, size, value, user: self.outs.append((port, value & 0xff)),
                    None, 1, 0, UC_X86_INS_OUT)
        uc.hook_add(UC_HOOK_INSN, port_in, None, 1, 0, UC_X86_INS_IN)
        return uc

    def run_code(self, uc, cs, ip, stack, stops, **regs):
        """Run from cs:ip with `stack` (words) on the stack until one of `stops` (linear) -> where it stopped."""
        import unicorn.x86_const as x
        for name, value in dict(self.REGS, **regs).items():
            uc.reg_write(getattr(x, 'UC_X86_REG_' + name), value)
        sp = 0xff00 - 2 * len(stack)
        uc.reg_write(x.UC_X86_REG_SS, 0x6000); uc.reg_write(x.UC_X86_REG_SP, sp)
        uc.mem_write(0x6000 * 16 + sp, b''.join(v.to_bytes(2, 'little') for v in stack))
        uc.reg_write(x.UC_X86_REG_CS, cs)
        for stop in stops:
            uc.mem_write(stop, b'\xf4')
        uc.emu_start(cs * 16 + ip, 0, count=200000)
        at = uc.reg_read(x.UC_X86_REG_CS) * 16 + uc.reg_read(x.UC_X86_REG_IP) - 1      # the hlt it ran into
        self.assertIn(at, stops)
        return at, {name: uc.reg_read(getattr(x, 'UC_X86_REG_' + name)) for name in list(self.REGS) + ['SP']}

    def int60(self, uc, ah):
        """int 60h with ah, as INTR.EXE calls its tune module -> (bytes written to the ports, the registers after)."""
        del self.outs[:]
        back = self.S * 16 + 0x0050
        _, regs = self.run_code(uc, self.MOD, 0, [0x0050, self.S, 0x0202], {back}, AX=ah << 8 | 0x34)
        return list(self.outs), regs

    def wait(self, uc):
        """One call of INTR.EXE's retrace wait (0000:0F9E) -> (retraces waited, where it came out, registers)."""
        before = self.reads[0]
        at, regs = self.run_code(uc, self.S, 0x0f9e, [0x0050], {self.S * 16 + 0x0050, self.S * 16 + 0x00d1})
        return (self.reads[0] - before) // 2, at - self.S * 16, regs

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_tune_module_sends_the_notes(self):
        import amiga_module, make_amiga_music, patches
        for name, tune in (('intro', 'ATUNE1.BIN'), ('ending', 'ATUNE6.BIN')):
            with self.subTest(tune=name):
                self.assertEqual(make_amiga_music.TUNE_FILES[name], tune)
                module = make_amiga_music.tune_module(name)
                self.assertEqual(module[0], 0x1e)           # push ds: what K9's skip knows a loaded module by
                self.assertEqual(int.from_bytes(module[1:3], 'little'), patches.INTR_TUNE_SIGN)
                self.assertLess(len(module), 0x200)
                uc = self.machine(module)
                left, right = amiga_module.TUNE_KEYS[name]
                a, b = amiga_module.TUNE_CHANNELS
                self.assertEqual((a, b, amiga_module.TUNE_PRESET, patches.AMIGA_BANK), (10, 11, 3, 100))
                pans = amiga_module.TUNE_PANS
                self.assertEqual((pans[0] + pans[1], pans[1] - pans[0]), (127, 95))       # three quarters of 127
                start = [(0x331, 0x3f)] + [(0x330, v) for v in (
                    0xb0 | a, 0, 100, 0xc0 | a, 3, 0xb0 | a, 7, amiga_module.TUNE_VOLUME, 0xb0 | a, 10, pans[0],
                    0xb0 | b, 0, 100, 0xc0 | b, 3, 0xb0 | b, 7, amiga_module.TUNE_VOLUME, 0xb0 | b, 10, pans[1],
                    0x90 | a, left, 0x7f, 0x90 | b, right, 0x7f)]
                kept = dict(self.REGS, SP=0xff00)
                outs, regs = self.int60(uc, 0)
                self.assertEqual(outs, start)
                self.assertEqual(regs, dict(kept, AX=0x0034))
                outs, regs = self.int60(uc, 1)              # the timer's tick: nothing is sent
                self.assertEqual((outs, regs), ([], dict(kept, AX=0x0134)))
                outs, regs = self.int60(uc, 2)
                self.assertEqual(outs, [(0x330, v) for v in (0x80 | a, left, 0, 0x80 | b, right, 0)])
                self.assertEqual(regs, dict(kept, AX=0x0234))
                self.assertEqual(self.int60(uc, 7)[0], [])
        self.assertEqual(len({k for keys in amiga_module.TUNE_KEYS.values() for k in keys}), 4)
        self.assertGreaterEqual(min(k for keys in amiga_module.TUNE_KEYS.values() for k in keys), 15)   # FluidSynth's root keys

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_pictures_are_paced_only_for_our_tune_module(self):
        import make_amiga_music, patches
        dos_tune = bytes.fromhex('1e538ccb8edb80fc') + bytes(64)        # how the game's tune modules begin
        uc = self.machine(dos_tune)
        waits = [self.wait(uc) for _ in range(20)]
        self.assertEqual([w[0] for w in waits], [1] * 20)               # the DOS tunes: one retrace a call, as before
        self.assertEqual({w[1] for w in waits}, {0x50})
        self.assertEqual(bytes(uc.mem_read(self.MOD * 16, len(dos_tune))), dos_tune)
        uc = self.machine(bytes(64))                                    # no module loaded yet
        self.assertEqual([self.wait(uc)[0] for _ in range(5)], [1] * 5)
        uc = self.machine(make_amiga_music.tune_module('intro', (2, 5, 0, 1)))
        self.assertEqual([self.wait(uc)[0] for _ in range(5)], [1] * 5)     # loaded, not playing yet: as the game
        self.int60(uc, 0)
        got = [self.wait(uc) for _ in range(20)]
        self.assertEqual([w[0] for w in got], [1, 1, 2, 1, 2] * 4)      # 7 retraces for 5 calls: 70 Hz -> 50 Hz
        kept = dict(self.REGS, SP=0xff00)
        for _, at, regs in got:                                         # the wait changes al and dx only, as the game's
            self.assertEqual((at, dict(regs, AX=regs['AX'] & 0xff00, DX=0)), (0x50, dict(kept, AX=0x1200, DX=0)))
        self.int60(uc, 2)                                               # stopped: as the game again
        self.assertEqual([self.wait(uc)[0] for _ in range(5)], [1] * 5)
        uc = self.machine(make_amiga_music.tune_module('intro', (0, 1, 0, 1)))
        self.int60(uc, 0)
        self.assertEqual([self.wait(uc)[0] for _ in range(6)], [1] * 6)
        uc = self.machine(make_amiga_music.tune_module('intro', (1, 1, 0, 1)))
        self.int60(uc, 0)
        self.assertEqual([self.wait(uc)[0] for _ in range(6)], [2] * 6)
        for bad in ((3, 2, 0, 1), (1, 2, 5, 5), (1, 2, 1, 200)):
            with self.assertRaises(ValueError):
                make_amiga_music.tune_module('intro', bad)

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_tick_slows_the_bios_clock_while_the_tune_plays(self):
        import make_amiga_music, patches
        divider = self.REGS['DS'] * 16 + patches.INTR_TIMER_DIVIDER     # the tick is called with INTR.EXE's ds
        def bios_ticks(uc, ticks):
            """INTR.EXE's timer handler, `ticks` times: the module's tick, then one off the count; at 0 the BIOS
            gets its tick and the count is 3 again."""
            n = 0
            for _ in range(ticks):
                self.assertEqual(self.int60(uc, 1)[0], [])
                left = int.from_bytes(uc.mem_read(divider, 2), 'little') - 1
                if left == 0:
                    n, left = n + 1, 3
                uc.mem_write(divider, left.to_bytes(2, 'little'))
            return n
        uc = self.machine(make_amiga_music.tune_module('intro', (0, 1, 11, 36)))
        uc.mem_write(divider, (3).to_bytes(2, 'little'))
        self.assertEqual(bios_ticks(uc, 108), 36)                       # not playing: every third tick, as the game
        self.int60(uc, 0)
        self.assertEqual(bios_ticks(uc, 108), 25)                       # 11 of every 36 held back: 1.44 times slower
        self.assertEqual(bios_ticks(uc, 108), 25)
        self.int60(uc, 2)
        self.assertEqual(bios_ticks(uc, 108), 36)
        self.int60(uc, 0)
        uc.mem_write(divider, (500).to_bytes(2, 'little'))              # not INTR.EXE's count: left alone
        for _ in range(72):
            self.int60(uc, 1)
        self.assertEqual(int.from_bytes(uc.mem_read(divider, 2), 'little'), 500)

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_skip_keys_work_with_our_tune_module(self):
        import make_amiga_music, patches
        uc = self.machine(make_amiga_music.tune_module('intro', (1, 1, 0, 1)))
        self.int60(uc, 0)
        self.assertEqual([self.wait(uc)[:2] for _ in range(2)], [(2, 0x50)] * 2)
        self.press_at = self.reads[0] + 4                               # a key goes down during a call's second retrace
        self.assertEqual(self.wait(uc)[:2], (2, 0x50))
        n, at, regs = self.wait(uc)                                     # the next call leaves through the intro's
        self.assertEqual((n, at, regs['DS'], regs['SP']),               # own shutdown, as K9 does for the DOS tunes
                         (0, 0x00d1, self.S + patches.INTR_DATA_SEG, patches.INTR_STACK_TOP))

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_our_tune_starts_in_the_first_sequence_as_on_the_amiga(self):
        """The first sequence's stage test (0000:0D76) calls the cave: at stage 4 our module's tune starts there; a
        DOS tune (or none) is left to start at 0000:008B, as the game does, and the registers are kept."""
        from unicorn import UC_HOOK_INTR
        import unicorn.x86_const as x
        import make_amiga_music, patches
        code, relocs, entries = patches._intr_cave()
        self.assertEqual(patches._intr_skip_code(), (code, relocs))
        dos_tune = bytes.fromhex('1e538ccb8edb80fc') + bytes(64)
        for module, stage, starts in ((make_amiga_music.tune_module('intro'), 4, [0x0034]),
                                      (make_amiga_music.tune_module('intro'), 3, []),
                                      (make_amiga_music.tune_module('intro'), 5, []),
                                      (dos_tune, 4, []), (bytes(64), 4, [])):
            with self.subTest(module=module[:3].hex(), stage=stage):
                uc = self.machine(module)
                calls = []
                uc.hook_add(UC_HOOK_INTR, lambda uc, n, user: calls.append((n, uc.reg_read(x.UC_X86_REG_AX))))
                uc.mem_write(self.REGS['DS'] * 16 + patches.INTR_STAGE, stage.to_bytes(2, 'little'))
                back = self.S * 16 + patches.INTR_STAGE_TEST + 5            # after the far call
                at, regs = self.run_code(uc, self.MOD, patches.INTR_CAVE_OFF + entries['stage'],
                                         [patches.INTR_STAGE_TEST + 5, self.S], {back})
                self.assertEqual([ax for n, ax in calls if n == 0x60], starts)
                self.assertEqual([n for n, ax in calls if n != 0x60], [])
                self.assertEqual(regs, dict(self.REGS, SP=0xff00))

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_second_pace_takes_over_after_its_ticks(self):
        import make_amiga_music, patches
        divider = self.REGS['DS'] * 16 + patches.INTR_TIMER_DIVIDER
        def ticks(uc, k):                                               # INTR.EXE's timer -> BIOS ticks passed on
            n = 0
            for _ in range(k):
                self.int60(uc, 1)
                left = int.from_bytes(uc.mem_read(divider, 2), 'little') - 1
                if left == 0:
                    n, left = n + 1, 3
                uc.mem_write(divider, left.to_bytes(2, 'little'))
            return n
        uc = self.machine(make_amiga_music.tune_module('intro', (0, 1, 0, 1, 72, 1, 1, 11, 36)))
        uc.mem_write(divider, (3).to_bytes(2, 'little'))
        self.assertEqual([self.wait(uc)[0] for _ in range(3)], [1] * 3)     # not playing
        self.int60(uc, 0)
        self.assertEqual([self.wait(uc)[0] for _ in range(3)], [1] * 3)     # the first pace: none
        self.assertEqual(ticks(uc, 71), 23)                             # every third tick, as the game
        self.assertEqual([self.wait(uc)[0] for _ in range(3)], [1] * 3)
        self.assertEqual(ticks(uc, 1), 1)                               # the 72nd: the second pace takes over
        self.assertEqual([self.wait(uc)[0] for _ in range(3)], [2] * 3)
        self.assertEqual((ticks(uc, 108), ticks(uc, 108)), (25, 25))    # 11 of every 36 held back
        self.int60(uc, 0)                                               # a start while playing: no change
        self.assertEqual([self.wait(uc)[0] for _ in range(2)], [2] * 2)
        self.int60(uc, 2)
        self.int60(uc, 0)                                               # started again: the first pace again
        self.assertEqual([self.wait(uc)[0] for _ in range(2)], [1] * 2)
        self.assertEqual(make_amiga_music.paces((2, 5, 41, 91)), ((2, 5, 41, 91), 0, (2, 5, 41, 91)))
        for bad in ((1, 2, 0, 1, 70000, 1, 1, 0, 1), (1, 2, 0, 1, 5, 3, 2, 0, 1), (1, 2, 0, 1, 5)):
            with self.assertRaises(ValueError):
                make_amiga_music.tune_module('intro', bad)

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_a_second_start_while_the_tune_plays_does_nothing(self):
        import make_amiga_music, patches
        uc = self.machine(make_amiga_music.tune_module('intro', (1, 2, 0, 1)))
        first, regs = self.int60(uc, 0)
        self.assertEqual(len(first), 1 + 22 + 6)                       # UART mode, the setup and the notes
        self.assertEqual([self.wait(uc)[0] for _ in range(3)], [1, 2, 1])
        again, regs2 = self.int60(uc, 0)                                # the game's own start at 0000:008B
        self.assertEqual((again, regs2), ([], regs))
        self.assertEqual([self.wait(uc)[0] for _ in range(3)], [2, 1, 2])  # the pace goes on where it was
        self.int60(uc, 2)
        self.assertEqual(self.int60(uc, 0)[0], first)                   # stopped: a start starts again

    def key(self, uc, scan, down=True, mode=0):
        """INTR.EXE's keyboard handler (0000:4774) gets `scan` (pressed or released) and stores it through the cave."""
        import patches
        uc.mem_write(self.S * 16 + patches.INTR_MODE, mode.to_bytes(2, 'little'))
        back = self.S * 16 + patches.INTR_KEY_STORE + 5
        at, regs = self.run_code(uc, self.MOD, patches.INTR_CAVE_OFF + patches._intr_cave()[2]['key'],
                                 [patches.INTR_KEY_STORE + 5, self.S], {back},
                                 AX=(0x00 if down else 0xff) << 8 | scan, BX=scan)
        self.assertEqual(regs, dict(self.REGS, AX=regs['AX'], BX=scan, SP=0xff00))     # ds kept
        return uc.mem_read(self.S * 16 + patches.KEY_STATE_TABLE + scan, 1)[0]

    def noted(self, uc):
        import patches
        return uc.mem_read(self.MOD * 16 + patches.INTR_CAVE_OFF + patches._intr_cave()[2]['latch'], 1)[0]

    def frame(self, uc):
        """The start of a frame of the scenes' frame loops (0000:021F, its tick set at 0228) -> where it went."""
        import patches
        back = self.S * 16 + patches.INTR_FRAME_SET + 5
        at, regs = self.run_code(uc, self.MOD, patches.INTR_CAVE_OFF + patches._intr_cave()[2]['frame'],
                                 [patches.INTR_FRAME_SET + 5, self.S], {back, self.S * 16 + 0x00d1}, AX=500)
        return at - self.S * 16, regs

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_keyboard_handler_notes_a_fresh_press(self):
        """The intro skips with any key but Ctrl, Alt, Shift and the lock keys, the ending with Enter, Space or Esc; a key's repeat
        (a press while it is held) and a release are not a press; the key state table is kept as the game keeps it."""
        import make_amiga_music
        for mode, keys in ((0, {0x1c: 1, 0x39: 1, 0x01: 1, 0x1e: 1, 0x3b: 1, 0x4d: 1, 0x1d: 0, 0x38: 0, 0x2a: 0, 0x36: 0, 0x3a: 0, 0x45: 0, 0x46: 0}),
                           (0x0101, {0x1c: 1, 0x39: 1, 0x01: 1, 0x1e: 0, 0x3b: 0, 0x4d: 0, 0x1d: 0, 0x38: 0})):
            for scan, skips in keys.items():
                with self.subTest(mode=mode, scan=hex(scan)):
                    uc = self.machine(make_amiga_music.tune_module('intro'))
                    self.assertEqual(self.key(uc, scan, down=False, mode=mode), 0xff)   # a release: nothing noted
                    self.assertEqual(self.noted(uc), 0)
                    self.assertEqual(self.key(uc, scan, mode=mode), 0x00)              # pressed: held in the table
                    self.assertEqual(self.noted(uc), skips)
        uc = self.machine(make_amiga_music.tune_module('intro'))
        uc.mem_write(self.S * 16 + 0x46f3 + 0x1c, b'\x00')                         # Enter held already
        self.assertEqual((self.key(uc, 0x1c), self.noted(uc)), (0x00, 0))          # its repeat is not a press
        self.assertEqual((self.key(uc, 0x1c, down=False), self.key(uc, 0x1c), self.noted(uc)), (0xff, 0x00, 1))

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_a_press_skips_from_frame_loops_and_the_first_sequence(self):
        import make_amiga_music, patches
        dos_tune = bytes.fromhex('1e538ccb8edb80fc') + bytes(64)
        stage = patches.INTR_CAVE_OFF + patches._intr_cave()[2]['stage']
        shutdown = (0x00d1, self.S + patches.INTR_DATA_SEG, patches.INTR_STACK_TOP)
        for module in (make_amiga_music.tune_module('intro'), dos_tune):
            with self.subTest(module=module[:3].hex()):
                uc = self.machine(module)
                at, regs = self.frame(uc)                                   # no press: the tick as the game sets it
                self.assertEqual((at, regs), (patches.INTR_FRAME_SET + 5, dict(self.REGS, AX=502, SP=0xff00)))
                self.assertEqual(uc.mem_read(self.REGS['DS'] * 16 + 0x4103, 2), (502).to_bytes(2, 'little'))
                self.key(uc, 0x1e)                                          # A, in the intro
                at, regs = self.frame(uc)
                self.assertEqual((at, regs['DS'], regs['SP']), shutdown)
                self.assertEqual([self.wait(uc)[1] for _ in range(2)], [0x50] * 2)   # skipping: not again
                uc = self.machine(module)
                self.key(uc, 0x39)
                at, regs = self.run_code(uc, self.MOD, stage, [patches.INTR_STAGE_TEST + 5, self.S],
                                         {self.S * 16 + patches.INTR_STAGE_TEST + 5, self.S * 16 + 0x00d1})
                self.assertEqual((at - self.S * 16, regs['DS'], regs['SP']), shutdown)
                uc = self.machine(module)
                self.key(uc, 0x1c)
                n, at, regs = self.wait(uc)
                self.assertEqual((n, at, regs['DS'], regs['SP']), (0,) + shutdown)
        uc = self.machine(bytes(64))                                        # no module loaded yet: the press waits
        self.key(uc, 0x1c)
        self.assertEqual((self.frame(uc)[0], self.wait(uc)[:2]), (patches.INTR_FRAME_SET + 5, (1, 0x50)))
        uc.mem_write(self.MOD * 16, dos_tune)                               # loaded: the next frame skips
        self.assertEqual(self.frame(uc)[0], 0x00d1)

    @unittest.skipUnless(has_unicorn(), 'the package unicorn')
    def test_k9_puts_the_stage_test_on_the_cave(self):
        import patches, unexepack
        image = bytearray(0x4920 + 0x2500)
        image[0x0f9e:0x0fae] = bytes.fromhex('bada0390eca80875fb90eca80874fbc3')
        image[0x0d76:0x0d80] = bytes.fromhex('833e620104' '7503' 'e86bfb')
        image[0x0228:0x022f] = bytes.fromhex('4040a3034107c3')
        image[0x477f:0x4786] = bytes.fromhex('8ac42e8887f346')
        image[0x4920 + 0x2402:0x4920 + 0x2406] = b'\x01\x02\x03\x04'    # the image's bytes after the cave
        exe = unexepack.build_mz(bytes(image), [(0x10, 0)], 0, 0, 0x6d2, 0x800, 0x100)
        out = patches.patch_intr_skip(exe)
        h = struct.unpack('<14H', out[:28])
        new = out[h[4] * 16:]
        relocs = {struct.unpack('<HH', out[h[12] + 4 * i:h[12] + 4 * i + 4]) for i in range(h[3])}
        code, code_relocs, entries = patches._intr_cave()
        at = patches.INTR_CAVE_OFF + entries['stage']
        self.assertEqual(new[0x0d76:0x0d80], bytes([0x9a, at & 0xff, at >> 8, 0x92, 0x04]) + b'\x90' * 5)   # call far 0492:
        at = patches.INTR_CAVE_OFF + entries['key']
        self.assertEqual(new[0x477f:0x4786], bytes([0x9a, at & 0xff, at >> 8, 0x92, 0x04]) + b'\x90' * 2)
        at = patches.INTR_CAVE_OFF + entries['frame']
        self.assertEqual(new[0x0228:0x022f], bytes([0x9a, at & 0xff, at >> 8, 0x92, 0x04, 0x07, 0xc3]))
        for word in (0x0d79, 0x4782, 0x022b, 0x0fa1):
            self.assertIn((word & 0xf, word >> 4), relocs)
        self.assertEqual(new[0x0f9e:0x0fa4], bytes.fromhex('ea00239204c3'))
        self.assertEqual(new[0x4920 + 0x2300:0x4920 + 0x2300 + len(code)], code)
        self.assertEqual(new[0x4920 + 0x2402:0x4920 + 0x2406], b'\x01\x02\x03\x04')
        self.assertLessEqual(len(code), 0x102)
        self.assertEqual(len(relocs), 1 + 4 + len(code_relocs))
        image[0x0d7d] = 0xe9                                            # not the GOG INTR.EXE
        with self.assertRaises(ValueError):
            patches.patch_intr_skip(unexepack.build_mz(bytes(image), [], 0, 0, 0x6d2, 0x800, 0x100))

    # --- the sound ----------------------------------------------------------------------------------------------------
    @unittest.skipUnless(has_numpy(), 'the package numpy')
    def test_paula_plays_a_modules_sample_once_and_then_its_loop(self):
        import numpy as np
        import make_amiga_audio as audio
        class Channel:
            stop, cur_vol, rate = False, 64, float(audio.RATE)          # one sample of the instrument a sample
        pcm = np.arange(1, 41, dtype=np.float32) / 64
        def played(frames, **instrument):
            ch, paula, out = Channel(), audio.Paula(), []
            ch.ins = dict(pcm=pcm, **instrument)
            for k, n in enumerate(frames):
                ch.trigger = k == 0
                out.append(paula.frame(ch, n))
            return [int(round(v * 64)) for v in np.concatenate(out)]
        # an effect's instrument: to its end, then 30-39 again and again
        self.assertEqual(played((25, 35), looped=True, loop=30), list(range(1, 41)) + [31 + k % 10 for k in range(20)])
        # a module's: 0-19 once, then 8-11
        self.assertEqual(played((7, 17, 12), looped=True, loop=8, first=20, end=12),
                         list(range(1, 21)) + [9 + k % 4 for k in range(16)])
        self.assertEqual(played((50,), looped=False, loop=0), list(range(1, 41)) + [0] * 10)     # a one-shot stops

    @unittest.skipUnless(has_numpy(), 'the package numpy')
    def test_tune_becomes_a_left_and_a_right_looped_sample(self):
        import numpy as np
        import amiga_module, make_amiga_audio as audio, soundfont
        left, right, loop, seconds = audio.tune_sides(tune_test_module(), amiga_module.equal_periods())
        per_tick = audio.RATE // amiga_module.TICK_HZ
        self.assertEqual(seconds, 24 / 50)
        self.assertEqual(loop, (6 * per_tick, 24 * per_tick))           # the test tune comes round to its tick 6
        self.assertEqual((len(left), len(right)), (24 * per_tick + audio.LOOP_TAIL,) * 2)
        self.assertTrue(np.array_equal(left[loop[1]:], left[loop[0]:loop[0] + audio.LOOP_TAIL]))
        # channels 0 and 3 are the left, 1 and 2 the right: channel 2 starts at tick 15, channel 1 at tick 0
        self.assertGreater(np.abs(left[:per_tick]).max(), 0.3)
        self.assertGreater(np.abs(right[:per_tick]).max(), 0.1)
        self.assertLessEqual(max(np.abs(left).max(), np.abs(right).max()), 2 * amiga_module.TUNE_LEVEL)
        with tempfile.TemporaryDirectory() as folder:
            font = Path(folder) / 'f.sf2'
            sounds = [(0, 20, 'effect', left[:1000], audio.RATE, None), (2, 21, 'part', left, audio.RATE, loop),
                      (amiga_module.TUNE_PRESET, 40, 'tune', left, audio.RATE, loop, audio.TUNE_RELEASE)]
            soundfont.write(str(font), sounds, 'Moonstone', cut=True)
            data = font.read_bytes()
            at = data.index(b'igen')
            gens = data[at + 8:at + 8 + int.from_bytes(data[at + 4:at + 8], 'little')]
            releases = [struct.unpack('<h', gens[k + 2:k + 4])[0] for k in range(0, len(gens), 4)
                        if struct.unpack('<H', gens[k:k + 2])[0] == soundfont.RELEASE]
            self.assertEqual(releases, [8000, -7000, -2084])            # one-shot, loop (17 ms), the tune (0.3 s)

    @unittest.skipUnless(has_numpy(), 'the package numpy')
    def test_font_without_disk_1_has_no_tunes(self):
        import make_amiga_audio as audio
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(audio.tune_sounds(folder), ([], ''))
            font = Path(folder) / 'amiga.sf2'
            (Path(folder) / 'amiga.tunes').write_text('x')
            audio.write_marker(str(font), audio.TUNES_MARKER, False, 'intro and ending tunes')
            self.assertFalse((Path(folder) / 'amiga.tunes').exists())
            audio.write_marker(str(font), audio.TUNES_MARKER, True, 'intro and ending tunes')
            self.assertIn('amiga.sf2 has the Amiga intro and ending tunes', (Path(folder) / 'amiga.tunes').read_text())
        # a module the player cannot play costs the tunes, not the effects' SoundFont
        import amiga_module
        broken = ('disk.adf', {'intro': b'short', 'ending': b'short'}, amiga_module.equal_periods())
        with patch.object(amiga_module, 'read_disk', return_value=broken):
            sounds, note = audio.tune_sounds('anywhere')
        self.assertEqual((sounds, note), ([], '; no intro and ending tunes: not a module (too short)'))
        with patch.object(amiga_module, 'read_disk', return_value=('disk.adf', {}, None)):
            self.assertEqual(audio.tune_sounds('anywhere')[0], [])      # `program` is not the known file


@unittest.skipUnless(os.name == 'nt', 'Windows batch files')
class AmigaTuneSwitches(unittest.TestCase):
    """D87 (phase 5, step 7: the host player retired): which intro and ending tunes Start.bat puts in DISKA, and which
    music profile it uses, for each combination of the music, the effects and the switches."""
    SETS = SoundSwitches.SETS
    run_bat = Launchers.run_bat
    switch = SoundSwitches.switch
    profile = SoundSwitches.profile

    def game(self, flag=True, tunes=('amiga', 'amiga_gm')):
        game = SoundSwitches.game(self)
        for name in ('AmigaMusic_On.bat', 'AmigaMusic_Off.bat'):
            shutil.copyfile(ROOT / name, game / name)
        amiga = game / '_music' / 'amiga'
        for music_set in SoundSwitches.SETS:
            for disk in ('DISKA', 'DISKB'):
                (game / '_music' / music_set / disk / 'ATUNE6.BIN').write_text(music_set)
        (amiga / 'font').mkdir()
        for tune in ('ATUNE1.BIN', 'ATUNE6.BIN'):
            (amiga / 'font' / tune).write_text('font')
        for name in tunes:
            (amiga / f'{name}.tunes').write_text('x')
        if flag:
            (game / 'AMIGA.FLG').write_text('amiga')
        return game

    def start(self, game):
        """-> (DISKA's two tunes, the profile music.conf was written from, DISKB's tune, AMIGATUN.FLG there), Start's output"""
        code, out = self.run_bat(game, 'Start.bat')
        self.assertEqual(code, 0, out)
        conf = (game / 'music.conf').read_text()
        profile = next((name for name in ('amiga_gm', 'amiga', 'gm', 'mt32', 'adlib')
                        if conf.startswith(self.profile(game, name))), conf)
        return ((game / 'DISKA' / 'ATUNE1.BIN').read_text(), (game / 'DISKA' / 'ATUNE6.BIN').read_text(), profile,
                (game / 'DISKB' / 'ATUNE6.BIN').read_text(), (game / 'AMIGATUN.FLG').exists()), out

    def test_font_tunes_with_adlib_and_gm_music_and_either_effects(self):
        game = self.game()
        for music, effects, profile, tunes in (('Music_AdLib.bat', 'AmigaSound_Off.bat', 'amiga', 'adlib'),
                                               ('Music_AdLib.bat', 'AmigaSound_On.bat', 'amiga', 'adlib'),
                                               ('Music_GM.bat', 'AmigaSound_On.bat', 'amiga_gm', 'gm_amiga'),
                                               ('Music_GM.bat', 'AmigaSound_Off.bat', 'amiga_gm', 'gm_amiga')):
            with self.subTest(music=music, effects=effects):
                self.switch(game, music)
                said = self.switch(game, effects)
                self.assertIn('Intro and ending music: Amiga', said)
                state, out = self.start(game)
                self.assertEqual(state, ('font', 'font', profile, tunes, True), out)
                self.assertEqual((game / 'AMIGASND.FLG').exists(), effects == 'AmigaSound_On.bat')
                self.assertEqual((game / 'effects.cfg').read_text().strip(), 'amiga' if effects == 'AmigaSound_On.bat' else 'dos')

    def test_mt32_keeps_its_roland_tunes(self):
        game = self.game()
        self.switch(game, 'Music_AdLib.bat')
        self.assertEqual(self.start(game)[0][:3], ('font', 'font', 'amiga'))
        said = self.switch(game, 'Music_MT32.bat')
        self.assertNotIn('Intro and ending music: Amiga', said)
        state, out = self.start(game)
        self.assertEqual(state, ('mt32', 'mt32', 'mt32', 'mt32', False))
        self.assertNotIn('AmigaMusic_Setup', out)                   # nothing to set up: MT-32 has its own tunes

    def test_the_dos_tunes_and_profile_come_back_without_the_switch(self):
        game = self.game()
        self.switch(game, 'Music_GM.bat')                           # GM with the DOS effects
        self.assertEqual(self.start(game)[0], ('font', 'font', 'amiga_gm', 'gm_amiga', True))
        (game / 'AMIGA.FLG').unlink()                               # deleted by hand: the fluidsynth device again
        state, out = self.start(game)
        self.assertEqual(state, ('gm', 'gm', 'gm', 'gm', False))
        self.assertIn('fluid.soundfont = soundfonts\\GeneralUser-GS.sf2', (game / 'music.conf').read_text())
        self.assertIn('Intro and ending music: Amiga', self.switch(game, 'AmigaMusic_On.bat'))
        self.assertEqual(self.start(game)[0], ('font', 'font', 'amiga_gm', 'gm_amiga', True))
        self.switch(game, 'Music_AdLib.bat')
        self.assertEqual(self.start(game)[0], ('font', 'font', 'amiga', 'adlib', True))
        self.switch(game, 'AmigaMusic_Off.bat')
        self.assertFalse((game / 'AMIGA.FLG').exists())
        self.assertEqual(((game / 'DISKA' / 'ATUNE1.BIN').read_text(), self.start(game)[0]),
                         ('adlib', ('adlib', 'adlib', 'adlib', 'adlib', False)))

    def test_original_mode_plays_the_dos_tunes(self):
        game = self.game()
        self.switch(game, 'Music_AdLib.bat')
        self.assertEqual(self.start(game)[0], ('font', 'font', 'amiga', 'adlib', True))
        (game / 'ORIGINAL.FLG').write_text('original')              # the original INTR.EXE does not pace the pictures
        state, out = self.start(game)
        self.assertEqual(state, ('adlib', 'adlib', 'adlib', 'adlib', False))
        self.assertNotIn('AmigaMusic_Setup', out)
        self.switch(game, 'AmigaSound_On.bat')                      # with the Amiga effects: their profile, DOS tunes
        self.assertEqual(self.start(game)[0], ('adlib', 'adlib', 'amiga', 'adlib', False))
        (game / 'ORIGINAL.FLG').unlink()
        self.assertEqual(self.start(game)[0], ('font', 'font', 'amiga', 'adlib', True))

    def test_without_the_tunes_in_the_font_as_the_dos_game(self):
        for missing in ('amiga.tunes', 'font', 'amiga.sf2'):
            with self.subTest(missing=missing):
                game = self.game()
                path = game / '_music' / 'amiga' / missing
                shutil.rmtree(path) if path.is_dir() else path.unlink()
                self.switch(game, 'Music_AdLib.bat')
                state, out = self.start(game)
                self.assertEqual(state, ('adlib', 'adlib', 'adlib', 'adlib', False))
                self.assertIn('run AmigaMusic_Setup.bat. Using the DOS music.', out)
        game = self.game(tunes=('amiga',))                          # the merged font without them: GM as before
        self.switch(game, 'Music_GM.bat')
        self.assertEqual(self.start(game)[0], ('gm', 'gm', 'gm', 'gm', False))
        self.switch(game, 'AmigaSound_On.bat')                      # with the effects: their merged font, DOS tunes
        self.assertEqual(self.start(game)[0], ('gm_amiga', 'gm_amiga', 'amiga_gm', 'gm_amiga', False))

    def test_amiga_music_on_needs_the_font_tunes(self):
        game = self.game(flag=False, tunes=())
        code, out = self.run_bat(game, 'AmigaMusic_On.bat')
        self.assertEqual(code, 1, out)
        self.assertIn('run AmigaMusic_Setup.bat first', out)
        self.assertFalse((game / 'AMIGA.FLG').exists())

    def test_no_host_player_is_left(self):
        self.assertFalse((ROOT / 'amiga_music.ps1').exists())
        for name in ('Start.bat', 'AmigaMusic_On.bat', 'AmigaMusic_Off.bat', 'AmigaMusic_Setup.bat', 'Setup.bat',
                     'tools/set_sound.bat', 'setup/setup.py'):
            text = (ROOT / name).read_text().lower()
            for word in ('amiga_music.ps1', 'powershell', 'vlc', 'intro.wav'):
                self.assertFalse(word in text, f'{name}: {word}')
        text = (ROOT / 'tools' / 'make_amiga_music.py').read_text().lower()   # it only removes the WAV files
        for word in ('vlc.exe', 'subprocess', 'def render', 'def mute'):
            self.assertFalse(word in text, f'make_amiga_music.py: {word}')

    def test_setup_removes_what_the_older_player_left(self):
        import make_amiga_music
        out = Path(tempfile.mkdtemp(dir=ROOT))
        self.addCleanup(shutil.rmtree, out, True)
        for name in ('intro.mod', 'ending.mod', 'intro.wav', 'ending.wav', 'amiga.sf2', 'amiga.tunes'):
            (out / name).write_text('x')
        for name in ('adlib', 'gm', 'gm_amiga', 'mt32', 'font'):
            (out / name).mkdir()
            (out / name / 'ATUNE1.BIN').write_text('x')
        self.assertEqual(sorted(make_amiga_music.remove_d8(str(out))),
                         ['adlib/', 'ending.mod', 'ending.wav', 'gm/', 'gm_amiga/', 'intro.mod', 'intro.wav', 'mt32/'])
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['amiga.sf2', 'amiga.tunes', 'font'])


class WalkFrames(unittest.TestCase):
    """D143: tools/walk_frames.py without the game's files (the pictures are tested against the approved sample in the
    development suites, which have the game)."""

    def test_no_game_pieces_no_file(self):
        import walk_frames
        game = Path(tempfile.mkdtemp(dir=ROOT))
        self.addCleanup(shutil.rmtree, game, True)
        (game / walk_frames.INB_NAME).write_bytes(b'an older file')
        self.assertIsNone(walk_frames.install(str(game)))        # no DISKB/KN1.OB
        self.assertFalse((game / walk_frames.INB_NAME).exists())
        (game / 'DISKB').mkdir()
        for name in walk_frames.BANKS:
            (game / 'DISKB' / name).write_bytes(b'not a bank')
        self.assertIsNone(walk_frames.install(str(game)))
        self.assertFalse((game / walk_frames.INB_NAME).exists())

    def test_slots_and_the_place(self):
        import walk_frames
        slots = sorted(walk_frames.slot_number(look, facing, fa, j) for look in (0, 1) for facing in (0, 1)
                       for fa in hook.WK_LOOP for j in range(1, 6))
        self.assertEqual(slots, list(range(1, hook.WK_SLOTS)))
        self.assertEqual(hook.WK_SLOT * hook.WK_SLOTS, 129600)
        # the legs piece from 10 to 13: the picture a sixth, a half and five sixths of the way, to the nearest
        # pixel; an exact half to the even pixel when the slot's word says its constant is whole, else up
        zero = 6 * hook.WK_BIAS + 3
        entry = (None, zero | hook.WK_WHOLE, zero)
        self.assertEqual([walk_frames.place(entry, j, 10, 10, 13, 13) for j in (1, 3, 5)], [(10, 11), (12, 12), (12, 13)])
        self.assertEqual(walk_frames.place(entry, 2, 13, 13, 10, 10), (12, 12))
        # a constant of a third of a pixel: never a half
        third = (None, zero + 2, zero + 2)
        self.assertEqual(walk_frames.place(third, 3, 10, 10, 13, 13), (12, 12))

    def test_the_overlay_group_and_the_room(self):
        code, labels = labelled_hook()
        self.assertIn('walk_match', labels)
        self.assertIn('wk_h', labels)
        self.assertEqual(code[labels['wk_h'] - 0x100:labels['wk_h'] - 0x100 + 2], bytes(2))   # no file until the installer finds it
        self.assertEqual(hook.BUF_MSG - hook.BUF_WALK, hook.WK_SLOT + hook.WK_MARGIN)   # D153: the unpacking's margin
        self.assertEqual(hook.BUF_HINT - hook.BUF_MSG, hook.MSG_ROOM)  # B9: the loading screen's scratch area kept
        self.assertEqual(hook.BUF_ILOG - hook.BUF_HINT, 66)            # B10: the hints' round (a place, 64 bytes of order)

    def test_packed_slots(self):
        # D153: a slot packed in place unpacks to itself (as wk_fetch does it, from the end of BUF_WALK's room); the
        # stream ends at WK_PACK, the rest of the slot is zero; a slot whose stream does not fit is refused
        import random, walk_frames
        rnd = random.Random(153)
        for nonzero in (0, 1, 200, 500):
            slot = bytearray(hook.WK_SLOT)
            for i in rnd.sample(range(hook.WK_SLOT - 300), nonzero): slot[i] = rnd.randrange(1, 256)
            packed = walk_frames.pack_slot(bytes(slot))
            self.assertEqual(len(packed), hook.WK_SLOT)
            self.assertEqual(packed[hook.WK_PACK:], bytes(hook.WK_SLOT - hook.WK_PACK))
            self.assertEqual(walk_frames.unpack_slot(packed), bytes(slot))
        with self.assertRaises(walk_frames.WalkError):
            walk_frames.pack_slot(bytes([7]) * hook.WK_SLOT)
        self.assertEqual((hook.WK_MAGIC, hook.WK_PACK % 2, hook.WK_SRC), (b'INB2', 0,
                         hook.BUF_WALK + hook.WK_SLOT + hook.WK_MARGIN - hook.WK_PACK))

    def test_conf_names_the_save_compression(self):
        # D153: DOSBox-X's default written out, with the comment on false
        text = (ROOT / 'moonstone-dosbox-x.conf').read_text()
        self.assertIn('compresssaveparts = true', text.splitlines())
        self.assertIn('about 41 MB', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
