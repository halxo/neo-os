#!/bin/bash

set -e

/usr/lib/neo/configure-plasma-branding

install -m755 /usr/share/neoos/target-overlay/usr/bin/neo /usr/bin/neo
/usr/lib/neo/configure-repositories arch

# Database signatures were checked by the host during pacstrap. Discard the
# build-time sync databases before mkarchiso queries the live package list:
# the live keyring is initialized on boot, and these databases are stale then.
find /var/lib/pacman/sync -maxdepth 1 -type f -delete
