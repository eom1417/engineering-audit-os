"""Audit trail."""
import os
from .pricing import base_total

AUDIT_SINK = os.environ.get('AUDIT_SINK', 'stdout')


def audit_log(action, subject):
    return {'action': action, 'subject': subject, 'sink': AUDIT_SINK}


def audit_totals(items):
    return audit_log('total', base_total(items))
