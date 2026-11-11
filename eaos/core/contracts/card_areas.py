"""The area and severity every report sorts a card by: each remediation pattern's (area, severity), and `classify`."""
from ..language.plain import kind as plain_kind

# The areas and severities every report sorts a card by, and each remediation pattern's (area, severity).
SEVERITIES = ('critical', 'high', 'medium', 'low')
AREAS = ('security', 'structure', 'quality', 'performance', 'ux', 'maintainability')
PATTERNS = {
    'upgrade_dependency': ('security', 'high'), 'security_weakness': ('security', 'high'),
    'broken_code': ('quality', 'high'), 'remove_dead': ('quality', 'low'), 'dead_code': ('quality', 'low'),
    'canonicalize': ('quality', 'low'), 'duplicated_rule': ('quality', 'medium'),
    'import_cycle': ('structure', 'medium'), 'mutable_state': ('structure', 'medium'),
    'mutable_state_private': ('structure', 'low'),
    'hidden_coupling': ('structure', 'low'), 'external_write': ('structure', 'medium'),
    'policy_violation': ('structure', 'medium'), 'layer_boundary': ('security', 'high'),
    'load_blocker': ('performance', 'medium'), 'redundant_work': ('performance', 'medium'),
    'hotspot': ('maintainability', 'medium'), 'split_module': ('structure', 'medium'),
    'trace_gap': ('maintainability', 'low'),
    'untested_path': ('maintainability', 'medium'), 'generic': ('maintainability', 'medium'),
    'design_review': ('ux', 'medium'), 'investigation': ('maintainability', 'low'),
    'repository_craft': ('maintainability', 'low'), 'real_data': ('security', 'high'),
    'old_engine': ('quality', 'medium'), 'data_keeping': ('performance', 'medium'),
    'person_rule': ('maintainability', 'high'), 'one_source': ('maintainability', 'medium'),
}
CATEGORY_AREA = {'security': 'security', 'supply_chain': 'security', 'architecture': 'structure', 'data': 'structure',
                 'dead_code': 'quality', 'reliability': 'maintainability', 'maintainability': 'maintainability'}


def classify(task, debt=None, category=None):
    """(area, severity) of one card: the PATTERNS table, with the debt register's severity when it has one."""
    pattern = plain_kind(task)
    area, severity = PATTERNS.get(pattern, PATTERNS['generic'])
    # An investigation (an unproven claim) stays in the area of what it is about.
    if pattern not in PATTERNS or pattern in ('generic', 'investigation', 'layer_boundary'):
        area = CATEGORY_AREA.get(category, area)
    debt = debt or (task.get('design') or {}).get('severity')
    if debt in SEVERITIES: severity = debt
    return area, severity
