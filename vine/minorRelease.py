import option, utility

# option that creates a new minor Release Branch
class MinorRelease(option.Option):
    def __init__(self):
        self._key = "minor"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Create a new minor Release branch (for fixing nightly/build failures)"

    def execute(self):
        branchPoint = utility.userInput("Where do you want this Release to branch from?","FIRSTFAIL")
        utility.createBranch(branchPoint,"minor")
        return True

