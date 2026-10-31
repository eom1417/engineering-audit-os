"""The look, as written and as seen (M15.4): the values written outside the tokens file (eaos/facts/duplication/look.py)
and the style census of the pictured pages (eaos/templates/screens/audit.mjs `stylesOf`, in live/screens.json), read
into one finding with the tokens file it calls for.

Near colours are one colour when CIEDE2000 puts them under NEAR_COLOUR apart (the formula of Sharma, Wu and Dalal
2005, written here and tested against its published pairs); a size is on the scale when it is one of the steps that
carry most of its uses, else off it. The tokens it proposes are in the W3C Design Tokens format (2025.10).
"""
import math
import re
from collections import Counter
from pathlib import Path

from ...core.contracts.code_laws import LOOK, PATTERN_REPEATS
from ...core.system.files import read_json

NEAR_COLOUR = 3.0
SCALE_SHARE = 0.85              # the steps most used, together carrying this share of the uses, are the scale
SCALE_MAX = {'font_size': 8, 'spacing': 10, 'radius': 5, 'shadow': 4, 'z_index': 8}
REPEATED_VALUES = 3             # values each written PATTERN_REPEATS times or more: a look that asks for its tokens
DRIFT_SHARE = 0.05              # off the scale or a near copy of another colour, in this share of the uses, is drift
HEX = re.compile(r'^#([0-9a-f]{3,8})$')
FUNC = re.compile(r'^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$')
PX = re.compile(r'^(-?[\d.]+)(px|rem|em|pt)$')


def _hex(digits):
    if len(digits) in (3, 4): digits = ''.join(c * 2 for c in digits)
    if len(digits) not in (6, 8) or digits[6:] == '00': return None       # a transparent one is no colour
    return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))


def rgb(value):
    """(r, g, b) in 0..255 of a hex or rgb() colour, None for a transparent one or one this does not read."""
    value = value.strip().lower()
    if (found := HEX.match(value)): return _hex(found.group(1))
    found = FUNC.match(value)
    if not found or (found.group(4) and float(found.group(4).rstrip('%')) == 0): return None
    return tuple(round(float(found.group(i))) for i in (1, 2, 3))


def lab(colour):
    """CIE L*a*b* (D65) of an sRGB colour."""
    def linear(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in colour)
    xyz = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, 0.2126 * r + 0.7152 * g + 0.0722 * b, (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = [t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116 for t in xyz]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def _hue(b, a):
    return 0.0 if a == 0 and b == 0 else math.degrees(math.atan2(b, a)) % 360


def ciede2000(one, other):
    """CIEDE2000 colour difference of two L*a*b* colours (kL = kC = kH = 1)."""
    (l1, a1, b1), (l2, a2, b2) = one, other
    c_mean = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_mean ** 7 / (c_mean ** 7 + 25 ** 7)))
    a1, a2 = a1 * (1 + g), a2 * (1 + g)
    c1, c2, h1, h2 = math.hypot(a1, b1), math.hypot(a2, b2), _hue(b1, a1), _hue(b2, a2)
    dh = 0 if c1 * c2 == 0 else (h2 - h1 if abs(h2 - h1) <= 180 else h2 - h1 - 360 if h2 > h1 else h2 - h1 + 360)
    dl, dc, dhh = l2 - l1, c2 - c1, 2 * math.sqrt(c1 * c2) * math.sin(math.radians(dh / 2))
    l_mean, c_mean = (l1 + l2) / 2, (c1 + c2) / 2
    h_mean = h1 + h2 if c1 * c2 == 0 else (h1 + h2) / 2 if abs(h1 - h2) <= 180 else (h1 + h2 + 360) / 2 if h1 + h2 < 360 else (h1 + h2 - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(h_mean - 30)) + 0.24 * math.cos(math.radians(2 * h_mean))
         + 0.32 * math.cos(math.radians(3 * h_mean + 6)) - 0.20 * math.cos(math.radians(4 * h_mean - 63)))
    sl = 1 + 0.015 * (l_mean - 50) ** 2 / math.sqrt(20 + (l_mean - 50) ** 2)
    sc, sh = 1 + 0.045 * c_mean, 1 + 0.015 * c_mean * t
    rt = -2 * math.sqrt(c_mean ** 7 / (c_mean ** 7 + 25 ** 7)) * math.sin(math.radians(60 * math.exp(-((h_mean - 275) / 25) ** 2)))
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dhh / sh) ** 2 + rt * (dc / sc) * (dhh / sh))


