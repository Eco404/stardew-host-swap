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


@dataclass
class SwapOptions:
    basic_swap: bool = True
    fix_home_location: bool = True
    fix_farmhand_reference: bool = True
    fix_house_interior: bool = False
    fix_mail_received: bool = True
    fix_user_id: bool = True
    sync_savegameinfo: bool = True
