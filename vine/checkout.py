import logging
import os
import re
import shutil
import stat
import time
from vine import config_parser_base
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.addSubproject import AddSubproject
from vine.updateView import UpdateView
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine import utility
from vine.vine_logging import log_wrapper


def handledCheckout(repo='', branch='master', args=[], *, workspace_dir):
    # 'workspace_dir' included for continuity with multi_repo_cmd_launcher.
    checkoutargs = args["checkout"]
    sync = args["sync"]
    quiet = args["quiet"]
    verbose = args["verbose"]
    if sync:
        # attempt to fetch the requested branch
        try:
            git.fetch("origin", f"{branch}:{branch}", execution_path=repo)
        except:
            # the branch may not exist, but ignore the exception
            # and allow the checkout to throw the exception.
            pass
    try:
        if verbose:
            logging.info(f"checking out {branch} in {repo}")
        git.checkout(f"{checkoutargs} {branch}", execution_path=repo)
    except grape_errors.GrapeGitError as e:
        if "already exists" in e.gitOutput and "-b" in checkoutargs:
            if not quiet:
                logging.info(f"Reattempting checkout of previously existing branch {branch} without using a '-b' in {repo}")
            git.checkout(f"{checkoutargs.replace('-b','')} {branch}", execution_path=repo)
        if "index.lock" in e.gitOutput:
            if not quiet:
                logging.info(f"waiting for 3 seconds in {branch} in {repo} due to index.lock detection")
            time.sleep(3)
            if not quiet:
                logging.info(f"retrying checkout out of {branch} in {repo}")
            git.checkout(f"{checkoutargs} {branch}", execution_path=repo)
        else:
            logging.debug(f"checkout failed in {repo}.")
            raise e
    if verbose:
        logging.info(f"Checked out {branch} in {repo}")

    return True

_skipBranchCreation = False
_createNewBranch = False
_skipPush = False

def handleCheckoutMRE(mre):
    global _skipBranchCreation
    global _createNewBranch
    global _skipPush
    newBranchReposArgTuples = []

    for e1, branch, project, checkoutargs in zip(mre.exceptions(), mre.branches(), mre.repos(), mre.args()):
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            if "pathspec" in e.gitOutput.lower():
                createNewBranch = _createNewBranch
                if _skipBranchCreation:
                    logging.info(f"Skipping checkout of {branch} in " +
                                 f"{project}")
                    createNewBranch = False

                elif not createNewBranch:
                    createNewBranch = utility.userInput(
                        "Branch not found locally or remotely. Would you "+
                        f"like to create a new branch called {branch} " +
                        f"in {project}? \n(select 'a' to say yes for"+
                        " (a)ll, 's' to (s)kip creation for branches that"+
                        " don't exist )\n(y,n,a,s)", 'y', ['a','s'])

                if str(createNewBranch).lower()[0] == 'a':
                    _createNewBranch = True
                    createNewBranch = True
                if str(createNewBranch).lower()[0] == 's':
                    _skipBranchCreation = True
                    createNewBranch = False
                if createNewBranch:
                    newBranchReposArgTuples.append((project, branch, {"checkout": checkoutargs["checkout"], "skippush": _skipPush, "quiet":checkoutargs["quiet"], "verbose":checkoutargs["verbose"]}))
                else:
                    continue

            elif "already exists" in e.gitOutput.lower():
                if not checkoutargs["quiet"]:
                    logging.info(f"Branch {branch} already exists in " +
                                 f"{project}.")
                branchDescription = git.commitDescription(branch, execution_path=project)
                headDescription = git.commitDescription("HEAD", execution_path=project)
                if branchDescription == headDescription:
                    if not checkoutargs["quiet"]:
                        logging.info(f"Branch {branch} and HEAD are the " +
                                     f"same. Switching to {branch}.")
                    action = "k"
                else:
                    if not checkoutargs["quiet"]:
                        logging.info(f"Branch {branch} and HEAD " +
                                              "are not the same.")
                    action = ''
                    valid = False
                    while not valid:
                        action = utility.userInput(
                            f"Would you like to\n(k)eep it as is at: " +
                            f"{branchDescription}\n or \n (f)orce " +
                            f"it to: {headDescription}?\n(k,f)", 'k')
                        valid = (action == 'k') or (action == 'f')
                        if not valid:
                            logging.info("Invalid input. Enter k or f. ")
                if action == 'k':
                    git.checkout(branch, execution_path=project)
                elif action == 'f':
                    git.checkout(f"-B {branch}", execution_path=project)
            elif e.has_conflict():
                logging.info("CONFLICT occurred when pulling {branch} " +
                             "from origin.")
            elif "does not appear to be a git repository" in e.gitOutput.lower():
                if not checkoutargs["quiet"]:
                    logging.info("Remote 'origin' does not exist. "
                                 "This branch was not updated from a remote repository.")
            elif e.could_not_find_remote_ref():
                if not checkoutargs["quiet"]:
                    logging.info(
                        f"Remote of {project} does not have reference to " +
                        f"{branch}. You may want to push this branch. ")
            else:
                raise e

    if newBranchReposArgTuples:
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            createNewBranches,
            listOfRepoBranchArgTuples=newBranchReposArgTuples,
            workspace_dir=mre.workspace_dir)
        launcher.launchFromWorkspaceDir(handleMRE=createNewBranchesMREHandler)

