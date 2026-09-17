"""Deterministically render documentation and packaged rule data from canonical files."""
from pathlib import Path
import json
import shutil
R=Path(__file__).resolve().parents[1]
def render():
    registry=json.loads((R/'controls.json').read_text());sources=json.loads((R/'sources.json').read_text())
    taxonomy=['# Taxonomy','', '| ID | Domain | Applies when | Controls |','|---|---|---|---|']
    outputs=[]
    for m in registry['modules']:
        taxonomy.append(f"| {m['id']} | {m['title']} | {m['applies_when']} | {len(m['controls'])} |")
        lines=[f"# {m['id']} — {m['title']}",'','Generated from controls.json. Do not edit this derived file.','',f"**Applicability:** {m['applies_when']}",f"**Artifacts:** {m['artifacts']}",'','قبل الحكم: حدد component/flow/environment/revision. افصل requirement عن preference. لكل control سجل evidence وcounter-evidence وcoverage instance؛ لا تعتبر N/A بلا سبب.','']
        for c in m['controls']:
            lines += [f"## {c['id']} — {c['name']}",'',f"- **Invariant:** {c['invariant']}",f"- **Inspection procedure:** {c['procedure']}",f"- **Verification / negative test:** {c['verification']}",f"- **Counter-evidence:** {c['counter_evidence']}",f"- **Required evidence:** {c['evidence_required']}",f"- **Source IDs:** {', '.join(c['source_ids'])}",f"- **Provenance:** {c['origin']}; seed references: {', '.join(c['seed_refs']) or 'external research / original synthesis'}",'']
        content='\n'.join(lines)+'\n'; (R/'modules'/f"{m['id']}.md").write_text(content);outputs.append(content)
    (R/'TAXONOMY.md').write_text('\n'.join(taxonomy)+'\n')
    parts=['# Engineering Audit OS — Master Manual\n\nVersion 2.1.0. Generated from canonical core, registry and research.\n']
    for name in ['START-HERE.md','core/ARCHITECTURE-FIRST.md','core/AGENT-WORKFLOW.md','core/OPERATING-MANUAL.md','core/EVIDENCE-AND-TRIAGE.md','core/REMEDIATION-AND-GATES.md','core/CLI-AND-CONTEXT.md','TAXONOMY.md']:
        parts.append((R/name).read_text())
    parts+=outputs
    for name in ['templates/RECORDS.md','examples/SCENARIOS.md','core/EXTENSION-PROTOCOL.md','research/RESEARCH.md','research/ARCHITECTURE-SEED.md','research/SOURCES.md']:
        parts.append((R/name).read_text())
    parts.append('# Architecture JSON Schema\n\n```json\n'+(R/'schemas/architecture.schema.json').read_text()+'```\n')
    parts.append('# Finding JSON Schema\n\n```json\n'+(R/'schemas/finding.schema.json').read_text()+'```\n')
    (R/'MASTER-MANUAL.md').write_text('\n\n---\n\n'.join(parts))
    data=R/'eaos/data';data.mkdir(exist_ok=True)
    for path in ['controls.json','sources.json','START-HERE.md']:
        shutil.copyfile(R/path,data/path)
    for folder in ['core','modules','schemas']:
        (data/folder).mkdir(exist_ok=True)
        for p in (R/folder).iterdir():
            if p.is_file():shutil.copyfile(p,data/folder/p.name)
    return len(outputs),sum(len(m['controls']) for m in registry['modules'])
if __name__=='__main__':print('Rendered modules, controls:',render())
