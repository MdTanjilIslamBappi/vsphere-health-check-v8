"""Parse ESXi's own built-in per-SSD/NVMe-device operational verdict.

Source: ``var/lib/vmware/osdata/healthd/vmw.ssdStorageHealth-*.json``
(see ``parsers/_healthd.py`` for how the most recent rotated snapshot is
selected). Like ``vmw.nfsDatastoreHealth``, the ``unstructured`` section
is a list -- one entry per SSD/NVMe device healthd tracks on this host.
An empty list means no such device is tracked here (e.g. only
spinning/SAS disks present), not that the check is unavailable.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo, SsdStorageDevice
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "vmw.ssdStorageHealth"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
    if not isinstance(unstructured, list):
        warnings.append("Most recent vmw.ssdStorageHealth snapshot had no 'unstructured' list")
        return warnings

    devices = [d for d in (_parse_entry(e) for e in unstructured) if d is not None]
    host.ssd_health_data_available = True
    host.ssd_devices = devices
    return warnings


def _parse_entry(entry: object) -> SsdStorageDevice | None:
    if not isinstance(entry, dict):
        return None
    device = entry.get("device")
    if not device:
        return None
    state_enum = entry.get("device_state_enum")
    return SsdStorageDevice(
        device=str(device),
        model=entry.get("model") or None,
        vendor=entry.get("vendor") or None,
        device_state=entry.get("device_state") or None,
        device_state_enum=int(state_enum) if isinstance(state_enum, int) else None,
    )
