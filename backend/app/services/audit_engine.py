"""
Module: Enterprise Features — Audit Logging.

`build_audit_entry` records who did what to what, when. `diff_fields` is
the genuinely useful piece: given a before/after snapshot of a record (e.g.
a journal entry that got edited), it computes exactly which fields changed
— so an auditor reviewing the log sees "amount: 50000 -> 75000" instead of
just "record was edited".
"""
from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class AuditEntry:
    user_id: str
    org_id: str | None
    action: str          # e.g. "create", "edit", "delete", "approve"
    entity_type: str     # e.g. "journal_entry", "user", "invoice"
    entity_id: str
    changes: dict | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def diff_fields(before: dict | None, after: dict | None) -> dict:
    """Compute field-level changes between two snapshots of a record.
    - before=None means a new record was created (all fields are "added").
    - after=None means the record was deleted (all fields are "removed").
    Returns {field: {"before": ..., "after": ...}} for only the fields that
    actually changed — unchanged fields are omitted to keep log entries
    readable.
    """
    if before is None and after is None:
        return {}
    if before is None:
        return {k: {"before": None, "after": v} for k, v in (after or {}).items()}
    if after is None:
        return {k: {"before": v, "after": None} for k, v in (before or {}).items()}

    changed = {}
    all_keys = set(before) | set(after)
    for key in all_keys:
        old_val = before.get(key)
        new_val = after.get(key)
        if old_val != new_val:
            changed[key] = {"before": old_val, "after": new_val}
    return changed


def build_audit_entry(
    user_id: str, org_id: str | None, action: str, entity_type: str, entity_id: str,
    before: dict | None = None, after: dict | None = None,
) -> AuditEntry:
    changes = diff_fields(before, after) if (before is not None or after is not None) else None
    return AuditEntry(
        user_id=user_id, org_id=org_id, action=action,
        entity_type=entity_type, entity_id=entity_id, changes=changes,
    )
