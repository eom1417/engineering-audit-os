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
"""
import json
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .. import __version__, artifact_contracts

PREFIX = 'studio-'
NO_STORE = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}


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
                                     'security': security, 'responses': {'200': {'description': 'server-sent events'}}}}}
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

    async def spec(request):
        return JSONResponse(document, headers=NO_STORE)

    return [Route('/api/session', session), Route('/api/manifest', manifest), Route('/api/sections/{name}', section),
            Route('/api/schemas/{name}', schema), Route('/api/openapi.json', spec)]
