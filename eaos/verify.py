"""An isolated copy of the target: the folder a codemod's dry run changes, never the project itself."""
import os
import shutil
from pathlib import Path

from .workspace import SKIP_DIRS


def isolated_copy(target, destination):
    destination.mkdir(parents=True)
    for base, directories, names in os.walk(target):
        directories[:] = sorted(d for d in directories if d not in SKIP_DIRS and not (Path(base) / d).is_symlink())
        for name in sorted(names):
            source_path = Path(base) / name
            if source_path.is_symlink() or not source_path.is_file(): continue
            relative = source_path.relative_to(target)
            (destination / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination / relative)
    return destination
