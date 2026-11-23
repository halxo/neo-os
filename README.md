# NeoOS (Gentoo + OpenRC)

NeoOS is a Gentoo Linux distribution powered by **OpenRC** with a graphical live desktop installer that **autocompiles a hardware-tailored Linux kernel** for each machine, lets you choose between **precompiled Gentoo binary packages** or **pure source compilation (`-march=native`)**, and offers **all major desktop environments**.

## Features

- **Init System**: OpenRC (`elogind`, `dbus`, `NetworkManager`, `display-manager-init`).
- **Graphical Live Desktop ISO**: Hybrid BIOS + UEFI ISO (`out/neoos-gentoo-1.0-x86_64.iso`) ready for VirtualBox and bare metal, booting directly into the GTK3 **NeoOS Easy Installer**.
- **Automatic Hardware-Tailored Kernel Compilation**:
  - Uses `sys-kernel/gentoo-sources`, `make localmodconfig` (seeded with the live system's loaded modules and enforced boot/filesystem/UEFI/VirtualBox drivers), and `dracut` initramfs generation.
  - Automatically falls back to compiling `sys-kernel/gentoo-kernel` from source if `localmodconfig` fails.
- **Precompiled or Source Mode**: Choose between Gentoo's official `23.0/x86-64` binary package host (`getbinpkg`) for fast installs or pure source compilation (`-march=native`), or switch anytime afterwards with `neo mode binpkg` / `neo mode source`.
- **All Desktop Environments**:
  - Full Desktops: **KDE Plasma**, **GNOME**, **Cinnamon**, **Budgie**
  - Lightweight Desktops: **XFCE**, **MATE**, **LXQt**
  - Window Managers: **Sway**, **Hyprland**, **i3**, **Openbox**
  - Server / CLI: **Minimal (OpenRC CLI)**

## Download & VirtualBox Quick Start (Windows)

Download the premade ISO, Docker Compose setup, and Windows launcher from the [v1.0-gentoo Release](https://github.com/halxo/neo-os/releases/tag/v1.0-gentoo):

- **Direct ISO Download**: [neoos-gentoo-1.0-x86_64.iso](https://github.com/halxo/neo-os/releases/download/v1.0-gentoo/neoos-gentoo-1.0-x86_64.iso)
- **Windows VirtualBox + Docker Launcher**: Double-click `neoos-virtualbox.bat` to either download the premade ISO or build it via Docker Compose, then automatically create and boot a VirtualBox VM (`NeoOS-Gentoo`).

## Build the Live ISO

Requires Docker (`gentoo/stage3:amd64-openrc`):

```sh
# Linux / macOS:
./tools/build-iso

# Or with the premade Docker Compose setup (Windows / macOS / Linux):
docker compose run --rm build-iso
```

The VirtualBox-ready hybrid BIOS + UEFI ISO is written to `out/neoos-gentoo-1.0-x86_64.iso`.

## Run Installer Tests

```sh
python3 tests/test_installer.py -v
```

You can also run a safe dry-run of the installer CLI without modifying any disks:

```sh
./installer/neo-installer --cli --dry-run --desktop kde --mode binpkg
```

## Post-Install CLI (`neo`)

```sh
neo mode status     # Show current Portage mode (binpkg vs source)
neo mode source     # Switch to pure source compilation (-march=native)
neo mode binpkg     # Switch to Gentoo official binary host
neo kernel rebuild  # Re-run hardware-tailored kernel autocompilation
neo desktops        # List supported desktop environments
neo update          # Sync Portage and upgrade @world
```
