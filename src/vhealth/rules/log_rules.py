from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule

_SIGNAL_RULES = {
    "pdl_error": (
        "storage.pdl_detected",
        "Permanent Device Loss (PDL) detected in vmkwarning log",
        Severity.CRITICAL,
        "A PDL event means ESXi determined a storage device will never "
        "return; any VM still running on it will fail I/O.",
        "Check this host's vmkwarning log (the matching lines are listed below) "
        "and run esxcli storage core device list for the affected device's "
        "current path state, then correlate the event timestamp with the "
        "SAN array controller and fabric/switch logs for the same LUN.",
    ),
    "apd_event": (
        "storage.apd_detected",
        "All-Paths-Down (APD) event detected in vmkwarning log",
        Severity.CRITICAL,
        "An APD event means every path to a device was unavailable, even if "
        "only transiently.",
        "Check this host's vmkwarning log (the matching lines are listed below) "
        "for the affected device/path IDs, then correlate the event timestamp "
        "with the SAN array controller and FC/iSCSI fabric or switch logs.",
    ),
    "path_dead": (
        "storage.path_dead_detected",
        "Dead storage path/device detected in vmkwarning log",
        Severity.HIGH,
        "A path or device was marked dead at least once during the log window.",
        "Check this host's vmkwarning log (the matching lines are listed below) "
        "and the HBA/multipathing plugin status for the named path, then "
        "correlate the timestamp with the SAN switch port and array-side "
        "presentation logs for the same device.",
    ),
    "alua_no_connection": (
        "storage.alua_path_connectivity",
        "Repeated ALUA path-connectivity errors detected",
        Severity.MEDIUM,
        "SATP_ALUA could not reach a target port; frequent recurrence suggests "
        "flapping SAN/fabric connectivity rather than a one-off blip.",
        "Check this host's vmkwarning log (the matching lines are listed below) "
        "for the affected target port, then correlate the timestamps with the "
        "storage array's ALUA target-port-group state and fabric/switch logs.",
    ),
    "vob_storage_problem": (
        "storage.vob_problem_event",
        "VMkernel Observation (VOB) flagged a storage problem event",
        Severity.MEDIUM,
        "vobd only logs events the ESXi host itself classified as a problem "
        "(esx.problem.*), as opposed to routine audit events.",
        "Check this host's vobd log (the matching lines are listed below) for "
        "the affected device/event ID, then correlate the timestamp with the "
        "SAN array and fabric/switch logs for the same timeframe.",
    ),
}

_REPEAT_THRESHOLD = 3


def _log_signal_findings(host: HostInfo) -> list[Finding]:
    findings = []
    for signal_name, (rule_id, title, severity, note, where_to_check) in _SIGNAL_RULES.items():
        count = host.log_signal_counts.get(signal_name, 0)
        if count <= 0:
            continue
        if signal_name == "alua_no_connection" and count < _REPEAT_THRESHOLD:
            continue
        examples = [e for e in host.log_events if e.startswith(f"[{signal_name}]")]
        excluded = host.log_signal_counts_excluded.get(signal_name, 0)
        findings.append(
            Finding(
                rule_id=rule_id,
                title=title,
                severity=severity,
                summary=f"{count} matching log line(s) found in the last 90 days (this quarter).",
                evidence=examples,
                affected_host=host.hostname,
                remediation=where_to_check,
                limitations=(
                    f"{note} Scoped to this quarter (the last 90 days of the bundle's own "
                    "capture date); only the rotations retained in the bundle at capture "
                    "time were scanned (older events may already have rolled off)."
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
        rule_id="storage.log_signals",
        title="Storage/hardware signals from vmkwarning and vobd logs",
        default_severity=Severity.MEDIUM,
        evidence_required=("log_signal_counts", "log_events"),
        limitations="Limited to retained log rotations at capture time; see individual findings.",
        evaluate=_log_signal_findings,
    ),
]
