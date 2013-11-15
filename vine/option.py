class Option:
    def __init__(self):
        self._key = "UNSET KEY"
        self._section = "UNSET SECTION"

    def description(self):
        pass

    def execute(self):
        pass

    @property
    def key(self):
        return self._key

    @property
    def section(self):
        return self._section