def handleCheckoutSkipBranchCreationMRE(mre):
    global _skipBranchCreation
    _skipBranchCreation = True
    handleCheckoutMRE(mre)
    _skipBranchCreation = False

def handleCheckoutSkipBranchPushMRE(mre):
    global _skipPush
    _skipPush = True
    handleCheckoutMRE(mre)
    _skipPush = False

def createNewBranches(repo='', branch='', args={}, *, workspace_dir):
    #workspace_dir ignored
    checkoutargs = args["checkout"]
    skippusharg = args["skippush"]
    quiet = args["quiet"]
    verbose = args["verbose"]
    if verbose:
        logging.info(f"Checking out new branch {branch} in {repo}.")
    git.checkout(f"{checkoutargs} -b {branch}", execution_path=repo)
    if not skippusharg:
        git.push(f"-u origin {branch}", execution_path=repo)
    return True

def createNewBranchesMREHandler(mre):
    for e, b in zip(mre.exceptions(), mre.branches()):
        logging.error(f"{b} {e}")

# check whether the branch exists already in the outer level repo
# return value 0 : does not exist
#              1 : already exists
#              2 : exists as a case-insensitive match
def branchAlreadyExists(branch, workspace_dir):
    retVal = 0
    git.fetch("origin", execution_path=workspace_dir)
    # Trailing '' used to add a delimiter to end of path.
    branch_path = git.join_list_as_git_path(['remotes', 'origin', ''])
    # make sure branch does not already exist
    allBranches = set([b[len(branch_path):] if b.startswith(branch_path) else b for b in git.allBranches(execution_path=workspace_dir)])
    if branch in allBranches:
        logging.info(f"Branch {branch} already exists!")
        retVal = 1
    else:
        # make sure branch is not a case-insensitive match
        # as this will cause problems on Windows and Mac filesystems.
        for b in allBranches:
            if branch.lower() == b.lower():
                logging.info(f"Branch {b} already exists!\n" +
                             f"{branch} is a case insensitive match.")
                retVal = 2
    return retVal

