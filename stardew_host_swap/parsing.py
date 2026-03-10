from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from .utils import text


def parse_root(path) -> ET.Element:
    return ET.parse(path).getroot()


def find_farmhands(root: ET.Element) -> list[ET.Element]:
    return root.findall("farmhands/Farmer")


def find_target_farmhand(
    root: ET.Element,
    *,
    name: Optional[str],
    mp_id: Optional[str],
) -> tuple[int, ET.Element]:
    farmhands = find_farmhands(root)
    if not farmhands:
        raise ValueError("No farmhands found in save file.")

    matches: list[tuple[int, ET.Element]] = []
    for idx, fh in enumerate(farmhands):
        fh_name = text(fh.find("name"))
        fh_id = text(fh.find("UniqueMultiplayerID"))
        ok = False
        if name is not None and fh_name == name:
            ok = True
        if mp_id is not None and fh_id == mp_id:
            ok = True
        if ok:
            matches.append((idx, fh))

    if not matches:
        details = []
        for idx, fh in enumerate(farmhands):
            details.append(
                f"[{idx}] name={text(fh.find('name'))!r}, UniqueMultiplayerID={text(fh.find('UniqueMultiplayerID'))}"
            )
        raise ValueError("Target farmhand not found. Available farmhands:\n" + "\n".join(details))

    if len(matches) > 1:
        raise ValueError("Multiple farmhands matched. Use --target-id for disambiguation.")

    return matches[0]


def list_farmhands(root: ET.Element) -> str:
    player = root.find("player")
    lines = [
        f"Host: name={text(player.find('name'))!r}, UniqueMultiplayerID={text(player.find('UniqueMultiplayerID'))}"
    ]
    for idx, fh in enumerate(find_farmhands(root)):
        lines.append(
            f"[{idx}] name={text(fh.find('name'))!r}, UniqueMultiplayerID={text(fh.find('UniqueMultiplayerID'))}"
        )
    return "\n".join(lines)
