import option
import Atlassian
import utility
import grapeConfig
import grapeGit as git


# Prepare Feature Branch for review
class Review(option.Option):
    """
    grape review
    Usage: grape-review [--descr=<file> | -m <description>]
                        [--user=<userName> ]
                        [--reviewers=<userNames>]
                        [--source=<topicBranch>]
                        [--target=<publicBranch>]

    Options:
        --descr=<file>              A file containing the detailed description of work done on <topicBranch>.
        -m <description>            The description of work done on <topicBranch>
        --user=<userName>           Your user name.
        --reviewers=<userNames>     A space-separate list of reviewers for <topicBranch>
        --source=<topicBranch>      The branch to review.
        --target=<publicBranch>     The branch to publish <topicBranch> to.

    """
    def __init__(self):
        super(Review, self).__init__()
        self._key = "review"
        self._section = "Code Reviews"


    def description(self):
        return "Prepare current topic branch for review"

    def execute(self, args):

        name = args["--user"]
        if not name:
            name = utility.getUserName()
        print("Logging into RZStash")
        rz_atlassian = Atlassian.Atlassian(name)
        rz_stash = rz_atlassian.stash


        config = grapeConfig.grapeConfig()
        project_name = config.get("project", "name")
        repo_name = config.get("repo", "name")
        repo = rz_stash.projects[project_name].repos[repo_name]
        current_branch = git.currentBranch()
        branch = utility.userInput("Branch to Review:", current_branch)
        prefix = branch.split('/')[0]
        dest_branch = grapeConfig.parseConfigPairList(config.get("flow", "topicPrefixMappings"))[prefix]
        target_branch = utility.userInput("Destination branch?", dest_branch)

        # check to see if pull request already exists for this
        # branch

        pull_requests = repo.pull_requests.list()
        print pull_requests
        
        count = 0
        for request in pull_requests:
            count += 1
            print request
            exit(0)
            print(request["title"], request["fromRef"]["id"], request["toRef"]["id"])
        if count == 0:
            # safe to create a new pull request
            print("safe")
            title = "title"
            description = "Default description"
            reviewers = []
            repo.pull_requests.create(title, branch, target_branch, description=description, reviewers=reviewers)

        else:
            print "not safe to create a pull request"

        return True
