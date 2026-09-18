"""Session creation shared by entrypoints and orchestration; no CLI dependency."""
from pathlib import Path
from . import __version__
from . import architecture as arch
from .workspace import inventory,write,registry,now,DATA

def create_run(target, out, profile="architecture", max_files=100000, max_bytes=2_000_000):
    target=Path(target).resolve();out=Path(out).resolve()
    if out==target or target in out.parents: raise ValueError('--out must be outside target to preserve read-only discovery')
    if out.exists(): raise ValueError('Output exists; choose a new run directory (never overwritten)')
    inv=inventory(target,max_files,max_bytes)
    out.mkdir(parents=True)
    write(out/'inventory.json',inv)
    state={'schema_version':2,'framework_version':__version__,'profile':profile,'id':out.name,'created_at':now(),'target':str(target),'revision':inv['fingerprint'],'mode':'audit_only','completion':'INCOMPLETE','remediation_completion':'NOT_REQUESTED','production_readiness':'NOT_ASSESSED','scope':{'description':'UNDEFINED — agent must define boundaries, environments and excluded surfaces','environments':[],'approved_exclusions':[]},'scope_confirmed':False,'inventory_reviewed':False,'architecture_reviewed':False,'product_flows_reviewed':False,'expected_instances':[],'unknowns':['Architecture, responsibilities and change impact have not been reconstructed.'],'module_decisions':[{'module_id':m['id'],'applicability':'UNDECIDED' if profile=='full' or m['id'] in arch.CORE_MODULES else 'OUT_OF_SCOPE','reason':'' if profile=='full' or m['id'] in arch.CORE_MODULES else 'Supporting lens; activate when architecture or change scenarios cross this domain. Not a complete domain audit.','evidence_ids':[]} for m in registry()['modules']]}
    write(out/'run.json',state)
    write(out/'architecture.json',arch.empty_model(state['revision']))
    for n in ['findings','coverage','evidence','gates','decisions']:write(out/(n+'.json'),[])
    (out/'architecture.md').write_text('# Architecture reconstruction\n\nUNREVIEWED. Record components, trust boundaries and evidence-backed edges.\n')
    (out/'product-flows.md').write_text('# Product journeys and invariants\n\nUNREVIEWED. Separate requirements, observed behavior and hypotheses.\n')
    (out/'AGENT-START.md').write_text((DATA/'START-HERE.md').read_text()+'\n\nRun directory: `'+str(out)+'`\nTarget: `'+str(target)+'`\nUse `eaos plan` and `eaos packet`; review unknowns before claiming completion.\n')
    return out

