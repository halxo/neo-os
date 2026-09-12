import os
import subprocess
import libcalamares


def run():
    gs = libcalamares.globalstorage

    if not gs.contains("neoPackageSource"):
        return (
            "NeoOS package source is missing.",
            "The package-source selection was not stored."
        )

    mode = gs.value("neoPackageSource")

    if mode not in ("arch", "cachyos"):
        return (
            "Invalid NeoOS package source.",
            "Received package source: {}".format(mode)
        )

    root = gs.value("rootMountPoint")

    if not root:
        return (
            "NeoOS installation target is missing.",
            "Calamares did not provide rootMountPoint."
        )

    command = [
        "/usr/lib/neo/online-install",
        root,
        mode
    ]


    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
    except Exception as error:
        return (
            "Could not start the NeoOS network installer.",
            str(error)
        )

    libcalamares.utils.debug(
        "NeoOS online-install output:\n{}".format(result.stdout)
    )

    if result.returncode != 0:
        return (
            "NeoOS network installation failed.",
            result.stdout[-4000:]
        )

    return None
