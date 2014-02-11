import option
import utility

class Quit(option.Option):
    """
    grape q
    Quits grape. 

    Usage: grape-q 

    """
    def __init__(self):
        self._key = "q"
        self._section = "Other"

    def description(self):
        return "Quit."

    def execute(self,argv):
        args =utility.parseArgs(Quit.__doc__,argv)
        return True
