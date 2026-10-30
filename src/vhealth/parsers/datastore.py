"""Parse VMFS datastore name/UUID and their backing device IDs.

Source: ``commands/vmkfstools_-P--v-10-vmfsvolumes<name-or-uuid>.txt``, one
file per VMFS volume (the output of ``vmkfstools -P -v 10 /vmfs/volumes/<x>``
captured by vm-support). This gives a human-readable datastore name for the
bare ``naa.xxxx``/``t10.xxxx``/``eui.xxxx``/``mpx.xxxx`` device IDs that
storage/log findings would otherwise show on their own -- see
``HostInfo.datastore_for_naa``.

Not every volume has a device-backed extent (``OSDATA``, ``BOOTBANK*``,
``scratch``, ``productLocker`` are typically backed by something other than
a plain SCSI LUN, or have no device line at all); those are parsed for
completeness but simply end up with an empty ``naa_ids`` list.
"""

from __future__ import annotations

import re
from pathlib import Path

from vhealth.models.host import Datastore, HostInfo

VERSION = "1.0.0"

_GLOB = "vmkfstools_-P--v-10-vmfsvolumes*.txt"

_LABEL_PREFIX = "File system label (if any): "
_UUID_PREFIX = "UUID: "
_DEVICE_ID_RE = re.compile(r"\b(?:naa|t10|eui|mpx)\.[0-9a-zA-Z]+(?=:\d+\b)")

_UNLABELLED = {"", "none", "(cannot get label)"}


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    command_dir = host_dir / "commands"
    if not command_dir.is_dir():
        return ["commands/ directory not found; datastore name mapping unavailable"]

    files = sorted(command_dir.glob(_GLOB))
    if not files:
        return [
            "vmkfstools_-P--v-10-vmfsvolumes* not found; datastore name mapping unavailable"
        ]

    # vm-support runs vmkfstools once per UUID path and once per friendly-name
    # symlink under /vmfs/volumes, so the same volume is typically captured
    # in two files; de-duplicate on UUID (falling back to name) so a volume
    # is not listed twice.
    seen: set[str] = set()
    for path in files:
        _parse_one(path, host, seen)

    if not host.datastores:
        return ["no VMFS volume reported a usable file system label"]
    return []


def _parse_one(path: Path, host: HostInfo, seen: set[str]) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    label: str | None = None
    uuid: str | None = None
    naa_ids: list[str] = []
    in_partitions = False
    for line in text.splitlines():
        if line.startswith(_LABEL_PREFIX):
            candidate = line[len(_LABEL_PREFIX) :].strip()
            if candidate.lower() not in _UNLABELLED:
                label = candidate
        elif line.startswith(_UUID_PREFIX):
            uuid = line[len(_UUID_PREFIX) :].strip() or None
        elif line.strip().startswith("Partitions spanned"):
            in_partitions = True
        elif in_partitions:
            if not line.startswith("\t") and not line.startswith(" "):
                in_partitions = False
                continue
            match = _DEVICE_ID_RE.search(line)
            if match:
                naa_ids.append(match.group(0))

    if label is None:
        return
    dedup_key = uuid or label
    if dedup_key in seen:
        return
    seen.add(dedup_key)
    host.datastores.append(Datastore(name=label, uuid=uuid, naa_ids=naa_ids))
