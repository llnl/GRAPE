import option, utility

# option that creates a new feature branch
class Feature(option.Option):
    def __init__(self):
        self._key = "dev"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Create a new feature development branch"

    def execute(self):
        utility.createBranch("develop","feature")
        return True