def parseGitModulesDiffOutput(currentSHA, branch, addedModules, removedModules,
                              changedURLModules, *, workspace_dir):
    try:
        submoduleListWillChange = ".gitmodules" in git.diff(f"--name-only {currentSHA} {branch} --", execution_path=workspace_dir)
    except grape_errors.GrapeGitError as e:
        if f"bad revision '{branch}'" in e.gitOutput:
            logging.info(f"Fetching {branch} in {workspace_dir}")
            git.fetch("origin", f"{branch}:{branch}", execution_path=workspace_dir)
            submoduleListWillChange = ".gitmodules" in git.diff(f"--name-only {currentSHA} {branch} --", execution_path=workspace_dir)
        else:
            raise e
    if submoduleListWillChange:
        output = git.diff(f"{currentSHA} {branch} --no-ext-diff -- .gitmodules", execution_path=workspace_dir)
        currentSubmodule = False
        pattern = re.compile(r"-\s+url\s*=")

        for line in output.split('\n'):
            if "[submodule" in line:
                currentSubmodule = line.split('"')[1]
            # This relies on the diff context being sufficient to catch the submodule line.
            # Only 2 lines of backwards context should be required, so this should be ok.
            if pattern.match(line):
                if currentSubmodule:
                    changedURLModules.append(currentSubmodule)
            if "+[submodule" in line:
                addedModules.append(line.split('"')[1])
                currentSubmodule = False
            if "-[submodule" in line:
                removedModules.append(line.split('"')[1])
                currentSubmodule = False

    return addedModules, removedModules, changedURLModules

def cleanSubmodule(sub, args, veryclean = False, activeSubmodules = [], *, workspace_dir):
    cleaned = False
    working_dir = os.path.join(workspace_dir, sub)
    dirExists = os.path.exists(working_dir)
    dirIsEmpty = not dirExists or len(os.listdir(working_dir)) == 0
    workingDirClean = dirIsEmpty or git.isWorkingDirectoryClean(execution_path=working_dir)
    changedActive = sub in activeSubmodules
    if workingDirClean or (veryclean and not changedActive):
        # veryclean will always try to clean, fail if the clean fails
        # and remove the back-end repo.
        if veryclean:
            unpushed = False
            if not dirIsEmpty and changedActive:
                unpushed = git.log("--branches --not --remotes --oneline --decorate", execution_path=working_dir)
            if unpushed:
                logging.info("You have unpushed changed in " +
                             f"{sub}:\n{unpushed}")
                clean = utility.userInput(
                    f"Would you like to remove the submodule {sub} " +
                    "(this will discard your unpushed changes)?", 'n')
            else:
                clean = True
        else:
            cleanBehaviorSet = args["--noUpdateView"] or args["--updateView"]
            if not cleanBehaviorSet:
                clean = utility.userInput("Would you like to remove " +
                                          f"the submodule {sub} ?", 'n')
            elif args["--noUpdateView"]:
                clean = False
            elif args["--updateView"]:
                clean = True
        if clean:
            logging.info(f"Removing clean submodule {sub}.")
            if not veryclean or changedActive:
                try:
                    shutil.rmtree(os.path.join(workspace_dir, sub))
                except FileNotFoundError:
                    pass
            if veryclean:
                if changedActive:
                    git.submodule(f"deinit -f {sub}", execution_path=workspace_dir)
                # This must be removed even for inactive submodules
                modulepath = os.path.join(workspace_dir, ".git", "modules", sub)
                if os.path.exists(modulepath):

                    try:
                        shutil.rmtree(modulepath)
                    except OSError:
                        # windows needs to change the permissions first
                        for root,dirs,files in os.walk(modulepath):
                            for name in files:
                                os.chmod(os.path.join(root, name), stat.S_IWRITE)
                        try:
                            shutil.rmtree(modulepath)
                        except OSError:
                            time.sleep(1)
                            shutil.rmtree(modulepath)
            cleaned = True
    else:
        logging.info(f"Unstaged / committed changes in {sub}," +
                     " not removing.")
    return cleaned


