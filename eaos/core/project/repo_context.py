"""Line-addressable, budgeted repository context with explicit exclusions."""
import json
from collections import OrderedDict
import re
from pathlib import Path
from .workspace import read, write, safe_file, digest
from ...core.system.clock import now

# Preserve line numbering; obvious credential values are removed before provider access.
SECRET=re.compile(r'''(?i)(\b[\w-]*(?:api[_-]?key|secret|password|access[_-]?token|authorization)[\w-]*["']?\s*[=:]\s*)("(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|[^\r\n,;}]+)''')
TOKEN=re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b')
URL_CREDENTIALS=re.compile(r'(?i)([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^@\s]+@')

def redact(text):
    text=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----',lambda m:'[REDACTED PRIVATE KEY]'+('\n'*m.group().count('\n')),text)
    text=URL_CREDENTIALS.sub(lambda m:m.group(1)+'[REDACTED CREDENTIALS]@',text)
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
        raw=''.join(lines[start-1:end])
        # Redact before slicing: a requested range can start inside a multiline key.
        # Redaction preserves line boundaries; evidence hashes still use raw source.
        clean=''.join(redact(''.join(lines)).splitlines(keepends=True)[start-1:end])
        ref={'path':path,'start_line':start,'end_line':end,'sha256':self.files[path]['sha256'],'range_sha256':digest(raw.encode())}
        eid='SRC-'+digest(json.dumps(ref,sort_keys=True).encode())[:20]
        block={'evidence_id':eid,'path':path,'start_line':start,'end_line':end,'redacted':raw!=clean,'source':'\n'.join(f'{i}: {line}' for i,line in enumerate(clean.splitlines(),start))}
        if len(json.dumps(block,ensure_ascii=False))>self.budget//2:raise ValueError('Requested range exceeds context allocation; narrow line range')
        self.evidence[eid]={'id':eid,'kind':'source','location':f'{path}:{start}-{end}','revision':self.state['revision'],'observed_at':now('auto'),'observation':'Source range made available to the model; semantic conclusions are separate.','method':'source_range_capture','limitations':'Static source only. '+('Credential-like values redacted; inspect sanitized behavior separately.' if raw!=clean else 'Not proof of runtime behavior.'),'source_ref':ref}
        self.seen.add(eid)
        if persist:write(self.run/'evidence.json',list(self.evidence.values()))
        return block

    def chunks(self,order=None,max_files=None):
        """Inspect in declared attention order; anything beyond the budget is deferred visibly, not dropped."""
        paths=_ordered(list(self.files),order,self.files)
        deferred=[]
        if max_files is not None and max_files < len(paths):
            paths,deferred=paths[:max_files],paths[max_files:]
        omissions=[{'path':path,'reason':'Deferred by the declared attention budget; this file was not semantically reviewed'} for path in deferred]
        return _stream(self,paths,omissions),omissions

    def verify_refs(self,value):
        errors=[]
        _walk_refs(value,self.evidence,errors)
        return errors


def _ordered(paths,order,files):
    """The declared attention order first, then every other file in inventory order."""
    if not order:return paths
    ranked=[p for p in order if p in files]
    return ranked+[p for p in paths if p not in set(ranked)]


def _readable(context,path,omissions):
    """The lines of a file the model may read; None, with the reason in `omissions`, for any other."""
    item=context.files[path]
    if item['capture']!='hashed':omissions.append({'path':path,'reason':item['capture']});return None
    try:lines=context.lines(path)
    except (ValueError,UnicodeError,OSError):omissions.append({'path':path,'reason':'Sensitive, binary, unreadable or changed source'});return None
    if not lines:omissions.append({'path':path,'reason':'empty file; metadata only'});return None
    return lines


def _span_end(lines,start,limit):
    """The line after the longest run from `start` whose size (each line and 20) stays under `limit`."""
    end=start;amount=0
    while end<=len(lines) and amount+len(lines[end-1])+20<limit:
        amount+=len(lines[end-1])+20;end+=1
    return end


def _file_blocks(context,path,lines,omissions):
    """(block, its size) of each run of a file's lines that fits the budget; a line alone too long is omitted."""
    start=1
    while start<=len(lines):
        end=_span_end(lines,start,context.budget//5)
        if end==start:
            omissions.append({'path':path,'start_line':start,'end_line':start,'reason':'Single line exceeds budget; explicit alternate inspection required'});start+=1;continue
        block=context.source(path,start,end-1,persist=False)
        yield block,len(json.dumps(block,ensure_ascii=False))
        start=end


def _stream(context,paths,omissions):
    """Batches of blocks, each within half the budget; the evidence is saved before each batch is handed on."""
    batch=[];size=0
    for path in paths:
        for block,amount in _file_blocks(context,path,_readable(context,path,omissions) or [],omissions):
            if batch and size+amount>context.budget//2:
                write(context.run/'evidence.json',list(context.evidence.values()))
                yield batch
                batch=[];size=0
            batch.append(block);size+=amount
    write(context.run/'evidence.json',list(context.evidence.values()))
    if batch:yield batch


def _valid_ids(ids,evidence):
    return isinstance(ids,list) and all(isinstance(e,str) and e in evidence for e in ids)


def _walk_refs(obj,evidence,errors):
    """An error for every `evidence_ids` in `obj`, at any depth, that names an id the context does not hold."""
    if isinstance(obj,dict):
        for k,v in obj.items():
            if k=='evidence_ids' and not _valid_ids(v,evidence):errors.append('Unknown or invalid evidence_ids')
            _walk_refs(v,evidence,errors)
    elif isinstance(obj,list):
        for item in obj:_walk_refs(item,evidence,errors)
