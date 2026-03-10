from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional


def text(elem: Optional[ET.Element]) -> str:
    return "" if elem is None or elem.text is None else elem.text
