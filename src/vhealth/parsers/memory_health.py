"""Parse ESXi's own built-in memory-health verdict.

Source: ``var/lib/vmware/osdata/healthd/vmw.memoryHealth-*.json`` -- one
of ``healthd``'s periodic self-checks (every 5 minutes, observed), kept
as several rotated snapshots rather than a single file (see
``parsers/_healthd.py`` for how the most recent one is selected). Each
snapshot carries two independent sub-states: ``hardware_info.hardware_state``
(physical/ECC memory health, plus corrected/uncorrected error tallies
since boot) and ``reservation_info.reservation_state`` (the host's
memory-reservation admission-control health). Both are ESXi's own
"Green"/"Yellow"/"Red"-style verdict, not something vhealth infers from
raw counters.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "vmw.memoryHealth"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
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
