"""Whether a started production build serves the program or only its pages: a load on a server of pages alone would
measure the wrong program (eaos/live/app/setup.py refuses it before the baseline is accepted)."""
import urllib.error

from ...core.system.web import opened

NOT_FOUND = b'404'


class PagesOnly(RuntimeError):
    """The started app serves its pages only: a load on it would not measure the program."""


def _answer(url):
    """The body a GET answers; NOT_FOUND when the route is not served; None when it answers otherwise
    (a sign-in asked)."""
    try:
        with opened(url, timeout=10) as response: return response.read()
    except urllib.error.HTTPError as answer: return NOT_FOUND if answer.code == 404 else None
    except (OSError, ValueError): return None


def server_routes(report):
    """The GET server routes (not pages) a load can call without a fixture: what the program serves beside its pages."""
    from ..behavior.specs import PARAM, features_of, kind_of, path_of, surfaces
    known = surfaces(report)
    return sorted({path for feature in features_of(report)
                   for surface in feature.get('surfaces') or [] if kind_of(surface, known)[0] == 'http'
                   and (path := _loadable(surface, known, kind_of, path_of, PARAM))})


def _loadable(surface, known, kind_of, path_of, param):
    """The path of a page or GET route that needs no fixture; None for any other surface."""
    kind, method, _ = kind_of(surface, known)
    path = path_of(surface) if surface != '*' else None
    # A hash route (/#/x) is drawn by the browser: a request only ever reaches the page that serves it.
    return (path if kind in ('page', 'http') and method == 'GET' and path and '#' not in path
            and not param.search(path) else None)


def refuse_a_page_server(report, base):
    """The load must hit the program, not a server of its pages alone: when most server routes of the code answer
    with the very page `/` answers (a front-end server's fallback), or are not found, the baseline would measure the
    wrong program. A route a preview server did not find, counted as served, would let it pass the setup."""
    if not report: return
    routes, page = [r for r in server_routes(report) if r != '/'], _answer(f'{base}/')
    if page is not None and sum(_answer(f'{base}{route}') in (page, NOT_FOUND) for route in routes) * 2 > len(routes):
        raise PagesOnly(f'the started app serves only its pages: its {len(routes)} server routes '
                        f'({", ".join(routes[:3])}...) answer with the page itself, so a load on it would not '
                        'measure the program. Propose a baseline whose start runs the real server, serving the built '
                        'pages and these routes (run_try with mode="baseline", its "app" the folder that server starts '
                        'in, and "headers" the token its routes need).')
