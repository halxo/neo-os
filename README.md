# NeoOS

NeoOS uses Arch Linux packages by default and lets users choose Arch-first or
CachyOS-first repository priority during installation or afterwards.

## Build the ISO

On an up-to-date Arch build host, install `archiso` (including its build dependencies).
The host must have a working Arch mirrorlist and a trusted CachyOS keyring; follow
the keyring setup in the [official CachyOS instructions](https://wiki.cachyos.org/features/optimized_repos/).
Remote package signatures remain required. The bundled local Neo and Calamares
packages are unsigned; replace them in `localrepo/` when updating those components.

Run from this checkout:

```sh
./tools/build-iso
```

Recent mkarchiso supports an unprivileged build using subordinate UID/GID mappings.
If the host lacks those mappings, run `sudo ./tools/build-iso` instead.
The wrapper builds the local package database, generates the absolute local repo
URL, and invokes mkarchiso with a fresh work directory. The output is
`out/neoos-1.0-x86_64.iso`. Old `work/` stage markers are never reused: mkarchiso
otherwise silently skips changed configuration and package stages.
Use the wrapper rather than passing the template `pacman.conf` directly to mkarchiso.

The ISO itself always uses Arch-first packages, including multilib. CachyOS supplies
packages absent from Arch. The build does not require host CachyOS mirrorlists.

## Choose repository priority

```sh
neo repos status
neo repos list
sudo neo repos cachyos
sudo pacman -Syu
# Switch back:
sudo neo repos arch
sudo pacman -Syu
```

`neoos-repoctl arch`, `neoos-repoctl cachyos`, and `neoos-repoctl status` use the
same backend. Arch-first orders core, extra, multilib, then the generic CachyOS
repository. CachyOS-first puts CPU-compatible v3/v4 repositories and the generic
CachyOS repository ahead of Arch. CPUs without v3/v4 use the generic repository.
Repository names and mirrorlists follow the official CachyOS documentation above.

This changes which repository pacman prefers for future transactions. It does not
immediately replace installed packages. `pacman -Syu` upgrades the complete system;
same-version builds are not reinstalled and newer installed packages are not
downgraded. A full migration of existing packages needs a separately reviewed
reinstallation/downgrade transaction. Packages only available in CachyOS remain
available in Arch-first mode.

The canonical configuration is `/etc/neo/repository-mode.conf` and
`/etc/pacman.d/neo-repositories.conf`. The installer uses the same renderer as the
runtime switcher and applies the selected mode to the target after installing Neo.

## Checks

```sh
python3 tests/repositories.py
```

These checks exercise mode round trips, invalid input, non-mutating configuration
rendering, CPU levels, and live/installed backend consistency without touching the
host package configuration. A full ISO build and VM installation are separate checks.

The generated configuration accepts CPU-compatible CachyOS architecture tags
(`x86_64_v2`, `x86_64_v3`, `x86_64_v4`) as well as `x86_64`. The baseline
architecture stays first so `$arch` mirror URLs continue to resolve correctly.
The tests use real pacman transaction preparation to verify compatible packages
are accepted and unsupported CPU levels are rejected.

The NeoOS KDE launcher icon is installed in both the live image and the target
system. `configure-plasma-branding` applies it to Plasma's default panel layout;
a pacman hook reapplies this default when the layout is updated by a package.

`tests/online-install-smoke` exercises the real network installer for both source
modes in disposable directories, starting from an existing built airootfs. Run it
inside `unshare --user --map-auto --map-root-user --mount --pid --fork`, passing
the absolute path of that airootfs. It uses the upstream rootless mount setup,
retains real `/tmp` tmpfs mounts, and checks Neo installation, branding, repository
mode, and staging cleanup. It downloads uncached packages and retains its test
files under `work-install-smoke.*`; it does not partition disks.
