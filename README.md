# Glean Go Link Migration Tool

Migrate go links (shortcuts) between Glean instances. Export from a source instance, import into a destination, and roll back if needed.

## Prerequisites

- Python 3.10+
- An API token for each Glean instance (source and destination)

## 1. Install

```bash
pip install -r requirements.txt
```

## 2. Create API Tokens

You need one token per instance. Both require the **SHORTCUTS** scope.

1. Go to **Admin Console > Platform > API Tokens** (`https://app.glean.com/admin/platform/tokenManagement?tab=client`).
2. Click **Add New Token**.
3. Set **Permissions** to **USER**, **Scopes** to **SHORTCUTS**, and choose an expiration date.
4. Click **Create** and copy the token immediately — it is only shown once.
5. Repeat for the other instance.

To verify a token works:

```bash
curl -X POST https://<instance>-be.glean.com/rest/api/v1/listshortcuts \
  -H 'Authorization: Bearer <TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"pageSize": 1}'
```

A `200` response with a `shortcuts` array means the token is valid.

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env` with your instance URLs and tokens:

```
GLEAN_SOURCE_URL=https://<source-instance>-be.glean.com
GLEAN_SOURCE_TOKEN=<token>

GLEAN_DEST_URL=https://<dest-instance>-be.glean.com
GLEAN_DEST_TOKEN=<token>
```

The `.env` file is loaded automatically and git-ignored.

## 4. Export

```bash
python migrate.py export --backup-dir ./backups
```

This fetches all go links from the source instance and saves them to a timestamped JSON file in `./backups/`.

## 5. Import

Run a dry run first to preview what will happen:

```bash
python migrate.py import \
  --backup ./backups/go_links_backup_<timestamp>.json \
  --dry-run
```

Then run the real import:

```bash
python migrate.py import \
  --backup ./backups/go_links_backup_<timestamp>.json
```

The import produces a result log (`migration_result_<timestamp>.json`) recording every action taken.

### Conflict handling

If a go link alias already exists in the destination, the `--on-conflict` flag controls behavior:

| Value | Behavior |
|-------|----------|
| `skip` (default) | Leave the existing destination go link untouched |
| `overwrite` | Update the destination go link with source data |
| `fail` | Abort the entire import on first conflict |

## 6. Roll Back (if needed)

```bash
python migrate.py restore \
  --result-log ./migration_result_<timestamp>.json \
  --force
```

This deletes only the go links that were **created** during the import. Updated and skipped entries are left untouched. Omit `--force` to get a confirmation prompt before deletion.

## Additional Flags

| Flag | Description |
|------|-------------|
| `-v` | Enable verbose/debug logging (must appear before the subcommand) |
| `--dry-run` | Simulate without making changes (works with `import` and `restore`) |
| `--on-conflict` | Conflict strategy: `skip`, `overwrite`, or `fail` (default: `skip`) |
| `--page-size N` | Page size when listing shortcuts (default: 100) |
| `--max-retries N` | Max retries on rate-limit/server errors (default: 5) |

## Limitations

- Go link **ownership** transfers to the API token holder. Original authorship is recorded in the backup file but cannot be preserved.
- Go link **IDs** are instance-specific and not preserved across instances.
- **Roles** are migrated only if the referenced users/groups exist in the destination instance.
