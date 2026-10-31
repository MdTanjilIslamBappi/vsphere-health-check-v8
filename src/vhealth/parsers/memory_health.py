"""Parse ESXi's own built-in memory-health verdict.

Source: ``var/lib/vmware/osdata/healthd/vmw.memoryHealth-*.json`` -- one
of ``healthd``'s periodic self-checks (every 5 minutes, observed), kept
as several rotated snapshots rather than a single file. Each snapshot
carries two independent sub-states: ``hardware_info.hardware_state``
(physical/ECC memory health, plus corrected/uncorrected error tallies
since boot) and ``reservation_info.reservation_state`` (the host's
memory-reservation admission-control health). Both are ESXi's own
"Green"/"Yellow"/"Red"-style verdict, not something vhealth infers from
raw counters.

The rotated filenames (``-0``, ``-1``, ``-2``, ...) are not in
chronological order -- each snapshot's own ``structured.time`` field is,
so the most recent snapshot is selected by parsing and comparing that
timestamp, not by filename.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_HEALTHD_RELATIVE_DIR = Path("var") / "lib" / "vmware" / "osdata" / "healthd"
_GLOB = "vmw.memoryHealth-*.json"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    healthd_dir = host_dir / _HEALTHD_RELATIVE_DIR
    if not healthd_dir.is_dir():
        return [f"{_HEALTHD_RELATIVE_DIR} not found; memory-health status unavailable"]

    paths = sorted(healthd_dir.glob(_GLOB))
    if not paths:
        return [
            f"No {_GLOB} files found under {_HEALTHD_RELATIVE_DIR}; "
            "memory-health status unavailable"
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
            f"None of the {len(paths)} {_GLOB} file(s) contained a recognisable "
            "structured.time; memory-health status unavailable"
        )
        return warnings

    unstructured = latest_data.get("unstructured")
    if not isinstance(unstructured, dict):
        warnings.append("Most recent vmw.memoryHealth snapshot had no 'unstructured' section")
        return warnings

    hardware_info = unstructured.get("hardware_info")
    if isinstance(hardware_info, dict):
        state = hardware_info.get("hardware_state")
        if isinstance(state, str):
            host.memory_hardware_state = state
        corrected = hardware_info.get("total_corrected_errors_since_boot")
        if isinstance(corrected, int):
            host.memory_corrected_errors_since_boot = corrected
        uncorrected = hardware_info.get("total_uncorrected_errors_since_boot")
        if isinstance(uncorrected, int):
            host.memory_uncorrected_errors_since_boot = uncorrected

    reservation_info = unstructured.get("reservation_info")
    if isinstance(reservation_info, dict):
        state = reservation_info.get("reservation_state")
        if isinstance(state, str):
            host.memory_reservation_state = state

    host.memory_health_data_available = True
    return warnings
