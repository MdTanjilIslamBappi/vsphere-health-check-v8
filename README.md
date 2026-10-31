# vhealth

Offline health assessment for VMware vSphere support bundles.

`vhealth` reads a customer-supplied ESXi/vCenter diagnostic bundle (the
`.zip`/`.tgz` produced by `vm-support`), runs a catalogue of assessment
rules against it, and produces a professional HTML/DOCX report — entirely
on your own machine. It never connects to vCenter, an ESXi host, or any
external/cloud service, and it never requires customer credentials.

## Status

Early alpha. See [CHANGELOG.md](CHANGELOG.md) for what has actually been
built and tested so far, and [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md)
for which bundle formats and ESXi versions have been validated.

New to this, or new to the command line / VMware in general? Start with
the [Beginner's Guide](docs/BEGINNER_GUIDE.md) instead — it walks through
every step in plain English.

## Requirements

* Python 3.11+
* [uv](https://docs.astral.sh/uv/) for dependency management
* Windows 10/11, or a current Ubuntu/Debian Linux (see
  [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md) for the exact tested matrix)

## Install

```bash
git clone https://github.com/MdTanjilIslamBappi/vsphere-health-check-v8.git
cd vsphere-health-check-v8

# Linux/macOS
./scripts/linux/install.sh

# Windows PowerShell
.\scripts\windows\install.ps1
```

Both scripts create a project-local virtual environment (`.venv`), install
pinned dependencies from `uv.lock`, install `vhealth` into it, and print
the exact command to run it. `scripts/windows/` and `scripts/linux/` each
hold a matching install/uninstall pair, so you only need to look at the
folder for your own OS.

**Using the same checkout from both Windows and WSL/Linux** (e.g. the
repo lives at `C:\path\to\repo`, which is the same folder as
`/mnt/c/path/to/repo` in WSL)? A Windows venv and a Linux venv can't be
the same directory, so give each OS its own venv name:

```bash
# Windows PowerShell
.\scripts\windows\install.ps1

# WSL/Linux, same checkout
./scripts/linux/install.sh .venv-linux
```

Both scripts take an optional venv directory name as their first
argument (default `.venv`), and the matching uninstall script takes the
same argument.

## Uninstall

```bash
# Linux/macOS
./scripts/linux/uninstall.sh

# Windows PowerShell
.\scripts\windows\uninstall.ps1
```

This removes the `.venv` virtual environment and any local build/test
caches (`dist/`, `build/`, `.pytest_cache/`, etc.) — i.e. everything
`install.sh`/`install.ps1` created. If you installed to a custom
directory (see above), pass that same name, e.g.
`./scripts/linux/uninstall.sh .venv-linux`. It does **not** remove `uv`
or Python themselves (they're outside this repo and likely used by other
projects), and it does **not** touch any report folders you passed to
`vhealth assess --output ...` — those are your own generated output.

To remove vhealth completely, also delete the folder you cloned the repo
into, and uninstall `uv` itself if you don't need it elsewhere (see
[the uv docs](https://docs.astral.sh/uv/getting-started/installation/#uninstallation)).

## Usage

```bash
vhealth --version

# See what's inside a bundle without running a full assessment
vhealth inspect --input support-bundle.zip

# Run the full assessment and write JSON + reports
vhealth assess --input support-bundle.zip --output ./out

# Same thing, shortest form: positional paths, no flags needed
vhealth assess support-bundle.zip ./out

# Output directory can be left out entirely -- a temp folder is used
# instead, and its path is printed at the end
vhealth assess support-bundle.zip

# Only count log/event-history signals from the last 4 weeks instead of
# the default 13 (1-26 weeks allowed)
vhealth assess support-bundle.zip ./out --weeks 4

# Re-render reports from a saved assessment.json (no need to re-parse)
vhealth report --assessment ./out/assessment.json --format docx,html --output ./out
```

Optional branding/behaviour overrides go in a TOML config file, passed with
`--config`; see [`src/vhealth/resources/defaults/config.default.toml`](src/vhealth/resources/defaults/config.default.toml)
for every available key and its default.

### Crediting who prepared the report

`assess` and `report` both accept `--engineer`, `--author`, and
`--verifier`, which appear on the cover page of the HTML and DOCX
reports, plus `--revision` (default `V01`) and `--description` (default
"Initial copy") for the report's Version History table:

```bash
vhealth assess --input support-bundle.zip --output ./out \
  --engineer "Jane Doe" --author "Jane Doe" --verifier "John Smith" \
  --revision V02 --description "Re-verified after remediation"
```

Leave `--engineer`/`--author`/`--verifier` off and you'll be prompted for
each interactively (press Enter to skip); pass `--no-prompt` to skip the
prompts entirely and leave them unset, which also happens automatically in
a non-interactive run (CI, a script). `--revision`/`--description` are
never prompted for. None of this is written into `assessment.json` -- a
verifier can add their name on a later `vhealth report` re-render without
re-running the assessment.

### Report layout

Every HTML/DOCX report has the same structure, written as a customer-facing
health check: a cover page, a Version History table, a table of contents,
an Executive Summary, a Scope of Health Check (a single bullet list --
items that need vCenter-level data, such as EVC mode, datastores, VM
inventory, or vCenter alarms, are listed as explicitly not assessed rather
than guessed or silently dropped), and a System Status section: 3.1 an
aggregate hardware-status grid, 3.2 a VMware-components status table plus
"Key Findings at a Glance", 3.3 an ESXi host inventory table (server
model/CPU model/management IP) plus "Detailed Observations", and 3.4
grouped Recommendations. Each 3.4 group names its category (Storage,
Network, Hardware / SEL, CPU, Memory, vCenter, or Other -- see
RULE_CATALOG.md), which hosts/objects are affected, why the finding
matters, specifically where to check it (the host-side log/file and,
where relevant, which external system to correlate it with), and a
short evidence table of the matching lines. See RULE_CATALOG.md and
SUPPORTED_FORMATS.md for exactly what backs each section.

When the bundle includes a vCenter Server appliance capture
(`vc-support`), its own "vCenter Server" status row additionally
covers `service-control` service status, appliance filesystem usage,
and vsphere.local SSO/STS certificate expiry -- distinct from the
vCenter-*database* content (EVC baseline, datastores, VM inventory,
alarms) that stays explicitly "not assessed" in the Scope section,
since no support bundle exports that database.

Every `assess`/`report` run that generates `docx` or `html` also writes a
companion `findings-log.docx`/`findings-log.html` with the full
per-finding detail (evidence lines, remediation, limitations) -- the main
report stays a concise executive read, and nothing is lost.

Log-based findings (PDL/APD/dead-path/ALUA/VOB from `vmkwarning`/`vobd`,
and the IPMI SEL hardware-event-history findings) are scoped to a
configurable lookback window of the bundle's own capture date -- 1 to
26 weeks, default 13 (91 days, about a quarter) -- via `vhealth assess
--weeks N` or the `assessment.log_window_weeks` config key; older
matches are still counted (not discarded) but don't drive an active
finding. The chosen window is always stated in the report's own text
(Scope of Health Check, Executive Summary, and each affected finding's
own wording), so a reader never has to guess what period was covered.

## How it works

1. **Ingestion** — the archive is extracted under strict safety limits
   (zip-slip protection, size/entry/compression-ratio caps). See
   [`src/vhealth/security/extraction_guard.py`](src/vhealth/security/extraction_guard.py).
2. **Discovery** — individual ESXi `vm-support` host bundles are located
   inside the extracted tree (a vCenter bundle contains one per host),
   along with the vCenter Server appliance's own `vc-support` member,
   if present.
3. **Parsing** — a set of parsers read specific command-output files
   (`localcli ... --json`, `smartinfo.txt`, IPMI sensor dumps, rotated
   `vmkwarning`/`vobd` logs, ESXi's own `healthd` self-checks, and, for
   the vCenter appliance member, `service-control`/`df`/certificate
   data) into typed models. See [RULE_CATALOG.md](RULE_CATALOG.md) and
   [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md).
4. **Rules** — each rule inspects the parsed data for one host (or, for
   a few vCenter-appliance-level rules, the vCenter bundle itself) and
   emits zero or more findings with a severity, evidence, remediation
   and documented limitations.
5. **Reporting** — the findings and inventory are rendered into an HTML
   report (Jinja2) and a Word report (python-docx).

Every assessment also writes a versioned, machine-readable `assessment.json`
(see [`ARCHITECTURE.md`](ARCHITECTURE.md)) so two runs of the same bundle,
version and configuration can be diffed meaningfully.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a parser or a rule,
and [SECURITY.md](SECURITY.md) to report a vulnerability.

## License

[MIT](LICENSE)
