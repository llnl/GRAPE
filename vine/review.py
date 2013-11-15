import option
import Atlassian
import utility
from grapeConfig import grapeConfig

# Prepare Feature Branch for review
class Review(option.Option):
    def __init__(self):
        self._key = "review"
        self._section = "Code Reviews"

    def description(self):
        return "Prepare current development branch for review"

    def execute(self):
        print("Logging into RZStash")
        name = utility.getUserName()
        rzAtlassian = Atlassian.Atlassian(name)
        rzStash = rzAtlassian.stash
        
        projectName = grapeConfig().get("project","name")
        repoName = grapeConfig().get("repo","name")
        repo = rzAtlassian.project( projectName ).repo( repoName )
        currentBranch = utility.GetCurrentBranch()

        # hack to work around possible corner case where utility.userInput would return
        # True / False if we happen to be working on a branch called 'y','Y',
        # 'N', or 'n'. Appending a space to the name should force utility.userInput
        # to return the actual string if the default is selected.
        if (currentBranch.lower() == 'n' or currentBranch.lower() == 'y'):
            currentBranch += " "

        branch = utility.userInput("Branch to Review:",currentBranch)
        targetBranch = utility.userInput("Destination branch?","develop")

        # check to see if pull request already exists for this
        # branch

        #pullRequests = repo.pull_requests.list()
        pullRequests = repo.pullrequests()

        count = 0
        for request in pullRequests:
            count += 1
            print(request.title(),request.fromRef(),request.toRef())
        if (count == 0):
            # safe to create a new pull request
            print("safe")
        else:
            print(count)

        return True
