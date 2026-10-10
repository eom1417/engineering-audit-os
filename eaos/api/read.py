"""The read API, generated from the contract: one route per Studio section schema, and the OpenAPI document of them.

The set of sections is the set of `studio-<section>` schemas EAOS ships (schemas/artifacts/, eaos.artifact_contracts),
so a section added to the contract is served with no change here. A section answers with the file the exporter wrote
(studio/<section>.json) when the manifest lists it; otherwise 404 with the section's row of studio/coverage.json, so
the Studio shows the honest coverage state instead of a blank page. Nothing here writes.

    GET /api/session            the server's mode, the CSRF token, the project, the feed's source and its last id
    GET /api/manifest           studio/manifest.json
    GET /api/sections/<name>    studio/<name>.json, for every section of the contract
    GET /api/schemas/<name>     the section's JSON Schema
    GET /api/openapi.json       the OpenAPI 3.1 document of the routes above, each response the section's own schema
    GET /api/events             the live stream (server.py)
    GET /api/progress           the journey (eaos/guided.py:journey) and every flow's progress folded into one row per
                                stage (eaos/progress/fold.py), each stage placed on its map: the first paint of the
                                live map, before its events. A flow that has not run yet shows its declared stages
    GET /api/scan-progress      the check's flow alone, as /api/progress has it (the v1 route)
    GET /api/report-file?path=  a text file the check produced, by its path inside the report folder: nothing outside
                                it, no `..`, text types only, at most 2 MB, never rendered (text/plain)
    GET /api/screen?path=       a screen the safety flow recorded (a PNG under the runtime folder's
                                behavior-lock/snapshots), at most 2 MB
"""
import json
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .. import __version__, artifact_contracts, guided
from ..studio.pipeline import SAFE, layout

PREFIX = 'studio-'
NO_STORE = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
TEXT_TYPES = ('.md', '.json', '.jsonl', '.txt', '.csv', '.html', '.yaml', '.yml', '.sarif', '.xml', '.log')
MAX_FILE = 2 * 2 ** 20
SHOTS = 'behavior-lock/snapshots'


def section_schemas():
    """{section: schema} for every Studio section of the contract (the manifest is its own route)."""
    return {name[len(PREFIX):]: schema for name, schema in artifact_contracts.contracts().items()
            if name.startswith(PREFIX) and name != f'{PREFIX}manifest'}


def openapi(schemas=None):
    schemas = section_schemas() if schemas is None else schemas
    security = [{'launchToken': []}]
    def ok(ref, summary):
        return {'get': {'summary': summary, 'security': security,
                        'responses': {'200': {'description': 'the section', 'content': {'application/json': {'schema': {'$ref': ref}}}},
                                      '401': {'description': 'no or wrong launch token'},
                                      '404': {'description': 'not written by the last check; the body is its coverage row'}}}}
    paths = {'/api/manifest': ok('/api/schemas/manifest', 'The Studio manifest: every section with its sha256'),
             '/api/session': {'get': {'summary': 'The mode, the CSRF token, the project and the live feed', 'security': security,
                                      'responses': {'200': {'description': 'the session'}}}},
             '/api/events': {'get': {'summary': 'The live stream (text/event-stream); Last-Event-ID replays what was missed',
                                     'security': security, 'responses': {'200': {'description': 'server-sent events'}}}},
             '/api/progress': {'get': {'summary': 'The journey and every flow\'s progress, one row per stage with its place on its map',
                                       'security': security, 'responses': {'200': {'description': 'the folded progress'}}}},
             '/api/scan-progress': {'get': {'summary': "The check's progress, one row per stage with its place on the map",
                                            'security': security, 'responses': {'200': {'description': 'the folded progress'}}}},
             '/api/report-file': {'get': {'summary': 'A text file the check produced, by its path inside the report folder',
                                          'security': security,
                                          'parameters': [{'name': 'path', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}],
                                          'responses': {'200': {'description': 'the file, as text/plain'},
                                                        '400': {'description': 'the path leaves the report folder'},
                                                        '404': {'description': 'no such file'}, '413': {'description': 'over 2 MB'},
                                                        '415': {'description': 'not a text file'}}}},
             '/api/screen': {'get': {'summary': 'A screen the safety flow recorded, by its path inside the runtime folder',
                                     'security': security,
                                     'parameters': [{'name': 'path', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}],
                                     'responses': {'200': {'description': 'the screen, as image/png'},
                                                   '400': {'description': 'not a recorded screen'},
                                                   '404': {'description': 'no such screen'}, '413': {'description': 'over 2 MB'}}}}}
    for name, schema in sorted(schemas.items()):
        paths[f'/api/sections/{name}'] = ok(f'/api/schemas/{name}', schema.get('description') or name)
    return {'openapi': '3.1.0',
            'info': {'title': 'EAOS Studio read API', 'version': __version__,
                     'description': 'Read only, on 127.0.0.1, generated from schemas/artifacts/studio-*.schema.json.'},
            'paths': paths,
            'components': {'securitySchemes': {'launchToken': {'type': 'apiKey', 'in': 'header', 'name': 'X-EAOS-Token'}}}}


