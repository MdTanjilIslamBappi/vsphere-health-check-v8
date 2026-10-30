class VHealthError(Exception):
    """Base class for errors with an actionable, user-facing message."""


class UnsupportedBundleError(VHealthError):
    """The input file is not a ZIP or gzip-compressed tar archive."""


class BundleCorruptError(VHealthError):
    """The archive could not be fully read (truncated or corrupted)."""

    def __init__(self, message: str, members_recovered: int = 0):
        super().__init__(message)
        self.members_recovered = members_recovered
