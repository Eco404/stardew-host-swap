from __future__ import annotations


def find_tag_bounds(xml: str, tag: str, start_pos: int = 0) -> tuple[int, int, int, int]:
    open_start = xml.find(f"<{tag}>", start_pos)
    if open_start == -1:
        raise ValueError(f"Tag <{tag}> not found.")
    open_end = open_start + len(f"<{tag}>")
    close_start = xml.find(f"</{tag}>", open_end)
    if close_start == -1:
        raise ValueError(f"Closing tag </{tag}> not found.")
    close_end = close_start + len(f"</{tag}>")
    return open_start, open_end, close_start, close_end


def find_nth_farmer_bounds(xml: str, index: int) -> tuple[int, int, int, int]:
    _, farmhands_open_end, farmhands_close_start, _ = find_tag_bounds(xml, "farmhands")
    pos = farmhands_open_end
    count = 0

    while True:
        farmer_open = xml.find("<Farmer>", pos, farmhands_close_start)
        if farmer_open == -1:
            raise ValueError(f"Target farmhand index {index} not found in raw XML.")
        farmer_open_end = farmer_open + len("<Farmer>")
        farmer_close = xml.find("</Farmer>", farmer_open_end, farmhands_close_start)
        if farmer_close == -1:
            raise ValueError("Closing tag </Farmer> not found for target farmhand.")
        farmer_close_end = farmer_close + len("</Farmer>")
        if count == index:
            return farmer_open, farmer_open_end, farmer_close, farmer_close_end
        count += 1
        pos = farmer_close_end


def extract_player_inner_from_main_save(xml_text: str) -> str:
    _, player_open_end, player_close_start, _ = find_tag_bounds(xml_text, "player")
    return xml_text[player_open_end:player_close_start]


def replace_savegameinfo_farmer_inner(savegameinfo_text: str, new_inner: str) -> str:
    open_start = savegameinfo_text.find("<Farmer")
    if open_start == -1:
        raise ValueError("Root <Farmer ...> not found in SaveGameInfo.")
    open_end = savegameinfo_text.find(">", open_start)
    if open_end == -1:
        raise ValueError("Malformed SaveGameInfo root <Farmer ...> tag.")
    open_end += 1
    close_start = savegameinfo_text.rfind("</Farmer>")
    if close_start == -1:
        raise ValueError("Closing tag </Farmer> not found in SaveGameInfo.")
    return savegameinfo_text[:open_end] + new_inner + savegameinfo_text[close_start:]


def swap_player_and_farmer_raw(xml_text: str, farmer_index: int) -> str:
    _, player_open_end, player_close_start, _ = find_tag_bounds(xml_text, "player")
    _, farmer_open_end, farmer_close_start, _ = find_nth_farmer_bounds(xml_text, farmer_index)

    player_inner = xml_text[player_open_end:player_close_start]
    farmer_inner = xml_text[farmer_open_end:farmer_close_start]

    replacements = [
        (player_open_end, player_close_start, farmer_inner),
        (farmer_open_end, farmer_close_start, player_inner),
    ]
    replacements.sort(key=lambda item: item[0])

    pieces: list[str] = []
    cursor = 0
    for start, end, repl in replacements:
        pieces.append(xml_text[cursor:start])
        pieces.append(repl)
        cursor = end
    pieces.append(xml_text[cursor:])
    return "".join(pieces)


def replace_player_and_farmer_inners(xml_text: str, farmer_index: int, new_player_inner: str, new_farmer_inner: str) -> str:
    _, player_open_end, player_close_start, _ = find_tag_bounds(xml_text, "player")
    _, farmer_open_end, farmer_close_start, _ = find_nth_farmer_bounds(xml_text, farmer_index)

    replacements = [
        (player_open_end, player_close_start, new_player_inner),
        (farmer_open_end, farmer_close_start, new_farmer_inner),
    ]
    replacements.sort(key=lambda item: item[0])

    pieces: list[str] = []
    cursor = 0
    for start, end, repl in replacements:
        pieces.append(xml_text[cursor:start])
        pieces.append(repl)
        cursor = end
    pieces.append(xml_text[cursor:])
    return "".join(pieces)
