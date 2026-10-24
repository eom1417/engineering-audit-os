"""What every part of the synthetic Studio folder shares (tools/studio_synthetic.py): EAOS on the path, the made-up
project's domains and layers, the sections' head, and a measure with its source."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from eaos.report.studio import export  # noqa: E402

DOMAINS = ('work-orders', 'assets', 'vehicles', 'drivers', 'invoices', 'payments', 'inventory', 'reports', 'auth', 'users',
           'billing', 'routes', 'maintenance', 'fuel', 'alerts', 'audit', 'settings', 'notifications', 'contracts', 'suppliers')
LAYERS = ('pages', 'features', 'shared', 'data-access', 'config')
HEAD = {'schema_version': 1, 'contract': export.CONTRACT}
V2 = {**HEAD, 'revision': export.REVISION}
WHEN = '2026-10-08T09:00:00+00:00'


def measure(value, src, unit='count'):
    return {'value': value, 'src': src, 'unit': unit}


def ratio(value, src):
    return {'value': value, 'src': src}
