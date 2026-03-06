from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass
class GoLinkRecord:
    """Serializable representation of a go link for backup/restore."""

    input_alias: str
    destination_url: str
    description: str = ""
    unlisted: bool = False
    url_template: str = ""
    created_by_name: str = ""
    created_by_email: str = ""
    create_time: str = ""
    is_external: bool = False
    roles: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoLinkRecord:
        return cls(
            input_alias=data["input_alias"],
            destination_url=data.get("destination_url", ""),
            description=data.get("description", ""),
            unlisted=data.get("unlisted", False),
            url_template=data.get("url_template", ""),
            created_by_name=data.get("created_by_name", ""),
            created_by_email=data.get("created_by_email", ""),
            create_time=data.get("create_time", ""),
            is_external=data.get("is_external", False),
            roles=data.get("roles", []),
        )

    @classmethod
    def from_shortcut(cls, shortcut: Any) -> GoLinkRecord:
        """Convert a Glean SDK Shortcut model to a GoLinkRecord."""
        created_by_name = ""
        created_by_email = ""
        if shortcut.created_by:
            created_by_name = getattr(shortcut.created_by, "name", "") or ""
            created_by_email = getattr(shortcut.created_by, "email", "") or ""

        create_time = ""
        if shortcut.create_time:
            create_time = shortcut.create_time.isoformat()

        roles_data: list[dict[str, Any]] = []
        if shortcut.roles:
            for role_spec in shortcut.roles:
                entry: dict[str, Any] = {"role": str(role_spec.role)}
                if role_spec.person:
                    entry["person_name"] = getattr(role_spec.person, "name", "")
                    entry["person_email"] = getattr(role_spec.person, "email", "")
                if role_spec.group:
                    entry["group_name"] = getattr(role_spec.group, "name", "")
                roles_data.append(entry)

        return cls(
            input_alias=shortcut.input_alias,
            destination_url=shortcut.destination_url or "",
            description=shortcut.description or "",
            unlisted=shortcut.unlisted or False,
            url_template=shortcut.url_template or "",
            created_by_name=created_by_name,
            created_by_email=created_by_email,
            create_time=create_time,
            is_external=shortcut.is_external or False,
            roles=roles_data,
        )


class MigrationAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class MigrationResultEntry:
    alias: str
    action: MigrationAction
    dest_id: int | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "action": self.action.value,
            "dest_id": self.dest_id,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MigrationResultEntry:
        return cls(
            alias=data["alias"],
            action=MigrationAction(data["action"]),
            dest_id=data.get("dest_id"),
            error=data.get("error", ""),
        )


def save_records(records: list[GoLinkRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in records], f, indent=2)


def load_records(path: Path) -> list[GoLinkRecord]:
    with open(path) as f:
        return [GoLinkRecord.from_dict(d) for d in json.load(f)]


def save_results(results: list[MigrationResultEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)


def load_results(path: Path) -> list[MigrationResultEntry]:
    with open(path) as f:
        return [MigrationResultEntry.from_dict(d) for d in json.load(f)]
