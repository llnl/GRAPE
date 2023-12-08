"""
Slightly modified version of:
https://sourcemaking.com/design_patterns/singleton/python/1
"""
class Singleton(type):
    """Ensures a class has only one instance."""

    def __init__(cls, name, bases, attrs, **kwargs):
        super(Singleton, cls).__init__(name, bases, attrs)
        cls._instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance
