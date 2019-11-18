import io
import logging
import re
import urllib
from stashy import errors as stashy_errors
from vine import Atlassian
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
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

        logging.info(f"Logging onto {args['--bitbucketURL']}")
        if args["--test"]:
            bitbucket = Atlassian.TestAtlassian(name)
        else:
            verify = True if args["--verifySSL"].lower() == "true" else False
            bitbucket = Atlassian.Atlassian(name, url=args["--bitbucketURL"],
                                            verify=verify,
                                            workspace_dir=self.workspace_dir)

        # default project (outer level project)
        project_name = args["--project"]

        # default repo (outer level repo)
        repo_name = args["--repo"]

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch(execution_path=self.workspace_dir)

        #ensure branch is pushed
        logging.info(f"Pushing {branch} to bitbucket...")
        git.push(f"origin {branch}", execution_path=self.workspace_dir)
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
            pr_description = existingOuterLevelRequest.description()
            if isinstance(pr_description, bytes):
                pr_description = pr_description.decode("utf-8")
            descr = pr_description

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
        missing = utility.getModifiedInactiveSubmodules(
            target_branch, branch, includeAdded=True, workspace_dir=self.workspace_dir)
        if missing:
            logging.info("The following submodules that you've modified are not currently present in your workspace.\n"
                             "You should activate them using grape uv  and then call grape review again. If you haven't modified "
                             "these submodules, you may need to do a grape md to proceed.")
            logging.info(','.join(missing))
            return False
        pullRequestLinks = {}
        if not args["--norecurse"] and (args["--recurse"] or config.getboolean(self.SECTION_WORKSPACE, "manageSubmodules")):
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, target_branch, branch, includeAdded=True)
            submoduleBranchMappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")

            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                # push branch
                logging.info(f"Pushing {branch} to bitbucket...")
                git.push(f"origin {branch}", execution_path=submodule)
                repo = bitbucket.repoFromWorkspaceRepoPath(submodule,
                                                           isSubmodule=True)
                # determine branch prefix
                prefix = git.branchPrefix(branch)
                sub_target_branch = submoduleBranchMappings[prefix]

                getReposPullRequestDescription(repo, branch, sub_target_branch,
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
                    url_ = urllib.parse.quote_plus(f"refs/heads/{branch}")
                    pullRequestLinks[f"{bitbucket.rzbitbucketURL}{repo.repo.url()}/browse?at={url_}"] = False

        ## NESTED SUBPROJECT REPOS
        nestedProjects = config_parser_user.getAllModifiedNestedSubprojects(
            target_branch, workspaceDir=self.workspace_dir)
        nestedProjectPrefixes = config_parser_user.getAllModifiedNestedSubprojectPrefixes(
            target_branch, workspaceDir=self.workspace_dir)

        for proj, prefix in zip(nestedProjects, nestedProjectPrefixes):
            git.push(f"origin {branch}", execution_path=prefix)
            repo = bitbucket.repoFromWorkspaceRepoPath(proj, isSubmodule=False, isNested=True)

            newRequest = postPullRequest(repo, title, branch, target_branch,descr, reviewers, args)
            if newRequest:
                pullRequestLinks[newRequest.link()] = True
            else:
                # if a pull request could not be generated, just add a link to browse the branch
                url_ = urllib.parse.quote_plus(f"refs/heads/{branch}")
                pullRequestLinks[f"{bitbucket.rzbitbucketURL}{repo.repo.url().replace('api/1.0','')}/browse?at={url_}"] = False

        ## OUTER LEVEL REPO
        # load the repo level REST resource
        if not args["--subprojectsOnly"]:
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

            repo_name = args["--repo"]
            repo = bitbucket.repoFromWorkspaceRepoPath(self.workspace_dir, topLevelRepo=repo_name, topLevelProject=project_name)
            logging.info(f"Posting pull request to {project_name},{repo_name}")
            request = postPullRequest(repo, title, branch, target_branch, descr, reviewers, args)
            updatedDescription = request.description()
            if isinstance(updatedDescription, bytes):
                updatedDescription = updatedDescription.decode("utf-8")

            for link in pullRequestLinks:
                updatedDescription = addLinkToDescription(updatedDescription, link, pullRequestLinks[link])

            if updatedDescription != request.description():
                request = postPullRequest(repo, title, branch, target_branch,
                                         updatedDescription,
                                         reviewers,
                                         args)

            logging.info(f"Request generated/updated:\n\n{request}")
        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "stashURL", "https://rzlc.llnl.gov/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")


def addLinkToDescription(descr, link, isPullRequest):
    if descr is not None and link is not None:
        if type(link) is not str:
            link = link.decode("utf-8")
        if type(descr) is not str:
            descr = descr.decode("utf-8")
        if link not in descr:
            if isPullRequest:
                descr += f"\nThis pull request is related to "
                descr += f"the pull request at: {link}"
            else:
                descr += f"\nThis pull request is related to "
                descr += f"the branch at: {link}"
    return descr

def getReposPullRequest(repo, branch, target_branch, args):
    pull_requests = repo.pullRequests(direction="OUTGOING", at=f"refs/heads/{branch}", state=args["--state"])
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
        if isinstance(descr, bytes):
            descr = descr.decode("utf-8")
    return descr

def pullRequestAlreadyMerged(errorMessage):
    if "already up-to-date with branch" in errorMessage or \
            "This pull request has already been merged" in errorMessage:
        return True
    return False

def postPullRequest(repo, title, branch, target_branch, descr, reviewers, args):
    # get the open pull requests outgoing from our public branch
    logging.info(f"Gathering active pull requests on {branch} for repo {repo}")
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
                url = request.link()
                logging.info(f"Pull request created at {url} .")
            except stashy_errors.GenericException as e:
                logging.error(f"BITBUCKET: {e.data['errors'][0]['message']}")
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
        else:
            vine_logging.printMsg(
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
                    request = request.update(ver, title=title,  description=descr, reviewers=subReviewers)
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
    from vine import grapeMenu
    grapeMenu.menu().applyMenuChoice("review",[])
