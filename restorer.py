from __future__ import annotations

import logging
from pathlib import Path

from api_client import GleanClient
from models import MigrationAction, MigrationResultEntry, load_results

logger = logging.getLogger(__name__)


async def restore(
    dest_client: GleanClient,
    result_log_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Roll back a migration by deleting shortcuts that were created.

    Only entries with action=CREATED and a valid dest_id are deleted.
    Updated and skipped entries are left untouched.
    """
    results = load_results(result_log_path)
    to_delete = [
        r
        for r in results
        if r.action == MigrationAction.CREATED and r.dest_id is not None
    ]

    if not to_delete:
        logger.info("No created shortcuts to roll back")
        return

    logger.info("Found %d shortcuts to delete", len(to_delete))

    if not force:
        aliases = ", ".join(r.alias for r in to_delete[:10])
        suffix = f" ... and {len(to_delete) - 10} more" if len(to_delete) > 10 else ""
        answer = input(
            f"About to delete {len(to_delete)} shortcuts ({aliases}{suffix}). "
            "Continue? [y/N] "
        )
        if answer.strip().lower() != "y":
            logger.info("Restore cancelled by user")
            return

    deleted = 0
    failed = 0
    for entry in to_delete:
        if dry_run:
            logger.info(
                "DRY-RUN: would delete alias %r (id=%s)", entry.alias, entry.dest_id
            )
            deleted += 1
            continue

        try:
            await dest_client.delete_shortcut(entry.dest_id)  # type: ignore[arg-type]
            logger.info("Deleted alias %r (id=%s)", entry.alias, entry.dest_id)
            deleted += 1
        except Exception as exc:
            logger.error(
                "Failed to delete alias %r (id=%s): %s",
                entry.alias,
                entry.dest_id,
                exc,
            )
            failed += 1

    logger.info("Restore complete: %d deleted, %d failed", deleted, failed)
