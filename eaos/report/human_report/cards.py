"""REPORT.html's progress: the ledger's gap bars, the history chart, and every task card with its state."""
from ...core import plain
from ...analysis import model as M
from ...core.markup import both as T, esc
from ...analysis.model import gap_totals, ledger_of
from .html import lit, num, said, unavailable
from .words import MILESTONE, OUTCOME


# ---------------------------------------------------------------- progress: the ledger and every task card

CARD_STATE = {  # state: (Arabic, English, chip colour); 'on_branch' is delivered, not merged, so it is not closed
    'done': ('أُصلحت ودُمجت ✓', 'Done ✓ merged', 'good'),
    'on_branch': ('على فرع ينتظر قرارك', 'Waiting on a branch', 'warn'), 'in_batch': ('في الدفعة الحالية', 'In the current batch', 'accent'),
    'open': ('مفتوحة', 'Open', 'plain'), 'skipped': ('تحتاج قرارًا', 'Needs a decision', 'bad')}
STATE_ORDER = ('open', 'in_batch', 'on_branch', 'skipped', 'done')
EVENT = {'baseline': ('الفحص الأول', 'first check'), 'merged': ('دُمجت دفعة', 'a batch merged'),
         'recheck': ('إعادة فحص', 'a recheck'), 'delivered': ('سُلّمت دفعة على فرع', 'a batch delivered on a branch')}


def pct(value):
    """A share in words a person reads: whole percents, one decimal under ten, and "<1%" rather than 0.4%."""
    value = float(value or 0)
    if value <= 0: return '0%'
    if value < 1: return '<1%'
    return f'{value:.1f}%'.replace('.0%', '%') if value < 10 else f'{round(value)}%'


def bar(share, cls=''):
    share = max(0, min(100, round(share or 0)))
    return (f'<div class="progress {cls}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{share}">'
            f'<span style="width:{share}%"></span></div>')


def state_chip(state, words=CARD_STATE):
    ar, en, tone = words.get(state) or (state, state, 'plain')
    return f'<span class="chip st st-{tone}" data-state="{state}">{T(esc(ar), esc(en))}</span>'


def gap_block(m, cards, chart=True):
    """How much of the gap is closed: only what is merged into the person's branch counts."""
    t, ledger = gap_totals(m, cards), ledger_of(m)
    head = f'<h3 id="gap-closed">{T("كم أُغلق من الفجوة", "How much of the gap is closed")}</h3>'
    if not t['total']:
        return head + f'<div class="card">{T("لا مشاكل مفتوحة في الخطة: لا فجوة لإغلاقها.", "The plan has no problem to close: there is no gap.", "p")}</div>'
    share = num(pct(t['percent']), 'share of the problems found that are closed: fixed and merged')
    closed, total = num(t['closed'], 'problems closed'), num(t['total'], 'problems in the plan, fixed ones included')
    tally = _gap_tally(t)
    branch = num(t['on_branch'], GAP_MEANING['on_branch'])
    waiting = (f'<p class="small">{T(f"على فرع ينتظر قرارك: {branch}. لا تُحسب مغلقة حتى تدمجها.", f"Waiting on a branch for your decision: {branch}. They count as closed only once you merge them.")}</p>'
               if t['on_branch'] else '')
    when = _last_updated(ledger)
    marker = ' data-part="progress-history"' if chart else ''
    body = (f'<div class="card gap-card"{marker}><div class="gap-head"><div class="gap-n">{share}</div><div>'
            f'<p class="lead">{T(f"من الفجوة أُغلق: {closed} من {total} مشكلة أُصلحت ودُمجت في فرعك الرئيسي.", f"of the gap is closed: {closed} of {total} problems are fixed and merged into your main branch.")}</p>'
            f'{bar(t["percent"], "big")}</div></div><ul class="tally">{tally}</ul>{waiting}{when}')
    if chart:
        body += history_block((ledger or {}).get('history') or [])
    return head + body + '</div>'


GAP_MEANING = {'done': 'problems fixed by EAOS and merged into your main branch',
               'on_branch': 'problems fixed on a branch that waits for your decision; not counted until merged',
               'in_batch': 'problems in the batch being fixed now', 'skipped': 'problems set aside that need your decision',
               'open': 'problems not started yet'}


def _gap_tally(t):
    """The plan's problems counted by state (the states with none left out), and the new ones a later check found."""
    parts = [(k, v) for k, v in (('done', t['done']), ('on_branch', t['on_branch']),
                                 ('in_batch', t['in_batch']), ('skipped', t['skipped']), ('open', t['open'])) if v]
    tally = ''.join(f'<li>{state_chip(k)} {num(v, GAP_MEANING[k])}</li>' for k, v in parts)
    if t.get('new'):
        tally += f'<li><span class="chip st st-accent">{T("جديدة", "New")}</span> {num(t["new"], "problems a later check found for the first time")}</li>'
    return tally


