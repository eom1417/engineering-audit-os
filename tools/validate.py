"""Validate the packaged data: every file eaos/data ships is expected, present, packaged and not a stale copy."""
from fnmatch import fnmatch
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]

# Files whose only home is the package itself: there is no canonical copy elsewhere to go stale against.
PACKAGED_OWN=['errors.json','intents.json','toolchain.json','stacks.json','product-standard.json','detector-verdicts.json','studio-actions.json','pipeline-rules.json','design.json','journeys.json','translation-memory.json']
PACKAGED_ROOTS=['schemas','schemas/artifacts']
# Packaged copies of files kept elsewhere in the repository: (packaged name, source).
PACKAGED_COPIES=[('toolchain.json','upstreams/toolchain.json'),('studio-actions.json','docs/studio-actions.json')]
# The built Studio (console/, npm run build): its SOURCE.json names every file it ships.
STUDIO_BUILT='studio/SOURCE.json'


def studio_files(data):
    try:return {'studio/'+name for name in json.loads((Path(data)/STUDIO_BUILT).read_text())['files']}|{STUDIO_BUILT}
    except (OSError,ValueError,KeyError):return set()


def expected_package_files(data):
    expected=set(PACKAGED_OWN)
    for folder in PACKAGED_ROOTS:
        for path in sorted((Path(data)/folder).iterdir()):
            if path.is_file():expected.add(folder+'/'+path.name)
    return expected


def package_data_patterns(root):
    try:import tomllib
    except ImportError:return None
    config=tomllib.loads((Path(root)/'pyproject.toml').read_text())
    return config.get('tool',{}).get('setuptools',{}).get('package-data',{}).get('eaos')


def packaged_errors(root,data=None):
    root=Path(root);data=Path(data) if data else root/'eaos/data'
    if not data.is_dir():return ['Packaged data directory is absent: '+str(data)]
    built=studio_files(data)
    expected=expected_package_files(data)|built
    present={path.relative_to(data).as_posix() for path in data.rglob('*') if path.is_file()}
    errors=['Missing packaged file '+rel for rel in sorted(expected-present)]
    errors+=['Unexpected packaged file '+rel for rel in sorted(present-expected)]
    errors+=['Stale packaged copy '+name+' of '+source for name,source in PACKAGED_COPIES
             if (root/source).is_file() and (data/name).is_file() and (root/source).read_bytes()!=(data/name).read_bytes()]
    patterns=package_data_patterns(root)
    if patterns is not None:
        for rel in sorted(expected):
            if not any(fnmatch(rel,pattern.split('data/',1)[-1] if pattern.startswith('data/') else pattern) for pattern in patterns):
                errors.append('Packaging pattern does not include '+rel)
    return errors


def main():
    errors=packaged_errors(R)
    print(json.dumps({'errors':errors},ensure_ascii=False,indent=2))
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
