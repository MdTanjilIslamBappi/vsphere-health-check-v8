"""Parse ESXi's own built-in vSAN cluster membership flag.

Source: ``var/lib/vmware/osdata/healthd/vmw.vSANStatus-*.json`` (see
``parsers/_healthd.py`` for how the most recent rotated snapshot is
selected). Reports only ``vSAN_cluster_enabled`` -- purely descriptive,
neither value is a problem by itself. Used by
``rules/core_services_rules.py`` to know when ``vsanmgmtd`` legitimately
shows PID 0 (vSAN disabled) rather than treating that as a failure.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "vmw.vSANStatus"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
    if not isinstance(unstructured, dict):
        warnings.append("Most recent vmw.vSANStatus snapshot had no 'unstructured' section")
        return warnings

    enabled = unstructured.get("vSAN_cluster_enabled")
    if isinstance(enabled, bool):
        host.vsan_cluster_enabled = enabled
    host.vsan_status_data_available = True
    return warnings
