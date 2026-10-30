"""Parse ESXi's host-configuration database (ConfigStore) integrity check.

Source: ``commands/sqlite3_etcvmwareconfigstorecurrent-store-1-PRAGMAintegrity_check.txt``
-- the literal output of running SQLite's own ``PRAGMA integrity_check``
against ``/etc/vmware/configstore``, the SQLite-backed database ESXi
7.x/8.x uses to hold the host's own configuration (replacing the old
flat-file ``esx.conf``). A healthy database reports exactly ``ok``;
anything else is one or more lines describing the specific corruption
found. ConfigStore corruption/exhaustion is a documented real issue
(Broadcom KB 312114, KB 438104) that can affect host reconfiguration,
backup, and upgrade.
"""

from __future__ import annotations

from pathlib import Path

from vhealth.models.host import HostInfo

VERSION = "1.0.0"

_FILENAME = "sqlite3_etcvmwareconfigstorecurrent-store-1-PRAGMAintegrity_check.txt"


def parse(host_dir: Path, host: HostInfo) -> list[str]:
    path = host_dir / "commands" / _FILENAME
    if not path.is_file():
        return [f"{_FILENAME} not found; ConfigStore integrity state unavailable"]

    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return [f"{_FILENAME} was empty; ConfigStore integrity state unavailable"]

    host.configstore_data_available = True
    host.configstore_integrity_ok = text == "ok"
    return []
