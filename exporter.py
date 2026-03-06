from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from api_client import GleanClient
from models import GoLinkRecord, save_records

logger = logging.getLogger(__name__)


async def export_all(
    client: GleanClient,
    backup_dir: Path,
    page_size: int = 100,
) -> Path:
    """Export all shortcuts from the source instance to a timestamped JSON backup.

    Returns the path to the backup file.
    """
    logger.info("Starting export from source instance")
    shortcuts = await client.list_all_shortcuts(page_size=page_size)
    logger.info("Retrieved %d total shortcuts", len(shortcuts))

    records = [GoLinkRecord.from_shortcut(s) for s in shortcuts]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"go_links_backup_{timestamp}.json"
    save_records(records, backup_path)
    logger.info("Backup written to %s (%d records)", backup_path, len(records))

    return backup_path
