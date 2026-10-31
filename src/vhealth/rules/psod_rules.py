"""ESXi's own built-in PSOD (purple-screen crash) history count (healthd's

vmw.PSODCount). A non-zero count is healthd's own tally, not something
vhealth derives from log scanning. Severity reflects recency: a crash
within the last 7 days is more urgent than one that only shows up in
the 15-day window.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _psod_detected(host: HostInfo) -> list[Finding]:
    if not host.psod_data_available:
        return []
    count_7 = host.psod_count_7_days or 0
    count_15 = host.psod_count_15_days or 0
    if count_7 == 0 and count_15 == 0:
        return []

    severity = Severity.CRITICAL if count_7 > 0 else Severity.HIGH
    window = "7" if count_7 > 0 else "15"
    count = count_7 if count_7 > 0 else count_15

    return [
        Finding(
            rule_id="hardware.psod_detected",
            title="Host has a recorded PSOD (purple-screen crash) in its recent history",
            severity=severity,
            summary=(
                f"{host.hostname}: ESXi's own healthd check reports {count} PSOD(s) in the "
                f"last {window} days."
            ),
            evidence=[
                f"vmw.PSODCount: psod_7_days_count={count_7}, psod_15_days_count={count_15}"
            ],
            affected_host=host.hostname,
            remediation=(
                "Review this host's vmkernel-zdump core files and VMware KB guidance for "
                "PSOD root-causing (/var/core on the host, or collect via vm-support); "
                "check for a pattern across hosts sharing the same hardware/firmware "
                "revision or a recently applied driver/patch."
            ),
            limitations=(
                "Reports healthd's own trailing crash count as of its own check time, not "
                "the crash's exact date/cause; cannot tell whether the host has since been "
                "patched or whether multiple PSODs share one root cause."
            ),
        )
    ]


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.psod_detected",
        title="Host has a recorded PSOD (purple-screen crash) in its recent history",
        default_severity=Severity.CRITICAL,
        evidence_required=("psod_count_7_days", "psod_count_15_days"),
        limitations="Point-in-time snapshot at capture only, from ESXi's own healthd check.",
        evaluate=_psod_detected,
    ),
]
