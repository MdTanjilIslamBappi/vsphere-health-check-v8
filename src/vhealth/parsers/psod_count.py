"""Parse ESXi's own built-in PSOD (purple-screen crash) history count.

Source: ``var/lib/vmware/osdata/healthd/vmw.PSODCount-*.json`` (see
``parsers/_healthd.py`` for how the most recent rotated snapshot is
selected). Reports ``psod_7_days_count``/``psod_15_days_count`` --
healthd's own trailing crash counts as of its own check time, not
something vhealth derives from log scanning.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "vmw.PSODCount"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
    if not isinstance(unstructured, dict):
        warnings.append("Most recent vmw.PSODCount snapshot had no 'unstructured' section")
        return warnings

    count_7 = unstructured.get("psod_7_days_count")
    count_15 = unstructured.get("psod_15_days_count")
    if isinstance(count_7, int):
        host.psod_count_7_days = count_7
    if isinstance(count_15, int):
        host.psod_count_15_days = count_15
    host.psod_data_available = True
    return warnings
