# Stage 0 — Baseline Revalidation Audit

Date: 2026-10-30
Scope: inspection + running existing checks only. No source code was modified, no commits made, nothing pushed.

## 1. Repository state

- **HEAD SHA:** `ed5273d87d031e871625be80b14a4534f00414c1`
- **Branch:** `master`
- **Upstream comparison:** `git status` reports "Your branch is up to date with 'origin/master'." `git fetch origin` succeeded (network available) and `git rev-parse origin/master` returned the same SHA as HEAD (`ed5273d...`). Local HEAD matches origin/master exactly.
- **Working tree:** clean. `git status --porcelain=v2 -uall` and `git status -uno` both report nothing to commit, no untracked files (`git ls-files --others --exclude-standard` returned empty).
- **`.gitignore` contents of note:** excludes `.venv/`, build/cache dirs, `*.zip`/`*.tgz`/`*.tar.gz`/`*.support-bundle`, and explicitly `/output/` and `/samples/` with the comment "Never commit customer data or generated output" — consistent with CONTRIBUTING.md's no-customer-data policy.
- **Recent history (`git log --oneline -20`, 8 commits total so far):**
  ```
  ed5273d Rework report to match customer-facing convention exactly, split findings into a companion log, scope logs to the last quarter
  3fad8b3 Redesign report layout to a single combined executive-style report; add host/CPU inventory and fleet-wide CPU compatibility check
  03ec632 Add report cover-page authorship fields; fix a real coverage bug found in validation
  a84c269 Split install/uninstall scripts into scripts/windows and scripts/linux
  804e478 Record real Linux test results (WSL2 Kali Linux)
  57038ca Add uninstall scripts and document the uninstall procedure
  a4bfb4c Add beginner's guide and fix README clone URL
  20cd5a9 Initial vhealth implementation: offline VMware support-bundle health assessment
  ```
- **Tracked tree:** 68 tracked files (`git ls-files`), matches the expected layout: `src/vhealth/{parsers,models,rules,reporting,security,ingestion,discovery,correlation,utils,resources}`, `tests/{unit,integration,security,cross_platform,fixtures}`, `scripts/{windows,linux}`, `.github/workflows/ci.yml`, root docs, `pyproject.toml`, `uv.lock`.
- **`git diff`:** empty (no uncommitted changes to show).

## 2. Environment

