"""An error a caller steps over on purpose, named and logged at debug level so it is never silent."""
import logging

LOG = logging.getLogger('eaos')


def noted(why, error):
    """Log `error`, which the caller steps over because of `why`; the caller then goes on as it chooses."""
    LOG.debug('%s: %r', why, error)
