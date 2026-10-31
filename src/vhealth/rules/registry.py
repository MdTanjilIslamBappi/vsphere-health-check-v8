from __future__ import annotations

from vhealth.models.findings import Finding
from vhealth.models.host import HostInfo
from vhealth.models.vcenter import VCenterInfo
from vhealth.rules import (
    configstore_rules,
    coredump_rules,
    coverage_rules,
    fleet_rules,
    log_rules,
    memory_rules,
    mobility_rules,
    multipath_rules,
    network_rules,
    nfs_datastore_rules,
    ntp_rules,
    pending_reboot_rules,
    sel_rules,
    sensor_rules,
    storage_rules,
    vcenter_rules,
    vib_rules,
)
from vhealth.rules.base import FleetRule, Rule

RULE_ENGINE_VERSION = "1.16.0"

ALL_RULES: list[Rule] = [
    *storage_rules.RULES,
    *sensor_rules.RULES,
    *log_rules.RULES,
    *coverage_rules.RULES,
    *ntp_rules.RULES,
    *coredump_rules.RULES,
    *vib_rules.RULES,
    *multipath_rules.RULES,
    *network_rules.RULES,
    *sel_rules.RULES,
    *configstore_rules.RULES,
    *mobility_rules.RULES,
    *pending_reboot_rules.RULES,
    *memory_rules.RULES,
    *nfs_datastore_rules.RULES,
]

ALL_FLEET_RULES: list[FleetRule] = [
    *fleet_rules.RULES,
]

ALL_VCENTER_RULES: list[vcenter_rules.VCenterRule] = [
    *vcenter_rules.ALL_VCENTER_RULES,
]


def evaluate_all_vcenter(
    vcenter: VCenterInfo | None, disabled_rules: tuple[str, ...] = ()
) -> list[Finding]:
    if vcenter is None:
        return []
    enabled_rules = [r for r in ALL_VCENTER_RULES if r.rule_id not in disabled_rules]
    findings: list[Finding] = []
    for rule in enabled_rules:
        findings.extend(rule.run(vcenter))
    return findings


def evaluate_all(hosts: list[HostInfo], disabled_rules: tuple[str, ...] = ()) -> list[Finding]:
    enabled_rules = [r for r in ALL_RULES if r.rule_id not in disabled_rules]
    findings: list[Finding] = []
    for host in hosts:
        for rule in enabled_rules:
            findings.extend(rule.run(host))
    return findings


def evaluate_all_fleet(
    hosts: list[HostInfo], disabled_rules: tuple[str, ...] = ()
) -> list[Finding]:
    enabled_rules = [r for r in ALL_FLEET_RULES if r.rule_id not in disabled_rules]
    findings: list[Finding] = []
    for rule in enabled_rules:
        findings.extend(rule.run(hosts))
    return findings
