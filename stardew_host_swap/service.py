from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Optional

from .models import SwapOptions
from .parsing import find_target_farmhand, parse_root
from .raw_xml import (
    extract_player_inner_from_main_save,
    find_nth_farmer_bounds,
    replace_player_and_farmer_inners,
    replace_savegameinfo_farmer_inner,
    swap_player_and_farmer_raw,
)
from .transformers import (
    get_mailreceived_list_from_farmer_elem,
    get_single_simple_tag_from_farmer_elem,
    ordered_union,
    set_mailreceived_on_wrapped_inner,
    set_single_simple_tag_on_wrapped_inner,
    swap_simple_tag_values_by_ids,
)
from .utils import text


# Keep the original XML declaration / root opening so the rewritten file
# stays as close as possible to the source formatting.
def _extract_xml_prefix_and_root_opening(raw_xml: str) -> tuple[str, str]:
    decl_match = re.match(r"^(<\?xml[^>]*\?>)", raw_xml)
    xml_decl = decl_match.group(1) if decl_match else ""

    root_match = re.search(r"<SaveGame\b[^>]*>", raw_xml)
    if root_match is None:
        raise ValueError("Could not locate the opening <SaveGame ...> tag in the save file.")
    root_opening = root_match.group(0)
    return xml_decl, root_opening


def _serialize_savegame_with_original_header(root: ET.Element, original_xml: str) -> str:
    xml_decl, root_opening = _extract_xml_prefix_and_root_opening(original_xml)
    serialized = ET.tostring(root, encoding="unicode")
    serialized = re.sub(r"^<SaveGame\b[^>]*>", root_opening, serialized, count=1)
    if xml_decl and not serialized.startswith(xml_decl):
        serialized = xml_decl + serialized
    return serialized


def _find_gamelocation_by_name(root: ET.Element, location_name: str) -> ET.Element:
    locations = root.find("locations")
    if locations is None:
        raise ValueError("Save file is missing /SaveGame/locations.")

    for loc in locations.findall("GameLocation"):
        if text(loc.find("name")) == location_name:
            return loc

    raise ValueError(f"GameLocation not found: {location_name!r}")


# Resolve the target cabin interior by the farmhand's original homeLocation.
def _find_cabin_indoors_by_unique_name(root: ET.Element, unique_name: str) -> ET.Element:
    if not unique_name:
        raise ValueError("Target farmhand homeLocation is empty; cannot locate cabin interior.")
    if unique_name == "FarmHouse":
        raise ValueError("Target farmhand homeLocation is 'FarmHouse'; cannot locate a cabin interior.")

    farm_loc = _find_gamelocation_by_name(root, "Farm")
    buildings = farm_loc.find("buildings")
    if buildings is None:
        raise ValueError("Farm location is missing /buildings.")

    for building in buildings.findall("Building"):
        indoors = building.find("indoors")
        if indoors is None:
            continue
        if text(indoors.find("uniqueName")) == unique_name:
            return indoors

    raise ValueError(f"Cabin indoors with uniqueName={unique_name!r} not found.")


# Swap a selected set of named child nodes between FarmHouse and the target cabin.
def _swap_named_children(parent_a: ET.Element, parent_b: ET.Element, tag_names: list[str]) -> list[str]:
    swapped: list[str] = []

    for tag in tag_names:
        elem_a = parent_a.find(tag)
        elem_b = parent_b.find(tag)
        if elem_a is None or elem_b is None:
            missing = []
            if elem_a is None:
                missing.append(f"left<{tag}>")
            if elem_b is None:
                missing.append(f"right<{tag}>")
            raise ValueError(
                "Missing house interior child while swapping: " + ", ".join(missing)
            )

        idx_a = list(parent_a).index(elem_a)
        idx_b = list(parent_b).index(elem_b)

        clone_a = deepcopy(elem_a)
        clone_b = deepcopy(elem_b)

        parent_a.remove(elem_a)
        parent_b.remove(elem_b)
        parent_a.insert(idx_a, clone_b)
        parent_b.insert(idx_b, clone_a)
        swapped.append(tag)

    return swapped


def _backup_file(path: Path) -> Path:
    backup_path = path.with_name(path.name + "_bak")
    shutil.copy2(path, backup_path)
    return backup_path