class Checkout(Option, WorkspaceDirHandler):
    """
    grape checkout

    Usage: grape-checkout [-v] [-q] [-b] [-F] [--sync=<bool>] [--emailSubject=<sbj>] [--updateView] [--noUpdateView] [--filter=<arg>] <branch>

    Options:
        -v                  Print output from individual directories.
        -q                  Quiet warnings from individual directories that don't cause failure.
        -b                  Create the branch off of the current HEAD in each project.
        -F                  Force removal of nested subprojects removed or replaced (with a different URL) as by the checkout.
        --sync=<bool>       Take extra steps to ensure the branch you check out is up to date with origin,
                            either by pushing or pulling the remote tracking branch.
                            [default: .grapeconfig.post-checkout.syncWithOrigin]
        --updateView        If your submodules / nested projects change, change your workspace to match the changes.
                            Warning - setting this may cause you to lose unpushed work in nested subprojects.
        --noUpdateView      If your submodules / nested projects change, do not change your workspace to match the changes.
        --filter=<arg>      Optional clone filter argument to use if any subprojects get cloned during checkout.
                            WARNING! This is still experimental and may have issues with grape workflows.
                            In particular, tree:0 has performance issues with git rev-list/log command on specified
                            files (it appears to download each commit separately).
          

    Arguments:
        <branch>    The name of the branch to checkout.

    """
    def __init__(self):
        super(Checkout, self).__init__()
        self._key = "checkout"
        self._section = "Workspace"

    def description(self):
        return "Checks out a branch in all projects in this workspace."

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        sync = args["--sync"].lower().strip() in ['true', 'yes']
        args["--sync"] = sync
        branch = args["<branch>"]

        if branch == "HEAD":
           logging.error("<branch> cannot be specified as HEAD")
           return False

        startingSHA = str(git.shortSHA(branchName="HEAD", execution_path=self.workspace_dir))
        startingBranch = git.currentBranch(execution_path=self.workspace_dir)

        addedModules = []
        removedModules = []
        changedURLModules = []
        uvArgs = []
        checkoutargs = ''
        submodulesDidChange = False
        if args['-b']:
            checkoutargs += " -b"

            branchStatus = branchAlreadyExists(branch, self.workspace_dir)
            if branchStatus:
                logging.info("Not creating new branch.")
                return False
        else:
            # check to see if we already have the branch
            try:
                git.shortSHA(branchName=branch, execution_path=self.workspace_dir)
            except:
                try:
                    # otherwise fetch it
                    git.fetch("origin", f"{branch}:{branch}", execution_path=self.workspace_dir)
                except grape_errors.GrapeGitError as e:
                    logging.info(
                        f"Branch {branch} could not be fetched in outer " +
                        f"level repo:\n{e}\nUse grape checkout -b if" +
                        " you really want to create a new branch off of HEAD.")
                    return False

            if config_parser_global.grapeConfig().getboolean(self.SECTION_WORKSPACE, "manageSubmodules"):
                parseGitModulesDiffOutput(
                    startingSHA, branch, addedModules, removedModules,
                    changedURLModules, workspace_dir=self.workspace_dir)

            if addedModules or removedModules or changedURLModules:
                submodulesDidChange = True

            # deinit and clean out any submodules that changed urls
            initiallyActiveSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            for sub in changedURLModules:
                maybe_active = "active" if sub in initiallyActiveSubmodules else "inactive"
                if not args["-q"]:
                    logging.info(
                        f"url for {sub} changed, attempting to remove " +
                        f"references for {maybe_active} submodule.")
                cleaned = cleanSubmodule(sub, args, True, initiallyActiveSubmodules, workspace_dir=self.workspace_dir)
                if not cleaned:
                    logging.info(f"Failed to remove old submodule for {sub}.")
                    return False

        logging.info(f"Performing checkout of {branch} in outer level project.")
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            handledCheckout,
            listOfRepoBranchArgTuples=[(self.workspace_dir, branch,
                                        {"checkout":checkoutargs, "sync":sync, "quiet":args["-q"], "verbose":args["-v"]})],
            workspace_dir=self.workspace_dir)

        retvals = launcher.launchFromWorkspaceDir(handleMRE=handleCheckoutMRE)
        if not retvals or not retvals[0]:
            return False

        # Ensure any global grape config is re-read from the new branch
        config_parser_global.read(workspace_dir=self.workspace_dir)

        # reinit any submodules with changed urls
        for sub in changedURLModules:
            if sub in initiallyActiveSubmodules:
                git.submodule(f"init {sub}", execution_path=self.workspace_dir)

        # clean out removed submodules
        for sub in removedModules:
            cleaned = cleanSubmodule(sub, args, workspace_dir=self.workspace_dir)

        # check to see if nested project list changed
        nestedProjectListDidChange = False
        addedProjects = set()
        removedProjects = set()
        replacedProjects = set()

        if ".grapeconfig" in git.diff(f"--name-only {startingSHA} {branch}", execution_path=self.workspace_dir):
            previousConfig = config_parser_base.GrapeConfigParserBase(
                configString=git.show(f"{startingSHA}:.grapeconfig", execution_path=self.workspace_dir))
            branchConfig = config_parser_base.GrapeConfigParserBase(
                configString=git.show(f"{branch}:.grapeconfig", execution_path=self.workspace_dir))
            previousNestedProjects = {}
            branchNestedProjects = {}
            for proj in previousConfig.getAllNestedSubprojects():
                url = previousConfig.get(f"nested-{proj}", "url")
                previousNestedProjects[proj] = url
            for proj in branchConfig.getAllNestedSubprojects():
                url = branchConfig.get(f"nested-{proj}", "url")
                branchNestedProjects[proj] = url

            # use set subtraction to figure out the removed and added projects
            previousSet = set(previousNestedProjects)
            branchSet = set(branchNestedProjects)
            removedProjects = previousSet - branchSet
            addedProjects = branchSet - previousSet

            for proj in branchSet.intersection(previousSet):
                if previousNestedProjects[proj] != branchNestedProjects[proj]:
                    replacedProjects.add(proj)

            nestedProjectListDidChange = bool(removedProjects or addedProjects or replacedProjects)

            if replacedProjects:
                okToReplace = True
                # First remove the projects that will be replaced
                for proj in replacedProjects:
                    projPrefix = previousConfig.get(f"nested-{proj}", "prefix")
                    logging.info(f"{projPrefix} URL changing from {previousNestedProjects[proj]} to {branchNestedProjects[proj]}.")
                    working_directory = os.path.join(self.workspace_dir, projPrefix)
                    if not os.path.exists(working_directory):
                        logging.info(f"{projPrefix} does not exist!")
                        okToReplace = False 
                    if git.isWorkingDirectoryClean(execution_path=working_directory):
                        replace = args["-F"] or utility.userInput(f"You will need to replace the nested subproject {projPrefix}\nAll work that has not been pushed will be lost. Proceed?", 'n')
                        if not replace:
                            logging.info(f"{projPrefix} must be replaced before proceeding!")
                            okToReplace = False 
                        else:
                            logging.info(f"Removing Nested Subproject {projPrefix}")
                            userConfig = config_parser_user.GrapeConfigParserUser(workspace_dir=self.workspace_dir)
                            rmArgs = { "-F":True, "-v":False }
                            if not UpdateView.deactivateNestedSubproject(proj, previousConfig, userConfig, self.workspace_dir, rmArgs):
                                logging.info(f"Failed to remove {projPrefix}!")
                                okToReplace = False 
                    else:
                        logging.info(f"Unstaged / committed changes in {projPrefix}, not removing.")
                        okToReplace = False 

                if not okToReplace:
                    # If the nested subproject changed URLs and we fail to replace the nested subproject, the workspace will be
                    # left in an inconsistent state (with the outer repo on the new branch, but the nested subproject on the starting branch).
                    resetLauncher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(handledCheckout,
                                                                                     listOfRepoBranchArgTuples=[(self.workspace_dir, startingBranch,
                                                                                                                 {"checkout":'',
                                                                                                                  "sync":False,
                                                                                                                  "quiet":args["-q"],
                                                                                                                  "verbose":args["-v"]})],
                                                                                     workspace_dir=self.workspace_dir)
                    logging.info(f"Cannot replace one or more nested subprojects!\nResetting outer level to {startingBranch} and exiting...")
                    resetLauncher.launchFromWorkspaceDir(handleMRE=handleCheckoutMRE)
                    return False

                # Reactivate the projects with their new URLs
                for proj in replacedProjects:
                    projPrefix = previousConfig.get(f"nested-{proj}", "prefix")
                    logging.info(f"Activating Nested Subproject {projPrefix} on {branch}")
                    userConfig = config_parser_user.GrapeConfigParserUser(workspace_dir=self.workspace_dir)
                    if not AddSubproject.activateNestedSubproject(proj, userConfig, branch, args["--filter"], self.workspace_dir):
                        logging.info(f"Failed to activate {proj}.\nExiting...")
                        return False

            if removedProjects:
                for proj in removedProjects:
                    projPrefix = previousConfig.get(f"nested-{proj}", "prefix")

                    # OK if directory does not exist as it may be removed soon.
                    working_directory = os.path.join(self.workspace_dir, projPrefix)
                    if not os.path.exists(working_directory):
                        continue

                    if git.isWorkingDirectoryClean(execution_path=working_directory):
                        removeBehaviorSet = args["--noUpdateView"] or args["--updateView"]
                        if not removeBehaviorSet:
                            remove = args["-F"] or utility.userInput(f"Would you like to remove the nested subproject {projPrefix}? \nAll work that has not been pushed will be lost. ", 'n')
                        elif args["--noUpdateView"]:
                            remove = False
                        elif args["--updateView"]:
                            remove = True
                        if remove:
                            remove = args["-F"] or utility.userInput(f"Are you sure you want to remove {projPrefix}?", 'n')
                        if remove:
                            shutil.rmtree(os.path.join(self.workspace_dir, projPrefix))
                    else:
                        if not args["-q"]:
                            logging.info(
                                f"Unstaged / committed changes in {projPrefix},"
                                " not removing. \nNote this project is NOT " +
                                f"active in {branch}. ")

        if not submodulesDidChange and not nestedProjectListDidChange:
            uvArgs.append("--checkSubprojects")
        else:
            updateViewSet = args["--noUpdateView"] or args["--updateView"]
            if not updateViewSet:
                updateView = utility.userInput("Submodules or subprojects were added/removed as a result of this checkout. \n" +
                                               "%s" % ("Added Projects: %s\n" % ','.join(addedProjects) if addedProjects else "") +
                                               "%s" % ("Added Submodules: %s\n"% ','.join(addedModules) if addedModules else "") +
                                               "%s" % ("Removed Projects: %s\n" % ','.join(removedProjects) if removedProjects else "") +
                                               "%s" % ("Removed Submodules: %s\n" % ','.join(removedModules) if removedModules else "") +
                                               "%s" % ("Replaced Projects: %s\n" % ','.join(replacedProjects) if replacedProjects else "") +
                                               "Would you like to update your workspace view? [y/n]", 'n')
            elif args["--noUpdateView"]:
                updateView = False
            elif args["--updateView"]:
                updateView = True
            if not updateView:
                uvArgs.append("--checkSubprojects")

        if args["-b"]:
            uvArgs.append("-b")
        if sync:
            uvArgs.append("--sync=True")
        else:
            uvArgs.append("--sync=False")
            uvArgs.append("--skipBranchPush")

        if args["--filter"]:
            uvArgs.append("--filter="+args["--filter"])

        # in case the user switches to a branch without corresponding branches in the submodules, make sure active submodules
        # are at the right commit before possibly creating new branches at the current HEAD.
        git.submodule("update", execution_path=self.workspace_dir)
        logging.info(f"Calling grape uv {' '.join(uvArgs)} to ensure" +
                     " branches are consistent across all active" +
                     " subprojects and submodules.")
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        menu.applyMenuChoice('uv', uvArgs)

        if sync:
            logging.info(
                f"Switched to {branch}. Updating from remote...\n\t (use"+
                " --sync=False or .grapeconfig.post-checkout.syncWithOrigin" +
                " to change behavior.)")
            if args["-b"]:
                menu.applyMenuChoice("push")
            else:
                menu.applyMenuChoice("pull")
        else:
            logging.info(f"Switched to {branch}.")

        global _skipBranchCreation
        global _createNewBranch
        _skipBranchCreation = False
        _createNewBranch = False
        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_POST_CHECKOUT)
        config.set(self.SECTION_POST_CHECKOUT, "syncWithOrigin", "True")
