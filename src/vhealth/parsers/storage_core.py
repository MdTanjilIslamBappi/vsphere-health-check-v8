"""Parse storage HBA/controller and device inventory.

Sources (JSON preferred over the text-table equivalents, since ESXi 7+
ships a machine-readable copy of every localcli command under ``json/``):

* ``json/localcli_storage-core-adapter-list.json``
* ``json/localcli_storage-core-device-list.json``
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo, StorageAdapter, StorageDevice
from vhealth.parsers.table_utils import load_json_array

VERSION = "1.0.0"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    warnings: list[str] = []
    json_dir = host_dir / "json"

    adapters = load_json_array(json_dir / "localcli_storage-core-adapter-list.json")
    if adapters:
        for entry in adapters:
            host.storage_adapters.append(
                StorageAdapter(
                    device=entry.get("HBA Name", "unknown"),
                    driver=entry.get("Driver"),
                    description=entry.get("Description"),
                    link_state=entry.get("Link State"),
                    uid=entry.get("UID"),
                )
            )
    else:
        warnings.append(
            "localcli_storage-core-adapter-list.json missing or empty; "
            "storage adapter inventory unavailable"
        )

    devices = load_json_array(json_dir / "localcli_storage-core-device-list.json")
    if devices:
        for entry in devices:
            host.storage_devices.append(
                StorageDevice(
                    device=entry.get("Device", "unknown"),
                    display_name=entry.get("Display Name"),
                    vendor=_clean(entry.get("Vendor")),
                    model=_clean(entry.get("Model")),
                    is_ssd=entry.get("Is SSD"),
                    is_local=entry.get("Is Local"),
                    size_mib=entry.get("Size"),
                    raid_level=entry.get("RAID Level"),
                    status=entry.get("Status"),
                    multipath_plugin=entry.get("Multipath Plugin"),
                )
            )
    else:
        warnings.append(
            "localcli_storage-core-device-list.json missing or empty; "
            "storage device inventory unavailable"
        )

    return warnings


def _clean(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value
