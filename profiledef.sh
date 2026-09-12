#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="neoos"
iso_label="NEOOS_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="NeoOS"
iso_application="NeoOS Live"
iso_version="1.0"
install_dir="arch"
buildmodes=('iso')
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15' '-b' '1M')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/usr/lib/neo/configure-plasma-branding"]="0:0:755"
  ["/usr/bin/neoos-repoctl"]="0:0:755"
  ["/usr/lib/neo/configure-repositories"]="0:0:755"
  ["/usr/lib/neo/init-live-repositories"]="0:0:755"
  ["/usr/lib/neo/online-install"]="0:0:755"
  ["/usr/share/neoos/target-overlay/usr/bin/"]="0:0:755"
  ["/usr/share/neoos/target-overlay/usr/lib/neo/"]="0:0:755"
  ["/etc/sudoers.d/99-neo-live"]="0:0:440"
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
)
