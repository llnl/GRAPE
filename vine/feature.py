import option, utility

# option that creates a new feature branch
class Feature(option.Option):
    key = "dev"
    section = "GITFLOW TASKS"

    def Description(self):
        return "Create a new feature development branch"

    def Execute(self):
        utility.createBranch("develop","feature")
        return True
