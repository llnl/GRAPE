__version__ = "0.1"

from .client import Stash

def connect(url, username =None, password = None):
    """
    Connect to a Stash instance given a username and password.

    This is only recommended via SSL.
    """
    return Stash(url, username, password)

__all__ = ['connect']
