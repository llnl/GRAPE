import importlib
import sys

try:
    import stashy.stashy
except ModuleNotFoundError:
    __helpers_module = importlib.import_module('.', 'stashy.stashy.helpers')
    sys.modules['stashy.helpers'] = __helpers_module
    __errors_module = importlib.import_module('.', 'stashy.stashy.errors')
    sys.modules['stashy.errors'] = __errors_module

