"""Parse ESXi's own built-in migration-network health check.

Source: ``commands/mobility_network_health_check.txt`` -- the output of
VMware's own ``vmware.mobility.mobility_health_checks`` module, which
validates VMkernel network readiness for migration traffic (vMotion,
Provisioning, ...): netstack/vmknic state, MTU consistency, and actual
TCP/ping connectivity to every other host's matching VMkernel adapter.
Unlike this tool's other checks, the *verdict* here (the
``"<netService> network health check status"`` field) is ESXi's own,
not something vhealth infers from raw state.

On several real hosts this tool crashes outright -- observed as a
Python traceback instead of JSON (e.g. ``Exception: Not supported``
deep in ``network_info.VsiList``), apparently an ESXi build/config
incompatibility with the health-check framework itself. That is
recorded as missing data, not a finding: vhealth cannot know whether
the underlying network is actually fine when ESXi's own checker could
not even run.
"""

from __future__ import annotations

import json
from pathlib import Path

from vhealth.models.host import HostInfo, MobilityNetworkCheck

VERSION = "1.0.0"

_FILENAME = "mobility_network_health_check.txt"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; migration-network health check unavailable"]

    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return [f"{_FILENAME} was empty; migration-network health check unavailable"]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [
            f"{_FILENAME} did not contain valid JSON (the health-check tool itself "
            "likely failed to run on this host); migration-network health check "
            "unavailable"
        ]
    if not isinstance(data, list):
        return [f"{_FILENAME} was not a JSON list; migration-network health check unavailable"]

    checks = [c for c in (_parse_entry(entry) for entry in data) if c is not None]
    if not checks:
        return [f"{_FILENAME} did not contain any recognisable netService result"]

    host.mobility_data_available = True
    host.mobility_checks = checks
    return []


def _parse_entry(entry: object) -> MobilityNetworkCheck | None:
    if not isinstance(entry, dict):
        return None
    net_service = entry.get("netService")
    if not net_service:
        return None
    status = entry.get(f"{net_service} network health check status")
    if status is None:
        return None
    tcp = entry.get("TcpConnectivity result")
    tested = len(tcp.get("results", [])) if isinstance(tcp, dict) else 0
    return MobilityNetworkCheck(
        net_service=str(net_service),
        status=str(status),
        expected_destinations=len(entry.get("checkConnectivityTo") or []),
        tested_destinations=tested,
        errors=_collect_errors(entry),
    )


def _collect_errors(entry: dict) -> list[str]:
    errors: list[str] = []
    for key, value in entry.items():
        if not key.endswith(" result") or not isinstance(value, dict):
            continue
        errors.extend(str(e) for e in (value.get("error") or []))
        for sub in value.get("results") or []:
            if isinstance(sub, dict):
                errors.extend(str(e) for e in (sub.get("error") or []))
    # De-duplicate while keeping order -- the same underlying cause often
    # surfaces on more than one sub-check.
    seen: set[str] = set()
    deduped = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            deduped.append(e)
    return deduped
