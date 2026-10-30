# Rule catalogue

Every rule below is implemented in `src/vhealth/rules/`. This file is
maintained by hand alongside the code; `CONTRIBUTING.md` requires any new
rule to add a row here in the same change.

Most rules are per-host: they inspect one `HostInfo` and run once per host
in the assessment. A **fleet rule** (marked below) instead sees every host
discovered in the bundle at once and runs once per assessment -- for
checks that are only meaningful across hosts, such as whether they share a
compatible CPU generation. A single-host bundle never triggers a fleet
rule.

Each rule is also assigned a **category** (`src/vhealth/reporting/summary.py:_CATEGORY_BY_RULE_ID`),
used to group the Recommendation section of the report by subsystem rather
than as one flat list: `Storage`, `Hardware / SEL`, `CPU`, or `Other`.
`Network` and `Memory` are reserved categories for rules not yet written --
see "Adding a rule" below.

| Rule ID | Category | Title | Severity | Evidence required | Limitations |
|---|---|---|---|---|---|
| `storage.smart_health_not_ok` | Storage | Local disk reports non-OK SMART health | High | `storage_devices[].smart_overall_health` | Only disks whose driver exposes SMART to ESXi (typically local SAS/SATA/NVMe); SAN LUNs over FC/iSCSI are not covered. |
| `storage.smart_reallocated_sectors` | Storage | Local disk has reallocated sectors | Medium | `storage_devices[].smart_raw` | A small, stable count on an older drive is not urgent by itself; this rule does not track trend over time (single snapshot only). |
| `storage.device_not_on` | Storage | Storage device is not in the `on` state | High | `storage_devices[].status` | A device intentionally taken offline for planned maintenance also matches; cannot distinguish planned from unplanned. |
| `hardware.ipmi_sensor_asserted` | Hardware / SEL | IPMI hardware sensor is in an asserted (alarm) state | High | `sensors[].status` | Only discrete asserted/deasserted IPMI sensors are evaluated; analog (threshold-crossing) sensors are not evaluated in v1. |
| `storage.pdl_detected` | Storage | Permanent Device Loss (PDL) detected in vmkwarning log | Critical | `log_signal_counts.pdl_error`, `log_events` | Scoped to the last 90 days of the bundle's own capture date (this is a quarterly assessment); limited to the vmkwarning rotations retained in the bundle at capture time; older events are tallied in `log_signal_counts_excluded` but do not drive this finding. |
| `storage.apd_detected` | Storage | All-Paths-Down (APD) event detected in vmkwarning log | Critical | `log_signal_counts.apd_event`, `log_events` | Pattern is based on documented VMware KB wording; not yet confirmed against a real APD event in test data (see below). Same 90-day quarterly scoping as `pdl_detected`. |
| `storage.path_dead_detected` | Storage | Dead storage path/device detected in vmkwarning log | High | `log_signal_counts.path_dead`, `log_events` | Same log-retention and 90-day quarterly-scoping caveats as PDL. |
| `storage.alua_path_connectivity` | Storage | Repeated ALUA path-connectivity errors detected | Medium | `log_signal_counts.alua_no_connection`, `log_events` | Only fires at 3+ occurrences to avoid flagging a single transient blip; the threshold is a heuristic, not a vendor-documented number. Same 90-day quarterly scoping as PDL. |
| `storage.vob_problem_event` | Storage | VMkernel Observation (VOB) flagged a storage problem event | Medium | `log_signal_counts.vob_storage_problem`, `log_events` | vobd only logs events ESXi itself classified as `esx.problem.*`; it is not a complete list of storage issues. Same 90-day quarterly scoping as PDL. |
| `storage.multipath_all_paths_dead` | Storage | All multipathing paths to a storage device are dead | Critical | `multipath_devices[].dead_paths`/`total_paths` (from `esxcli storage nmp path list`) | Point-in-time snapshot at capture only; does not confirm which datastore/VM (if any) is backed by the affected device. Sees a dead path even if it predates every retained vmkwarning rotation, unlike the log-derived `storage.path_dead_detected`. |
| `storage.multipath_reduced_redundancy` | Storage | Storage device has one or more dead multipathing paths | High | `multipath_devices[].dead_paths`/`total_paths` (from `esxcli storage nmp path list`) | Point-in-time snapshot at capture only; same visibility advantage over `storage.path_dead_detected` as above. |
| `coverage.limited_diagnostic_data` | Other | Limited diagnostic data available in this support bundle | Low (Info if only 1-2 categories missing) | `coverage()` -- derived from `storage_adapters`/`storage_devices`/`smart_data`/`hardware_sensors`/`log_signals`/`hardware_inventory` presence | Reports what is missing, not why; cannot distinguish a reduced/incident-mode vm-support capture from hardware that genuinely has nothing to report (e.g. no local disks). |
| `fleet.cpu_model_mismatch` (**fleet rule**) | CPU | Multiple CPU models detected across assessed hosts | Medium | `cpu_model` (from `smbiosDump.txt`) on 2+ hosts in the assessment | Compares raw SMBIOS CPU model strings across hosts in this assessment only; has no visibility into actual vCenter cluster membership or EVC configuration, so it cannot tell you whether these hosts share a cluster or whether EVC already mitigates the mismatch. |
| `hardware.ntp_not_synchronized` | Other | Host clock is not synchronized via NTP | Medium | `ntp_time_synchronized`, `ntp_servers` (from `esxcli system ntp get`) | Point-in-time snapshot from the bundle's capture moment only; a host that synced (or lost sync) before/after capture is not reflected. Does not distinguish "NTP service disabled" from "enabled but server unreachable" -- both surface as `Time Synchronized = false`. |
| `hardware.coredump_not_configured` | Other | No active kernel-coredump target configured | Medium | `coredump_configured` (from `esxcli system coredump file list`) | Point-in-time snapshot at capture only. Implemented from documented esxcli behaviour; every real bundle seen so far has at least one `Active=true`/`Configured=true` row, so the firing (not-configured) case has not yet been observed against real-world data -- see below. |
| `hardware.community_supported_vib_installed` | Other | Host has a CommunitySupported (unsupported) VIB installed | Medium | `community_supported_vibs` (from `esxcli software vib list`) | Only reports the acceptance level ESXi itself records; cannot see any separately-granted VMware GSS exception for a specific VIB in this environment. |

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

