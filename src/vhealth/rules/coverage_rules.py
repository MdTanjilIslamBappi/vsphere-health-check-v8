"""Flag when a bundle is missing whole categories of diagnostic data.

Real vm-support bundles are not all captured the same way -- a reduced or
"incident" capture can omit esxcli storage-core output, SMART data, or
log rotations entirely, with no error, just absence. Every other rule in
this catalogue can only report what it finds; none of them can tell a
reader that a *lack* of findings might mean "nothing wrong" or might mean
"we couldn't check." This rule exists to make that distinction explicit
rather than let a short findings list be misread as a clean bill of
health.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

# readme/system_version are metadata about the bundle itself, not health
# data; a bundle missing those has deeper problems a human will notice
# immediately. Only the categories below actually drive the rule catalogue.
_HEALTH_CATEGORIES = {
    "storage_adapters": "storage HBA/controller inventory (esxcli storage core adapter list)",
    "storage_devices": "storage device/LUN inventory (esxcli storage core device list)",
    "smart_data": "SMART disk health data (smartinfo.txt)",
    "hardware_sensors": "IPMI hardware sensor readings",
    "log_signals": "vmkwarning/vobd storage log signals",
    "hardware_inventory": "server/CPU model identity (smbiosDump.txt)",
}


def _limited_diagnostic_coverage(host: HostInfo) -> list[Finding]:
    coverage = host.coverage()
    missing = [key for key in _HEALTH_CATEGORIES if not coverage.get(key, False)]
    if not missing:
        return []

    severity = Severity.LOW if len(missing) >= 3 else Severity.INFO
    missing_labels = "; ".join(_HEALTH_CATEGORIES[key] for key in missing)

    return [
        Finding(
            rule_id="coverage.limited_diagnostic_data",
            title="Limited diagnostic data available in this support bundle",
            severity=severity,
            summary=(
                f"{len(missing)} of {len(_HEALTH_CATEGORIES)} diagnostic data categories "
                f"were not found for {host.hostname}, so the related checks could not run: "
                f"{missing_labels}."
            ),
            evidence=[f"supported_format_coverage.{key} = false" for key in missing],
            affected_host=host.hostname,
            remediation=(
                "If a more complete picture is needed, re-collect the bundle with a full "
                "'vm-support' capture rather than a reduced/incident one, and confirm the "
                "expected storage/SMART/IPMI drivers are loaded on the host."
            ),
            limitations=(
                "This finding only reports what data vhealth found in the bundle, not why "
                "it is missing -- it may be a reduced vm-support capture mode, an "
                "unsupported driver, or a genuinely minimal hardware configuration (e.g. "
                "a host with no local disks)."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="coverage.limited_diagnostic_data",
        title="Limited diagnostic data available in this support bundle",
        default_severity=Severity.LOW,
        evidence_required=("coverage()",),
        limitations=(
            "Reports what is missing, not why; cannot distinguish a reduced capture mode "
            "from hardware that genuinely has nothing to report."
        ),
        evaluate=_limited_diagnostic_coverage,
    ),
]
