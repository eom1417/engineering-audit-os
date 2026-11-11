"""External analysis engines, behind one contract.

A missing engine reduces coverage; it never fails the run. Every engine's version is discovered by
running it, never assumed, and a version that does not match its pin is reported as such and still
recorded — so a reader can tell "we did not look" apart from "we looked and found nothing".
"""
from .run import ADAPTERS, ENGINE_MB, analyze, health, missing, not_applicable, observed, ordered  # noqa: F401
