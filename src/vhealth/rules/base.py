"""Base type for assessment rules.

A rule is deliberately simple: a function that inspects one host's
already-parsed data and returns zero or more Findings. Rules must not
raise -- an exception in one rule should not abort the rest of the
assessment (the registry wraps every call).

Per CONTRIBUTING.md, every rule must document:

* ``evidence_required`` -- which parsed fields it depends on, so a
  missing-evidence warning can be raised instead of silently skipping.
* ``limitations`` -- known false-positive/false-negative conditions,
  surfaced in RULE_CATALOG.md and copied onto every Finding it raises.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vhealth.models.findings import Finding, Severity
from vhealth.models.host import HostInfo

RuleFunc = Callable[[HostInfo], list[Finding]]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    default_severity: Severity
    evidence_required: tuple[str, ...]
    limitations: str
    evaluate: RuleFunc

    def run(self, host: HostInfo) -> list[Finding]:
        try:
            return self.evaluate(host)
        except Exception as exc:  # noqa: BLE001
            return [
                Finding(
                    rule_id=self.rule_id,
                    title=f"{self.title} (rule error)",
                    severity=Severity.INFO,
                    summary=f"Rule raised an unexpected error and was skipped: {exc}",
                    affected_host=host.hostname,
                    limitations=self.limitations,
                )
            ]
