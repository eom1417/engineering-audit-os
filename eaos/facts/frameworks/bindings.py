"""The names a file binds, as the files that import it reach them: by the importing path's last part (its stem). Shared by
the data-access detectors (http_access, supabase_access); a stem too common to carry a binding is left out."""

# Stems too common to carry a binding: importing any `types` or `index` says nothing about a client.
GENERIC_STEMS = {'index', 'types', 'utils', 'constants', 'config', 'helpers'}


def stem(path):
    return path.rstrip('/').rsplit('/', 1)[-1].split('.')[0]


def by_stem(bound):
    """{file stem: the names the files of that stem bind}, generic stems left out."""
    found = {}
    for rel, names in bound.items():
        if names and stem(rel) not in GENERIC_STEMS: found.setdefault(stem(rel), set()).update(names)
    return found
