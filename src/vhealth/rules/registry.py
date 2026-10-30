from __future__ import annotations

from vhealth.models.findings import Finding
from vhealth.models.host import HostInfo
from vhealth.rules import log_rules, sensor_rules, storage_rules
from vhealth.rules.base import Rule

RULE_ENGINE_VERSION = "1.0.0"

ALL_RULES: list[Rule] = [
    *storage_rules.RULES,
    *sensor_rules.RULES,
    *log_rules.RULES,
]


def evaluate_all(hosts: list[HostInfo]) -> list[Finding]:
    findings: list[Finding] = []
    for host in hosts:
        for rule in ALL_RULES:
            findings.extend(rule.run(host))
    return findings
