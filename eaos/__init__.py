"""EAOS (Engineering Audit OS). HOME is the package's own folder: data/, rules/ and templates/ are read from it."""
from pathlib import Path

__version__ = "0.0.92"
HOME = Path(__file__).resolve().parent
