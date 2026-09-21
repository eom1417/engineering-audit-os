"""Two vocabularies every layer shares: what a path is, and whether a record fits its schema.

Both lived in the agent-led run subsystem, so the facts and ledger layers reached across a
boundary to borrow them. They belong to neither subsystem; they are how the whole system reads a
path and checks a record.
"""
from pathlib import Path
import re

from .workspace import INFRA, STACKS

SOURCE = {'.py','.js','.jsx','.ts','.tsx','.mjs','.cjs','.go','.rs','.java','.kt','.cs','.php','.rb','.ex','.exs','.dart','.vue','.svelte','.swift','.c','.cpp','.h','.sql'}
CONFIG = {'.json','.toml','.yaml','.yml','.xml','.ini','.cfg','.tf','.sh'}

SUPPORTED_KEYWORDS={'type','enum','const','properties','required','additionalProperties','items',
                    'minLength','maxLength','pattern','minItems','maxItems','minimum','maximum','description',
                    '$schema','$id','title','format','anyOf'}

# Contract checks deliberately limited to record consistency, never proof of real-world behavior.
# Keywords outside SUPPORTED_KEYWORDS are reported rather than ignored: a constraint nobody enforces
# is worse than no constraint, because the schema reads as a guarantee.


def classify(path):
    p=Path(path);name=p.name.lower();parts={s.lower() for s in p.parts}
    if p.name in STACKS or p.suffix in {'.csproj','.fsproj'}:return 'manifest'
    if INFRA.search(path):return 'infrastructure'
    if parts & {'tests','test','__tests__','spec'} or re.search(r'(^test_|[._](test|spec)\.)',name):return 'test'
    if p.suffix in SOURCE:return 'source'
    if p.suffix in CONFIG or name in {'dockerfile','makefile'}:return 'configuration'
    if p.suffix in {'.md','.rst','.txt'}:return 'documentation'
    return 'other'


def schema_errors(value, spec, path='$'):
    errors=[]
    types={'object':dict,'array':list,'string':str,'null':type(None),'boolean':bool,'integer':int,'number':(int,float)}
    unsupported=sorted(set(spec)-SUPPORTED_KEYWORDS)
    if unsupported:errors.append(path+' schema uses unenforced keywords: '+', '.join(unsupported))
    expected=spec.get('type')
    allowed=expected if isinstance(expected,list) else [expected] if expected else []
    if allowed:
        if any(t=='integer' for t in allowed) and isinstance(value,bool):return [path+' invalid type']
        if not any(isinstance(value,types[t]) for t in allowed if t in types):return [path+' invalid type']
    if 'enum' in spec and value not in spec['enum']:errors.append(path+' invalid enum')
    if 'const' in spec and value!=spec['const']:errors.append(path+' must equal '+repr(spec['const']))
    if isinstance(value,str):
        if len(value)<spec.get('minLength',0):errors.append(path+' empty text')
        if 'maxLength' in spec and len(value)>spec['maxLength']:errors.append(path+' longer than '+str(spec['maxLength']))
        if 'pattern' in spec and not re.search(spec['pattern'],value):errors.append(path+' does not match '+spec['pattern'])
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if 'minimum' in spec and value<spec['minimum']:errors.append(path+' below minimum')
        if 'maximum' in spec and value>spec['maximum']:errors.append(path+' above maximum')
    if isinstance(value,list):
        if len(value)<spec.get('minItems',0):errors.append(path+' needs at least '+str(spec['minItems'])+' items')
        if 'maxItems' in spec and len(value)>spec['maxItems']:errors.append(path+' has more than '+str(spec['maxItems'])+' items')
    if isinstance(value,dict):
        for key in spec.get('required',[]):
            if key not in value:errors.append(path+' missing '+key)
        props=spec.get('properties',{})
        for key,v in value.items():
            if key in props:errors+=schema_errors(v,props[key],path+'.'+key)
            elif spec.get('additionalProperties') is False:errors.append(path+' unexpected '+key)
    if isinstance(value,list) and 'items' in spec:
        for i,v in enumerate(value):errors+=schema_errors(v,spec['items'],path+f'[{i}]')
    return errors
