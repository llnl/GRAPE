"""
Simple filesystem based keyring implementation.

This module provides a minimal password storage mechanism using a local
INI style configuration file located at:

    ~/.grape/keyring_pass.cfg

Passwords are stored per service and username:
- Each service is represented as a section in the config file.
- Each username is an option within that section.
- The corresponding value is the stored password in plain text.

Security considerations
-----------------------
- The keyring file is created (or updated) with file permissions restricted
  to user read/write only (mode 0o600 via USER_READ_WRITE).
- This protects the file from other users on the same system, but the
  contents are not encrypted.
- This implementation is suitable for simple local use cases where
  filesystem permissions are considered sufficient protection.

Provided functionality
----------------------
- KEYRING_FILE
    Path to the keyring configuration file in the user's home directory.
- USER_READ_WRITE
    File permission mode used to secure the keyring file.
- set_password(service, username, password)
    Store or update a password for a given service and username in the
    keyring file.
- get_password(service, username)
    Retrieve the password for a given service and username, or return
    None if no entry exists.

Usage example
-------------
    from vine import GrapeKeyring

    GrapeKeyring.set_password("github", "alice", "s3cr3t")
    token = GrapeKeyring.get_password("github", "alice")

Limitations
-----------
- No encryption, only filesystem permission based protection is provided.
- No support for concurrent writes from multiple processes.
"""

from configparser import ConfigParser
from pathlib import Path


#: Path to the local keyring configuration file used to store passwords securely.
#: The file is created in the user's home directory under the hidden ".grape"
#: folder with the name "keyring_pass.cfg".
KEYRING_FILE = Path.home() / '.grape' / 'keyring_pass.cfg'

#: File permission mode that allows read and write access for the owner only.
#: This is typically used to protect sensitive files, such as keyring data,
#: so that no other users on the system can read or modify them.
USER_READ_WRITE = 0o600


def get_password(service, username):
    """
    Retrieve a stored password for a given service and username.

    This function looks up credentials in the keyring configuration file
    located at `KEYRING_FILE`. The configuration file is expected to use
    INI-style sections, where each section name corresponds to a service,
    and each option within that section is a username whose value is the
    associated password.

    Parameters
    ----------
    service : str
        The name of the service whose credentials are being requested.
        This maps to a section name in the config file.
    username : str
        The username within the specified service section whose password
        should be retrieved.

    Returns
    -------
    Optional[str]
        The stored password if it exists in the configuration file,
        otherwise `None` if the file does not exist, the section is
        missing, or the username is not found.

    Notes
    -----
    No exception is raised if the keyring file is missing or does not
    contain the requested credentials; in these cases the function simply
    returns `None`.
    """
    # Get config parser
    config = ConfigParser()

    # Return early if file does not exist
    if not KEYRING_FILE.exists():
        return None

    # Load existing config
    config.read(KEYRING_FILE, encoding='utf-8')

    # Return password if found
    if config.has_section(service) and config.has_option(service, username):
        return config.get(service, username)

    # Return None if not found
    return None


def set_password(service, username, password):
    """
    Store or update a password for a given service and username.

    This function maintains credentials in an INI-style keyring file at
    `KEYRING_FILE`. Each service is represented as a section, and each
    username within that section is stored as an option whose value is the
    associated password.

    If the keyring file already exists, its contents are loaded and updated
    in place. If it does not exist, the parent directory is created as needed
    and a new file is written. After writing, the file permissions are
    restricted to user read/write only, using `USER_READ_WRITE` (typically
    `0o600`).

    Parameters
    ----------
    service : str
        The name of the service for which the password is being stored.
        This corresponds to a section name in the keyring file.
    username : str
        The username whose password should be stored or updated under
        the given service.
    password : str
        The password to store for the specified service and username.

    Returns
    -------
    None
        This function does not return a value. It writes the updated
        configuration to `KEYRING_FILE` on disk.

    Notes
    -----
    - Existing entries for the same `service` and `username` are overwritten.
    - The parent directory of `KEYRING_FILE` is created if it does not exist.
    - File permissions are explicitly set after each write to ensure that
      only the current user can read or modify the keyring file.
    """
    # Get config parser
    config = ConfigParser()

    # Load existing config if present
    if KEYRING_FILE.exists():
        config.read(KEYRING_FILE, encoding='utf-8')

    # Ensure section exists
    if not config.has_section(service):
         config.add_section(service)

    # Set/update value
    config.set(service, username, password)

    # Ensure parent dir exists
    KEYRING_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write back to disk
    with KEYRING_FILE.open("w", encoding="utf-8") as config_file:
        config.write(config_file)

    # Ensure proper file permissions (user read/write only)
    KEYRING_FILE.chmod(USER_READ_WRITE)

