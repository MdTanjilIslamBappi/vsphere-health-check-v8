"""Parse installed VIB (vSphere Installation Bundle) acceptance levels.

Source: ``commands/localcli_software-vib-list.txt``. ESXi enforces four
acceptance levels for installed software: ``VMwareCertified``,
``VMwareAccepted``, ``PartnerSupported``, and ``CommunitySupported``.
The last is explicitly unsupported by VMware GSS -- a host running any
CommunitySupported VIB loses official support for issues that driver or
module could plausibly be involved in, which is a real operational/
support risk worth surfacing rather than leaving buried in a 100+ row
table.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers.table_utils import parse_fixed_width_table

VERSION = "1.0.0"

_FILENAME = "localcli_software-vib-list.txt"
_UNSUPPORTED_ACCEPTANCE_LEVEL = "CommunitySupported"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; VIB acceptance levels unknown"]

    text = path.read_text(encoding="utf-8", errors="replace")
    rows = parse_fixed_width_table(text)
    if not rows:
        return [f"{_FILENAME} did not match the expected table format"]

    host.vib_data_available = True
    host.community_supported_vibs = [
        row["Name"]
        for row in rows
        if row.get("Acceptance Level") == _UNSUPPORTED_ACCEPTANCE_LEVEL and row.get("Name")
    ]
    return []
