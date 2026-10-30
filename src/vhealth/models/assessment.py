from __future__ import annotations

from pydantic import BaseModel, Field

ASSESSMENT_SCHEMA_VERSION = "1.0.0"


class ProcessingWarning(BaseModel):
    source: str
    message: str


class EvidenceManifestEntry(BaseModel):
    path: str
    sha256: str
    size_bytes: int


class AssessmentMetadata(BaseModel):
    """Execution metadata, kept separate from deterministic findings data.

    Everything here except ``assessment_timestamp`` is stable for a given
    (bundle, app version, rule catalogue, config) tuple, so two assessments
    of the same input can be diffed meaningfully.
    """

    schema_version: str = ASSESSMENT_SCHEMA_VERSION
    app_version: str
    rule_engine_version: str
    parser_versions: dict[str, str] = Field(default_factory=dict)
    input_filename: str
    input_sha256: str
    assessment_timestamp: str
    config_fingerprint: str
    evidence_manifest: list[EvidenceManifestEntry] = Field(default_factory=list)
    supported_format_coverage: dict[str, bool] = Field(default_factory=dict)
    processing_warnings: list[ProcessingWarning] = Field(default_factory=list)


class Assessment(BaseModel):
    """Top-level, versioned assessment result."""

    metadata: AssessmentMetadata
    hosts: list[HostInfo] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)


from vhealth.models.findings import Finding  # noqa: E402
from vhealth.models.host import HostInfo  # noqa: E402

Assessment.model_rebuild()
