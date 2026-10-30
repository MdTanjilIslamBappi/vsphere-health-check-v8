"""Parse ``commands/smartinfo.txt`` (per-device SMART health).

The file concatenates one record per storage device. Devices behind a
SAN/HBA that does not expose SMART (the common case for Fibre Channel or
iSCSI LUNs) produce a one-line failure record; local SAS/SATA/NVMe disks
produce a small attribute table::

    Failed to get SMART stats for naa.xxxx error Cannot open device

    SMART Data for Disk : naa.yyyy
    Parameter                       Value  Threshold Worst  Raw
    -----------------------------------------------------------
    Health Status                   OK     N/A        N/A    N/A
    Reallocated Sector Count        0      90         N/A    N/A
    Drive Temperature               28     N/A        N/A    N/A

Only ``Health Status`` and ``Reallocated Sector Count`` are used for
findings; the ``Threshold``/``Worst`` columns are populated inconsistently
across controllers/drivers and are not used for pass/fail decisions.
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_RECORD_START_RE = re.compile(
    r"^Failed to get SMART stats for\s*(?P<dev_failed>\S*)\s*error\s*(?P<err>.+?)\s*$"
    r"|^SMART Data for Disk\s*:\s*(?P<dev_ok>\S+)\s*$",
    re.MULTILINE,
)
_FIELD_SPLIT_RE = re.compile(r"\t+|\s{2,}")


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    smart_path = host_dir / "commands" / "smartinfo.txt"
    if not smart_path.is_file():
        return ["smartinfo.txt not found; SMART health data unavailable"]

    text = smart_path.read_text(encoding="utf-8", errors="replace")
    matches = list(_RECORD_START_RE.finditer(text))
    if not matches:
        return ["smartinfo.txt did not match the expected format"]

    devices_by_id = {d.device: d for d in host.storage_devices}

    for i, m in enumerate(matches):
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end() : block_end]

        if m.group("dev_ok"):
            device_id = m.group("dev_ok")
            attrs = _parse_attribute_table(block)
            device = devices_by_id.get(device_id)
            if device is not None:
                device.smart_raw = attrs
                device.smart_overall_health = attrs.get("Health Status")
        # A "Failed to get SMART stats" record is expected and not an error
        # in itself (e.g. SAN LUNs do not expose SMART over FC/iSCSI); it
        # is simply not recorded as device-level SMART data.

    return []


def _parse_attribute_table(block: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or set(line.strip()) == {"-"}:
            continue
        parts = [p for p in _FIELD_SPLIT_RE.split(line.strip()) if p != ""]
        if len(parts) >= 2 and parts[0] != "Parameter":
            attrs[parts[0].strip()] = parts[1].strip()
    return attrs
