"""Evidence-backed architecture records and graph queries. No inferred code semantics."""
from collections import deque

VERSION = 1
RELATIONS = {'imports','calls','uses_contract','reads','writes','configures'}
STATIC_RELATIONS = {'imports','uses_contract'}
CORE_MODULES = {'01','02','03','04','15','22','26','27'}


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