def _last_updated(ledger):
    """When the progress was last updated, from the ledger; '' without a date."""
    updated = str((ledger or {}).get('updated') or '')[:10]
    return (f'<p class="muted small">{T("آخر تحديث:", "Last updated:")} {num(updated, "the date the progress was last updated")}</p>' if updated else '')


def history_block(history):
    points = [h for h in history if isinstance(h, dict) and h.get('at') and isinstance(h.get('percent'), (int, float))]
    title = f'<h4>{T("التقدم عبر الوقت", "Progress over time")}</h4>'
    if not points:
        return title + T('يظهر الخط هنا بعد أول دفعة تُدمج أو أول إعادة فحص.', 'The line shows here after the first merged batch or the first recheck.', 'p', 'muted small')
    rows = ''.join(f'<tr><td>{num(str(h["at"])[:10], "date of this event")}</td><td>{T(*map(esc, EVENT.get(h.get("event"), (h.get("event") or "", h.get("event") or ""))))}</td>'
                   f'<td>{num(h.get("closed", 0), "problems closed by then")}</td><td>{num(h.get("total", 0), "problems in the plan then")}</td>'
                   f'<td>{num(pct(h["percent"]), "share of the gap closed by then")}</td></tr>' for h in points)
    table = (f'<details><summary>{T("عرض كجدول", "Show as a table")}</summary><table class="tbl"><thead><tr><th>{T("التاريخ", "Date")}</th>'
             f'<th>{T("ما حدث", "What happened")}</th><th>{T("المغلق", "Closed")}</th><th>{T("المجموع", "Total")}</th><th>{T("النسبة", "Share")}</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></details>')
    return title + history_chart(points) + table


def _decision_options(group):
    """The suggested options of the first card of a group that has some; '' when none has."""
    sample = next((r for r in group if r['options']), None)
    if not sample: return ''
    return (f'<details><summary>{T("الخيارات المقترحة لمثال منها", "The suggested options, for one example")} {lit(sample["id"])}</summary><ul class="options">'
            + ''.join(f'<li><b>{esc(o.get("option", ""))}</b> <span class="muted">{esc(o.get("verdict", ""))}</span></li>'
                      for o in sample['options'] if isinstance(o, dict)) + '</ul></details>')


def _decision_card(pattern, group):
    """One kind of problem waiting for a decision: what it is, what the person chooses, and its cards."""
    (tar, why_ar), (ten, why_en) = plain.problem(pattern, 'ar'), plain.problem(pattern, 'en')
    found = {o for r in group for o in r['outcomes']}
    outcomes = [o for o in OUTCOME if o in found] + sorted(found - set(OUTCOME))
    answers = ''.join(f'<li>{T(*map(esc, OUTCOME.get(o, (o, o))))}</li>' for o in outcomes)
    ids = ' '.join(lit(r['id']) for r in group[:40]) + (T(f' و{num(M.remaining(group, 40), "more cards")} غيرها', f' and {num(M.remaining(group, 40), "more cards")} more') if len(group) > 40 else '')
    count = num(M.collection_count(group), 'cards waiting for a decision')
    return (f'<div class="card decision"><h4>{T(esc(tar), esc(ten))} <span class="count">{T(f"البطاقات: {count}", f"cards: {count}")}</span></h4>'
            f'<p>{T(esc(why_ar), esc(why_en))}</p>'
            + (f'<p class="small">{T("المطلوب منك أن تختار لكل حالة:", "For each case you choose:")}</p><ul class="answers">{answers}</ul>' if answers else '')
            + _decision_options(group) + f'<details><summary>{T("البطاقات", "The cards")}</summary><p class="ids">{ids}</p></details></div>')


def _history_times(points):
    """Each event's time as a number; their order instead when one has no time or all share one."""
    from datetime import datetime
    def when(h):
        try: return datetime.fromisoformat(str(h['at']).replace('Z', '+00:00')).timestamp()
        except ValueError: return None
    times = [when(h) for h in points]
    return list(range(len(points))) if None in times or max(times) == min(times) else times


