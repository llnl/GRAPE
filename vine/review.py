import os
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
                        [--recurse]

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
        --recurse                   If set, adds a pull request for each modified submodule. The pull request for the
                                    outer level repo will have a description with links to the submodules' pull
                                    requests.

    """
    def __init__(self):
        super(Review, self).__init__()
        self._key = "review"
        self._section = "Code Reviews"

    def description(self):
        return "Prepare current topic branch for review"

    def execute(self, args):
        """
        A fair chunk of this stuff relies on stashy's wrapping of the STASH REST API, which is posted at
        https://developer.atlassian.com/static/rest/stash/2.12.1/stash-rest.html
        """
        name = args["--user"]
        if not name:
            name = utility.getUserName()
        print("Logging into RZStash")
        rz_atlassian = Atlassian.Atlassian(name)
        rz_stash = rz_atlassian.stash

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
        #Stash REST API for reviewer definition snippet:
        # "reviewers": [
        #     {
        #         "user": {
        #             "name": "charlie"
        #         }
        #     }
        #   ]
        # Which I interpret to mean the following:
        if reviewers:
            revList = []
            for r in reviewers.split(' '):
                revList.append(dict(user=dict(name=r)))
            reviewers = revList

        # default project (outer level project)
        config = grapeConfig.grapeConfig()
        project_name = config.get("project", "name")

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch()

        #ensure branch is pushed
        git.push("origin %s" % branch)
        #target branch for outer level repo
        target_branch = args["--target"]

        if not target_branch:
            prefix = branch.split('/')[0]
            target_branch = grapeConfig.parseConfigPairList(config.get("flow", "topicPrefixMappings"))[prefix]

        # subprojects
        submoduleLinks = []
        if args["--recurse"] or config.get("workspace", "manageSubmodules").lower() == 'true':

            cwd = utility.workspaceDir()
            os.chdir(cwd)
            submodules = git.getSubmodules()
            modifiedSubmodules = []
            for submodule in submodules:
                status = git.diff("--name-only %s %s -- %s" % (target_branch, branch, submodule), quiet=True)
                if status:
                    modifiedSubmodules.append(submodule)

            submoduleBranchMappings = grapeConfig.parseConfigPairList(
                config.get("workspace", "submoduleTopicPrefixMappings"))

            for submodule in modifiedSubmodules:
                url = git.config("--get submodule.%s.url" % submodule).split('/')
                proj = url[-2]
                repo_name = url[-1]
                repo_name = repo_name.split('.')[0]
                repo = rz_stash.projects[proj].repos[repo_name]
                prefix = branch.split('/')[0]
                sub_target_branch = submoduleBranchMappings[prefix]
                newRequest = postPullRequest(repo, title, branch, sub_target_branch, descr, reviewers, args)
                submoduleLinks.append(newRequest["links"]["self"][0]["href"])

        ## OUTER LEVEL REPO
        # load the repo level REST resource

        repo_name = config.get("repo", "name")
        repo = rz_stash.projects[project_name].repos[repo_name]

        if descr:
            descr += "\nThis pull request is related to the following submodules' pull requests:\n"
            for link in submoduleLinks:
                descr += '%s\n' % link
        postPullRequest(repo, title, branch, target_branch, descr, reviewers, args)

        return True


def postPullRequest(repo, title, branch, target_branch, descr, reviewers, args):
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
                request = repo.pull_requests.create(title, branch, target_branch,
                                                    description=descr, reviewers=reviewers)
                print("Pull request created.")
            except stashy.errors.GenericException as e:
                print("STASH: %s" % e.message)
                exit(1)
        else:
            print ("STASH: No pull request  from %s to %s to update" % (branch, target_branch))

    else:
        if not args["--add"]:
            # update the pull request
            print("Updating pull request")
            try:
                ver = requestData["version"]
                request = request.update(ver, title=title,  description=descr, reviewers=reviewers)
                print("Pull request updated.")
            except stashy.errors.GenericException as e:
                print("STASH: %s" % e.message)
                exit(1)

        else:
            print ("STASH: Pull request from %s to %s already exists, can't add a new one" %
                   (branch, target_branch))
    return request
