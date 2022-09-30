import logging
import os
import re
import shutil
import stat
import time
from vine import config_parser_base
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine import utility
from vine.vine_logging import log_wrapper


def handledCheckout(repo='', branch='master', args=[], *, workspace_dir):
    # 'workspace_dir' included for continuity with multi_repo_cmd_launcher.
    checkoutargs = args[0]
    sync = args[1]
    if sync:
        # attempt to fetch the requested branch
        try:
            git.fetch("origin", f"{branch}:{branch}", execution_path=repo)
        except:
            # the branch may not exist, but ignore the exception
            # and allow the checkout to throw the exception.
            pass
    try:
        logging.info(f"checking out {branch} in {repo}")
        git.checkout(f"{checkoutargs} {branch}", execution_path=repo)
    except grape_errors.GrapeGitError as e:
        if "already exists" in e.gitOutput and "-b" in checkoutargs:
            logging.info(f"Reattempting checkout of previously existing branch {branch} without using a '-b' in {repo}")
            git.checkout(f"{checkoutargs.replace('-b','')} {branch}", execution_path=repo)
        if "index.lock" in e.gitOutput:
            logging.info(f"waiting for 3 seconds in {branch} in {repo} due to index.lock detection")
            time.wait(3)
            logging.info(f"retrying checkout out of {branch} in {repo}")
            git.checkout(f"{checkoutargs} {branch}", execution_path=repo)
        else:
            logging.debug(f"checkout failed in {repo}.")
            raise e
    logging.info(f"Checked out {branch} in {repo}")

    return True

_skipBranchCreation = False
_createNewBranch = False
def handleCheckoutMRE(mre):
    global _skipBranchCreation
    global _createNewBranch
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
                        " don't exist )\n(y,n,a,s)", 'y')

                if str(createNewBranch).lower()[0] == 'a':
                    _createNewBranch = True
                    createNewBranch = True
                if str(createNewBranch).lower()[0] == 's':
                    _skipBranchCreation = True
                    createNewBranch = False
                if createNewBranch:
                    newBranchReposArgTuples.append((project, branch, {"checkout": checkoutargs[0]}))
                else:
                    continue

            elif "already exists" in e.gitOutput.lower():
                logging.info(f"Branch {branch} already exists in " +
                             f"{project}.")
                branchDescription = git.commitDescription(branch, execution_path=project)
                headDescription = git.commitDescription("HEAD", execution_path=project)
                if branchDescription == headDescription:
                    logging.info(f"Branch {branch} and HEAD are the " +
                                 f"same. Switching to {branch}.")
                    action = "k"
                else:
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
                logging.info("Remote 'origin' does not exist. "
                                 "This branch was not updated from a remote repository.")
            elif e.could_not_find_remote_ref():
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

