"""Shared helper for ESXi's own built-in ``healthd`` self-checks.

Source: rotated JSON snapshots under
``var/lib/vmware/osdata/healthd/<check_name>-*.json`` -- each ``healthd``
check (memory, NFS datastores, core services, ...) keeps several recent
snapshots a few minutes apart instead of one file. The rotated filenames
(``-0``, ``-1``, ``-2``, ...) are not in chronological order, so every
healthd-based parser must select by each snapshot's own
``structured.time`` field, not filename -- this helper does that once
for all of them.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

HEALTHD_RELATIVE_DIR = Path("var") / "lib" / "vmware" / "osdata" / "healthd"


def latest_snapshot(host_dir: Path, check_name: str) -> tuple[dict | None, list[str]]:
    """Return the most-recent-by-timestamp snapshot for ``check_name`` under

    ``host_dir``, plus any warnings encountered. The first element is
    ``None`` if no usable snapshot was found (missing directory, no
    matching files, or none with a parseable ``structured.time``).
    """
    healthd_dir = host_dir / HEALTHD_RELATIVE_DIR
    glob = f"{check_name}-*.json"
    if not healthd_dir.is_dir():
        return None, [f"{HEALTHD_RELATIVE_DIR} not found; {check_name} status unavailable"]

    paths = sorted(healthd_dir.glob(glob))
    if not paths:
        return None, [
            f"No {glob} files found under {HEALTHD_RELATIVE_DIR}; "
            f"{check_name} status unavailable"
        ]

    latest_time: datetime | None = None
    latest_data: dict | None = None
    warnings: list[str] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            warnings.append(f"{path.name} did not contain valid JSON; skipped")
            continue
        if not isinstance(data, dict):
            continue
        structured = data.get("structured")
        time_str = structured.get("time") if isinstance(structured, dict) else None
        if not isinstance(time_str, str):
            continue
        try:
            snapshot_time = datetime.fromisoformat(time_str)
        except ValueError:
            continue
        if latest_time is None or snapshot_time > latest_time:
            latest_time = snapshot_time
            latest_data = data

    if latest_data is None:
        warnings.append(
            f"None of the {len(paths)} {glob} file(s) contained a recognisable "
            f"structured.time; {check_name} status unavailable"
        )
    return latest_data, warnings
