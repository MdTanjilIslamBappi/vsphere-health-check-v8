"""Parse ESXi's own built-in core-service-running verdict.

Source: ``var/lib/vmware/osdata/healthd/vmw.coreServicesStatus-*.json``
(see ``parsers/_healthd.py`` for how the most recent rotated snapshot is
selected). The ``unstructured`` section is a flat map of service name to
PID, where ``0`` means that service is not running. Every service name
observed is recorded as-is (no fixed allow-list), since this is an
ESXi self-check, not something vhealth should second-guess the shape of.
``vsanmgmtd`` legitimately reports ``0`` whenever vSAN is disabled on
this host -- see ``rules/core_services_rules.py`` for how that is
handled without false-positiving on every non-vSAN host.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo
from vhealth.parsers._healthd import latest_snapshot

VERSION = "1.0.0"

_CHECK_NAME = "vmw.coreServicesStatus"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    data, warnings = latest_snapshot(host_dir, _CHECK_NAME)
    if data is None:
        return warnings

    unstructured = data.get("unstructured")
    if not isinstance(unstructured, dict):
        warnings.append("Most recent vmw.coreServicesStatus snapshot had no 'unstructured' section")
        return warnings

    pids = {name: pid for name, pid in unstructured.items() if isinstance(pid, int)}
    host.core_service_pids = pids
    host.core_services_data_available = True
    return warnings
