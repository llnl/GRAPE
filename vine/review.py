import io
import os
import logging
import re
import urllib
from stashy import errors as stashy_errors
from requests import adapters
from vine import CodeReviewsFactory
from vine import Atlassian
from vine import Gitlab
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
from vine import grapeMenu
from vine import multi_repo_cmd_launcher
from vine import utility
from vine import vine_logging
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper

# Prepare Feature Branch for review
class Review(Option, WorkspaceDirHandler):
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
                        [--codeReviewsURL=<url>]
                        [--verifySSL=<bool>]
                        [--project=<prj>]
                        [--repo=<repo>]
                        [--recurse]
                        [--noRecurse]
                        [--noRecurseSubprojects]
                        [--test]
                        [--prepend | --append]
                        [--subprojectsOnly]
                        [--ssh_pat_url=<url>]
                        [--ssh_pat_port=<int>]
                        [--noLocal]

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
        --codeReviewsURL=<url>      The code review platform url, e.g. https://your.host.org/gitlab. Grape supports
                                    both Bitbucket and Gitlab code review platforms.
                                    [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --project=<prj>             The project key part of the codeReviews url, e.g. the "GRP" in
                                    https://your.host.org/gitlab/or/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repo name part of the codeReviews url, e.g. the "grape" in
                                    https://your.host.org/gitlab/or/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.repo.name]
        --recurse                   If set, adds a pull request for each modified submodule.
                                    The pull request for the outer level repo will have a description with links to the
                                    submodules' pull requests. On by default if grapeConfig.workspace.manageSubmodules
                                    is set to true.
        --noRecurse                 Disables adding pull requests to submodules.
        --noRecurseSubprojects      Disables adding pull requests to nested subprojects.
        --test                      Uses a dummy version of stashy that requires no communication to an actual Bitbucket
                                    server.
        --prepend                   For reviewers, title,  and description updates, prepend <userNames>, <title>,  and
                                    <description> to the existing title / description instead of replacing it.
        --append                    For reviewers, title,  and description updates, append <userNames>, <title>,  and
                                    <description> to the existing reviewers, title, or description instead of replacing it.
        --subprojectsOnly           As a work around to when you've only touched a subproject, this will prevent errors
                                    arising in the top level repo.
        --ssh_pat_url=<url>         SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                    REST API.
                                    [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>        Port number to issue ssh command over to generate a Personal Access Token for authentication
                                    into a Code Review service's REST API.
                                    [default: .grapeconfig.repo.ssh_pat_port]
        --noLocal                   Do not perform any pushes of the topic branch or any git operations relying on the existence
                                    of the local branch in the local workspace. Branches must still exist on the codeReviews
                                    (Bitbucket, Gitlab) server.



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
                with io.open(descrFile) as f:
                    descr = f.readlines()
                descr = ''.join(descr)
                for encoding in ['utf-8', 'windows-1252']:
                    try:
                        descr = descr.decode(encoding).encode('ascii','ignore')
                    except:
                        pass
        else:
            # Convert \n to a newline, but only if it is not escaped
            # (alternation allows newline on separate line)
            descr = re.sub('([^\\\\]|)\\\\n', r'\1\n', descr)
            # Remove one backslash from any escaped \n's.
            descr = re.sub('\\\\\\\\n', "\\\\n", descr)
        return descr

    def parseReviewerArgs(self, args):
        reviewers = args["--reviewers"]
        if reviewers is not None:
            reviewers = reviewers.split()
        return reviewers


    @log_wrapper
    def execute(self, args):
        """
        A fair chunk of this stuff relies on stashy's wrapping of the STASH REST API, which is posted at
        https://developer.atlassian.com/static/rest/stash/2.12.1/stash-rest.html
        """
        config = config_parser_global.grapeConfig()
        name = args["--user"]
        if not name:
            name = utility.getUserName()

        logging.info(f"Logging onto {args['--codeReviewsURL']}")
        if args["--test"]:
            codeReviews = Atlassian.TestAtlassian(name)
        else:
            verify = True if args["--verifySSL"].lower() == "true" else False
            codeReviews = CodeReviewsFactory.makeCodeReviews(name, url=args["--codeReviewsURL"],
                                                verify=verify,
                                                port=int(args["--ssh_pat_port"]),
                                                ssh_path = args["--ssh_pat_url"],
                                                workspace_dir=self.workspace_dir
                                                )
        # default project (outer level project)
        project_name = args["--project"]

        # default repo (outer level repo)
        repo_name = args["--repo"]

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch(execution_path=self.workspace_dir)

        #ensure branch is pushed
        if "--noLocal" not in args or ("--noLocal" in args and not args["--noLocal"]):
            logging.info(f"Pushing {branch} to {codeReviews.url}...")
            git.push(f"origin {branch}", execution_path=self.workspace_dir)
        #target branch for outer level repo
        target_branch = args["--target"]
        if not target_branch:
            target_branch = config.getPublicBranchFor(branch)
        # load pull request from Bitbucket if it already exists
        wsRepo =  codeReviews.project(project_name).repo(repo_name)
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
            pr_description = existingOuterLevelRequest.description()
            if isinstance(pr_description, bytes):
                pr_description = pr_description.decode("utf-8")
            descr = pr_description
        
        # list of description suffixes
        projects_with_reviewer_lists = config.get("publish", "projects_with_reviewer_lists")
        description_suffixes = []

        # determine pull request reviewers
        reviewers = self.parseReviewerArgs(args)
        if reviewers is None and existingOuterLevelRequest is not None:
            reviewers = [r[0] for r in existingOuterLevelRequest.reviewers()]

        # if we're in append mode, only append what was asked for:
        if args["--append"] or args["--prepend"]:
            title = args["--title"]
            descr = self.parseDescriptionArgs(args)
            reviewers = self.parseReviewerArgs(args)

        logging.info(f"Updating remote tracking branches for {target_branch}...")

        # Fetch the remote tracking branch for the target branch
        git.fetch(f"origin {target_branch}", execution_path=self.workspace_dir)
        # Skip fetching of remote tracking branch in submodules if no gitlink changes were fetched
        submodulesModifiedInOrigin = git.getModifiedSubmodules(self.workspace_dir, "origin/"+target_branch, target_branch)
                     
        upArgs = ['up', f'--public={target_branch}', '--updateRemoteOnly']
        if not submodulesModifiedInOrigin:
           upArgs.extend(['--noRecurse', '--recurseSubprojects'])

        upToDate = grapeMenu.menu().applyMenuChoice('up', upArgs)
        if not upToDate:
            logging.info("Failed to update local branches.")
            return False

        runInSubmodules = not args["--noRecurse"] and (args["--recurse"] or config.getboolean(self.SECTION_WORKSPACE, "manageSubmodules"))
        # assemble description suffixes from any projects with reviewer lists
        if runInSubmodules:
            activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            url_map = git.getAllSubmoduleURLMap(execution_path=self.workspace_dir)
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, f"origin/{target_branch}", branch, includeAdded=True)
            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                if submodule in projects_with_reviewer_lists:
                    description_suffix = config.get(f"{submodule}-reviewers", "description_suffix")
                    description_suffix_name = config.get(f"{submodule}-reviewers", "description_suffix_name")
                    description_suffixes.append({"name": description_suffix_name,"body":description_suffix})
        if not args["--noRecurseSubprojects"]:
           nestedProjects = config_parser_user.getAllModifiedNestedSubprojects(
               "origin/"+target_branch, workspaceDir=self.workspace_dir)
           for proj in nestedProjects:
                if proj in projects_with_reviewer_lists:
                    description_suffix = config.get(f"{proj}-reviewers", "description_suffix")
                    description_suffix_name = config.get(f"{proj}-reviewers", "description_suffix_name")
                    description_suffixes.append({"name": description_suffix_name,"body":description_suffix})
        
        # append the description suffixes that aren't already present in the description to the description
        if description_suffixes:
            for suffix in description_suffixes:
                suffix_name = suffix["name"]
                suffix_body = suffix["body"]
                if f"{suffix_name} START" not in descr or f"{suffix_name} STOP" not in descr:
                    descr = f"{descr}\n--------------------{suffix_name} START--------------------\n{suffix_body}\n--------------------{suffix_name} STOP--------------------"

        # assemble arguments for parallel execution of code reviews
        listOfRepoBranchArgTuples=[]
        ##  Submodule Repos
        if runInSubmodules:
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, target_branch, branch, includeAdded=True)
            # update target branch based off of branch prefix
            submoduleBranchMappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")
            # determine branch prefix
            prefix = git.branchPrefix(branch)
            sub_target_branch = submoduleBranchMappings[prefix]
            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                changed = False
                if submodule in activeSubmodules:
                    if git.log(f"--oneline origin/{sub_target_branch}..{branch}", execution_path=os.path.join(self.workspace_dir, submodule)):
                        changed = True
                else:
                    url = url_map[submodule]
                    remotes = git.lsRemote("--heads "+git.parseSubprojectRemoteURL(url, execution_path=self.workspace_dir), execution_path=self.workspace_dir)
                    targetHead = f"refs/heads/{sub_target_branch}"
                    branchHead = f"refs/heads/{branch}"
                    targetSHA = None
                    branchSHA = None
        
                    for entry in remotes.splitlines():
                       if entry:
                          SHA_and_ref = entry.split()
                          if SHA_and_ref[1] == targetHead:
                             targetSHA = SHA_and_ref[0]
                          elif SHA_and_ref[1] == branchHead:
                             branchSHA = SHA_and_ref[0]
                          if branchSHA and targetSHA:
                             break
                    if targetSHA and branchSHA and targetSHA != branchSHA:
                       changed = True 

                if changed:
                    listOfRepoBranchArgTuples.append((submodule,branch,[{"codeReviews":codeReviews,
                                                                         "isSubmodule": True,
                                                                         "isNested": False,
                                                                         "args": args,
                                                                         "target_branch": sub_target_branch,
                                                                         "descr": descr,
                                                                         "title": title,
                                                                         "proj": submodule,
                                                                         "outerLevelURL": outerLevelURL,
                                                                         "reviewers": reviewers,
                                                                         "active": submodule in activeSubmodules }]))

        ## NESTED SUBPROJECT REPOS
        if not args["--noRecurseSubprojects"]:
           activeNestedSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir)
           nestedProjects = config_parser_user.getAllModifiedNestedSubprojects(
               "origin/"+target_branch, now=branch, workspaceDir=self.workspace_dir, checkRemote=True)
           nestedProjectPrefixes = config_parser_user.getAllModifiedNestedSubprojectPrefixes(
               "origin/"+target_branch, now=branch, workspaceDir=self.workspace_dir, checkRemote=True)

           for proj, prefix in zip(nestedProjects, nestedProjectPrefixes):
               prefix_path = os.path.join(self.workspace_dir, prefix)
               listOfRepoBranchArgTuples.append((prefix_path,branch,[{"codeReviews":codeReviews,
                                                                    "isSubmodule": False,
                                                                    "isNested": True,
                                                                    "args": args,
                                                                    "target_branch": target_branch,
                                                                    "descr": descr,
                                                                    "title": title,
                                                                    "proj": proj,
                                                                    "outerLevelURL": outerLevelURL,
                                                                    "reviewers": reviewers,
                                                                    "active": proj in activeNestedSubprojects}]))

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(PostPullRequestForRepo, listOfRepoBranchArgTuples=listOfRepoBranchArgTuples, workspace_dir=self.workspace_dir)
        pullRequestLinks = launcher.launchFromWorkspaceDir(noPause=True, handleMRE=HandlePostPullRequestForRepoMRE)
        pullRequestLinks.sort()

        ## OUTER LEVEL REPO
        # load the repo level REST resource
        if not args["--subprojectsOnly"]:
            if "--noLocal" in args and args["--noLocal"]:
                pass
            else:
                if not git.hasBranch(branch, execution_path=self.workspace_dir):
                    logging.info(
                        f"Top level repository does not have a branch {branch}," +
                        " not generating a Pull Request")
                    return True
                if git.branchUpToDateWith(target_branch, branch, execution_path=self.workspace_dir):
                    logging.info(
                        f"{target_branch} up to date with {branch}," +
                        " not generating a Pull Request in Top Level repo")
                    return True
                if not git.log(f"--oneline origin/{target_branch}..{branch}", execution_path=self.workspace_dir):
                    logging.info(
                        f"{branch} is in the history of {target_branch}," +
                        " not generating a Pull Request in Top Level repo")
                    return True

            repo_name = args["--repo"]
            repo = codeReviews.repoFromWorkspaceRepoPath(self.workspace_dir, topLevelRepo=repo_name, topLevelProject=project_name)
            logging.info(f"Posting pull request to {project_name},{repo_name}")
            request = postPullRequest(repo, title, branch, target_branch, descr, reviewers, args, self.workspace_dir)
            updatedDescription = request.description()
            if isinstance(updatedDescription, bytes):
                updatedDescription = updatedDescription.decode("utf-8")

            for link in pullRequestLinks:
                updatedDescription = addLinkToDescription(updatedDescription, link)

            pre_update_description = request.description()
            if isinstance(pre_update_description, bytes):
                pre_update_description = pre_update_description.decode("utf-8")
            if updatedDescription != pre_update_description:
                request = postPullRequest(repo, title, branch, target_branch,
                                         updatedDescription,
                                         reviewers,
                                         args,
                                         self.workspace_dir)

            logging.info(f"Request generated/updated:\n\n{request}")
        return True


    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")


def HandlePostPullRequestForRepoMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        raise e


def PostPullRequestForRepo(repo, branch, args, *, workspace_dir):
    kwargs = args[0]
    codeReviews = kwargs["codeReviews"]
    isSubmodule = kwargs["isSubmodule"]
    isNested = kwargs["isNested"]
    review_args = kwargs["args"]
    target_branch = kwargs["target_branch"]
    descr = kwargs["descr"]
    title = kwargs["title"]
    proj = kwargs["proj"]
    outerLevelURL = kwargs["outerLevelURL"]
    reviewers = kwargs["reviewers"]
    active = kwargs["active"]

    # push branch
    if active and ("--noLocal" not in review_args or ("--noLocal" in review_args and not review_args["--noLocal"])):
        logging.info(f"Pushing {branch} to {codeReviews.url} in {repo}")
        git.push(f"origin {branch}", execution_path=repo)
    codeReview_repo = codeReviews.repoFromWorkspaceRepoPath(proj, isSubmodule=isSubmodule, isNested=isNested)

    #amend the subproject pull request description with the link to the outer pull request
    getReposPullRequestDescription(codeReview_repo, branch, target_branch, review_args)
    subDescr = addLinkToDescription(descr, outerLevelURL)
    if review_args["--prepend"] or review_args["--append"]:
        subDescr = descr
    descr = subDescr

    newRequest = postPullRequest(codeReview_repo, title, branch, target_branch, descr, reviewers, review_args, repo)
    if newRequest:
        return newRequest.link()
    else:
        return ""

