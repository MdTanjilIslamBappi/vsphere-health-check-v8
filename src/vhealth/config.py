"""Load the default bundled configuration, optionally overlaid by a
user-supplied TOML file. No part of this ever touches the network."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from vhealth.ingestion.exceptions import VHealthError
from vhealth.security.extraction_guard import ExtractionLimits

# How many weeks of log/event history (vmkwarning/vobd, IPMI SEL) count
# toward an active finding. 13 weeks (~91 days) is the closest whole-week
# approximation of this tool's original "quarterly" (90-day) default; the
# 26-week ceiling is this project's own choice, not a VMware-documented
# limit, to keep the window from growing large enough to resurface very
# stale events as if they were current.
DEFAULT_LOG_WINDOW_WEEKS = 13
MIN_LOG_WINDOW_WEEKS = 1
MAX_LOG_WINDOW_WEEKS = 26


@dataclass(frozen=True)
class ReportConfig:
    title: str
    company_name: str
    # Cover-page branding images (background graphic behind the title, the
    # preparer's own logo, and the customer's logo). All three are optional
    # and unset by default -- vhealth itself ships with none, and these are
    # meant to point at image files kept *outside* this repository (e.g. a
    # sibling directory), never committed alongside it. See README.md.
    cover_background_image: str
    preparer_logo_image: str
    customer_logo_image: str


@dataclass(frozen=True)
class AssessmentConfig:
    report: ReportConfig
    extraction_limits: ExtractionLimits
    disabled_rules: tuple[str, ...]
    log_window_weeks: int
    raw: dict


def _load_default() -> dict:
    text = resources.files("vhealth.resources").joinpath(
        "defaults/config.default.toml"
    ).read_text(encoding="utf-8")
    return tomllib.loads(text)


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(user_config_path: Path | None) -> AssessmentConfig:
    data = _load_default()
    if user_config_path is not None:
        user_text = user_config_path.read_text(encoding="utf-8")
        data = _deep_merge(data, tomllib.loads(user_text))

    report = data.get("report", {})
    extraction = data.get("extraction", {})
    assessment = data.get("assessment", {})

    return AssessmentConfig(
        report=ReportConfig(
            title=report.get("title", "VMware vSphere® Health Check Report"),
            company_name=report.get("company_name", ""),
            cover_background_image=report.get("cover_background_image", ""),
            preparer_logo_image=report.get("preparer_logo_image", ""),
            customer_logo_image=report.get("customer_logo_image", ""),
        ),
        extraction_limits=ExtractionLimits(
            max_total_uncompressed_bytes=extraction.get(
                "max_total_uncompressed_bytes", ExtractionLimits.max_total_uncompressed_bytes
            ),
            max_member_uncompressed_bytes=extraction.get(
                "max_member_uncompressed_bytes", ExtractionLimits.max_member_uncompressed_bytes
            ),
            max_entries=extraction.get("max_entries", ExtractionLimits.max_entries),
            max_compression_ratio=extraction.get(
                "max_compression_ratio", ExtractionLimits.max_compression_ratio
            ),
        ),
        disabled_rules=tuple(assessment.get("disabled_rules", [])),
        log_window_weeks=_validated_log_window_weeks(
            assessment.get("log_window_weeks", DEFAULT_LOG_WINDOW_WEEKS)
        ),
        raw=data,
    )


def _validated_log_window_weeks(weeks: object) -> int:
    if not isinstance(weeks, int) or isinstance(weeks, bool):
        raise VHealthError(
            f"assessment.log_window_weeks must be a whole number, got {weeks!r}"
        )
    if not (MIN_LOG_WINDOW_WEEKS <= weeks <= MAX_LOG_WINDOW_WEEKS):
        raise VHealthError(
            f"assessment.log_window_weeks must be between {MIN_LOG_WINDOW_WEEKS} and "
            f"{MAX_LOG_WINDOW_WEEKS}, got {weeks}"
        )
    return weeks