# Restore the current save from *_bak files, then remove the used backup files.
def restore_backups(main_save_path: Path, savegameinfo_path: Optional[Path] = None) -> list[Path]:
    restored: list[Path] = []

    main_backup = main_save_path.with_name(main_save_path.name + "_bak")
    if not main_backup.exists():
        raise FileNotFoundError(f"Main save backup not found: {main_backup}")
    shutil.copy2(main_backup, main_save_path)
    main_backup.unlink()
    restored.append(main_save_path)

    if savegameinfo_path is not None:
        saveinfo_backup = savegameinfo_path.with_name(savegameinfo_path.name + "_bak")
        if saveinfo_backup.exists():
            shutil.copy2(saveinfo_backup, savegameinfo_path)
            saveinfo_backup.unlink()
            restored.append(savegameinfo_path)

    return restored


# Main swap pipeline used by both CLI and GUI.
def perform_swap(
    main_save_path: Path,
    output_main_path: Path,
    *,
    target_name: Optional[str],
    target_id: Optional[str],
    savegameinfo_in: Optional[Path] = None,
    output_savegameinfo: Optional[Path] = None,
    options: Optional[SwapOptions] = None,
) -> None:
    options = options or SwapOptions()
    if not options.basic_swap:
        raise ValueError("Basic swap is required and cannot be disabled.")

    root = parse_root(main_save_path)
    player = root.find("player")
    if player is None or root.find("farmhands") is None:
        raise ValueError("Save file is missing /SaveGame/player or /SaveGame/farmhands.")

    target_index, target_fh = find_target_farmhand(root, name=target_name, mp_id=target_id)

    old_host_name = text(player.find("name"))
    old_host_id = text(player.find("UniqueMultiplayerID"))
    old_guest_name = text(target_fh.find("name"))
    old_guest_id = text(target_fh.find("UniqueMultiplayerID"))

    old_host_mail = get_mailreceived_list_from_farmer_elem(player)
    old_guest_mail = get_mailreceived_list_from_farmer_elem(target_fh)
    merged_host_mail = ordered_union(old_guest_mail, old_host_mail)

    old_guest_home = get_single_simple_tag_from_farmer_elem(target_fh, "homeLocation")
    old_guest_userid = get_single_simple_tag_from_farmer_elem(target_fh, "userID")

    raw_xml = main_save_path.read_text(encoding="utf-8-sig")
    swapped_xml = swap_player_and_farmer_raw(raw_xml, target_index)
    ET.fromstring(swapped_xml.encode("utf-8"))

    swapped_player_inner = extract_player_inner_from_main_save(swapped_xml)
    _, farmer_open_end, farmer_close_start, _ = find_nth_farmer_bounds(swapped_xml, target_index)
    swapped_farmer_inner = swapped_xml[farmer_open_end:farmer_close_start]

    fixed_player_inner = swapped_player_inner
    fixed_farmer_inner = swapped_farmer_inner

    # Apply optional per-player field fixes after the raw body swap.
    if options.fix_mail_received:
        fixed_player_inner = set_mailreceived_on_wrapped_inner(fixed_player_inner, merged_host_mail)
        fixed_farmer_inner = set_mailreceived_on_wrapped_inner(fixed_farmer_inner, old_host_mail)

    if options.fix_home_location:
        fixed_player_inner = set_single_simple_tag_on_wrapped_inner(
            fixed_player_inner, "homeLocation", "FarmHouse"
        )
        fixed_farmer_inner = set_single_simple_tag_on_wrapped_inner(
            fixed_farmer_inner, "homeLocation", old_guest_home
        )

    if options.fix_user_id:
        fixed_player_inner = set_single_simple_tag_on_wrapped_inner(
            fixed_player_inner, "userID", ""
        )
        fixed_farmer_inner = set_single_simple_tag_on_wrapped_inner(
            fixed_farmer_inner, "userID", old_guest_userid
        )

    swapped_xml = replace_player_and_farmer_inners(
        swapped_xml, target_index, fixed_player_inner, fixed_farmer_inner
    )

    ref_counts = {"farmhandReference": 0}
    if options.fix_farmhand_reference:
        swapped_xml, ref_counts = swap_simple_tag_values_by_ids(
            swapped_xml,
            ["farmhandReference"],
            old_host_id,
            old_guest_id,
        )

    interior_swapped_tags: list[str] = []
    if options.fix_house_interior:
        swapped_root = ET.fromstring(swapped_xml.encode("utf-8"))
        farmhouse_elem = _find_gamelocation_by_name(swapped_root, "FarmHouse")
        cabin_indoors_elem = _find_cabin_indoors_by_unique_name(swapped_root, old_guest_home)
        interior_swapped_tags = _swap_named_children(
            farmhouse_elem,
            cabin_indoors_elem,
            [
                "objects",
                "furniture",
                "wallPaper",
                "appliedWallpaper",
                "floor",
                "appliedFloor",
                "fridge",
                "fridgePosition",
                "cribStyle",
            ],
        )
        swapped_xml = _serialize_savegame_with_original_header(swapped_root, swapped_xml)

    ET.fromstring(swapped_xml.encode("utf-8"))

    main_backup = _backup_file(output_main_path)
    output_main_path.write_text(swapped_xml, encoding="utf-8-sig", newline="")

    savegameinfo_written = None
    savegameinfo_backup = None
    if options.sync_savegameinfo and savegameinfo_in is not None and output_savegameinfo is not None:
        new_player_inner = extract_player_inner_from_main_save(swapped_xml)
        savegameinfo_raw = savegameinfo_in.read_text(encoding="utf-8-sig")
        new_savegameinfo_xml = replace_savegameinfo_farmer_inner(savegameinfo_raw, new_player_inner)
        ET.fromstring(new_savegameinfo_xml.encode("utf-8"))
        savegameinfo_backup = _backup_file(output_savegameinfo)
        output_savegameinfo.write_text(new_savegameinfo_xml, encoding="utf-8-sig", newline="")
        savegameinfo_written = output_savegameinfo

    verify_root = ET.fromstring(swapped_xml.encode("utf-8"))
    new_player = verify_root.find("player")
    new_guest = verify_root.findall("farmhands/Farmer")[target_index]
    new_player_mail = get_mailreceived_list_from_farmer_elem(new_player)
    new_guest_mail = get_mailreceived_list_from_farmer_elem(new_guest)

    print("Swap complete.")
    print("Mode: raw inner-XML swap + selectable fixes")
    print(f"  Host before:  name={old_host_name!r}, id={old_host_id}")
    print(f"  Guest before: name={old_guest_name!r}, id={old_guest_id}")
    print(f"  New host:     name={text(new_player.find('name'))!r}, id={text(new_player.find('UniqueMultiplayerID'))}")
    print(f"  New guest:    name={text(new_guest.find('name'))!r}, id={text(new_guest.find('UniqueMultiplayerID'))}")
    print("  Applied changes: raw inner XML swap of /SaveGame/player and target /SaveGame/farmhands/Farmer")
    print(
        f"  Enabled options: homeLocation={options.fix_home_location}, "
        f"farmhandReference={options.fix_farmhand_reference}, "
        f"indoors={options.fix_house_interior}, "
        f"mailReceived={options.fix_mail_received}, "
        f"userID={options.fix_user_id}, "
        f"SaveGameInfo={options.sync_savegameinfo}"
    )
    print(
        f"  homeLocation: new host -> {text(new_player.find('homeLocation'))!r} ; "
        f"new guest -> {text(new_guest.find('homeLocation'))!r}"
    )
    print(
        f"  userID:       new host -> {text(new_player.find('userID'))!r} ; "
        f"new guest -> {text(new_guest.find('userID'))!r}"
    )
    print(
        f"  mailReceived: new host {len(old_guest_mail)} -> {len(new_player_mail)} ; "
        f"new guest restored to {len(new_guest_mail)}"
    )
    print(f"  ID refs:      farmhandReference={ref_counts['farmhandReference']}")
    if options.fix_house_interior:
        print(
            "  Indoors fix: swapped between FarmHouse and target cabin -> "
            + ", ".join(interior_swapped_tags)
        )
    print(f"  Main save backup: {main_backup}")
    print(f"  Main save written in-place: {output_main_path}")
    if savegameinfo_written is not None:
        print("  SaveGameInfo sync: root /Farmer inner XML replaced with swapped /SaveGame/player inner XML")
        print(f"  SaveGameInfo backup: {savegameinfo_backup}")
        print(f"  SaveGameInfo written in-place: {savegameinfo_written}")
