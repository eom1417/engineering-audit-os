"""Compatibility entry point over the single declared pipeline."""
from pathlib import Path


def run(target, out, max_files=100000, max_bytes=2_000_000, exclude=None, language='ar',
        policy_path=None, engines=None):
    from .pipeline import execute
    manifest = execute(target, out, language=language, exclude=exclude or (), engines=engines,
                       max_files=max_files, max_bytes=max_bytes, policy_path=policy_path)
    out = Path(out).resolve()
    return {'target': str(Path(target).resolve()), 'out': str(out), 'status': manifest['status'],
            'manifest': str(out / 'run-manifest.json'),
            'sustainability': str(out / 'SUSTAINABILITY.md'),
            'transform_plan': str(out / 'transform-plan.md'),
            'transform_plan_json': str(out / 'transform-plan.json'),
            'target_architecture': str(out / 'TARGET-ARCHITECTURE.md'),
            'executive': str(out / 'EXECUTIVE.md'), 'bundles_dir': str(out / 'bundles'),
            'limits': manifest['limits']}