def addLinkToDescription(descr, link):
    if descr is not None and link:
        if not isinstance(link, str):
            link = link.decode("utf-8")
        if not isinstance(descr, str):
            descr = descr.decode("utf-8")
        if link not in descr:
            descr += f"\nThis merge request is related to "
            descr += f"the merge request at: {link}"
    return descr


def getReposPullRequest(repo, branch, target_branch, args):
    pull_requests = repo.pullRequests(direction="OUTGOING", at=f"refs/heads/{branch}", state=args["--state"])
    # check to see if pull request already exists for this branch
    request = None
    for rqst in pull_requests:
        if rqst.toRef() == target_branch and rqst.fromRef() == branch:
            request = rqst
            break
    return request


def getReposPullRequestDescription(repo, branch, target_branch, args):
    descr = None
    request = getReposPullRequest(repo, branch, target_branch, args)
    if request is not None:
        descr = request.description()
        if isinstance(descr, bytes):
            descr = descr.decode("utf-8")
    return descr


def pullRequestAlreadyMerged(errorMessage):
    if "already up-to-date with branch" in errorMessage or \
            "This pull request has already been merged" in errorMessage:
        return True
    return False


def targetBranchMissing(errorMessage):
    if "Repository" in errorMessage and "of project with key" in errorMessage and "has no branch" in errorMessage:
        return True
    return False


