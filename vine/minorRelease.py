import option, utility

# option that creates a new minor Release Branch
class MinorRelease(option.Option):
    def __init__(self):
        self._key = "bugfix"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Create a new bugfix branch (for fixing nightly/build failures)"

    def execute(self):
#       branchPoint = utility.userInput("Where do you want this Release to branch from?","FIRSTFAIL")
        branchPoint = "develop"
        utility.createBranch(branchPoint,"bugfix")
        return True

