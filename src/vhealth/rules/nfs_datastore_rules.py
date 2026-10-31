"""ESXi's own built-in NFS-datastore-health check (healthd's

vmw.nfsDatastoreHealth). The verdict here comes directly from ESXi's own
self-check (see ``parsers/nfs_datastore_health.py``), not from
pattern-matching raw state: ``is_accessible``/``is_mounted`` are
healthd's own read of each NFS mount's current state.
"""

from __future__ import annotations

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo
from vhealth.rules.base import Rule


def _nfs_datastore_inaccessible(host: HostInfo) -> list[Finding]:
    findings = []
    for ds in host.nfs_datastores:
        if ds.is_accessible and ds.is_mounted:
            continue

        states = []
        if not ds.is_accessible:
            states.append("not accessible")
        if not ds.is_mounted:
            states.append("not mounted")
        state_text = " and ".join(states)

        evidence = [
            f"vmw.nfsDatastoreHealth: volume_name={ds.volume_name}, "
            f"is_accessible={ds.is_accessible}, is_mounted={ds.is_mounted}"
        ]
        if ds.remote_share_name or ds.remote_hosts:
            remote = ds.remote_share_name or ""
            hosts = ",".join(ds.remote_hosts)
            evidence.append(f"remote share: {remote} on {hosts or 'unknown host'}")
        if ds.inaccessible_reason:
            evidence.append(f"inaccessible_reason: {ds.inaccessible_reason}")

        findings.append(
            Finding(
                rule_id="storage.nfs_datastore_inaccessible",
                title="NFS datastore is not accessible/mounted",
                severity=Severity.HIGH,
                summary=(
                    f"{host.hostname}: ESXi's own healthd check reports NFS datastore "
                    f"'{ds.volume_name}' is {state_text}."
                ),
                evidence=evidence,
                affected_host=host.hostname,
                affected_object=ds.volume_name,
                remediation=(
                    "Verify the NFS server backing this datastore is reachable from this "
                    "host's VMkernel network, confirm the NFS export's permissions/firewall "
                    "rules, and remount the datastore (vSphere Client or 'esxcli storage "
                    "nfs41 add') if its unmounted state was unintentional."
                ),
                limitations=(
                    "Point-in-time snapshot from ESXi's own healthd check, selecting "
                    "whichever rotated snapshot has the most recent timestamp in the "
                    "bundle; cannot tell whether this is a transient NFS server blip, a "
                    "sustained outage, or an intentional detach (e.g. decommissioning)."
                ),
            )
        )
    return findings


RULES: list[Rule] = [
    Rule(
        rule_id="storage.nfs_datastore_inaccessible",
        title="NFS datastore is not accessible/mounted",
        default_severity=Severity.HIGH,
        evidence_required=("nfs_datastores[].is_accessible", "nfs_datastores[].is_mounted"),
        limitations=(
            "Point-in-time snapshot at capture only, from ESXi's own healthd check."
        ),
        evaluate=_nfs_datastore_inaccessible,
    ),
]
