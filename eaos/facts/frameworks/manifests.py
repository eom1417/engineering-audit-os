"""Entry points declared by manifests and container images rather than by code."""
import json
import re

FILENAMES = ('package.json', 'pyproject.toml', 'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', 'Makefile')
SCRIPT = re.compile(r'^(?P<name>[\w.-]+)\s*=\s*[\'"](?P<target>[^\'"]+)[\'"]', re.M)
DOCKER = re.compile(r'^\s*(?P<kind>CMD|ENTRYPOINT)\s+(?P<value>.+)$', re.M | re.I)
MAKE = re.compile(r'^(?P<name>[A-Za-z][\w.-]*):(?!=)', re.M)


def detect(context):
    name = context.rel.split('/')[-1]
    found = []
    if name == 'package.json':
        try: manifest = json.loads(context.text)
        except ValueError: return []
        for script in sorted(manifest.get('scripts', {}) if isinstance(manifest.get('scripts'), dict) else {}):
            found.append({'surface': 'cli', 'route': 'npm run ' + script, 'http_method': None, 'handler': None,
                          'framework': 'npm_script', 'line': 1})
    elif name == 'pyproject.toml':
        block = context.text.split('[project.scripts]')
        if len(block) > 1:
            for match in SCRIPT.finditer(block[1].split('\n[')[0]):
                found.append({'surface': 'cli', 'route': match.group('name'), 'http_method': None,
                              'handler': match.group('target'), 'framework': 'console_script',
                              'line': context.line_of(context.text.index(match.group(0)))})
    elif name == 'Dockerfile':
        for match in DOCKER.finditer(context.text):
            found.append({'surface': 'container', 'route': match.group('value').strip(), 'http_method': None,
                          'handler': None, 'framework': 'docker_' + match.group('kind').lower(),
                          'line': context.line_of(match.start())})
    elif name == 'Makefile':
        for match in MAKE.finditer(context.text):
            if match.group('name') in {'.PHONY'}: continue
            found.append({'surface': 'cli', 'route': 'make ' + match.group('name'), 'http_method': None,
                          'handler': None, 'framework': 'make', 'line': context.line_of(match.start())})
    return found
