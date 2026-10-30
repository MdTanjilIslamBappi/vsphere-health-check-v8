"""Parse storage multipath state (esxcli storage nmp path list).

Source: ``commands/localcli_storage-nmp-path-list.txt`` -- a block-style
dump (not a fixed-width table): each physical path is a non-indented
header line (the path's own WWN-based identifier, ending in ``:``)
followed by indented ``Key: Value`` lines, one of which (``Device:``)
names the storage device this path leads to and another (``Group
State:``) reports that path's current state. ``active``/``active
unoptimized`` (ALUA) are healthy; ``dead`` means that specific path is
not usable right now. A device can have several path blocks (one per
HBA/target/LUN combination), so this parser aggregates per device
rather than reporting path blocks individually.
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import HostInfo, MultipathDevice

VERSION = "1.0.0"

_FILENAME = "localcli_storage-nmp-path-list.txt"
_FIELD_RE = re.compile(r"^ {3}([^:]+):\s?(.*)$")


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; storage multipath state unknown"]

    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = _split_blocks(text)
    if not blocks:
        return [f"{_FILENAME} did not match the expected block format"]

    host.multipath_data_available = True
    devices: dict[str, MultipathDevice] = {}
    for block in blocks:
        device_id = block.get("Device")
        if not device_id:
            continue
        device = devices.setdefault(
            device_id,
            MultipathDevice(device=device_id, display_name=block.get("Device Display Name")),
        )
        device.total_paths += 1
        if block.get("Group State") == "dead":
            device.dead_paths += 1
    host.multipath_devices = list(devices.values())
    return []


def _split_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        match = _FIELD_RE.match(line)
        if match and current is not None:
            current[match.group(1).strip()] = match.group(2).strip()
            continue
        # Any non-indented, non-blank line is a new path-block header.
        current = {}
        blocks.append(current)
    return blocks
