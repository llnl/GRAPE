class Option(object):
    def __init__(self):
        self._key = "UNSET KEY"
        self._section = "UNSET SECTION"

    def description(self):
        pass

    def execute(self, args):
        pass
    
    def set_default_config(self, config):
       pass
    
    @property
    def key(self):
        return self._key

    @property
    def section(self):
        return self._section