`fleet.cpu_model_mismatch` was first validated against two real EAMSC2
hosts run together in one assessment (`eamsc2esxi03`/`eamsc2esxi04`):
both report the identical CPU model from `smbiosDump.txt`, so the rule
correctly did not fire. It has since fired against real data: a 20-host
real vCenter-style bundle (Etisalat "HO-Q4" site) genuinely contains 6
different CPU models across its hosts (Xeon Gold 6258R/6330N/6430/5218,
Silver 4216/4110), and the rule correctly flagged it.

The 90-day quarterly log-window scoping (`storage.pdl_detected` and the
other vmkwarning/vobd-derived rules above) was validated against real
EAMSC2 bundles: `eamsc2esxi03`'s retained `vmkwarning` rotations span
roughly 2026-08-06 to 2026-10-12 against a 2026-10-27 capture date, all
within the 90-day window, so no exclusions occurred there; the exclusion
path itself (an event older than 90 days being tallied in
`log_signal_counts_excluded` instead of raising a finding) is covered by
a synthetic unit test rather than observed in this specific real sample.

`hardware.ntp_not_synchronized` was validated against a real 10-host
EAMSC2 bundle: `localcli system ntp get` on `eamsc2esxi02` genuinely
reports `"Time Synchronized": false` while the other 9 hosts in the same
bundle all report `true`, so the rule correctly fires on exactly the one
host with a real, currently-unresolved clock-sync problem.

`hardware.coredump_not_configured`'s table parsing (`localcli system
coredump file list`, via the shared `parse_fixed_width_table` helper) was
confirmed against the same real 10-host EAMSC2 bundle: all 10 hosts
report exactly one row with `Active=true`/`Configured=true`, so the
non-firing path is real-data-validated. The firing path (no such row --
either an empty table or one with `Active=false`/`Configured=false`) is
implemented from documented `esxcli` behaviour and covered by a
synthetic unit test only, per the "Do not add a rule..." rule below,
since no real bundle seen so far has a misconfigured coredump target.

`hardware.community_supported_vib_installed`'s table parsing (`esxcli
software vib list`, via the shared `parse_fixed_width_table` helper) was
confirmed against the same real 10-host EAMSC2 bundle: each host lists
~99 VIBs across exactly `VMwareCertified`/`VMwareAccepted`/
`PartnerSupported`, with zero `CommunitySupported` entries anywhere, so
the non-firing path is real-data-validated. The firing path has not yet
been observed against real-world data and is covered by a synthetic
unit test only.

`storage.multipath_all_paths_dead` has fired against real data: the
same real 10-host EAMSC2 bundle shows device
`naa.600507688283b1c88000000000000007` ("IBM Fibre Channel Disk") with
its one and only known path reporting `Group State: dead` on both
`eamsc2esxi08` and `eamsc2esxi09` -- a genuine, previously-unreported
storage-access problem this rule correctly caught.
`storage.multipath_reduced_redundancy` has not yet been observed firing
(no real bundle seen so far has a device with some, but not all, paths
dead) and is covered by a synthetic unit test only.

## Adding a rule

A new rule must, in the same change:

1. Live in `src/vhealth/rules/<category>_rules.py` as a plain function
   `HostInfo -> list[Finding]`, registered in that module's `RULES` list
   and picked up via `src/vhealth/rules/registry.py`.
2. Set `evidence_required` and `limitations` on its `Rule(...)` entry.
   Also set a specific, actionable `remediation` on each `Finding` it
   raises -- state where to look (the exact host-side file/log this rule
   reads) and, where relevant, what external system to correlate it
   with, not a generic "investigate further".
3. Add a row to this table, including its category. Add an entry to
   `_CATEGORY_BY_RULE_ID` in `src/vhealth/reporting/summary.py` -- pick
   an existing category (`Storage`, `Hardware / SEL`, `CPU`, `Network`,
   `Memory`, `Other`) or add a new one in both places.
4. Add at least one unit test in `tests/unit/test_rules.py` using the
   synthetic fixture builder in `tests/fixtures/synthetic_bundle.py` (add
   a new parameter there if the existing fixture can't express the
   condition), covering both the firing and non-firing case.

Do not add a rule whose only "evidence" is fabricated/synthetic data with
no real-world sample to validate the pattern string against, unless that
limitation is stated explicitly in this table (as with `apd_detected`
above).
