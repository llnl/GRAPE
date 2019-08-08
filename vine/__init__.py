import importlib
import os
import sys

try:
    import stashy.stashy
except ModuleNotFoundError:
    __helpers_module = importlib.import_module('.', 'stashy.stashy.helpers')
    sys.modules['stashy.helpers'] = __helpers_module
    __errors_module = importlib.import_module('.', 'stashy.stashy.errors')
    sys.modules['stashy.errors'] = __errors_module

grape_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(grape_dir, 'keyring'))
import entrypoints
try:
    import stashy.stashy
except ModuleNotFoundError:
    pass
