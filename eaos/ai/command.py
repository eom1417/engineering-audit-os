"""Running the person's AI assistant: its adapter is a command (eaos/ai/claude_adapter.py, codex_adapter.py)
that reads JSON messages on stdin and answers JSON on stdout. No key, no endpoint, no shell."""
import json
import os
import subprocess
import tempfile

from ..core.process import wait


def _int_in(value,low,high):
    """Whether `value` is an integer (not a bool) from `low` to `high`."""
    return type(value) is int and low<=value<=high


def _request(messages,small,reads,deep):
    """The JSON the adapter reads on stdin: the messages and only the options asked."""
    return json.dumps({'messages':messages,**({'small':True} if small else {}),
                       **({'reads':str(reads)} if reads else {}),**({'deep':True} if deep else {})}).encode()


class Provider:
    def __init__(self,config):
        self.config=dict(config)
        self.kind=config.get('kind','command')
        max_calls=config.get('max_calls',400)
        if not _int_in(max_calls,1,100000):raise ValueError('max_calls must be an integer between 1 and 100000')
        self.limit=config.get('max_response_bytes',2_000_000)
        if not _int_in(self.limit,1024,8_000_000):raise ValueError('Invalid provider response limit')
        if self.kind!='command':raise ValueError('Unknown provider kind')
        argv=config.get('argv')
        if not isinstance(argv,list) or not argv or any(not isinstance(x,str) or not x for x in argv):raise ValueError('Provider argv must be a nonempty string array; shell is never used')

    def identity(self):
        # Cache identity omits secret values; changing model/endpoint/adapter changes jobs.
        return {k:v for k,v in self.config.items() if k in {'kind','model','endpoint','argv','max_completion_tokens'}}

    def complete(self,messages,small=False,stage=None,reads=None,deep=False):
        # `reads`: a folder the assistant may read and search itself (read only); `deep`: it thinks as long as it needs
        # `stage`: what asks, so its use is counted under it in config['usage'] (eaos/core/usage.py), when the check names a file
        # A user-selected adapter receives JSON on stdin and emits JSON on stdout; it may work as long as it needs
        # while it writes anything (its progress on stderr counts): only silence for STUCK seconds ends it.
        # CWD is empty so repository code cannot be imported accidentally by the adapter.
        with tempfile.TemporaryDirectory(prefix='eaos-adapter-') as cwd, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                counted={'EAOS_MODEL_USAGE':str(self.config['usage']),'EAOS_MODEL_STAGE':stage or 'other'} if self.config.get('usage') else {}
                p=subprocess.Popen(self.config['argv'],stdin=subprocess.PIPE,stdout=out,stderr=err,cwd=cwd,shell=False,start_new_session=(os.name=='posix'),
                                 env={**os.environ,**counted})
                try:
                    with p.stdin:p.stdin.write(_request(messages,small,reads,deep))
                except BrokenPipeError:pass   # it ended before reading: its exit code says why
                wait(p,(out,err))
            except OSError:raise ValueError('Model adapter could not start; no raw stderr exposed') from None
            if p.returncode:raise ValueError('Model adapter exited unsuccessfully; no raw stderr exposed')
            out.seek(0);raw=out.read(self.limit+1)
        if len(raw)>self.limit:raise ValueError('Model adapter response exceeds limit')
        result=json.loads(raw)
        if not isinstance(result,dict):raise ValueError('Model adapter must return a JSON object')
        return result,{}