- **Python:** 3.12.10 (`.venv/Scripts/python.exe --version`), matches CHANGELOG.md/SUPPORTED_FORMATS.md's claimed dev environment.
- **OS:** Windows 11 Pro, build 26300 (matches SUPPORTED_FORMATS.md's tested row).
- **uv:** 0.13.6 installed and on PATH.
- **`.venv`:** already present and populated; `uv sync --locked --group dev` ran clean (`Resolved 27 packages... Checked 20 packages`, exit 0) — the lockfile is in sync with `pyproject.toml`, nothing needed re-installing.
- **Key dependency versions actually installed** (`uv pip list`): click 8.5.0, pydantic 2.14.2, jinja2 3.1.6, python-docx 1.2.0, lxml 6.1.3, pytest 8.4.2, pytest-cov 5.0.0, ruff 0.17.3, coverage 7.17.0 — all within the ranges pinned in `pyproject.toml` (`click>=8.1,<9`, `pydantic>=2.6,<3`, `jinja2>=3.1,<4`, `python-docx>=1.1,<2`; dev group `pytest>=8.0,<9`, `ruff>=0.6,<1`).
- Plain `pip` is not installed inside `.venv` (expected — this is a `uv`-managed venv; `uv pip list` was used instead, per the brief's guidance to avoid relying on bare `python`/`pip`).
- `mypy`/`pyright` are **not configured anywhere** in this repo (no mention in `pyproject.toml`, `CONTRIBUTING.md`, or `.github/workflows/ci.yml`) — confirmed by grep, not assumed.

## 3. Baseline validation results

| # | Check | Command | Result | Note |
|---|---|---|---|---|
| 1 | Dependency/env validation | `uv sync --locked --group dev` | **PASS** | "Resolved 27 packages... Checked 20 packages", exit 0. `.venv` already matched the lockfile. |
| 2 | Full pytest suite | `./.venv/Scripts/python.exe -m pytest -q` | **PASS** | `68 passed in 1.63s`, exit 0. |
| 3a | Ruff lint | `./.venv/Scripts/python.exe -m ruff check .` | **PASS** | "All checks passed!", exit 0. |
| 3b | Ruff format check | `./.venv/Scripts/python.exe -m ruff format --check .` | **FAIL** | Exit 1 — 9 files would be reformatted (`cli.py`, `config.py`, `ingestion/extract.py`, `parsers/hardware_inventory.py`, `parsers/vmk_log.py`, `rules/log_rules.py`, `tests/unit/test_parsers.py`, `tests/unit/test_reporting_summary.py`, `tests/unit/test_rules.py`); 55 files already formatted. See §4 — this is not currently enforced anywhere (not in CI, not in CONTRIBUTING.md's required-checks list), so it is a drift/gap rather than a broken contractual check. |
| 3c | mypy / pyright | — | **NOT RUN** | Not configured as a project check (confirmed by grep across `pyproject.toml`/CI/CONTRIBUTING.md) — out of scope to introduce one during a read-only audit. |
| 4 | CLI `--version` / `--help` | `./.venv/Scripts/vhealth.exe --version` / `--help` | **PASS** | `vhealth, version 0.1.0`; `--help` lists `assess`, `inspect`, `report` as documented. |
| 5 | Import/install check | `./.venv/Scripts/python.exe -c "import vhealth; print(vhealth.__file__)"` | **PASS** | Resolved to `C:\ATS\vmware-health-assessment\src\vhealth\__init__.py`, `__version__` = `0.1.0`. |
| 6 | Synthetic-bundle `inspect`/`assess` | fixture `tests/fixtures/synthetic_bundle.py:build_tgz()` → `vhealth inspect`/`assess` against `C:\vhealth-audit-tmp\in\host.tgz`, output to `C:\vhealth-audit-tmp\out1` | **PASS** | `inspect`: "Files extracted: 12... ESXi host bundles found: 1". `assess`: wrote `assessment.json`, `report.html`, `findings-log.html`, `report.docx`, `findings-log.docx`; "Assessment complete: 1 host(s), 1 finding(s)." (the `smart_health="FAILED"` fixture param). Short path used per the brief, to dodge MAX_PATH. |
| 7 | JSON-schema validation of `assessment.json` | — | **BLOCKED** | `src/vhealth/resources/schemas/assessment_schema_v1.json` exists (a Pydantic-exported JSON Schema for `Assessment`), but `jsonschema` is **not** an installed/declared dependency (`import jsonschema` → `ModuleNotFoundError`) and no test under `tests/` actually validates `assessment.json` against this schema file (`grep -rn "jsonschema\|assessment_schema" tests/` returned nothing). The schema file is present but currently unused by any automated check — not run, not fabricated as passing. |
| 8 | HTML + DOCX report generation | (same `assess` run as #6; default `--format` is `docx,html`) | **PASS** | All four report files (`report.{html,docx}`, `findings-log.{html,docx}`) were written in the same run; `report.docx` 39,146 bytes, `report.html` 10,493 bytes, confirming both renderers ran. |
| 9 | Report re-render from saved `assessment.json` | `vhealth report --assessment out1\assessment.json --format docx,html --output out3 --no-prompt` | **PASS (with caveat)** | First attempt *without* `--no-prompt` printed "Engineer name (for the report cover page, press Enter to skip): Aborted!" and exited 1 — see §4, this environment's `sys.stdin.isatty()` returns `True` even though no interactive operator is present, so the CLI's auto-detect-non-interactive fallback did not trigger. Re-run with `--no-prompt` passed cleanly and wrote all 4 files. |
| 10 | Determinism check | ran `assess` twice (`out1`, `out2`) against the identical input bundle, diffed `assessment.json` field-by-field with a one-off Python script | **PASS** | Exactly one field differed between the two runs: `metadata.assessment_timestamp`. Every other field (hosts, findings, hashes, versions, `config_fingerprint`) was byte-identical — matches ARCHITECTURE.md's documented reproducibility guarantee exactly. |
| 11 | Archive-security tests | `./.venv/Scripts/python.exe -m pytest tests/security/ -v` (re-run in isolation to confirm, on top of already running inside the full suite in #2) | **PASS** | 5/5 passed: zip-slip, tar-slip, non-archive rejection, truncated-gzip graceful degradation, empty-zip rejection. Already included in the 68 passed in #2; this just confirms which subset they are. |
| 12 | Release-build smoke test (PyInstaller) | — | **NOT RUN** (by design) | Per the brief, a fresh PyInstaller build was not attempted (too slow/heavy for this audit). Per CHANGELOG.md, it was previously built and smoke-tested on Windows 11/Python 3.12 only (`vhealth-windows-amd64.exe`, ~18 MB, ran `--version` and a full `assess` outside the repo/venv); Linux build is explicitly "Not yet built or tested." This claim is internally consistent with SUPPORTED_FORMATS.md (PyInstaller row: Windows-only) and with what this audit independently observed (Windows-only `.venv/Scripts/*.exe` shims, no Linux artifacts in the tree). No contradiction found. |

Cleanup note for #6/#9/#10: per the brief, `C:\vhealth-audit-tmp\` (containing `in\host.tgz` and `out1`/`out2`/`out3`) was left in place rather than fought with — a sandbox safety check blocked `rm -rf /c/vhealth-audit-tmp` as a "dangerous removal of what looks like a top-level directory" and required a human to approve it, which is outside this audit's scope. No repository files were touched by this; it is entirely outside `C:\ATS\vmware-health-assessment`.

## 4. Existing known defects/limitations

From **CHANGELOG.md "Known limitations"** (as currently documented, not re-verified beyond what's above):
- Linux validation is WSL2 (Kali) only; bare-metal Ubuntu/Debian not tried.
- PyInstaller portable binary built/tested on Windows only.
- Only `vmkwarning`-derived signals are scanned; binary VLF `vmkernel.log` format is not decoded.
- Offline-install procedure validated on Windows only; a local Windows Application Control policy blocked the `vhealth.exe` shim directly on the dev machine (`python -m vhealth.cli` worked around it) — see `docs/OFFLINE_INSTALL.md`.
- Rule catalogue covers storage/RAID/hardware-sensor health only; no networking, compute, or vSAN rules yet.

**Newly observed in this audit (not previously documented):**

1. **`ruff format --check .` currently fails on 9 files** (listed in §3, check 3b). This is not a regression against any documented claim — CONTRIBUTING.md's "must pass" list is `pytest`, `pytest --cov`, and `ruff check .` only, and does not mention `ruff format --check`. But the brief for this audit explicitly asked to run it (since it's "already configured... check pyproject.toml for the exact configured commands"), and `[tool.ruff]` in `pyproject.toml` does configure line-length/target-version/lint rules that imply formatting is a first-class concern. Net: not a broken promise, but a real, reproducible drift between the code and `ruff format`'s own opinion that nothing currently catches (CI only runs `ruff check .`, not `ruff format --check .`).

2. **CI workflow's `push` trigger targets `branches: [main]`, but the repository's actual (and only) branch is `master`.** `.github/workflows/ci.yml` line 5. This means a direct push to `master` would never trigger the `push`-triggered CI run on GitHub (the `pull_request` trigger has no branch filter, so PRs would still run CI regardless of base branch — but direct pushes to the real default branch would silently not). This is a real, observable discrepancy between the CI config and the repo's actual branch name, not something that shows up in a local audit like this one unless the workflow file is read carefully, which the brief's instructions did ask for.

3. **`vhealth report`/`assess` without `--engineer`/`--author`/`--verifier`/`--no-prompt` aborts instead of prompting, in this specific non-interactive shell environment.** The CLI's non-interactive detection is `no_prompt or not sys.stdin.isatty()` (`src/vhealth/cli.py`). In the Bash-tool shell used for this audit, `sys.stdin.isatty()` returns `True` even though no human is present to answer the prompt, so `click.prompt(...)` immediately hits EOF and aborts (exit 1) rather than silently skipping as README's "which also happens automatically in a non-interactive run (CI, a script)" implies. This is an environment-dependent gap in the isatty-based heuristic, not a bug that would necessarily show up in GitHub Actions (where stdin is typically not a tty) — but it is a real, reproducible failure mode for *some* non-interactive automation contexts (this one included) that `--no-prompt` works around. Worth flagging since the README states the auto-skip "just happens" without caveating this.

4. **README Windows path commands checked character-by-character:** `.\scripts\windows\install.ps1` / `.\scripts\windows\uninstall.ps1` (lines 38, 54 of README.md) — no stray double-spaces, no trailing whitespace, no smart-quote/en-dash corruption found via `cat -A`. These render and would execute correctly as written. No discrepancy found here, contrary to what the project owner suspected — this is worth noting as a negative result, not a gap.

No other contradictions were found between documented claims (README/CHANGELOG/ARCHITECTURE/RULE_CATALOG/SUPPORTED_FORMATS) and what was actually observed while running the checks above.

## 5. Proposed priorities for next stages

- **P0 (trust/safety):** Wire up real JSON-schema validation of `assessment.json` against `src/vhealth/resources/schemas/assessment_schema_v1.json` (add `jsonschema` as a dev dependency and a test) — right now the schema file exists but nothing in the test suite actually checks a real run's output against it (§3 check 7).
- **P0 (trust/safety):** `storage.apd_detected` is still explicitly marked "not yet confirmed against a real APD event" in RULE_CATALOG.md — validate against real/representative data before relying on it for a customer-facing finding.
- **P0 (CI correctness):** Fix the `.github/workflows/ci.yml` `push.branches: [main]` vs actual `master` branch mismatch (§4 item 2) — as written, CI's push trigger silently never fires on the real default branch.
- **P0 (trust/safety):** Decide whether `ruff format --check .` should be a required/CI-enforced gate; if yes, run `ruff format .` to clear the current 9-file drift and add it to CI and CONTRIBUTING.md's checklist (§3/§4 item 1).
- **P1 (quarterly comparison feature):** The reproducibility guarantees already validated here (byte-identical `assessment.json` apart from timestamp; `config_fingerprint` hashing) are exactly the foundation a quarter-over-quarter diff feature would build on — this stage's determinism check (§3 check 10) is a good regression baseline to keep re-running once that feature lands.
- **P1:** Decide the CLI's non-interactive-prompt fallback story (§4 item 3) before quarterly-comparison automation scripts start calling `assess`/`report` unattended — `--no-prompt` works today but the isatty-based auto-skip cannot be relied on in every automation context.
- **P2 (cross-platform CI):** CI matrix (`ubuntu-latest`/`windows-latest` × Python 3.11/3.12) exists and looks reasonable, but per SUPPORTED_FORMATS.md it has only actually been exercised as WSL2 Kali locally, not bare-metal Ubuntu/Debian or in a real GitHub Actions run against this exact repo state (confirm GitHub Actions is actually green on this SHA once `git fetch`/push access is used for that).
- **P2 (CPU/cluster rule refinement):** `fleet.cpu_model_mismatch` has no visibility into real vCenter cluster/EVC membership (documented limitation in RULE_CATALOG.md) — natural next refinement once/if vCenter-side data becomes available.
- **P3 (new rule categories):** RULE_CATALOG.md confirms coverage is storage/RAID/hardware-sensor only; networking, compute, and vSAN rule categories remain open per CHANGELOG.md's "Known limitations."
- **Housekeeping:** `C:\vhealth-audit-tmp\` was left on disk after this audit (sandbox blocked `rm -rf` on it) — a human should delete it manually; it contains only synthetic data, nothing from `C:\ATS\E&F\`.
