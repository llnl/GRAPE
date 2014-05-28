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
                        [--state=<openMergedDeclined>]
                        [--project=<prj>]
                        [--repo=<repo>]
                        [--recurse]
                        [-v]
                        [--test]
                        [--prepend | --append]

    Options:
        --update                    Update an existing pull request with a new description, set of reviewers, etc.
                                    This is the default behavior if a pull request already exists for <topicBranch>
                                    targeting <publicBranch>. If --update is set, and an open pull request doesn't
                                    exist, an error will be generated.
        --add                       Add a new pull request. Default behavior if a pull request doesn't exist for
                                    <topicBranch> targeting <publicBranch>. If a pull request already exists and --add
                                    is set, an error will be generated.
        --title=<title>             The pull request`s title.
        --descr=<file>              A file containing the detailed description of work done on <topicBranch>.
        -m <description>            The pull request description.
        --user=<userName>           Your Stash user name.
        --reviewers=<userNames>     A space-separate list of reviewers for <topicBranch>
        --source=<topicBranch>      The branch to review. Defaults to current branch.
        --target=<publicBranch>     The branch to publish <topicBranch> to.
                                    Defaults to .grapeconfig.topicPrefixMappings[topicBranchPrefix].
        --state=<state>             The state of the pull request to update. Valid values are open, merged, and
                                    declined.
                                    [default: open]
        --project=<prj>             The project key part of the stash url, e.g. the "GRP" in
                                    https://rzlc.llnl.gov/stash/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repo name part of the stash url, e.g. the "grape" in
                                    https://rzlc.llnl.gov/stash/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.repo.name]
        --recurse                   If set, adds a pull request for each modified submodule. The pull request for the
                                    outer level repo will have a description with links to the submodules' pull
                                    requests.
        -v                          Be more verbose with git commands.
        --test                      Uses a dummy version of stashy that requires no communication to an actual Stash
                                    server.
        --prepend                   For reviewers, title,  and description updates, prepend <userNames>, <title>,  and
                                    <description> to the existing title / description instead of replacing it.
        --append                    For reviewers, title,  and description updates, append <userNames>, <title>,  and
                                    <description> to the existing title / description instead of replacing it.


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
        config = grapeConfig.grapeConfig()
        quiet = not args["-v"]
        name = args["--user"]
        if not name:
            name = utility.getUserName()
        print("Logging into RZStash")
        if args["--test"]:
            rz_atlassian = Atlassian.TestAtlassian(name)
        else:
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
                    descr = f.readlines()
                descr = ''.join(descr)
        # determine pull request reviewers
        reviewers = args["--reviewers"]
        if reviewers:
            reviewers = reviewers.split()

        # default project (outer level project)
        project_name = args["--project"]

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch()

        #ensure branch is pushed
        git.push("origin %s" % branch)
        #target branch for outer level repo
        target_branch = args["--target"]

        if not target_branch:
            target_branch = config.getPublicBranchFor(branch)

        # subprojects
        submoduleLinks = []
        if args["--recurse"] or config.get("workspace", "manageSubmodules").lower() == 'true':
            cwd = git.baseDir(quiet=quiet)
            os.chdir(cwd)
            modifiedSubmodules = git.getModifiedSubmodules(target_branch, branch)
            submoduleBranchMappings = config.getMapping("workspace", "submoduleTopicPrefixMappings")

            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                # push branch
                os.chdir(submodule)
                git.push("origin %s" % branch)
                os.chdir(cwd)
                # url is typically  [type]://some.base/url/stash/.../PROJ/REPO.git
                url = git.config("--get submodule.%s.url" % submodule).split('/')
                proj = url[-2]
                repo_name = url[-1]
                # strip off the .git extension
                repo_name = repo_name.split('.')[0]
                repo = rz_stash.projects[proj].repos[repo_name]
                prefix = branch.split('/')[0]
                sub_target_branch = submoduleBranchMappings[prefix]
                newRequest = postPullRequest(repo, title, branch, sub_target_branch, descr, reviewers, args)
                submoduleLinks.append(newRequest["links"]["self"][0]["href"])

        ## OUTER LEVEL REPO
        # load the repo level REST resource

        repo_name = args["--repo"]
        repo = rz_stash.projects[project_name].repos[repo_name]
        if not quiet:
            print("Posting pull request to %s,%s" % (project_name, repo_name))
        if descr and submoduleLinks and not (args["--append"] or args["--prepend"]):
            descr += "\nThis pull request is related to the following submodules' pull requests:\n"
            for link in submoduleLinks:
                descr += '%s\n' % link
        request = postPullRequest(repo, title, branch, target_branch, descr, reviewers, args)
        if not quiet:
            print("Request generated/updated: ", request)
        return True

    def setDefaultConfig(self, config):
        pass


def postPullRequest(repo, title, branch, target_branch, descr, reviewers, args):
    # get the open pull requests outgoing from our public branch
    quiet = not args["-v"]
    print("Gathering active pull requests on %s" % branch)
    pull_requests = repo.pull_requests.all(direction="OUTGOING", at="refs/heads/%s" % branch, state=args["--state"])

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
                print("Creating new pull request titled '%s' \n for branch %s targeting %s. " %
                      (title, branch, target_branch))
                if not quiet:
                    print("descr: %s" % descr)
                    print("reviewers: %s" % reviewers)
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
                    if args["--prepend"] or args["--append"]:
                        revList = requestData["reviewers"]
                    else:
                        revList = []
                    for r in reviewers:
                        revList.append(dict(user=dict(name=r)))
                    reviewers = revList
                if not reviewers: 
                    reviewers = requestData["reviewers"]
                ver = requestData["version"]

                if title is not None and (args["--prepend"] or args["--append"]):
                    currentTitle = requestData["title"]
                    if args["--prepend"]:
                        title = title+currentTitle
                    elif args["--append"]:
                        title = currentTitle+title
                if descr is not None and (args["--prepend"] or args["--append"]):
                    if "description" in requestData:
                        currentDescription = requestData["description"]
                        if args["--prepend"]:
                            descr = descr + "\n" + currentDescription
                        elif args["--append"]:
                            descr = currentDescription + "\n" + descr


                if title is not None or descr is not None or reviewers is not None:
                    if not quiet:
                        print("upating request with title=%s, description=%s, reviewers=%s" % (title, descr, reviewers))
                        print(requestData)
                        print(reviewers is None)
                    request = request.update(ver, title=title,  description=descr, reviewers=reviewers)
                else:
                    request = requestData
                print("Pull request updated.")
            except stashy.errors.GenericException as e:
                print("STASH: %s" % e.message)
                exit(1)

        else:
            print ("STASH: Pull request from %s to %s already exists, can't add a new one" %
                   (branch, target_branch))
    return request
