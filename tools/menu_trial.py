"""A trial of the menu (eaos/menu.py): the real Claude Code and Codex, each in its own terminal screen (tmux), on a project
EAOS has checked. The person types only /eaos (Codex: $eaos), sees the first page of the menu, and picks "done and coming
next" by its number; the assistant does it.

    python tools/menu_trial.py calisthenics-coach ~/projects/calisthenics-coach

What is read is the screen the person sees (tmux capture-pane) and the EAOS journal (every tool call, with the assistant
that made it). Claude Code must show the page as a choice (its arrow-key list), Codex as a numbered list; both with
exactly the labels of menu()'s first page, in order, the recommended one first; then the option chosen must reach the
tools its `do` names. Both assistants have the EAOS tools only. Claude Code runs in its default configuration, signed in
and past its first-run screens; Codex likewise.

Writes $EAOS_MEASURE/menu/<name>/trial.json:
  {project, at, eaos, menu: {ar, en}, claude: {...}, codex: {...}}, each assistant
  {shown, as_choice, labels_in_order, recommended_first, chose, tools_after, did_it, screen}
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import dev_paths

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MEASURE = dev_paths.MEASURE / 'menu'
CHOSEN = 'tasks'                       # on the first page of a checked project, and read-only
DOES = {'plan', 'status'}              # the tools its `do` names
NESTED = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_CHILD_SESSION', 'CLAUDE_CODE_SESSION_ID', 'CLAUDE_PID',
          'CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN', 'CLAUDE_CODE_SESSION_ATTENDED', 'CLAUDE_CONFIG_DIR')


def tmux(*args):
    return subprocess.run(['tmux', *args], capture_output=True, text=True).stdout


def screen(name, history=200):
    return tmux('capture-pane', '-pt', name, '-S', f'-{history}')


def type_in(name, text, enter=True):
    tmux('send-keys', '-t', name, '-l', text)
    time.sleep(1)
    if enter: tmux('send-keys', '-t', name, 'Enter')


def until(name, test, seconds):
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(3)
        if test(screen(name)): return True
    return False


def busy(text):
    return 'esc to interrupt' in text or 'Working (' in text


def journal(state, since):
    from eaos import handover
    return [e for e in handover.entries(state, 400) if e.get('at', '') >= since]


def judged(text, page):
    """The screen against the menu's first page: every label, in order, the recommended one first."""
    for lang, options in page.items():
        labels = [o['label'] for o in options]
        at = [text.find(label.split(' (')[0]) for label in labels]
        if all(i >= 0 for i in at):
            return {'language': lang, 'labels_in_order': at == sorted(at),
                    'recommended_first': labels[0] in text and ('موصى به' in labels[0] or 'Recommended' in labels[0]),
                    'number': next(n + 1 for n, o in enumerate(options) if o['id'] == CHOSEN)}
    return None


def run(assistant, name, project, page, launch, open_menu, as_choice):
    from eaos import guided
    state = guided.load(project)
    since = datetime.now(timezone.utc).isoformat(timespec='seconds')
    tmux('kill-session', '-t', name)
    tmux('new-session', '-d', '-s', name, '-x', '160', '-y', '60', '-c', str(project), launch)
    result = {'shown': False}
    try:
        if not until(name, lambda s: 'for shortcuts' in s or '❯' in s or 'Trust' in s or 'trust' in s, 90):
            return {**result, 'error': 'the assistant did not start', 'screen': screen(name)[-3000:]}
        if re.search(r'[Tt]rust (this folder|the files)', screen(name)):   # a folder opened for the first time
            tmux('send-keys', '-t', name, 'Enter')
            until(name, lambda s: 'for shortcuts' in s or '❯ ' in s, 60)
        time.sleep(6)                                   # MCP servers connect
        open_menu(name)
        until(name, lambda s: not busy(s) and ('Enter to select' in s or re.search(r'\n\s*4\. ', s)), 240)
        text = screen(name)
        seen = judged(text, page)
        result.update(shown=bool(seen), as_choice=as_choice(text), **(seen or {}),
                      menu_called=any(e.get('tool') == 'menu' for e in journal(state, since)))
        if not seen:
            return {**result, 'screen': text[-4000:]}
        type_in(name, str(seen['number']), enter=assistant == 'codex')
        if assistant == 'claude': tmux('send-keys', '-t', name, 'Enter')
        time.sleep(10)
        until(name, lambda s: not busy(s), 300)
        after = [e.get('tool') for e in journal(state, since) if e.get('tool') != 'menu']
        result.update(chose=CHOSEN, tools_after=after, did_it=bool(DOES & set(after)), screen=screen(name)[-4000:])
        return result
    finally:
        tmux('kill-session', '-t', name)


