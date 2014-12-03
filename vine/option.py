import abc


class Option(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self._key = "UNSET KEY"
        self._section = "UNSET SECTION"
        self._config = None

    @abc.abstractmethod
    def description(self):
        pass

    @abc.abstractmethod
    def execute(self, args):
        pass

    @abc.abstractmethod
    def setDefaultConfig(self, config):
        pass
    
    @property
    def key(self):
        return self._key

    @property
    def section(self):
        return self._section
