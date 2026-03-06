from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from glean.api_client import models

from api_client import GleanClient
from config import ConflictStrategy, MigrationConfig
from models import (
    GoLinkRecord,
    MigrationAction,
    MigrationResultEntry,
    load_records,
    save_results,
)

logger = logging.getLogger(__name__)


def _build_mutable_props(record: GoLinkRecord) -> models.ShortcutMutableProperties:
    return models.ShortcutMutableProperties(
        input_alias=record.input_alias,
        destination_url=record.destination_url or None,
        description=record.description or None,
        unlisted=record.unlisted if record.unlisted else None,
        url_template=record.url_template or None,
    )


async def _process_record(
    record: GoLinkRecord,
    dest_client: GleanClient,
    config: MigrationConfig,
) -> MigrationResultEntry:
    alias = record.input_alias

    try:
        existing = await dest_client.get_shortcut_by_alias(alias)
    except Exception as exc:
        logger.error("Failed to check alias %r in destination: %s", alias, exc)
        return MigrationResultEntry(
            alias=alias, action=MigrationAction.FAILED, error=str(exc)
        )

    if existing is not None:
        if config.on_conflict == ConflictStrategy.SKIP:
            logger.info("SKIP: alias %r already exists (id=%s)", alias, existing.id)
            return MigrationResultEntry(
                alias=alias, action=MigrationAction.SKIPPED, dest_id=existing.id
            )

        if config.on_conflict == ConflictStrategy.FAIL:
            msg = f"Alias {alias!r} already exists and --on-conflict=fail"
            logger.error(msg)
            raise RuntimeError(msg)

        # overwrite
        if config.dry_run:
            logger.info("DRY-RUN: would UPDATE alias %r (id=%s)", alias, existing.id)
            return MigrationResultEntry(
                alias=alias, action=MigrationAction.UPDATED, dest_id=existing.id
            )

        try:
            updated = await dest_client.update_shortcut(
                existing.id,  # type: ignore[arg-type]
                input_alias=record.input_alias,
                destination_url=record.destination_url or None,
                description=record.description or None,
                unlisted=record.unlisted if record.unlisted else None,
                url_template=record.url_template or None,
            )
            dest_id = updated.id if updated else existing.id
            logger.info("UPDATED: alias %r -> id=%s", alias, dest_id)
            return MigrationResultEntry(
                alias=alias, action=MigrationAction.UPDATED, dest_id=dest_id
            )
        except Exception as exc:
            logger.error("Failed to update alias %r: %s", alias, exc)
            return MigrationResultEntry(
                alias=alias, action=MigrationAction.FAILED, error=str(exc)
            )

    # Does not exist -- create
    if config.dry_run:
        logger.info("DRY-RUN: would CREATE alias %r", alias)
        return MigrationResultEntry(alias=alias, action=MigrationAction.CREATED)

    try:
        props = _build_mutable_props(record)
        created = await dest_client.create_shortcut(props)
        dest_id = created.id if created else None
        logger.info("CREATED: alias %r -> id=%s", alias, dest_id)
        return MigrationResultEntry(
            alias=alias, action=MigrationAction.CREATED, dest_id=dest_id
        )
    except Exception as exc:
        logger.error("Failed to create alias %r: %s", alias, exc)
        return MigrationResultEntry(
            alias=alias, action=MigrationAction.FAILED, error=str(exc)
        )


async def import_all(
    dest_client: GleanClient,
    backup_path: Path,
    config: MigrationConfig,
) -> Path:
    """Import go links from a backup file into the destination instance.

    Returns the path to the migration result log.
    """
    records = load_records(backup_path)
    logger.info("Loaded %d records from %s", len(records), backup_path)

    results: list[MigrationResultEntry] = []

    for i, record in enumerate(records, 1):
        logger.info("Processing %d/%d: %r", i, len(records), record.input_alias)
        entry = await _process_record(record, dest_client, config)
        results.append(entry)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_path = config.backup_dir / f"migration_result_{timestamp}.json"
    save_results(results, result_path)

    created = sum(1 for r in results if r.action == MigrationAction.CREATED)
    updated = sum(1 for r in results if r.action == MigrationAction.UPDATED)
    skipped = sum(1 for r in results if r.action == MigrationAction.SKIPPED)
    failed = sum(1 for r in results if r.action == MigrationAction.FAILED)
    logger.info(
        "Import complete: %d created, %d updated, %d skipped, %d failed",
        created,
        updated,
        skipped,
        failed,
    )
    logger.info("Result log written to %s", result_path)

    return result_path
