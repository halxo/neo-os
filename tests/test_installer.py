#!/usr/bin/env python3
"""Unit and dry-run integration tests for the NeoOS Gentoo OpenRC installer."""
import pathlib
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "installer"))

from neo_installer.backend import (
    GentooInstaller,
    InstallConfig,
    partition_paths,
    render_chroot_install_script,
    render_make_conf,
)
from neo_installer.desktops import get_desktop, load_desktops
from neo_installer.hardware import (
    DiskInfo,
    HardwareProfile,
    compute_safe_makeopts_jobs,
)
from neo_installer.kernel import render_kernel_autocompile_script, write_lsmod_snapshot


def sample_hw(firmware: str = "uefi", hypervisor: str = "virtualbox") -> HardwareProfile:
    return HardwareProfile(
        cpu_model="Test x86_64 CPU",
        cpu_cores=8,
        makeopts_jobs=compute_safe_makeopts_jobs(8, 8192),
        ram_mb=8192,
        cpu_flags_x86=["aes", "avx", "avx2", "sse4_2"],
        video_cards=["virtualbox", "vmware", "fbdev", "vesa"],
        hypervisor=hypervisor,
        firmware=firmware,
        loaded_modules=["ext4", "ahci", "vboxguest", "e1000"],
        disks=[DiskInfo("/dev/sda", 40 * 1024**3, "40.0 GiB", "VBOX HARDDISK")],
    )


class TestGentooInstaller(unittest.TestCase):
    def test_desktop_catalog_covers_all_major_desktops(self):
        desktops = load_desktops()
        ids = {d.id for d in desktops}
        expected = {
            "kde", "gnome", "xfce", "cinnamon", "mate", "lxqt",
            "budgie", "sway", "hyprland", "i3", "openbox", "minimal",
        }
        self.assertTrue(expected.issubset(ids), f"Missing desktops: {expected - ids}")
        for d in desktops:
            self.assertIn("23.0", d.profile)
            self.assertIn("dbus", d.openrc_services)
            self.assertIn("NetworkManager", d.openrc_services)

    def test_make_conf_binpkg_vs_source(self):
        hw = sample_hw()
        kde = get_desktop("kde")

        binpkg_conf = render_make_conf(hw, kde, "binpkg")
        self.assertIn('COMMON_FLAGS="-O2 -pipe"', binpkg_conf)
        self.assertIn("getbinpkg", binpkg_conf)
        self.assertIn("-systemd", binpkg_conf)
        self.assertIn("elogind", binpkg_conf)
        self.assertIn('VIDEO_CARDS="virtualbox vmware fbdev vesa"', binpkg_conf)

        source_conf = render_make_conf(hw, kde, "source")
        self.assertIn('COMMON_FLAGS="-march=native -O2 -pipe"', source_conf)
        self.assertNotIn("getbinpkg", source_conf)

    def test_kernel_autocompile_and_fallback(self):
        hw = sample_hw(hypervisor="virtualbox")
        script = render_kernel_autocompile_script(hw, install_mode="binpkg")
        self.assertIn("sys-kernel/gentoo-sources", script)
        self.assertIn("make LSMOD=\"$LSMOD_FILE\" localmodconfig", script)
        self.assertIn("CONFIG_DRM_VBOXVIDEO", script)
        self.assertIn("dracut --force --kver", script)
        self.assertIn("fallback_gentoo_kernel", script)
        self.assertIn("sys-kernel/gentoo-kernel", script)

        with tempfile.TemporaryDirectory() as tmp:
            lsmod_file = pathlib.Path(tmp) / "lsmod.txt"
            write_lsmod_snapshot(lsmod_file, hw.loaded_modules)
            content = lsmod_file.read_text()
            self.assertIn("vboxguest", content)

    def test_partition_paths_sata_and_nvme(self):
        self.assertEqual(
            partition_paths("/dev/sda", True),
            {"boot": "/dev/sda1", "swap": "/dev/sda2", "root": "/dev/sda3"},
        )
        self.assertEqual(
            partition_paths("/dev/nvme0n1", False),
            {"boot": "/dev/nvme0n1p1", "swap": None, "root": "/dev/nvme0n1p2"},
        )

    def test_chroot_script_includes_openrc_and_vbox_additions(self):
        hw = sample_hw(firmware="uefi", hypervisor="virtualbox")
        cfg = InstallConfig(target_disk="/dev/sda", desktop_id="xfce", install_mode="source")
        script = render_chroot_install_script(cfg, hw, get_desktop("xfce"))
        self.assertIn("app-emulation/virtualbox-guest-additions", script)
        self.assertIn("rc-update add virtualbox-guest-additions default", script)
        self.assertIn('DISPLAYMANAGER="lightdm"', script)
        self.assertIn("grub-install --target=x86_64-efi", script)
        self.assertNotIn("--getbinpkg", script)

    def test_dry_run_end_to_end_uefi_and_bios(self):
        for firmware in ("uefi", "bios"):
            for mode in ("binpkg", "source"):
                with self.subTest(firmware=firmware, mode=mode):
                    cfg = InstallConfig(
                        target_disk="/dev/sda",
                        desktop_id="kde",
                        install_mode=mode,
                        dry_run=True,
                    )
                    logs = []
                    installer = GentooInstaller(cfg, hardware=sample_hw(firmware=firmware), log_callback=logs.append)
                    result = installer.run()
                    self.assertEqual(result["firmware"], firmware)
                    self.assertEqual(result["install_mode"], mode)
                    self.assertGreaterEqual(result["commands_count"], 12)


if __name__ == "__main__":
    unittest.main()