def colour_groups(counts):
    """[(head, [values], uses)]: each colour joined to the most used one under NEAR_COLOUR from it."""
    groups = []
    for value, uses in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        colour = rgb(value)
        if colour is None: continue
        point = lab(colour)
        group = next((g for g in groups if ciede2000(g['lab'], point) < NEAR_COLOUR), None)
        if group: group['values'].append(value); group['uses'] += uses
        else: groups.append({'head': value, 'lab': point, 'values': [value], 'uses': uses})
    return [(g['head'], g['values'], g['uses']) for g in groups]


def scale(counts, kind):
    """(the steps of the scale, the values off it): the most used values carrying SCALE_SHARE of the uses."""
    total, steps, carried = sum(counts.values()), [], 0
    for value, uses in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if carried >= SCALE_SHARE * total or len(steps) >= SCALE_MAX.get(kind, 8): break
        steps.append(value); carried += uses
    return steps, [value for value in counts if value not in steps]


def census(out):
    """{kind: Counter(value: uses)} over the pictured pages, each page counted once (its first wide picture)."""
    seen, counts = set(), {kind: Counter() for kind in (*LOOK, 'font_family')}
    for row in (read_json(Path(out) / 'live/screens.json') or {}).get('rows') or []:
        styles, page = row.get('styles'), (row.get('url') or '').split('?')[0]
        if not styles or page in seen: continue
        seen.add(page)
        for kind, values in styles.items(): counts.setdefault(kind, Counter()).update(values)
    return counts if seen else None


def _px(value):
    found = PX.match(value.strip())
    if not found: return None
    number, unit = float(found.group(1)), found.group(2)
    return number * (16 if unit in ('rem', 'em') else 4 / 3 if unit == 'pt' else 1)


def _dtcg_value(kind, value):
    """(type, value) of one token in the W3C Design Tokens format (2025.10), None when it does not read."""
    if kind == 'color':
        colour = rgb(value)
        return colour and ('color', {'colorSpace': 'srgb', 'components': [round(c / 255, 4) for c in colour], 'hex': '#%02x%02x%02x' % colour})
    if kind in ('font_size', 'spacing', 'radius'):
        px = _px(value)
        return None if px is None else ('dimension', {'value': px, 'unit': 'px'})
    if kind == 'shadow': return 'shadow', _shadow(value)
    return 'number', value


SHADOW = re.compile(r'(?P<color>rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})|(?P<length>-?[\d.]+(?:px)?)|(?P<inset>inset)')


def _dtcg_dimension(text):
    return {'value': float(text.replace('px', '')), 'unit': 'px'}


def _one_shadow(text):
    """One shadow as the W3C composite, in whichever order the browser or the source wrote it."""
    found = list(SHADOW.finditer(text))
    lengths = [m['length'] for m in found if m['length']] + ['0', '0']
    colour = next((m['color'] for m in found if m['color']), None)
    return {'color': (_dtcg_value('color', colour) or (None, None))[1] if colour else None, 'offsetX': _dtcg_dimension(lengths[0]), 'offsetY': _dtcg_dimension(lengths[1]),
            'blur': _dtcg_dimension(lengths[2]), 'spread': _dtcg_dimension(lengths[3]), 'inset': any(m['inset'] for m in found)}


def _shadow(value):
    """The W3C composite of a CSS shadow, an array when it has several; commas inside a colour do not part them."""
    parts = [_one_shadow(part) for part in re.split(r',(?![^(]*\))', str(value))]
    return parts[0] if len(parts) == 1 else parts


