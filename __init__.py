import os
import sys
# Explicit import path to resolve "stashy" import issue.
grapedir = os.path.dirname(os.path.realpath(__file__))
stashy_path = os.path.join(grapedir, 'stashy')
if stashy_path not in sys.path:
    sys.path.insert(0, stashy_path)
# Explicit import path to resolve "keyring" import issue.
keyring_dir = os.path.join(grapedir, 'keyring')
if keyring_dir not in sys.path:
    sys.path.insert(0, keyring_dir)
