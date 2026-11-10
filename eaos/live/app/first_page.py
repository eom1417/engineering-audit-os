"""What the first page a run opened says about the app behind it: an empty, no-data state (the run lacks a value), a
plain listing of files (no app at all), and the assistant's answer that the project has no interface to start."""
import re


class NoInterface(Exception):
    """The project has no interface a browser can open (a library, a command-line tool, a mobile app): its own tests
    and build are what keep a change safe, never pictures of a stand-in page."""


# A server's own listing of a folder: Python's http.server, nginx and Apache autoindex, `npx serve`.
LISTING = re.compile(r'^\s*(Directory listing for /|Index of /|Files within /)', re.I)


def listing(page):
    """Why the first page is no app: it is a plain listing of the project's files that a static server made, not a
    page of the project; '' otherwise."""
    if not LISTING.search(page.get('text') or ''): return ''
    raise NoInterface('the page is a listing of the project\'s files made by a static file server, not a page of the project')


def declined(proposal):
    """The assistant answered that nothing in the project opens in a browser (`no_interface`, and why): asked again it
    would make one up (Python's file server on the project folder), so its answer is taken."""
    if str(proposal.get('no_interface') or '').strip(): raise NoInterface(str(proposal['no_interface']).strip()[:400])


# The words of a page that shows nothing yet: no data, no report, an empty list.
SHORT = 40                      # words: a longer first page is the app itself, never an empty state
EMPTY = re.compile(r'\b(no (data|reports?|results?|items?|records?|content|entries)\b|nothing (here|to show|yet)|is empty\b|'
                   r'(not|none) (found|available|loaded) yet)|لا (يوجد|توجد|شيء|بيانات)|فارغ', re.I)


def empty_state(page, unset):
    """Why the first page is no working app although it answered: it shows an empty, "no data" state while the run
    has no value for a name the app reads, so every screen would be pictured empty. '' otherwise: a page of more than
    SHORT words is the app, whatever "no ... yet" it shows."""
    text = ' '.join((page.get('text') or '').split())
    if text.startswith(('{', '[')): return ''          # an API's answer, not an empty screen
    if not unset or len(text.split()) > SHORT or not (EMPTY.search(text) or len(text.split()) < 3): return ''
    return ('the first page shows an empty, no-data state while the app runs without a value for: ' + ', '.join(unset[:12])
            + '. Give it one (often a folder or address the app reads its data from); the page says: ' + (text[:400] or '(nothing)'))
