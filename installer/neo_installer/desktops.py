"""Desktop environment catalog loader for NeoOS Gentoo OpenRC."""
from __future__ import annotations

import dataclasses
import json
import pathlib
from typing import List, Optional


@dataclasses.dataclass(frozen=True)
class DesktopOption:
    id: str
    name: str
    category: str
    description: str
    profile: str
    display_manager: Optional[str]
    use_flags: List[str]
    packages: List[str]
    openrc_services: List[str]


def _default_catalog_path() -> pathlib.Path:
    installed = pathlib.Path("/usr/share/neoos/desktops.json")
    if installed.is_file():
        return installed
    return pathlib.Path(__file__).resolve().parents[2] / "gentoo" / "desktops.json"


def load_desktops(catalog_path: Optional[pathlib.Path] = None) -> List[DesktopOption]:
    path = catalog_path or _default_catalog_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DesktopOption(**item) for item in data["desktops"]]


def get_desktop(desktop_id: str, catalog_path: Optional[pathlib.Path] = None) -> DesktopOption:
    for opt in load_desktops(catalog_path):
        if opt.id == desktop_id:
            return opt
    raise ValueError(f"Unknown desktop option: {desktop_id}")
