import option
import Atlassian
import utility

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
        print "Projects:", rzAtlassian.projectlist()

        repo = rzAtlassian.project('ALE').repo('ale3d')
        for pull in repo.pullrequests():
            if pull.author() == name:
                print " my review     ", pull.title()
            else:
                print " other review  ", pull.title()

        if 1:
            return

        # none of this stuff works.

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
        pullRequests = repo.pull_requests.all()

        count = 0
        for request in pullRequests:
            count += 1
            print(request["title"],request["fromRef"]['id'],request["toRef"]['id'])
        if (count == 0):
            # safe to create a new pull request
            print("safe")
        else:
            print(count)

        return True
