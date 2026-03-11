from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
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


def _backup_file(path: Path) -> Path:
    backup_path = path.with_name(path.name + "_bak")
    shutil.copy2(path, backup_path)
    return backup_path


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

    if options.fix_house_interior:
        # Placeholder for future implementation.
        pass

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
        f"houseInterior={options.fix_house_interior}, "
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
        print("  House interior fix: placeholder only, not implemented yet.")
    print(f"  Main save backup: {main_backup}")
    print(f"  Main save written in-place: {output_main_path}")
    if savegameinfo_written is not None:
        print("  SaveGameInfo sync: root /Farmer inner XML replaced with swapped /SaveGame/player inner XML")
        print(f"  SaveGameInfo backup: {savegameinfo_backup}")
        print(f"  SaveGameInfo written in-place: {savegameinfo_written}")