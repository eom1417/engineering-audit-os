"""Two vocabularies every layer shares: what a path is, and whether a record fits its schema.

Both lived in the agent-led run subsystem, so the facts and ledger layers reached across a
boundary to borrow them. They belong to neither subsystem; they are how the whole system reads a
path and checks a record.
"""
from pathlib import Path
import re

from ..project.workspace import INFRA, STACKS

SOURCE = {'.py','.js','.jsx','.ts','.tsx','.mjs','.cjs','.go','.rs','.java','.kt','.cs','.php','.rb','.ex','.exs','.dart','.vue','.svelte','.swift','.c','.cpp','.h','.sql'}
CONFIG = {'.json','.toml','.yaml','.yml','.xml','.ini','.cfg','.tf','.sh'}

SUPPORTED_KEYWORDS={'type','enum','const','properties','required','additionalProperties','items',
                    'minLength','maxLength','pattern','minItems','maxItems','minimum','maximum','description',
                    '$schema','$id','title','format','anyOf'}

# Contract checks deliberately limited to record consistency, never proof of real-world behavior.
# Keywords outside SUPPORTED_KEYWORDS are reported rather than ignored: a constraint nobody enforces
# is worse than no constraint, because the schema reads as a guarantee.


TYPES={'object':dict,'array':list,'string':str,'null':type(None),'boolean':bool,'integer':int,'number':(int,float)}


def _is_test(name, parts):
    return bool(parts & {'tests','test','__tests__','spec'}) or bool(re.search(r'(^test_|[._](test|spec)\.)',name))


def _kind_by_suffix(suffix, name):
    if suffix in SOURCE:return 'source'
    if suffix in CONFIG or name in {'dockerfile','makefile'}:return 'configuration'
    if suffix in {'.md','.rst','.txt'}:return 'documentation'
    return 'other'


def classify(path):
    p=Path(path);name=p.name.lower();parts={s.lower() for s in p.parts}
    if p.name in STACKS or p.suffix in {'.csproj','.fsproj'}:return 'manifest'
    # A deployment word in the path (docker, compose, helm) makes a manifest infrastructure, not code:
    # eaos/core/language/words.py and src/components/DockerStatus.tsx are source files like any other.
    if INFRA.search(path) and p.suffix not in SOURCE:return 'infrastructure'
    if _is_test(name,parts):return 'test'
    return _kind_by_suffix(p.suffix,name)


def _wrong_type(value, spec):
    expected=spec.get('type')
    allowed=expected if isinstance(expected,list) else [expected] if expected else []
    if not allowed:return False
    if 'integer' in allowed and isinstance(value,bool):return True
    return not any(isinstance(value,TYPES[t]) for t in allowed if t in TYPES)


def _text_errors(value, spec, path):
    errors=[]
    if len(value)<spec.get('minLength',0):errors.append(path+' empty text')
    if 'maxLength' in spec and len(value)>spec['maxLength']:errors.append(path+' longer than '+str(spec['maxLength']))
    if 'pattern' in spec and not re.search(spec['pattern'],value):errors.append(path+' does not match '+spec['pattern'])
    return errors


def _number_errors(value, spec, path):
    errors=[]
    if 'minimum' in spec and value<spec['minimum']:errors.append(path+' below minimum')
    if 'maximum' in spec and value>spec['maximum']:errors.append(path+' above maximum')
    return errors


def _list_errors(value, spec, path):
    errors=[]
    if len(value)<spec.get('minItems',0):errors.append(path+' needs at least '+str(spec['minItems'])+' items')
    if 'maxItems' in spec and len(value)>spec['maxItems']:errors.append(path+' has more than '+str(spec['maxItems'])+' items')
    if 'items' in spec:
        for i,v in enumerate(value):errors+=schema_errors(v,spec['items'],path+f'[{i}]')
    return errors


def _object_errors(value, spec, path):
    errors=[path+' missing '+key for key in spec.get('required',[]) if key not in value]
    props=spec.get('properties',{})
    for key,v in value.items():
        if key in props:errors+=schema_errors(v,props[key],path+'.'+key)
        elif spec.get('additionalProperties') is False:errors.append(path+' unexpected '+key)
    return errors


def _shape_errors(value, spec, path):
    if isinstance(value,str):return _text_errors(value,spec,path)
    if isinstance(value,bool):return []
    if isinstance(value,(int,float)):return _number_errors(value,spec,path)
    if isinstance(value,list):return _list_errors(value,spec,path)
    if isinstance(value,dict):return _object_errors(value,spec,path)
    return []


def schema_errors(value, spec, path='$'):
    if _wrong_type(value,spec):return [path+' invalid type']
    unsupported=sorted(set(spec)-SUPPORTED_KEYWORDS)
    errors=[path+' schema uses unenforced keywords: '+', '.join(unsupported)] if unsupported else []
    if 'enum' in spec and value not in spec['enum']:errors.append(path+' invalid enum')
    if 'const' in spec and value!=spec['const']:errors.append(path+' must equal '+repr(spec['const']))
    return errors+_shape_errors(value,spec,path)
