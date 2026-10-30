# Beginner's Guide to vhealth

This guide assumes you have never used a terminal, never installed Python,
and have only vague familiarity with VMware. If you already know your way
around a command line, the [README](../README.md) is faster.

## 1. What this tool actually does

A VMware administrator (or you) can export a diagnostic snapshot from an
ESXi host or vCenter — a single `.tgz` or `.zip` file called a **support
bundle**. It contains logs, configuration dumps, and hardware status, but
no VM data and no credentials.

`vhealth` reads that file on your own computer and writes back a report
(a webpage and/or a Word document) pointing out things worth checking —
failing disks, flaky storage paths, hardware sensor alarms, etc.

Important things it does **not** do:

- It does **not** connect to vCenter or any ESXi host.
- It does **not** need a username, password, or API key.
- It does **not** send anything over the network. Everything happens on
  your machine, in a folder you choose.

So the only two inputs you need are: the support bundle file, and a
computer to run `vhealth` on (Windows or Linux).

## 2. Words you'll see in this guide

| Term | Plain-English meaning |
|---|---|
| **Terminal** / **shell** | A text window where you type commands instead of clicking. On Windows this is **PowerShell**; on Linux it's usually just called **Terminal**. |
| **Command line** | The command you type into the terminal and press Enter on. |
| **Repository ("repo")** | The folder of source code for vhealth, hosted on GitHub. |
| **Clone** | Download a copy of a repo onto your computer using `git`. |
| **Python** | The programming language vhealth is written in. You need it installed, but you won't write any Python yourself. |
| **`uv`** | A small tool that installs the exact right Python packages for vhealth automatically. You run it once; you don't need to understand it. |
| **Virtual environment (`.venv`)** | An isolated folder of Python packages just for this project, so it never touches anything else on your system. |
| **Support bundle** | The `.tgz` (Linux-style ESXi export) or `.zip` (vCenter export, can contain several hosts) diagnostic file you're analyzing. |

## 3. Get the code

You need `git` installed (Windows: `winget install --id Git.Git`, Linux:
usually already installed, or `sudo apt install git`).

Open a terminal (PowerShell on Windows, Terminal on Linux) and run:

```bash
git clone https://github.com/MdTanjilIslamBappi/vsphere-health-check-v8.git
cd vsphere-health-check-v8
```

