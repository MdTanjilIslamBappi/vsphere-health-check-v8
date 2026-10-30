"""Ties ingestion, discovery, parsing, rules and reporting together.

This is the implementation behind `vhealth assess`; it is a plain function
(no CLI concerns) so it is easy to unit-test and to call from other code.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from vhealth import __version__
from vhealth.config import AssessmentConfig
from vhealth.correlation import build_host_infos, build_vcenter_info
from vhealth.discovery import find_host_bundles, find_vcenter_bundles
from vhealth.discovery.bundle import VCenterBundleRef
from vhealth.ingestion import extract_bundle
from vhealth.models.assessment import (
    Assessment,
    AssessmentMetadata,
    EvidenceManifestEntry,
    ProcessingWarning,
)
from vhealth.models.host import COVERAGE_CATEGORIES
from vhealth.models.vcenter import VCenterInfo
from vhealth.parsers import PARSER_VERSIONS
from vhealth.parsers import vcenter as vcenter_parser
from vhealth.rules import (
    RULE_ENGINE_VERSION,
    evaluate_all,
    evaluate_all_fleet,
    evaluate_all_vcenter,
)
from vhealth.utils.hashing import sha256_file

_EVIDENCE_RELATIVE_PATHS = [
    "README",
    "commands/uname_-a.txt",
    "commands/localcli_system-version-get.txt",
    "json/localcli_storage-core-adapter-list.json",
    "json/localcli_storage-core-device-list.json",
    "commands/smartinfo.txt",
    "commands/localcli_hardware-ipmi-sdr-list--p--i--n-all.txt",
    "commands/smbiosDump.txt",
    "commands/esxcfg-vmknic_-l.txt",
    "commands/clusterAdmin_cluster-status.txt",
]


def run_assessment(input_path: Path, output_dir: Path, config: AssessmentConfig) -> Assessment:
    output_dir.mkdir(parents=True, exist_ok=True)
    processing_warnings: list[ProcessingWarning] = []

    input_sha256 = sha256_file(input_path)

    extraction_dir = Path(tempfile.mkdtemp(prefix="vhealth-extract-", dir=str(output_dir)))
    extraction_result = extract_bundle(input_path, extraction_dir, config.extraction_limits)
    for warning in extraction_result.warnings:
        processing_warnings.append(ProcessingWarning(source="ingestion", message=warning))

    bundle_refs = find_host_bundles(extraction_dir)
    if not bundle_refs:
        processing_warnings.append(
            ProcessingWarning(
                source="discovery",
                message="No ESXi vm-support host bundles were found in the extracted archive.",
            )
        )

    vcenter, vcenter_ref = _ingest_vcenter_bundle(extraction_dir, processing_warnings)

    hosts = build_host_infos(bundle_refs)
    for host in hosts:
        for warning in host.parse_warnings:
            processing_warnings.append(ProcessingWarning(source=host.hostname, message=warning))
    if vcenter is not None:
        for warning in vcenter.parse_warnings:
            processing_warnings.append(
                ProcessingWarning(source=f"vCenter/{vcenter.hostname}", message=warning)
            )
        _resolve_cluster_names(hosts, vcenter)

    findings = evaluate_all(hosts, config.disabled_rules)
    findings += evaluate_all_fleet(hosts, config.disabled_rules)
    findings += evaluate_all_vcenter(vcenter, config.disabled_rules)

    evidence_manifest = _build_evidence_manifest(bundle_refs)
    if vcenter_ref is not None:
        evidence_manifest += _build_vcenter_evidence_manifest(vcenter_ref, vcenter)
    supported_format_coverage = _build_format_coverage(hosts)

    metadata = AssessmentMetadata(
        app_version=__version__,
        rule_engine_version=RULE_ENGINE_VERSION,
        parser_versions={**dict(PARSER_VERSIONS), "vcenter": vcenter_parser.VERSION},
        input_filename=input_path.name,
        input_sha256=input_sha256,
        assessment_timestamp=datetime.now(UTC).isoformat(),
        config_fingerprint=_fingerprint_config(config),
        evidence_manifest=evidence_manifest,
        supported_format_coverage=supported_format_coverage,
        processing_warnings=processing_warnings,
    )

    return Assessment(metadata=metadata, hosts=hosts, findings=findings, vcenter=vcenter)


def _resolve_cluster_names(hosts, vcenter: VCenterInfo) -> None:
    """Resolve each host to its cluster's display name.

    Two independent sources are tried, since neither is reliably present
    on its own:

    1. The host's own self-reported ``cluster_id`` moref (bare
       ``domain-c8`` or namespaced ``<vCenter-UUID>:domain-c8``) looked up
       in the vCenter bundle's log-derived moref -> name mapping.
    2. The host's hostname looked up in that same bundle's moref -> member
       -hostname mapping (``cluster_members``), matched case-insensitively
       and ignoring any FQDN domain suffix, since clusterAdmin reports a
       cluster ID far less consistently than vpxd logs cluster membership.
    """
    members_by_host: dict[str, str] = {}
    for moref, members in vcenter.cluster_members.items():
        name = vcenter.cluster_names.get(moref)
        if not name:
            continue
        for member in members:
            short = member.split(".", 1)[0].lower()
            members_by_host[short] = name

    for host in hosts:
        if host.cluster_id:
            moref = host.cluster_id.rsplit(":", 1)[-1].strip()
            name = vcenter.cluster_names.get(moref)
            if name:
                host.cluster_name = name
                continue
        short_hostname = host.hostname.split(".", 1)[0].lower()
        name = members_by_host.get(short_hostname)
        if name:
            host.cluster_name = name


def _build_evidence_manifest(bundle_refs) -> list[EvidenceManifestEntry]:
    manifest = []
    for ref in bundle_refs:
        for rel_path in _EVIDENCE_RELATIVE_PATHS:
            path = ref.root / rel_path
            if path.is_file():
                manifest.append(
                    EvidenceManifestEntry(
                        path=f"{ref.hostname_hint}/{rel_path}",
                        sha256=sha256_file(path),
                        size_bytes=path.stat().st_size,
                    )
                )
    return manifest


_VCENTER_EVIDENCE_RELATIVE_PATHS = [
    "README",
    "commands/uname_-a.txt",
    "commands/rpm_-qa.txt",
    "commands/service-control_--status---all.txt",
    "commands/df.txt",
]


def _build_vcenter_evidence_manifest(
    ref: VCenterBundleRef, vcenter: VCenterInfo | None
) -> list[EvidenceManifestEntry]:
    if vcenter is None:
        return []
    manifest = []
    for rel_path in _VCENTER_EVIDENCE_RELATIVE_PATHS:
        path = ref.root / rel_path
        if path.is_file():
            manifest.append(
                EvidenceManifestEntry(
                    path=f"vCenter/{vcenter.hostname}/{rel_path}",
                    sha256=sha256_file(path),
                    size_bytes=path.stat().st_size,
                )
            )
    return manifest


def _ingest_vcenter_bundle(
    extraction_dir: Path, processing_warnings: list[ProcessingWarning]
) -> tuple[VCenterInfo | None, VCenterBundleRef | None]:
    """Parse the (optional) vCenter appliance bundle member of the archive."""
    refs = find_vcenter_bundles(extraction_dir)
    if not refs:
        return None, None
    if len(refs) > 1:
        processing_warnings.append(
            ProcessingWarning(
                source="discovery",
                message=(
                    f"{len(refs)} vCenter appliance bundles were found; only the first "
                    f"({refs[0].root.name}) was parsed."
                ),
            )
        )
    ref = refs[0]
    try:
        vcenter = build_vcenter_info(ref)
    except Exception as exc:  # noqa: BLE001 - a single parser must not abort the run
        processing_warnings.append(
            ProcessingWarning(
                source="discovery",
                message=f"vCenter bundle {ref.root.name} could not be parsed: {exc}",
            )
        )
        return None, ref
    return vcenter, ref


def _build_format_coverage(hosts) -> dict[str, bool]:
    coverage = dict.fromkeys(COVERAGE_CATEGORIES, False)
    for host in hosts:
        for category, present in host.coverage().items():
            coverage[category] |= present
    return coverage


def _fingerprint_config(config: AssessmentConfig) -> str:
    canonical = json.dumps(config.raw, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
