"""Hardware-tailored kernel autocompilation with automatic gentoo-kernel fallback."""
from __future__ import annotations

import pathlib
from typing import List, Optional

from .hardware import HardwareProfile

# Kernel config symbols forced ON so localmodconfig never strips essential boot/rootfs/VM drivers.
REQUIRED_KERNEL_OPTIONS = [
    "CONFIG_DEVTMPFS=y",
    "CONFIG_DEVTMPFS_MOUNT=y",
    "CONFIG_TMPFS=y",
    "CONFIG_PROC_FS=y",
    "CONFIG_SYSFS=y",
    "CONFIG_BLK_DEV_INITRD=y",
    "CONFIG_EFI=y",
    "CONFIG_EFI_STUB=y",
    "CONFIG_EFIVAR_FS=y",
    "CONFIG_EXT4_FS=y",
    "CONFIG_BTRFS_FS=y",
    "CONFIG_XFS_FS=y",
    "CONFIG_VFAT_FS=y",
    "CONFIG_NLS_CODEPAGE_437=y",
    "CONFIG_NLS_ISO8859_1=y",
    "CONFIG_BLK_DEV_NVME=y",
    "CONFIG_SATA_AHCI=y",
    "CONFIG_BLK_DEV_SD=y",
    "CONFIG_USB_HID=y",
    "CONFIG_INPUT_EVDEV=y",
    "CONFIG_NET=y",
    "CONFIG_INET=y",
    "CONFIG_PACKET=y",
    "CONFIG_UNIX=y",
    "CONFIG_CGROUPS=y",
    "CONFIG_INOTIFY_USER=y",
    "CONFIG_FB=y",
    "CONFIG_DRM=y",
    "CONFIG_DRM_FBDEV_EMULATION=y",
]

VIRTUALBOX_KERNEL_OPTIONS = [
    "CONFIG_DRM_VBOXVIDEO=m",
    "CONFIG_DRM_VMWGFX=m",
    "CONFIG_VBOXGUEST=m",
    "CONFIG_VBOXSF_FS=m",
    "CONFIG_E1000=y",
    "CONFIG_VIRTIO_PCI=y",
    "CONFIG_VIRTIO_BLK=y",
    "CONFIG_VIRTIO_NET=y",
]


def render_kernel_autocompile_script(
    hw: HardwareProfile,
    install_mode: str = "binpkg",
    lsmod_path: str = "/tmp/neoos-lsmod.txt",
) -> str:
    """Generate the in-chroot bash script that autocompiles a hardware-tailored kernel.

    Strategy:
      1. Install sys-kernel/gentoo-sources, sys-kernel/linux-firmware, and sys-kernel/dracut.
      2. Seed /usr/src/linux/.config from the running live kernel config (or defconfig).
      3. Run `make LSMOD=<lsmod> localmodconfig` to strip unneeded drivers for fast compiles.
      4. Force-enable essential boot, filesystem, UEFI, and VM (VirtualBox) options.
      5. Compile and install the kernel, modules, and dracut initramfs.
      6. If any step of localmodconfig/gentoo-sources fails, automatically fall back to
         compiling `sys-kernel/gentoo-kernel` from source so the system always boots.
    """
    emerge_flags = "--getbinpkg" if install_mode == "binpkg" else ""
    extra_opts = list(REQUIRED_KERNEL_OPTIONS)
    if hw.hypervisor in ("virtualbox", "vmware", "kvm"):
        extra_opts.extend(VIRTUALBOX_KERNEL_OPTIONS)

    config_tweaks = []
    for opt in extra_opts:
        sym, val = opt.split("=", 1)
        flag = "--enable" if val == "y" else "--module"
        config_tweaks.append(f'    ./scripts/config {flag} {sym}')
    tweaks_block = "\n".join(config_tweaks)

    return f"""#!/bin/bash
set -euo pipefail

JOBS="{hw.makeopts_jobs}"
LSMOD_FILE="{lsmod_path}"

echo "==> [NeoOS Kernel] Installing firmware, dracut, and gentoo-sources..."
emerge {emerge_flags} --noreplace sys-kernel/linux-firmware sys-kernel/dracut sys-kernel/gentoo-sources

build_localmodconfig_kernel() {{
    echo "==> [NeoOS Kernel] Auto-configuring kernel for this hardware (localmodconfig)..."
    eselect kernel set 1
    cd /usr/src/linux

    if [[ -r /proc/config.gz ]]; then
        zcat /proc/config.gz > .config
    elif [[ -r /boot/config-live ]]; then
        cp /boot/config-live .config
    else
        make defconfig
    fi

    if [[ -s "$LSMOD_FILE" ]]; then
        yes "" | make LSMOD="$LSMOD_FILE" localmodconfig
    else
        yes "" | make localmodconfig
    fi

    echo "==> [NeoOS Kernel] Enforcing required boot, filesystem, and VM drivers..."
{tweaks_block}
    yes "" | make olddefconfig

    echo "==> [NeoOS Kernel] Compiling custom kernel with -j${{JOBS}}..."
    make -j"${{JOBS}}"
    make modules_install
    make install

    KVER="$(make -s kernelrelease)"
    echo "==> [NeoOS Kernel] Generating dracut initramfs for ${{KVER}}..."
    dracut --force --kver "${{KVER}}" "/boot/initramfs-${{KVER}}.img"
    echo "==> [NeoOS Kernel] Custom hardware kernel ${{KVER}} built successfully."
}}

fallback_gentoo_kernel() {{
    echo "==> [NeoOS Kernel] WARNING: localmodconfig build failed; falling back to sys-kernel/gentoo-kernel (compiled from source)..."
    # Compile gentoo-kernel from source (without --getbinpkg) so it still optimizes for this CPU.
    USE="initramfs" emerge --noreplace sys-kernel/gentoo-kernel
    echo "==> [NeoOS Kernel] Fallback sys-kernel/gentoo-kernel installed successfully."
}}

if ! build_localmodconfig_kernel; then
    fallback_gentoo_kernel
fi
"""


def write_lsmod_snapshot(dest: pathlib.Path, loaded_modules: Optional[List[str]] = None) -> None:
    """Write an lsmod-compatible file for `make LSMOD=... localmodconfig` inside chroot."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if loaded_modules is None and pathlib.Path("/proc/modules").is_file():
        lines = ["Module                  Size  Used by"]
        for line in pathlib.Path("/proc/modules").read_text(errors="ignore").splitlines():
            parts = line.split()
            if len(parts) >= 3:
                lines.append(f"{parts[0]} {parts[1]} {parts[2]}")
        dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines = ["Module                  Size  Used by"]
    for mod in (loaded_modules or []):
        lines.append(f"{mod} 16384 0")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
