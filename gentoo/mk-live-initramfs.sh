#!/usr/bin/env bash
set -euo pipefail

# Builds a fast, self-contained live initramfs for Gentoo + OpenRC that boots
# /LiveOS/squashfs.img over overlayfs without systemd-udevd settle hangs.

KVER="$1"
OUT_IMG="$2"
WORK="$(mktemp -d /tmp/neoos-initrd.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK"/{bin,sbin,usr/bin,usr/sbin,lib,lib64,etc,proc,sys,dev,run,mnt/cdrom,mnt/ro,mnt/rw,sysroot}

copy_bin() {
    local bin="$1"
    local src
    src="$(command -v "$bin" || true)"
    [[ -n "$src" ]] || { echo "Missing binary for initramfs: $bin" >&2; exit 1; }
    local dest="$WORK/bin/$(basename "$bin")"
    cp -L "$src" "$dest"
    chmod 755 "$dest"
    # Copy shared libraries and dynamic linker
    ldd "$src" 2>/dev/null | awk '/=> \//{print $3} $1 ~ /^\//{print $1}' | while read -r lib; do
        [[ -f "$lib" ]] || continue
        local dir
        dir="$(dirname "$lib")"
        mkdir -p "$WORK$dir"
        cp -nL "$lib" "$WORK$lib" 2>/dev/null || true
    done
}

for b in bash mount umount switch_root modprobe depmod blkid losetup sleep mkdir ls cat dmesg grep sed; do
    copy_bin "$b"
done
ln -sf bash "$WORK/bin/sh"
ln -sf /bin/mount "$WORK/sbin/mount"
ln -sf /bin/umount "$WORK/sbin/umount"
ln -sf /bin/modprobe "$WORK/sbin/modprobe"
ln -sf /bin/switch_root "$WORK/sbin/switch_root"

# Copy essential kernel modules for CD-ROM, USB, SATA/AHCI, NVMe, VirtIO, VirtualBox, squashfs, overlayfs
MODSRC="/lib/modules/$KVER"
MODDST="$WORK/lib/modules/$KVER"
mkdir -p "$MODDST"

for rel in \
    modules.builtin modules.builtin.modinfo modules.order modules.dep modules.dep.bin modules.alias modules.alias.bin modules.symbols modules.symbols.bin \
    kernel/fs/isofs kernel/fs/squashfs kernel/fs/overlayfs kernel/fs/nls \
    kernel/drivers/block/loop.ko* kernel/drivers/cdrom \
    kernel/drivers/ata/ata_piix.ko* kernel/drivers/ata/ahci.ko* kernel/drivers/ata/libahci.ko* kernel/drivers/ata/libata.ko* \
    kernel/drivers/scsi/sr_mod.ko* kernel/drivers/scsi/sd_mod.ko* kernel/drivers/scsi/virtio_scsi.ko* \
    kernel/drivers/nvme/host \
    kernel/drivers/virtio kernel/drivers/block/virtio_blk.ko* \
    kernel/drivers/usb/host/xhci*.ko* kernel/drivers/usb/host/ehci*.ko* kernel/drivers/usb/storage/usb-storage.ko* kernel/drivers/usb/storage/uas.ko* \
    kernel/lib/lzo kernel/lib/zstd kernel/lib/zlib_inflate; do
    for src in $MODSRC/$rel; do
        if [[ -e "$src" ]]; then
            local_rel="${src#$MODSRC/}"
            parent="$(dirname "$local_rel")"
            mkdir -p "$MODDST/$parent"
            cp -a "$src" "$MODDST/$parent/"
        fi
    done
done

depmod -b "$WORK" "$KVER" 2>/dev/null || true

cat > "$WORK/init" <<'EOF'
#!/bin/sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin

mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
exec </dev/console >/dev/console 2>&1

echo "==> [NeoOS Initramfs] Loading storage, filesystem, and VirtualBox drivers..."
modprobe loop max_loop=8 2>/dev/null || true
for mod in cdrom sr_mod ata_piix ahci sd_mod usb-storage xhci-pci ehci-pci \
           virtio_pci virtio_blk virtio_scsi nvme isofs squashfs overlay; do
    modprobe "$mod" 2>/dev/null || true
done

echo "==> [NeoOS Initramfs] Searching for NeoOS Live media (/LiveOS/squashfs.img)..."
FOUND=""
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    for dev in /dev/sr* /dev/cdrom* /dev/sd* /dev/vd* /dev/nvme*n*p* /dev/nvme*n*; do
        [ -b "$dev" ] || continue
        echo "==> [NeoOS Initramfs] Trying $dev..."
        if mount -t iso9660 -o ro "$dev" /mnt/cdrom || mount -o ro "$dev" /mnt/cdrom 2>/dev/null; then
            if [ -f /mnt/cdrom/LiveOS/squashfs.img ]; then
                FOUND="$dev"
                echo "==> [NeoOS Initramfs] Found NeoOS Live media on $dev"
                break 2
            fi
            umount /mnt/cdrom 2>/dev/null || true
        fi
    done
    sleep 1
done

if [ -z "$FOUND" ]; then
    echo "ERROR: Could not find /LiveOS/squashfs.img on any block device!"
    ls -la /dev/sr* /dev/sd* /dev/vd* 2>/dev/null || true
    exec /bin/sh
fi

echo "==> [NeoOS Initramfs] Mounting LiveOS squashfs + overlayfs..."
LOOPDEV="$(losetup -f --show /mnt/cdrom/LiveOS/squashfs.img)" || {
    echo "ERROR: Failed to attach loop device for squashfs.img!"
    ls -la /dev/loop* 2>/dev/null || true
    exec /bin/sh
}
mount -t squashfs -o ro "$LOOPDEV" /mnt/ro || {
    echo "ERROR: Failed to mount squashfs.img!"
    exec /bin/sh
}

mount -t tmpfs -o mode=0755 tmpfs /mnt/rw
mkdir -p /mnt/rw/upper /mnt/rw/work

mount -t overlay overlay -o lowerdir=/mnt/ro,upperdir=/mnt/rw/upper,workdir=/mnt/rw/work /sysroot || {
    echo "ERROR: Failed to mount overlayfs!"
    exec /bin/sh
}

mkdir -p /sysroot/proc /sysroot/sys /sysroot/dev /sysroot/run/live/cdrom /sysroot/run/live/ro /sysroot/run/live/rw /sysroot/tmp
mount --move /mnt/cdrom /sysroot/run/live/cdrom 2>/dev/null || true
mount --move /mnt/ro /sysroot/run/live/ro 2>/dev/null || true
mount --move /mnt/rw /sysroot/run/live/rw 2>/dev/null || true
mount --move /dev /sysroot/dev
mount --move /proc /sysroot/proc
mount --move /sys /sysroot/sys

echo "==> [NeoOS Initramfs] Switching root to Gentoo OpenRC (/sbin/init)..."
exec switch_root /sysroot /sbin/init
echo "ERROR: switch_root failed!"
exec /bin/sh
EOF
chmod 755 "$WORK/init"

(cd "$WORK" && find . -print0 | cpio --null -ov --format=newc 2>/dev/null | gzip -1 > "$OUT_IMG")
echo "==> [NeoOS Initramfs] Built $(du -h "$OUT_IMG" | cut -f1) -> $OUT_IMG"
