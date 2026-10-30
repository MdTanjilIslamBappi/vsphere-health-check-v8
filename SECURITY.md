# Security policy

## Reporting a vulnerability

Please open a private security advisory on GitHub
(`Security` tab -> `Report a vulnerability`) rather than a public issue.
If that is not available, open an issue asking for a private contact
channel without describing the vulnerability itself.

Include: the version/commit, the input (a synthetic reproduction, not a
real customer bundle -- see "Handling reports that include customer
data" below), and the observed vs expected behaviour.

## Threat model

`vhealth` is designed to run against **untrusted, customer-supplied
diagnostic archives** with no network access. The main attack surface is
therefore archive extraction, not network input. Specifically in scope:

* Path traversal / zip-slip during extraction (`src/vhealth/security/extraction_guard.py`).
* Decompression bombs (size and compression-ratio limits, same module).
* Malformed/truncated archives causing a crash instead of a clean error.
* Anything that would make `vhealth` write outside the directory the
  user asked it to write to, or read/execute anything outside the
  supplied bundle and the installed package's own resources.

Out of scope: the diagnostic bundle's own contents are not itself
trusted to be *accurate* (a compromised ESXi host could emit misleading
`localcli` output), but `vhealth` only ever reads and reports on that
content -- it never acts on it (no commands are ever executed against the
data in a bundle).

## Handling reports that include customer data

If you believe a vulnerability can only be demonstrated with a real
customer support bundle, do not attach it to a report. Describe the
archive structure/content that triggers the issue so a synthetic
reproduction can be built (see `tests/fixtures/synthetic_bundle.py`).

## Supported versions

Only the latest released version receives security fixes while this
project is pre-1.0.
