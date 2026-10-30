"""Who to credit on the report cover page.

Deliberately kept out of ``assessment.json``: these names describe how a
particular *report render* was prepared, not the deterministic analysis
of the bundle, and the same assessment is often rendered more than once
(e.g. a verifier adding their name on a later re-render via `vhealth
report`) without re-running the assessment itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportAuthorship:
    engineer_name: str | None = None
    author: str | None = None
    verifier: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.engineer_name or self.author or self.verifier)