def main(name, project):
    from eaos import __version__, agent_tools, build_info, menu
    project = Path(project).resolve()
    if not shutil.which('tmux'): raise SystemExit('tmux is needed: the trial reads the screens the person sees')
    env = os.environ.get('EAOS_HOME')
    state = agent_tools.status(str(project))
    if not state.get('checked'): raise SystemExit(f'{project} has not been checked: run the audit first (the menu of a checked project is the one tried)')
    page = {lang: menu.menu(str(project), lang)['pages'][0] for lang in ('ar', 'en')}
    if CHOSEN not in [o['id'] for o in page['ar']]: raise SystemExit(f'"{CHOSEN}" is not on the first page here: {page["ar"]}')
    py, extra = sys.executable, {'PYTHONPATH': str(ROOT), **({'EAOS_HOME': env} if env else {}),
                                 **({'EAOS_ENGINE_TOOLS': os.environ['EAOS_ENGINE_TOOLS']} if os.environ.get('EAOS_ENGINE_TOOLS') else {})}
    folder = MEASURE / name
    folder.mkdir(parents=True, exist_ok=True)

    config = folder / 'mcp.json'
    config.write_text(json.dumps({'mcpServers': {'eaos': {'command': py, 'args': ['-m', 'eaos', 'mcp'],
                                                          'env': {**extra, 'EAOS_ASSISTANT': 'Claude Code'}}}}))
    skill = Path.home() / '.claude/skills/eaos/SKILL.md'      # what `eaos assistant install` puts there, this version
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text((ROOT / 'eaos/templates/assistants/claude-skill.md').read_text(encoding='utf-8'), encoding='utf-8')
    claude = run('claude', 'eaos-menu-claude', project, page,
                 ' '.join(['env', *[f'-u {v}' for v in NESTED], 'claude', '--mcp-config', str(config), '--strict-mcp-config',
                           '--allowedTools', 'mcp__eaos']),
                 lambda n: type_in(n, '/eaos'),
                 lambda s: 'Enter to select' in s)

    from eaos.assistant_setup import codex_skill
    codex_home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')
    (codex_home / 'skills/eaos').mkdir(parents=True, exist_ok=True)
    (codex_home / 'skills/eaos/SKILL.md').write_text(codex_skill(), encoding='utf-8')
    env_toml = ', '.join(f'{k}="{v}"' for k, v in {**extra, 'EAOS_ASSISTANT': 'Codex'}.items())
    server = (f'mcp_servers.eaos={{command="{py}", args=["-m", "eaos", "mcp"], startup_timeout_sec=60, tool_timeout_sec=120, '
              f'env={{{env_toml}}}}}')
    codex = run('codex', 'eaos-menu-codex', project, page,
                f"codex -c '{server}' -c 'approval_policy=\"never\"' -c 'sandbox_mode=\"read-only\"' -c 'check_for_update_on_startup=false'",
                lambda n: (type_in(n, '$eaos', enter=False), time.sleep(2), tmux('send-keys', '-t', n, 'Enter'),
                           time.sleep(1), tmux('send-keys', '-t', n, 'Enter')),
                lambda s: bool(re.search(r'\n\s*1\. .*\n(.*\n)*?\s*4\. ', s)))

    record = {'project': name, 'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'eaos': {'version': __version__, 'commit': build_info.commit()},
              'menu': {lang: [o['label'] for o in options] for lang, options in page.items()}, 'claude': claude, 'codex': codex}
    (folder / 'trial.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
    for who in ('claude', 'codex'):
        r = record[who]
        print(who, {k: r.get(k) for k in ('shown', 'as_choice', 'labels_in_order', 'recommended_first', 'menu_called', 'did_it', 'tools_after', 'error')})
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
