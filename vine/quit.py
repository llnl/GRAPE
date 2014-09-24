import option


class Quit(option.Option):
    """
    grape q
    Quits grape. 

    Usage: grape-q 

    """
    def __init__(self):
        super(Quit, self).__init__()
        self._key = "q"
        self._section = "Other"

    def description(self):
        return "Quit."

    def execute(self, args):
        return True

    def setDefaultConfig(self, config):
        pass