def _file(path):
    try: return Path(path).read_bytes()
    except OSError: return None


def routes(ctx):
    schemas = section_schemas()
    folder = Path(ctx.report) / 'studio'
    document = openapi(schemas)

    def listed():
        manifest = json.loads(_file(folder / 'manifest.json') or b'null')
        return {s.get('name') for s in (manifest or {}).get('sections') or [] if isinstance(s, dict)}

    def coverage_row(name):
        coverage = json.loads(_file(folder / 'coverage.json') or b'null') or {}
        return next((row for row in coverage.get('sections') or [] if isinstance(row, dict) and row.get('section') == name), None)

    async def session(request):
        manifest = json.loads(_file(folder / 'manifest.json') or b'null') or {}
        extra = await run_in_threadpool(ctx.session_extra) if ctx.session_extra else {}
        return JSONResponse({**(extra if isinstance(extra, dict) else {}), 'mode': 'live', 'version': __version__, 'csrf': ctx.keys.csrf,
                             'project': manifest.get('project') or {'name': ctx.name},
                             'feed': {'source': ctx.feed.source, 'last': ctx.feed.last_id()},
                             'sections': sorted(listed() - {None}), 'actions': ctx.actions_mounted}, headers=NO_STORE)

    async def manifest(request):
        body = _file(folder / 'manifest.json')
        if body is None:
            return JSONResponse({'error': 'empty', 'message': 'no check has written the Studio data yet'}, status_code=404, headers=NO_STORE)
        return Response(body, media_type='application/json', headers=NO_STORE)

    async def section(request):
        name = request.path_params['name']
        if name not in schemas:
            return JSONResponse({'error': 'unknown', 'message': f'{name} is not a section of the contract'}, status_code=404, headers=NO_STORE)
        body = _file(folder / f'{name}.json') if name in listed() or name == 'coverage' else None
        if body is None:
            return JSONResponse({'error': 'not_written', 'section': name, 'coverage': coverage_row(name)}, status_code=404, headers=NO_STORE)
        return Response(body, media_type='application/json', headers=NO_STORE)

    async def schema(request):
        name = request.path_params['name']
        found = schemas.get(name) or (artifact_contracts.contracts().get(f'{PREFIX}manifest') if name == 'manifest' else None)
        if found is None:
            return JSONResponse({'error': 'unknown'}, status_code=404, headers=NO_STORE)
        return JSONResponse(found, headers=NO_STORE)

    async def locale(request):
        if request.path_params['lang'] != 'en':
            return JSONResponse({'error': 'unknown_language'}, status_code=404, headers=NO_STORE)
        body = _file(folder / 'locale.json')
        if body is None:
            return JSONResponse({'error': 'not_written'}, status_code=404, headers=NO_STORE)
        return Response(body, media_type='application/json', headers=NO_STORE)

    async def spec(request):
        return JSONResponse(document, headers=NO_STORE)

    return [Route('/api/locales/{lang}', locale), Route('/api/session', session), Route('/api/manifest', manifest), Route('/api/sections/{name}', section),
            Route('/api/schemas/{name}', schema), Route('/api/openapi.json', spec)] + progress_routes(ctx)


def progress_routes(ctx):
    """The live map's routes: the progress of every flow, the check's alone, the files the check produced and the
    screens the safety flow recorded."""
    async def scan_progress(request):
        return JSONResponse(await run_in_threadpool(scan_state, ctx.report, ctx.feed.last_id()), headers=NO_STORE)

    async def all_progress(request):
        return JSONResponse(await run_in_threadpool(progress_state, ctx.report, ctx.state(), ctx.feed.last_id()), headers=NO_STORE)

    async def produced(request):
        return await run_in_threadpool(report_file, ctx.report, request.query_params.get('path') or '')

    async def screen(request):
        state = ctx.state()
        return await run_in_threadpool(screen_file, guided.runtime_of(state) if state else None, request.query_params.get('path') or '')

    return [Route('/api/scan-progress', scan_progress), Route('/api/progress', all_progress), Route('/api/report-file', produced),
            Route('/api/screen', screen)]


