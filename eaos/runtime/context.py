"""Line-addressable, budgeted repository context with explicit exclusions."""
import json
from collections import OrderedDict
import re
from pathlib import Path
from ..workspace import read,write,safe_file,digest,now
from ..discovery import classify

# Preserve line numbering; obvious credential values are removed before provider access.
SECRET=re.compile(r'(?i)(\b(?:api[_-]?key|secret|password|access[_-]?token|authorization)\b\s*[=:]\s*)([^\r\n]+)')
TOKEN=re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b')

def redact(text):
    text=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----',lambda m:'[REDACTED PRIVATE KEY]'+('\n'*m.group().count('\n')),text)
    return TOKEN.sub('[REDACTED TOKEN]',SECRET.sub(lambda m:m.group(1)+'[REDACTED VALUE]',text))

class Context:
    def __init__(self,run,state,budget):
        self.run=Path(run);self.state=state;self.budget=budget
        self.inventory=read(self.run/'inventory.json');self.files={f['path']:f for f in self.inventory['files']}
        self.evidence={e['id']:e for e in read(self.run/'evidence.json')}
        self.seen=set();self.text_cache=OrderedDict()

    def lines(self,path):
        item=self.files.get(path)
        if not item or item['capture']!='hashed':raise ValueError('Source is excluded or absent from inventory')
        if path not in self.text_cache:
            raw=safe_file(Path(self.state['target']),path).read_bytes()
            if digest(raw)!=item['sha256']:raise ValueError('Source changed during analysis')
            text=raw.decode('utf-8')
            if '\x00' in text:raise ValueError('Binary source cannot enter model context')
            self.text_cache[path]=text.splitlines(keepends=True)
            while len(self.text_cache)>8:self.text_cache.popitem(last=False)
        self.text_cache.move_to_end(path)
        return self.text_cache[path]

    def source(self,path,start,end,persist=True):
        lines=self.lines(path)
        if type(start) is not int or type(end) is not int or not 1<=start<=end<=len(lines):raise ValueError('Invalid requested source range')
        raw=''.join(lines[start-1:end]);clean=redact(raw)
        ref={'path':path,'start_line':start,'end_line':end,'sha256':self.files[path]['sha256'],'range_sha256':digest(raw.encode())}
        eid='SRC-'+digest(json.dumps(ref,sort_keys=True).encode())[:20]
        block={'evidence_id':eid,'path':path,'start_line':start,'end_line':end,'redacted':raw!=clean,'source':'\n'.join(f'{i}: {line}' for i,line in enumerate(clean.splitlines(),start))}
        if len(json.dumps(block,ensure_ascii=False))>self.budget//2:raise ValueError('Requested range exceeds context allocation; narrow line range')
        self.evidence[eid]={'id':eid,'kind':'source','location':f'{path}:{start}-{end}','revision':self.state['revision'],'observed_at':now(),'observation':'Source range made available to the model; semantic conclusions are separate.','method':'source_range_capture','limitations':'Static source only. '+('Credential-like values redacted; inspect sanitized behavior separately.' if raw!=clean else 'Not proof of runtime behavior.'),'source_ref':ref}
        self.seen.add(eid)
        if persist:write(self.run/'evidence.json',list(self.evidence.values()))
        return block

    def chunks(self):
        omissions=[]
        def stream():
            batch=[];size=0
            for path,item in self.files.items():
                if item['capture']!='hashed':omissions.append({'path':path,'reason':item['capture']});continue
                try:lines=self.lines(path)
                except (ValueError,UnicodeError,OSError):omissions.append({'path':path,'reason':'Sensitive, binary, unreadable or changed source'});continue
                if not lines:omissions.append({'path':path,'reason':'empty file; metadata only'});continue
                start=1
                while start<=len(lines):
                    end=start;amount=0
                    while end<=len(lines) and amount+len(lines[end-1])+20<self.budget//5:
                        amount+=len(lines[end-1])+20;end+=1
                    if end==start:
                        omissions.append({'path':path,'start_line':start,'end_line':start,'reason':'Single line exceeds budget; explicit alternate inspection required'});start+=1;continue
                    block=self.source(path,start,end-1,persist=False);amount=len(json.dumps(block,ensure_ascii=False))
                    if batch and size+amount>self.budget//2:
                        write(self.run/'evidence.json',list(self.evidence.values()))
                        yield batch
                        batch=[];size=0
                    batch.append(block);size+=amount;start=end
            write(self.run/'evidence.json',list(self.evidence.values()))
            if batch:yield batch
        return stream(),omissions

    def verify_refs(self,value):
        errors=[]
        def walk(obj):
            if isinstance(obj,dict):
                for k,v in obj.items():
                    if k=='evidence_ids':
                        if not isinstance(v,list) or not all(isinstance(e,str) and e in self.evidence for e in v):errors.append('Unknown or invalid evidence_ids')
                    walk(v)
            elif isinstance(obj,list):
                for item in obj:walk(item)
        walk(value);return errors