def proposed(out):
    """The tokens the look calls for, by kind, or {}: what design/tokens.proposed.json holds."""
    from ...facts.store import facts
    found = finding(facts(out, 'look_value', 'look_home'), out)
    return found['evidence']['tokens'] if found else {}


def _dtcg(kind, values):
    """The proposed tokens of one kind, each value once, sizes in their order."""
    rows = [row for value in values if (row := _dtcg_value(kind, value))]
    if kind in ('font_size', 'spacing', 'radius'): rows = sorted({row[1]['value']: row for row in rows}.values(), key=lambda r: r[1]['value'])
    return {f"{kind.replace('_', '-')}-{i + 1}": {'$type': kind_of, '$value': value} for i, (kind_of, value) in enumerate(rows)}


def _colours(uses):
    groups = colour_groups(uses)
    near = [values for _, values, _ in groups if len(values) > 1]
    return {'would_do': len(groups), 'near': near[:10], 'steps': [head for head, _, _ in groups],
            'drift_uses': sum(uses[v] for values in near for v in values[1:])}


def _sizes(uses, kind):
    steps, off = scale(uses, kind)
    return {'would_do': len(steps), 'off_scale': sorted(off, key=lambda v: -uses[v])[:12], 'steps': steps,
            'drift_uses': sum(uses[v] for v in off)}


def _seen(counts):
    """{kind: what the pages show}: how many values, the groups or steps that would do, and the drift."""
    return {kind: {'values': len(uses), 'uses': sum(uses.values()), **(_colours(uses) if kind == 'color' else _sizes(uses, kind))}
            for kind in LOOK if (uses := counts.get(kind))}


def _drifts(seen):
    return {kind: row for kind, row in seen.items() if row['drift_uses'] >= DRIFT_SHARE * row['uses'] and row['values'] > row['would_do']}


def _written(facts):
    """(the look's values written outside the tokens file, {kind: places}, their places, the tokens files)."""
    written = [f['value'] for f in facts if f['kind'] == 'look_value']
    by_kind = Counter()
    for row in written: by_kind[row['kind']] += row['count']
    places = sorted((p for row in written for p in row['places']), key=lambda p: (p['path'], p['line']))
    return written, by_kind, places, next((f['value']['paths'] for f in facts if f['kind'] == 'look_home'), [])


def _tokens(seen, written, by_kind):
    """The tokens file it calls for: what the pages show on their scale, else what the code writes, in DTCG."""
    steps = {kind: row['steps'] for kind, row in seen.items()} if seen else \
        {kind: sorted({r['value'] for r in written if r['kind'] == kind}) for kind in by_kind}
    return {kind: _dtcg(kind, values) for kind, values in steps.items() if values}


def _place(homes, places):
    """Where the look's card is: its tokens file, else the first place a value is written."""
    return (homes or [p['path'] for p in places] or ['the pages'])[0]


def finding(facts, out):
    """The one finding of the look, or None: the values written outside the tokens file (from `facts`, the patterns
    set's look_value and look_home), and what the pages show (the census) where it drifts."""
    written, by_kind, places, homes = _written(facts)
    counts = census(out) if out else None
    seen = _seen(counts) if counts else {}
    drifts = _drifts(seen)
    repeated = [row for row in written if row['count'] >= PATTERN_REPEATS]
    # a card when the look truly repeats: values written again and again that a token would name, or drift on the pages
    if len(repeated) < REPEATED_VALUES and not drifts: return None
    total = sum(by_kind.values())
    return {'kind': 'look', 'place': _place(homes, places), 'line': None, 'severity': 'medium' if drifts or total >= 50 else 'low',
            'evidence': {'written': total, 'by_kind': dict(sorted(by_kind.items())), 'places': places[:30], 'home': homes,
                         'repeated': [f"{row['kind']} {row['value']} ×{row['count']}" for row in sorted(repeated, key=lambda r: -r['count'])][:12],
                         'seen': seen, 'drifts': sorted(drifts), 'tokens': _tokens(seen, written, by_kind)}}
