"""Resumable model jobs, bounded context, source retrieval and validation feedback."""
import json
from pathlib import Path
from ..workspace import read,write,digest,now
from .contracts import SYSTEM,contract,basic_errors

class Jobs:
    def __init__(self,run,context,provider,budget,max_rounds=8):
        self.run=Path(run);self.context=context;self.provider=provider;self.budget=budget;self.max_rounds=max_rounds
        (self.run/'jobs').mkdir(exist_ok=True)
        self.catalog=set();self.dependencies={}
        self.metrics=read(self.run/'usage.json') if (self.run/'usage.json').exists() else []

    def record(self,name,offset=0,limit=20,section=None):
        if name not in self.catalog and name!='record-index.json':raise ValueError('Record is not exposed to this engine session')
        p=self.run/name
        if p.is_symlink():raise ValueError('Symlink record prohibited')
        value=sorted(self.catalog) if name=='record-index.json' else read(p)
        if name!='record-index.json':self.dependencies[name]=digest(p.read_bytes())
        if section is not None:
            if not isinstance(value,dict) or section not in value:raise ValueError('Unknown record section')
            value=value[section]
        if type(offset) is not int or type(limit) is not int or offset<0 or not 1<=limit<=100:raise ValueError('Invalid record page')
        if isinstance(value,list):value={'items':value[offset:offset+limit],'total':len(value),'offset':offset,'next_offset':offset+limit if offset+limit<len(value) else None}
        if len(json.dumps(value,ensure_ascii=False))>self.budget//2:raise ValueError('Record is too large; request section/page')
        return {'name':name,'section':section,'content':value}

    def run_job(self,name,stage,payload,validate=None):
        identity={'stage':stage,'payload':payload,'contract':contract(stage),'provider':self.provider.identity(),'protocol':SYSTEM,'revision':None if stage=='inspect' else self.context.state['revision']}
        key=digest(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode())
        path=self.run/'jobs'/(name+'-'+key[:16]+'.json')
        if path.exists():
            cached=read(path);result=cached['result']
            errors=basic_errors(stage,result)+self.context.verify_refs(result)+(validate(result) if validate else [])
            dependencies=cached.get('record_hashes',{})
            records_current=all((self.run/name).is_file() and digest((self.run/name).read_bytes())==h for name,h in dependencies.items())
            if cached.get('key')==key and not errors and records_current:return result
        initial={'stage':stage,'instructions':payload,'output_contract':contract(stage),'available_records':{'catalog':'record-index.json (paginated array of all available record names)','core':[n for n in sorted(self.catalog) if not n.startswith(('brief-','synthesis-','scope-','review-'))]}}
        memory={};history=[];self.dependencies={}
        for round_no in range(self.max_rounds):
            messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(initial,ensure_ascii=False)}]
            if memory:messages.append({'role':'user','content':json.dumps(memory,ensure_ascii=False)})
            chars=len(json.dumps(messages,ensure_ascii=False))
            if chars>self.budget:raise ValueError(f'Job {name} exceeds context budget ({chars}>{self.budget}); nothing silently truncated')
            if len(self.metrics)>=400:raise ValueError('Run reached its 400-call limit; progress preserved. Review usage before starting additional work.')
            response,usage=self.provider.complete(messages)
            self.metrics.append({'job':name,'round':round_no+1,'request_characters':chars,'usage':usage,'time':now()})
            write(self.run/'usage.json',self.metrics)
            if response.get('action')=='read':
                try:
                    reads=response.get('reads',[]);records=response.get('records',[])
                    if not isinstance(reads,list) or not isinstance(records,list) or not 1<=len(reads)+len(records)<=8:raise ValueError('Request 1–8 sources/records per round')
                    supplied=[self.context.source(r['path'],r['start'],r['end']) for r in reads]
                    supplied += [self.record(r['name'],r.get('offset',0),r.get('limit',20),r.get('section')) for r in records]
                    notes=response.get('notes','')
                    if not isinstance(notes,str) or len(notes)>self.budget//8:raise ValueError('Working notes too large')
                    memory={'working_notes':notes,'requested_data':supplied}
                    if len(json.dumps(memory,ensure_ascii=False))>self.budget//2:raise ValueError('Read response too large; request smaller ranges/pages')
                except (KeyError,TypeError,ValueError,OSError,UnicodeError) as exc:
                    memory={'feedback':str(exc),'instruction':'Narrow or correct the read request; do not invent inaccessible content.'}
                continue
            result=response.get('result')
            errors=basic_errors(stage,result) if response.get('action')=='final' else ['Expected read or final action']
            if not errors:errors=self.context.verify_refs(result)+(validate(result) if validate else [])
            if errors:
                history.append({'round':round_no+1,'errors':errors})
                memory={'validation_errors':errors,'previous_result':result,'instruction':'Correct these record/engineering gaps; retain unresolved facts instead of inventing proof.'}
                # Large invalid output is retained on disk for diagnosis; no silent truncation.
                write(self.run/'jobs'/(name+'-invalid.json'),{'response':response,'errors':errors})
                continue
            write(path,{'key':key,'stage':stage,'revision':self.context.state['revision'],'result':result,'validation_history':history,'record_hashes':dict(self.dependencies),'created_at':now()})
            return result
        raise ValueError(f'Job {name} exhausted {self.max_rounds} rounds; progress saved, no completion claim')
