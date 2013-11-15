from grapeConfig import grapeConfig

class Clone(Option):
    """Clones the ALE3D repo into a new local repo"""
    key = "clone"
    section = " GETTING STARTED "
    def Description(self):
        name = grapeConfig().get("repo","name")
        return "Clone the %s repo and initialize your git config" % name

    def Execute(self):
        user = utility.GetUserName()

        remotePath = utility.userInput("Enter Remote Repo address:",
                               "https://%s@rzlc.llnl.gov/stash/scm/ale/ale3d.git" % user)

        destPath = utility.userInput("Enter destination directory:",os.path.join(os.getcwd(),"ale3d"))

        print("calling git clone %s %s" % (remotePath,destPath))
        print("you may need to authenticate using your CRYPTOCARD")
        repo = git.Repo(destPath)
        try:
            repo = repo.clone(remotePath)
        except git.GitCommandError as error:
            print("Error: %s: git clone failed", remotePath)
            print(error)
            return False

        return True
