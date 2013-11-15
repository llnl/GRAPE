import option, utility

# option that creates a new minor Release Branch
class MinorRelease(option.Option):
    key = "minor"
    section = "GITFLOW TASKS"

    def Description(self):
        return "Create a new minor Release branch (for fixing nightly/build failures)"

    def Execute(self):
        branchPoint = utility.userInput("Where do you want this Release to branch from?","FIRSTFAIL")
        utility.createBranch(branchPoint,"minor")
        return True