def createNewBranches(repo='', branch='', args={}, *, workspace_dir):
    #workspace_dir ignored
    checkoutargs = args["checkout"]
    logging.info(f"Checking out new branch {branch} in {repo}.")
    git.checkout(f"{checkoutargs} -b {branch}", execution_path=repo)
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
    git.fetch("--prune", execution_path=workspace_dir)
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
    submoduleListWillChange = ".gitmodules" in git.diff(f"--name-only {currentSHA} {branch}", execution_path=workspace_dir)
    if submoduleListWillChange:
        output = git.diff(f"{currentSHA} {branch} --no-ext-diff -- .gitmodules", execution_path=workspace_dir)
        currentSubmodule = False
        for line in output.split('\n'):
            if "[submodule" in line:
                currentSubmodule = line.split('"')[1]
            # This relies on the diff context being sufficient to catch the submodule line.
            # Only 2 lines of backwards context should be required, so this should be ok.
            if re.match("-\s+url\s*=", line):
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

    Usage: grape-checkout  [-b] [--sync=<bool>] [--emailSubject=<sbj>] [--updateView] [--noUpdateView] <branch>

    Options:
    -b                  Create the branch off of the current HEAD in each project.
    --sync=<bool>       Take extra steps to ensure the branch you check out is up to date with origin,
                        either by pushing or pulling the remote tracking branch.
                        [default: .grapeconfig.post-checkout.syncWithOrigin]
    --updateView        If your submodules / nested projects change, change your workspace to match the changes.
                        Warning - setting this may cause you to lose unpushed work in nested subprojects.
    --noUpdateView      If your submodules / nested projects change, do not change your workspace to match the changes.


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

        currentSHA = str(git.shortSHA(branchName="HEAD", execution_path=self.workspace_dir))

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
                    currentSHA, branch, addedModules, removedModules,
                    changedURLModules, workspace_dir=self.workspace_dir)

            if addedModules or removedModules or changedURLModules:
                submodulesDidChange = True

            # deinit and clean out any submodules that changed urls
            initiallyActiveSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            for sub in changedURLModules:
                maybe_active = "active" if sub in initiallyActiveSubmodules else "inactive"
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
                                        (checkoutargs, sync))],
            workspace_dir=self.workspace_dir)

        retvals = launcher.launchFromWorkspaceDir(handleMRE=handleCheckoutMRE)
        if not retvals or not retvals[0]:
            return False

        previousSHA = currentSHA

        # reinit any submodules with changed urls
        for sub in changedURLModules:
            if sub in initiallyActiveSubmodules:
                git.submodule(f"init {sub}", execution_path=self.workspace_dir)

        # clean out and removed submodules
        for sub in removedModules:
            cleaned = cleanSubmodule(sub, args, workspace_dir=self.workspace_dir)

        # check to see if nested project list changed
        nestedProjectListDidChange = False
        addedProjects = []
        removedProjects = []
        if ".grapeconfig" in git.diff(f"--name-only {previousSHA} {branch}", execution_path=self.workspace_dir):
            previousConfig = config_parser_base.GrapeConfigParserBase(
                configString=git.show(f"{previousSHA}:.grapeconfig", execution_path=self.workspace_dir))
            branchConfig = config_parser_base.GrapeConfigParserBase(
                configString=git.show(f"{branch}:.grapeconfig", execution_path=self.workspace_dir))
            previousNestedProjects = set(previousConfig.getAllNestedSubprojects())
            branchNestedProjects = set(branchConfig.getAllNestedSubprojects())
            # use set subtraction to figure out the removed and added projects
            removedProjects = previousNestedProjects - branchNestedProjects
            addedProjects = branchNestedProjects - previousNestedProjects
            nestedProjectListDidChange = bool(removedProjects or addedProjects)

            if removedProjects:
                for proj in removedProjects:
                    projPrefix = previousConfig.get(f"nested-{proj}", "prefix")

                    # OK if directory does not exist as it may be removed soon.
                    working_directory = os.path.join(self.workspace_dir, proj)
                    if not os.path.exists(working_directory):
                        continue

                    if git.isWorkingDirectoryClean(execution_path=working_directory):
                        removeBehaviorSet = args["--noUpdateView"] or args["--updateView"]
                        if not removeBehaviorSet:
                            remove = utility.userInput(
                                "Would you like to remove the nested " +
                                f"subproject {projPrefix}? \nAll work " +
                                "that has not been pushed will be lost. ", 'n')
                        elif args["--noUpdateView"]:
                            remove = False
                        elif args["--updateView"]:
                            remove = True
                        if remove:
                            remove = utility.userInput(
                                "Are you sure you want to remove " +
                                f"{projPrefix}? When you switch back to" +
                                " the previous branch, you will have to\n" +
                                f"reclone {projPrefix}.", 'n')
                        if remove:
                            shutil.rmtree(os.path.join(self.workspace_dir, projPrefix))
                    else:
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

        # in case the user switches to a branch without corresponding branches in the submodules, make sure active submodules
        # are at the right commit before possibly creating new branches at the current HEAD.
        git.submodule("update", execution_path=self.workspace_dir)
        logging.info(f"Calling grape uv {' '.join(uvArgs)} to ensure" +
                     " branches are consistent across all active " +
                     " subprojects and submodules.")
        config_parser_global.read(workspace_dir=self.workspace_dir)
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
