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
                        [--stashURL=<url>]
                        [--verifySSL=<bool>]
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
        --stashURL=<url>            The stash url, e.g. https://rzlc.llnl.gov/stash. 
                                    [default: .grapeconfig.project.stashURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --project=<prj>             The project key part of the stash url, e.g. the "GRP" in
                                    https://rzlc.llnl.gov/stash/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repo name part of the stash url, e.g. the "grape" in
                                    https://rzlc.llnl.gov/stash/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.repo.name]
        --recurse                   If set, adds a pull request for each modified submodule and nested subproject.
                                    The pull request for the outer level repo will have a description with links to the 
                                    submodules' pull requests.
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
            
        utility.printMsg("Logging onto %s" % args["--stashURL"])
        if args["--test"]:
            stash = Atlassian.TestAtlassian(name)
        else:
            verify = True if args["--verifySSL"].lower() == "true" else False
            stash = Atlassian.Atlassian(name, url=args["--stashURL"], verify=verify)

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
        utility.printMsg("Pushing %s to stash..." % branch)
        git.push("origin %s" % branch, quiet=quiet)
        #target branch for outer level repo
        target_branch = args["--target"]

        if not target_branch:
            target_branch = config.getPublicBranchFor(branch)

        cwd = utility.workspaceDir()
        os.chdir(cwd)

        # submodules
        submoduleLinks = []
        if args["--recurse"] or config.get("workspace", "manageSubmodules").lower() == 'true':
            
            modifiedSubmodules = git.getModifiedSubmodules(target_branch, branch)
            submoduleBranchMappings = config.getMapping("workspace", "submoduleTopicPrefixMappings")

            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                # push branch
                os.chdir(submodule)
                utility.printMsg("Pushing %s to stash..." % branch)
                git.push("origin %s" % branch, quiet=quiet)
                os.chdir(cwd)
                # url is typically  [type]://some.base/url/stash/.../PROJ/REPO.git
                url = git.config("--get submodule.%s.url" % submodule).split('/')
                proj = url[-2]
                repo_name = url[-1]

                # strip off the .git extension
                repo_name = '.'.join(repo_name.split('.')[:-1])
                repo = stash.project(proj).repo(repo_name)
                prefix = branch.split('/')[0]
                sub_target_branch = submoduleBranchMappings[prefix]
                newRequest = postPullRequest(repo, title, branch, sub_target_branch, descr, reviewers, args)
                submoduleLinks.append(newRequest.link())
        
        #nested subprojects
        nestedProjects = grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojects(target_branch)
        nestedProjectPrefixes = grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojectPrefixes(target_branch)
        nestedProjectURLs = [config.get("nested-%s" % proj, "url") for proj in nestedProjects]
        for proj, url in zip(nestedProjectPrefixes, nestedProjectURLs):
            os.chdir(proj)
            git.push("origin %s" % branch, quiet=quiet)
            os.chdir(cwd)
            url = utility.parseSubprojectRemoteURL(url)

            urlTokens = url.split('/')
            proj = urlTokens[-2]
            repo_name = urlTokens[-1]           
            # strip off the .git extension
            repo_name = '.'.join(repo_name.split('.')[:-1])
            repo = stash.project(proj).repo(repo_name)
            
            newRequest = postPullRequest(repo, title, branch, target_branch,descr, reviewers, args)

            submoduleLinks.append(newRequest.link())
            
            
        ## OUTER LEVEL REPO
        # load the repo level REST resource

        repo_name = args["--repo"]
        repo = stash.project(project_name).repo(repo_name)
        if not quiet:
            utility.printMsg("Posting pull request to %s,%s" % (project_name, repo_name))
        request = postPullRequest(repo, title, branch, target_branch, descr, reviewers, args)
        updatedDescription = request.description()
        for link in submoduleLinks:
            if link not in updatedDescription: 
                updatedDescription+="\nThis pull request is related to the pull request at: %s" % link
        if updatedDescription != request.description(): 
            request = postPullRequest(repo, title, branch, target_branch, 
                                     updatedDescription, 
                                     reviewers, 
                                     args)
        
            
       
        if not quiet:
            utility.printMsg("Request generated/updated: %s" % request)
        return True

    def setDefaultConfig(self, config):
        config.ensureSection("project")
        config.set("project", "stashURL", "https://rzlc.llnl.gov/stash")
        config.set("project", "verifySSL", "True")
        config.set("project", "name", "My unnamed project")
        pass


def postPullRequest(repo, title, branch, target_branch, descr, reviewers, args):
    # get the open pull requests outgoing from our public branch
    quiet = not args["-v"]
    utility.printMsg("Gathering active pull requests on %s" % branch)
    pull_requests = repo.pullRequests(direction="OUTGOING", at="refs/heads/%s" % branch, state=args["--state"])

    # check to see if pull request already exists for this branch
    request = None
    for rqst in pull_requests:
        if rqst.toRef() == target_branch:
            request = rqst
            break

    if not request:
        if not args["--update"]:
            # add a new pull request
            if not title:
                title = branch
            try:
                utility.printMsg("Creating new pull request titled '%s' \n for branch %s targeting %s. " %
                      (title, branch, target_branch))
                if not quiet:
                    utility.printMsg("descr: %s" % descr)
                    utility.printMsg("reviewers: %s" % reviewers)
                request = repo.createPullRequest(title, branch, target_branch, description=descr, reviewers=reviewers)
                url = request.link()
                utility.printMsg("Pull request created at %s ." % url)
            except stashy.errors.GenericException as e:
                print("STASH: %s" % e.message)
                exit(1)
        else:
            utility.printMsg("No pull request  from %s to %s to update" % (branch, target_branch))

    else:
        if not args["--add"]:
            # update the pull request
            utility.printMsg("Updating pull request...")
            try:

                if reviewers:
                    
                    if args["--prepend"] or args["--append"]:
                        revList = [r[0] for r in request.reviewers()]
                    else:
                        revList = []
                    reviewers += revList
                if not reviewers: 
                    reviewers = [r[0] for r in request.reviewers()]
                if not quiet:
                    utility.printMsg("reviewer list is: %s" % reviewers)
                ver = request.version()

                if title is not None and (args["--prepend"] or args["--append"]):
                    currentTitle = request.title()
                    if args["--prepend"]:
                        title = title+currentTitle
                    elif args["--append"]:
                        title = currentTitle+title
                if descr is not None and (args["--prepend"] or args["--append"]):
                    currentDescription = request.description()
                    if args["--prepend"]:
                        descr = descr + "\n" + currentDescription
                    elif args["--append"]:
                        descr = currentDescription + "\n" + descr


                if title is not None or descr is not None or reviewers:
                    if not quiet:
                        utility.printMsg("updating request with title=%s, description=%s, reviewers=%s" % (title, descr, reviewers))
                    request = request.update(ver, title=title,  description=descr, reviewers=reviewers)
                    url = request.link()
                    utility.printMsg("Pull request updated at %s ." % url)
                else:
                    url = request.link()
                    utility.printMsg("Pull request unchanged at %s ." % url)
            except stashy.errors.GenericException as e:
                print("STASH: %s" % e.message)
                exit(1)

        else:
            print ("STASH: Pull request from %s to %s already exists, can't add a new one" %
                   (branch, target_branch))
            
    return request

if __name__ == "__main__":
    import grapeMenu
    grapeMenu.menu().applyMenuChoice("review",[])