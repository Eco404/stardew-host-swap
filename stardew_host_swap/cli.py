from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .parsing import list_farmhands, parse_root
from .paths import resolve_paths
from .reporting import generate_report
from .service import perform_swap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stardew Valley host swap tool")
    parser.add_argument("input_path", type=Path, help="Path to the main save XML file, or directly to the save folder.")
    parser.add_argument(
        "--output-main",
        type=Path,
        help="Deprecated. The current version operates in-place only and creates *_bak backups before overwriting.",
    )
    parser.add_argument("--target-name", help="Target farmhand name to promote to host.")
    parser.add_argument("--target-id", help="Target farmhand UniqueMultiplayerID to promote to host.")
    parser.add_argument("--list", action="store_true", help="List host/farmhands and exit.")
    parser.add_argument("--report", action="store_true", help="Preview changes without writing files.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.target_name and not args.target_id and not args.list:
        print("Provide --target-name or --target-id, or use --list.", file=sys.stderr)
        return 2

    try:
        resolved = resolve_paths(args.input_path, output_main=args.output_main, report=args.report)
        root = parse_root(resolved.main_save_in)

        if args.list:
            print(list_farmhands(root))
            return 0

        if args.report:
            print(
                generate_report(
                    resolved.main_save_in,
                    target_name=args.target_name,
                    target_id=args.target_id,
                    resolved=resolved,
                )
            )
            return 0

        perform_swap(
            resolved.main_save_in,
            resolved.output_main,
            target_name=args.target_name,
            target_id=args.target_id,
            savegameinfo_in=resolved.savegameinfo_in,
            output_savegameinfo=resolved.output_savegameinfo,
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
