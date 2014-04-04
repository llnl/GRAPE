import option
import Atlassian
import utility
import grapeConfig
import grapeGit as git
import stashy.stashy as stashy


# Prepare Feature Branch for review
class Review(option.Option):
    """
    grape review
    Usage: grape-review [--update | --add]
                        [--title=<title>]
                        [--descr=<file> | -m <description>]
                        [--user=<userName> ]
                        [--reviewers=<userNames>]
                        [--source=<topicBranch>]
                        [--target=<publicBranch>]

    Options:
        --update                    Update an existing pull request with a new description, set of reviewers, etc.
                                    This is the default behavior if a pull request already exists for <topicBranch>
                                    targeting <publicBranch>. If --update is set, and an open pull request doesn't
                                    exist, an error will be generated.
        --add                       Add a new pull request. Default behavior if a pull request doesn't exist for
                                    <topicBranch> targeting <publicBranch>. If a pull request already exists and --add
                                    is set, an error will be generated.
        --title=<title>             The pull request tile.
        --descr=<file>              A file containing the detailed description of work done on <topicBranch>.
        -m <description>            The pull request description.
        --user=<userName>           Your Stash user name.
        --reviewers=<userNames>     A space-separate list of reviewers for <topicBranch>
        --source=<topicBranch>      The branch to review. Defaults to current branch.
        --target=<publicBranch>     The branch to publish <topicBranch> to.
                                    Defaults to .grapeconfig.topicPrefixMappings[topicBranchPrefix].

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

        # load the repo level REST resource
        config = grapeConfig.grapeConfig()
        project_name = config.get("project", "name")
        repo_name = config.get("repo", "name")
        repo = rz_stash.projects[project_name].repos[repo_name]

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch()
        target_branch = args["--target"]
        if not target_branch:
            prefix = branch.split('/')[0]
            target_branch = grapeConfig.parseConfigPairList(config.get("flow", "topicPrefixMappings"))[prefix]


        # determine pull request title
        title = args["--title"]

        # determine pull request description
        descr = args["-m"]
        if not descr:
            descrFile = args["--descr"]
            if descrFile:
                with open(descrFile) as f:
                    descr = f.readall()

        # determine pull request reviewers
        reviewers = args["--reviewers"]

        # get the open pull requests outgoing from our public branch
        print("Gathering active pull requests on %s" % branch)
        pull_requests = repo.pull_requests.all(direction="OUTGOING", at="refs/heads/%s" % branch)

        # check to see if pull request already exists for this branch
        request = None
        requestData = None
        for rqst in pull_requests:
            print rqst["toRef"]["id"]
            if rqst["toRef"]["id"] == "refs/heads/%s" % target_branch:
                request = repo.pull_requests[str(rqst["id"])]
                requestData = rqst
                break

        if not request:
            if not args["--update"]:
                # add a new pull request
                if not title:
                    title = branch
                try:
                    print("Creating new pull request. ")
                    repo.pull_requests.create(title, branch, target_branch, description=descr, reviewers=reviewers)
                    print("Pull request created.")
                except stashy.errors.GenericException as e:
                    print("STASH: %s" % e.msg)
                    exit(int(e.msg.split(':')[0]))
            else:
                print ("STASH: No pull request  from %s to %s to update" % (branch, target_branch))

        else:
            if not args["--add"]:
                # update the pull request
                print("Updating pull request")
                print(title, descr, reviewers)
                try:
                    ver = requestData["version"]
                    print reviewers
                    revList = []
                    for r in reviewers.split(' '):
                        revList.append(dict(user=dict(name=r)))

                    request.update(ver, title=title,  description=descr, reviewers=revList)
                except stashy.errors.GenericException as e:
                    print("STASH: %s" % e.message)
                    exit(1)

                print("Pull request updated")
            else:
                print ("STASH: Pull request from %s to %s already exists, can't add a new one" % (branch, target_branch))

        return True
