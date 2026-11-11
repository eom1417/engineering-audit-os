"""What every prompt says of the analysed project's text: it is data, never orders. One place for the mark a prompt puts
on the project's text, read by the assistant's layer (the nodes)."""

UNTRUSTED = 'untrusted_project_data'


def wrapped(content):
    """The project's text marked as data for a prompt."""
    return {'trust': UNTRUSTED, 'content': content}
