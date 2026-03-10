from __future__ import annotations

import xml.etree.ElementTree as ET

from .utils import text


WRAPPER_PREFIX = (
    '<Wrapper xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
)
WRAPPER_SUFFIX = "</Wrapper>"


def get_mailreceived_list_from_farmer_elem(farmer_elem: ET.Element) -> list[str]:
    mail_elem = farmer_elem.find("mailReceived")
    if mail_elem is None:
        return []
    values: list[str] = []
    for child in list(mail_elem):
        if child.tag == "string":
            values.append(text(child))
    return values


def ordered_union(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in primary + secondary:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _wrap_inner_xml(inner_xml: str) -> ET.Element:
    wrapped = WRAPPER_PREFIX + inner_xml + WRAPPER_SUFFIX
    return ET.fromstring(wrapped.encode("utf-8"))


def _unwrap_wrapper_children(wrapper_root: ET.Element) -> str:
    return "".join(ET.tostring(child, encoding="unicode") for child in list(wrapper_root))


def set_mailreceived_on_wrapped_inner(inner_xml: str, new_mail_values: list[str]) -> str:
    wrapper_root = _wrap_inner_xml(inner_xml)
    mail_elem = wrapper_root.find("mailReceived")
    if mail_elem is None:
        raise ValueError("mailReceived not found in player/farmhand inner XML.")

    for child in list(mail_elem):
        mail_elem.remove(child)
    mail_elem.text = None

    for value in new_mail_values:
        child = ET.SubElement(mail_elem, "string")
        child.text = value

    return _unwrap_wrapper_children(wrapper_root)


def set_single_simple_tag_on_wrapped_inner(inner_xml: str, tag_name: str, new_value: str) -> str:
    wrapper_root = _wrap_inner_xml(inner_xml)
    elem = wrapper_root.find(tag_name)
    if elem is None:
        raise ValueError(f"{tag_name} not found in player/farmhand inner XML.")
    elem.text = new_value
    return _unwrap_wrapper_children(wrapper_root)


def get_single_simple_tag_from_farmer_elem(farmer_elem: ET.Element, tag_name: str) -> str:
    return text(farmer_elem.find(tag_name))


def swap_simple_tag_values_by_ids(xml_text: str, tag_names: list[str], id_a: str, id_b: str) -> tuple[str, dict[str, int]]:
    counts = {tag: 0 for tag in tag_names}
    out = xml_text

    for tag in tag_names:
        open_tag = f"<{tag}>"
        close_tag = f"</{tag}>"
        start = 0
        pieces: list[str] = []
        changed = 0

        while True:
            open_idx = out.find(open_tag, start)
            if open_idx == -1:
                pieces.append(out[start:])
                break

            value_start = open_idx + len(open_tag)
            close_idx = out.find(close_tag, value_start)
            if close_idx == -1:
                raise ValueError(f"Malformed XML while scanning <{tag}> values.")

            pieces.append(out[start:value_start])
            raw_value = out[value_start:close_idx]
            stripped = raw_value.strip()

            if stripped == id_a:
                left_ws_len = len(raw_value) - len(raw_value.lstrip())
                right_ws_len = len(raw_value) - len(raw_value.rstrip())
                new_raw = raw_value[:left_ws_len] + id_b + (raw_value[len(raw_value) - right_ws_len:] if right_ws_len else "")
                pieces.append(new_raw)
                changed += 1
            elif stripped == id_b:
                left_ws_len = len(raw_value) - len(raw_value.lstrip())
                right_ws_len = len(raw_value) - len(raw_value.rstrip())
                new_raw = raw_value[:left_ws_len] + id_a + (raw_value[len(raw_value) - right_ws_len:] if right_ws_len else "")
                pieces.append(new_raw)
                changed += 1
            else:
                pieces.append(raw_value)

            pieces.append(close_tag)
            start = close_idx + len(close_tag)

        out = "".join(pieces)
        counts[tag] = changed

    return out, counts
