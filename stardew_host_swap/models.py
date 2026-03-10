from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ResolvedPaths:
    main_save_in: Path
    output_main: Optional[Path]
    mode: str
    savegameinfo_in: Optional[Path] = None
    output_savegameinfo: Optional[Path] = None
    source_folder: Optional[Path] = None
    output_folder: Optional[Path] = None
