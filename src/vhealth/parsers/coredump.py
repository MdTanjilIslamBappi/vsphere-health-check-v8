"""Parse ESXi kernel-coredump target configuration.

Source: ``commands/localcli_system-coredump-file-list.txt`` -- the
file-based coredump target(s) configured on modern ESXi (default since
6.5). The older partition-based config (``localcli system coredump
partition get``) is effectively legacy and reports blank on hosts using
file-based coredump, so this parser reads the file-based table instead.
A host needs at least one entry marked both ``Active`` and
``Configured``, or there is nowhere for ESXi to write a kernel crash
dump on a PSOD -- the single most useful artifact for root-causing a
host crash.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers.table_utils import parse_fixed_width_table

VERSION = "1.0.0"

_FILENAME = "localcli_system-coredump-file-list.txt"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; coredump configuration unknown"]

    text = path.read_text(encoding="utf-8", errors="replace")
    rows = parse_fixed_width_table(text)
    # An empty table (header/separator present, zero data rows) is a real,
    # distinct signal -- coredump genuinely has no target configured -- not
    # a parse failure, so it must not be confused with a missing/malformed
    # file. The header text is the only reliable marker available once the
    # separator line has already been consumed by parse_fixed_width_table.
    has_table_markers = "Active" in text and "Configured" in text
    if not rows and not has_table_markers:
        return [f"{_FILENAME} did not match the expected table format"]

    host.coredump_data_available = True
    active_row = next(
        (r for r in rows if r.get("Active") == "true" and r.get("Configured") == "true"),
        None,
    )
    host.coredump_configured = active_row is not None
    if active_row is not None:
        host.coredump_active_path = active_row.get("Path")
    return []
