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
        import death_frames, horse_frames, make_gm_tunes, make_intr_exe, make_main_exe, make_voc_rates
        with patch.object(installer, 'HERE', str(game)), patch.object(installer, 'check_gog', lambda g: []), \
                patch.object(installer, 'find_gog', lambda a: str(game)), patch.object(make_voc_rates, 'FILES', []), \
                patch.object(make_main_exe, 'make_main_exe', main_exe), \
                patch.object(make_intr_exe, 'make_intr_exe', lambda gog, fixes=None: b'FIXED_INTR'), \
                patch.object(death_frames, 'install', lambda here, exe: exe), \
                patch.object(horse_frames, 'install', lambda here: None), \
                patch.object(make_gm_tunes, 'main', lambda gog, out: None), \
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

    def test_every_substitute_has_its_source_listed(self):
        sources = (ROOT / 'sounds' / 'SOURCES.md').read_text(encoding='utf-8')
        for path in (ROOT / 'sounds').glob('*.wav'):
            self.assertIn(f'`{path.name}`', sources, f'{path.name} is not in sounds/SOURCES.md')


if __name__ == '__main__':
    unittest.main(verbosity=2)
