import option

class Quit(option.Option):
    def __init__(self):
        self._key = "q"
        self._section = "Other"

    def description(self):
        return "Quit."

    def execute(self):
        return True
