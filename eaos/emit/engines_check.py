"""Whether validators are installed, for callers that must say so rather than count a missing tool as a pass."""
from ..engines.process import which


def installed(*binaries):
    return all(which(binary) for binary in binaries)
