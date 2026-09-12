#!/usr/bin/env python3
"""Unprivileged regression checks: no host pacman configuration is modified."""
import io
import re
import tarfile
import os
import pathlib
import subprocess
import tempfile
import unittest

PROFILE = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = PROFILE / 'airootfs/usr/lib/neo/configure-repositories'


class Repositories(unittest.TestCase):
    def test_switch_roundtrip_and_invalid_mode(self):
        with tempfile.TemporaryDirectory() as root:
            def run(*args, ok=True):
                return subprocess.run(['bash', str(SCRIPT), '--root', root, *args],
                                      capture_output=True, text=True, check=ok)
            config = pathlib.Path(root) / 'etc/pacman.d/neo-repositories.conf'
            for mode in ('arch', 'cachyos', 'arch'):
                run(mode)
                repos = run('list').stdout.splitlines()
                self.assertEqual(len(repos), len(set(repos)))
                if mode == 'arch':
                    self.assertEqual(repos, ['core', 'extra', 'multilib', 'cachyos'])
                else:
                    self.assertTrue(repos[0].startswith('cachyos'))
                    self.assertEqual(repos[-3:], ['core', 'extra', 'multilib'])
                self.assertIn(f'Repository mode: {mode}', run('status').stdout)
            before = config.read_bytes()
            self.assertNotEqual(run('invalid', ok=False).returncode, 0)
            self.assertEqual(config.read_bytes(), before)
            rendered = run('cachyos', '--print').stdout
            self.assertIn('[cachyos]', rendered)
            self.assertEqual(config.read_bytes(), before)

    def test_cpu_levels(self):
        # Substitute only the loader path to exercise supported/unsupported hardware.
        for level in ('x86-64', 'x86-64-v2', 'x86-64-v3', 'x86-64-v4'):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as tmp:
                loader = pathlib.Path(tmp) / 'loader'
                loader.write_text(f'#!/bin/sh\necho "{level} (supported, searched)"\n')
                loader.chmod(0o755)
                script = pathlib.Path(tmp) / 'configure'
                script.write_text(SCRIPT.read_text().replace(
                    '/usr/lib/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2', str(loader)))
                result = subprocess.check_output(['bash', str(script), 'cachyos', '--print'], text=True)
                # Use real pacman transaction preparation, not only string checks.
                config = pathlib.Path(tmp) / 'pacman.conf'
                config.write_text(re.sub(r'Include = .*',
                    'Server = https://example.invalid/$arch/$repo', result)
                    .replace('[options]', '[options]\nSigLevel = Never'))
                arches = subprocess.check_output(
                    ['pacman-conf', '--config', str(config), 'Architecture'], text=True).splitlines()
                self.assertEqual(arches[0], 'x86_64')
                max_level = 1 if level == 'x86-64' else int(level[-1])
                for package_level in (2, 3, 4):
                    package = pathlib.Path(tmp) / f'neo-test-1-1-x86_64_v{package_level}.pkg.tar'
                    with tarfile.open(package, 'w') as archive:
                        data = (f'pkgname = neo-test\npkgver = 1-1\npkgdesc = test\n'
                                f'arch = x86_64_v{package_level}\nsize = 0\n').encode()
                        info = tarfile.TarInfo('.PKGINFO')
                        info.size = len(data)
                        archive.addfile(info, io.BytesIO(data))
                    prepared = subprocess.run(['pacman', '--config', str(config), '-Up', str(package)],
                                              capture_output=True, text=True)
                    self.assertEqual(prepared.returncode == 0, package_level <= max_level,
                                     prepared.stdout + prepared.stderr)
                if level.endswith(('v3', 'v4')):
                    suffix = level[-2:]
                    self.assertIn(f'[cachyos-core-{suffix}]', result)
                    self.assertIn(f'[cachyos-extra-{suffix}]', result)
                else:
                    self.assertNotIn('[cachyos-v', result)

    def test_installer_uses_selected_mode_and_cleans_temp_config(self):
        for mode in ('arch', 'cachyos'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                target = root / 'target'
                target.mkdir()
                binaries = root / 'bin'
                binaries.mkdir()
                capture = root / 'pacman-config-path'
                pacstrap = binaries / 'pacstrap'
                pacstrap.write_text('#!/bin/bash\nprintf "%s" "$2" > "$CAPTURE"\n'
                                    'cp "$2" "$CAPTURE.contents"\n')
                pacstrap.chmod(0o755)
                chroot = binaries / 'arch-chroot'
                chroot.write_text('#!/bin/bash\nset -e\n'
                                  'if [[ "$2" == pacman && "$3" == -U ]]; then\n'
                                  '  package="${@: -1}"\n'
                                  '  [[ "$package" != /tmp/* ]] || exit 91\n'
                                  '  [[ -r "$1$package" ]] || exit 92\n'
                                  '  printf "%s" "$1$package" > "$CAPTURE.package"\n'
                                  'fi\n' 
                                  'if [[ "$2" == /usr/lib/neo/configure-repositories ]]; then\n'
                                  '  bash "$BACKEND" --root "$1" "$3"\n'
                                  'fi\n')
                chroot.chmod(0o755)
                installer = root / 'installer'
                code = (PROFILE / 'airootfs/usr/lib/neo/online-install').read_text()
                code = code.replace('/usr/share/neoos', str(PROFILE / 'airootfs/usr/share/neoos'))
                code = code.replace('/usr/lib/neo/configure-repositories "$MODE" --print',
                                    f'"{SCRIPT}" "$MODE" --print')
                installer.write_text(code)
                env = dict(os.environ, PATH=str(binaries) + ':' + os.environ['PATH'],
                           CAPTURE=str(capture), BACKEND=str(SCRIPT))
                subprocess.run(['bash', str(installer), str(target), mode], env=env,
                               check=True, capture_output=True, text=True)
                self.assertFalse(pathlib.Path(capture.read_text()).exists())
                staged = pathlib.Path(pathlib.Path(str(capture) + '.package').read_text())
                self.assertFalse(staged.exists())
                self.assertFalse(staged.parent.exists())
                rendered = pathlib.Path(str(capture) + '.contents').read_text()
                first_repo = next(line for line in rendered.splitlines()
                                  if line.startswith('[') and line != '[options]')
                self.assertEqual(first_repo == '[core]', mode == 'arch')
                self.assertEqual((target / 'etc/neo/repository-mode.conf').read_text(),
                                 f'mode={mode}\n')
                self.assertTrue((target / 'usr/bin/neoos-repoctl').stat().st_mode & 0o111)

    def test_live_and_target_share_backend(self):
        overlay = PROFILE / 'airootfs/usr/share/neoos/target-overlay'
        self.assertEqual(SCRIPT.read_bytes(), (overlay / 'usr/lib/neo/configure-repositories').read_bytes())
        installer = (PROFILE / 'airootfs/usr/lib/neo/online-install').read_text()
        self.assertIn('configure-repositories "$MODE" --print', installer)
        self.assertLess(installer.index('pacman -U'), installer.index('cp -a "$TARGET_OVERLAY"'))


if __name__ == '__main__':
    unittest.main()
