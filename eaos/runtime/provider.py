"""Explicit model adapters. No repository-controlled endpoints or executable commands."""
import json
import os
from pathlib import Path
import subprocess
import signal
import tempfile
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class Provider:
    def __init__(self,config):
        self.config=dict(config)
        self.kind=config.get('kind','chat_completions')
        self.timeout=config.get('timeout_seconds',120)
        if type(self.timeout) not in (int,float) or not 1<=self.timeout<=600:raise ValueError('Provider timeout must be 1–600 seconds')
        self.limit=config.get('max_response_bytes',2_000_000)
        if type(self.limit) is not int or not 1024<=self.limit<=8_000_000:raise ValueError('Invalid provider response limit')
        if self.kind=='chat_completions':
            self.endpoint=config.get('endpoint','https://api.openai.com/v1/chat/completions')
            url=urlparse(self.endpoint)
            if url.username or url.password or url.query or url.fragment:raise ValueError('Endpoint must not contain credentials, query or fragment')
            if url.scheme!='https' and not (url.scheme=='http' and url.hostname in {'127.0.0.1','localhost','::1'}):raise ValueError('Use HTTPS, or loopback HTTP for a local model')
            if not isinstance(config.get('model'),str) or not config['model']:raise ValueError('Model is required')
            key_name=config.get('api_key_env','OPENAI_API_KEY')
            self.key=os.environ.get(key_name,'') if key_name else ''
            if key_name and not self.key:raise ValueError('Configured API key environment variable is not set')
        elif self.kind=='command':
            argv=config.get('argv')
            if not isinstance(argv,list) or not argv or any(not isinstance(x,str) or not x for x in argv):raise ValueError('Provider argv must be a nonempty string array; shell is never used')
        else:raise ValueError('Unknown provider kind')

    def identity(self):
        # Cache identity omits secret values; changing model/endpoint/adapter changes jobs.
        return {k:v for k,v in self.config.items() if k not in {'api_key','token','password'}}

    def complete(self,messages):
        if self.kind=='command':
            # A user-selected adapter receives JSON on stdin and emits JSON on stdout.
            # CWD is empty so repository code cannot be imported accidentally by the adapter.
            with tempfile.TemporaryDirectory(prefix='eaos-adapter-') as cwd, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                try:
                    p=subprocess.Popen(self.config['argv'],stdin=subprocess.PIPE,stdout=out,stderr=err,cwd=cwd,shell=False,start_new_session=(os.name=='posix'))
                    try:p.communicate(json.dumps({'messages':messages}).encode(),timeout=self.timeout)
                    except subprocess.TimeoutExpired:
                        if os.name=='posix':os.killpg(p.pid,signal.SIGKILL)
                        else:p.kill()
                        p.wait()
                        raise ValueError('Model adapter timed out; no raw stderr exposed') from None
                except OSError:raise ValueError('Model adapter could not start; no raw stderr exposed') from None
                if p.returncode:raise ValueError('Model adapter exited unsuccessfully; no raw stderr exposed')
                out.seek(0);raw=out.read(self.limit+1)
            if len(raw)>self.limit:raise ValueError('Model adapter response exceeds limit')
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError('Model adapter must return a JSON object')
            return result,{}
        body={'model':self.config['model'],'messages':messages,'response_format':{'type':'json_object'}}
        if 'max_completion_tokens' in self.config:body['max_completion_tokens']=self.config['max_completion_tokens']
        headers={'Content-Type':'application/json'}
        if self.key:headers['Authorization']='Bearer '+self.key
        req=Request(self.endpoint,data=json.dumps(body).encode(),headers=headers,method='POST')
        try:
            with build_opener(NoRedirect()).open(req,timeout=self.timeout) as response:raw=response.read(self.limit+1)
        except (HTTPError,URLError,TimeoutError):raise ValueError('Model endpoint request failed; endpoint error body and credentials withheld') from None
        if len(raw)>self.limit:raise ValueError('Model response exceeds configured limit')
        data=json.loads(raw)
        try:
            choice=data['choices'][0]
            if choice.get('finish_reason')!='stop':raise ValueError('Model response incomplete/refused; not accepted')
            result=json.loads(choice['message']['content'])
        except (KeyError,IndexError,TypeError):raise ValueError('Unexpected model response shape') from None
        if not isinstance(result,dict):raise ValueError('Model output must be a JSON object')
        return result,data.get('usage',{})


def load_provider(path):
    config=json.loads(Path(path).read_text())
    if not isinstance(config,dict):raise ValueError('Provider config must be an object')
    if any(k in config for k in ['api_key','token','password']):raise ValueError('Use an environment variable for provider secrets, not config values')
    return Provider(config)
