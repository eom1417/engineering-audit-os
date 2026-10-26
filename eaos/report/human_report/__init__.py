"""human/index.html: the report for a person, in one self-contained page, Arabic and English.

The report's other files are written for AI agents and stay exactly as they are. This page reads the same
records (plan.json, dossier.json, debt-register.json, target-architecture.json, gap-matrix.json,
run-manifest.json, and the graph, flow and structure facts) and shows six reports on one page: the project
summary, the gaps and risks, the structure map (today's parts, their imports, files, functions and pages;
eaos/analysis/maps/architecture.py), the system map (every page, API, server handler, part and table; eaos/analysis/maps/system.py),
the target structure with the gap each part has closed, and the plan with its progress, the work log
(progress['handover'], eaos/journeys/handover.py brief) and every task card. progress['eaos'] stamps the page with the
EAOS that built it; progress['report_errors'] and every part that failed show in a warning at the top. No external asset, no network: inline CSS, inline SVG, a little inline JS. Every
number on the page carries its meaning in words next to it.

Progress comes from the ledger when the caller passes one (progress={'waves': [...], 'ledger': L}): a card
is closed only when it is 'done' (an EAOS fix merged into the person's main branch); a problem a later check no
longer finds leaves the plan, it is not counted as closed; 'on_branch' waits for the person and is not closed. With no ledger, a card a batch
kept counts as done, as before.

What a problem is, its area and severity, and the health score are computed once, in eaos/analysis/presentation/model.py, and
read here: the Studio and this page show the same numbers. The page is built in eaos/report/human_report/page.py; this
package names what the rest of EAOS imports.
"""
from .page import MAP_JS, SECTIONS, SYSTEM_JS, empty, model, render, section_summary, write

__all__ = ['MAP_JS', 'SECTIONS', 'SYSTEM_JS', 'empty', 'model', 'render', 'section_summary', 'write']
