"""Parsers for individual files inside an ESXi vm-support bundle.

Each parser module exposes a ``VERSION`` string and a ``parse(host_dir,
host)`` function that enriches a ``vhealth.models.host.HostInfo`` in
place and returns a list of warning strings. Parsers must never raise on
malformed/missing input -- missing evidence is recorded as a warning so
the rest of the assessment can proceed.
"""

from vhealth.parsers import (
    coredump,
    datastore,
    hardware_inventory,
    ipmi_sel,
    multipath,
    nic_link,
    ntp,
    readme,
    sensors,
    smart,
    storage_core,
    system_version,
    vib,
    vm_inventory,
    vmk_log,
    vswitch,
)

PARSER_MODULES = [
    readme,
    system_version,
    storage_core,
    datastore,
    vm_inventory,
    smart,
    sensors,
    vmk_log,
    hardware_inventory,
    ntp,
    coredump,
    vib,
    multipath,
    vswitch,
    ipmi_sel,
    nic_link,
]

PARSER_VERSIONS = {m.__name__.rsplit(".", 1)[-1]: m.VERSION for m in PARSER_MODULES}