def _history_axes(points, times, X, Y, box):
    """The share's grid lines and the first, middle and last dates; `box`: (width, height, left, right)."""
    width, height, left, right = box
    out = [f'<line x1="{left}" x2="{width - right}" y1="{Y(tick):.1f}" y2="{Y(tick):.1f}" class="grid"/>'
           f'<text x="{left - 8}" y="{Y(tick) + 4:.1f}" text-anchor="end" class="tick" data-meaning="share of the gap closed">{tick:g}%</text>'
           for tick in M.history_ticks(points)]
    out += [f'<text x="{X(times[i]):.1f}" y="{height - 10}" text-anchor="middle" class="tick" data-meaning="date of this event">{esc(str(points[i]["at"])[:10])}</text>'
            for i in sorted({0, len(points) - 1, (len(points) - 1) // 2})]
    return out


def _history_line(points, times, X, Y):
    path = f'M{X(times[0]):.1f},{Y(points[0]["percent"]):.1f}'
    for t, h in zip(times[1:], points[1:]):
        path += f' H{X(t):.1f} V{Y(h["percent"]):.1f}'
    area = path + f' V{Y(0):.1f} H{X(times[0]):.1f} Z'
    return f'<path d="{area}" class="area"/><path d="{path}" class="line"/>'


def _history_dot(t, h, X, Y):
    words = f'{str(h["at"])[:10]}: {pct(h["percent"])} ({EVENT.get(h.get("event"), ("", h.get("event") or ""))[1]})'
    return (f'<circle cx="{X(t):.1f}" cy="{Y(h["percent"]):.1f}" r="4.5" class="dot-pt" data-meaning="share of the gap closed on this date">'
            f'<title>{esc(words)}</title></circle>')


def history_chart(points):
    """A step line of the share closed over time: it holds its value until the next event. One colour, labelled axes."""
    width, height, left, right, top, bottom = 760, 230, 52, 70, 16, 34
    times = _history_times(points)
    scale = M.history_scale(points)
    span = (max(times) - min(times)) or 1
    X = lambda t: left + (width - left - right) * ((t - min(times)) / span if len(points) > 1 else 0.5)
    Y = lambda v: top + (height - top - bottom) * (1 - min(v, scale) / scale)
    out = [f'<svg viewBox="0 0 {width} {height}" direction="ltr" role="img" class="chart history" '
           f'aria-label="{esc("share of the gap closed over time")}">']
    out += _history_axes(points, times, X, Y, (width, height, left, right))
    out.append(_history_line(points, times, X, Y))
    out += [_history_dot(t, h, X, Y) for t, h in zip(times, points)]
    last = points[-1]
    out.append(f'<text x="{X(times[-1]) + 10:.1f}" y="{Y(last["percent"]) + 4:.1f}" class="end-label" data-meaning="share of the gap closed now">{esc(pct(last["percent"]))}</text>')
    return ''.join(out) + '</svg>'


def card_item(c, words=CARD_STATE, extra=''):
    """One task card, collapsed: its state and title; open, what it is, where, now and should-be, and when."""
    new = f' <span class="chip st st-accent">{T("جديدة", "New")}</span>' if c.get('new') else ''
    search = ' '.join([c.get('id') or '', c.get('title') or '', c.get('pattern') or '', *c['paths']]).lower()
    return (f'<details class="tcard" data-state="{c["state"]}" data-new="{int(bool(c.get("new")))}" data-search="{esc(search)}">'
            f'<summary>{state_chip(c["state"], words)}{new} {said(c["title"]) or lit(c.get("id") or c.get("key") or "")}'
            f'{(" " + lit(c["id"])) if c.get("id") else ""}</summary><div class="tbody">{_card_body(c, extra)}</div></details>')


def _card_body(c, extra):
    """An open card: what the problem is, where, now and should-be, `extra`, when its state changed, and why."""
    lines = []
    if c.get('pattern') in plain.ORDER:
        (tar, why_ar), (ten, why_en) = plain.problem(c['pattern'], 'ar'), plain.problem(c['pattern'], 'en')
        lines.append(f'<p><b>{T(esc(tar), esc(ten))}</b>: {T(esc(why_ar), esc(why_en))}</p>')
    if where := _card_where(c['paths']): lines.append(f'<div class="where">{T("أين:", "Where:", cls="lbl")} {where}</div>')
    if c.get('before') or c.get('after'):
        lines.append(f'<div class="nowto"><div><b>{T("الآن", "Now")}</b> {said(c["before"] or c["title"])}</div>'
                     f'<div><b>{T("المطلوب", "Should be")}</b> {said(c["after"]) or T("لم يُحدَّد بعد؛ يقرره شخص.", "Not stated yet; a person decides.")}</div></div>')
    lines.append(extra + (c.get('extra') or ''))
    lines.append(_card_when(c))
    if c.get('why'): lines.append(f'<p class="small">{T("السبب:", "Why:", cls="lbl")} {said(c["why"])}</p>')
    return ''.join(lines)


def _card_where(paths):
    """A card's first six files, and how many more."""
    where = ' '.join(lit(p) for p in paths[:6])
    if len(paths) > 6: where += ' ' + T(f'و{num(M.remaining(paths, 6), "more files")} ملفات أخرى', f'and {num(M.remaining(paths, 6), "more files")} more files')
    return where


def _card_when(c):
    """When a card's state changed: its batch, its date and its commit; '' when none is known."""
    when = []
    if c.get('batch') is not None: when.append(T(f'الدفعة {num(c["batch"], "batch number")}', f'batch {num(c["batch"], "batch number")}'))
    if c.get('at'): when.append(T(f'بتاريخ {num(str(c["at"])[:10], "the date its state last changed")}', f'on {num(str(c["at"])[:10], "the date its state last changed")}'))
    if c.get('commit'): when.append(T('في الإيداع', 'in commit') + ' ' + lit(str(c['commit'])[:12]))
    return f'<p class="muted small">{" · ".join(when)}</p>' if when else ''


def cards_block(groups, words=CARD_STATE, total=None):
    """"All task cards": collapsed; inside, a status filter, a search, and one collapsed group per milestone."""
    count = num(total if total is not None else M.all_card_count(groups), 'all task cards')
    options = ''.join(f'<option value="{s}" data-ar="{esc(words[s][0])}" data-en="{esc(words[s][1])}">{esc(words[s][0])}</option>'
                      for s in STATE_ORDER if s in words)
    if words is CARD_STATE: options += '<option value="new" data-ar="جديدة" data-en="New">جديدة</option>'
    blocks = [_milestone_group(label, stone, cards, words) for label, stone, cards in groups if cards]
    return (f'<details class="card allcards" id="allcards" data-part="cards"><summary>{T("كل بطاقات المهام", "All task cards")} '
            f'<span class="g-meta">{T(f"البطاقات: {count}", f"{count} cards")}</span></summary>'
            f'<p class="muted small">{T("كل بطاقة مشكلة واحدة وحالتها. افتح المرحلة ثم البطاقة لترى التفاصيل.", "Each card is one problem and its state. Open a milestone, then a card, to see the details.")}</p>'
            f'<div class="filters cfilters" role="search"><select id="cstate"><option value="" data-ar="كل الحالات" data-en="All states">كل الحالات</option>{options}</select>'
            f'<input type="search" id="cq" data-ph-ar="ابحث بعنوان أو ملف أو رقم بطاقة…" data-ph-en="Search a title, a file or a card id…" placeholder="ابحث بعنوان أو ملف أو رقم بطاقة…">'
            f'<span class="muted" id="cshown" aria-live="polite"></span></div>{"".join(blocks) or unavailable("cards")}</details>')


def _milestone_group(label, stone, cards, words):
    """One milestone's cards, collapsed under its name, how many are closed and a bar."""
    counts = M.card_counts(cards)
    closed = counts['closed']
    tally = T(f'المغلق: {num(closed, "cards closed in this milestone")} من {num(M.collection_count(cards), "cards in this milestone")}',
              f'{num(closed, "cards closed in this milestone")} of {num(M.collection_count(cards), "cards in this milestone")} closed')
    return (f'<details class="mgroup"><summary><span>{T(esc(label[0]), esc(label[1]))} {lit(stone) if stone else ""}</span>'
            f'<span class="g-meta">{tally}</span></summary>{bar(counts["percent"], "thin")}'
            f'<div class="tcards">{"".join(card_item(c, words) for c in cards)}</div></details>')


def milestone_label(stone):
    name = stone.get('name') or ''
    label = MILESTONE.get(name)
    if not label and name.startswith('build:'): label = (f'بناء {name[6:]}', f'Build {name[6:]}')
    if not label and stone.get('name_ar'): label = (stone['name_ar'], name)
    return label or (name, name)


def card_groups(m, cards):
    stones = [s for s in m['plan'].get('milestones') or [] if isinstance(s, dict)]
    groups = [(milestone_label(s), s.get('id') or '', [c for c in cards if c['milestone'] == s.get('id')]) for s in stones]
    return groups + _no_milestone(stones, cards)


def _no_milestone(stones, cards):
    """The cards of no known milestone as one more group; none when every card has one."""
    known = {s.get('id') for s in stones}
    rest = [c for c in cards if c['milestone'] not in known]
    return [(('بلا مرحلة', 'No milestone'), '', rest)] if rest else []
