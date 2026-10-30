"""ESXi host-configuration database (ConfigStore) integrity check.

``/etc/vmware/configstore`` is the SQLite-backed database ESXi 7.x/8.x
uses to hold the host's own configuration (replacing the old flat-file
``esx.conf``). Corruption or exhaustion here is a documented real issue
that can affect reconfiguration, backup, and upgrade (Broadcom KB
312114, KB 438104); SQLite's own ``PRAGMA integrity_check`` reports a
single line, ``ok``, when the database is structurally sound.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _configstore_integrity_check_failed(host: HostInfo) -> list[Finding]:
    if not host.configstore_data_available or host.configstore_integrity_ok is not False:
        return []

    return [
        Finding(
            rule_id="hardware.configstore_integrity_check_failed",
            title="ConfigStore database integrity check did not report 'ok'",
            severity=Severity.CRITICAL,
            summary=(
                f"{host.hostname}'s ConfigStore (/etc/vmware/configstore) failed its "
                "own SQLite integrity check -- its host-configuration database may be "
                "corrupt."
            ),
            evidence=[
                "sqlite3 /etc/vmware/configstore/current-store-1 'PRAGMA "
                "integrity_check;' did not return 'ok'"
            ],
            affected_host=host.hostname,
            remediation=(
                "Engage VMware GSS or use the documented configstore-recovery tool "
                "(esxcli/configstore-recovery --recover, where available for this "
                "build) before the next reboot or upgrade attempt; a corrupt "
                "ConfigStore can affect host reconfiguration, backup, and upgrade."
            ),
            limitations=(
                "Reports a point-in-time snapshot from the bundle's capture moment "
                "only. The firing (not-'ok') case is implemented from SQLite's own "
                "documented integrity_check behaviour; every real bundle seen so far "
                "reports 'ok', so this condition has not yet been observed firing "
                "against real-world data."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.configstore_integrity_check_failed",
        title="ConfigStore database integrity check did not report 'ok'",
        default_severity=Severity.CRITICAL,
        evidence_required=("configstore_integrity_ok",),
        limitations=(
            "Point-in-time snapshot at capture only; implemented from SQLite's "
            "documented integrity_check behaviour but not yet observed firing "
            "against real-world data."
        ),
        evaluate=_configstore_integrity_check_failed,
    ),
]
