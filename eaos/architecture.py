"""Evidence-backed architecture records and graph queries. No inferred code semantics."""
from collections import deque
from pathlib import PurePosixPath

VERSION = 1
RELATIONS = {'imports','calls','uses_contract','reads','writes','configures'}
STATIC_RELATIONS = {'imports','uses_contract'}
CORE_MODULES = {'01','02','03','04','15','22','26','27'}

def empty_model(revision):
    return {'schema_version':VERSION,'revision':revision,'coverage':{'status':'UNREVIEWED','scope':'UNDEFINED','limitations':['Model has not been reconstructed from source.']},'nodes':[],'edges':[],'contracts':[],'business_rules':[],'change_scenarios':[],'dependency_policies':[]}

def validate_model(model,evidence,revision,inventory_paths):
    errors=[];gaps=[]
    if not isinstance(model,dict):return ['Architecture must be an object'],['Architecture unreviewed']
    if model.get('schema_version')!=VERSION:errors.append('Unsupported architecture schema')
    if model.get('revision')!=revision:errors.append('Architecture revision is stale')
    ids={};collections=['nodes','edges','contracts','business_rules','change_scenarios','dependency_policies']
    for col in collections:
        rows=model.get(col)
        if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):
            errors.append(col+' must be an array of objects');continue
        ids[col]={}
        for row in rows:
            rid=row.get('id')
            if not isinstance(rid,str) or not rid:errors.append(col+' missing string id');continue
            if rid in ids[col]:errors.append('Duplicate '+col+' id '+rid)
            ids[col][rid]=row
            refs=row.get('evidence_ids',[])
            if not isinstance(refs,list) or any(not isinstance(e,str) for e in refs):errors.append(rid+' invalid evidence_ids');continue
            for eid in refs:
                if eid not in evidence:errors.append(rid+' unknown evidence '+eid)
                elif evidence[eid].get('revision')!=revision:errors.append(rid+' stale evidence '+eid)
            if not refs:gaps.append(rid+' has no evidence')
    if len(ids)!=len(collections):return errors,['Architecture has malformed collections']
    nodes=ids['nodes']
    def node_ref(rid,ref):
        if not isinstance(ref,str) or ref not in nodes:errors.append(str(rid)+' unknown node '+str(ref))
    def text_fields(row,fields):
        for k in fields:
            if not isinstance(row.get(k),str) or not row[k].strip():errors.append(row.get('id','?')+' missing '+k)
    for n in nodes.values():
        text_fields(n,['name','kind','responsibility','domain','boundary','owner'])
        paths=n.get('paths',[])
        if not isinstance(paths,list) or any(not isinstance(p,str) for p in paths):errors.append(n['id']+' invalid paths');continue
        for p in paths:
            if PurePosixPath(p).is_absolute() or '..' in PurePosixPath(p).parts or p not in inventory_paths:errors.append(n['id']+' path absent from inventory: '+p)
        if n.get('kind')!='external' and not paths:gaps.append(n['id']+' no source paths')
    for e in ids['edges'].values():
        node_ref(e['id'],e.get('from'));node_ref(e['id'],e.get('to'))
        if e.get('relation') not in RELATIONS:errors.append(e['id']+' invalid relation')
        if e.get('status') not in ['CONFIRMED','HYPOTHESIS']:errors.append(e['id']+' invalid edge status')
        if e.get('status')=='HYPOTHESIS':gaps.append(e['id']+' unresolved edge')
        text_fields(e,['reason'])
    for col in ['contracts','business_rules']:
        for row in ids[col].values():
            node_ref(row['id'],row.get('owner'));text_fields(row,['description','invariant'])
            consumers=row.get('consumers')
            if not isinstance(consumers,list):errors.append(row['id']+' consumers must be array');continue
            for consumer in consumers:node_ref(row['id'],consumer)
            if col=='contracts':text_fields(row,['failure_semantics','compatibility'])
    for row in ids['change_scenarios'].values():
        text_fields(row,['stimulus','environment','artifact','response','measure','method'])
        refs=row.get('affected_nodes')
        if not isinstance(refs,list) or not refs:errors.append(row['id']+' requires affected_nodes')
        else:
            for n in refs:node_ref(row['id'],n)
        if row.get('status') not in ['UNREVIEWED','TRACED','TESTED']:errors.append(row['id']+' invalid scenario status')
        if row.get('status')=='UNREVIEWED':gaps.append(row['id']+' scenario unreviewed')
        if row.get('status')=='TESTED' and not any(evidence.get(e,{}).get('kind')=='test' for e in row.get('evidence_ids',[])):
            errors.append(row['id']+' TESTED requires test evidence')
    for row in ids['dependency_policies'].values():
        node_ref(row['id'],row.get('from'));node_ref(row['id'],row.get('to'));text_fields(row,['reason'])
        if row.get('relation') not in RELATIONS:errors.append(row['id']+' invalid policy relation')
        if row.get('rule')!='forbid':errors.append(row['id']+' unsupported policy rule')
    coverage=model.get('coverage',{})
    if not isinstance(coverage,dict):return errors+['Invalid architecture coverage'],gaps
    if coverage.get('status') not in ['UNREVIEWED','PARTIAL','REVIEWED']:errors.append('Invalid architecture coverage status')
    if coverage.get('status')!='REVIEWED':gaps.append('Architecture coverage not reviewed')
    if not isinstance(coverage.get('scope'),str) or not coverage['scope'].strip() or coverage['scope']=='UNDEFINED':gaps.append('Architecture scope undefined')
    if coverage.get('limitations'):gaps.append('Architecture coverage has unresolved limitations')
    if not nodes:gaps.append('No reconstructed components')
    if not ids['change_scenarios']:gaps.append('No change scenario assessed')
    if not ids['business_rules']:gaps.append('No business rules or explicit no-domain invariant mapped')
    if not ids['contracts']:gaps.append('No explicit component contracts mapped')
    return sorted(set(errors)),sorted(set(gaps))

