import libcalamares


def run():
    gs = libcalamares.globalstorage

    if not gs.contains("packageOperations"):
        return (
            "NeoOS package source was not selected.",
            "Calamares did not provide packageOperations."
        )

    operations = gs.value("packageOperations")

    selected = []

    for operation in operations:
        packages = operation.get("install", [])

        if "neo-source-arch" in packages:
            selected.append("arch")

        if "neo-source-cachyos" in packages:
            selected.append("cachyos")

    selected = list(dict.fromkeys(selected))

    if len(selected) == 0:
        return (
            "NeoOS package source was not selected.",
            "Choose Arch Linux or CachyOS Optimized."
        )

    if len(selected) > 1:
        return (
            "Multiple NeoOS package sources were selected.",
            "Choose only one package source: Arch Linux or CachyOS Optimized."
        )

    mode = selected[0]

    gs.insert("neoPackageSource", mode)

    # Remove our fake marker packages so the Calamares packages
    # module can never try to install them later.
    cleaned_operations = []

    for operation in operations:
        new_operation = dict(operation)

        if "install" in new_operation:
            packages = [
                package
                for package in new_operation["install"]
                if package not in (
                    "neo-source-arch",
                    "neo-source-cachyos"
                )
            ]

            if packages:
                new_operation["install"] = packages
                cleaned_operations.append(new_operation)
        else:
            cleaned_operations.append(new_operation)

    gs.insert("packageOperations", cleaned_operations)

    libcalamares.utils.debug(
        "NeoOS package source: {}".format(mode)
    )

    return None
