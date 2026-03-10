from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import ResolvedPaths


def resolve_paths(input_path: Path, *, output_main: Optional[Path], report: bool) -> ResolvedPaths:
    input_path = input_path.expanduser().resolve()

    if output_main is not None:
        raise ValueError("The current version operates in-place only. Do not pass --output-main.")

    if input_path.is_dir():
        folder = input_path
        main_in = folder / folder.name
        if not main_in.exists():
            raise FileNotFoundError(f"Main save file not found inside folder: {main_in}")

        savegameinfo_in = folder / "SaveGameInfo"
        if not savegameinfo_in.exists():
            savegameinfo_in = None

        out_main = None if report else main_in
        out_savegameinfo = None if report else savegameinfo_in

        return ResolvedPaths(
            main_save_in=main_in,
            output_main=out_main,
            mode="folder",
            savegameinfo_in=savegameinfo_in,
            output_savegameinfo=out_savegameinfo,
            source_folder=folder,
            output_folder=folder,
        )

    if not input_path.exists():
        raise FileNotFoundError(f"Main save file not found: {input_path}")

    return ResolvedPaths(
        main_save_in=input_path,
        output_main=None if report else input_path,
        mode="file",
    )
