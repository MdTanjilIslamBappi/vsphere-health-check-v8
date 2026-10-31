"""Parse ESXi's own built-in vpxa<->hostd<->vCenter connectivity verdict.

Source: ``var/lib/vmware/osdata/healthd/vmw.vpxaStatus-*.json`` (see
``parsers/_healthd.py`` for how the most recent rotated snapshot is
selected). Reports the host's own view of whether its management
connection to vCenter is actually working right now (``responsive``,
``connected_to_hostd``, ``managed_by_VC``, ``config_status``) -- not
just whether it is configured to be managed.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "vmw.vpxaStatus"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
    if not isinstance(unstructured, dict):
        warnings.append("Most recent vmw.vpxaStatus snapshot had no 'unstructured' section")
        return warnings

    responsive = unstructured.get("responsive")
    if isinstance(responsive, bool):
        host.vpxa_responsive = responsive
    connected = unstructured.get("connected_to_hostd")
    if isinstance(connected, bool):
        host.vpxa_connected_to_hostd = connected
    managed = unstructured.get("managed_by_VC")
    if isinstance(managed, bool):
        host.vpxa_managed_by_vc = managed
    config_status = unstructured.get("config_status")
    if isinstance(config_status, str):
        host.vpxa_config_status = config_status
    host.vpxa_status_data_available = True
    return warnings