If you don't want to use `git` at all, you can instead click the green
**Code** button on the
[GitHub repo page](https://github.com/MdTanjilIslamBappi/vsphere-health-check-v8)
→ **Download ZIP**, extract it, and open a terminal inside the extracted
folder.

## 4. Install the prerequisites (Python + uv)

You only need to do this once per computer.

**Windows (in PowerShell):**

```bash
winget install --id astral-sh.uv -e
```

**Linux (in a terminal):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

You do **not** need to separately install Python — `uv` will download a
matching version automatically in the next step if one isn't already on
your system. Nothing here needs administrator/root privileges, and
nothing is installed system-wide.

Close and reopen your terminal after this step, so it picks up the new
`uv` command.

## 5. Run the install script

The repo keeps a separate folder per operating system — `scripts/windows/`
and `scripts/linux/` — so you only ever need to look at the one for your
own OS. From inside the repo folder:

**Windows (PowerShell):**

```bash
.\scripts\windows\install.ps1
```

**Linux:**

```bash
chmod +x scripts/linux/install.sh   # only needed the first time
./scripts/linux/install.sh
```

This creates a `.venv` folder inside the repo, installs everything
vhealth needs into it, and prints a confirmation with the exact command
to run vhealth. It's safe to run again later — it reuses what's already
there instead of starting over.

If it prints `ERROR: uv was not found on PATH`, close and reopen your
terminal (step 4 needs a fresh terminal to take effect) and try again.

## 6. Get a support bundle to analyze

If you already have a `.tgz` or `.zip` support bundle from your VMware
team, skip to step 7.

If you need to generate one yourself and have access to vSphere:

- **From the vCenter web UI**: right-click a host (or the vCenter
  instance itself) → **Export System Logs...** → follow the wizard. This
  produces a `.zip`.
- **Directly on an ESXi host** (via SSH): run `vm-support` at the shell.
  This produces a `.tgz`.

Either way, copy the resulting file to the computer where you installed
vhealth. `vhealth` only ever reads this one local file — generating it is
the only step that touches real vSphere infrastructure, and vhealth has
no part in that step.

## 7. Run vhealth

All three commands below are run from inside the repo folder.

**Windows:** use `.\.venv\Scripts\vhealth.exe`
**Linux:** use `./.venv/bin/vhealth`

The examples below use `vhealth` for brevity — substitute the path for
your platform (or activate the virtual environment first, as the install
script's final message explains, so you can just type `vhealth`).

**Check the tool is working:**

```bash
vhealth --version
```

**Peek inside a bundle without doing a full analysis** (fast, good first
sanity check that the file isn't corrupt and vhealth can see your
host(s) inside it):

```bash
vhealth inspect --input path\to\your-bundle.zip
```

**Run the full assessment** — this is the main command:

```bash
vhealth assess --input path\to\your-bundle.zip --output .\out
```

This writes, into the `out` folder:

- `assessment.json` — the raw, versioned results (useful for automation
  or diffing two runs; you probably won't read this directly)
- `report.html` — open this in any web browser
- `report.docx` — open this in Word (or LibreOffice)

When it finishes it prints a one-line summary, e.g.:

```
Assessment complete: 2 host(s), 5 finding(s).
```

**Re-generate just the reports later** (e.g. you want a DOCX now and only
generated HTML before), without re-reading the bundle:

```bash
vhealth report --assessment .\out\assessment.json --format docx --output .\out
```

## 8. Reading the report

Open `report.html` (or `.docx`) and look for:

- **Severity**: `critical` and `high` findings deserve attention first;
  `info`/`low` are usually just things worth being aware of.
- **Evidence**: the exact log lines or data vhealth based the finding on
  — so you can verify it yourself rather than taking the tool's word for
  it.
- **Limitations**: some findings include a note about what the rule
  *can't* rule out (e.g. a count-based heuristic that doesn't know about
  scheduled maintenance). Read these before escalating a finding.

A few VMware terms you may see in findings:

| Term | Meaning |
|---|---|
| **PDL** (Permanent Device Loss) | The host decided a storage device is gone for good, not just temporarily unreachable. Usually serious. |
| **APD** (All Paths Down) | Every path to a storage device is currently down, but the host isn't (yet) sure it's permanent. |
| **ALUA** | A storage multipathing feature; repeated path-state-change warnings can indicate flaky connectivity rather than a one-off blip. |
| **SMART** | Self-reported disk health data. "Not OK" or reallocated-sector counts are early failure warnings. |
| **IPMI sensor** | A hardware health sensor built into the physical server (temperature, fan, power supply, etc.), independent of ESXi itself. |

## 9. If something goes wrong

| Symptom | Likely fix |
|---|---|
| `uv: command not found` / `'uv' is not recognized` | Close and reopen your terminal after installing uv (step 4), or re-run the install command from step 4. |
| PowerShell says running scripts is disabled | Run PowerShell as yourself (not admin) and try `powershell -ExecutionPolicy Bypass -File .\scripts\windows\install.ps1` instead of double-clicking the script. |
| `Permission denied` running `./scripts/linux/install.sh` | Run `chmod +x scripts/linux/install.sh` first. |
| `vhealth.exe` won't launch / silently does nothing on a corporate Windows machine | Some corporate "Application Control" policies block unsigned `.exe` shims. Use `.\.venv\Scripts\python.exe -m vhealth.cli` instead — same tool, same result, just invoked through Python directly. |
| `uv sync --locked` fails | The repo's lock file and dependency list disagree — this would indicate a packaging bug; please open an issue. |

## 10. Uninstalling when you're done

vhealth only ever installed things inside its own `.venv` folder inside
the repo — it never touched anything system-wide. To remove it:

**Windows (PowerShell):**

```bash
.\scripts\windows\uninstall.ps1
```

**Linux:**

```bash
./scripts/linux/uninstall.sh
```

This deletes `.venv` and any local test/build leftovers. It's safe to
run even if you already removed things by hand, or never finished
installing — it just reports there's nothing to do.

It will **not** delete:

- `uv` or Python themselves — they were installed separately (step 4),
  not by vhealth, and other projects on your machine might use them
- any report folder you gave to `vhealth assess --output ...` — those
  are your own files

If you want the whole thing gone, including the source code, delete the
entire folder you cloned in step 3 (e.g. `vsphere-health-check-v8`) after
running the uninstall script.

## 11. Where to go next

- [README.md](../README.md) — the quick-reference version of this guide
- [SUPPORTED_FORMATS.md](../SUPPORTED_FORMATS.md) — exactly which bundle
  types, ESXi versions, and operating systems have actually been tested
- [RULE_CATALOG.md](../RULE_CATALOG.md) — every check vhealth runs, and
  whether it's been validated against real-world data
- [CHANGELOG.md](../CHANGELOG.md) — current known limitations
- [CONTRIBUTING.md](../CONTRIBUTING.md) — if you'd like to add a parser
  or a rule
