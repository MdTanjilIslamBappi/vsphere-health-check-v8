"""Turn discovered host and vCenter bundles into normalised model records."""

from __future__ import annotations

from vhealth.discovery.bundle import HostBundleRef, VCenterBundleRef
from vhealth.models.host import HostInfo
from vhealth.models.vcenter import VCenterInfo
from vhealth.parsers import PARSER_MODULES
from vhealth.parsers import vcenter as vcenter_parser


def build_host_infos(
    bundle_refs: list[HostBundleRef], log_window_weeks: int = 13
) -> list[HostInfo]:
    hosts: list[HostInfo] = []
    for ref in bundle_refs:
        # Store the bundle directory *name*, not its absolute path: the
        # absolute path lives under a freshly randomised extraction temp
        # directory on every run, which would otherwise make two
        # assessments of the identical input bundle non-comparable.
        host = HostInfo(
            hostname=ref.hostname_hint,
            bundle_source=ref.root.name,
            log_window_weeks=log_window_weeks,
        )
        for module in PARSER_MODULES:
            try:
                warnings = module.parse(ref.root, host)
            except Exception as exc:  # noqa: BLE001 - a single parser must not abort the run
                warnings = [f"{module.__name__} failed unexpectedly: {exc}"]
            host.parse_warnings.extend(warnings)
        hosts.append(host)
    return hosts


def build_vcenter_info(ref: VCenterBundleRef) -> VCenterInfo:
    """Parse one vCenter ``vc-support`` bundle directory into a VCenterInfo."""
    vcenter = VCenterInfo(
        hostname=ref.hostname_hint or "vCenter Server", bundle_source=ref.root.name
    )
    try:
        warnings = vcenter_parser.parse(ref.root, vcenter)
    except Exception as exc:  # noqa: BLE001 - a single parser must not abort the run
        warnings = [f"vcenter parser failed unexpectedly: {exc}"]
    vcenter.parse_warnings.extend(warnings)
    return vcenter
