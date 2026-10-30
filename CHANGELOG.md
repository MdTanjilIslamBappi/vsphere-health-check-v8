# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - Unreleased

Initial implementation. Built and tested on Windows 11 with Python 3.12 and
`uv` 0.13. Also tested on Linux via WSL2 (Kali Linux, Debian-based) --
install, the full test suite, a real `assess` run, and uninstall all pass
there too -- but this is not a bare-metal/Ubuntu test, and the PyInstaller
build is still Windows-only (see [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md)
and the "Known limitations" section of [README.md](README.md)).

### Changed

- Report convention rework based on direct user feedback on the first
  redesign: the main report now mirrors a customer-facing executive
  health-check convention exactly (Executive Summary, Scope, System
  Status 3.1-3.4 ending in Recommendation -- no more), written in report
  voice ("This quarterly health check assessment was performed on the
  customer's...") instead of tool/software voice. The full per-finding
  evidence dump that used to live inline in the main report now lives in
  a separate companion document instead (`findings-log.docx`/
  `findings-log.html`, written automatically alongside `report.docx`/
  `report.html`), so the main report stays a concise executive read.
- Log-based findings (PDL/APD/dead-path/ALUA/VOB) are now scoped to the
  last 90 days of the bundle's own capture date -- this is a *quarterly*
  health check, so an event from a year-old log rotation no longer
  appears as an active finding. Older matches are still tallied
  (`HostInfo.log_signal_counts_excluded`) rather than discarded, and a
  finding's limitations note how many older occurrences exist outside
  the window, but they do not drive severity or an active finding.

### Added

- New default HTML/DOCX report layout: cover page, a Version History table
  (`--revision`/`--description` options, default `V01`/"Initial copy"), a
  table of contents, Executive Summary, Scope of Health Check (a single
  checked/not-checked bullet list -- EVC mode, datastores, VM inventory,
  and vCenter alarms are listed as explicitly not assessed rather than
  guessed or silently omitted, since an ESXi host bundle has no vCenter
  data), and System Status: 3.1 an aggregate Hardware Status grid, 3.2 a
  VMware Components status table (Component/Status/Remarks) plus a "Key
  Findings at a Glance" bullet list, 3.3 an ESXi host inventory table
  (Server Name/Management IP/Server Model/CPU Model) plus a "Detailed
  Observations" bullet list, and 3.4 Recommendation grouping findings by
  rule with an Affected/Action layout. See RULE_CATALOG.md and
  SUPPORTED_FORMATS.md.
- `findings-log.docx`/`findings-log.html`: a companion document, written
  automatically alongside every `report.docx`/`report.html`, carrying the
  full per-finding detail (evidence lines, remediation, limitations) that
  used to live inline in the main report.
- `hardware_inventory.py` parser: server manufacturer/model and CPU model
  (from `commands/smbiosDump.txt`), management IP (`vmk0` from
  `commands/esxcfg-vmknic_-l.txt`), and host-reported cluster/compute-resource
  membership (`commands/clusterAdmin_cluster-status.txt`, where present).
  Validated against real EAMSC2 bundles: extracted server model, CPU
  model, and management IP matched a prior hand-written customer report
  for the same hosts exactly.
- `fleet.cpu_model_mismatch` rule: a new "fleet rule" category that
  compares data *across* every host in one assessment rather than one
  host at a time, flagging mixed CPU models (a real vMotion/EVC
  compatibility risk) across the hosts in a single run.
- `--engineer`/`--author`/`--verifier` options on `assess` and `report`,
  shown on the cover page of both the HTML and DOCX reports. Any left
  unset are prompted for interactively (press Enter to skip); `--no-prompt`
  or a non-interactive run (CI, a script) leaves them unset instead of
  hanging on a prompt. Not stored in `assessment.json` -- a report can be
  re-rendered later (e.g. a verifier adding their name) without re-running
  the assessment.
- `coverage.limited_diagnostic_data` rule: raises a visible finding (not
  just a buried metadata flag) when a bundle is missing whole categories
  of diagnostic data (storage-core, SMART, IPMI, or log signals), so a
  short findings list can't be misread as "all checked, all clean" when
  it may really mean "mostly unchecked". See RULE_CATALOG.md.
- `vhealth` CLI (`inspect`, `assess`, `report`, `--version`) built on Click.
- Safe, offline extraction of `.zip` and `.tgz` support bundles with
  zip-slip protection, size/entry/compression-ratio limits, and graceful
  degradation on truncated/corrupted archives.
- Discovery of ESXi `vm-support` host bundles inside a single-host `.tgz`
  or a multi-host vCenter-style `.zip`.
- Parsers for: vm-support `README` metadata, ESXi version/build/hostname,
  storage adapter/device inventory (`esxcli storage core`), SMART health
  (`smartinfo.txt`), IPMI hardware sensors, and storage/hardware signals
  from rotated `vmkwarning`/`vobd` logs.
- A rule engine with findings for: SMART health failures and reallocated
  sectors, storage devices not in the `on` state, asserted IPMI hardware
  sensors, and PDL/APD/dead-path/ALUA/VOB storage log signals.
- Versioned, machine-readable `assessment.json` output (schema v1.0.0)
  carrying full reproducibility metadata (input hash, parser/rule-engine
  versions, evidence manifest, processing warnings).
- HTML (Jinja2) and Word (`python-docx`) report generation from either a
  fresh assessment or a saved `assessment.json`.
- `scripts/windows/uninstall.ps1` / `scripts/linux/uninstall.sh`, removing
  everything the matching install script created (the project-local
  `.venv` and local build/test caches), and a
  [Beginner's Guide](docs/BEGINNER_GUIDE.md) for readers new to the
  command line, Python tooling, or VMware terminology.
- `scripts/windows/install.ps1` / `scripts/linux/install.sh` for a
  reproducible, project-local, non-admin install via `uv`. Split into
  per-OS folders so each platform only sees its own two scripts.
- Unit, integration, security and cross-platform test suites using
  synthetic fixtures (no customer data).
- `scripts/build_release.py` (PyInstaller, one-file build). Built and
  smoke-tested on Windows 11/Python 3.12: the resulting
  `vhealth-windows-amd64.exe` (~18 MB) ran `--version` and a full
  `assess` (bundled templates/config/schema included) outside the repo
  and outside the dev virtualenv. **Not yet built or tested on Linux.**
- `hardware.ntp_not_synchronized` rule and `ntp.py` parser: reads each
  ESXi host's own `localcli system ntp get` output and flags a host
  whose clock is not actually synchronized, regardless of whether the
  NTP service is enabled -- no vCenter bundle required. Surfaced as a
  new "Time Synchronization (NTP)" row in the report's component-status
  table. Validated against a real 10-host EAMSC2 bundle: correctly
  flagged the one host (`eamsc2esxi02`) genuinely reporting
  `Time Synchronized: false`, and stayed silent on the other 9.
- `hardware.coredump_not_configured` rule and `coredump.py` parser:
  reads each ESXi host's own `localcli system coredump file list`
  output and flags a host with no kernel-coredump target marked both
  Active and Configured -- without one, a PSOD leaves no crash dump to
  root-cause it. Surfaced as a new "Kernel Coredump Configuration" row
  in the report's component-status table. Table parsing confirmed
  against a real 10-host EAMSC2 bundle (all 10 correctly resolve as
  configured); the firing (not-configured) case has not yet been
  observed against real data and is covered by a synthetic test only.
- `hardware.community_supported_vib_installed` rule and `vib.py`
  parser: reads each ESXi host's own `localcli software vib list`
  output and flags any VIB at the `CommunitySupported` acceptance
  level, which VMware GSS does not provide support for. Surfaced as a
  new "VIB Acceptance Level" row in the report's component-status
  table. Table parsing confirmed against a real 10-host EAMSC2 bundle
  (~99 VIBs per host, all `VMwareCertified`/`VMwareAccepted`/
  `PartnerSupported`, zero `CommunitySupported`); the firing case has
  not yet been observed against real data and is covered by a
  synthetic test only.
- `storage.multipath_all_paths_dead` / `storage.multipath_reduced_redundancy`
  rules and `multipath.py` parser: reads each ESXi host's own `esxcli
  storage nmp path list` output and aggregates path state per device,
  flagging a device with some or all of its known paths reporting
  `Group State: dead`. Unlike the vmkwarning-log-derived
  `storage.path_dead_detected`, this is a direct point-in-time
  snapshot, so it also catches a path that has been dead since before
  the oldest retained log rotation. Folded into the existing "Storage
  & Hardware Findings" component row rather than a new one, same as
  the other storage rules. **Fired against real data on first try**:
  the real 10-host EAMSC2 bundle has device
  `naa.600507688283b1c88000000000000007` ("IBM Fibre Channel Disk")
  with its one and only known path dead on both `eamsc2esxi08` and
  `eamsc2esxi09` -- a genuine, previously-unreported storage-access
  problem this rule caught.
- `network.vswitch_single_uplink` rule and `vswitch.py` parser: reads
  each ESXi host's own `esxcfg-vswitch -l` output and flags any
  standard vSwitch/DVS with exactly one physical uplink NIC (no
  cable/card/upstream-switch-port redundancy), excluding the BMC/iDRAC
  out-of-band vSwitch's virtual `vusb0` uplink, which has no physical
  redundancy to have by design. Also adds `fleet.vswitch_mtu_mismatch`
  (in `fleet_rules.py`), flagging a same-named vSwitch/DVS configured
  with different MTU values across the hosts in one assessment.
  Surfaced as a new "Network (vSwitch/DVS)" component row, and puts
  the `Network` category (reserved since the report's first version)
  to use for the first time. The `esxcfg-vswitch -l` output has no
  dashed separator row and is not reliably fixed-width either -- a
  real 22-character DVS name shifts every later column right of where
  shorter names put them -- so the parser splits each data row on 2+
  whitespace characters instead of slicing at fixed offsets.
  **Fired against real data on first try**: the real 10-host EAMSC2
  bundle shows host `eamsc2esxi09` with all three of its DVS switches
  down to a single uplink each (every other host has two), and hosts
  `eamsc2esxi14`/`eamsc2esxi15` each separately down to one uplink on
  a fourth DVS -- five genuine, previously-unreported redundancy gaps.
- The companion `findings-log.docx`/`findings-log.html` (the detailed,
  per-finding document separate from the main executive report) now
  groups its findings under category headers (Storage, Network,
  Hardware / SEL, CPU, vCenter, Other -- `findings_by_category()` in
  `reporting/summary.py`, reusing the same category map the main
  report's Recommendation section already assigns per item) instead of
  one flat list sorted only by severity, so a reader can jump straight
  to the subsystem they care about. Verified against the real 10-host
  EAMSC2 bundle: its 47 findings split into Storage (34), Network (5),
  CPU (1), vCenter (2), and Other (5) sections.
- `vhealth assess` now also accepts the bundle path and output
  directory as plain positional arguments (`vhealth assess
  support-bundle.zip [output-dir]`) alongside the existing `--input`/
  `--output` flags, and the output directory is now optional: if
  omitted entirely, a new folder under the system temp directory is
  used instead and its path is printed as `Report location: ...` once
  the report is written, so the whole tool can be driven with one line
  without first deciding where output should go. Verified by running
  this exact one-line form against the real 4.6GB EAMSC2 bundle end to
  end (extraction through report generation).
- `hardware.sel_ecc_uncorrectable`, `hardware.sel_drive_predictive_failure`,
  `hardware.sel_psu_failure`, and `hardware.sel_temperature_critical`
  rules and `ipmi_sel.py` parser: read each ESXi host's own IPMI System
  Event Log (`esxcli hardware ipmi sel list`), a historical event log
  distinct from the current-sensor-state `hardware.ipmi_sensor_asserted`
  rule -- a transient event that already cleared itself (a drive pulled
  and replaced, a brief PSU blip) still shows up here even though the
  live sensor reading is clean again at capture time. Only `Assert +`
  records matching a hand-picked set of unambiguous hardware-failure
  message types are tracked; routine SEL chatter (boot/shutdown,
  log-area-reset housekeeping, chassis intrusion, and the more ambiguous
  AC-lost/redundancy-state message types) is intentionally not reported
  on. Same 90-day quarterly log-window scoping as the existing
  vmkwarning/vobd-derived rules (`log_rules.py`), reusing the same
  `host.log_signal_counts`/`log_signal_counts_excluded`/`log_events`
  fields. Folded into the existing "Storage & Hardware Findings"
  component row and "Hardware / SEL" category rather than a new row.
  **Fired against real data on first try**: the real 10-host EAMSC2
  bundle's SEL history for `eamsc2esxi17` shows `Assert + Drive Slot
  Predictive Failure` on 2026-08-01, within the 90-day window of the
  bundle's 2026-10-26 capture date; the same SEL history also contains
  real (but 9+ months stale, correctly excluded) ECC, PSU-failure, and
  critical-temperature events on other hosts, confirming the message
  matching end to end even though only the drive-predictive-failure
  signal is young enough to raise an active finding in this bundle.
- `network.vswitch_uplink_link_down` and `network.vswitch_all_uplinks_down`
  rules and `nic_link.py` parser: read each ESXi host's own physical NIC
  link state (`nicinfo.sh`) and cross-reference it against the uplink
  NICs each vSwitch/DVS reports in `esxcfg-vswitch -l`. The existing
  `network.vswitch_single_uplink` rule only counts how many uplinks are
  *configured*; it cannot see that one of two configured uplinks has no
  actual cable/link, which already loses the redundancy a reader would
  assume is intact. The parser slices out just the `nicinfo.sh` summary
  table (it has a lot of unrelated per-NIC detail after it, separated
  by a blank line, which `table_utils.parse_fixed_width_table` has no
  notion of stopping at) using the same header/dash-separator detection
  `table_utils.py` itself uses. Folded into the existing "Storage &
  Hardware Findings" row/"Network" category and the existing "Network
  (vSwitch/DVS)" component row rather than a new one. **Fired against
  real data on first try**: the real 10-host EAMSC2 bundle shows hosts
  `eamsc2esxi02`, `eamsc2esxi07`, and `eamsc2esxi08` each with all three
  of their DVS switches configured with 2 uplinks (so
  `vswitch_single_uplink` stays silent), but one of those two uplinks
  per switch (9 total) reports `Link Status: Down` in `nicinfo.sh` --
  redundancy that was already gone and completely invisible to the
  configured-uplink-count check alone.
- `fleet.datastore_usage_warning`/`fleet.datastore_usage_critical` rules:
  `datastore.py` now also extracts each VMFS volume's own
  `Capacity .../avail` line from the same `vmkfstools -P -v 10` dump it
  already read for datastore names, and two new fleet rules compare
  each distinct datastore's used space (deduplicated by UUID, since a
  shared datastore is typically mounted and independently reported by
  every host that uses it) against vCenter's own default "Datastore
  usage on disk" alarm thresholds -- Warning at 75% used, Critical at
  85% used (Broadcom KB 450627) -- rather than an invented number.
  **This corrects a previously-documented limitation**: earlier
  versions of this tool's own docs (`SUPPORTED_FORMATS.md`, this
  report's Scope of Health Check wording) stated that datastore
  capacity/free-space "exists only in vCenter's own inventory database"
  and is never assessable from a support bundle. That was wrong -- it
  is a direct per-host fact in a file already being read for an
  unrelated purpose; only vCenter-side storage-policy compliance status
  and historical capacity trending remain genuinely vCenter-only. All
  affected scope/report wording is corrected in this change. **Fired
  against real data on first try**: the real 10-host EAMSC2 bundle has
  four real, shared datastores above the 75%-used warning threshold
  (`ETA-DRM APP Server- Datastore` 82.5%, `Sys-Admin_Datastore08-Digital
  Archive Project` 77.3%, `PI_Network_Volume` 75.8%, `ADMS Project Data
  Store` 75.1%), each correctly deduplicated to one finding per
  datastore rather than one per each of the 10 hosts that mounts it.
- `hardware.configstore_integrity_check_failed` rule and `configstore.py`
  parser: reads each ESXi host's own ConfigStore (`/etc/vmware/configstore`,
  the SQLite-backed database that replaced the old flat-file `esx.conf`
  in ESXi 7.x/8.x) integrity check result (`sqlite3 ... PRAGMA
  integrity_check`) and flags anything other than the healthy `ok`
  result as Critical. ConfigStore corruption/exhaustion is a documented
  real failure mode (Broadcom KB 312114, KB 438104), not a hypothetical
  one. New "ConfigStore Integrity" component row, folded into the
  existing "Other" category. Validated against the real 10-host EAMSC2
  bundle: every host reports `ok`, so the healthy (non-firing) path is
  real-data-confirmed; the firing (corrupt) path is covered by a
  synthetic unit test only, same convention as `coredump_not_configured`
  and `community_supported_vib_installed` before it.
- `network.mobility_health_check_error` rule and `mobility.py` parser:
  reads ESXi's own built-in migration-network health-check tool
  (`vmware.mobility.mobility_health_checks`, captured as
  `mobility_network_health_check.txt`) and flags any netService
  (vMotion, Provisioning) whose own reported status is `"ERROR"` --
  unlike every other rule in this catalogue, the verdict here is
  ESXi's own, not something vhealth infers from raw state. New
  "Migration Network Health" component row and scope item, folded into
  the existing "Network" category. **Fired against real data on first
  try**: on the real 10-host EAMSC2 bundle, the tool itself is a Python
  traceback instead of JSON on 8 of 10 hosts (a build/configuration
  incompatibility, correctly treated as missing data rather than a
  finding), but on the 2 hosts where it did run (`eamsc2esxi18`,
  `eamsc2esxi22`) both VMOTION and PROVISIONING report ERROR with two
  distinct, independently-confirmable causes: PROVISIONING's explicit
  `"No valid vmknics"` sub-check error, and VMOTION testing only 1 of
  22 expected cluster-peer destinations for connectivity despite every
  individual sub-check passing -- a genuine, previously-unreported
  migration-readiness gap surfaced directly by VMware's own tooling.

### Fixed

- CI's `push` trigger (`.github/workflows/ci.yml`) was scoped to
  `branches: [main]`, but the repository's actual default branch is
  `master` -- so pushing straight to `master` never ran CI via that
  trigger (the `pull_request` trigger was unaffected). Found during a
  Stage 0 baseline audit; fixed by pointing the trigger at `master`.
- `_resolve_authorship()` decided whether to prompt based solely on
  `sys.stdin.isatty()`, which can report a tty is attached even in some
  unattended/automation contexts with nobody present to answer -- leaving
  the prompt to hang indefinitely. The prompts are now wrapped so an
  `EOFError`/abort while reading input is treated the same as
  `--no-prompt` (leave the field unset) instead of propagating.
- `supported_format_coverage.log_signals` (and the new coverage rule built
  on the same data) previously computed "did a bad signal fire in the
  logs" rather than "was log data present to check" -- a perfectly
  healthy host with clean vmkwarning/vobd logs was wrongly reported as
  having no log coverage at all. Found while validating against real
  data; fixed by tracking whether log rotations were found, independent
  of whether anything in them matched a known-bad pattern.

### Validated

- Re-ran the full tool against all 12 real EAMSC2 ESXi 8.0.3 `vm-support`
  bundles (locally, never committed -- see CONTRIBUTING.md). All 12
  completed without error; 11 had full diagnostic data and raised real
  storage findings (PDL, ALUA, VOB, a dead-state device); one
  (`eamsc2esxi01`) turned out to be a reduced/incident-mode capture
  missing storage-core/SMART/log data entirely, which is what led to the
  `coverage.limited_diagnostic_data` rule and the `log_signals` fix above.

### Known limitations

- Linux validation so far is limited to WSL2 (Kali Linux, Debian-based):
  install.sh/uninstall.sh, the full test suite, and a real `assess` run
  via the installed CLI binary all pass there. Bare-metal Ubuntu/Debian
  has not been tried, and the PyInstaller portable binary has still only
  been built and tested on Windows 11 + Python 3.12 (see
  [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md) for the exact matrix).
- Only a `vmkwarning`-derived subset of vmkernel events is scanned; this
  tool does not decode the binary VLF log format some ESXi 8.x releases
  use for the full `vmkernel.log` (see SUPPORTED_FORMATS.md).
- PyInstaller build verified on Windows only; Linux portable binary not
  yet attempted.
- Offline installation package procedure validated on Windows (see
  `docs/OFFLINE_INSTALL.md`); not yet attempted on Linux. On this
  development machine, a local Windows Application Control policy
  blocked running the generated `vhealth.exe` shim directly (though
  `python -m vhealth.cli` worked); if you hit the same thing, see that
  doc's "Known gap" section.
- Rule catalogue covers storage/RAID/hardware-sensor health only; no
  networking, compute, or vSAN-specific rules yet.
