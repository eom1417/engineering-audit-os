"""Entry points declared by manifests and container images rather than by code.

A task-runner script (a package.json script, a Makefile target) is an entry point into the system
when it runs a program of the repository: `node scripts/ship.mjs`, `python tools/check.py`,
`python -m pkg.tool`, directly or through another script it calls. Its handler is then that file,
so the flow tracer starts there. A script that only runs an external tool (`vite build`, `tsc`,
`vitest run`, `ruff check .`) names no program of the repository: it is reported as a
`tool_command`, a command the project declares, not a way into its code.
"""
import json
import posixpath
import re
import shlex

FILENAMES = ('package.json', 'pyproject.toml', 'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', 'Makefile')
SCRIPT = re.compile(r'^(?P<name>[\w.-]+)\s*=\s*[\'"](?P<target>[^\'"]+)[\'"]', re.M)
DOCKER = re.compile(r'^[ \t]*(?P<kind>CMD|ENTRYPOINT)\s+(?P<value>.+)$', re.M | re.I)
MAKE = re.compile(r'^(?P<name>[A-Za-z][\w.-]*):(?!=)', re.M)

# The files a runner executes. A file handed to any other tool (`eslint src/a.ts`) is read, not run.
PROGRAM_SUFFIXES = ('.py', '.js', '.mjs', '.cjs', '.ts', '.mts', '.cts', '.jsx', '.tsx', '.sh')
RUNNERS = {'node', 'nodejs', 'tsx', 'ts-node', 'ts-node-esm', 'esno', 'esrun', 'vite-node', 'babel-node', 'bun', 'deno',
           'python', 'python3', 'py', 'pypy3', 'sh', 'bash', 'zsh'}
RUNNER_VARIABLE = re.compile(r'^\$[({](?P<name>[A-Z_]*(?:PYTHON|NODE)[A-Z_]*)[)}]$')
PACKAGE_MANAGERS = {'npm', 'pnpm', 'yarn', 'bun'}
SHELL_SEPARATOR = re.compile(r'\s*(?:&&|\|\||;|\|(?!\|)|(?<![<>&])&(?!&))\s*')
ENV_ASSIGNMENT = re.compile(r'^[A-Za-z_]\w*=')


def _words(command):
    try: return shlex.split(command)
    except ValueError: return command.split()


def _program(words, base):
    """The repository file a command runs, or None when it runs only an external tool."""
    if _launcher(words): words = _launcher(words)
    first = words[0]
    runner = posixpath.basename(first)
    if runner in RUNNERS or RUNNER_VARIABLE.match(first) or re.fullmatch(r'python3?\.\d+', runner):
        return _runner_program(runner, words[1:], base)
    # A command that is itself a file of the repository: ./scripts/build.sh, bin/tool.py.
    if '/' in first and first.endswith(PROGRAM_SUFFIXES): return _inside(base, first)
    return None


def _runner_program(runner, rest, base):
    """The file a runner is given (`node a.js`, `python -m pkg.tool`), or None when its first argument is no program."""
    if runner in ('deno', 'bun') and rest[:1] == ['run']: rest = rest[1:]
    for index, word in enumerate(rest):
        if word == '-m' and index + 1 < len(rest):
            return _inside(base, rest[index + 1].replace('.', '/') + '.py')
        if word.startswith('-'): continue
        return _inside(base, word) if word.endswith(PROGRAM_SUFFIXES) else None
    return None


def _inside(base, path):
    """`path` relative to the manifest's folder, as a repository path; None when it leaves the repository."""
    joined = posixpath.normpath(posixpath.join(base, path)) if base else posixpath.normpath(path)
    return None if joined.startswith('../') or joined == '..' or posixpath.isabs(joined) else joined


def _launcher(words):
    """The command a package launcher runs (`npx tsx a.ts` runs `tsx a.ts`), or None for any other command."""
    word = posixpath.basename(words[0])
    if word in {'npx', 'pnpx', 'bunx'} or (word in {'pnpm', 'yarn'} and words[1:2] == ['dlx']):
        rest = words[2:] if words[1:2] == ['dlx'] else words[1:]
        while rest and rest[0].startswith('-'): rest = rest[1:]
        return rest or None
    return None


def _tool(words):
    return posixpath.basename((_launcher(words) or words)[0])


def classify(commands, references, base):
    """Follow a script's commands (and the scripts they call) to the first repository program.

    `commands(name)` gives a script's command strings; `references(words)` gives the script a command
    calls (`npm run lint`, `make test`) or None. Returns (handler, tools): the program it runs and the
    external tools it invokes on the way.
    """
    tools, seen = [], set()

    def walk(name):
        if name in seen: return None
        seen.add(name)
        for command in commands(name):
            for segment in SHELL_SEPARATOR.split(command.strip()):
                found = step(_command_words(segment))
                if found: return found
        return None

    def step(words):
        """The program one command runs, itself or through the script it calls; an external tool it runs is noted."""
        if not words: return None
        called = references(words)
        if called is not None: return walk(called)
        found = _program(words, base)
        if found: return found
        tool = _tool(words)
        if tool not in tools: tools.append(tool)
        return None

    return walk, tools


