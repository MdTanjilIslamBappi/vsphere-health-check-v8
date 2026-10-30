from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):  # noqa: UP042 - str mixin kept explicit for clarity
    """Finding severity, ordered from least to most urgent."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


class Finding(BaseModel):
    """A single assessment finding produced by a rule."""

    rule_id: str
    title: str
    severity: Severity
    summary: str
    evidence: list[str] = Field(default_factory=list)
    affected_host: str | None = None
    affected_object: str | None = None
    remediation: str | None = None
    limitations: str | None = None
    references: list[str] = Field(default_factory=list)
