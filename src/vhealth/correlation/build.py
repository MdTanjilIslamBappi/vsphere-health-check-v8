"""Turn discovered host bundles into normalised HostInfo records."""

from __future__ import annotations

from vhealth.discovery.bundle import HostBundleRef
from vhealth.models.host import HostInfo
from vhealth.parsers import PARSER_MODULES


def build_host_infos(bundle_refs: list[HostBundleRef]) -> list[HostInfo]:
    hosts: list[HostInfo] = []
    for ref in bundle_refs:
        # Store the bundle directory *name*, not its absolute path: the
        # absolute path lives under a freshly randomised extraction temp
        # directory on every run, which would otherwise make two
        # assessments of the identical input bundle non-comparable.
        host = HostInfo(hostname=ref.hostname_hint, bundle_source=ref.root.name)
        for module in PARSER_MODULES:
            try:
                warnings = module.parse(ref.root, host)
            except Exception as exc:  # noqa: BLE001 - a single parser must not abort the run
                warnings = [f"{module.__name__} failed unexpectedly: {exc}"]
            host.parse_warnings.extend(warnings)
        hosts.append(host)
    return hosts