def _command_words(segment):
    """A command's words without the variables and wrappers before it (`FOO=1 cross-env node a.js`)."""
    words = [word for word in _words(segment) if word]
    while words and (ENV_ASSIGNMENT.match(words[0]) or words[0] in {'env', 'cross-env', 'exec', 'time'}):
        words = words[1:]
    return words


def _npm_reference(scripts):
    def reference(words):
        manager = posixpath.basename(words[0])
        if manager not in PACKAGE_MANAGERS: return None
        rest = [word for word in words[1:] if not word.startswith('-')]
        name = _npm_script(manager, rest) if rest else None
        return name if name in scripts else None
    return reference


def _npm_script(manager, rest):
    """The script a package-manager command runs (`npm run x`, `npm test`, `yarn x`), or None."""
    if rest[0] in {'run', 'run-script'} and len(rest) > 1: return rest[1]
    if rest[0] in {'test', 't', 'start', 'stop', 'restart'}: return 'test' if rest[0] == 't' else rest[0]
    return rest[0] if manager in {'yarn', 'pnpm', 'bun'} else None


def _make_targets(text):
    """Each target with its prerequisites and recipe lines, in file order."""
    targets, current = {}, None
    for number, line in enumerate(text.split('\n'), start=1):
        if line.startswith('\t') and current is not None:
            targets[current]['recipe'].append(line.strip().lstrip('@-+').strip())
            continue
        match = MAKE.match(line)
        if not match:
            if line.strip() and not line.lstrip().startswith('#'): current = None
            continue
        current = match.group('name')
        rest = line[match.end():].split('#')[0]
        prerequisites, _, inline = rest.partition(';')
        row = targets.setdefault(current, {'line': number, 'prerequisites': [], 'recipe': []})
        row['prerequisites'] += prerequisites.replace('|', ' ').split()
        if inline.strip(): row['recipe'].append(inline.strip())
    return targets


def _make_reference(targets):
    def reference(words):
        if words[0] not in {'make', '$(MAKE)', '${MAKE}'}: return None
        rest = words[1:]
        return rest[0] if len(rest) == 1 and rest[0] in targets else None
    return reference


def _entry(route, framework, line, handler, tools):
    """One script: an entry point when it runs a repository program, a tool command when it does not."""
    if handler:
        return {'surface': 'cli', 'route': route, 'http_method': None, 'handler': handler, 'framework': framework,
                'line': line}
    return {'kind': 'tool_command', 'surface': 'cli', 'route': route, 'http_method': None, 'handler': None,
            'framework': framework, 'line': line, 'tools': tools}


def detect(context):
    read = READERS.get(context.rel.split('/')[-1])
    return read(context, posixpath.dirname(context.rel)) if read else []


def _package_json(context, base):
    """Every npm script, in name order."""
    try: manifest = json.loads(context.text)
    except ValueError: return []
    scripts = manifest.get('scripts') if isinstance(manifest.get('scripts'), dict) else {}
    scripts = {key: value for key, value in scripts.items() if isinstance(value, str)}
    found = []
    for script in sorted(scripts):
        walk, tools = classify(lambda key: [scripts[key]], _npm_reference(scripts), base)
        found.append(_entry('npm run ' + script, 'npm_script', 1, walk(script), tools))
    return found


def _pyproject(context, base):
    """The console scripts of [project.scripts]."""
    block = context.text.split('[project.scripts]')
    if len(block) < 2: return []
    return [{'surface': 'cli', 'route': match.group('name'), 'http_method': None,
             'handler': match.group('target'), 'framework': 'console_script',
             'line': context.line_of(context.text.index(match.group(0)))}
            for match in SCRIPT.finditer(block[1].split('\n[')[0])]


def _dockerfile(context, base):
    """Each CMD and ENTRYPOINT of the image."""
    return [{'surface': 'container', 'route': match.group('value').strip(), 'http_method': None,
             'handler': None, 'framework': 'docker_' + match.group('kind').lower(),
             'line': context.line_of(match.start())} for match in DOCKER.finditer(context.text)]


def _makefile(context, base):
    """Each make target but .PHONY, followed through the targets and commands it runs."""
    targets = _make_targets(context.text)

    def commands(key):
        row = targets.get(key) or {'prerequisites': [], 'recipe': []}
        return ['make ' + item for item in row['prerequisites'] if item in targets] + row['recipe']

    found = []
    for target, row in targets.items():
        if target in {'.PHONY'}: continue
        walk, tools = classify(commands, _make_reference(targets), base)
        handler = walk(target)
        if not handler and not tools:
            # A target with nothing to run here (a file rule, a variable-only line): no evidence either way.
            found.append({'surface': 'cli', 'route': 'make ' + target, 'http_method': None, 'handler': None,
                          'framework': 'make', 'line': row['line']})
            continue
        found.append(_entry('make ' + target, 'make', row['line'], handler, tools))
    return found


# The manifests read here, by file name, and the reader of each.
READERS = {'package.json': _package_json, 'pyproject.toml': _pyproject, 'Dockerfile': _dockerfile, 'Makefile': _makefile}
