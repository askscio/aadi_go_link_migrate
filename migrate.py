#!/usr/bin/env python3
"""CLI tool to migrate Glean go links between instances."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from api_client import GleanClient
from config import ConflictStrategy, MigrationConfig
from exporter import export_all
from importer import import_all
from restorer import restore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate Glean go links between instances"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- export ---
    exp = sub.add_parser("export", help="Export go links from a source instance")
    exp.add_argument("--source-url", help="Source Glean API base URL (or GLEAN_SOURCE_URL)")
    exp.add_argument("--source-token", help="Source API token (or GLEAN_SOURCE_TOKEN)")
    exp.add_argument(
        "--output",
        type=Path,
        help="Output backup file path (default: auto-timestamped in --backup-dir)",
    )
    exp.add_argument(
        "--backup-dir", type=Path, default=Path("."), help="Directory for backup files"
    )
    exp.add_argument("--page-size", type=int, default=100, help="Page size for listing")
    exp.add_argument("--max-retries", type=int, default=5)

    # --- import ---
    imp = sub.add_parser("import", help="Import go links into a destination instance")
    imp.add_argument("--backup", type=Path, required=True, help="Backup JSON file to import")
    imp.add_argument("--dest-url", help="Destination Glean API base URL (or GLEAN_DEST_URL)")
    imp.add_argument("--dest-token", help="Destination API token (or GLEAN_DEST_TOKEN)")
    imp.add_argument(
        "--on-conflict",
        choices=["skip", "overwrite", "fail"],
        default="skip",
        help="How to handle existing aliases (default: skip)",
    )
    imp.add_argument("--dry-run", action="store_true", help="Simulate without making changes")
    imp.add_argument(
        "--backup-dir", type=Path, default=Path("."), help="Directory for result log"
    )
    imp.add_argument("--max-retries", type=int, default=5)

    # --- restore ---
    rst = sub.add_parser("restore", help="Roll back a migration using the result log")
    rst.add_argument(
        "--result-log", type=Path, required=True, help="Migration result log JSON"
    )
    rst.add_argument("--dest-url", help="Destination Glean API base URL (or GLEAN_DEST_URL)")
    rst.add_argument("--dest-token", help="Destination API token (or GLEAN_DEST_TOKEN)")
    rst.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    rst.add_argument("--dry-run", action="store_true", help="Simulate without making changes")
    rst.add_argument("--max-retries", type=int, default=5)

    return parser


async def _run_export(args: argparse.Namespace) -> None:
    config = MigrationConfig.from_env(
        source_api_token=args.source_token,
        source_base_url=args.source_url,
        page_size=args.page_size,
        max_retries=args.max_retries,
        backup_dir=args.backup_dir,
    )
    if not config.source_api_token or not config.source_base_url:
        sys.exit("Source token and URL are required (--source-token/--source-url or env vars)")

    client = GleanClient(
        config.source_api_token, config.source_base_url, config.max_retries
    )
    try:
        backup_dir = args.output.parent if args.output else config.backup_dir
        path = await export_all(client, backup_dir, config.page_size)
        if args.output and args.output != path:
            path.rename(args.output)
            path = args.output
        print(f"Export complete: {path}")
    finally:
        client.close()


async def _run_import(args: argparse.Namespace) -> None:
    config = MigrationConfig.from_env(
        dest_api_token=args.dest_token,
        dest_base_url=args.dest_url,
        on_conflict=ConflictStrategy(args.on_conflict),
        dry_run=args.dry_run,
        max_retries=args.max_retries,
        backup_dir=args.backup_dir,
    )
    if not config.dest_api_token or not config.dest_base_url:
        sys.exit("Destination token and URL are required (--dest-token/--dest-url or env vars)")

    dest_client = GleanClient(
        config.dest_api_token, config.dest_base_url, config.max_retries
    )
    try:
        result_path = await import_all(dest_client, args.backup, config)
        print(f"Import complete. Result log: {result_path}")
    finally:
        dest_client.close()


async def _run_restore(args: argparse.Namespace) -> None:
    config = MigrationConfig.from_env(
        dest_api_token=args.dest_token,
        dest_base_url=args.dest_url,
        max_retries=args.max_retries,
    )
    if not config.dest_api_token or not config.dest_base_url:
        sys.exit("Destination token and URL are required (--dest-token/--dest-url or env vars)")

    dest_client = GleanClient(
        config.dest_api_token, config.dest_base_url, config.max_retries
    )
    try:
        await restore(
            dest_client,
            args.result_log,
            force=args.force,
            dry_run=args.dry_run,
        )
        print("Restore complete.")
    finally:
        dest_client.close()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    dispatch = {
        "export": _run_export,
        "import": _run_import,
        "restore": _run_restore,
    }
    asyncio.run(dispatch[args.command](args))


if __name__ == "__main__":
    main()
