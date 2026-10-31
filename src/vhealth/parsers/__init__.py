"""Parsers for individual files inside an ESXi vm-support bundle.

Each parser module exposes a ``VERSION`` string and a ``parse(host_dir,
host)`` function that enriches a ``vhealth.models.host.HostInfo`` in
place and returns a list of warning strings. Parsers must never raise on
malformed/missing input -- missing evidence is recorded as a warning so
the rest of the assessment can proceed.
"""

from vhealth.parsers import (
    configstore,
    core_services_status,
    coredump,
    datastore,
    hardware_inventory,
    hostd_health,
    ipmi_sel,
    memory_health,
    mobility,
    multipath,
    nfs_datastore_health,
    nic_link,
    ntp,
    pending_reboot,
    psod_count,
    readme,
    sensors,
    smart,
    ssd_storage_health,
    storage_core,
    system_version,
    vib,
    vm_inventory,
    vmk_log,
    vpxa_status,
    vsan_status,
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
    configstore,
    mobility,
    pending_reboot,
    memory_health,
    nfs_datastore_health,
    ssd_storage_health,
    psod_count,
    core_services_status,
    hostd_health,
    vpxa_status,
    vsan_status,
]

PARSER_VERSIONS = {m.__name__.rsplit(".", 1)[-1]: m.VERSION for m in PARSER_MODULES}