def adjacency(model,relations=None):
    graph={n['id']:set() for n in model['nodes']}
    for e in model['edges']:
        if e['status']=='CONFIRMED' and (relations is None or e['relation'] in relations):graph[e['from']].add(e['to'])
    return graph

def cycles(graph):
    """Iterative Kosaraju SCC; an SCC is a signal, not automatically a defect."""
    reverse={n:set() for n in graph}
    for n,neighbors in graph.items():
        for other in neighbors:reverse[other].add(n)
    seen=set();order=[]
    for start in sorted(graph):
        if start in seen:continue
        stack=[(start,False)]
        while stack:
            n,done=stack.pop()
            if done:order.append(n);continue
            if n in seen:continue
            seen.add(n);stack.append((n,True))
            stack.extend((other,False) for other in sorted(graph[n],reverse=True) if other not in seen)
    seen=set();groups=[]
    for start in reversed(order):
        if start in seen:continue
        stack=[start];group=[];seen.add(start)
        while stack:
            n=stack.pop();group.append(n)
            for other in sorted(reverse[n]):
                if other not in seen:seen.add(other);stack.append(other)
        if len(group)>1 or start in graph[start]:groups.append(sorted(group))
    return sorted(groups)

def impact(model,node,depth=2):
    graph=adjacency(model)
    if node not in graph:raise ValueError('Unknown architecture node: '+node)
    reverse={n:set() for n in graph}
    for n,neighbors in graph.items():
        for other in neighbors:reverse[other].add(n)
    distances={node:0};queue=deque([node])
    while queue:
        current=queue.popleft()
        if distances[current]>=depth:continue
        for consumer in sorted(reverse[current]):
            if consumer not in distances:distances[consumer]=distances[current]+1;queue.append(consumer)
    frontier=sorted({c for n,d in distances.items() if d==depth for c in reverse[n] if c not in distances})
    direct_contract_consumers=sorted({c for col in ['contracts','business_rules'] for r in model[col] if r['owner']==node for c in r['consumers']})
    # Explicit consumer declarations participate even if an edge has not yet been modelled.
    return {'node':node,'potential_dependents':sorted(n for n in distances if n!=node),'distances':distances,'direct_dependencies':sorted(graph[node]),'declared_contract_or_rule_consumers':direct_contract_consumers,'depth':depth,'unexpanded_frontier':frontier,'hypothesis_edges':[e['id'] for e in model['edges'] if e['status']=='HYPOTHESIS' and (e['from'] in distances or e['to'] in distances)],'interpretation':'Potential review scope in the supplied model, not proof that every node must change. Missing/dynamic edges can expand impact.'}

def summary(model):
    graph=adjacency(model,STATIC_RELATIONS)
    fan_in={n:0 for n in graph}
    for neighbors in graph.values():
        for n in neighbors:fan_in[n]+=1
    violations=[]
    for p in model['dependency_policies']:
        for e in model['edges']:
            if e['status']=='CONFIRMED' and all(e[k]==p[k] for k in ['from','to','relation']):violations.append({'policy_id':p['id'],'edge_id':e['id'],'evidence_ids':sorted(set(p['evidence_ids']+e['evidence_ids']))})
    return {'coverage':model['coverage'],'nodes':len(graph),'confirmed_edges':sum(e['status']=='CONFIRMED' for e in model['edges']),'static_dependency_cycles':cycles(graph),'degree_signals':[{'node':n,'fan_in':fan_in[n],'fan_out':len(graph[n])} for n in sorted(graph)],'declared_policy_violations':violations,'interpretation':'Cycles/degree are investigation signals, never severity scores. Only explicitly declared forbidden dependencies yield policy matches.'}

def context_data(model,node,depth):
    assessment=impact(model,node,depth)
    selected=set(assessment['distances'])|set(assessment['direct_dependencies'])|set(assessment['declared_contract_or_rule_consumers'])
    records={col:[r for r in model[col] if r['owner'] in selected or any(c in selected for c in r['consumers'])] for col in ['contracts','business_rules']}
    # Include all endpoints referenced by selected semantic contracts, no silently dangling context.
    for rows in records.values():
        for r in rows:selected.add(r['owner']);selected.update(r['consumers'])
    result={'impact':assessment,'nodes':[n for n in model['nodes'] if n['id'] in selected],'edges':[e for e in model['edges'] if e['from'] in selected and e['to'] in selected],**records,'change_scenarios':[s for s in model['change_scenarios'] if any(n in selected for n in s['affected_nodes'])]}
    result['omitted_node_count']=len(model['nodes'])-len(selected)
    result['omitted_incident_edge_ids']=[e['id'] for e in model['edges'] if (e['from'] in selected)!=(e['to'] in selected)]
    return result
