# Rule catalogue

Every rule below is implemented in `src/vhealth/rules/`. This file is
maintained by hand alongside the code; `CONTRIBUTING.md` requires any new
rule to add a row here in the same change.

| Rule ID | Title | Severity | Evidence required | Limitations |
|---|---|---|---|---|
| `storage.smart_health_not_ok` | Local disk reports non-OK SMART health | High | `storage_devices[].smart_overall_health` | Only disks whose driver exposes SMART to ESXi (typically local SAS/SATA/NVMe); SAN LUNs over FC/iSCSI are not covered. |
| `storage.smart_reallocated_sectors` | Local disk has reallocated sectors | Medium | `storage_devices[].smart_raw` | A small, stable count on an older drive is not urgent by itself; this rule does not track trend over time (single snapshot only). |
| `storage.device_not_on` | Storage device is not in the `on` state | High | `storage_devices[].status` | A device intentionally taken offline for planned maintenance also matches; cannot distinguish planned from unplanned. |
| `hardware.ipmi_sensor_asserted` | IPMI hardware sensor is in an asserted (alarm) state | High | `sensors[].status` | Only discrete asserted/deasserted IPMI sensors are evaluated; analog (threshold-crossing) sensors are not evaluated in v1. |
| `storage.pdl_detected` | Permanent Device Loss (PDL) detected in vmkwarning log | Critical | `log_signal_counts.pdl_error`, `log_events` | Limited to the vmkwarning rotations retained in the bundle at capture time; older events may have already rolled off. |
| `storage.apd_detected` | All-Paths-Down (APD) event detected in vmkwarning log | Critical | `log_signal_counts.apd_event`, `log_events` | Pattern is based on documented VMware KB wording; not yet confirmed against a real APD event in test data (see below). |
| `storage.path_dead_detected` | Dead storage path/device detected in vmkwarning log | High | `log_signal_counts.path_dead`, `log_events` | Same log-retention caveat as PDL. |
| `storage.alua_path_connectivity` | Repeated ALUA path-connectivity errors detected | Medium | `log_signal_counts.alua_no_connection`, `log_events` | Only fires at 3+ occurrences to avoid flagging a single transient blip; the threshold is a heuristic, not a vendor-documented number. |
| `storage.vob_problem_event` | VMkernel Observation (VOB) flagged a storage problem event | Medium | `log_signal_counts.vob_storage_problem`, `log_events` | vobd only logs events ESXi itself classified as `esx.problem.*`; it is not a complete list of storage issues. |
| `coverage.limited_diagnostic_data` | Limited diagnostic data available in this support bundle | Low (Info if only 1-2 categories missing) | `coverage()` -- derived from `storage_adapters`/`storage_devices`/`smart_data`/`hardware_sensors`/`log_signals` presence | Reports what is missing, not why; cannot distinguish a reduced/incident-mode vm-support capture from hardware that genuinely has nothing to report (e.g. no local disks). |

## Validation status

`storage.pdl_detected` and `storage.alua_path_connectivity` have each been
confirmed to fire against a real-world ESXi 8.0.3 `vm-support` bundle
during development (not committed to this repository -- see
`CONTRIBUTING.md` for why). `storage.apd_detected` is implemented from the
documented VMware log wording for an APD event but has not yet been
observed firing against real data; treat it as unverified until it has
been.

`coverage.limited_diagnostic_data` was added after validating against 12
real EAMSC2 ESXi 8.0.3 bundles (locally, not committed): 11 of the 12 had
full esxcli storage-core/SMART/log data and raised real storage findings
as expected; one (`eamsc2esxi01`) turned out to be a reduced/incident-mode
`vm-support` capture missing storage-core, SMART, and log data entirely,
and previously assessed as "0 findings" with no indication that most
checks had not actually run. This rule exists specifically to make that
distinction visible instead of silent. While fixing this, a related bug
was also found and fixed: the `log_signals` coverage flag was computing
"did a bad signal fire" instead of "was log data present to check",
which would have wrongly marked every host with clean logs as having no
log coverage at all -- see `CHANGELOG.md`.

## Adding a rule

A new rule must, in the same change:

1. Live in `src/vhealth/rules/<category>_rules.py` as a plain function
   `HostInfo -> list[Finding]`, registered in that module's `RULES` list
   and picked up via `src/vhealth/rules/registry.py`.
2. Set `evidence_required` and `limitations` on its `Rule(...)` entry.
3. Add a row to this table.
4. Add at least one unit test in `tests/unit/test_rules.py` using the
   synthetic fixture builder in `tests/fixtures/synthetic_bundle.py` (add
   a new parameter there if the existing fixture can't express the
   condition), covering both the firing and non-firing case.

Do not add a rule whose only "evidence" is fabricated/synthetic data with
no real-world sample to validate the pattern string against, unless that
limitation is stated explicitly in this table (as with `apd_detected`
above).