def declaration(flow):
    """The declared stages of a flow: the check's (eaos/pipeline/stages.py), a later step's FLOW, or the tools'."""
    from .. import behavior_lock, live_setup, toolchain, waves
    from ..pipeline.stages import STAGES
    if flow == toolchain.FLOW: return toolchain.stages(toolchain.ordered(toolchain.registry()['tools']))
    return {'check': STAGES, 'setup': live_setup.FLOW, 'safety': behavior_lock.FLOW, 'fix': waves.FLOW}[flow]


def flow_state(folder, flow='check'):
    """The folded progress of a flow's last (or running) run, each stage placed by the same pinned layered layout as the
    other maps (longest path, barycentre), its time left (eaos/progress/estimate.py), and whether a run that never
    ended is still heard from (eaos/progress/liveness.py): a stopped process makes it `interrupted`, 30 s without a
    line from a run that promised heartbeats makes it `stalled`, never a run that glows for ever. A flow that has not
    run yet is its declared stages, all waiting."""
    import time
    from .. import progress
    state = progress.fold(progress.read(folder, flow))
    if state['run'] is None: state = progress.declared(flow, progress.stage_rows(declaration(flow)))
    state['state'] = progress.judge(state, progress.heard_at(progress.path_for(folder, flow)), time.time(), progress.alive(state))
    places = layout([s['name'] for s in state['stages']], [(need, s['name']) for s in state['stages'] for need in s['requires']])
    for s in state['stages']:
        s['layer'], s['order'] = places.get(s['name'], (0, 0))
    state.pop('pid', None)
    state.pop('host', None)
    return {**state, 'estimate': progress.estimate(state, time.time())}


def scan_state(report, last_id=None):
    """`/api/scan-progress`: the check's flow, the server's clock for the page's timers and the feed's last id."""
    from .events import now
    return {**flow_state(report), 'now': now(), 'feed_last': last_id}


def progress_state(report, state, last_id=None):
    """`/api/progress`: the journey's four steps and every flow, the check from `report`, the others from the
    project's runtime folder, and the install of the tools with the ones the check needs on this project
    (`tools_needed`); the check and the tools alone when no project is known."""
    from .. import toolchain
    from .events import now
    flows = {'check': flow_state(report), toolchain.FLOW: flow_state(toolchain.home(), toolchain.FLOW)}
    if state: flows.update((flow, flow_state(guided.runtime_of(state), flow)) for flow in guided.FLOWS.values() if flow != 'check')
    needed = toolchain.needed(toolchain.project_files(state['project']) if state else ())
    return {'journey': guided.journey(state) if state else [], 'flows': flows, 'tools_needed': needed, 'now': now(), 'feed_last': last_id}


def report_file(report, path):
    """`/api/report-file`: a file inside the report folder (resolved, so no link leads out of it), a text type, at
    most MAX_FILE bytes, answered as text/plain so a page never renders it; a refusal says why."""
    target = _inside(report, path)
    if target is None: return _refuse(400, 'path', 'only a relative path inside the report folder is served')
    if not target.is_file(): return _refuse(404, 'not_found', 'no such file in the report')
    if target.suffix.lower() not in TEXT_TYPES: return _refuse(415, 'type', 'only text files are served')
    if target.stat().st_size > MAX_FILE: return _refuse(413, 'size', 'the file is larger than 2 MB')
    try: text = target.read_bytes().decode('utf-8')
    except UnicodeDecodeError: return _refuse(415, 'type', 'the file is not UTF-8 text')
    return Response(text, media_type='text/plain; charset=utf-8', headers={**NO_STORE, 'Content-Security-Policy': 'sandbox'})


def screen_file(runtime, path):
    """`/api/screen`: a screen the safety flow recorded (a step's `artifact`, relative to the runtime folder), a PNG
    inside its behavior-lock/snapshots folder, at most MAX_FILE bytes."""
    target = _inside(runtime, path) if runtime else None
    if target is None or target.suffix.lower() != '.png' or not target.is_relative_to((Path(runtime) / SHOTS).resolve()):
        return _refuse(400, 'path', 'only a recorded screen is served')
    if not target.is_file(): return _refuse(404, 'not_found', 'no such screen')
    if target.stat().st_size > MAX_FILE: return _refuse(413, 'size', 'the file is larger than 2 MB')
    return Response(target.read_bytes(), media_type='image/png', headers=NO_STORE)


def _inside(root, path):
    """The file `path` names inside `root`, resolved so no link leads out of it; None for any other path."""
    root = Path(root).resolve()
    target = (root / path).resolve() if path and '\0' not in path and SAFE.match(path) else None
    return target if target is not None and target.is_relative_to(root) else None


def _refuse(status, error, message):
    return JSONResponse({'error': error, 'message': message}, status_code=status, headers=NO_STORE)
