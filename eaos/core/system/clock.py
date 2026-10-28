"""The time now, written one way (M15.3): an ISO 8601 stamp in UTC for what EAOS records, and a stamp for a name."""
from datetime import datetime, timezone


def now(timespec='seconds'):
    """The time now in UTC, ISO 8601 to `timespec` ('seconds', 'milliseconds', or 'auto': microseconds)."""
    return datetime.now(timezone.utc).isoformat(timespec=timespec)


def stamp(pattern='%Y%m%d-%H%M%S', utc=False):
    """The time now for a name (a file, a branch, a folder), in this computer's time unless `utc`."""
    return (datetime.now(timezone.utc) if utc else datetime.now()).strftime(pattern)
