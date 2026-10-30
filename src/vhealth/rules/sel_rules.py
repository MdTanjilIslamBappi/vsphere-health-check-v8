"""Hardware-failure signals from the IPMI System Event Log (SEL) history.

See ``parsers/ipmi_sel.py`` for why this is a separate source from
``hardware.ipmi_sensor_asserted`` (current sensor state only) and from
``log_rules.py`` (vmkwarning/vobd storage signals): same quarterly-scope
convention, independent file, independent per-signal rule IDs. Only one
``Rule`` is registered for the whole module (mirroring ``log_rules.py``'s
own ``storage.log_signals`` umbrella) because ``_sel_signal_findings``
itself produces every signal's findings in one pass -- registering a
second ``Rule`` pointed at the same function would double-evaluate it.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

_SIGNAL_RULES = {
    "sel_ecc_uncorrectable": (
        "hardware.sel_ecc_uncorrectable",
        "Uncorrectable memory (ECC) error recorded in the IPMI event log",
        Severity.CRITICAL,
        "An uncorrectable ECC error means the memory controller detected a bit "
        "error it could not fix in hardware; the affected DIMM is suspect.",
        "Identify the affected DIMM slot from the BMC/iDRAC/iLO web console's own "
        "event detail (the SEL record carries a sensor number this tool does not "
        "decode further) and schedule a memory diagnostic/replacement.",
    ),
    "sel_drive_predictive_failure": (
        "hardware.sel_drive_predictive_failure",
        "Drive predictive-failure event recorded in the IPMI event log",
        Severity.HIGH,
        "The storage backplane/HBA itself (not ESXi's own SMART polling) flagged "
        "a drive as likely to fail soon.",
        "Check the storage controller/BMC console for which physical drive slot "
        "raised this and confirm whether it has already been replaced; "
        "cross-check against this host's own SMART data for the same timeframe.",
    ),
    "sel_psu_failure": (
        "hardware.sel_psu_failure",
        "Power supply failure event recorded in the IPMI event log",
        Severity.HIGH,
        "A power supply unit reported a failure status, not just a brief "
        "AC-input blip.",
        "Check the BMC/iDRAC/iLO console for which PSU bay raised this and "
        "confirm the unit has since been reseated or replaced.",
    ),
    "sel_temperature_critical": (
        "hardware.sel_temperature_critical",
        "Critical temperature threshold event recorded in the IPMI event log",
        Severity.HIGH,
        "A temperature sensor crossed its upper-critical threshold, not just the "
        "earlier non-critical warning.",
        "Check airflow, fan status, and ambient rack/room temperature around the "
        "time of this event.",
    ),
}


def _sel_signal_findings(host: HostInfo) -> list[Finding]:
    findings = []
    for signal_name, (rule_id, title, severity, note, where_to_check) in _SIGNAL_RULES.items():
        count = host.log_signal_counts.get(signal_name, 0)
        if count <= 0:
            continue
        examples = [e for e in host.log_events if e.startswith(f"[{signal_name}]")]
        excluded = host.log_signal_counts_excluded.get(signal_name, 0)
        findings.append(
            Finding(
                rule_id=rule_id,
                title=title,
                severity=severity,
                summary=(
                    f"{count} matching IPMI SEL record(s) found in the last 90 days "
                    "(this quarter)."
                ),
                evidence=examples,
                affected_host=host.hostname,
                remediation=where_to_check,
                limitations=(
                    f"{note} Scoped to this quarter (the last 90 days of the bundle's "
                    "own capture date); a later Deassert/clearing record for the same "
                    "condition is not distinguished from this -- it only reports that "
                    "the condition occurred during the window, not whether it is still "
                    "active as of capture time."
                    + (
                        f" {excluded} additional older occurrence(s) were also found in "
                        "the bundle but fall outside this quarter's window."
                        if excluded
                        else ""
                    )
                ),
            )
        )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="hardware.sel_signals",
        title="Hardware-failure signals from the IPMI System Event Log",
        default_severity=Severity.HIGH,
        evidence_required=("log_signal_counts", "log_events"),
        limitations="See individual findings for each specific SEL signal's own caveats.",
        evaluate=_sel_signal_findings,
    ),
]
