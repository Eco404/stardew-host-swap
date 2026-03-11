from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import ResolvedPaths, SwapOptions
from .parsing import find_target_farmhand, parse_root
from .raw_xml import swap_player_and_farmer_raw
from .transformers import (
    get_mailreceived_list_from_farmer_elem,
    get_single_simple_tag_from_farmer_elem,
    ordered_union,
    swap_simple_tag_values_by_ids,
)
from .utils import text


def generate_report(
    main_save_path: Path,
    *,
    target_name: Optional[str],
    target_id: Optional[str],
    resolved: Optional[ResolvedPaths] = None,
    options: Optional[SwapOptions] = None,
) -> str:
    options = options or SwapOptions()

    root = parse_root(main_save_path)
    player = root.find("player")
    if player is None or root.find("farmhands") is None:
        raise ValueError("Save file is missing /SaveGame/player or /SaveGame/farmhands.")

    idx, target_fh = find_target_farmhand(root, name=target_name, mp_id=target_id)

    lines = ["Swap report (raw inner-XML swap mode)", f"Source save: {main_save_path}"]
    if resolved is not None and resolved.mode == "folder" and resolved.source_folder is not None:
        lines.append(f"Source folder: {resolved.source_folder}")
        if resolved.savegameinfo_in is not None:
            lines.append(f"SaveGameInfo: {resolved.savegameinfo_in}")
        else:
            lines.append("SaveGameInfo: not found")
        lines.append("Operation mode: in-place (backup files will be created in the same folder)")

    lines += ["", "Players"]
    lines.append(f"  Host before:  name={text(player.find('name'))!r}, id={text(player.find('UniqueMultiplayerID'))}")
    lines.append(
        f"  Guest before: name={text(target_fh.find('name'))!r}, id={text(target_fh.find('UniqueMultiplayerID'))}, farmhands index={idx}"
    )

    host_mail = get_mailreceived_list_from_farmer_elem(player)
    guest_mail = get_mailreceived_list_from_farmer_elem(target_fh)
    merged_mail = ordered_union(guest_mail, host_mail)
    host_userid = get_single_simple_tag_from_farmer_elem(player, "userID")
    guest_userid = get_single_simple_tag_from_farmer_elem(target_fh, "userID")
    host_home = get_single_simple_tag_from_farmer_elem(player, "homeLocation")
    guest_home = get_single_simple_tag_from_farmer_elem(target_fh, "homeLocation")

    lines.append("  Enabled options:")
    lines.append(f"    basic swap: {options.basic_swap}")
    lines.append(f"    homeLocation fix: {options.fix_home_location}")
    lines.append(f"    farmhandReference fix: {options.fix_farmhand_reference}")
    lines.append(f"    house interior fix: {options.fix_house_interior} (placeholder)")
    lines.append(f"    mailReceived fix: {options.fix_mail_received}")
    lines.append(f"    userID fix: {options.fix_user_id}")
    lines.append(f"    SaveGameInfo sync: {options.sync_savegameinfo}")

    if options.fix_house_interior:
        lines.append("  Note: house interior fix is not implemented yet; checking it currently has no effect.")

    lines.append("  After swap: raw inner XML of /SaveGame/player and the target /SaveGame/farmhands/Farmer is exchanged.")

    ref_counts = {"farmhandReference": 0}
    if options.fix_farmhand_reference:
        raw_xml = main_save_path.read_text(encoding="utf-8-sig")
        swapped_preview = swap_player_and_farmer_raw(raw_xml, idx)
        _, ref_counts = swap_simple_tag_values_by_ids(
            swapped_preview,
            ["farmhandReference"],
            text(player.find("UniqueMultiplayerID")),
            text(target_fh.find("UniqueMultiplayerID")),
        )

    fixes = ["basic swap"]
    if options.fix_mail_received:
        fixes.append("mailReceived")
    if options.fix_home_location:
        fixes.append("homeLocation")
    if options.fix_user_id:
        fixes.append("userID")
    if options.fix_farmhand_reference:
        fixes.append("farmhandReference")
    if options.sync_savegameinfo:
        fixes.append("SaveGameInfo sync")
    if options.fix_house_interior:
        fixes.append("house interior (placeholder)")
    lines.append(f"  Additional fixes: {', '.join(fixes)}.")

    if options.fix_home_location:
        lines.append(f"    New host homeLocation: {guest_home!r} -> 'FarmHouse'")
        lines.append(f"    New guest homeLocation: {host_home!r} -> {guest_home!r}")
    if options.fix_user_id:
        lines.append(f"    New host userID: {guest_userid!r} -> ''")
        lines.append(f"    New guest userID: {host_userid!r} -> {guest_userid!r}")
    if options.fix_mail_received:
        lines.append(f"    New host mailReceived: {len(guest_mail)} -> {len(merged_mail)} (guest ∪ host)")
        lines.append(f"    New guest mailReceived: restored to original host count {len(host_mail)}")
    if options.fix_farmhand_reference:
        lines.append(f"    ID reference swaps: farmhandReference={ref_counts['farmhandReference']}")

    lines.append("  Backups to be created before overwrite:")
    lines.append(f"    Main save backup: {main_save_path.name}_bak")
    if resolved is not None and resolved.savegameinfo_in is not None and options.sync_savegameinfo:
        lines.append("    SaveGameInfo backup: SaveGameInfo_bak")

    return "\n".join(lines)
