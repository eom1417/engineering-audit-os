"""Every HTTP read EAOS makes goes through `opened`: urllib also opens file:// and ftp:// addresses, and an address
built from a record, a setting or a project's own configuration could then read a file of this computer instead
(CWE-22, CWE-939: bandit and semgrep agreed on each of the eleven calls in EAOS's check of itself, 2026-10-24).
Only http and https pass, and a file for what is checked by its pinned sha256 before use (`files`)."""
import urllib.request
from urllib.parse import urlsplit


def opened(url, headers=None, timeout=30, files=False):
    """The response of a GET of an http(s) address or Request, to use as a context manager; ValueError otherwise.
    `files`: a pinned release, checked by its sha256 before use, may also come from a folder (an offline mirror)."""
    request = url if isinstance(url, urllib.request.Request) else urllib.request.Request(url, headers=headers or {})
    if urlsplit(request.full_url).scheme not in ('http', 'https', *(('file',) if files else ())): raise ValueError(f'not an http(s) address: {request.full_url}')
    return urllib.request.urlopen(request, timeout=timeout)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected -- the scheme is checked above (nosec B310)