def postPullRequest(repo, title, branch, target_branch, descr, reviewers, args, git_execution_path):
    config = config_parser_global.grapeConfig()
    projects_with_reviewer_lists = config.get("publish", "projects_with_reviewer_lists")
    reviewer_list_name = None
    reviewer_list = None
    reviewer_list_min_reviewers = None
    repo_name = repo.project.name
    if repo_name in projects_with_reviewer_lists:
        reviewer_list_name = config.get(f"{repo_name}-reviewers","reviewer_list_name")
        reviewer_list = config.get(f"{repo_name}-reviewers","reviewer_list").split()
        reviewer_list_min_reviewers = config.get(f"{repo_name}-reviewers","min_reviewers")



    projects_with_reviewer_lists = projects_with_reviewer_lists.split()
    # get the open pull requests outgoing from our public branch
    logging.info(f"Gathering active pull requests on {branch} for repo {args['--repo']}")
    request = getReposPullRequest(repo, branch, target_branch, args)

    if not request:
        if not args["--update"]:
            # add a new pull request
            if not title:
                title = branch
            try:
                logging.info(
                    f"Creating new pull request titled '{title}' " + "\n" +
                    f" for branch {branch} targeting {target_branch}. ")
                logging.info(f"reviewers: {reviewers}")
                request = repo.createPullRequest(title, branch, target_branch, description=descr, reviewers=reviewers)
                if request:
                   url = request.link()
                   logging.info(f"Pull request created at {url} .")
            except stashy_errors.GenericException as e:
                logging.error(f"BITBUCKET: {e.data['errors'][0]['message']}")
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
            except stashy_errors.NotFoundException as e:
                if targetBranchMissing(e.data["errors"][0]["message"]):
                    if utility.userInput(f"Target branch {target_branch} in {git_execution_path} is missing ... would you like to create and push it? [y/n]"):
                        start_branch = utility.userInput(f"Where should {target_branch} branch off of?")
                        git.branch(f"{target_branch} {start_branch}", execution_path=git_execution_path)
                        git.push(f"origin {target_branch}", execution_path=git_execution_path)
                        postPullRequest(repo, title, branch, target_branch, descr, reviewers, args, git_execution_path)
        else:
            logging.info(
                f"No pull request from {branch} to {target_branch} to update")

    else:
        if not args["--add"]:
            # update the pull request
            logging.info("Updating pull request...")
            try:

                if reviewers:
                    if args["--prepend"] or args["--append"]:
                        revList = [r[0] for r in request.reviewers()]
                    else:
                        revList = []
                    reviewers += revList
                if not reviewers:
                    reviewers = [r[0] for r in request.reviewers()]
                logging.info(f"reviewer list is: {reviewers}")
                ver = request.version()

                if title is not None and (args["--prepend"] or args["--append"]):
                    currentTitle = request.title()
                    if args["--prepend"]:
                        title = title+currentTitle
                    elif args["--append"]:
                        title = currentTitle+title
                if descr is not None and (args["--prepend"] or args["--append"]):
                    currentDescription = request.description()
                    if isinstance(descr, bytes):
                        descr = descr.decode("utf-8")
                    if isinstance(currentDescription, bytes):
                        currentDescription = currentDescription.decode("utf-8")
                    if args["--prepend"]:
                        descr = descr + "\n" + currentDescription
                    elif args["--append"]:
                        descr = currentDescription + "\n" + descr

                subReviewers = reviewers
                if request.author() in subReviewers:
                    logging.info(
                            f"{request.author()} is the author of the pull" +
                            " request and cannot be a reviewer")
                    subReviewers.remove(request.author())
                if title is not None or descr is not None or subReviewers:
                    logging.info(
                        f"updating request with title={title}, " +
                        f"description={descr}, reviewers={subReviewers}")
                    request = request.update(ver, title=title,  description=f"{descr}", reviewers={Gitlab.GRAPE_GITLAB_APPROVAL_RULE_NAME:(subReviewers, len(subReviewers)),
                                                                                              reviewer_list_name:(reviewer_list, reviewer_list_min_reviewers)
                                                                                              })
                    url = request.link()
                    logging.info(f"Pull request updated at {url} .")
                else:
                    url = request.link()
                    logging.info(f"Pull request unchanged at {url} .")
            except stashy_errors.GenericException as e:
                logging.error(f"BITBUCKET: {e.data['errors'][0]['message']}")
                logging.error(f"BITBUCKET: {e.data}")
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
        else:
            logging.info(f"BITBUCKET: Pull request from {branch} to " +
                         f"{target_branch} already exists, can't add a new one")

    return request


if __name__ == "__main__":
    grapeMenu.menu().applyMenuChoice("review",[])
