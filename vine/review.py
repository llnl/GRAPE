import os
import option
import re
import Atlassian
import urllib
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
                        [--bitbucketURL=<url>]
                        [--verifySSL=<bool>]
                        [--project=<prj>]
                        [--repo=<repo>]
                        [--recurse]
                        [--norecurse]
                        [--test]
                        [--prepend | --append]
                        [--subprojectsOnly]

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
        --user=<userName>           Your Bitbucket user name.
        --reviewers=<userNames>     A space-separate list of reviewers for <topicBranch>
        --source=<topicBranch>      The branch to review. Defaults to current branch.
        --target=<publicBranch>     The branch to publish <topicBranch> to.
                                    Defaults to .grapeconfig.topicPrefixMappings[topicBranchPrefix].
        --state=<state>             The state of the pull request to update. Valid values are open, merged, and
                                    declined.
                                    [default: open]
        --bitbucketURL=<url>            The bitbucket url, e.g. https://rzlc.llnl.gov/bitbucket. 
                                    [default: .grapeconfig.project.stashURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --project=<prj>             The project key part of the bitbucket url, e.g. the "GRP" in
                                    https://rzlc.llnl.gov/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repo name part of the bitbucket url, e.g. the "grape" in
                                    https://rzlc.llnl.gov/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.repo.name]
        --recurse                   If set, adds a pull request for each modified submodule and nested subproject.
                                    The pull request for the outer level repo will have a description with links to the 
                                    submodules' pull requests. On by default if grapeConfig.workspace.manageSubmodules
                                    is set to true. 
        --norecurse                 Disables adding pull requests to submodules and subprojects. 
        --test                      Uses a dummy version of stashy that requires no communication to an actual Bitbucket 
                                    server.
        --prepend                   For reviewers, title,  and description updates, prepend <userNames>, <title>,  and
                                    <description> to the existing title / description instead of replacing it.
        --append                    For reviewers, title,  and description updates, append <userNames>, <title>,  and
                                    <description> to the existing reviewers, title, or description instead of replacing it.
        --subprojectsOnly           As a work around to when you've only touched a subproject, this will prevent errors
                                    arising
 


    """
    def __init__(self):
        super(Review, self).__init__()
        self._key = "review"
        self._section = "Code Reviews"

    def description(self):
        return "Prepare current topic branch for review"

    def parseDescriptionArgs(self, args):
        descr = args["-m"]
        if not descr:
            descrFile = args["--descr"]
            if descrFile:
                with open(descrFile) as f:
                    descr = f.readlines()
                descr = ''.join(descr)
                for encoding in ['utf-8', 'windows-1252']:
                    try:
                        descr = descr.decode(encoding).encode('ascii','ignore')
                    except:
                        pass
        else:
            # Convert \n to a newline, but only if it is not escaped
            descr = re.sub('([^\\\\])\\\\n', r'\1\n', descr)
            # Remove one backslash from any escaped \n's.
            descr = re.sub('\\\\\\\\n', "\\\\n", descr)
        return descr
    
    def parseReviewerArgs(self, args):
        reviewers = args["--reviewers"]
        if reviewers is not None:
            reviewers = reviewers.split()
        return reviewers
        

    def execute(self, args):
        """
        A fair chunk of this stuff relies on stashy's wrapping of the STASH REST API, which is posted at
        https://developer.atlassian.com/static/rest/stash/2.12.1/stash-rest.html
        """
        config = grapeConfig.grapeConfig()
        name = args["--user"]
        if not name:
            name = utility.getUserName()
            
        utility.printMsg("Logging onto %s" % args["--bitbucketURL"])
        if args["--test"]:
            bitbucket = Atlassian.TestAtlassian(name)
        else:
            verify = True if args["--verifySSL"].lower() == "true" else False
            bitbucket = Atlassian.Atlassian(name, url=args["--bitbucketURL"], verify=verify)

        # default project (outer level project)
        project_name = args["--project"]
        
        # default repo (outer level repo)
        repo_name = args["--repo"]

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch()

        # make sure we are in the outer level repo before we push
        wsDir = utility.workspaceDir()
        os.chdir(wsDir)

        #ensure branch is pushed
        utility.printMsg("Pushing %s to bitbucket..." % branch)
        git.push("origin %s" % branch)
        #target branch for outer level repo
        target_branch = args["--target"]
        if not target_branch:
            target_branch = config.getPublicBranchFor(branch)        
        # load pull request from Bitbucket if it already exists
        wsRepo =  bitbucket.project(project_name).repo(repo_name)
        existingOuterLevelRequest = getReposPullRequest(wsRepo, branch, target_branch, args)  

        # determine pull request title
        title = args["--title"]
        if existingOuterLevelRequest is not None and not title:
            title = existingOuterLevelRequest.title()

        
        #determine pull request URL
        outerLevelURL = None
        if existingOuterLevelRequest:
            outerLevelURL = existingOuterLevelRequest.link()
        
        # determine pull request description
        descr = self.parseDescriptionArgs(args)

        if not descr and existingOuterLevelRequest:
            descr = existingOuterLevelRequest.description()

    
        # determine pull request reviewers
        reviewers = self.parseReviewerArgs(args)
        if reviewers is None and existingOuterLevelRequest is not None:
            reviewers = [r[0] for r in existingOuterLevelRequest.reviewers()]

        # if we're in append mode, only append what was asked for:
        if args["--append"] or args["--prepend"]:
            title = args["--title"]
            descr = self.parseDescriptionArgs(args)
            reviewers = self.parseReviewerArgs(args)
            
        ##  Submodule Repos
        missing = utility.getModifiedInactiveSubmodules(target_branch, branch)
        if missing:
            utility.printMsg("The following submodules that you've modified are not currently present in your workspace.\n"
                             "You should activate them using grape uv  and then call grape review again. If you haven't modified "
                             "these submodules, you may need to do a grape md to proceed.")
            utility.printMsg(','.join(missing))
            return False        
        pullRequestLinks = {}
        if not args["--norecurse"] and (args["--recurse"] or config.getboolean("workspace", "manageSubmodules")):
            
            modifiedSubmodules = git.getModifiedSubmodules(target_branch, branch)
            submoduleBranchMappings = config.getMapping("workspace", "submoduleTopicPrefixMappings")
                        
            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                # push branch
                os.chdir(submodule)
                utility.printMsg("Pushing %s to bitbucket..." % branch)
                git.push("origin %s" % branch)
                os.chdir(wsDir)
                repo = bitbucket.repoFromWorkspaceRepoPath(submodule, 
                                                         isSubmodule=True)
                # determine branch prefix
                prefix = branch.split('/')[0]
                sub_target_branch = submoduleBranchMappings[prefix]
                
                prevSubDescr = getReposPullRequestDescription(repo, branch, 
                                                             sub_target_branch, 
                                                             args)
                #amend the subproject pull request description with the link to the outer pull request
                subDescr = addLinkToDescription(descr, outerLevelURL, True)
                if args["--prepend"] or args["--append"]:
                    subDescr = descr
                newRequest = postPullRequest(repo, title, branch, sub_target_branch, subDescr, reviewers, args)
                if newRequest:
                    pullRequestLinks[newRequest.link()] = True
                else:
                    # if a pull request could not be generated, just add a link to browse the branch
                    pullRequestLinks["%s%s/browse?at=%s" % (bitbucket.rzbitbucketURL,
                                                            repo.repo.url(),
                                                            urllib.quote_plus("refs/heads/%s" % branch))] = False
        
        ## NESTED SUBPROJECT REPOS 
        nestedProjects = grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojects(target_branch)
        nestedProjectPrefixes = grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojectPrefixes(target_branch)
        
        for proj, prefix in zip(nestedProjects, nestedProjectPrefixes):
            with utility.cd(prefix):
                git.push("origin %s" % branch)
            repo = bitbucket.repoFromWorkspaceRepoPath(proj, isSubmodule=False, isNested=True)
            
            newRequest = postPullRequest(repo, title, branch, target_branch,descr, reviewers, args)
            if newRequest:
                pullRequestLinks[newRequest.link()] = True
            else:
                # if a pull request could not be generated, just add a link to browse the branch
                pullRequestLinks["%s%s/browse?at=%s" % (bitbucket.rzbitbucketURL,
                                                        repo.repo.url(),
                                                        urllib.quote_plus("refs/heads/%s" % branch))] = False
            

        ## OUTER LEVEL REPO
        # load the repo level REST resource
        if not args["--subprojectsOnly"]:
            if not git.hasBranch(branch):
                utility.printMsg("Top level repository does not have a branch %s, not generating a Pull Request" % (branch))
                return True
            if git.branchUpToDateWith(target_branch, branch):
                utility.printMsg("%s up to date with %s, not generating a Pull Request in Top Level repo" % (target_branch, branch))
                return True
            
                
            repo_name = args["--repo"]
            repo = bitbucket.repoFromWorkspaceRepoPath(wsDir, topLevelRepo=repo_name, topLevelProject=project_name)
            utility.printMsg("Posting pull request to %s,%s" % (project_name, repo_name))
            request = postPullRequest(repo, title, branch, target_branch, descr, reviewers, args)
            updatedDescription = request.description()
            for link in pullRequestLinks:
                updatedDescription = addLinkToDescription(updatedDescription, link, pullRequestLinks[link])

            if updatedDescription != request.description(): 
                request = postPullRequest(repo, title, branch, target_branch, 
                                         updatedDescription, 
                                         reviewers, 
                                         args)
                       
            utility.printMsg("Request generated/updated:\n\n%s" % request)
        return True

    def setDefaultConfig(self, config):
        config.ensureSection("project")
        config.set("project", "stashURL", "https://rzlc.llnl.gov/bitbucket")
        config.set("project", "verifySSL", "True")
        config.set("project", "name", "My unnamed project")
        pass

def addLinkToDescription(descr, link, isPullRequest):
    if descr is not None and link is not None:
        if link not in descr: 
            if isPullRequest:
               descr +="\nThis pull request is related to the pull request at: %s" % link
            else:
               descr +="\nThis pull request is related to the branch at: %s" % link
    return descr

def getReposPullRequest(repo, branch, target_branch, args):
    pull_requests = repo.pullRequests(direction="OUTGOING", at="refs/heads/%s" % branch, state=args["--state"])
    # check to see if pull request already exists for this branch
    request = None
    for rqst in pull_requests:
        if rqst.toRef() == target_branch:
            request = rqst
            break
    return request

    
def getReposPullRequestDescription(repo, branch, target_branch, args):
    descr = None
    request = getReposPullRequest(repo, branch, target_branch, args)
    if request is not None:
        descr = request.description()
    return descr

def pullRequestAlreadyMerged(errorMessage):
   if "already up-to-date with branch" in errorMessage:
      return True
   elif "This pull request has already been merged" in errorMessage:
      return True
   else:
      return False

def postPullRequest(repo, title, branch, target_branch, descr, reviewers, args):
    # get the open pull requests outgoing from our public branch
    utility.printMsg("Gathering active pull requests on %s" % branch)
    request = getReposPullRequest(repo, branch, target_branch, args)

    if not request:
        if not args["--update"]:
            # add a new pull request
            if not title:
                title = branch
            try:
                utility.printMsg("Creating new pull request titled '%s' \n for branch %s targeting %s. " %
                      (title, branch, target_branch))
                utility.printMsg("reviewers: %s" % reviewers)
                request = repo.createPullRequest(title, branch, target_branch, description=descr, reviewers=reviewers)
                url = request.link()
                utility.printMsg("Pull request created at %s ." % url)
            except stashy.errors.GenericException as e:
                print("BITBUCKET: %s" % e.data["errors"][0]["message"])
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
        else:
            utility.printMsg("No pull request from %s to %s to update" % (branch, target_branch))

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

                subReviewers = reviewers
                if request.author() in subReviewers:
                    utility.printMsg("%s is the author of the pull request and cannot be a reviewer" % request.author())
                    subReviewers.remove(request.author())
                if title is not None or descr is not None or subReviewers:
                    utility.printMsg("updating request with title=%s, description=%s, reviewers=%s" % (title, descr, subReviewers))
                    request = request.update(ver, title=title,  description=descr, reviewers=subReviewers)
                    url = request.link()
                    utility.printMsg("Pull request updated at %s ." % url)
                else:
                    url = request.link()
                    utility.printMsg("Pull request unchanged at %s ." % url)
            except stashy.errors.GenericException as e:
                print("BITBUCKET: %s" % e.data["errors"][0]["message"])
                print("BITBUCKET: %s" % e.data)
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)

        else:
            print ("BITBUCKET: Pull request from %s to %s already exists, can't add a new one" %
                   (branch, target_branch))
            
    return request

if __name__ == "__main__":
    import grapeMenu
    grapeMenu.menu().applyMenuChoice("review",[])
