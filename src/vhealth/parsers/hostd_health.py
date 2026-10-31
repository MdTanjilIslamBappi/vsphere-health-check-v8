"""Parse ESXi's own built-in hostd-responsiveness verdict.

Source: ``var/lib/vmware/osdata/healthd/hostd-health-*.json`` (see
``parsers/_healthd.py`` for how the most recent rotated snapshot is
selected). Reports ``hostd.state`` (observed value: ``"Responsive"``) --
distinct from ``core_services_status.py``'s ``hostd`` PID, which only
shows whether the process exists, not whether it is actually answering
probes.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "hostd-health"
_HEALTHY_STATE = "Responsive"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
    hostd = unstructured.get("hostd") if isinstance(unstructured, dict) else None
    if not isinstance(hostd, dict):
        warnings.append("Most recent hostd-health snapshot had no 'unstructured.hostd' section")
        return warnings

    state = hostd.get("state")
    if isinstance(state, str):
        host.hostd_responsive = state == _HEALTHY_STATE
    host.hostd_health_data_available = True
    return warnings
