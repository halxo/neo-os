#!/usr/bin/env bash
set -euo pipefail

# Runs inside neoos-gentoo-live:latest to install NeoOS files, build the live
# dracut initramfs, compress squashfs.img, and emit a hybrid BIOS+UEFI ISO.

WORKSPACE="${1:-/workspace}"
OUT_DIR="${WORKSPACE}/out"
ISO_LABEL="NEOOS_GENTOO"
ISO_NAME="neoos-gentoo-1.0-x86_64.iso"
ISO_STAGING="/tmp/neoos-iso"

mkdir -p "$OUT_DIR" "$ISO_STAGING/LiveOS" "$ISO_STAGING/boot/grub"

echo "==> [NeoOS Pack ISO] Installing NeoOS graphical installer and branding..."
mkdir -p /usr/share/neoos /usr/local/lib/neo-installer /etc/lightdm /etc/conf.d
cp -a "$WORKSPACE/gentoo/desktops.json" /usr/share/neoos/desktops.json
cp -a "$WORKSPACE/branding/neoos.png" /usr/share/neoos/neoos.png
cp -a "$WORKSPACE/installer/neo_installer" /usr/local/lib/neo-installer/
install -m 755 "$WORKSPACE/installer/neo-installer" /usr/local/bin/neo-installer
sed -i 's|ROOT = pathlib.Path(__file__).resolve().parent|ROOT = pathlib.Path("/usr/local/lib/neo-installer")|' /usr/local/bin/neo-installer
install -m 755 "$WORKSPACE/tools/neo" /usr/local/bin/neo

echo "==> [NeoOS Pack ISO] Configuring live user (neo) with graphical autologin..."
id -u neo >/dev/null 2>&1 || useradd -m -G wheel,audio,video,input,plugdev -s /bin/bash neo
printf 'root:neo\nneo:neo\n' | chpasswd
mkdir -p /etc/sudoers.d
printf '%%wheel ALL=(ALL:ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/99-neo-live
chmod 440 /etc/sudoers.d/99-neo-live

printf 'DISPLAYMANAGER="lightdm"\n' > /etc/conf.d/display-manager
cat > /etc/lightdm/lightdm.conf <<'EOF'
[Seat:*]
autologin-user=neo
autologin-user-timeout=0
user-session=openbox
EOF

mkdir -p /home/neo/.config/openbox
cat > /home/neo/.config/openbox/autostart <<'EOF'
xsetroot -solid "#141824" &
xterm -title "NeoOS Terminal" &
sudo -E /usr/local/bin/neo-installer &
EOF
chown -R neo:neo /home/neo/.config

for svc in dbus elogind NetworkManager display-manager; do
    rc-update add "$svc" default || true
done

echo "==> [NeoOS Pack ISO] Building dracut live initramfs..."
KVER="$(ls -1 /lib/modules | sort -V | tail -n 1)"
VMLINUZ="$(find /boot -maxdepth 1 -name 'vmlinuz-*' | sort -V | tail -n 1)"
dracut --force --no-hostonly --kver "$KVER" \
    --add "dmsquash-live pollcdrom" \
    --filesystems "squashfs ext4 vfat iso9660 overlay" \
    "$ISO_STAGING/boot/initramfs.img"
cp -a "$VMLINUZ" "$ISO_STAGING/boot/vmlinuz"

echo "==> [NeoOS Pack ISO] Packing LiveOS squashfs image..."
mksquashfs / "$ISO_STAGING/LiveOS/squashfs.img" \
    -comp lzo -b 1M -noappend \
    -e proc sys dev run tmp mnt media var/tmp var/log var/cache/distfiles var/cache/binpkgs var/cache/binhost var/db/repos usr/share/doc usr/share/man usr/share/gtk-doc usr/include workspace

echo "==> [NeoOS Pack ISO] Generating GRUB2 hybrid BIOS + UEFI ISO..."
cat > "$ISO_STAGING/boot/grub/grub.cfg" <<EOF
set timeout=5
set default=0

menuentry "NeoOS Live (Gentoo + OpenRC Graphical Installer)" {
    linux /boot/vmlinuz root=live:CDLABEL=${ISO_LABEL} rd.live.image rd.live.squashimg=squashfs.img quiet
    initrd /boot/initramfs.img
}

menuentry "NeoOS Live (Safe Graphics / VirtualBox nomodeset)" {
    linux /boot/vmlinuz root=live:CDLABEL=${ISO_LABEL} rd.live.image rd.live.squashimg=squashfs.img nomodeset
    initrd /boot/initramfs.img
}
EOF

grub-mkrescue -o "${OUT_DIR}/${ISO_NAME}" "$ISO_STAGING" -- -volid "${ISO_LABEL}"

if [[ -n "${HOST_UID:-}" && -n "${HOST_GID:-}" ]]; then
    chown -R "${HOST_UID}:${HOST_GID}" "$OUT_DIR"
fi

echo "==> [NeoOS Pack ISO] Done: ${OUT_DIR}/${ISO_NAME}"
ls -lh "${OUT_DIR}/${ISO_NAME}"
