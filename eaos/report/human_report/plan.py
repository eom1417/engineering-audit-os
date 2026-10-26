"""REPORT.html's plan section: the milestones, the batches, the decisions waiting for the person."""
from ...analysis.presentation import model as M
from ...core.language.markup import both as T, esc
from ...analysis.presentation.model import gap_totals, waves_state
from .cards import _decision_card, card_groups, cards_block, milestone_label
from .html import lit, num, quoted, tech, unavailable
from .work_log import work_log


def section_plan(m):
    plan, rows, progress = m['plan'], m['rows'], m['progress'] or {}
    by_id = {r['id']: r for r in rows}
    _, failed = waves_state(progress)
    cards = m.get('cards') or []
    t = gap_totals(m, cards)
    out = [work_log(progress), f'<div class="grid three"><div class="card stat good-bg"><div class="stat-n">{num(t["closed"], "problems fixed and merged so far")}</div><p>{T("مشاكل أُغلقت حتى الآن: أُصلحت ودُمجت", "problems closed so far: fixed and merged")}</p></div>'
           f'<div class="card stat"><div class="stat-n">{num(M.problems_left(t), "problems left")}</div><p>{T("مشاكل باقية", "problems left")}</p></div>'
           f'<div class="card stat"><div class="stat-n">{num(t["on_branch"], "fixes on a branch waiting for your decision")}</div><p>{T("إصلاحات على فرع تنتظر قرارك، لا تُحسب حتى تُدمج", "fixes on a branch waiting for your decision; not counted until merged")}</p></div>'
           f'<div class="card stat warn-bg"><div class="stat-n">{num(M.collection_count(failed), "fixes that were tried and did not pass")}</div><p>{T("إصلاحات جُرّبت ولم تنجح", "fixes tried that did not pass")}</p></div></div>']
    milestones = plan.get('milestones') or []
    if not milestones:
        out.append(f'<h3>{T("المراحل", "Milestones")}</h3>{unavailable("milestones")}')
    else:
        steps = []
        for index, stone in enumerate(milestones, 1):
            counts = M.milestone_counts(stone, cards, by_id)
            finished, share, ready, state = (counts[key] for key in ('closed', 'percent', 'automatic', 'state'))
            label = milestone_label(stone)
            n_done, n_all = num(finished, 'cards finished in this milestone'), num(counts["total"], 'cards in this milestone')
            n_share, n_auto = num(f'{share}%', 'share finished'), num(ready, 'cards EAOS can fix automatically here')
            tally = T(f'المنجز: {n_done} من {n_all} ({n_share}) · يصلحها EAOS آليًا: {n_auto}',
                      f'{n_done} of {n_all} done ({n_share}) · {n_auto} automatic')
            steps.append(
                f'<li class="stone {state}"><span class="dot" data-meaning="milestone order">{index}</span><div class="card">'
                f'<h4>{T(esc(label[0]), esc(label[1]))} {lit(stone.get("id", ""))}</h4>'
                f'<p>{T(quoted(stone.get("goal_ar") or stone.get("goal")), quoted(stone.get("goal")))}</p>'
                f'<p class="muted small">{T("تُعتبر منجزة حين: " + quoted(stone.get("exit_ar") or stone.get("exit")), "Done when: " + quoted(stone.get("exit")))}</p>'
                f'<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{share}"><span style="width:{share}%"></span></div>'
                f'<p class="small">{tally}</p></div></li>')
        out.append(f'<h3>{T("المراحل بالترتيب", "Milestones in order")}</h3><ol class="roadmap">{"".join(steps)}</ol>')
    out.append(cards_block(card_groups(m, cards)))
    out.append(waves_block(progress, failed, by_id))
    out.append(decisions_block(rows))
    return ''.join(out)


def waves_block(progress, failed, by_id):
    waves = progress.get('waves') or []
    head = f'<h3>{T("دفعات الإصلاح", "Fix batches")}</h3>'
    if not waves:
        return head + f'<div class="card">{T("لم تبدأ أي دفعة إصلاح بعد. حين تبدأ، تُبنى هذه الصفحة من جديد وتظهر هنا.", "No fix batch has started yet. When one does, this page is rebuilt and it shows here.", "p")}</div>'
    status_words = {'done': ('انتهت', 'finished'), 'merged': ('دُمجت', 'merged'), 'running': ('تعمل الآن', 'running'),
                    'failed': ('فشلت', 'failed'), 'pending': ('تنتظر', 'waiting')}
    rows = ''.join(
        f'<tr><td>{num(wave.get("number", i), "batch number")}</td><td>{T(*map(esc, status_words.get(wave.get("status"), (wave.get("status") or "—",) * 2)))}</td>'
        f'<td>{num(M.collection_count(wave.get("kept") or []), "fixes kept in this batch")}</td><td>{num(M.collection_count(wave.get("failed") or {}), "fixes that did not pass in this batch")}</td>'
        f'<td>{lit(wave.get("branch") or "—")}</td></tr>' for i, wave in enumerate(waves, 1))
    fails = ''.join(f'<li>{lit(card)} {tech(reason)}</li>' for card, reason in sorted(failed.items()))
    return head + (f'<div class="card scroll"><table class="tbl"><thead><tr><th>{T("الدفعة", "Batch")}</th><th>{T("الحالة", "Status")}</th>'
                   f'<th>{T("أُصلح", "Fixed")}</th><th>{T("لم ينجح", "Did not pass")}</th><th>{T("الفرع", "Branch")}</th></tr></thead><tbody>{rows}</tbody></table>'
                   + (f'<h4>{T("ما لم ينجح ولماذا", "What did not pass, and why")}</h4><ul class="fails">{fails}</ul>' if fails else '') + '</div>')


def decisions_block(rows):
    waiting = [r for r in rows if not r['auto']]
    head = f'<h3>{T("قرارات تحتاجك", "Decisions that need you")}</h3>'
    if not waiting:
        return head + f'<div class="card">{T("لا توجد قرارات معلقة.", "No decision is waiting.", "p")}</div>'
    groups = {}
    for r in waiting: groups.setdefault(r['pattern'], []).append(r)
    cards = [_decision_card(pattern, groups[pattern]) for pattern in sorted(groups, key=lambda p: -len(groups[p]))]
    return head + (f'<p class="muted">{T("هذه المشاكل لا يغيّرها EAOS وحده: تحتاج أن يقرر شخص هل هي مطلوبة، وما الصحيح.", "EAOS does not change these alone: a person has to decide whether they are wanted, and what is right.")}</p>'
                   f'<div class="grid two">{"".join(cards)}</div>')
